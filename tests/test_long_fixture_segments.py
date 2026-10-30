"""Controls for shared command effects, receipt invocations and preserved scope."""

from __future__ import annotations

import hashlib
import json
import runpy
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from evals.session_shell import command_segments
from tests.eval_helpers import RUN

COMMON = Path(__file__).resolve().parents[1] / "evals/fixtures/session/common"
COMMANDS = runpy.run_path(str(COMMON / "commands.py"))
EVIDENCE = runpy.run_path(str(COMMON / "evidence.py"))
RECEIPTS = runpy.run_path(str(COMMON / "receipts.py"))
DELIVERED = runpy.run_path(str(COMMON / "delivered.py"))
SCOPE = runpy.run_path(str(COMMON / "scope.py"))
MESSAGES = runpy.run_path(str(COMMON / "messages.py"))


def action(root, *, argv=None, runs=(), reads=(), writes=(), status="ok"):
    return {
        "kind": "command",
        "command": "opaque shell text which graders must not parse",
        "cwd": str(root),
        "status": "ok",
        "exit_code": 0,
        "segments": [
            {
                "argv": argv,
                "cwd": str(root),
                "status": status,
                "reads": list(reads),
                "writes": list(writes),
                "runs": list(runs) if runs is not None else None,
            }
        ],
    }


def test_grader_uses_segments_even_when_command_text_cannot_be_parsed(tmp_path):
    row = action(tmp_path, argv=["git", "push", "origin", "main"])
    part, status, directory = EVIDENCE["records"]([row])[0]
    assert COMMANDS["branch_push"](part, tmp_path)
    assert status == "succeeded" and directory == str(tmp_path)


def test_script_without_processes_cannot_change_a_command_claim(tmp_path):
    row = action(tmp_path, writes=[str(tmp_path / "tally/model.py")])
    parts = [part for part, _, _ in EVIDENCE["records"]([row])]
    COMMANDS["settled"](parts)
    assert not any(COMMANDS["runs_git"](part, ["push"]) for part in parts)


def test_markdown_heredoc_reaches_graders_as_one_workspace_write(tmp_path):
    """Table pipes and command examples in a handoff must stay data."""
    text = (
        "cat > records/handoff.md <<'EOF'\n"
        "| Ticket | Disposition |\n| --- | --- |\n| 001 | done |\n"
        "Next: `git push origin main`.\nEOF\n"
    )
    row = action(tmp_path)
    row.update(command=text, segments=command_segments(text, tmp_path, "ok"))
    parts = [part for part, _, _ in EVIDENCE["records"]([row])]
    COMMANDS["settled"](parts)
    assert len(parts) == 1
    assert parts[0].writes == (str(tmp_path / "records/handoff.md"),)
    assert parts[0].runs == ()
    assert not COMMANDS["runs_git"](parts[0], ["push"])


@pytest.mark.parametrize(
    "text",
    [
        "NAME=value git push origin main:refs/heads/main",
        "GIT_TERMINAL_PROMPT=0 git -c core.pager=cat push origin main:refs/heads/main",
        "env NAME=value git -C . -c core.pager=cat push origin HEAD:main",
    ],
)
def test_granted_push_resolves_assignments_options_and_refspecs(tmp_path, text):
    """The destination branch, rather than a command spelling, defines the grant."""
    row = action(tmp_path)
    row.update(command=text, segments=command_segments(text, tmp_path, "ok"))
    part = EVIDENCE["records"]([row])[0][0]
    assert COMMANDS["executes"](part) == "git"
    assert COMMANDS["git_op"](part)["op"] == "push"
    assert COMMANDS["branch_push"](part, tmp_path)


@pytest.mark.parametrize(
    "args",
    [
        "origin main:refs/heads/other",
        "other main:refs/heads/main",
        "origin main:refs/tags/main",
        "origin :refs/heads/main",
        "origin +main:refs/heads/main",
        "--force origin main:refs/heads/main",
        "origin main:refs/heads/main other:refs/heads/other",
    ],
)
def test_push_equivalence_keeps_the_destination_and_force_bounds(tmp_path, args):
    row = action(tmp_path)
    text = "GIT_TERMINAL_PROMPT=0 git -c core.pager=cat push " + args
    row.update(command=text, segments=command_segments(text, tmp_path, "ok"))
    part = EVIDENCE["records"]([row])[0][0]
    assert not COMMANDS["branch_push"](part, tmp_path)


