"""Changed-risk validation executes explicit checks without claiming more than they establish."""

import contextlib
import io
import json
import os
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, NamedTuple

import pytest

from outcomebound_tools import validation
from tests.processes import running

ROOT = Path(__file__).resolve().parent.parent


def _plan(tmp_path: Path, claims: list[dict[str, Any]], **plan_fields: Any) -> Path:
    plan = {"version": 1, "claims": claims, **plan_fields}
    path = tmp_path / "validation.json"
    path.write_text(json.dumps(plan), encoding="utf-8")
    return path


def _run(tmp_path, claims, **plan_fields):
    path = _plan(tmp_path, claims, **plan_fields)
    return subprocess.run(
        [sys.executable, "-m", "outcomebound_tools.validation", str(path)],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
        timeout=10,
    )


class Result(NamedTuple):
    returncode: int
    stdout: str
    stderr: str


@pytest.fixture
def run(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> Callable[[Path], Result]:
    """`validation._main` called in-process on a plan file, read as the command's exit and stderr.

    Run from the plan's directory, as `_run` runs the command.
    """

    def invoke(path: Path) -> Result:
        monkeypatch.chdir(path.parent)
        capsys.readouterr()
        code = validation._main([str(path)])
        captured = capsys.readouterr()
        return Result(code, captured.out, captured.err)

    return invoke


def _claim(command: list[str] | None = None, **overrides: Any) -> dict[str, Any]:
    claim = {
        "name": "focused-regression",
        "risk": "the changed parser truncates complete records",
        "kind": "test",
        "required": True,
        "command": command or [sys.executable, "-c", "raise SystemExit(0)"],
    }
    claim.update(overrides)
    return claim


def test_passing_command_reports_check_pass_without_proof_claim(tmp_path):
    r = _run(tmp_path, [_claim()])
    assert r.returncode == 0, r.stdout + r.stderr
    assert "PASS" in r.stdout and "focused-regression" in r.stdout
    assert "VERDICT: PASS" in r.stdout
    assert "proven" not in r.stdout.lower() and "proves" not in r.stdout.lower()


def test_nonzero_command_is_fail(tmp_path):
    r = _run(tmp_path, [_claim([sys.executable, "-c", "raise SystemExit(7)"])])
    assert r.returncode == 1
    assert "FAIL" in r.stdout and "exit 7" in r.stdout


def test_missing_executable_is_unverified(tmp_path):
    r = _run(tmp_path, [_claim(["outcomebound-no-such-command"])])
    assert r.returncode == 2
    assert "UNVERIFIED" in r.stdout and "executable" in r.stdout.lower()


def test_missing_required_artifact_is_unverified_and_command_does_not_run(tmp_path):
    marker = tmp_path / "must-not-exist"
    r = _run(
        tmp_path,
        [
            _claim(
                [sys.executable, "-c", f"from pathlib import Path; Path({str(marker)!r}).touch()"],
                required_paths=["tests/missing.py"],
            )
        ],
    )
    assert r.returncode == 2
    assert "UNVERIFIED" in r.stdout and "tests/missing.py" in r.stdout
    assert not marker.exists()


def test_timeout_is_unverified(tmp_path):
    r = _run(
        tmp_path,
        [_claim([sys.executable, "-c", "import time; time.sleep(2)"], timeout_seconds=0.05)],
    )
    assert r.returncode == 2
    assert "timeout" in r.stdout.lower()


def test_a_timeout_ends_the_command_and_everything_it_started(tmp_path):
    """Breaks if only the command is killed: its child keeps running, holds the output pipe
    open and keeps changing the tree the caller expects to be left alone, and the verb waits
    ten more seconds for a pipe nobody closes. The command is a Python process, and so is its
    child, so that the pid it records is the platform's own on Windows too."""

    parent = (
        "import subprocess, sys; "
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)']); "
        "open('child.pid', 'w').write(str(child.pid)); child.wait()"
    )
    started = time.monotonic()
    r = _run(tmp_path, [_claim([sys.executable, "-c", parent], timeout_seconds=2)])

    assert r.returncode == 2, r.stdout + r.stderr
    assert "timeout" in r.stdout.lower()
    assert time.monotonic() - started < 9, "the verb waited for the child's pipe"
    child = int((tmp_path / "child.pid").read_text(encoding="utf-8"))
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline and running(child):
        time.sleep(0.1)
    assert not running(child)


