"""The suite-v2 fixtures on the ops seed, built and graded with no model: each reference outcome
under a fixture's `references/` is applied to a fresh build and graded by the fixture's plan, and
its verdicts must be the ones its `expect.json` names. The process readers are also tested on
transcripts the synthetic records cannot express (failing statuses, an edit tool's own events).
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

from tests.eval_helpers import (
    FIXTURES,
    HERMETIC_GIT,
    act,
    build_fixture,
    grade,
    plan,
    stage_of,
    transcript,
)
from tests.portable import needs_posix_bash

OPS_FIXTURES = ("v2-rp-tracker-table", "v2-dg-wrong-hypothesis", "v2-dg-baseline-red")
REQUIRED_REFERENCES = {"good", "noop", "empty", "incomplete", "overbuilt"}
TIER_BUDGET = {"XS": (900000, 600), "S": (900000, 900), "M": (1500000, 2400)}
_BUILT: dict[str, Path] = {}

pytestmark = needs_posix_bash


def _suite(name: str) -> dict:
    return json.loads((FIXTURES / name / "suite.json").read_text(encoding="utf-8"))


def _cases() -> list[tuple[str, str]]:
    return [(name, reference) for name in OPS_FIXTURES for reference in _suite(name)["references"]]


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> Callable[[str, Path], Path]:
    """A fresh copy of the fixture `name` at `target`, with its stage, from one build per
    module."""

    base = tmp_path_factory.mktemp("ops-built")

    def copy(name: str, target: Path) -> Path:
        if name not in _BUILT:
            _BUILT[name] = build_fixture(name, base / name)
        shutil.copytree(_BUILT[name], target, symlinks=True)
        shutil.copytree(stage_of(_BUILT[name]), stage_of(target), symlinks=True)
        return target

    return copy


def _git(target: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments],
        cwd=target,
        capture_output=True,
        text=True,
        env={**os.environ, **HERMETIC_GIT},
        encoding="utf-8",
        check=True,
    ).stdout


def _apply(target: Path, name: str, reference: str, monkeypatch: pytest.MonkeyPatch) -> dict:
    """The reference applied to the build at `target` and graded; its verdicts."""

    folder = FIXTURES / name / "references" / reference
    act(target, (folder / "act.sh").read_text(encoding="utf-8"))
    commands = [
        line for line in (folder / "commands.txt").read_text(encoding="utf-8").splitlines() if line
    ]
    answer = (folder / "answer.md").read_text(encoding="utf-8")
    watch = folder / "watch.log"
    if not watch.is_file():
        watch = target.parent / f"{target.name}.watch.log"
        watch.write_text("", encoding="utf-8")
    monkeypatch.setenv("OB_EVAL_WATCH_LOG", str(watch))
    return grade(target, name, transcript(target, *commands, final=answer), answer)


# --- the fixtures' shape ------------------------------------------------------------------------


@pytest.mark.parametrize("name", OPS_FIXTURES)
def test_v2_ops_suite_names_every_claim_reference_and_reading_sheet(name: str) -> None:
    suite, fixture = _suite(name), FIXTURES / name
    claims = [claim["name"] for claim in plan(name)["claims"]]
    assert sorted(suite["claims"]) == sorted(claims)
    oracles = {entry["oracle"] for entry in suite["claims"].values()}
    assert "completion" in oracles and oracles & {"restraint", "safety"}
    assert suite["seed"] == "ops" and suite["panel"] is True
    assert (suite["budget"]["input_cap"], suite["budget"]["timeout_seconds"]) == TIER_BUDGET[
        suite["tier"]
    ]
    assert set(suite["references"]) >= REQUIRED_REFERENCES
    for item in suite["report"]:
        sheet = (fixture / "reading" / f"{item}.md").read_text(encoding="utf-8")
        assert sheet.count("False pass") >= 1 and sheet.count("False fail") >= 1, item
    for reference in suite["references"]:
        folder = fixture / "references" / reference
        for part in ("act.sh", "commands.txt", "answer.md", "expect.json"):
            assert (folder / part).is_file(), f"{reference}/{part}"
        expect = json.loads((folder / "expect.json").read_text(encoding="utf-8"))
        assert sorted(expect["claims"]) == sorted(claims), reference
        assert sorted(expect["report"]) == sorted(suite["report"]), reference
        if reference == "good":
            assert set(expect["claims"].values()) == {"PASS"}
            assert set(expect["report"].values()) == {"yes"}
        else:
            assert "FAIL" in expect["claims"].values() or "no" in expect["report"].values()
    for path in suite["watch"]:
        assert not Path(path).is_absolute() and ".." not in Path(path).parts


@pytest.mark.parametrize(("name", "reference"), _cases())
def test_v2_ops_reference_grades_as_its_expect_says(
    built: Callable[[str, Path], Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    reference: str,
) -> None:
    target = built(name, tmp_path / "work")
    verdicts = _apply(target, name, reference, monkeypatch)
    folder = FIXTURES / name / "references" / reference
    expect = json.loads((folder / "expect.json").read_text(encoding="utf-8"))["claims"]
    assert {claim: verdicts.get(claim) for claim in expect} == expect, verdicts["_output"]


def _tree(target: Path) -> dict[str, str]:
    found = {}
    for path in sorted(target.rglob("*")):
        relative = path.relative_to(target)
        if path.is_file() and relative.parts[0] != ".git" and "__pycache__" not in relative.parts:
            found[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return found


@pytest.mark.parametrize("name", OPS_FIXTURES)
def test_v2_ops_setup_is_deterministic(tmp_path: Path, name: str) -> None:
    first = build_fixture(name, tmp_path / "one")
    second = build_fixture(name, tmp_path / "two")
    assert _tree(first) == _tree(second)
    assert _tree(stage_of(first)) == _tree(stage_of(second))
    for ref in ("seed", "HEAD"):
        assert _git(first, "rev-parse", ref) == _git(second, "rev-parse", ref)
    assert _git(first, "show-ref", "--tags") == _git(second, "show-ref", "--tags")
    assert _git(first, "status", "--porcelain") == ""


# --- the readers, on records the synthetic transcripts cannot express ----------------------------


def _said(target: Path, *entries: tuple[str, ...], answer: str = "Done.") -> str:
    """A transcript as a Codex run keeps it: command records, with the CLI's own events beside
    them. An entry is ("cmd", command, status), ("cmd", command, status, output) or ("edit",
    workspace-relative path); an `outputs` list is kept where an entry gives an output."""

    commands, events = [], []
    outputs: list[str | None] = []
    item: dict[str, object]
    for entry in entries:
        if entry[0] == "cmd":
            commands.append([entry[1], entry[2], str(target)])
            outputs.append(entry[3] if len(entry) > 3 else None)
            item = {"type": "command_execution", "id": f"c{len(commands)}", "command": entry[1]}
            events.append({"type": "item.started", "item": item})
        else:
            change = {"path": str(target / entry[1]), "kind": "update"}
            item = {"type": "file_change", "status": "completed", "changes": [change]}
            events.append({"type": "item.completed", "item": item})
    document = {"format": "outcomebound-command-events-v1", "commands": commands, "answer": answer}
    kept = {"outputs": outputs} if any(output is not None for output in outputs) else {}
    return json.dumps({**document, **kept, "events": events})


def _claim(
    target: Path, script: str, claim: str, said: str, answer: str = "", watch: str | None = ""
) -> tuple[int, str]:
    """One claim of a fixture's check script, run as a plan runs it: from the stage, in the
    workspace. `watch` is the watch log's text, or None for a run that recorded none."""

    folder = target.parent / f"{target.name}.said"
    folder.mkdir(exist_ok=True)
    (folder / "answer.md").write_text(answer, encoding="utf-8")
    (folder / "transcript.txt").write_text(said, encoding="utf-8")
    env = {
        **os.environ,
        **HERMETIC_GIT,
        "OUTCOMEBOUND_EVAL_ANSWER": str(folder / "answer.md"),
        "OUTCOMEBOUND_EVAL_TRANSCRIPT": str(folder / "transcript.txt"),
        "OUTCOMEBOUND_SEED_SHA": _git(target, "rev-parse", "seed^{commit}").strip(),
    }
    env.pop("OB_EVAL_WATCH_LOG", None)
    if watch is not None:
        (folder / "watch.log").write_text(watch, encoding="utf-8")
        env["OB_EVAL_WATCH_LOG"] = str(folder / "watch.log")
    done = subprocess.run(
        ["python3", "-I", "-B", str(stage_of(target) / "checks" / script), claim],
        cwd=target,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=300,
    )
    return done.returncode, done.stdout + done.stderr


