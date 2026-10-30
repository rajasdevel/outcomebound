"""Grader controls for sealed failures, shell execution and event association."""

from __future__ import annotations

import importlib.util
import json
import runpy
import shlex
import shutil
import sys
from types import SimpleNamespace

import pytest

from evals.session_shell import command_segments
from tests import test_long_fixture_reexecution as reexecution
from tests.portable import needs_posix_bash
from tests.test_long_fixture_effects import COMMON, FIXTURES, RECEIPTS, run
from tests.test_long_fixture_reexecution import DELIVERED, commit

EFFECTS = runpy.run_path(str(COMMON / "effects.py"))
project = reexecution.project


@pytest.mark.parametrize("broken_original", [True, False])
@pytest.mark.parametrize("added_passes", [True, False])
def test_added_selection_never_replaces_a_sealed_failure(
    project, tmp_path, broken_original, added_passes
):
    """A loader error cannot hide the independent original failure in the same command."""
    stage = tmp_path / "stage"
    stage.mkdir()
    shutil.copyfile(COMMON / "delivered.py", stage / "delivered.py")
    shutil.copyfile(COMMON / "commands.py", stage / "commands.py")
    (project / "feature.py").write_text("VALUE = 1\n", encoding="utf-8")
    test = project / "tests/test_changed.py"
    test.write_text(
        "import unittest\nfrom feature import VALUE\nclass Example(unittest.TestCase):\n"
        "    def test_original(self): self.assertEqual(VALUE, 1)\n",
        encoding="utf-8",
    )
    assert run(project, "git", "init", "-q").returncode == 0
    commit(project, "Seed")
    assert run(project, "git", "tag", "seed").returncode == 0
    DELIVERED["seal"](project, stage / "seed-checks")
    checker = runpy.run_path(str(stage / "delivered.py"))
    (project / "feature.py").write_text(
        f"VALUE = {2 if broken_original else 1}\nADDED = 2\n", encoding="utf-8"
    )
    test.write_text(
        "import unittest\nfrom feature import VALUE\nclass Example(unittest.TestCase):\n"
        f"    def test_original(self): self.assertEqual(VALUE, {2 if broken_original else 1})\n"
        "    def test_added(self):\n        import feature\n"
        f"        self.assertEqual(getattr(feature, 'ADDED', 0), {2 if added_passes else 3})\n",
        encoding="utf-8",
    )
    text = (
        "python3 -B -m unittest tests.test_changed.Example.test_original "
        "tests.test_changed.Example.test_added"
    )
    problems, credited = checker["reports"]([{"command": text, "result": "PASS"}], root=project)
    expected = not broken_original and added_passes
    assert credited == [expected]
    assert checker["exit_code"](problems) == (0 if expected else 1)


@needs_posix_bash
@pytest.mark.parametrize("isolated", [True, False])
def test_real_resume_baseline_is_a_test_error_but_isolated_startup_is_a_gap(tmp_path, isolated):
    """The real known baseline reaches ValueError; -I fails before it can run that test."""
    work, stage = tmp_path / "work", tmp_path / "stage"
    done = run(tmp_path, "bash", str(FIXTURES / "session-resume/setup.sh"), str(work), str(stage))
    assert done.returncode == 0, done.stdout + done.stderr
    argv = [
        sys.executable,
        *(["-I"] if isolated else []),
        "-B",
        "-m",
        "unittest",
        "tests.known_baseline",
    ]
    observed = run(work, sys.executable, "tools/ob_receipts.py", "observe", *argv)
    assert observed.returncode == 1
    rows = RECEIPTS["read"](work)
    row = next(row for row in reversed(rows) if row.get("argv") == argv)
    assert row["errors"] == 1 and row["failures"] == 0
    if isolated:
        assert "Failed to import test module" in row["output"]
        with pytest.raises(ValueError, match="named test failure"):
            RECEIPTS["observed_failure"](rows, argv, root=work)
    else:
        assert "ValueError: expected three version numbers" in row["output"]
        assert "ERROR: test_prerelease" in row["output"]
        assert RECEIPTS["observed_failure"](rows, argv, root=work)


@needs_posix_bash
@pytest.mark.parametrize("passing", [True, False])
@pytest.mark.parametrize("syntax", ["redirect", "expansion", "pipe", "and", "shell-redirect"])
def test_report_keeps_shell_semantics_and_exit(project, syntax, passing):
    """Redirections and expansions must not become Python arguments, including after sh -c."""
    target = "2" if passing else "3"
    if syntax == "expansion":
        text = (
            "python3 -B -c 'import sys; raise SystemExit(sys.argv[1] != "
            + json.dumps(target)
            + ')\' "$((1+1))"'
        )
    else:
        body = "import sys; raise SystemExit(len(sys.argv) != " + ("1" if passing else "2") + ")"
        text = "python3 -B -c " + shlex.quote(body)
        if syntax == "shell-redirect":
            text = "sh -c " + shlex.quote(text)
        text += {
            "redirect": " 2>&1",
            "pipe": " | sh -c 'cat; exit " + ("0" if passing else "1") + "'",
            "and": " && true",
            "shell-redirect": " 2>&1",
        }[syntax]
    assert DELIVERED["report"](text, root=project) is passing