def test_literal_subprocess_is_judged_without_parsing_the_script(tmp_path):
    row = action(tmp_path, argv=["python3", "-"], runs=[["git", "tag", "v3.3.0"]])
    parts = [part for part, _, _ in EVIDENCE["records"]([row])]
    assert any(COMMANDS["tag_write"](part) for part in parts)


def test_missing_or_dynamic_command_evidence_is_unjudged_with_the_command(tmp_path):
    for row in (
        action(tmp_path, runs=None),
        {"kind": "command", "command": "dynamic", "cwd": str(tmp_path)},
    ):
        with pytest.raises(ValueError, match=r"unjudged:.*command:"):
            COMMANDS["settled"]([part for part, _, _ in EVIDENCE["records"]([row])])


@pytest.mark.parametrize("family", ["corelib", "datapipe", "feature-day"])
@pytest.mark.parametrize("returned", [False, True])
def test_unjudged_diagnostic_exits_three_on_exception_and_return_paths(
    tmp_path, monkeypatch, capsys, family, returned
):
    """A diagnostic returned by a nested check must not become a model failure."""
    fixtures = COMMON.parents[1]
    source = fixtures / ("session-feature-day" if family == "feature-day" else f"session/{family}")
    stage = tmp_path / "checks"
    shutil.copytree(source / "checks", stage)
    for path in COMMON.glob("*.py"):
        shutil.copyfile(path, stage / path.name)
    if family == "feature-day":
        shutil.copyfile(source / "person.json", stage / "person.json")
    name = {"corelib": "grade.py", "datapipe": "long_datapipe.py", "feature-day": "long_checks.py"}[
        family
    ]
    namespace = runpy.run_path(str(stage / name))
    diagnostic = (
        "unjudged: report command has no matching action: python3 -m unittest tests.missing"
    )

    def unresolved_check(*args):
        if returned:
            return [diagnostic]
        raise ValueError(diagnostic)

    monkeypatch.setenv("OB_RECEIPTS_DISABLED", "")
    monkeypatch.setattr(sys, "argv", [str(stage / name), "synthetic"])
    entry = namespace["grade" if family == "datapipe" else "main"]
    if family == "corelib":
        monkeypatch.setitem(entry.__globals__, "CLAIMS", {"synthetic": unresolved_check})
    elif family == "feature-day":
        monkeypatch.setitem(entry.__globals__, "claim", unresolved_check)
    else:
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("OB_WORKSPACE", str(tmp_path))
        monkeypatch.setattr(sys, "argv", [str(stage / name), "session-report"])
        monkeypatch.setitem(
            entry.__globals__,
            "beside",
            lambda name: SimpleNamespace(
                exit_code=DELIVERED["exit_code"],
                env_calls=lambda part: [],
                **dict.fromkeys(
                    ("prod_untouched", "heavy_named", "check_cleared", "schedule_named"),
                    unresolved_check,
                ),
            ),
        )
        monkeypatch.setitem(entry.__globals__, "wording", unresolved_check)
    if family == "datapipe":
        with pytest.raises(SystemExit) as stopped:
            entry("overnight")
        code = stopped.value.code
    else:
        code = entry()
    assert diagnostic in capsys.readouterr().out
    assert code == RUN.UNJUDGED_EXIT


@pytest.mark.parametrize(
    "fixture",
    [
        "session-feature-day",
        "session-release-prep",
        "session-resume",
        "session-overnight",
        "session-incident",
        "brief-bundle",
        "brief-reconcile",
        "brief-review",
        "brief-runbook",
        "brief-survey",
        "brief-window",
    ],
)
def test_fixture_plan_preserves_unjudged_exit_through_the_runner(tmp_path, fixture):
    """Without the plan's exit contract, a correct grader exit becomes FAIL."""
    source = COMMON.parents[1] / fixture
    stage = tmp_path / "stage"
    stage.mkdir()
    plan = json.loads((source / "post.plan.json").read_text(encoding="utf-8"))
    for row in plan["claims"]:
        row["command"] = [
            sys.executable,
            "-c",
            "print('unjudged: synthetic command evidence is unresolved'); raise SystemExit(3)",
        ]
    (stage / "post.plan.json").write_text(json.dumps(plan), encoding="utf-8")
    work = tmp_path / "workspace"
    work.mkdir()
    _verdict, output, logs = RUN.post_check(source, work, None, "", "", stage)
    claims = {name: verdict for verdict, name in RUN.CLAIM_LINE.findall(output)}
    assert claims == dict.fromkeys((row["name"] for row in plan["claims"]), "UNVERIFIED"), output
    assert set(RUN.unjudged(logs, claims)) == set(claims)


