"""The runner's support for the replica fixtures, with no model call.

A replica fixture's `install.json` sets the Done commands its install records, the fragments it
selects and the sandbox of its call; `--dump-arm` shows what one arm's call would receive; the
`none` arm reaches no `outcomebound` and a replica run refuses a Codex home that would give a call
the operator's instructions or skills; each run keeps what its call spent. Every fixture here is
a fake one in a temporary folder, and every codex is a fake that records being started.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from evals.codex_events import session_tokens
from evals.harnesses import CallResult, Request
from evals.harnesses import codex as codex_harness
from outcomebound_tools import adopt
from tests.eval_helpers import RUN
from tests.portable import needs_posix_bash

pytestmark = needs_posix_bash

NOTE = "# Team notes\n\nStack: Python. `make test` runs the unit tests (a few seconds).\n"
SETUP = """#!/usr/bin/env bash
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
target="${1:?}"; stage="${2:?}"
mkdir -p "$target" "$stage/checks"
cd "$target"
cat > AGENTS.md <<'NOTE'
@NOTE@
NOTE
printf 'test:\\n\\t@true\\ncheck:\\n\\t@true\\n' > Makefile
git init -q
git add -A
git -c user.name=t -c user.email=t@example.invalid commit -q -m seed
git tag seed
""".replace("@NOTE@", NOTE.rstrip("\n"))
PLAN = {
    "version": 1,
    "cwd": ".",
    "timeout_seconds": 60,
    "claims": [
        {"name": "always", "risk": "none", "kind": "static", "required": True, "command": ["true"]}
    ],
}
INSTALL = {"done": ["make check", "make test"], "fragments": ["commands"], "sandbox": "eval"}
# The fragments the replica fixtures select, `workspace` among them (it writes .agents/.gitignore).
FIELD_FRAGMENTS = ["commands", "workspace", "multi-agent", "research", "python"]
TOKENS = {
    "input_tokens": 1000,
    "cached_input_tokens": 800,
    "output_tokens": 50,
    "reasoning_output_tokens": 20,
}


def _fixture(
    root: Path, name: str = "replica-fake", install: dict[str, Any] | str | None = None
) -> Path:
    """A fake fixture under `root/evals/fixtures`, with `install` as its install.json (a string
    is written as it is), and the folder that holds the fixtures."""

    fixture = root / "evals" / "fixtures" / name
    fixture.mkdir(parents=True)
    (fixture / "setup.sh").write_text(SETUP, encoding="utf-8")
    (fixture / "prompt.md").write_text("Record the release in the changelog.\n", encoding="utf-8")
    (fixture / "protected.paths").write_text("Makefile\n", encoding="utf-8")
    (fixture / "post.plan.json").write_text(json.dumps(PLAN), encoding="utf-8")
    if install is not None:
        text = install if isinstance(install, str) else json.dumps(install)
        (fixture / "install.json").write_text(text, encoding="utf-8")
    return fixture.parent


def _fake_codex(bindir: Path, calls: Path) -> None:
    """A codex that records every start in `calls` and does nothing else."""

    bindir.mkdir(parents=True, exist_ok=True)
    (bindir / "codex").write_text(f'#!/bin/sh\necho "$*" >> "{calls}"\nexit 9\n', "utf-8")
    (bindir / "codex").chmod(0o755)


def _launcher(bindir: Path) -> Path:
    """A folder holding an `outcomebound` and another command, as an operator's own bin."""

    bindir.mkdir(parents=True)
    for name in ("outcomebound", "othertool"):
        (bindir / name).write_text("#!/bin/sh\necho ran\n", encoding="utf-8")
        (bindir / name).chmod(0o755)
    return bindir


def _home(root: Path, dirty: bool) -> Path:
    """A Codex home holding codex's own skills and, where `dirty`, an operator's instruction file,
    skill and agent role."""

    home = root / "codex-home"
    (home / "skills" / ".system" / "imagegen").mkdir(parents=True)
    if dirty:
        (home / "AGENTS.md").write_text("", encoding="utf-8")
        (home / "skills" / "pdf").mkdir()
        (home / "agents").mkdir()
        (home / "agents" / "role.toml").write_text("", encoding="utf-8")
    return home


