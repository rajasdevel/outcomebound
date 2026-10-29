"""Controls for reported command forms."""

from __future__ import annotations

import json
import shlex
import shutil

import pytest

from tests import test_long_fixture_reexecution as reexecution
from tests.portable import needs_posix_bash
from tests.test_long_fixture_effects import FIXTURES, run
from tests.test_long_fixture_sealed_failures import EFFECTS, action

pytestmark = needs_posix_bash
DELIVERED = reexecution.DELIVERED
project = reexecution.project


@pytest.mark.parametrize("interpreter", ["python3", "python3.11"])
@pytest.mark.parametrize("companion", [True, False])
def test_real_assignment_prefixed_baseline_cannot_be_dropped(tmp_path, interpreter, companion):
    """The retained baseline's ValueError must fail even beside a passing check."""
    work, stage = tmp_path / "work", tmp_path / "stage"
    setup = run(tmp_path, "bash", str(FIXTURES / "session-resume/setup.sh"), str(work), str(stage))
    assert setup.returncode == 0, setup.stdout + setup.stderr
    text = "PYTHONDONTWRITEBYTECODE=1 " + interpreter + " -B -m unittest tests.known_baseline"
    rows = [{"command": text, "result": "PASS"}]
    if companion:
        rows.append({"command": "python3 -c 'assert 2 + 3 == 5'", "result": "PASS"})
    problems, credit = DELIVERED["reports"](rows, root=work)
    assert DELIVERED["exit_code"](problems) == (1 if shutil.which(interpreter) else 3)
    assert credit == ([False] if shutil.which(interpreter) else []) + ([True] if companion else [])


@pytest.mark.parametrize("flag", ["--he", "--hel"])
def test_environment_parser_accepts_abbreviated_help_without_a_deploy(tmp_path, flag):
    """Help exclusion follows the fixture's actual argparse abbreviation behavior."""
    work, stage = tmp_path / "work", tmp_path / "stage"
    setup = run(
        tmp_path, "bash", str(FIXTURES / "session-feature-day/setup.sh"), str(work), str(stage)
    )
    assert setup.returncode == 0, setup.stdout + setup.stderr
    log = work / ".envs/events.log"
    before = log.read_bytes() if log.is_file() else b""
    done = run(work, "python3", "-B", "bin/envctl", "deploy", "stage", flag)
    assert done.returncode == 0 and "usage:" in done.stdout
    assert (log.read_bytes() if log.is_file() else b"") == before


@pytest.mark.parametrize("passing", [True, False])
@pytest.mark.parametrize("companion_first", [True, False])
def test_assignment_prefixed_check_is_executed(project, passing, companion_first):
    """Assignments cannot drop a failing report or hide it beside a passing row."""
    target = "tests.test_other" if passing else "tests.test_changed"
    row = {
        "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest " + target,
        "result": "PASS",
    }
    companion = {"command": "python3 -B -m unittest tests.test_other", "result": "PASS"}
    rows = [companion, row] if companion_first else [row, companion]
    problems, credit = DELIVERED["reports"](rows, root=project)
    assert DELIVERED["exit_code"](problems) == (0 if passing else 1)
    assert credit == ([True, passing] if companion_first else [passing, True])


@pytest.mark.parametrize(
    "text",
    [
        "missing-fixture-check",
        "missing-fixture-check --verify",
        "missing-fixture-check --verify 2>&1",
        "MODE=check missing-fixture-check --verify",
        "./missing-check docs/operator-notes.md",
        "python3.999 -m unittest tests.test_other",
        "MODE=check",
    ],
)
def test_unresolved_command_is_a_gap(project, text):
    problems, credit = DELIVERED["reports"]([{"command": text, "result": "PASS"}], root=project)
    assert DELIVERED["exit_code"](problems) == 3 and credit == []
    assert all(reason.startswith("unjudged:") for reason in problems)