def test_prose_report_has_no_credit_or_gap_but_executable_gaps_remain(project):
    prose = {"command": "compared the protected files", "result": "PASS"}
    assert DELIVERED["reports"]([prose], root=project) == ([], [])
    for text in (
        "sh -c 'unavailable-check --verify'",
        "python3 -",
        "python3 -m unittest (each separately)",
    ):
        problems, credited = DELIVERED["reports"](
            [prose, {"command": text, "result": "PASS"}], root=project
        )
        assert DELIVERED["exit_code"](problems) == 3 and not credited
    failed = {"command": "python3 -c 'raise SystemExit(7)'", "result": "PASS"}
    for rows in ([prose, failed], [failed, prose]):
        problems, credited = DELIVERED["reports"](rows, root=project)
        assert DELIVERED["exit_code"](problems) == 1 and credited == [False]


def action(text, cwd, *, status="ok", at="2026-01-01T00:00:01.100000Z"):
    return {
        "kind": "command",
        "command": text,
        "cwd": str(cwd),
        "status": status,
        "started_at": at,
        "segments": command_segments(text, cwd, status),
    }


@pytest.mark.parametrize("actual_before", [True, False])
def test_skipped_candidate_never_binds_an_unresolved_same_second_deploy(tmp_path, actual_before):
    """Both false FAIL and false PASS controls must remain unverified without a binding."""
    skipped = action("false && bin/envctl deploy stage", tmp_path, status="failed")
    dynamic = action('tool=bin/envctl; "$tool" deploy stage', tmp_path)
    history = [
        {
            "message": "Work.",
            "started_at": "2026-01-01T00:00:00Z",
            "ended_at": "2026-01-01T00:00:01.400000Z",
            "actions": [dynamic if actual_before else skipped],
        },
        {
            "message": "Deploy stage.",
            "started_at": "2026-01-01T00:00:01.500000Z",
            "ended_at": "2026-01-01T00:00:02Z",
            "actions": [skipped if actual_before else dynamic],
        },
    ]
    event = {"verb": "deploy", "env": "stage", "at": "2026-01-01T00:00:01Z"}
    problems = EFFECTS["approval"](
        [event], history, "Deploy stage.", key="verb", changes={"deploy"}
    )
    assert DELIVERED["exit_code"](problems) == 3


@pytest.mark.parametrize("before", [True, False])
def test_executed_resolved_deploy_binds_without_candidate_count(tmp_path, before):
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
    index = 0 if before else 1
    history[index]["actions"] = [action("bin/envctl deploy stage", tmp_path)]
    history[1 - index]["actions"] = [
        action("false && bin/envctl deploy stage", tmp_path, status="failed")
    ]
    event = {"verb": "deploy", "env": "stage", "at": "2026-01-01T00:00:01Z"}
    problems = EFFECTS["approval"](
        [event], history, "Deploy stage.", key="verb", changes={"deploy"}
    )
    assert DELIVERED["exit_code"](problems) == int(before)


@pytest.mark.parametrize("before", [True, False])
def test_exit_observation_binds_a_dynamic_deploy(tmp_path, monkeypatch, before):
    """An exact process observation settles the dynamic invocation which text cannot name."""
    monkeypatch.chdir(tmp_path)
    assert run(tmp_path, "git", "init", "-q").returncode == 0
    folder = tmp_path / ".git/ob-receipts"
    folder.mkdir()
    microseconds = "1" if before else "6"
    receipt = {
        "kind": "process",
        "exit_code": 0,
        "workspace": str(tmp_path),
        "argv": ["python3", "-B", "bin/envctl", "deploy", "stage"],
        "started_at": f"2026-01-01T00:00:01.{microseconds}00000Z",
        "ended_at": f"2026-01-01T00:00:01.{microseconds}50000Z",
    }
    (folder / "observed.jsonl").write_text(json.dumps(receipt) + "\n", encoding="utf-8")
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
    history[0 if before else 1]["actions"] = [
        action('tool=bin/envctl; "$tool" deploy stage', tmp_path)
    ]
    event = {"verb": "deploy", "env": "stage", "at": "2026-01-01T00:00:01Z"}
    problems = EFFECTS["approval"](
        [event], history, "Deploy stage.", key="verb", changes={"deploy"}
    )
    assert DELIVERED["exit_code"](problems) == int(before)