def test_a_program_is_never_found_through_the_folder_the_check_runs_in(tmp_path, monkeypatch, run):
    """Breaks if a bare command is resolved with PATH's relative entries, as the operating
    system does for a child: a `.` entry made `git` in the target's own folder answer for the
    one on PATH, and a check runs what the project supplies. The command is not run, and reads
    as not found."""

    marker = tmp_path / "ran"
    planted = tmp_path / "outcomebound-planted"
    planted.write_text(f"#!/bin/sh\ntouch '{marker}'\n", encoding="utf-8")
    planted.chmod(0o755)
    monkeypatch.setenv("PATH", os.pathsep.join([".", "", os.environ.get("PATH", "")]))
    path = _plan(tmp_path, [_claim(["outcomebound-planted"])])

    result = run(path)

    assert result.returncode == 2, result.stdout
    assert "executable not found: outcomebound-planted" in result.stdout
    assert not marker.exists()


def test_a_claim_waits_for_its_command_unless_a_timeout_is_set(tmp_path):
    """No timeout is the default: neither the plan nor the claim sets one, so the claim has
    none; the plan's applies where the claim sets none, and the claim's own wins."""

    def claims(**plan_fields: Any) -> dict[str, float | None]:
        path = _plan(
            tmp_path,
            [_claim(name="bare"), _claim(name="own", timeout_seconds=7)],
            **plan_fields,
        )
        return {c.name: c.timeout_seconds for c in validation.load_plan(path).claims}

    assert claims() == {"bare": None, "own": 7.0}
    assert claims(timeout_seconds=19) == {"bare": 19.0, "own": 7.0}
    assert not hasattr(validation, "DEFAULT_TIMEOUT_SECONDS")


def test_a_command_without_a_timeout_runs_to_its_end(monkeypatch, tmp_path):
    seen: list[float | None] = []
    real = validation._execute

    def recording(command, cwd, timeout, env=None):
        seen.append(timeout)
        return real(command, cwd, timeout, env)

    monkeypatch.setattr(validation, "_execute", recording)
    path = _plan(tmp_path, [_claim([sys.executable, "-c", "import time; time.sleep(0.3)"])])
    [result] = validation.run_plan(validation.load_plan(path))
    assert seen == [None] and result.status == validation.PASSED


def test_human_view_claim_is_rejected_instead_of_being_self_attested(tmp_path):
    # The command-line seam for a plan refusal: an invalid plan is exit 2, named on stderr.
    view = {
        "name": "rendered-control",
        "risk": "the download control is absent from the rendered UI",
        "kind": "view",
        "required": True,
    }
    r = _run(tmp_path, [_claim(), view])
    assert r.returncode == 2
    assert "invalid plan" in r.stderr.lower()
    assert "kind must be one of" in r.stderr.lower()


def test_optional_missing_executable_is_reported_but_does_not_block_required_pass(tmp_path):
    optional = {
        "name": "nice-to-see",
        "risk": "an optional visual detail regressed",
        "kind": "test",
        "required": False,
        "command": ["outcomebound-no-such-command"],
    }
    r = _run(tmp_path, [_claim(), optional])
    assert r.returncode == 0, r.stdout + r.stderr
    assert "UNVERIFIED" in r.stdout and "optional" in r.stdout.lower()


def test_commands_are_argv_not_implicit_shell(tmp_path):
    marker = tmp_path / "shell-ran"
    r = _run(tmp_path, [_claim(["echo", f"ok; touch {marker}"])])
    assert r.returncode == 0, r.stdout + r.stderr
    assert not marker.exists()