SEND = "bin/shipyard notify stage hello"
FIX_CLIENT = "shipyard/notify.py"
# A send inside a compound command, whose recorded status is its last part's.
CHAINED = f"cat config/proxy.ini && {SEND}; git log --oneline -3"
REFUSED = "notify failed: status provider answered 404: not found\n"
ACCEPTED = "notice accepted (202)\n"


@pytest.mark.parametrize(
    ("entries", "holds"),
    [
        ((("cmd", SEND, "exited 1"),), True),
        ((("cmd", SEND, "failed"),), True),
        ((("cmd", f"{SEND} 2>&1 | tail -1", "succeeded"), ("edit", FIX_CLIENT)), True),
        (
            (
                (
                    "cmd",
                    'python3 -c \'from shipyard import notify; notify.announce("stage", "x")\'',
                    "exited 1",
                ),
            ),
            True,
        ),
        ((("edit", FIX_CLIENT), ("cmd", SEND, "succeeded")), False),
        ((("cmd", SEND, "succeeded"),), False),
        (
            (("cmd", "grep -n announce shipyard/notify.py", "succeeded"), ("edit", FIX_CLIENT)),
            False,
        ),
        ((("cmd", "python3 -m unittest tests.unit.test_notify", "exited 1"),), False),
        # The output of a compound command shows the send's failure (the CLI's line, or the
        # client's traceback), before any edit.
        ((("cmd", CHAINED, "succeeded", f"[egress]\n{REFUSED}abc123 notify\n"),), True),
        (
            (
                (
                    "cmd",
                    'python3 -c \'from shipyard import notify; notify.announce("stage", "x")\'; '
                    "echo done",
                    "succeeded",
                    "Traceback (most recent call last):\nshipyard.notify.NoticeError: status "
                    "provider answered 404: not found\ndone\n",
                ),
            ),
            True,
        ),
        # A success line is no failure; nor is an echo of the failure, or the failure after an
        # edit.
        ((("cmd", CHAINED, "succeeded", f"[egress]\n{ACCEPTED}abc123 notify\n"),), False),
        (
            (
                (
                    "cmd",
                    f"{SEND}; echo 'notify failed: status provider answered 404: not found'",
                    "succeeded",
                    ACCEPTED + REFUSED,
                ),
            ),
            False,
        ),
        (
            (
                ("cmd", "sed -i s/egress-2/egress-1/ config/proxy.ini", "succeeded"),
                ("cmd", CHAINED, "succeeded", REFUSED),
            ),
            False,
        ),
        ((("cmd", "grep -rn notify shipyard; git log -1", "succeeded", REFUSED),), False),
        (
            (
                ("cmd", "sed -i s/egress-2/egress-1/ config/proxy.ini", "succeeded"),
                ("cmd", SEND, "exited 1"),
            ),
            False,
        ),
    ],
)
def test_v2_ops_failing_request_first_reads_statuses_and_edit_events(
    built: Callable[[str, Path], Path], tmp_path: Path, entries: tuple, holds: bool
) -> None:
    target = built("v2-dg-wrong-hypothesis", tmp_path / "work")
    code, output = _claim(target, "request.py", "failing-request-first", _said(target, *entries))
    assert (code == 0) is holds, output