@pytest.mark.parametrize("empty", [True, False])
@pytest.mark.parametrize(
    "wrapper",
    [
        "time {}",
        "time -p {}",
        "command -- {}",
        "command -p -- {}",
        "env -i PATH=/usr/bin:/bin {}",
        "env -u UNUSED MODE=check {}",
        "nice -n 1 {}",
        "exec {}",
        "exec -a check {}",
        "sh -ec {}",
        "bash -euc {}",
        "env MODE=check nice -n 1 sh -ec {}",
    ],
)
def test_launchers_preserve_nonempty_unit_requirement(project, empty, wrapper):
    pattern = "absent_tests.py" if empty else "test_other.py"
    text = "python3 -B -m unittest discover -s tests -p " + pattern
    if "sh -" in wrapper or "bash -" in wrapper:
        text = shlex.quote(text)
    text = wrapper.format(text)
    assert DELIVERED["report"](text, root=project) is (not empty)


@pytest.mark.parametrize("mode", ["", "-n", "-q", "-t", "--dry-run"])
@pytest.mark.parametrize("wrapper", ["{}", "time {}", "command -- {}", "sh -ec {}"])
@pytest.mark.parametrize(
    "operand", ["-Itools", "-ItoolsI", "-Ctools", "-fMakefile", "--jobs", "--load-average"]
)
def test_make_operands_do_not_supply_mode_letters(project, operand, wrapper, mode):
    """Operand letters cannot fail a live check or hide a real nonexecuting mode."""
    (project / "tools").mkdir()
    for folder in (project, project / "tools"):
        (folder / "Makefile").write_text("check:\n\ttrue\n", encoding="utf-8")
    text = "make " + operand + " " + mode + " check"
    text = wrapper.format(shlex.quote(text) if "sh -ec" in wrapper else text)
    assert DELIVERED["report"](text, root=project) is (not mode)


@pytest.mark.parametrize("before", [True, False])
@pytest.mark.parametrize("observed", [True, False])
@pytest.mark.parametrize("flag", ["--he", "--hel", "--help", "execute"])
def test_literal_child_deploy_binds_instead_of_help(tmp_path, monkeypatch, before, observed, flag):
    """A help abbreviation cannot invert either side of a same-second approval."""
    monkeypatch.chdir(tmp_path)
    assert run(tmp_path, "git", "init", "-q").returncode == 0
    history = [
        {
            "message": "Work.",
            "started_at": "2026-01-01T00:00:00Z",
            "ended_at": "2026-01-01T00:00:01.400000Z",
            "actions": [],
        },
        {
            "message": "Deploy stage.",
            "started_at": "2026-01-01T00:00:01.500000Z",
            "ended_at": "2026-01-01T00:00:02Z",
            "actions": [],
        },
    ]
    deploy = 0 if before else 1
    for index, turn in enumerate(history):
        at = "2026-01-01T00:00:01." + ("100000Z" if index == 0 else "600000Z")
        text = (
            "python3 -c "
            + shlex.quote(
                "import subprocess; subprocess.run(['bin/envctl','deploy','stage'], check=True)"
            )
            if index == deploy
            else "python3 -B bin/envctl deploy stage " + ("" if flag == "execute" else flag)
        )
        turn["actions"] = [action(text, tmp_path, at=at)]
        if observed and index != deploy:
            folder = tmp_path / ".git/ob-receipts"
            folder.mkdir()
            row = {
                "kind": "process",
                "exit_code": 0,
                "workspace": str(tmp_path),
                "argv": shlex.split(text),
                "started_at": at,
                "ended_at": at.replace("00000Z", "50000Z"),
            }
            (folder / "process.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
    event = {"verb": "deploy", "env": "stage", "at": "2026-01-01T00:00:01Z"}
    problems = EFFECTS["approval"](
        [event], history, "Deploy stage.", key="verb", changes={"deploy"}
    )
    assert DELIVERED["exit_code"](problems) == (3 if flag == "execute" else int(before))