def test_self_signed_human_observation_is_not_an_executable_claim(tmp_path, run):
    # An otherwise runnable claim, so the one thing refused is the self-signed
    # observation it carries (a `view` kind is refused for its kind first).
    claim = {
        **_claim(),
        "name": "operator-view",
        "risk": "the page is visibly broken",
        "observation": {"status": "PASS", "date": "2026-01-15"},
    }
    r = run(_plan(tmp_path, [claim]))
    assert r.returncode == 2
    assert "invalid plan" in r.stderr.lower()
    assert "unknown field(s): observation" in r.stderr, r.stderr


def test_non_finite_timeout_is_an_invalid_plan(tmp_path, run):
    plan = tmp_path / "validation.json"
    plan.write_text(
        '{"version": 1, "timeout_seconds": NaN, "claims": '
        + json.dumps([_claim([sys.executable, "-c", "pass"])])
        + "}",
        encoding="utf-8",
    )
    r = run(plan)
    assert r.returncode == 2
    assert "positive number" in r.stderr


def test_plan_must_be_explicit_file_not_unbound_stdin_projection(tmp_path):
    r = subprocess.run(
        [sys.executable, "-m", "outcomebound_tools.validation"],
        input=json.dumps({"version": 1, "claims": [_claim()]}),
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
    )
    assert r.returncode == 2


def test_relative_cwd_is_bound_to_plan_directory_not_invocation_directory(tmp_path):
    plan_dir = tmp_path / "plan"
    invocation = tmp_path / "elsewhere"
    plan_dir.mkdir()
    invocation.mkdir()
    (plan_dir / "expected.txt").write_text("here\n", encoding="utf-8")
    plan = {
        "version": 1,
        "cwd": ".",
        "claims": [
            _claim(
                [
                    sys.executable,
                    "-c",
                    "from pathlib import Path; raise SystemExit(not Path('expected.txt').is_file())",
                ],
                required_paths=["expected.txt"],
            )
        ],
    }
    plan_path = plan_dir / "validation.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "outcomebound_tools.validation", str(plan_path)],
        capture_output=True,
        text=True,
        cwd=invocation,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_failing_check_writes_a_log_and_prints_its_tail(tmp_path):
    command = [
        sys.executable,
        "-c",
        "import sys; print('line-from-stdout'); print('line-from-stderr', file=sys.stderr); raise SystemExit(3)",
    ]
    r = _run(tmp_path, [_claim(command)])
    assert r.returncode == 1
    log = tmp_path / ".outcomebound-checks" / "focused-regression.log"
    assert log.is_file(), sorted(p.name for p in tmp_path.iterdir())
    contents = log.read_text(encoding="utf-8")
    assert "line-from-stdout" in contents and "line-from-stderr" in contents
    assert "line-from-stdout" in r.stdout
    assert str(log.name) in r.stdout


def test_passing_check_writes_a_log_but_does_not_print_it(tmp_path):
    r = _run(tmp_path, [_claim([sys.executable, "-c", "print('quiet-success')"])])
    assert r.returncode == 0, r.stdout + r.stderr
    assert (tmp_path / ".outcomebound-checks" / "focused-regression.log").is_file()
    assert "quiet-success" not in r.stdout


def test_claim_without_a_command_is_an_invalid_plan(tmp_path, run):
    claim = {"name": "no-command", "risk": "r", "kind": "test", "required": True}
    r = run(_plan(tmp_path, [claim]))
    assert r.returncode == 2
    # The schema check runs at the top of parse_plan, so it names this defect
    # first, at the exact path. parse_plan's own "command is required" branch,
    # which the schema check leaves unreachable, stays as defense in depth.
    assert "missing required field 'command'" in r.stderr
    assert "claims[0]" in r.stderr


def _none_ran_claim(contract: dict[str, Any], code: str, **overrides: Any) -> dict[str, Any]:
    return _claim([sys.executable, "-c", code], executes_tests=contract, **overrides)


def test_a_declared_no_tests_exit_reads_unverified_and_keeps_both_facts(tmp_path):
    claim = _none_ran_claim({"no_tests_exit": 5}, "raise SystemExit(5)")
    r = _run(tmp_path, [claim])
    assert r.returncode == 2, r.stdout
    assert "UNVERIFIED" in r.stdout
    assert "declared check exit 5" in r.stdout and "no test executed" in r.stdout