@pytest.fixture
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    """This process's PATH with a fake codex and an operator's `outcomebound`, a clean Codex
    home, and no skill folders outside it."""

    calls = tmp_path / "codex-calls.txt"
    _fake_codex(tmp_path / "fakebin", calls)
    operator = _launcher(tmp_path / "operator-bin")
    path = os.pathsep.join([str(tmp_path / "fakebin"), str(operator), os.environ["PATH"]])
    monkeypatch.setenv("PATH", path)
    monkeypatch.setenv("CODEX_HOME", str(_home(tmp_path, dirty=False)))
    monkeypatch.setattr(RUN, "OUTSIDE_SKILLS", ())
    return {"calls": calls, "operator": operator}


def _build(name: str, arm: Any, root: Path) -> tuple[Path, str]:
    """The fixture built under `arm` as a run builds it; its workspace and prompt."""

    workdir = root / "workspace"
    workdir.mkdir(parents=True)
    stage = root / "stage"
    stage.mkdir()
    extra: dict[str, Any] = {}
    failure, _protected, _seed, prompt = RUN.build_workspace(name, arm, workdir, extra, stage)
    assert failure is None, (failure, extra)
    return workdir, prompt


def _block(text: str, block: str) -> str:
    found = re.search(
        rf"<!-- outcomebound:begin id={block} .*?<!-- outcomebound:end id={block} -->", text, re.S
    )
    assert found, text
    return found.group(0)


# --- install.json ------------------------------------------------------------------------


