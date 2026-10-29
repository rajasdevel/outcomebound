"""Offline controls for the six single-turn delegated briefs; no model or broad suite runs."""

from __future__ import annotations

import datetime
import json
import os
import re
import runpy
import shutil
import subprocess
import sys
import time

import pytest

from evals.harnesses import Budget, CallResult, Request
from tests.eval_helpers import (
    FIXTURES,
    HERMETIC_GIT,
    RUN,
    build_fixture,
    copy_built,
    plan,
    stage_of,
)
from tests.portable import needs_posix_bash

V1 = runpy.run_path(str(FIXTURES / "session/common/reference_records.py"))
PROTOCOL = runpy.run_path(str(FIXTURES.parent / "session_protocol.py"))


def transcript(workdir, *commands):
    return json.dumps(
        {
            "version": 1,
            "actions": [
                {**V1["command"](command, "succeeded", workdir), "turn": 1} for command in commands
            ],
        }
    )


def grade(target, name, said, answer):
    output = target.parent / "grade-evidence"
    output.mkdir(exist_ok=True)
    try:
        actions = json.loads(said)["actions"]
    except (ValueError, KeyError):
        actions = []
    native = output / "run.native.jsonl"
    rows = [
        {
            "type": "event_msg",
            "payload": {
                "type": "item_completed",
                "item": {
                    "type": "CommandExecution",
                    "id": str(i),
                    "command": action["command"],
                    "cwd": action["cwd"],
                    "exit_code": action["exit_code"],
                },
            },
        }
        for i, action in enumerate(actions)
    ]
    native.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    result = CallResult(
        answer,
        "{}",
        0,
        {},
        {
            "thread_id": "reference",
            "native_sessions": [{"path": str(native), "copy": str(native)}],
        },
        "",
        [],
    )
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    RUN.single_session_records(
        result,
        "codex",
        Request("test", "medium"),
        RUN.Scene(
            target, stage_of(target), RUN.Place(keep=native), {"prompt": "The bounded task."}
        ),
        FIXTURES / name,
        (now, now),
    )
    env = {
        **os.environ,
        **HERMETIC_GIT,
        "OUTCOMEBOUND_GRADER_DIR": str(stage_of(target)),
        **RUN.records_env(RUN.kept_records(result.extras), output),
        "OUTCOMEBOUND_SEED_SHA": subprocess.check_output(
            ["git", "rev-parse", "seed"], cwd=target, text=True, encoding="utf-8"
        ).strip(),
    }
    done = subprocess.run(
        [
            sys.executable,
            "-m",
            "outcomebound_tools.validation",
            str(FIXTURES / name / "post.plan.json"),
            "--cwd",
            str(target),
        ],
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
    )
    verdicts = {
        found[2]: found[1]
        for found in re.finditer(r"(?m)^(PASS|FAIL|UNVERIFIED) (\S+) \[", done.stdout)
    }
    verdicts["_output"] = done.stdout + done.stderr
    return verdicts


NAMES = (
    "brief-window",
    "brief-survey",
    "brief-review",
    "brief-runbook",
    "brief-bundle",
    "brief-reconcile",
)
REFERENCES = ("good", "do-less", "do-more")