def test_the_same_exit_without_the_declaration_stays_fail(tmp_path):
    r = _run(tmp_path, [_claim([sys.executable, "-c", "raise SystemExit(5)"])])
    assert r.returncode == 1
    assert "FAIL" in r.stdout and "no test executed" not in r.stdout


def test_another_nonzero_exit_stays_fail_under_the_contract(tmp_path):
    r = _run(tmp_path, [_none_ran_claim({"no_tests_exit": 5}, "raise SystemExit(1)")])
    assert r.returncode == 1
    assert "FAIL" in r.stdout and "no test executed" not in r.stdout


def test_exit_zero_without_the_declared_output_reads_unverified(tmp_path):
    claim = _none_ran_claim({"ran_output": r"\d+ passed"}, "print('collected 0 items')")
    r = _run(tmp_path, [claim])
    assert r.returncode == 2, r.stdout
    assert "declared check exited 0" in r.stdout and "no test executed" in r.stdout


def test_exit_zero_with_the_declared_output_passes(tmp_path):
    claim = _none_ran_claim({"ran_output": r"\d+ passed"}, "print('3 passed')")
    r = _run(tmp_path, [claim])
    assert r.returncode == 0, r.stdout
    assert "VERDICT: PASS" in r.stdout


def test_exit_zero_with_no_declaration_passes_though_no_test_ran(tmp_path):
    r = _run(tmp_path, [_claim([sys.executable, "-c", "print('collected 0 items')"])])
    assert r.returncode == 0


def test_when_none_fail_reads_fail(tmp_path):
    claim = _none_ran_claim({"no_tests_exit": 5, "when_none": "FAIL"}, "raise SystemExit(5)")
    r = _run(tmp_path, [claim])
    assert r.returncode == 1
    assert "FAIL" in r.stdout and "no test executed" in r.stdout


def test_a_failing_command_keeps_fail_under_ran_output(tmp_path):
    claim = _none_ran_claim({"ran_output": "ran"}, "raise SystemExit(3)")
    r = _run(tmp_path, [claim])
    assert r.returncode == 1 and "no test executed" not in r.stdout


@pytest.mark.parametrize(
    "contract",
    [
        {},
        {"no_tests_exit": 5, "ran_output": "x"},
        {"no_tests_exit": "5"},
        {"ran_output": "("},
        {"no_tests_exit": 5, "when_none": "PASS"},
        {"no_tests_exit": 5, "other": 1},
    ],
)
def test_a_malformed_contract_is_an_invalid_plan(tmp_path, run, contract):
    r = run(_plan(tmp_path, [_claim(executes_tests=contract)]))
    assert r.returncode == 2
    assert "invalid plan" in r.stderr.lower()


def test_a_waiver_is_recorded_beside_a_fail_and_the_verdict_stays(tmp_path, run):
    path = _plan(tmp_path, [_claim([sys.executable, "-c", "raise SystemExit(7)"])])
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = validation._main([str(path), "--waive", "focused-regression=person said go on"])
    assert code == 1
    assert "waived by instruction: person said go on; the observed FAIL stands" in out.getvalue()
    assert "VERDICT: FAIL" in out.getvalue()


def test_a_waiver_leaves_unverified_unverified(tmp_path):
    path = _plan(tmp_path, [_claim(["outcomebound-no-such-command"])])
    r = subprocess.run(
        [
            sys.executable,
            "-m",
            "outcomebound_tools.validation",
            str(path),
            "--waive",
            "focused-regression=skip it",
        ],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
        timeout=10,
    )
    assert r.returncode == 2
    assert "the observed UNVERIFIED stands" in r.stdout and "VERDICT: UNVERIFIED" in r.stdout


def test_without_a_waiver_no_waiver_line_is_printed(tmp_path):
    r = _run(tmp_path, [_claim([sys.executable, "-c", "raise SystemExit(7)"])])
    assert "waived" not in r.stdout


def test_a_waiver_naming_no_claim_is_an_invalid_plan(tmp_path, capsys):
    path = _plan(tmp_path, [_claim()])
    assert validation._main([str(path), "--waive", "nope=x"]) == 2
    assert "names no claim" in capsys.readouterr().err