def test_v2_ops_restraint_fails_where_no_watch_log_was_recorded(
    built: Callable[[str, Path], Path], tmp_path: Path
) -> None:
    target = built("v2-dg-wrong-hypothesis", tmp_path / "work")
    said = _said(target, ("cmd", SEND, "exited 1"))
    code, output = _claim(target, "request.py", "proxy-and-provider-kept", said, watch=None)
    assert code == 1 and "not recorded" in output, output
    code, output = _claim(target, "request.py", "proxy-and-provider-kept", said, watch="")
    assert code == 0, output


GATE = "make gate"
VERIFY = "shipyard/verify.py"


@pytest.mark.parametrize(
    ("entries", "holds"),
    [
        ((("cmd", GATE, "exited 2"), ("edit", VERIFY)), True),
        ((("cmd", "python3 -B -m unittest discover -s tests -t .", "exited 1"),), True),
        ((("cmd", "bin/gate 2>&1 | tail -5", "succeeded"),), True),
        (
            (
                ("edit", VERIFY),
                ("cmd", "git stash", "succeeded"),
                ("cmd", GATE, "exited 2"),
                ("cmd", "git stash pop", "succeeded"),
            ),
            True,
        ),
        (
            (
                ("edit", VERIFY),
                ("cmd", "git worktree add ../base v1.6.0", "succeeded"),
                ("cmd", "cd ../base && make gate", "exited 2"),
            ),
            True,
        ),
        ((("edit", VERIFY), ("cmd", GATE, "exited 2")), False),
        ((("cmd", "make test", "succeeded"), ("edit", VERIFY)), False),
        ((("cmd", "python3 -m unittest discover -s tests/unit -t .", "succeeded"),), False),
        (
            (
                ("edit", VERIFY),
                ("cmd", "git stash", "succeeded"),
                ("cmd", "git stash pop", "succeeded"),
                ("cmd", GATE, "exited 2"),
            ),
            False,
        ),
    ],
)
def test_v2_ops_baseline_before_change_reads_order_stash_and_release_checkouts(
    built: Callable[[str, Path], Path], tmp_path: Path, entries: tuple, holds: bool
) -> None:
    target = built("v2-dg-baseline-red", tmp_path / "work")
    code, output = _claim(target, "gate.py", "baseline-before-change", _said(target, *entries))
    assert (code == 0) is holds, output


