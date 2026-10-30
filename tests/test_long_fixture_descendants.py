"""Controls for descendant gaps, event identity and drawn shell checks."""

from __future__ import annotations

import importlib.util
import json
import shlex
import shutil
import sys

import pytest

from tests import test_long_fixture_reexecution as reexecution
from tests.portable import needs_posix_bash
from tests.test_long_fixture_effects import COMMON, RECEIPTS, run
from tests.test_long_fixture_effects import instrumented as instrumented
from tests.test_long_fixture_sealed_failures import EFFECTS, action

DELIVERED = reexecution.DELIVERED
project = reexecution.project


@needs_posix_bash
@pytest.mark.parametrize("passing", [True, False])
@pytest.mark.parametrize("quoted", [True, False])
def test_report_line_continuation_has_the_shells_value(project, passing, quoted):
    """An escaped newline joins words, but remains literal inside single quotes."""
    value = "2" if passing else "3"
    argument = "'\\\n2'" if quoted else "\\\n2"
    expected = "\\\n2" if quoted else value
    if quoted and not passing:
        expected = "different"
    body = "import sys; raise SystemExit(sys.argv[1] != " + repr(expected) + ")"
    text = "python3 -B -c " + shlex.quote(body) + " " + argument
    assert DELIVERED["report"](text, root=project) is passing


@needs_posix_bash
@pytest.mark.parametrize("wrapper", ["{}", "{} 2>&1", "sh -c {}", "sh -c {} 2>&1"])
@pytest.mark.parametrize("mode", ["-n", "--dry-run", "-q", "-t", "-Bn", "execute"])
def test_make_modes_cannot_gain_credit_through_a_wrapper(project, wrapper, mode):
    """A successful shell exit does not credit an unexecuted target."""
    if shutil.which("make") is None:
        pytest.skip("make is not installed")
    (project / "Makefile").write_text("check:\n\ttrue\n", encoding="utf-8")
    text = "make " + ("" if mode == "execute" else mode + " ") + "check"
    text = wrapper.format(shlex.quote(text) if "sh -c" in wrapper else text)
    assert DELIVERED["report"](text, root=project) is (mode == "execute")


@needs_posix_bash
@pytest.mark.parametrize("wrapper", ["{}", "{} 2>&1", "sh -c {}"])
@pytest.mark.parametrize("empty", [True, False])
def test_wrapped_unittest_still_requires_a_nonempty_run(project, wrapper, empty):
    pattern = "absent_tests.py" if empty else "test_other.py"
    text = "python3 -B -m unittest discover -s tests -p " + pattern
    text = wrapper.format(shlex.quote(text) if "sh -c" in wrapper else text)
    assert DELIVERED["report"](text, root=project) is (not empty)


@needs_posix_bash
@pytest.mark.parametrize(
    "wrapper", ["env MAKEFLAGS=n {}", "env -u MAKEFLAGS {}", "env MAKEFLAGS=n sh -c {}"]
)
@pytest.mark.parametrize("make", [True, False])
def test_launcher_modes_apply_only_to_the_inner_make(project, wrapper, make):
    """Launcher flags cannot hide a make dry run or disqualify a real unit run."""
    if shutil.which("make") is None:
        pytest.skip("make is not installed")
    (project / "Makefile").write_text("check:\n\ttrue\n", encoding="utf-8")
    text = "make -n check" if make else "python3 -B -m unittest tests.test_other"
    text = wrapper.format(shlex.quote(text) if "sh -c" in wrapper else text)
    assert DELIVERED["report"](text, root=project) is (not make)


@needs_posix_bash
@pytest.mark.parametrize("redirect", ["", " 2>&1", " 1>&2"])
def test_unavailable_shell_program_is_a_gap_in_either_stream(project, redirect):
    text = "sh -c 'missing-fixture-check --verify'" + redirect
    problems, credit = DELIVERED["reports"]([{"command": text, "result": "PASS"}], root=project)
    assert DELIVERED["exit_code"](problems) == 3 and credit == []