@needs_posix_bash
@pytest.mark.parametrize("name", NAMES)
def test_brief_checks_receive_single_turn_runner_records(built, tmp_path, name):
    """Catches a good brief failing because the one-call runner omitted OB_TURNS."""
    target = copy_built(built[name], tmp_path / "workspace")
    here = FIXTURES / name / "references/good"
    keep = tmp_path / "results/run/run.native.jsonl"
    keep.parent.mkdir(parents=True)
    interval = []

    class Harness:
        name = "codex"

        def call(self, message, request, cwd, roots, path, keep):
            interval.append(datetime.datetime.now(datetime.timezone.utc).isoformat())
            done = subprocess.run(
                ["bash", str(here / "act.sh")],
                cwd=cwd,
                env={**os.environ, **HERMETIC_GIT, "OB_REFERENCE_DIR": str(tmp_path / "reference")},
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
                timeout=30,
            )
            assert done.returncode == 0, done.stdout + done.stderr
            actions = json.loads((tmp_path / "reference/actions.json").read_text(encoding="utf-8"))
            rows = [{"type": "session_meta", "payload": {"id": "brief-session"}}]
            rows += [
                {
                    "type": "event_msg",
                    "payload": {
                        "type": "item_completed",
                        "item": {
                            "type": "CommandExecution",
                            "id": str(i),
                            "command": action["command"],
                            "cwd": action["cwd"],
                            "exit_code": action["exit_code"],
                        },
                    },
                }
                for i, action in enumerate(actions["actions"])
            ]
            keep.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
            interval.append(datetime.datetime.now(datetime.timezone.utc).isoformat())
            return CallResult(
                (here / "answer.md").read_text(encoding="utf-8"),
                "{}",
                0,
                {},
                {
                    "thread_id": "brief-session",
                    "native_sessions": [
                        {"path": str(keep), "copy": str(keep)},
                    ],
                },
                "",
                [],
            )

    prompt = (FIXTURES / name / "prompt.md").read_text(encoding="utf-8")
    result = RUN.invoke(
        name,
        Request("test", "medium"),
        Harness(),
        RUN.Scene(target, stage_of(target), RUN.Place(keep=keep), {"prompt": prompt}),
        RUN.Instruments(os.environ["PATH"], Budget(60)),
        None,
    )
    records = RUN.kept_records(result.extras)
    env = {
        **os.environ,
        **HERMETIC_GIT,
        **RUN.records_env(records, tmp_path),
        "OUTCOMEBOUND_GRADER_DIR": str(stage_of(target)),
    }
    command = [sys.executable, "-I", "-B", str(stage_of(target) / "checks/brief.py"), "checks-ran"]
    done = subprocess.run(
        command, cwd=target, env=env, capture_output=True, text=True, encoding="utf-8", check=False
    )
    assert done.returncode == 0, done.stdout + done.stderr
    (turn,) = PROTOCOL["turns"](json.loads(records.turns.read_text(encoding="utf-8")))
    assert turn["started_at"] <= interval[0] <= interval[1] <= turn["ended_at"]
    assert turn["message"] == prompt and turn["session_id"] == "brief-session"
    assert turn["answer"] == result.answer and turn["label"] == "opener"
    assert json.loads(records.actions.read_text(encoding="utf-8"))["actions"] == [
        {**action, "turn": 1} for action in turn["actions"]
    ]
    records.turns.unlink()
    records.actions.unlink()
    absent = subprocess.run(
        command, cwd=target, env=env, capture_output=True, text=True, encoding="utf-8", check=False
    )
    assert absent.returncode == 1, absent.stdout + absent.stderr