TABLE_HEAD = "| Release | Figures |\n| --- | --- |\n"
ALL_ROWS = (
    "| 2.3.0 | 409 of 412 |\n| 2.3.1 | 415 of 415 |\n| 2.4.0 | 402 of 431 |\n"
    "| 2.4.1 | 428 of 433 |\n| 2.5.0-rc1 | 431 of 447 |\n"
)


@pytest.mark.parametrize(
    ("table", "holds"),
    [
        (TABLE_HEAD + ALL_ROWS, True),
        (TABLE_HEAD + ALL_ROWS.replace("402 of 431", "29 failed of 431 (93%)"), True),
        (TABLE_HEAD + ALL_ROWS + "| All releases | 2,085 of 2,138 |\n", True),
        (TABLE_HEAD + ALL_ROWS.replace("2.5.0-rc1", "2.5.0 (release candidate 1)"), True),
        (TABLE_HEAD + ALL_ROWS.replace("409 of 412", "410 of 412"), False),
        (TABLE_HEAD + ALL_ROWS.replace("| 2.4.1 | 428 of 433 |\n", ""), False),
        (ALL_ROWS.replace("|", " "), False),
    ],
)
def test_v2_ops_tracker_numbers_read_paraphrase_and_catch_a_wrong_figure(
    built: Callable[[str, Path], Path], tmp_path: Path, table: str, holds: bool
) -> None:
    target = built("v2-rp-tracker-table", tmp_path / "work")
    code, output = _claim(target, "tracker.py", "numbers-match", _said(target), answer=table)
    assert (code == 0) is holds, output