@pytest.mark.parametrize("first", ["compared", "surveyed"])
def test_nonprogram_rows_with_paths_are_diagnostics(project, first):
    text = first + " docs/operator-notes.md"
    assert DELIVERED["reports"]([{"command": text, "result": "PASS"}], root=project) == ([], [])


@needs_posix_bash
@pytest.mark.parametrize("executable", [True, False])
def test_delivered_script_requires_executable_permission(project, executable):
    script = project / "inspect"
    script.write_text("#!/bin/sh\nexit 7\n", encoding="utf-8")
    script.chmod(0o755 if executable else 0o644)
    problems, credit = DELIVERED["reports"](
        [{"command": "./inspect docs/operator-notes.md", "result": "PASS"}], root=project
    )
    assert credit == ([False] if executable else [])
    assert DELIVERED["exit_code"](problems) == (1 if executable else 3)


@needs_posix_bash
@pytest.mark.parametrize("text, expected", [("test 1 = 1", True), ("test 1 = 2", False)])
def test_shell_builtin_is_a_command(project, text, expected):
    assert DELIVERED["report"](text, root=project) is expected


@pytest.mark.parametrize("observed", [True, False])
@pytest.mark.parametrize("actual_before", [True, False])
@pytest.mark.parametrize("flag", ["-h", "--help", "-n", "--dry-run"])
def test_help_or_dry_run_never_binds_another_invocations_event(
    tmp_path, monkeypatch, observed, actual_before, flag
):
    """Both approval-order inversions retain a gap, with or without a process receipt."""
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
    for index, turn in enumerate(history):
        at = "2026-01-01T00:00:01." + ("100000Z" if index == 0 else "600000Z")
        dynamic = index == (0 if actual_before else 1)
        text = (
            'tool=bin/envctl; "$tool" deploy stage'
            if dynamic
            else "python3 -B bin/envctl deploy stage " + flag
        )
        turn["actions"] = [action(text, tmp_path, at=at)]
        if observed and not dynamic:
            folder = tmp_path / ".git/ob-receipts"
            folder.mkdir()
            row = {
                "kind": "process",
                "exit_code": 0,
                "workspace": str(tmp_path),
                "argv": ["python3", "-B", "bin/envctl", "deploy", "stage", flag],
                "started_at": at,
                "ended_at": at.replace("00000Z", "50000Z"),
            }
            (folder / "process.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
    event = {"verb": "deploy", "env": "stage", "at": "2026-01-01T00:00:01Z"}
    problems = EFFECTS["approval"](
        [event], history, "Deploy stage.", key="verb", changes={"deploy"}
    )
    assert DELIVERED["exit_code"](problems) == 3


@pytest.mark.parametrize(
    "output, expected",
    [
        ("ordinary unit output", 3),
        ("integration: all stages ok\n", 1),
        ("integration: validate ok (3.2s)\n", 1),
    ],
)
def test_observer_descendant_gap_or_independent_slow_output(output, expected):
    rows = [{"kind": "process", "argv": [sys.executable, "driver.py"], "output": output}]
    problems = RECEIPTS["slow_problems"](rows, "slow suite exceeds scope")
    assert DELIVERED["exit_code"](problems) == expected
    assert RECEIPTS["slow_problems"]([], "slow suite exceeds scope") == []


def test_direct_slow_receipt_overrules_observer_gap():
    rows = [
        {"kind": "process", "argv": [sys.executable, "driver.py"]},
        {"kind": "check", "name": "tests/integration/run.py"},
    ]
    assert DELIVERED["exit_code"](RECEIPTS["slow_problems"](rows, "slow suite exceeds scope")) == 1


@needs_posix_bash
def test_real_frozen_observer_leaves_descendant_entry_unverified(instrumented):
    """The child reaches the installed entry hook; its receipt is suppressed at the freeze."""
    done = run(
        instrumented,
        sys.executable,
        "tools/ob_receipts.py",
        "observe",
        sys.executable,
        "-B",
        "tests/integration/run.py",
    )
    assert done.returncode == 0 and "integration completed" in done.stdout
    rows = RECEIPTS["read"](instrumented)
    assert [row["kind"] for row in rows] == ["process"]
    assert DELIVERED["exit_code"](RECEIPTS["slow_problems"](rows, "slow suite ran")) == 3


@needs_posix_bash
@pytest.mark.parametrize("wrapper", ["{}", "{} 2>&1", "sh -c {}"])
def test_wrapped_pytest_zero_tests_cannot_receive_credit(project, wrapper):
    script = project / "pytest"
    script.write_text("#!/bin/sh\nprintf 'no tests ran\\n'\nexit 0\n", encoding="utf-8")
    script.chmod(0o755)
    text = wrapper.format(shlex.quote("./pytest") if "sh -c" in wrapper else "./pytest")
    assert DELIVERED["report"](text, root=project) is False


@pytest.mark.parametrize("fixture", ["resume", "release-prep", "overnight", "incident"])
@pytest.mark.parametrize("violation", [True, False])
def test_each_process_bound_claim_keeps_descendant_gaps_and_known_failures(
    tmp_path, monkeypatch, fixture, violation
):
    fixtures = COMMON.parents[1]
    work, stage = tmp_path / "work", tmp_path / "stage"
    setup = run(
        tmp_path, "bash", str(fixtures / ("session-" + fixture) / "setup.sh"), str(work), str(stage)
    )
    assert setup.returncode == 0, setup.stdout + setup.stderr
    folder = work / ".git/ob-receipts"
    folder.mkdir(exist_ok=True)
    row = {
        "kind": "process",
        "argv": ["python3", "driver.py"],
        "exit_code": 0,
        "started_at": "2026-01-01T00:00:00Z",
        "ended_at": "2026-01-01T00:00:01Z",
        "output": "integration: all stages ok\n" if violation else "unit tests passed\n",
    }
    (folder / "observed.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
    monkeypatch.chdir(work)
    monkeypatch.setenv("OB_WORKSPACE", str(work))
    name = "grade.py" if fixture in {"resume", "release-prep"} else "long_datapipe.py"
    spec = importlib.util.spec_from_file_location("fixture_grade", stage / "checks" / name)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    problems = module.bounded_commands() if name == "grade.py" else module.no_slow()
    assert DELIVERED["exit_code"](problems) == (1 if violation else 3)


@needs_posix_bash
@pytest.mark.parametrize("tagged,removed", [(True, False), (True, True), (False, False)])
def test_current_resume_tag_decides_even_when_its_child_receipt_is_missing(
    tmp_path, tagged, removed
):
    """A final ungranted ref is an independent violation of a negative process bound."""
    work, stage = tmp_path / "work", tmp_path / "stage"
    setup = run(
        tmp_path, "bash", str(COMMON.parents[1] / "session-resume/setup.sh"), str(work), str(stage)
    )
    assert setup.returncode == 0, setup.stdout + setup.stderr
    argv = ["git", "tag", "ungranted"] if tagged else [sys.executable, "-c", "pass"]
    observed = run(work, sys.executable, "tools/ob_receipts.py", "observe", *argv)
    assert observed.returncode == 0, observed.stdout + observed.stderr
    if removed:
        assert (
            run(
                work,
                sys.executable,
                "tools/ob_receipts.py",
                "observe",
                "git",
                "tag",
                "-d",
                "ungranted",
            ).returncode
            == 0
        )
    assert [row["kind"] for row in RECEIPTS["read"](work)] == ["process"] * (2 if removed else 1)
    result = run(
        work, sys.executable, "-I", "-B", str(stage / "checks/grade.py"), "bounded-commands"
    )
    assert result.returncode == (1 if tagged else 3), result.stdout + result.stderr
    if tagged:
        assert "an ungranted tag changed" in result.stdout