def test_runner_install_json_is_read_whole(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(RUN, "FIXTURES", _fixture(tmp_path, install=INSTALL))
    assert RUN.fixture_install("replica-fake") == RUN.Install(
        ("make check", "make test"), ("commands",), "eval", True
    )


def test_runner_a_fixture_without_install_json_keeps_todays_install(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixtures = _fixture(tmp_path)
    (fixtures / "replica-fake" / "fragments").write_text("commands\n", encoding="utf-8")
    monkeypatch.setattr(RUN, "FIXTURES", fixtures)
    assert RUN.fixture_install("replica-fake") == RUN.Install((), ("commands",), "eval")


@pytest.mark.parametrize(
    ("install", "reason"),
    [
        ("{not json", "not readable JSON"),
        ("[]", "exactly done, fragments, sandbox"),
        ({"done": [], "fragments": []}, "exactly done, fragments, sandbox"),
        ({**INSTALL, "extra": 1}, "exactly done, fragments, sandbox"),
        ({**INSTALL, "done": "make test"}, "done is a list of strings"),
        ({**INSTALL, "done": ["make test", 3]}, "done is a list of strings"),
        ({**INSTALL, "done": [""]}, "not one line"),
        ({**INSTALL, "done": [" make test"]}, "not one line"),
        ({**INSTALL, "done": ["make test\nmake check"]}, "not one line"),
        ({**INSTALL, "done": ["make test", "make test"]}, "names an item twice"),
        ({**INSTALL, "done": ["make test <!-- x"]}, "comment opener"),
        ({**INSTALL, "fragments": ["no-such-fragment"]}, "no-such-fragment"),
        ({**INSTALL, "sandbox": "loose"}, "sandbox is eval or field"),
    ],
)
def test_runner_a_bad_install_json_refuses_the_run_before_any_model_call(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    isolated: dict[str, Path],
    install: Any,
    reason: str,
) -> None:
    """Breaks if a malformed install.json is read leniently, or if the refusal comes after a
    codex start (preflight included) or after the run directory is made."""

    monkeypatch.setattr(RUN, "FIXTURES", _fixture(tmp_path, install=install))
    with pytest.raises(RUN.InstallError, match=re.escape(reason)):
        RUN.fixture_install("replica-fake")
    out = tmp_path / "out"
    arguments = ["--arm", "current", "--model", "m", "--fixtures", "replica-fake"]
    with pytest.raises(SystemExit) as stopped:
        RUN._main([*arguments, "--out", str(out)])
    assert stopped.value.code == 2
    assert "replica-fake/install.json" in capsys.readouterr().err
    assert not isolated["calls"].exists() and not out.exists()


def test_runner_install_json_and_a_fragments_file_together_are_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixtures = _fixture(tmp_path, install=INSTALL)
    (fixtures / "replica-fake" / "fragments").write_text("commands\n", encoding="utf-8")
    monkeypatch.setattr(RUN, "FIXTURES", fixtures)
    with pytest.raises(RUN.InstallError, match="both name fragments"):
        RUN.fixture_install("replica-fake")


DATE = re.compile(rb"\d{4}-\d{2}-\d{2}(?:[T ][\d:.]+(?:Z|[+-]\d{2}:?\d{2})?)?")


def _files(root: Path) -> dict[str, bytes]:
    """Every file under `root` outside `.git`, by relative path, with any date blanked."""

    return {
        path.relative_to(root).as_posix(): DATE.sub(b"<date>", path.read_bytes())
        for path in sorted(root.rglob("*"))
        if path.is_file() and ".git" not in path.relative_to(root).parts
    }


def _git(workdir: Path, *arguments: str) -> str:
    env = {**os.environ, **RUN.HERMETIC_GIT}
    done = subprocess.run(
        ["git", *arguments],
        cwd=workdir,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        check=True,
    )
    return done.stdout


def test_runner_the_current_arm_is_what_adopt_installs_in_the_field(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Breaks if, for a fixture with an install.json, the current arm's workspace differs from
    what `outcomebound adopt --harness codex --fragments ... --done ...` makes of the same
    project (dates aside): the kernel in AGENTS.md, the facts and pointers blocks, the skills,
    the fragments, `.agents/.gitignore` and `.outcomebound/manifest.json`; or if the install is
    not folded into the seed commit; or if the Done commands reach the none arm."""

    fixtures = _fixture(tmp_path, install={**INSTALL, "fragments": FIELD_FRAGMENTS})
    monkeypatch.setattr(RUN, "FIXTURES", fixtures)
    chosen = RUN.fixture_install("replica-fake")
    arm = RUN.load_arm("current", chosen.fragments, chosen.done, chosen.adopted)
    assert arm.adopted and arm.record()["arm_done"] == ["make check", "make test"]
    workdir, _prompt = _build("replica-fake", arm, tmp_path / "eval")

    field = tmp_path / "field"
    subprocess.run(
        ["bash", str(fixtures / "replica-fake" / "setup.sh"), str(field), str(tmp_path / "s")],
        check=True,
        capture_output=True,
    )
    flags = ["--harness", "codex", "--fragments", ",".join(chosen.fragments)]
    code = adopt.main(
        [str(field), *flags, "--done", "make check", "--done", "make test"], source=RUN.REPO
    )
    capsys.readouterr()
    assert code == 0
    installed, adopted = _files(workdir), _files(field)
    assert sorted(installed) == sorted(adopted)
    assert installed == adopted
    for path in (
        ".agents/.gitignore",
        ".outcomebound/manifest.json",
        ".agents/skills/diagnose/SKILL.md",
    ):
        assert path in installed, path
    agents = (workdir / "AGENTS.md").read_text(encoding="utf-8")
    assert "<!-- outcomebound:begin id=operating-contract" in agents
    assert (
        "- Done: `make check` and `make test`"
        " (the full suite: run it where the change reaches what it tests)"
    ) in agents
    assert _git(workdir, "status", "--porcelain") == ""
    assert _git(workdir, "rev-parse", "HEAD") == _git(workdir, "rev-parse", "seed^{commit}")
    assert ".outcomebound/manifest.json" in _git(workdir, "ls-files").split()

    none = RUN.load_arm("none", chosen.fragments, chosen.done, chosen.adopted)
    plain, _prompt = _build("replica-fake", none, tmp_path / "none")
    assert (plain / "AGENTS.md").read_text(encoding="utf-8").strip() == NOTE.strip()


def test_runner_the_current_and_none_prompts_are_the_task_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Breaks if the adopted current arm's prompt still carries the kernel, or differs from the
    none arm's; a fixture with no install.json keeps the kernel in its prompt, as before."""

    fixtures = _fixture(tmp_path, install=INSTALL)
    shutil.copytree(fixtures / "replica-fake", fixtures / "plain")
    (fixtures / "plain" / "install.json").unlink()
    monkeypatch.setattr(RUN, "FIXTURES", fixtures)
    prompts = {}
    for name in ("current", "none"):
        arm = RUN.fixture_arms(RUN._parser(), name, ["replica-fake"])["replica-fake"]
        prompts[name] = _build("replica-fake", arm, tmp_path / name)[1]
    assert prompts["current"] == prompts["none"]
    assert prompts["none"] == "Task:\nRecord the release in the changelog.\n"
    plain = RUN.fixture_arms(RUN._parser(), "current", ["plain"])["plain"]
    assert not plain.adopted
    assert _build("plain", plain, tmp_path / "plain")[1].startswith(plain.kernel)


# --- the field sandbox ---------------------------------------------------------------------


def _argv(tmp_path: Path, sandbox: str) -> list[str]:
    workspace = tmp_path / sandbox
    workspace.mkdir()
    subprocess.run(["git", "init", "-q", str(workspace)], check=True)
    request = Request("m", "medium", False, sandbox)
    return RUN.make_harness().argv(request, workspace, tmp_path / "last.md")


def test_runner_a_field_call_is_not_granted_the_task_note_folder(tmp_path: Path) -> None:
    """Breaks if the field sandbox still grants `.agents/work`, or takes `.git` away."""

    def grants(argv: list[str]) -> list[str]:
        return [Path(argv[i + 1]).name for i, arg in enumerate(argv) if arg == "--add-dir"]

    assert grants(_argv(tmp_path, "eval")) == [".git", "work"]
    assert grants(_argv(tmp_path, "field")) == [".git"]
    with pytest.raises(ValueError, match="no sandbox 'loose'"):
        _argv(tmp_path, "loose")


def _session(tmp_path: Path, roots: list[str] | None) -> tuple[str, Path, Path]:
    """A stream and a native session of one call in `tmp_path/ws`, whose sandbox grants
    `roots` (None: the record names no writable roots)."""

    key = "0192f0aa-1111-7222-8333-444455556666"
    cwd = tmp_path / "ws"
    cwd.mkdir()
    policy: dict[str, Any] = {"type": "workspace-write", "network_access": False}
    if roots is not None:
        policy["writable_roots"] = roots
    records = [
        {"type": "session_meta", "payload": {"id": key, "cwd": str(cwd), "cli_version": "0.163.0"}},
        {
            "type": "turn_context",
            "payload": {
                "cwd": str(cwd),
                "model": "m",
                "effort": "medium",
                "sandbox_policy": policy,
            },
        },
    ]
    day = tmp_path / "sessions" / "2026" / "10" / "21"
    day.mkdir(parents=True)
    text = "".join(json.dumps(record) + "\n" for record in records)
    (day / f"rollout-2026-10-21T00-00-00-{key}.jsonl").write_text(text, encoding="utf-8")
    stdout = json.dumps({"type": "thread.started", "thread_id": key}) + "\n"
    return stdout, tmp_path / "sessions", cwd


@pytest.mark.parametrize(
    ("roots", "verdict"),
    [
        (["{cwd}/.git"], "PASS"),
        (["{cwd}/.git", "{cwd}/.agents/work"], "FAIL"),
        (["{cwd}/.agents"], "FAIL"),
        (None, "FAIL"),
    ],
)
def test_runner_a_field_call_counts_only_where_its_session_shows_no_task_note_grant(
    tmp_path: Path, roots: list[str] | None, verdict: str
) -> None:
    cwd = tmp_path / "ws"
    filled = [root.format(cwd=cwd) for root in roots] if roots is not None else None
    stdout, sessions, cwd = _session(tmp_path, filled)
    request = Request("m", "medium", False, "field")
    _observed, _extras, checks, _records = codex_harness.identify(
        stdout, sessions, tmp_path / "kept.jsonl", request, cwd
    )
    found = {item: result for item, result, _detail in checks}
    assert found["native-field-sandbox"] == verdict, checks
    eval_checks = codex_harness.identify(
        stdout, sessions, tmp_path / "kept-eval.jsonl", Request("m", "medium"), cwd
    )[2]
    assert "native-field-sandbox" not in {item for item, _result, _detail in eval_checks}


class Recorder:
    """A harness that records each request and answers at once, with the cost a session kept."""

    name = "codex"

    def __init__(self) -> None:
        self.requests: list[Request] = []

    def call(self, _prompt, request, _cwd, _roots, _path, _keep):
        self.requests.append(request)
        extras = {"session_tokens": {**TOKENS, "source": "native"}}
        return CallResult("done", "", 0, {"model": request.model}, extras, "", [])


def test_runner_a_field_fixture_asks_its_call_for_the_field_sandbox_and_records_its_cost(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Breaks if install.json's sandbox does not reach the harness, or if a run's meta and its
    printed line lose what its session spent."""

    monkeypatch.setattr(
        RUN, "FIXTURES", _fixture(tmp_path, install={**INSTALL, "sandbox": "field"})
    )
    harness = Recorder()
    out = tmp_path / "out"
    out.mkdir()
    status = {
        "model": "m",
        "effort": "medium",
        "repetition": 1,
        "workspace_root": None,
        "harness": "codex",
        "arm": "none",
    }
    failed, _row = RUN.run_one(out, status, "replica-fake", RUN.load_arm("none"), "", harness)
    assert not failed
    assert [request.sandbox for request in harness.requests] == ["field"]
    meta = json.loads((out / "replica-fake.meta.json").read_text(encoding="utf-8"))
    assert meta["session_tokens"] == {**TOKENS, "source": "native"}
    assert isinstance(meta["elapsed_seconds"], float)
    printed = capsys.readouterr().out
    assert "replica-fake: PASS" in printed
    assert "input 1000 (cached 800), output 50 (reasoning 20) tokens" in printed


# --- the arm isolation audit ----------------------------------------------------------------


def test_runner_no_outcomebound_but_the_arms_own_is_on_a_calls_path(
    tmp_path: Path, isolated: dict[str, Path]
) -> None:
    """Breaks if the operator's `outcomebound` reaches the none arm, if the current arm reaches
    any but its own, or if another command of the same folder stops resolving."""

    none = RUN.call_path(RUN.load_arm("none"), str(tmp_path))
    assert shutil.which("outcomebound", path=none) is None
    other = shutil.which("othertool", path=none)
    assert other and Path(other).resolve() == (isolated["operator"] / "othertool").resolve()
    assert RUN.launchers(none) == []
    current = RUN.load_arm("current")
    reached = RUN.launchers(RUN.call_path(current, str(tmp_path)))
    assert [item.rsplit(" -> ", 1)[1] for item in reached] == [os.path.realpath(current.launcher)]


def test_runner_a_codex_homes_instructions_skills_and_roles_are_found(tmp_path: Path) -> None:
    home = _home(tmp_path, dirty=True)
    assert sorted(Path(item).name for item in RUN.home_leaks(home)) == [
        "AGENTS.md",
        "pdf",
        "role.toml",
    ]
    clean = _home(tmp_path / "clean", dirty=False)
    assert RUN.home_leaks(clean) == [], "codex's own bundled skills are the harness's"


def _guiding(home: Path) -> None:
    """Give the home an instruction file with text and a skill that names OutcomeBound."""

    (home / "AGENTS.md").write_text("Always plan first.\n", encoding="utf-8")
    (home / "skills" / "planner").mkdir()
    (home / "skills" / "planner" / "SKILL.md").write_text("Run outcomebound.\n", "utf-8")


def test_runner_only_outcomebound_text_or_an_instruction_with_text_is_refused(
    tmp_path: Path,
) -> None:
    """Breaks if the operator's own skills, roles or an empty AGENTS.md are refused (both arms
    read them alike), or if a home or a folder above the workspace that names OutcomeBound or
    instructs with text is let through."""

    home = _home(tmp_path, dirty=True)
    above = tmp_path / "root"
    (above / "workspaces").mkdir(parents=True)
    assert RUN.guiding_reach(home, above / "workspaces") == []
    _guiding(home)
    (above / "AGENTS.override.md").write_text("Use the OutcomeBound kernel.\n", "utf-8")
    found = RUN.guiding_reach(home, above / "workspaces")
    assert sorted(Path(item).name for item in found) == [
        "AGENTS.md",
        "AGENTS.override.md",
        "planner",
    ]
    assert RUN.unclean_reach(["small-fix"], home, above) == []
    assert RUN.unclean_reach(["replica-fake"], home, above) == found


def _dump(tmp_path: Path, arm: str, capsys: pytest.CaptureFixture[str]) -> tuple[int, str]:
    root = tmp_path / "dumps"
    arguments = ["--dump-arm", "replica-fake", "--arm", arm, "--model", "m"]
    code = RUN._main([*arguments, "--workspace-root", str(root)])
    return code, capsys.readouterr().out


def test_runner_the_dump_shows_what_the_none_arms_call_receives_with_no_model_call(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    isolated: dict[str, Path],
) -> None:
    """Breaks if the dump starts codex, or leaves out the argv, the prompt, the instruction
    files, the Codex home or the launchers; or if a dirty home passes."""

    monkeypatch.setattr(RUN, "FIXTURES", _fixture(tmp_path, install=INSTALL))
    code, printed = _dump(tmp_path, "none", capsys)
    assert code == 0, printed
    assert not isolated["calls"].exists(), "the dump started codex"
    assert re.search(r"^codex exec --json .* -m m ", printed, re.M), printed
    assert "Record the release in the changelog." in printed
    assert re.search(r"replica-fake-none/AGENTS\.md \(\d+ bytes, in the workspace\)", printed)
    assert "  | Stack: Python." in printed
    assert "--- PATH entries holding outcomebound ---\n(none)" in printed
    for rule in ("launcher-on-path", "codex-home-neutral", "nothing-above-workspace"):
        assert f"{rule} PASS" in printed, printed
    assert "no-outcomebound-text PASS" in printed and "no-engine-import PASS" in printed

    dirty = _home(tmp_path / "dirty", dirty=True)
    monkeypatch.setenv("CODEX_HOME", str(dirty))
    code, printed = _dump(tmp_path, "none", capsys)
    assert code == 0, "the operator's own skills and roles reach both arms alike"
    assert "codex-home-neutral PASS" in printed
    assert re.search(r"reaches the call: .*/skills/pdf", printed)
    _guiding(dirty)
    code, printed = _dump(tmp_path, "none", capsys)
    assert code == 1
    assert "codex-home-neutral FAIL" in printed


def test_runner_the_dump_of_the_current_arm_shows_its_install(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    isolated: dict[str, Path],
) -> None:
    monkeypatch.setattr(
        RUN, "FIXTURES", _fixture(tmp_path, install={**INSTALL, "sandbox": "field"})
    )
    code, printed = _dump(tmp_path, "current", capsys)
    assert code == 0, printed
    assert (
        "install: field sandbox, Done ['make check', 'make test'], fragments ['commands']"
        in printed
    )
    assert ".agents/skills/using-outcomebound/SKILL.md" in printed
    assert ".outcomebound/fragments/commands.md" in printed
    assert "/.agents/work" not in printed.split("--- prompt ---")[0], (
        "a field call has no notes grant"
    )
    assert (
        "  | - Done: `make check` and `make test`"
        " (the full suite: run it where the change reaches what it tests)"
    ) in printed
    assert not isolated["calls"].exists()


def test_runner_a_replica_run_refuses_a_codex_home_that_names_outcomebound_or_instructs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    isolated: dict[str, Path],
) -> None:
    """Breaks if a replica run starts with OutcomeBound text or an instruction with text in its
    Codex home, or refuses before any codex start no longer; and if a home that holds only the
    operator's own skills, roles and an empty AGENTS.md is refused, or what it gives every call
    goes unrecorded."""

    monkeypatch.setattr(RUN, "FIXTURES", _fixture(tmp_path, install=INSTALL))
    home = _home(tmp_path / "dirty", dirty=True)
    monkeypatch.setenv("CODEX_HOME", str(home))
    arguments = ["--arm", "none", "--model", "m", "--fixtures", "replica-fake"]
    out = tmp_path / "out"
    assert RUN._main([*arguments, "--out", str(out)]) == RUN.PREFLIGHT_EXIT
    assert "gives every call alike" in capsys.readouterr().out
    status = json.loads((out / "STATUS.json").read_text(encoding="utf-8"))
    assert status["codex_home"] == str(home)
    assert sorted(Path(item).name for item in status["codex_home_reach"]) == [
        "AGENTS.md",
        "pdf",
        "role.toml",
    ]
    isolated["calls"].unlink()

    _guiding(home)
    refused = tmp_path / "refused"
    with pytest.raises(SystemExit) as stopped:
        RUN._main([*arguments, "--out", str(refused)])
    assert stopped.value.code == 2
    assert "planner" in capsys.readouterr().err
    assert not isolated["calls"].exists() and not refused.exists()


def test_runner_replica_fixtures_run_only_when_named(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixtures = _fixture(tmp_path, install=INSTALL)
    shutil.copytree(fixtures / "replica-fake", fixtures / "plain")
    (fixtures / "plain" / "install.json").unlink()
    monkeypatch.setattr(RUN, "FIXTURES", fixtures)
    assert RUN.fixture_names() == ["plain", "replica-fake"]
    assert RUN.default_fixtures() == ["plain"]


# --- cost --------------------------------------------------------------------------------


def _count(total: dict[str, int] | None) -> dict[str, Any]:
    info = None if total is None else {"total_token_usage": {**total, "total_tokens": 1}}
    return {"type": "event_msg", "payload": {"type": "token_count", "info": info}}


def test_runner_a_sessions_cost_is_its_last_running_total() -> None:
    """Breaks if the cost is read from the first count, from a count with no total, or from the
    stream where the session kept one."""

    first = {key: value // 2 for key, value in TOKENS.items()}
    records = [_count(first), _count(TOKENS), _count(None), {"type": "turn_context"}]
    usage = {"input_tokens": 1, "cached_input_tokens": 0, "output_tokens": 1}
    stream = [{"type": "turn.completed", "usage": {**usage, "reasoning_output_tokens": 0}}]
    assert session_tokens(records, stream) == {**TOKENS, "source": "native"}
    assert session_tokens(None, stream) == {
        **usage,
        "reasoning_output_tokens": 0,
        "source": "stream",
    }
    assert session_tokens([], [{"type": "turn.completed", "usage": usage}]) is None


SUMMARY = {
    "fixture": "replica-fake",
    "harness": "codex",
    "arm": "none",
    "model": "m",
    "effort": "medium",
    "claims": {},
    "protected_intact": True,
    "observations": [],
    "kernel_sha256": "k",
    "commit": "c" * 40,
    "dirty": False,
}


def test_runner_the_summary_gives_each_runs_cost_beside_its_verdict_failed_calls_counted(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Breaks if a failed call's spend is left out of the total, or a run's cost is not beside
    its verdict; a record from before costs were kept has them read from its native copy."""

    double = {key: value * 2 for key, value in TOKENS.items()}
    runs = [
        {"repetition": 1, "verdict": "PASS", "error": "", "session_tokens": TOKENS},
        {"repetition": 2, "verdict": "FAIL", "error": "", "session_tokens": double},
        {"repetition": 3, "verdict": "FAIL", "error": "codex exited 1", "session_tokens": TOKENS},
    ]
    for run in runs:
        meta = {**SUMMARY, **run, "thread_id": f"t{run['repetition']}", "elapsed_seconds": 10.0}
        (tmp_path / f"{run['repetition']}.meta.json").write_text(json.dumps(meta), "utf-8")
    older = tmp_path / "older"
    older.mkdir()
    meta = {**SUMMARY, "repetition": 1, "verdict": "PASS", "error": "", "thread_id": "old"}
    (older / "replica-fake.meta.json").write_text(json.dumps({**meta, "arm": "current"}), "utf-8")
    (older / "replica-fake.native.jsonl").write_text(json.dumps(_count(TOKENS)) + "\n", "utf-8")
    assert RUN.summarize([tmp_path]) == 0
    printed = capsys.readouterr().out.splitlines()
    assert printed[0] == "replica-fake | codex | current | m medium: PASS 1/1", printed
    assert (
        "  repetition 1: PASS; input 1000 (cached 800), output 50 (reasoning 20) tokens; "
        "unrecorded seconds" in printed
    )
    none = printed[
        printed.index(
            "replica-fake | codex | none | m medium: PASS 1/2 (1 failed call(s) not counted)"
        ) :
    ]
    assert (
        "  median cost input 1500 (cached 1200), output 75 (reasoning 30) tokens over 2 "
        "counted run(s)" in none
    )
    assert (
        "  spent on 3 call(s), 1 failed among them: input 4000 (cached 3200), output 200 "
        "(reasoning 80) tokens; 30.0 seconds over all 3" in none
    )
    assert (
        "  repetition 3: call failed, not counted; input 1000 (cached 800), output 50 "
        "(reasoning 20) tokens; 10.0 seconds" in none
    )