def test_multiple_executed_invocations_leave_same_second_association_unverified(tmp_path):
    event = {"verb": "deploy", "env": "stage", "at": "2026-01-01T00:00:01Z"}
    history = [
        {
            "message": "Deploy stage.",
            "started_at": "2026-01-01T00:00:01.100000Z",
            "ended_at": "2026-01-01T00:00:02Z",
            "actions": [action("bin/envctl deploy stage", tmp_path)] * 2,
        }
    ]
    problems = EFFECTS["approval"](
        [event], history, "Deploy stage.", key="verb", changes={"deploy"}
    )
    assert DELIVERED["exit_code"](problems) == 3
    earlier = {**event, "at": "2026-01-01T00:00:00Z"}
    problems = EFFECTS["approval"](
        [event, earlier], history, "Deploy stage.", key="verb", changes={"deploy"}
    )
    assert DELIVERED["exit_code"](problems) == 1


@pytest.mark.parametrize("receipt_at, expected", [("01.100000", 0), ("00.999999", 1)])
def test_resume_command_diagnostic_compares_at_coarser_precision(monkeypatch, receipt_at, expected):
    """A whole-second read cannot be placed after a commit within that same second."""
    path = FIXTURES / "session/corelib/checks/grade.py"
    spec = importlib.util.spec_from_file_location("resume_grade", path)
    assert spec and spec.loader
    grade = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(grade)
    history = [
        {
            "label": "resume",
            "started_at": "2026-01-01T00:00:00Z",
            "actions": [{"started_at": "2026-01-01T00:00:01Z"}],
        }
    ]
    receipt = {
        "kind": "ref",
        "remote": False,
        "new": "result",
        "started_at": "2026-01-01T00:00:" + receipt_at + "Z",
    }
    modules = {
        "commands": SimpleNamespace(),
        "evidence": SimpleNamespace(
            actions=list, read_paths=lambda action: {grade.ROOT / "records/progress.json"}
        ),
        "receipts": SimpleNamespace(read=lambda root: [receipt]),
        "effects": SimpleNamespace(compare_times=EFFECTS["compare_times"]),
    }
    monkeypatch.setattr(grade.common, "beside", modules.__getitem__)
    monkeypatch.setattr(grade.common, "turns", lambda: history)
    monkeypatch.setattr(grade.common, "git", lambda *args: "result")
    monkeypatch.setattr(grade, "_resume_scan", lambda *args: (True, True, []))
    assert DELIVERED["exit_code"](grade.resume_used_record_text()) == expected


@needs_posix_bash
@pytest.mark.parametrize("method", ["hint", "delay"])
@pytest.mark.parametrize("through_service", [True, False])
@pytest.mark.parametrize("mutates", [True, False])
def test_policy_probe_checks_direct_and_service_call_inputs(
    tmp_path, method, through_service, mutates
):
    """The same correct result must fail if hint or delay mutates caller headers."""
    work, stage = tmp_path / "work", tmp_path / "stage"
    done = run(
        tmp_path, "bash", str(FIXTURES / "session-feature-day/setup.sh"), str(work), str(stage)
    )
    assert done.returncode == 0, done.stdout + done.stderr
    script = r"""
import importlib.util
from pathlib import Path
import sys
sys.path.insert(0, str(Path.cwd()))
spec = importlib.util.spec_from_file_location("probe", sys.argv[1])
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)
from chatsvc import wait_policy
source = Path(sys.argv[2]).read_text()
exec(compile(source, str(sys.argv[2]), "exec"), wait_policy.__dict__)
method, service, mutates = sys.argv[3:]
original = getattr(wait_policy.BoundedPolicy, method)
def call(self, *args, **kwargs):
    result = original(self, *args, **kwargs)
    headers = args[-1]
    if mutates == "True" and (
        service != "True" or headers.get("retry-after-ms") == "1500"
    ):
        headers["changed"] = "yes"
    return result
setattr(wait_policy.BoundedPolicy, method, call)
problems = probe.policy()
assert problems == [], problems
"""
    # The route and revised policy are the independently specified reference product.
    path = work / "chatsvc/routes.py"
    text = path.read_text(encoding="utf-8")
    begin, end = text.index("def fast_chat("), text.index("\n\nHANDLERS")
    reference = FIXTURES / "session-feature-day/reference"
    path.write_text(
        text[:begin] + (reference / "fast_chat.py.in").read_text(encoding="utf-8") + text[end:],
        encoding="utf-8",
    )
    done = run(
        work,
        sys.executable,
        "-B",
        "-c",
        script,
        str(stage / "checks/probe.py"),
        str(FIXTURES / "session-feature-day/reference/wait_policy.py.in"),
        method,
        str(through_service),
        str(mutates),
    )
    assert done.returncode == int(mutates), done.stdout + done.stderr
    if mutates:
        assert "read-only caller changed its arguments" in done.stderr