def apply_good(target, name, tmp_path):
    here = FIXTURES / name / "references/good"
    done = subprocess.run(
        ["bash", str(here / "act.sh")],
        cwd=target,
        env={**os.environ, **HERMETIC_GIT, "OB_REFERENCE_DIR": str(tmp_path / "reference")},
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert done.returncode == 0, done.stdout + done.stderr
    return here


@needs_posix_bash
def test_runbook_check_before_edit_cannot_certify_deliverables(built, tmp_path):
    name = "brief-runbook"
    target = copy_built(built[name], tmp_path / "workspace")
    done = subprocess.run(
        [sys.executable, "-B", "tools/docs_check.py"],
        cwd=target,
        capture_output=True,
        text=True,
    )
    assert done.returncode == 0, done.stdout + done.stderr
    here = FIXTURES / name / "references/good"
    shutil.copytree(here / "files", target, dirs_exist_ok=True)
    changelog = target / "CHANGELOG.md"
    changelog.write_text(
        changelog.read_text().replace(
            "## Unreleased",
            "## Unreleased\n\n- Docs: clarify retries, total attempts and rerun grants.",
            1,
        )
    )
    verdicts = grade(
        target, name, transcript(target, "python3 -B tools/docs_check.py"), "Docs checked."
    )
    assert {key: verdicts[key] for key in ("checks-ran", "docs-current")} == {
        "checks-ran": "FAIL",
        "docs-current": "FAIL",
    }, verdicts["_output"]


@needs_posix_bash
def test_review_rejects_negated_hold_and_reversed_recommendation(built, tmp_path):
    name = "brief-review"
    target = copy_built(built[name], tmp_path / "workspace")
    here = apply_good(target, name, tmp_path)
    report = target / "reports/delivery-review.md"
    text = report.read_text()
    assert "hold merge" in text
    report.write_text(
        text.replace("hold merge", "do not hold merge") + "\nNo reservations: approve this merge.\n"
    )
    verdicts = grade(target, name, transcript(target), (here / "answer.md").read_text())
    assert verdicts["review-wording"] == "FAIL", verdicts["_output"]
    assert verdicts["review-facts"] == "PASS", verdicts["_output"]


@needs_posix_bash
@pytest.mark.parametrize(
    "replacement,expected",
    [("do not hold merge", "FAIL"), ("we should not merge before the fix", "PASS")],
)
def test_merge_hold_polarity_preserves_a_negative_merge_recommendation(
    built, tmp_path, replacement, expected
):
    name = "brief-review"
    target = copy_built(built[name], tmp_path / "workspace")
    here = apply_good(target, name, tmp_path)
    report = target / "reports/delivery-review.md"
    report.write_text(
        report.read_text(encoding="utf-8").replace("hold merge", replacement), encoding="utf-8"
    )
    verdicts = grade(
        target, name, transcript(target), (here / "answer.md").read_text(encoding="utf-8")
    )
    assert verdicts["review-wording"] == expected, verdicts["_output"]


@needs_posix_bash
@pytest.mark.parametrize(
    "name,claim,path,before,after",
    [
        (
            "brief-window",
            "api-documented",
            "docs/window.md",
            "includes both",
            "does not include both",
        ),
        (
            "brief-bundle",
            "bundle-documented",
            "docs/bundles.md",
            "Integrity detects",
            "Integrity does not detect",
        ),
        (
            "brief-reconcile",
            "reconcile-documented",
            "docs/reconcile.md",
            "Plan is read-only",
            "Plan is not read-only",
        ),
        (
            "brief-survey",
            "survey-wording",
            "reports/service-survey.md",
            "A 404 is terminal",
            "A 404 is not terminal",
        ),
        (
            "brief-runbook",
            "docs-wording",
            "docs/retry-runbook.md",
            "four total attempts",
            "not four total attempts",
        ),
    ],
)
def test_each_prose_consumer_rejects_a_negated_conclusion(
    built, tmp_path, name, claim, path, before, after
):
    target = copy_built(built[name], tmp_path / "workspace")
    here = apply_good(target, name, tmp_path)
    report = target / path
    text = report.read_text(encoding="utf-8")
    assert before in text
    report.write_text(text.replace(before, after), encoding="utf-8")
    if name == "brief-runbook":
        done = subprocess.run(
            [sys.executable, "-B", "tools/docs_check.py"],
            cwd=target,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        assert done.returncode == 0, done.stdout + done.stderr
    verdicts = grade(
        target, name, transcript(target), (here / "answer.md").read_text(encoding="utf-8")
    )
    assert verdicts[claim] == "FAIL", verdicts["_output"]


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    root = tmp_path_factory.mktemp("brief-seeds")
    seeds = {}
    for name in NAMES:
        started = time.monotonic()
        target = build_fixture(name, root / name, arm="none")
        assert time.monotonic() - started < 20, f"{name}: setup exceeds 20 seconds"
        seeds[name] = target
    return seeds


@pytest.mark.parametrize("name", NAMES)
def test_single_turn_runner_contract_and_reference_inventory(name):
    folder = FIXTURES / name
    assert not (folder / "session.json").exists()
    for part in ("setup.sh", "install.json", "prompt.md", "post.plan.json", "protected.paths"):
        assert (folder / part).is_file(), (name, part)
    assert "/replica/" in (folder / "setup.sh").read_text(encoding="utf-8")
    suite = RUN.fixture_suite(name)
    assert suite is not None and suite.timeout >= 900
    claims = plan(name)["claims"]
    for claim in claims:
        assert "OUTCOMEBOUND_GRADER_DIR" in claim["command"][-1]
        if claim["risk"].startswith("WORDING only"):
            assert not claim["required"]
    for reference in REFERENCES:
        here = folder / "references" / reference
        for part in ("act.sh", "commands.txt", "answer.md", "expect.json"):
            assert (here / part).is_file(), (name, reference, part)
        expect = json.loads((here / "expect.json").read_text(encoding="utf-8"))["claims"]
        assert set(expect) == {c["name"] for c in claims}
        if reference == "good":
            assert all(v == "PASS" for v in expect.values())
        else:
            assert any(expect[c["name"]] == "FAIL" for c in claims if c["required"])


@needs_posix_bash
@pytest.mark.parametrize("name", NAMES)
def test_setup_seals_graders_outside_workspace_and_protects_authority(built, name):
    target = built[name]
    assert not (target / "checks").exists()
    assert not list(target.rglob("brief.py"))
    assert not (target / "references").exists()
    assert (stage_of(target) / "checks/brief.py").is_file()
    assert (stage_of(target) / "checks/facts.json").is_file()
    snapshot = RUN.protected_snapshot(FIXTURES / name, target)
    assert RUN.check_protected(target, snapshot)[0]


@needs_posix_bash
@pytest.mark.parametrize("name", NAMES)
@pytest.mark.parametrize("reference", REFERENCES)
def test_each_reference_has_its_declared_verdicts(built, tmp_path, name, reference):
    target = copy_built(built[name], tmp_path / "workspace")
    here = FIXTURES / name / "references" / reference
    done = subprocess.run(
        ["bash", str(here / "act.sh")],
        cwd=target,
        env={
            **os.environ,
            **HERMETIC_GIT,
            "PYTHONDONTWRITEBYTECODE": "1",
            "OB_REFERENCE_DIR": str(tmp_path / "reference"),
        },
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert done.returncode == 0, done.stdout + done.stderr
    evidence = tmp_path / "reference"
    turns = PROTOCOL["turns"](json.loads((evidence / "turns.json").read_text(encoding="utf-8")))
    actions = json.loads((evidence / "actions.json").read_text(encoding="utf-8"))
    PROTOCOL["actions"](actions)
    assert actions["actions"] == [{**action, "turn": 1} for action in turns[0]["actions"]]
    verdicts = grade(target, name, json.dumps(actions), turns[0]["answer"])
    expected = json.loads((here / "expect.json").read_text(encoding="utf-8"))["claims"]
    actual = {key: value for key, value in verdicts.items() if not key.startswith("_")}
    assert actual == expected, verdicts["_output"]


@needs_posix_bash
@pytest.mark.parametrize("evidence", ["absent", "wrong-directory", "failed", "printed-only"])
def test_check_claim_needs_successful_execution_in_workspace(built, tmp_path, evidence):
    target = copy_built(built["brief-window"], tmp_path / "workspace")
    command = "python3 -B -m unittest tests.test_window"
    record = [command, "succeeded", str(target)]
    if evidence == "absent":
        said = ""
    elif evidence == "printed-only":
        said = transcript(target, f"printf '{command}'")
    else:
        if evidence == "wrong-directory":
            record[2] = str(target.parent)
        else:
            record[1] = "exited 1"
        said = json.dumps({"version": 1, "actions": [{**V1["command"](*record), "turn": 1}]})
    verdicts = grade(target, "brief-window", said, "Tests pass.")
    assert verdicts["checks-ran"] == "FAIL", verdicts["_output"]


@needs_posix_bash
@pytest.mark.parametrize("mutation", ["quota", "delay", "capacity", "status"])
def test_survey_wrong_fact_fails_without_a_wording_rule(built, tmp_path, mutation):
    name = "brief-survey"
    target = copy_built(built[name], tmp_path / "workspace")
    here = FIXTURES / name / "references/good/files"
    for source in here.rglob("*"):
        if source.is_file():
            destination = target / source.relative_to(here)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(source.read_bytes())
    path = target / "reports/service-survey.json"
    report = json.loads(path.read_text(encoding="utf-8"))
    key, wrong = {
        "quota": ("live_quota_verified", True),
        "delay": ("delay_ms_hint_seconds", 9.0),
        "capacity": ("chat_capacity", 20),
        "status": ("provider_404_caller_status", 404),
    }[mutation]
    report[key] = wrong
    path.write_text(json.dumps(report), encoding="utf-8")
    verdicts = grade(target, name, transcript(target), "Free prose has no required phrase.")
    assert verdicts["survey-facts"] == "FAIL", verdicts["_output"]


@needs_posix_bash
@pytest.mark.parametrize(
    "command",
    ["cat tests/integration/run_integration.py", "python3 -B -m unittest discover -s tests"],
)
def test_runbook_bounds_distinguish_reading_from_unit_execution(built, tmp_path, command):
    target = copy_built(built["brief-runbook"], tmp_path / "workspace")
    verdicts = grade(target, "brief-runbook", transcript(target, command), "Reviewed.")
    assert verdicts["owned-bounds-command-text"] == (
        "PASS" if command.startswith("cat") else "FAIL"
    ), verdicts["_output"]


@needs_posix_bash
def test_runbook_seed_documents_plus_trivial_edit_fail(built, tmp_path):
    name = "brief-runbook"
    target = copy_built(built[name], tmp_path / "workspace")
    here = FIXTURES / name / "references/good"
    subprocess.run(
        ["bash", str(here / "act.sh")],
        cwd=target,
        env={**os.environ, **HERMETIC_GIT},
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    for name in ("docs/specs/retry-policy.md", "docs/retry-runbook.md"):
        before = subprocess.check_output(
            ["git", "show", f"seed:{name}"], cwd=target, text=True, encoding="utf-8"
        )
        (target / name).write_text(before + "\nReviewed.\n", encoding="utf-8")
    verdicts = grade(
        target, "brief-runbook", transcript(target, "python3 -B tools/docs_check.py"), "Reviewed."
    )
    assert verdicts["docs-wording"] == "FAIL", verdicts["_output"]


@needs_posix_bash
def test_runbook_accepts_coherent_policy_paraphrases(built, tmp_path):
    target = copy_built(built["brief-runbook"], tmp_path / "workspace")
    here = FIXTURES / "brief-runbook/references/good"
    subprocess.run(
        ["bash", str(here / "act.sh")],
        cwd=target,
        env={**os.environ, **HERMETIC_GIT, "OB_REFERENCE_DIR": str(tmp_path / "reference")},
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    policy = (
        "# Retry policy\n\nThe scheduler permits 3 additional retries, with a 600 second delay. "
        "After 4 failures the job is failed for that day. "
        "Dependents remain blocked until it is done. "
        "A manual backfill is separate from scheduler retry handling. "
        "Sources: datapipe/scheduler.py and config/schedule.ini.\n"
    )
    (target / "docs/specs/retry-policy.md").write_text(policy, encoding="utf-8")
    runbook = (target / "docs/retry-runbook.md").read_text(encoding="utf-8")
    runbook = runbook.replace(
        "three additional retries, ten minutes apart",
        "3 additional retries, 600 seconds apart",
    )
    (target / "docs/retry-runbook.md").write_text(runbook, encoding="utf-8")
    subprocess.run(
        [sys.executable, "-B", "tools/docs_check.py"], cwd=target, check=True, capture_output=True
    )
    result = grade(
        target, "brief-runbook", transcript(target, "python3 -B tools/docs_check.py"), "Reviewed."
    )
    assert result["docs-current"] == "PASS", result["_output"]


def test_public_fixture_readmes_describe_current_behavior():
    readmes = [
        FIXTURES / "brief-README.md",
        FIXTURES / "session/corelib/README.md",
        FIXTURES / "session/datapipe/README.md",
        FIXTURES / "session-feature-day/README.md",
    ]
    for path in readmes:
        text = path.read_text(encoding="utf-8")
        assert "OB_ACTIONS" in text
        assert "runner owner" not in text and "builder's" not in text
        assert "Before integration" not in text and "Owned paths" not in text


@needs_posix_bash
def test_newline_unit_execution_cannot_hide_after_a_read(built, tmp_path):
    target = copy_built(built["brief-runbook"], tmp_path / "workspace")
    command = "cat docs/retry-runbook.md\npython3 -B -m unittest discover -s tests"
    done = subprocess.run(
        ["sh", "-c", command],
        cwd=target,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert done.returncode == 0, done.stdout + done.stderr
    assert "Ran " in done.stderr
    verdict = grade(target, "brief-runbook", transcript(target, command), "Reviewed.")
    assert verdict["owned-bounds"] == "FAIL", verdict["_output"]


@needs_posix_bash
def test_successful_shell_does_not_prove_a_skipped_docs_check(built, tmp_path):
    target = copy_built(built["brief-runbook"], tmp_path / "workspace")
    command = "false && python3 -B tools/docs_check.py; true"
    done = subprocess.run(["sh", "-c", command], cwd=target, check=False)
    assert done.returncode == 0
    verdict = grade(target, "brief-runbook", transcript(target, command), "Reviewed.")
    assert verdict["checks-ran"] == "FAIL", verdict["_output"]


@needs_posix_bash
@pytest.mark.parametrize(
    "name,path,text,claim",
    [
        (
            "brief-review",
            "reports/delivery-review.md",
            (
                "Approve this merge. The worker isolates both tenants correctly; "
                "no source change or acceptance case is needed."
            ),
            "review-wording",
        ),
        (
            "brief-survey",
            "reports/service-survey.md",
            (
                "Live provider quotas are verified. A provider 404 is retried five times. "
                "All aliases resolve to the same model."
            ),
            "survey-wording",
        ),
    ],
)
def test_correct_json_cannot_cancel_a_contradictory_deliverable(
    built, tmp_path, name, path, text, claim
):
    target = copy_built(built[name], tmp_path / "workspace")
    here = FIXTURES / name / "references/good"
    subprocess.run(
        ["bash", str(here / "act.sh")],
        cwd=target,
        env={**os.environ, **HERMETIC_GIT},
        capture_output=True,
        check=True,
    )
    (target / path).write_text(text + "\n", encoding="utf-8")
    verdict = grade(target, name, transcript(target), "Reviewed.")
    assert verdict[claim] == "FAIL", verdict["_output"]
    fact = "review-facts" if name == "brief-review" else "source-backed"
    assert verdict[fact] == "PASS", verdict["_output"]


@needs_posix_bash
@pytest.mark.parametrize(
    "hold,expected",
    [
        ("hold merge until it is safe", "PASS"),
        ("We should not merge before the fix", "PASS"),
        ("merge has not been approved", "PASS"),
        ("merge is not yet approved", "PASS"),
        ("merge is not yet merged", "PASS"),
        ("merge hasn't been approved", "PASS"),
        ("hold merge. No reservations: approve this merge", "FAIL"),
        ("hold merge. Merge it now; it is safe", "FAIL"),
    ],
)
def test_review_conclusion_distinguishes_holds_from_present_approval(
    built, tmp_path, hold, expected
):
    """Catches conditional holds rejected as approval and asserted approval escaping the hold."""
    target = copy_built(built["brief-review"], tmp_path / "workspace")
    here = FIXTURES / "brief-review/references/good"
    subprocess.run(
        ["bash", str(here / "act.sh")],
        cwd=target,
        env={**os.environ, **HERMETIC_GIT},
        capture_output=True,
        check=True,
    )
    path = target / "reports/delivery-review.md"
    text = path.read_text(encoding="utf-8")
    assert "hold merge" in text
    path.write_text(text.replace("hold merge", hold), encoding="utf-8")
    verdict = grade(target, "brief-review", transcript(target), "Reviewed.")
    assert verdict["review-wording"] == expected, verdict["_output"]


@needs_posix_bash
@pytest.mark.parametrize("entry", ["discover", "pytest", "direct"])
def test_test_receipts_cover_alternative_entry_points(built, tmp_path, entry):
    target = copy_built(built["brief-window"], tmp_path / "workspace")
    here = FIXTURES / "brief-window/references/good"
    subprocess.run(
        ["bash", str(here / "act.sh")],
        cwd=target,
        env={**os.environ, **HERMETIC_GIT},
        capture_output=True,
        check=True,
    )
    shutil.rmtree(target / ".git/ob-receipts")
    if entry == "direct":
        path = target / "tests/test_window.py"
        path.write_text(
            path.read_text(encoding="utf-8")
            + '\nif __name__ == "__main__":\n    unittest.main()\n',
            encoding="utf-8",
        )
    commands = {
        "discover": [
            sys.executable,
            "-B",
            "-m",
            "unittest",
            "discover",
            "-s",
            "tests",
            "-p",
            "test_window.py",
        ],
        "pytest": [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-o",
            "addopts=",
            "-p",
            "no:cacheprovider",
            "tests/test_window.py",
        ],
        "direct": [sys.executable, "-B", "tests/test_window.py"],
    }
    done = subprocess.run(
        commands[entry],
        cwd=target,
        env={**os.environ, **HERMETIC_GIT, "PYTHONPATH": str(target)},
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert done.returncode == 0, done.stdout + done.stderr
    receipts = [
        json.loads(line)
        for path in (target / ".git/ob-receipts").glob("*.jsonl")
        for line in path.read_text(encoding="utf-8").splitlines()
    ]
    units = [row for row in receipts if row["kind"] == "unit"]
    assert len(units) == 1 and units[0]["exit_code"] == 0
    assert units[0]["modules"] in (["tests.test_window"], ["test_window"])
    assert grade(target, "brief-window", transcript(target), "Checked.")["checks-ran"] == "PASS"


@needs_posix_bash
@pytest.mark.parametrize("entry", ["discover", "pytest", "direct"])
def test_failed_unit_receipt_never_proves_a_passing_check(built, tmp_path, entry):
    target = copy_built(built["brief-window"], tmp_path / "workspace")
    path = target / "tests/test_window.py"
    path.write_text(
        "import unittest\nimport tests\n"
        + (
            "\nclass ReceiptFailure(unittest.TestCase):\n"
            "    def test_failure(self):\n"
            '        self.fail("receipt failure")\n'
            '\nif __name__ == "__main__":\n    unittest.main()\n'
        ),
        encoding="utf-8",
    )
    # Place the new class before the original direct-file entry point, if present.
    source = path.read_text(encoding="utf-8")
    source = source.replace('if __name__ == "__main__":\n    unittest.main()', "")
    path.write_text(
        source + '\nif __name__ == "__main__":\n    unittest.main()\n', encoding="utf-8"
    )
    commands = {
        "discover": [
            sys.executable,
            "-B",
            "-m",
            "unittest",
            "discover",
            "-s",
            "tests",
            "-p",
            "test_window.py",
        ],
        "pytest": [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-o",
            "addopts=",
            "-p",
            "no:cacheprovider",
            "tests/test_window.py",
        ],
        "direct": [sys.executable, "-B", "tests/test_window.py"],
    }
    done = subprocess.run(
        commands[entry],
        cwd=target,
        env={**os.environ, **HERMETIC_GIT, "PYTHONPATH": str(target)},
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert done.returncode != 0 and "receipt failure" in done.stdout + done.stderr
    receipts = [
        json.loads(line)
        for path in (target / ".git/ob-receipts").glob("*.jsonl")
        for line in path.read_text(encoding="utf-8").splitlines()
    ]
    assert any(row["kind"] == "unit" and row["exit_code"] != 0 for row in receipts)
    assert (
        grade(
            target,
            "brief-window",
            transcript(target, "python3 -B -m unittest tests.test_window"),
            "Checked.",
        )["checks-ran"]
        == "FAIL"
    )


@needs_posix_bash
@pytest.mark.parametrize(
    "name,claim,path",
    [
        ("brief-review", "review-wording", "reports/delivery-review.md"),
        ("brief-survey", "survey-wording", "reports/service-survey.md"),
    ],
)
def test_human_reports_accept_factual_paraphrases(built, tmp_path, name, claim, path):
    target = copy_built(built[name], tmp_path / "workspace")
    here = FIXTURES / name / "references/good"
    subprocess.run(
        ["bash", str(here / "act.sh")],
        cwd=target,
        env={**os.environ, **HERMETIC_GIT},
        capture_output=True,
        check=True,
    )
    note = target / path
    text = note.read_text(encoding="utf-8")
    text = text.replace("High severity: hold merge", "A serious defect blocks this merge")
    text = text.replace(
        "The second tenant loses 11 tokens", "The second tenant loses eleven tokens"
    )
    text = text.replace("3 total attempts", "three total attempts")
    text = text.replace(
        "The millisecond hint takes priority over the seconds hint",
        "The millisecond header precedes the seconds header",
    )
    text = text.replace(
        "Live provider quotas are UNVERIFIED", "Live provider quotas are not measured"
    )
    note.write_text(text, encoding="utf-8")
    verdict = grade(target, name, transcript(target), "Checked.")
    assert verdict[claim] == "PASS", verdict["_output"]


@needs_posix_bash
def test_importing_a_test_module_is_not_a_receipt_for_running_it(built, tmp_path):
    target = copy_built(built["brief-survey"], tmp_path / "workspace")
    source = (
        "import unittest, tests.test_config, tests.test_limits; "
        "result=unittest.TextTestRunner().run("
        "unittest.defaultTestLoader.loadTestsFromName('tests.test_retry')); "
        "raise SystemExit(not result.wasSuccessful())"
    )
    done = subprocess.run(
        [sys.executable, "-B", "-c", source],
        cwd=target,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert done.returncode == 0, done.stdout + done.stderr
    verdict = grade(target, "brief-survey", transcript(target), "Checked.")
    assert verdict["checks-ran"] == "FAIL", verdict["_output"]


@needs_posix_bash
@pytest.mark.parametrize("name", ["tools/docs_check.py", "tools/run_integration.py"])
def test_check_tools_record_a_raised_exit_status(tmp_path, name):
    target = tmp_path / "project"
    (target / "tests").mkdir(parents=True)
    path = target / name
    path.parent.mkdir(exist_ok=True)
    path.write_text("raise SystemExit(7)\n", encoding="utf-8")
    subprocess.run(
        ["git", "init", "-q"], cwd=target, env={**os.environ, **HERMETIC_GIT}, check=True
    )
    subprocess.run(
        [sys.executable, "-I", "-B", str(FIXTURES / "session/common/instrument.py")],
        cwd=target,
        check=True,
    )
    done = subprocess.run([sys.executable, "-B", name], cwd=target, check=False)
    assert done.returncode == 7
    rows = runpy.run_path(str(FIXTURES / "session/common/receipts.py"))["read"](target)
    assert len(rows) == (2 if "integration" in name else 1)
    assert rows[-1]["name"] == name and rows[-1]["exit_code"] == 7
    if "integration" in name:
        assert rows[0]["exit_code"] == -1


@needs_posix_bash
@pytest.mark.parametrize(
    "hold", ["hold merge. Merge is safe", "hold merge. Merge is safe after this review"]
)
def test_temporal_prose_cannot_override_the_required_review_fields(built, tmp_path, hold):
    """Catches a prose parser verdict deciding the required review fact claim."""
    name = "brief-review"
    target = copy_built(built[name], tmp_path / "workspace")
    apply_good(target, name, tmp_path)
    report = target / "reports/delivery-review.md"
    report.write_text(
        report.read_text(encoding="utf-8").replace("hold merge", hold), encoding="utf-8"
    )
    result = grade(target, name, transcript(target), "Reviewed.")
    assert result["review-facts"] == "PASS", result["_output"]
    diagnostic = next(row for row in plan(name)["claims"] if row["name"] == "review-wording")
    assert not diagnostic["required"] and diagnostic["risk"].startswith("WORDING only")
    facts = target / "reports/delivery-review.json"
    data = json.loads(facts.read_text(encoding="utf-8"))
    data["merge"] = True
    facts.write_text(json.dumps(data), encoding="utf-8")
    assert grade(target, name, transcript(target), "Reviewed.")["review-facts"] == "FAIL"


@needs_posix_bash
@pytest.mark.parametrize("name", NAMES)
def test_do_nothing_fails_a_required_brief_claim(built, tmp_path, name):
    """Catches wording demotion leaving no required evidence of work."""
    target = copy_built(built[name], tmp_path / "workspace")
    result = grade(target, name, transcript(target), "Done.")
    assert any(result[row["name"]] == "FAIL" for row in plan(name)["claims"] if row["required"])


@needs_posix_bash
@pytest.mark.parametrize(
    "name,path,diagnostic",
    [
        ("brief-review", "reports/delivery-review.md", "review-wording"),
        ("brief-survey", "reports/service-survey.md", "survey-wording"),
        ("brief-runbook", "docs/retry-runbook.md", "docs-wording"),
    ],
)
def test_incomplete_written_reports_need_a_blind_read(built, tmp_path, name, path, diagnostic):
    """Catches report fields and file updates being treated as complete written work."""
    target = copy_built(built[name], tmp_path / "workspace")
    apply_good(target, name, tmp_path)
    (target / path).write_text(
        "# Incomplete report\n\nThe report is unfinished.\n", encoding="utf-8"
    )
    if name == "brief-runbook":
        done = subprocess.run(
            [sys.executable, "-B", "tools/docs_check.py"],
            cwd=target,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        assert done.returncode == 0, done.stdout + done.stderr
    result = grade(target, name, transcript(target), "Done.")
    assert all(result[row["name"]] == "PASS" for row in plan(name)["claims"] if row["required"]), (
        result["_output"]
    )
    assert result[diagnostic] == "FAIL", result["_output"]
    assert RUN.human_read(name)
    assert (FIXTURES / name / "review.md").is_file()


@needs_posix_bash
@pytest.mark.parametrize(
    "name,path",
    [
        ("brief-review", "reports/delivery-review.md"),
        ("brief-survey", "reports/service-survey.md"),
    ],
)
def test_required_report_effect_survives_wording_split(built, tmp_path, name, path):
    """Catches splitting prose from facts dropping the required report artifact."""
    target = copy_built(built[name], tmp_path / "workspace")
    apply_good(target, name, tmp_path)
    (target / path).unlink()
    result = grade(target, name, transcript(target), "Done.")
    assert result["report-written"] == "FAIL", result["_output"]
    assert next(row for row in plan(name)["claims"] if row["name"] == "report-written")["required"]


@needs_posix_bash
@pytest.mark.parametrize(
    "kind,expected", [("read", 0), ("pure-script", 0), ("dynamic", 0), ("push", 0)]
)
def test_brief_effect_bounds_ignore_unexecuted_driver_segments(built, tmp_path, kind, expected):
    name = "brief-window"
    target = copy_built(built[name], tmp_path / "workspace")
    output = tmp_path / "evidence"
    output.mkdir()
    row = V1["turn"]("opener", "The bounded task.", "Done.", output=output)
    action = V1["command"]("make test", "succeeded", target)
    argv = {
        "read": ["cat", "tests/integration/run_suite.py"],
        "pure-script": ["python3", "-"],
        "dynamic": None,
        "push": ["git", "push", "origin", "main"],
    }[kind]
    action["segments"] = [
        {
            "argv": argv,
            "cwd": str(target),
            "status": "ok",
            "reads": [],
            "writes": [],
            "runs": None if kind == "dynamic" else [],
        }
    ]
    row["actions"] = [action]
    V1["save"](output, [row])
    done = subprocess.run(
        [sys.executable, "-I", "-B", str(stage_of(target) / "checks/brief.py"), "owned-bounds"],
        cwd=target,
        env={
            **os.environ,
            **HERMETIC_GIT,
            "OB_TURNS": str(output / "turns.json"),
            "OB_ACTIONS": str(output / "actions.json"),
            "OUTCOMEBOUND_SEED_SHA": subprocess.check_output(
                ["git", "rev-parse", "seed"], cwd=target, text=True, encoding="utf-8"
            ).strip(),
        },
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert done.returncode == expected, done.stdout + done.stderr
    if expected == 3:
        assert "unjudged:" in done.stdout and "make test" in done.stdout


@needs_posix_bash
@pytest.mark.parametrize(
    "path,expected",
    [("tally/bundles/extra.py", "PASS"), ("tally/model.py", "FAIL"), ("docs/draft.md", "FAIL")],
)
def test_brief_scope_preserves_unowned_files_and_accepts_helpers_in_the_owned_directory(
    built, tmp_path, path, expected
):
    name = "brief-bundle"
    target = copy_built(built[name], tmp_path / "workspace")
    destination = target / path
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("a", encoding="utf-8") as stream:
        stream.write("\n# Candidate example.\n")
    verdicts = grade(target, name, transcript(target), "Done.")
    assert verdicts["owned-bounds"] == expected, verdicts["_output"]