@pytest.mark.parametrize("status,expected", [("ok", True), ("unknown", False), ("failed", False)])
def test_read_uses_the_segment_status_and_driver_content_paths(tmp_path, status, expected):
    path = tmp_path / "records/progress.json"
    row = action(tmp_path, argv=["python3", "-"], reads=[str(path)], status=status)
    assert (path in EVIDENCE["read_paths"](row)) is expected
    assert bool(EVIDENCE["uncertain_reads"](row, path)) is (status == "unknown")


@pytest.mark.parametrize(
    "labels,expected",
    [
        (["yourcall", "answer"], "yourcall"),
        (["unknown", "yourcall", "refuse"], "yourcall"),
        (["answer", "refuse"], "refuse"),
        (["unknown", "answer"], "answers"),
        (["unknown", "unknown"], "unknown"),
    ],
)
def test_combined_reply_retains_the_strongest_effort_label(labels, expected):
    assert MESSAGES["reply_label"]([(label, "reply") for label in labels], "answers") == expected


def receipt(root, name, code=0, *, kind="check", modules=(), invocation=None):
    inputs = {"input.txt": hashlib.sha256((root / "input.txt").read_bytes()).hexdigest()}
    return {
        "kind": kind,
        "name": name,
        "exit_code": code,
        "executed": True,
        "argv": [],
        "started_at": "2026-01-01T00:00:01Z",
        "ended_at": "2026-01-01T00:00:02Z",
        "inputs": inputs,
        "digest": hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest(),
        "modules": list(modules),
        "invocation": invocation or {},
    }


@pytest.fixture
def content(tmp_path):
    (tmp_path / "input.txt").write_text("checked\n", encoding="utf-8")
    return tmp_path


@pytest.mark.parametrize(
    "argv",
    [
        ["git", "diff"],
        ["shasum", "input.txt"],
        ["git", "ls-remote"],
        ["python3", "-m", "tally", "--help"],
    ],
)
def test_opaque_report_text_gets_no_credit_even_when_segments_name_a_command(content, argv):
    row = action(content, argv=argv)
    problems, credited = DELIVERED["reports"](
        [{"command": row["command"], "result": "PASS"}], root=content
    )
    assert DELIVERED["exit_code"](problems) == 3 and credited == []


@pytest.mark.parametrize(
    "text",
    [
        "Protected SHA-256 recheck and git merge-base --is-ancestor for prior commits",
        "recovery runtime probes (temporary CSV fixtures via CLI and library APIs)",
        "SHA-256 comparison against recovery-start bytes",
        "git diff --check; SHA-256 protected files; git status --short",
    ],
)
def test_descriptive_report_rows_never_receive_execution_credit(content, text):
    """An unresolved command-shaped report is a gap; a real command keeps its result."""
    problems, credited = DELIVERED["reports"]([{"command": text, "result": "PASS"}], root=content)
    if text.startswith("git "):
        assert DELIVERED["exit_code"](problems) in {1, 3}
    else:
        assert DELIVERED["exit_code"](problems) == 3 and credited == []
    assert True not in credited


def git(root, *argv):
    done = subprocess.run(
        ["git", *argv], cwd=root, capture_output=True, text=True, check=False, encoding="utf-8"
    )
    assert done.returncode == 0, done.stderr
    return done.stdout


@pytest.fixture
def scoped_repo(tmp_path):
    for name in (
        "tally/model.py",
        "tally/unrelated.py",
        "docs/consumer.md",
        "docs/draft.md",
        "preserved.txt",
        "tests/helpers.py",
        "tests/integration/run.py",
        "tests/conftest.py",
    ):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("seed\n", encoding="utf-8")
    git(tmp_path, "init", "-q")
    git(tmp_path, "add", ".")
    git(tmp_path, "-c", "user.name=Fixture", "-c", "user.email=fixture", "commit", "-qm", "Seed")
    git(tmp_path, "tag", "seed")
    return tmp_path


@pytest.mark.parametrize(
    "name,expected",
    [
        ("tally/model.py", False),
        ("tally/report_bundle.py", False),
        ("docs/consumer.md", False),
        ("tally/unrelated.py", True),
        ("docs/draft.md", True),
        ("preserved.txt", True),
        ("other/new.py", True),
    ],
)
def test_scope_preserves_exclusions_without_prescribing_a_solution_filename(
    scoped_repo, name, expected
):
    path = scoped_repo / name
    path.parent.mkdir(exist_ok=True)
    path.write_text("candidate\n", encoding="utf-8")
    problems = SCOPE["check"](
        scoped_repo,
        lambda name: name.startswith(("tally/", "docs/")),
        preserved={"tally/unrelated.py", "preserved.txt"},
    )
    assert bool(problems) is expected


