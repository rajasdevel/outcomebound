"""Changed-risk validation executes explicit checks without claiming more than they establish."""

import json
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, NamedTuple

import pytest

from outcomebound_tools import validation

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
