"""The two continuity fixtures through the runner's own path: the build, the seal of the grading
stage, a simulated agent that acts in the workspace, the check that the stage is as sealed, and
the judging. The release check of these fixtures is a process that logs what it is asked while the
call runs; the log has to reach the checks without a change to the sealed stage. No test here calls
a model.

The tests that grade a reference or a control (`test_v2_effect_fixtures.py`) skip the runner's
seal, which is how a log written into the stage once failed every real run.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import subprocess
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

from evals.harnesses import CallResult, Request
from tests.eval_helpers import HERMETIC_GIT, ROOT, RUN, transcript
from tests.portable import needs_posix_bash

pytestmark = needs_posix_bash

RELAY = ROOT / "evals" / "fixtures" / "seeds" / "relay"
NAMES = ("v2-ck-continuity-pending", "v2-ck-continuity-passed")
# The agent's work, in the steps of the references: a look, both items, their commits, the wait for
# the pass, the release record and its commit.
WORK = f"""set -euo pipefail
. {RELAY}/reference.sh
relay_status
relay_code
relay_doc
relay_commit_items
relay_wait_passed
relay_record
"""
COMMANDS = ("python3 tools/check_status.py", "python3 tools/release.py", "git commit")
ANSWER = "Done. Both items are committed, the check had passed, and RELEASE_RECORD is committed.\n"


class Agent:
    """A stand-in harness: `call` runs `script` in the workspace as the agent's commands, after
    `before` (given the workspace, the stage and the request), and records what it was given."""

    name = "codex"

    def __init__(
        self,
        script: str,
        stage: Callable[[], Path],
        before: Callable[[Path, Path, Request], None] | None = None,
    ):
        self.script, self.stage, self.before = script, stage, before
        self.request: Request | None = None
        self.cwd: Path | None = None

    def call(self, _prompt, request, cwd, _roots, _path, _keep):
        self.request, self.cwd = request, cwd
        if self.before:
            self.before(cwd, self.stage(), request)
        env = {**RUN.child_env(), **HERMETIC_GIT}
        subprocess.run(
            ["bash", "-c", self.script], cwd=cwd, env=env, check=True, timeout=120,
            capture_output=True,
        )  # fmt: skip
        return CallResult(ANSWER, transcript(cwd, *COMMANDS, final=ANSWER), 0, None, {}, "", [])


@pytest.fixture
def made(monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, Any]]:
    """The stages the runner makes and the check processes its builds start, with the check's
    delay set to four seconds; every process is ended at the end of the test."""

    record: dict[str, Any] = {"stages": [], "pids": []}
    setup_env, new_stage, bounded = RUN.fixture_setup_env, RUN.new_stage, RUN.bounded_command
    monkeypatch.setattr(
        RUN, "fixture_setup_env", lambda: {**setup_env(), "OB_EVAL_CHECK_DELAY": "4"}
    )

    def stage(*arguments, **keywords):
        record["stages"].append(new_stage(*arguments, **keywords))
        return record["stages"][-1]

    def command(*arguments, **keywords):
        done = bounded(*arguments, **keywords)
        record["pids"] += [
            int(pid) for pid in re.findall(r"check started: process (\d+)", done.stdout)
        ]
        return done

    monkeypatch.setattr(RUN, "new_stage", stage)
    monkeypatch.setattr(RUN, "bounded_command", command)
    yield record
    with contextlib.suppress(OSError):
        for pid in record["pids"]:
            os.kill(pid, 9)


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    # A process that ended but that no parent reaped (a container whose first process does not
    # reap orphans) still answers the signal; its state in /proc is Z.
    stat = Path(f"/proc/{pid}/stat")
    try:
        return stat.read_text(encoding="utf-8").rsplit(")", 1)[1].split()[0] != "Z"
    except (OSError, IndexError):
        return True


def _run(base: Path, name: str, agent: Agent) -> tuple[tuple[str, str, int | None, dict], Path]:
    workspace = base / name
    arm = RUN.fixture_arm(name, RUN.load_arm("current", RUN.selected_fragments(name)))
    path = RUN.child_env().get("PATH", os.defpath)
    done = RUN.run_fixture(
        name, Request("m", "medium"), arm, path, agent, RUN.Place(workspace=workspace)
    )
    return done, workspace


@pytest.mark.parametrize("name", NAMES)
def test_a_run_that_does_the_work_passes_every_claim_with_the_stage_as_sealed(
    tmp_path: Path, made: dict[str, Any], name: str
) -> None:
    """The check logs each look while the call runs. The seal of the grading stage is checked
    after the call: the log must not be in the stage, and the order claim must still read it."""

    agent = Agent(WORK, lambda: made["stages"][-1])
    (_answer, report, _code, extra), workspace = _run(tmp_path, name, agent)

    assert RUN.fixture_suite(name).observe is True
    assert extra.get("error") is None, report[-1500:]
    assert extra["protected_intact"] is True, report[-1500:]
    assert "FAIL protected-grading-inputs" not in report
    claims = extra["claims"]
    assert claims and set(claims.values()) == {"PASS"}, (claims, report[-2500:])
    assert extra["verdict"] == "PASS"
    assert ("independent-work-first" in claims) == (name == "v2-ck-continuity-pending")

    # The log is outside the stage, hidden from the call, and kept as the meta says.
    stage = made["stages"][-1]
    assert not list(stage.rglob("reads.jsonl")), "the check logged into the sealed stage"
    assert agent.request is not None
    hidden = [str(path) for path in agent.request.unreadable]
    live = f"{workspace}.observed{RUN.LIVE_SUFFIX}"
    assert live in hidden and str(stage) in hidden
    kept = Path(extra["observed_dir"])
    assert kept == Path(f"{workspace}.observed") and not Path(live).exists()
    assert extra["observed_sha256"] == RUN.tree_digest(kept)
    rows = [
        json.loads(line) for line in (kept / "reads.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert rows[-1]["served"] == "passed" and rows[0]["served"] == (
        "pending" if name == "v2-ck-continuity-pending" else "passed"
    )

    # A regrade finds the folder from the meta, and the check ended with its stage.
    assert RUN.kept_records(extra).observed == kept
    assert all(not _alive(pid) or _wait_gone(pid) for pid in made["pids"])


def _wait_gone(pid: int) -> bool:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if not _alive(pid):
            return True
        time.sleep(0.1)
    return False


def test_a_change_of_the_stage_during_the_call_still_fails_the_run(
    tmp_path: Path, made: dict[str, Any]
) -> None:
    """The log does not exempt the stage: a file the call adds there fails the seal."""

    def tamper(_cwd: Path, stage: Path, _request: Request) -> None:
        assert stage.stat().st_mode & 0o7777 == 0
        stage.chmod(0o700)
        try:
            (stage / "checks" / "reads.jsonl").write_text(
                '{"t": 1, "served": "pending"}\n', encoding="utf-8"
            )
        finally:
            stage.chmod(0)

    agent = Agent(WORK, lambda: made["stages"][-1], tamper)
    (_answer, report, _code, extra), _workspace = _run(tmp_path, NAMES[0], agent)
    assert extra["protected_intact"] is False
    assert "FAIL protected-grading-inputs" in report and "stage/checks/reads.jsonl" in report
    assert extra["verdict"] == "FAIL"


def test_a_line_written_into_the_log_by_the_call_is_not_believed(
    tmp_path: Path, made: dict[str, Any]
) -> None:
    """A run that finds the folder and appends a late `passed` line, to make its waiting look
    like work first, fails the order claim: the lines carry marks only the check can make."""

    def forge(_cwd: Path, _stage: Path, request: Request) -> None:
        live = next(path for path in request.unreadable if path.name.endswith(RUN.LIVE_SUFFIX))
        later = json.dumps(
            {"t": time.time() + 3600, "kind": "status", "served": "passed", "mac": "0"}
        )
        live.joinpath("reads.jsonl").open("a", encoding="utf-8").write(later + "\n")

    agent = Agent(WORK, lambda: made["stages"][-1], forge)
    (_answer, report, _code, extra), _workspace = _run(tmp_path, NAMES[0], agent)
    assert extra["protected_intact"] is True
    assert extra["claims"]["independent-work-first"] == "FAIL", report[-1500:]
    assert "does not verify" in report


TRUNCATING_TEST = """
    def test_truncates_the_log(self):
        import os
        from pathlib import Path

        if directory := os.environ.get("OB_EVAL_OBSERVED"):
            log = Path(directory) / "reads.jsonl"
            os.chmod(log, 0o644)
            log.write_text(log.read_text("utf-8").splitlines()[0] + "\\n", "utf-8")
"""
WAIT_FIRST = f"""set -euo pipefail
. {RELAY}/reference.sh
relay_status
relay_wait_passed
relay_code
relay_doc
cat >> tests/test_slug.py <<'PY'
{TRUNCATING_TEST}PY
relay_commit_items
relay_record
"""


def test_a_submitted_test_that_truncates_the_log_fails_the_run(
    tmp_path: Path, made: dict[str, Any]
) -> None:
    """A run that waits for the check before the work, and commits a test that cuts the log back
    to its first (pending) line: the chain still verifies the prefix, and without a logged pass
    the order claim would read the work as done first. The runner's digest of the kept folder,
    taken again after the post-checks, fails the run with its own reason."""

    agent = Agent(WAIT_FIRST, lambda: made["stages"][-1])
    (_answer, report, _code, extra), _workspace = _run(tmp_path, NAMES[0], agent)
    assert extra["verdict"] == "FAIL", report[-2000:]
    assert "observed evidence changed during grading" in report
    assert RUN.tree_digest(Path(extra["observed_dir"])) != extra["observed_sha256"]