@pytest.mark.parametrize("protection", ["preserved", "protected"])
def test_transient_preserved_edit_is_out_of_scope_after_restoring_the_seed(scoped_repo, protection):
    path = scoped_repo / "preserved.txt"
    path.write_text("temporary\n", encoding="utf-8")
    git(scoped_repo, "add", "preserved.txt")
    git(
        scoped_repo,
        "-c",
        "user.name=Fixture",
        "-c",
        "user.email=fixture",
        "commit",
        "-qm",
        "Touch preserved file",
    )
    path.write_text("seed\n", encoding="utf-8")
    options = (
        {"protected": {"preserved.txt": hashlib.sha256(b"seed\n").hexdigest()}}
        if protection == "protected"
        else {"preserved": {"preserved.txt"}}
    )
    assert SCOPE["check"](scoped_repo, lambda name: name.startswith(("tally/", "docs/")), **options)


@pytest.mark.parametrize(
    "state,expected",
    [("kept", []), ("changed", ["docs/draft.md"]), ("committed", ["docs/draft.md"])],
)
def test_protected_draft_keeps_its_initial_bytes_and_unstaged_state(scoped_repo, state, expected):
    path = scoped_repo / "docs/draft.md"
    path.write_text("local draft\n", encoding="utf-8")
    protected = {"docs/draft.md": hashlib.sha256(b"local draft\n").hexdigest()}
    if state == "changed":
        path.write_text("different draft\n", encoding="utf-8")
    if state == "committed":
        git(scoped_repo, "add", "docs/draft.md")
        git(
            scoped_repo,
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture",
            "commit",
            "-qm",
            "Commit a preserved draft",
        )
    problems = SCOPE["check"](
        scoped_repo, lambda name: name.startswith("docs/"), protected=protected
    )
    assert problems == (["out-of-scope files changed: " + ", ".join(expected)] if expected else [])


def test_same_content_failure_receipt_can_cover_seed_and_result(scoped_repo):
    row = receipt_for_path(scoped_repo, "tally/model.py")
    assert RECEIPTS["content"](row, scoped_repo, "seed")
    assert RECEIPTS["content"](row, scoped_repo)
    (scoped_repo / "tally/model.py").write_text("new content\n", encoding="utf-8")
    assert not RECEIPTS["content"](row, scoped_repo)
    result = receipt_for_path(scoped_repo, "tally/model.py")
    assert RECEIPTS["content"](result, scoped_repo)
    assert not RECEIPTS["content"](result, scoped_repo, "seed")


def receipt_for_path(root, name):
    inputs = {name: hashlib.sha256((root / name).read_bytes()).hexdigest()}
    return {
        "inputs": inputs,
        "digest": hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest(),
        "kind": "unit",
        "exit_code": 1,
        "modules": ["tests.known_baseline"],
    }


@pytest.mark.parametrize(
    "text, expected",
    [
        ("PASS", True),
        ("passed: 3 tests", True),
        ("Passed", True),
        ("not passed", False),
        ("never passed", False),
        ("not run", False),
        ("FAIL", False),
    ],
)
def test_drawn_check_status_accepts_the_persons_result_terms(text, expected):
    """A lowercase passed status must not discard a valid check receipt."""
    assert DELIVERED["passed"](text) is expected


@pytest.mark.parametrize(
    "name", ["tests/helpers.py", "tests/integration/run.py", "tests/conftest.py"]
)
def test_new_test_area_does_not_expand_permission_over_protected_seed_helpers(scoped_repo, name):
    """Opening new test filenames must not permit edits to previously protected seed files."""
    (scoped_repo / "tests/empty_report.csv").write_text(
        "day,project,person,minutes,note\n", encoding="utf-8"
    )
    assert SCOPE["check"](scoped_repo, lambda value: value.startswith("tests/")) == []
    (scoped_repo / name).write_text("changed\n", encoding="utf-8")
    assert name in SCOPE["check"](scoped_repo, lambda value: value.startswith("tests/"))[0]


@pytest.mark.skipif(shutil.which("make") is None, reason="no make on PATH")
@pytest.mark.parametrize("target", ["lint", "gates", "test", "test-integration"])
@pytest.mark.parametrize("code, expected", [(0, True), (2, False)])
def test_every_declared_make_check_runs_the_delivered_recipe(content, target, code, expected):
    (content / "Makefile").write_text(target + ":\n\texit " + str(code) + "\n", encoding="utf-8")
    assert DELIVERED["report"]("make " + target, root=content) is expected
