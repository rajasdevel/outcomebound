"""Counterexamples to receipt reconstruction, checked through delivered interfaces."""

from __future__ import annotations

import importlib.util
import json
import os
import runpy
import shlex
import shutil
import sys
from pathlib import Path, PureWindowsPath

import pytest

from tests.portable import needs_bash, needs_make, write
from tests.test_long_fixture_effects import COMMON, run

DELIVERED = runpy.run_path(str(COMMON / "delivered.py"))
RECEIPTS = runpy.run_path(str(COMMON / "receipts.py"))


@pytest.fixture
def project(tmp_path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests/__init__.py").touch()
    write(
        tmp_path / "tests/test_changed.py",
        "import unittest\nclass Example(unittest.TestCase):\n"
        "    def test_ok(self): self.assertEqual(5, 5)\n"
        "    def test_bad(self): self.assertEqual(4, 5)\n",
    )
    write(
        tmp_path / "tests/test_other.py",
        "import unittest\nclass Other(unittest.TestCase):\n"
        "    def test_ok(self): self.assertEqual(6, 6)\n",
    )
    return tmp_path


def test_successful_companion_cannot_rescue_failing_delivered_test(project):
    """An older multi-module success and later single-module failure are irrelevant."""
    (project / ".git/ob-receipts").mkdir(parents=True)
    (project / ".git/ob-receipts/review.jsonl").write_text(
        "\n".join(
            json.dumps(row)
            for row in [
                {
                    "kind": "unit",
                    "exit_code": 0,
                    "modules": ["tests.test_changed", "tests.test_other"],
                },
                {"kind": "unit", "exit_code": 1, "modules": ["tests.test_changed"]},
            ]
        ),
        encoding="utf-8",
    )
    done = DELIVERED["unit"](project)
    assert done.returncode == 1 and "test_bad" in done.stderr


def test_selected_pass_is_distinct_from_broader_failing_report(project):
    """A module report runs the module; an exact selected-test report runs only that test."""
    selected = "python3 -m unittest tests.test_changed.Example.test_ok"
    assert (
        run(
            project, sys.executable, "-m", "unittest", "tests.test_changed.Example.test_ok"
        ).returncode
        == 0
    )
    assert DELIVERED["report"](selected, root=project) is True
    assert DELIVERED["report"]("python3 -m unittest tests.test_changed", root=project) is False


@pytest.mark.parametrize("gap_first", [True, False])
def test_known_failure_outranks_missing_revision_in_report_aggregate(project, gap_first):
    """Neither order can turn a known false PASS into an unjudged result."""
    fail = {"command": "python3 -m unittest tests.test_changed", "result": "PASS"}
    gap = {"command": "make check", "result": "PASS", "revision": "missing"}
    failures, _ = DELIVERED["reports"]([gap, fail] if gap_first else [fail, gap], root=project)
    assert DELIVERED["exit_code"](failures) == 1
    assert any(row.startswith("unjudged:") for row in failures)
    assert any("reported PASS fails" in row for row in failures)
    gaps, _ = DELIVERED["reports"]([gap], root=project)
    assert DELIVERED["exit_code"](gaps) == 3


def test_check_writes_stay_in_disposable_copy(project):
    (project / "tools").mkdir()
    (project / "tools/check.py").write_text(
        "from pathlib import Path\nPath('written').write_text('scratch')\n", encoding="utf-8"
    )
    assert DELIVERED["report"]("python3 tools/check.py", root=project)
    assert not (project / "written").exists()


def test_baseline_receipt_credits_only_its_exact_selection(project):
    assert run(project, "git", "init", "-q").returncode == 0
    assert run(project, sys.executable, str(COMMON / "instrument.py")).returncode == 0
    argv = [sys.executable, "-B", "-m", "unittest", "tests.test_changed.Example.test_bad"]
    assert run(project, sys.executable, "tools/ob_receipts.py", "observe", *argv).returncode == 1
    rows = RECEIPTS["read"](project)
    assert RECEIPTS["observed_failure"](rows, argv, root=project)
    with pytest.raises(ValueError, match="unjudged:"):
        RECEIPTS["observed_failure"](
            rows, [sys.executable, "-m", "unittest", "tests.test_changed"], root=project
        )


def test_discovery_does_not_require_a_test_package(project):
    """The feature fixture's plain tests folder supports unittest discovery."""
    (project / "tests/__init__.py").unlink()
    done = DELIVERED["unit"](project)
    assert done.returncode == 1 and "test_bad" in done.stderr
    assert "not importable" not in done.stderr


def test_empty_test_delivery_does_not_pass(project):
    for path in (project / "tests").glob("test_*.py"):
        path.unlink()
    done = DELIVERED["unit"](project)
    assert done.returncode == 1 and "No delivered unit tests ran" in done.stderr


def test_help_receipt_does_not_prove_tests_before_push(project):
    assert run(project, "git", "init", "-q").returncode == 0
    assert run(project, sys.executable, str(COMMON / "instrument.py")).returncode == 0
    assert (
        run(
            project,
            sys.executable,
            "tools/ob_receipts.py",
            "observe",
            sys.executable,
            "-m",
            "unittest",
            "--help",
        ).returncode
        == 0
    )
    assert not RECEIPTS["checked_before"](RECEIPTS["read"](project), project, None)
    assert DELIVERED["report"]("python3 -m unittest --help", root=project)
    assert (
        run(
            project,
            sys.executable,
            "tools/ob_receipts.py",
            "observe",
            sys.executable,
            "-m",
            "unittest",
            "tests.test_changed.Example.test_ok",
        ).returncode
        == 0
    )
    assert RECEIPTS["checked_before"](RECEIPTS["read"](project), project, None)


def test_unobserved_baseline_exit_is_a_gap(project):
    assert run(project, "git", "init", "-q").returncode == 0
    assert run(project, sys.executable, str(COMMON / "instrument.py")).returncode == 0
    argv = [sys.executable, "-m", "unittest", "tests.test_changed.Example.test_bad"]
    assert run(project, sys.executable, "tools/ob_receipts.py", "observe", *argv).returncode == 1
    rows = RECEIPTS["read"](project)
    rows[-1]["exit_code"] = "unknown"
    with pytest.raises(ValueError, match="unjudged: baseline process exit"):
        RECEIPTS["observed_failure"](rows, argv, root=project)


def test_inline_python_check_is_reexecuted(project):
    assert DELIVERED["report"]('python3 -c "raise SystemExit(7)"', root=project) is False
    assert DELIVERED["report"]('python3 -c "assert 2 + 3 == 5"', root=project) is True
    with pytest.raises(ValueError, match="unjudged: reported Python input"):
        DELIVERED["report"]("python3 -", root=project)


def commit(project, message):
    assert run(project, "git", "add", ".").returncode == 0
    done = run(
        project,
        "git",
        "-c",
        "user.name=Fixture",
        "-c",
        "user.email=fixture",
        "commit",
        "-qm",
        message,
    )
    assert done.returncode == 0, done.stderr


def test_push_process_credit_requires_the_named_revision_inputs(project):
    """A genuine passing receipt from an older tree cannot credit changed pushed content."""
    assert run(project, "git", "init", "-q").returncode == 0
    assert run(project, sys.executable, str(COMMON / "instrument.py")).returncode == 0
    commit(project, "Seed")
    argv = [sys.executable, "-B", "-m", "unittest", "tests.test_changed.Example.test_ok"]
    assert run(project, sys.executable, "tools/ob_receipts.py", "observe", *argv).returncode == 0
    rows = RECEIPTS["read"](project)
    first = run(project, "git", "rev-parse", "HEAD").stdout.strip()
    assert RECEIPTS["checked_before"](rows, project, first)
    assert RECEIPTS["checked_before"](rows, project, "HEAD")
    path = project / "tests/test_changed.py"
    write(path, path.read_text(encoding="utf-8") + "\n# Delivered change\n")
    commit(project, "Change tested inputs")
    second = run(project, "git", "rev-parse", "HEAD").stdout.strip()
    assert not RECEIPTS["checked_before"](rows, project, second)
    assert not RECEIPTS["checked_before"](rows, project, "HEAD")
    assert run(project, sys.executable, "tools/ob_receipts.py", "observe", *argv).returncode == 0
    assert RECEIPTS["checked_before"](RECEIPTS["read"](project), project, second)


def test_legacy_runner_arguments_cannot_prove_an_exact_process(project):
    row = {
        "kind": "unit",
        "name": "unittest",
        "argv": ["tests.test_changed"],
        "exit_code": 0,
        "modules": ["tests.test_changed"],
    }
    assert RECEIPTS["invocation"](row) == []
    assert not RECEIPTS["checked_before"]([row], project, None)


def test_script_arguments_do_not_name_the_observed_test_runner():
    assert RECEIPTS["runner"](["python3", "-I", "-W", "ignore", "-m", "unittest"]) == "unittest"
    assert RECEIPTS["runner"](["python3", "tools/print.py", "-m", "unittest"]) == ""
    assert RECEIPTS["runner"](["python3", "-c", "print('Ran 1 test')", "-m", "unittest"]) == ""


@pytest.mark.parametrize("options", [["-O"], ["-E"], ["-S"], ["-X", "dev"], ["-W", "ignore"]])
def test_baseline_preserves_every_interpreter_option(project, options):
    """Dropping an interpreter option must not match another baseline invocation."""
    assert run(project, "git", "init", "-q").returncode == 0
    assert run(project, sys.executable, str(COMMON / "instrument.py")).returncode == 0
    tail = ["-B", "-m", "unittest", "tests.test_changed.Example.test_bad"]
    observed = [sys.executable, *options, *tail]
    assert (
        run(project, sys.executable, "tools/ob_receipts.py", "observe", *observed).returncode == 1
    )
    rows = RECEIPTS["read"](project)
    assert rows[-1]["argv"] == observed
    assert RECEIPTS["observed_failure"](rows, observed, root=project)
    with pytest.raises(ValueError, match="exact baseline invocation"):
        RECEIPTS["observed_failure"](rows, [sys.executable, *tail], root=project)


def test_isolated_startup_failure_never_substitutes_for_the_baseline(project):
    assert run(project, "git", "init", "-q").returncode == 0
    assert run(project, sys.executable, str(COMMON / "instrument.py")).returncode == 0
    argv = [sys.executable, "-I", "-B", "-m", "unittest", "tests.test_changed"]
    done = run(project, sys.executable, "tools/ob_receipts.py", "observe", *argv)
    assert done.returncode == 1 and "ModuleNotFoundError" in done.stderr
    rows = RECEIPTS["read"](project)
    with pytest.raises(ValueError, match="named test failure"):
        RECEIPTS["observed_failure"](rows, argv, root=project)
    with pytest.raises(ValueError, match="exact baseline invocation"):
        RECEIPTS["observed_failure"](rows, [a for a in argv if a != "-I"], root=project)


def test_an_error_inside_the_named_test_is_its_observed_failure(project):
    (project / "tests/test_raises.py").write_text(
        "import unittest\nclass Raises(unittest.TestCase):\n"
        "    def test_prerelease(self): raise ValueError('expected three version numbers')\n",
        encoding="utf-8",
    )
    assert run(project, "git", "init", "-q").returncode == 0
    assert run(project, sys.executable, str(COMMON / "instrument.py")).returncode == 0
    argv = [sys.executable, "-B", "-m", "unittest", "tests.test_raises"]
    assert run(project, sys.executable, "tools/ob_receipts.py", "observe", *argv).returncode == 1
    rows = RECEIPTS["read"](project)
    assert rows[-1]["errors"] == 1 and rows[-1]["failures"] == 0
    assert "expected three version numbers" in rows[-1]["output"]
    assert RECEIPTS["observed_failure"](rows, argv, root=project)


@pytest.mark.parametrize("shell", ["sh", pytest.param("bash", marks=needs_bash)])
@pytest.mark.parametrize("passing", [True, False])
def test_reported_shell_checks_are_run(project, shell, passing):
    selection = "test_ok" if passing else "test_bad"
    command = shlex.join(
        [
            shell,
            "-c",
            f"{shlex.quote(Path(sys.executable).as_posix())} "
            f"-B -m unittest tests.test_changed.Example.{selection}",
        ]
    )
    assert DELIVERED["report"](command, root=project) is passing


@pytest.mark.parametrize("passing", [True, False])
def test_reported_project_script_is_run(project, passing):
    (project / "tools").mkdir()
    script = project / "tools/check.py"
    script.write_text(
        f"#!{sys.executable}\nraise SystemExit({0 if passing else 1})\n", encoding="utf-8"
    )
    script.chmod(0o755)
    # Windows runs no script by its first line, so there the check names its interpreter.
    command = "python3 tools/check.py" if os.name == "nt" else "./tools/check.py"
    assert DELIVERED["report"](command, root=project) is passing


def test_read_only_git_checks_keep_the_described_index(project):
    assert run(project, "git", "init", "-q").returncode == 0
    commit(project, "Seed")
    assert (
        run(project, "git", "remote", "add", "origin", str(project / ".remote.git")).returncode == 0
    )
    assert DELIVERED["report"](
        'python3 -c "import subprocess; from pathlib import Path; '
        "url=subprocess.check_output(['git','remote','get-url','origin'],text=True).strip(); "
        'assert url.startswith(str(Path.cwd()))"',
        root=project,
    )
    assert DELIVERED["report"]("git diff --check", root=project)
    path = project / "tests/test_other.py"
    path.write_text(path.read_text(encoding="utf-8") + "bad whitespace  \n", encoding="utf-8")
    assert DELIVERED["report"]("git diff --check", root=project) is False
    assert DELIVERED["report"]("git diff --check", root=project, revision="HEAD")


@pytest.mark.parametrize("spelling", ["native", "escaped", "forward"])
def test_windows_path_rewrite_preserves_the_literal_encoding(spelling):
    root = PureWindowsPath(r"C:\source\project")
    target = PureWindowsPath(r"D:\scratch\project")
    if spelling == "native":
        before, after = str(root), str(target)
    elif spelling == "escaped":
        before, after = str(root).replace("\\", "\\\\"), str(target).replace("\\", "\\\\")
    else:
        before, after = root.as_posix(), target.as_posix()
    text = before + "/file.py"
    assert DELIVERED["rewrite_path"](text, root, target) == after + "/file.py"


@pytest.mark.parametrize("gap_first", [True, False])
def test_unsupported_report_is_a_gap_but_cannot_hide_a_shell_failure(project, gap_first):
    fail = {"command": "sh -c 'python3 -B -m unittest tests.test_changed'", "result": "PASS"}
    gap = {"command": "sh -c 'unavailable-check --verify'", "result": "PASS"}
    problems, _ = DELIVERED["reports"]([gap], root=project)
    assert DELIVERED["exit_code"](problems) == 3 and "unavailable program" in problems[0]
    problems, _ = DELIVERED["reports"]([gap, fail] if gap_first else [fail, gap], root=project)
    assert DELIVERED["exit_code"](problems) == 1


@pytest.mark.parametrize("status,last,expected", [(0, "false", False), (7, "true", True)])
def test_attached_shell_separator_keeps_the_exact_shell_exit(project, status, last, expected):
    text = f"python3 -c 'raise SystemExit({status})'; {last}"
    assert DELIVERED["report"](text, root=project) is expected


def test_missing_shell_program_is_not_hidden_by_a_later_success(project):
    with pytest.raises(ValueError, match="unavailable program"):
        DELIVERED["report"]("true; unavailable-check; true", root=project)


def test_parenthetical_report_description_is_a_gap_but_shell_groups_are_executed(project):
    with pytest.raises(ValueError, match="unexpanded description"):
        DELIVERED["report"](
            "python3 -m unittest --help; python3 -m unittest (each separately)", root=project
        )
    assert DELIVERED["report"]("false; (exit 0)", root=project)
    assert DELIVERED["report"]("true; (exit 1)", root=project) is False


@needs_make
def test_seed_machinery_runs_on_delivered_content_despite_workspace_edits(project, tmp_path):
    stage = tmp_path / "sealed"
    stage.mkdir()
    shutil.copy2(COMMON / "delivered.py", stage / "delivered.py")
    shutil.copy2(COMMON / "commands.py", stage / "commands.py")
    (project / "scripts").mkdir()
    (project / "scripts/docs_check.py").write_text(
        "from pathlib import Path\nassert Path('README.md').read_text() == 'valid'\n",
        encoding="utf-8",
    )
    (project / "README.md").write_text("valid", encoding="utf-8")
    (project / "scripts/report.py").write_text("raise SystemExit(0)\n", encoding="utf-8")
    (project / "Makefile").write_text(
        "check:\n\tpython3 -B scripts/docs_check.py\n", encoding="utf-8"
    )
    # Seal only a passing seed test; the delivered module must continue to satisfy it.
    (project / "tests/test_changed.py").unlink()
    (project / "feature.py").write_text("VALUE = 0\n", encoding="utf-8")
    assert run(project, "git", "init", "-q").returncode == 0
    commit(project, "Seed")
    assert run(project, "git", "tag", "seed").returncode == 0
    DELIVERED["seal"](project, stage / "seed-checks")
    spec = importlib.util.spec_from_file_location("sealed_delivery", stage / "delivered.py")
    assert spec is not None and spec.loader is not None
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    assert checker.report("make check", root=project)
    (project / "feature.py").write_text("VALUE = 1\n", encoding="utf-8")
    test = project / "tests/test_other.py"
    test.write_text(
        test.read_text(encoding="utf-8") + "    def test_added(self):\n        import feature\n"
        "        self.assertEqual(feature.VALUE, 1)\n",
        encoding="utf-8",
    )
    selected = "python3 -B -m unittest tests.test_other.Other.test_added"
    assert checker.report(selected, root=project)
    (project / "feature.py").write_text("VALUE = 0\n", encoding="utf-8")
    assert checker.report(selected, root=project) is False
    (project / "feature.py").write_text("VALUE = 1\n", encoding="utf-8")
    assert checker.report("python3 scripts/report.py", root=project)
    (project / "scripts/report.py").write_text("raise SystemExit(7)\n", encoding="utf-8")
    assert checker.report("python3 scripts/report.py", root=project) is False
    assert checker.unit(project).returncode == 0
    (project / "scripts/docs_check.py").write_text("raise SystemExit(0)\n", encoding="utf-8")
    (project / "Makefile").write_text("check:\n\ttrue\n", encoding="utf-8")
    (project / "README.md").write_text("broken", encoding="utf-8")
    assert checker.report("make check", root=project) is False
    (project / "tests/test_other.py").write_text(
        "raise RuntimeError('workspace test')\n", encoding="utf-8"
    )
    assert checker.unit(project).returncode == 0


@pytest.mark.parametrize("passing", [True, False])
def test_abbreviated_check_uses_only_its_native_body(project, monkeypatch, passing):
    native = project / "turn.native.jsonl"
    body = (
        "import sys\nassert sys.argv[0] == '-'\nassert 2 + 3 == "
        + ("5" if passing else "6")
        + "\nfrom pathlib import Path\n"
        + f"Path({str(project / 'body-written')!r}).write_text('copy')\n"
        + "print('arithmetic')"
    )
    native.write_text(
        json.dumps(
            {
                "payload": {
                    "item": {
                        "command": [
                            "sh",
                            "-c",
                            "touch forbidden\npython3 -B - <<'PY'\n" + body + "\nPY\n"
                            "python3 -B - <<'OTHER'\n"
                            "note = '(inline arithmetic assertions)'\n"
                            "assert True\nprint('another check')\nOTHER\n",
                        ]
                    }
                }
            }
        )
        + "\n",
        encoding="utf-8",
    )
    turns = project / "turns.json"
    turns.write_text(
        json.dumps({"turns": [{"transcript": str(project / "turn.transcript.txt")}]}),
        encoding="utf-8",
    )
    monkeypatch.setenv("OB_TURNS", str(turns))
    assert (
        DELIVERED["report"]("python3 -B - (inline arithmetic assertions)", root=project) is passing
    )
    assert not (project / "forbidden").exists()
    assert not (project / "body-written").exists()


def test_abbreviated_check_without_native_body_stays_unverified(project):
    with pytest.raises(ValueError, match="no unique native input body"):
        DELIVERED["report"]("python3 -B - (inline arithmetic assertions)", root=project)
