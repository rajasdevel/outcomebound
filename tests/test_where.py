"""`outcomebound where`: each source with a reading, one it cannot read and one that is empty, each
row of the next-skill table, the choice rules for briefs, reviews and tickets, that nothing is
written and no process but `git` and `gh` starts, and the shape of the JSON report. Every project is
a temporary Git repository with an `origin` of its own."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

from outcomebound_tools import adopt, home, review_check, schemacheck, validation, where
from outcomebound_tools.__main__ import VERBS
from tests import tickets_export as export
from tests.fake_tools import shell_tool

IDENTITY = ("-c", "user.name=T", "-c", "user.email=t@example.test", "-c", "commit.gpgsign=false")
SCHEMA = json.loads((home.ROOT / "schemas" / "where.schema.json").read_text(encoding="utf-8"))
OK = [sys.executable, "-c", "raise SystemExit(0)"]
BAD = [sys.executable, "-c", "raise SystemExit(3)"]
DECLARATION = {
    "version": 1,
    "store": "github",
    "repo": export.REPO,
    "label": export.LABEL,
    "human_label": "human-only",
    "request_label": "human-requested",
    "claims": ".outcomebound/ticket-claims.json",
}


@pytest.fixture(autouse=True)
def hermetic_git(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


def git(where_: Path, *args: str) -> str:
    done = subprocess.run(["git", *IDENTITY, *args], cwd=where_, check=True, capture_output=True)
    return done.stdout.decode("utf-8").strip()


def put(root: Path, name: str, text: str) -> Path:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


def commit(root: Path, message: str = "change") -> str:
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", message)
    return git(root, "rev-parse", "HEAD")


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """A work tree on branch `feature`, one commit past `main`, which `origin` holds."""

    bare = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(bare)], check=True)
    root = tmp_path / "work"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    put(root, ".gitignore", ".agents/\n.outcomebound-checks/\nissues.json\n")
    put(root, "src/a.py", "a = 1\n")
    commit(root, "start")
    git(root, "remote", "add", "origin", str(bare))
    git(root, "push", "-q", "origin", "main")
    git(root, "remote", "set-head", "origin", "main")
    git(root, "checkout", "-q", "-b", "feature")
    put(root, "src/b.py", "b = 1\n")
    commit(root, "feature work")
    return root


def read(root: Path, **options) -> list[dict]:
    options = {"export": None, "plans": [], "offline": True, **options}
    report = where.build(root, **options)
    assert schemacheck.validate(report, SCHEMA) == []
    return report["items"]


def lines(items: list[dict], kind: str) -> list[dict]:
    return [i for i in items if i["kind"] == kind]


def one(items: list[dict], kind: str, **match: str) -> dict:
    found = [i for i in lines(items, kind) if all(match[k] in i.get(k, "") for k in match)]
    assert len(found) == 1, f"{kind} {match}: {found}"
    return found[0]


def declare(root: Path, *, claims: list[dict] | None = None) -> None:
    put(root, ".outcomebound/tickets.json", json.dumps(DECLARATION))
    plan = {"version": 1, "claims": claims or []}
    put(root, ".outcomebound/ticket-claims.json", json.dumps(plan))


def issues(root: Path, *nodes) -> Path:
    path = root / "issues.json"
    path.write_text(json.dumps(export.export(*nodes)), encoding="utf-8")
    return path


def claim(name: str = "unit", **fields) -> dict:
    return {"name": name, "risk": "r", "kind": "test", "command": OK, "paths": ["src"], **fields}


def run_plan(root: Path, claims: list[dict], capsys) -> Path:
    path = put(root, "plan.json", json.dumps({"version": 1, "claims": claims}))
    capsys.readouterr()
    validation._main([str(path)])
    return path


# --- git and worktrees ---------------------------------------------------------------------


def test_the_branch_line_gives_upstream_counts_and_uncommitted_paths(project):
    git(project, "push", "-q", "-u", "origin", "feature")
    put(project, "src/c.py", "c = 1\n")  # untracked
    put(project, "src/a.py", "a = 2\n")  # tracked, edited
    put(project, "ignored.log", "x")
    put(project, ".gitignore", ".agents/\nignored.log\n")
    line = one(read(project), "git")
    assert line["verdict"] == "NOTE" and line["subject"] == "feature"
    assert "0 ahead and 0 behind origin/feature" in line["text"]
    assert "3 uncommitted path(s)" in line["text"]  # a.py, c.py and .gitignore; not ignored.log
    put(project, "src/d.py", "d = 1\n")
    commit(project)
    assert "1 ahead and 0 behind" in one(read(project), "git")["text"]


def test_a_branch_with_no_upstream_says_so(project):
    assert "no upstream" in one(read(project), "git")["text"]


def test_a_folder_outside_git_reads_unverified_and_the_report_still_prints(tmp_path, capsys):
    folder = tmp_path / "plain"
    put(folder, "notes.txt", "x")
    assert where.main([str(folder)]) == 0
    out = capsys.readouterr().out
    assert out.startswith("where: ") and "UNVERIFIED  git:" in out
    assert "Does not establish:" in out


def test_other_worktrees_are_listed_when_they_hold_work_else_counted(project, tmp_path):
    git(project, "push", "-q", "origin", "feature")  # the commits of `feature` are pushed
    clean = tmp_path / "clean"
    dirty = tmp_path / "dirty"
    git(project, "worktree", "add", "-q", "-b", "clean-branch", str(clean))
    git(project, "worktree", "add", "-q", "-b", "dirty-branch", str(dirty))
    put(dirty, "scratch.txt", "x")
    items = read(project)
    held = one(items, "worktree", subject="dirty-branch")
    assert "1 uncommitted path(s)" in held["text"] and held["verdict"] == "NOTE"
    assert "commits pushed" in held["text"] and "clean-branch" not in held["text"]
    summary = one(items, "worktree", text="1 other worktree(s) with nothing uncommitted")
    assert "clean-branch" in summary["text"]


def test_a_worktree_with_commits_held_nowhere_else_is_listed_though_clean(project, tmp_path):
    git(project, "push", "-q", "origin", "feature")
    tree = tmp_path / "ahead"
    git(project, "worktree", "add", "-q", "-b", "ahead-branch", str(tree))
    put(tree, "src/new.py", "n = 1\n")
    commit(tree, "only here")
    line = one(read(project), "worktree", subject="ahead-branch")
    assert "commits local" in line["text"] and "0 uncommitted path(s)" in line["text"]


def test_a_worktree_with_no_or_an_older_install_is_counted_as_adopt_check_names_it(
    project, tmp_path
):
    other = tmp_path / "other"
    git(project, "worktree", "add", "-q", "-b", "other", str(other))
    older = one(read(project), "worktree", source="adopt_worktrees")
    assert "1 worktree(s) have no readable install, one older" in older["text"]


def install(root: Path, capsys) -> None:
    assert adopt.main([str(root), "--harness", "claude-code"]) == 0
    capsys.readouterr()
    commit(root, "install")


def test_this_checkouts_block_missing_on_disk_is_named_with_the_manifest_kept(project, capsys):
    install(project, capsys)
    assert [i for i in read(project) if i["source"] == "adopt_worktrees"] == []
    agents = project / "AGENTS.md"
    agents.write_text(adopt.cut(agents.read_text(encoding="utf-8"), adopt.KERNEL), encoding="utf-8")

    line = one(read(project), "git", source="adopt_worktrees")

    assert line["verdict"] == "NOTE" and line["text"].startswith("this checkout: installed ")
    assert "missing on disk, its commit holds them: AGENTS.md (operating-contract)" in line["text"]


def test_a_checkout_without_an_install_is_named_only_beside_one_that_has_it(
    project, tmp_path, capsys
):
    early = tmp_path / "early"
    git(project, "worktree", "add", "-q", "-b", "early", str(early))
    assert [i for i in lines(read(early), "git") if i["source"] == "adopt_worktrees"] == []
    install(project, capsys)

    line = one(read(early), "git", source="adopt_worktrees")

    assert line["text"].startswith("this checkout: no OutcomeBound install; its commit holds no ")
    assert f"while worktree {project} has an install" in line["text"]


def test_a_worktree_whose_folder_is_gone_is_unverified(project, tmp_path):
    gone = tmp_path / "gone"
    git(project, "worktree", "add", "-q", "-b", "gone", str(gone))
    shutil.rmtree(gone)
    assert one(read(project), "worktree", text="the folder is gone")["verdict"] == "UNVERIFIED"


# --- pull requests -------------------------------------------------------------------------


def gh_on_path(monkeypatch, tmp_path: Path, script: str) -> Path:
    shell_tool(tmp_path / "bin", "gh", script)
    monkeypatch.setenv("PATH", f"{tmp_path / 'bin'}{os.pathsep}{os.environ['PATH']}")
    return tmp_path / "bin"


def test_an_open_pull_request_is_open_and_names_land_change(project, tmp_path, monkeypatch):
    listed = json.dumps(
        [
            {
                "number": 7,
                "title": "Add b",
                "headRefName": "feature",
                "isDraft": True,
                "reviewDecision": "",
            }
        ]
    )
    gh_on_path(monkeypatch, tmp_path, f"#!/bin/sh\ncat <<'EOF'\n{listed}\nEOF\n")
    line = one(read(project, offline=False), "pr")
    assert (line["verdict"], line["subject"], line["next"]) == ("OPEN", "#7", "land-change")
    assert "draft" in line["text"] and "branch feature" in line["text"]


def test_no_open_pull_request_is_clear(project, tmp_path, monkeypatch):
    gh_on_path(monkeypatch, tmp_path, "#!/bin/sh\necho '[]'\n")
    line = one(read(project, offline=False), "pr")
    assert line["verdict"] == "CLEAR" and "next" not in line


def test_a_gh_that_fails_reads_unverified_with_its_first_line(project, tmp_path, monkeypatch):
    gh_on_path(monkeypatch, tmp_path, "#!/bin/sh\necho 'not signed in' >&2\nexit 4\n")
    line = one(read(project, offline=False), "pr")
    assert line["verdict"] == "UNVERIFIED" and "not signed in" in line["text"]


def test_no_gh_on_path_reads_unverified(project, tmp_path, monkeypatch):
    real = shutil.which("git")
    assert real is not None
    shell_tool(tmp_path / "only-git", "git", f'#!/bin/sh\nexec "{Path(real).as_posix()}" "$@"\n')
    monkeypatch.setenv("PATH", str(tmp_path / "only-git"))
    assert "gh is not on PATH" in one(read(project, offline=False), "pr")["text"]


def test_offline_never_starts_gh(project, tmp_path, monkeypatch):
    marker = tmp_path / "gh-ran"
    gh_on_path(monkeypatch, tmp_path, f"#!/bin/sh\ntouch '{marker.as_posix()}'\necho '[]'\n")
    assert "--offline" in one(read(project, offline=True), "pr")["text"]
    assert not marker.exists()


# --- tickets -------------------------------------------------------------------------------


def test_a_ticket_in_a_project_that_declares_no_store_is_a_note(project):
    line = one(read(project), "ticket")
    assert line["verdict"] == "NOTE" and "no ticket store" in line["text"]


def test_a_declared_store_with_no_export_is_unverified_and_names_the_command(project):
    declare(project)
    line = one(read(project), "ticket")
    assert line["verdict"] == "UNVERIFIED" and "outcomebound tickets export" in line["text"]


def test_a_misshapen_export_is_unverified_with_its_refusal(project):
    declare(project)
    (project / "issues.json").write_text("{}", encoding="utf-8")
    line = one(read(project), "ticket")
    assert line["verdict"] == "UNVERIFIED" and "not the array of pages" in line["text"]


def test_tickets_are_ready_held_blocked_or_waiting_each_with_its_reason(project):
    declare(project)
    waits = export.body(extra=["waits-on: Q7"])
    issues(
        project,
        export.issue(1, title="ready one"),
        export.issue(2, title="held one", text=export.body(hold="yes")),
        export.issue(3, title="blocked one", blocked_by=[1]),
        export.issue(4, title="waiting one", text=waits),
        export.issue(5, title="finished", state="closed"),
        export.issue(6, title="after finished", blocked_by=[5]),
    )
    items = read(project)
    by = {i["subject"]: i for i in lines(items, "ticket") if "subject" in i}
    assert (by["#1"]["verdict"], by["#1"]["next"]) == ("OPEN", "hand-off-tickets")
    assert by["#2"]["verdict"] == "NOTE" and "held for a person" in by["#2"]["text"]
    assert by["#3"]["verdict"] == "NOTE" and "blocked by #1" in by["#3"]["text"]
    assert by["#4"]["verdict"] == "NOTE" and "waits on brief(s) Q7" in by["#4"]["text"]
    assert by["#6"]["verdict"] == "OPEN"  # its blocker is closed
    assert "#5" not in by
    claimed = [i for i in lines(items, "ticket") if "claimed" in i["text"]]
    assert claimed[0]["verdict"] == "UNVERIFIED"
    assert "export written" in one(items, "ticket", text="open ticket(s)")["text"]


def test_a_ticket_waiting_on_an_unanswered_brief_points_at_the_brief_not_twice(project):
    declare(project)
    issues(project, export.issue(4, text=export.body(extra=["waits-on: Q7"])))
    put(project, ".agents/work/t/briefs.md", "### Q7 · Which store?\n\nbody\n")
    items = read(project)
    brief = one(items, "brief", subject="Q7")
    assert (brief["verdict"], brief["next"]) == ("OPEN", "decision-brief")
    assert "next" not in one(items, "ticket", subject="#4")


def test_an_answered_wait_leaves_the_ticket_ready_and_says_it_is_still_named(project):
    declare(project)
    issues(project, export.issue(4, text=export.body(extra=["waits-on: Q7"])))
    put(
        project,
        ".agents/work/t/briefs.md",
        '### Q7 · Which store?\n\nDecided: Q7 · chat · maintainer · 2026-10-01 · "github"\n',
    )
    items = read(project)
    ticket = one(items, "ticket", subject="#4")
    assert ticket["verdict"] == "OPEN" and "answered but still named" in ticket["text"]
    assert one(items, "brief", subject="q7")["verdict"] == "CLEAR"


def test_a_wait_on_an_id_two_briefs_carry_is_unverified(project):
    declare(project)
    issues(project, export.issue(4, text=export.body(extra=["waits-on: Q7"])))
    put(project, ".agents/work/a/briefs.md", "### Q7 · One\n")
    put(project, ".agents/work/b/briefs.md", "### Q7 · Two\n")
    line = one(read(project), "brief", subject="q7")
    assert line["verdict"] == "UNVERIFIED" and "two different briefs carry this id" in line["text"]


def test_a_wait_on_an_id_no_brief_defines_is_unverified(project):
    declare(project)
    issues(project, export.issue(4, text=export.body(extra=["waits-on: Q9"])))
    assert "no brief file defines it" in one(read(project), "brief", subject="q9")["text"]


def test_an_export_given_by_name_is_read_in_place_of_the_default(project, tmp_path):
    declare(project)
    elsewhere = tmp_path / "export.json"
    elsewhere.write_text(
        json.dumps(export.export(export.issue(9, title="far one"))), encoding="utf-8"
    )
    line = one(read(project, export=elsewhere), "ticket", subject="#9")
    assert line["verdict"] == "OPEN"


# --- validation ----------------------------------------------------------------------------


def test_a_failed_claim_is_open_and_names_diagnose(project, capsys):
    plan = run_plan(project, [claim(command=BAD)], capsys)
    items = read(project, plans=[plan])
    line = one(items, "validation", subject="unit")
    assert (line["verdict"], line["next"]) == ("OPEN", "diagnose")
    assert "last result FAIL" in line["text"]


def test_a_claim_whose_declared_path_changed_is_stale_and_names_tests_worth_keeping(
    project, capsys
):
    plan = run_plan(project, [claim()], capsys)
    assert one(read(project, plans=[plan]), "validation", text="1 claim(s)")["verdict"] == "CLEAR"
    put(project, "src/a.py", "a = 2\n")
    items = read(project, plans=[plan])
    line = one(items, "validation", subject="unit")
    assert (line["verdict"], line["next"]) == ("STALE", "tests-worth-keeping")
    assert one(items, "validation", text="1 claim(s)")["verdict"] == "NOTE"


def test_claims_with_no_result_are_counted_not_listed(project):
    plan = put(project, "plan.json", json.dumps({"version": 1, "claims": [claim("a"), claim("b")]}))
    items = read(project, plans=[plan])
    assert len(lines(items, "validation")) == 1
    assert "2 UNVERIFIED (2 with no result kept)" in lines(items, "validation")[0]["text"]


def test_the_ticket_declaration_names_the_plan_where_none_is_given(project, capsys):
    declare(project, claims=[claim("declared")])
    summary = one(read(project), "validation", source=".outcomebound/ticket-claims.json")
    assert "1 claim(s)" in summary["text"]


def test_no_plan_reads_unverified_and_a_broken_plan_too(project):
    assert "no validation plan" in one(read(project), "validation")["text"]
    broken = put(project, "plan.json", "{not json")
    line = one(read(project, plans=[broken]), "validation")
    assert line["verdict"] == "UNVERIFIED" and "could not be read" in line["text"]


def test_the_claim_reader_agrees_with_validation_status(project, capsys):
    plan = run_plan(project, [claim("a"), claim("b", command=BAD)], capsys)
    capsys.readouterr()
    validation._main(["status", str(plan)])
    status = capsys.readouterr().out.splitlines()[1:]
    states = validation.claim_states(validation.load_plan(plan))
    assert [f"{s.state} {s.claim.name}" for s in states] == [ln.split(" — ")[0] for ln in status]
    assert [s.verdict for s in states] == ["PASS", "FAIL"]


# --- reviews -------------------------------------------------------------------------------


def review(root: Path, name: str, ref: str, *findings: str) -> str:
    body = f"Reviewed: {ref}\n\n" + "".join(findings)
    return str(put(root, f".agents/work/r/{name}.md", body))


OPEN_FINDING = "### F1 · A hole\n\nsrc/b.py:1 is wrong.\n"
CLOSED_FINDING = (
    "### F1 · A hole\n\nsrc/b.py:1 is wrong.\nDisposition: fixed — in the next commit\n"
)


def test_a_review_with_a_finding_without_a_disposition_is_open(project):
    review(project, "r1", "main", OPEN_FINDING)
    line = one(read(project), "review", source=".agents/work/r/r1.md")
    assert (line["verdict"], line["next"]) == ("OPEN", "review-findings")
    assert "DISPOSITION_MISSING" in line["text"]


def test_a_review_of_this_branch_is_clear_until_a_file_changes_then_a_note(project):
    head = git(project, "rev-parse", "HEAD")
    review(project, "r2", head, CLOSED_FINDING)
    line = one(read(project), "review", source=".agents/work/r/r2.md")
    assert line["verdict"] == "CLEAR" and "next" not in line
    put(project, "src/b.py", "b = 2\n")
    line = one(read(project), "review", source=".agents/work/r/r2.md")
    assert line["verdict"] == "NOTE" and "next" not in line
    assert "1 file(s) differ now: src/b.py" in line["text"]


def test_a_review_of_commits_the_base_holds_is_counted_not_listed(project):
    base = git(project, "rev-parse", "main")
    review(project, "old", base, CLOSED_FINDING)
    items = read(project)
    assert not [i for i in lines(items, "review") if "old.md" in i["source"]]
    assert "1 other review file(s) with every finding dispositioned" in one(items, "review")["text"]


def test_without_a_base_only_open_findings_are_listed_and_the_line_says_why(project):
    git(project, "update-ref", "-d", "refs/remotes/origin/HEAD")
    review(project, "r3", "main", CLOSED_FINDING)
    review(project, "r4", "main", OPEN_FINDING)
    items = read(project)
    assert one(items, "review", text="no base tells which reviews")["verdict"] == "UNVERIFIED"
    assert one(items, "review", source="r4.md")["verdict"] == "OPEN"


def test_the_sweep_keeps_the_ref_each_review_read(project):
    path = review(project, "r5", "abc1234", CLOSED_FINDING)
    swept = review_check.sweep(project / ".agents" / "work")
    assert swept.reviewed == {path: "abc1234"}


# --- briefs and the handoff ----------------------------------------------------------------


def test_a_brief_the_newest_handoff_defines_is_open_until_a_decided_line_answers_it(project):
    put(project, ".agents/handoffs/2026-10-18-x.md", "# Handoff\n\n### Q1 · Which way?\n\nbody\n")
    line = one(read(project), "brief", subject="Q1")
    assert (line["verdict"], line["next"]) == ("OPEN", "decision-brief")
    assert "newest handoff" in line["text"]
    put(
        project,
        ".agents/work/x/answer.md",
        'Decided: Q1 · chat · maintainer · 2026-10-18 · "left"\n',
    )
    assert not [i for i in lines(read(project), "brief") if i.get("subject") == "Q1"]


def test_briefs_nothing_in_flight_names_are_counted_and_the_note_warns_of_old_answers(project):
    put(project, ".agents/work/old/briefs.md", "### D1 · Old\n\n### D2 · Older\n")
    note = one(read(project), "brief", text="other brief heading(s)")
    assert note["verdict"] == "NOTE" and "2 other brief heading(s)" in note["text"]
    assert "recorded before that form" in note["text"]
    assert not [i for i in lines(read(project), "brief") if i["verdict"] == "OPEN"]


def test_the_newest_handoff_gives_its_age_and_the_commits_since(project):
    first = put(project, ".agents/handoffs/a.md", "old")
    second = put(project, ".agents/handoffs/b.md", "new")
    os.utime(first, (time.time() - 90000, time.time() - 90000))
    os.utime(second, (time.time() - 7200, time.time() - 7200))
    line = one(read(project), "handoff")
    assert line["source"] == ".agents/handoffs/b.md" and "written 2h ago" in line["text"]
    assert f"{git(project, 'rev-list', '--count', 'HEAD')} commit(s) on HEAD since" in line["text"]
    assert "claim" in line["text"]


def test_no_handoff_is_a_note(project):
    assert one(read(project), "handoff")["verdict"] == "NOTE"


def test_a_worktree_reads_the_main_checkouts_handoffs_and_reviews(project, tmp_path):
    put(project, ".agents/handoffs/a.md", "# h\n")
    review(project, "r6", "main", OPEN_FINDING)
    tree = tmp_path / "tree"
    git(project, "worktree", "add", "-q", "-b", "tree", str(tree))
    items = read(tree)
    assert one(items, "handoff")["source"] == "main checkout: .agents/handoffs/a.md"
    assert one(items, "review", source="main checkout: .agents/work/r/r6.md")["verdict"] == "OPEN"


# --- the whole report ----------------------------------------------------------------------


def snapshot(root: Path) -> dict[str, bytes]:
    return {
        str(p.relative_to(root)): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file() and ".git/objects" not in p.as_posix()
    }


def test_a_run_writes_nothing_not_even_the_index(project, capsys):
    declare(project, claims=[claim()])
    issues(project, export.issue(1))
    put(project, ".agents/handoffs/a.md", "# h\n")
    review(project, "r7", "main", OPEN_FINDING)
    put(project, "src/untracked.py", "x = 1\n")
    git(project, "update-index", "--really-refresh")
    before = snapshot(project)
    assert where.main([str(project), "--offline"]) == 0
    assert snapshot(project) == before


def test_a_run_starts_no_process_but_git_and_gh(project, tmp_path, monkeypatch, capsys):
    gh_on_path(monkeypatch, tmp_path, "#!/bin/sh\necho '[]'\n")
    declare(project, claims=[claim()])
    started: list[str] = []
    real = subprocess.run

    def spy(argv, *a, **k):
        started.append(Path(str(argv[0])).stem.lower())
        return real(argv, *a, **k)

    monkeypatch.setattr(subprocess, "run", spy)
    assert where.main([str(project)]) == 0
    assert started and set(started) <= {"git", "gh"}
    assert "gh" in started


def test_the_report_lists_kinds_in_the_fixed_order_with_counts_that_add_up(project):
    declare(project)
    issues(project, export.issue(1))
    put(project, ".agents/handoffs/a.md", "# h\n")
    report = where.build(project, export=None, plans=[], offline=True)
    kinds = [i["kind"] for i in report["items"]]
    assert kinds == sorted(kinds, key=where.KINDS.index)
    assert sum(report["counts"].values()) == len(report["items"])
    assert schemacheck.validate(report, SCHEMA) == []


def test_json_and_text_carry_the_same_lines(project, capsys):
    declare(project)
    issues(project, export.issue(1, title="ready one"))
    assert where.main([str(project), "--offline", "--json"]) == 0
    document = json.loads(capsys.readouterr().out)
    assert schemacheck.validate(document, SCHEMA) == []
    assert where.main([str(project), "--offline"]) == 0
    text = capsys.readouterr().out.splitlines()
    assert len(text) == len(document["items"]) + 2  # the head line and the limits line
    assert "next: hand-off-tickets" in "\n".join(text)
    assert text[0].startswith(f"where: {len(document['items'])} line(s)")
    for item, line in zip(document["items"], text[1:-1], strict=True):
        assert line.startswith(f"{item['verdict']:<11} {item['kind']}")
        assert f"[{item['source']}]" in line and item["text"] in line
        assert line.endswith(f"; next: {item.get('next')}") == ("next" in item)


def test_exits_are_zero_for_any_verdict_and_two_for_a_usage_error(project):
    assert where.main([str(project), "--offline"]) == 0
    with pytest.raises(SystemExit) as stop:
        where.main(["--nonsense"])
    assert stop.value.code == 2


def test_text_from_a_file_is_escaped_so_it_cannot_steer_the_terminal(project):
    declare(project)
    issues(project, export.issue(1, title="evil \x1b[31m title"))
    text = where.render_text(where.build(project, export=None, plans=[], offline=True))
    assert "\x1b" not in text


def test_every_skill_the_table_names_ships_and_the_schema_lists_exactly_those():
    for skill in where.NEXT_SKILL.values():
        assert (home.ROOT / "skills" / skill / "SKILL.md").is_file(), skill
    listed = SCHEMA["properties"]["items"]["items"]["properties"]["next"]["enum"]
    assert sorted(listed) == sorted(set(where.NEXT_SKILL.values()))
    assert set(SCHEMA["properties"]["counts"]["required"]) == set(where.VERDICTS)


def test_the_verb_is_routed_and_has_help(capsys):
    assert VERBS["where"] == "where"
    with pytest.raises(SystemExit) as stop:
        where.main(["--help"])
    assert stop.value.code == 0
    assert "never by a hook" in capsys.readouterr().out


# --- the review's findings -----------------------------------------------------------------


def test_a_claim_that_never_ran_to_an_exit_is_not_clear(project, capsys):
    plan = run_plan(project, [claim(command=["no-such-program-here"])], capsys)
    items = read(project, plans=[plan])
    line = one(items, "validation", subject="unit")
    assert line["verdict"] == "UNVERIFIED" and "next" not in line
    assert one(items, "validation", text="1 claim(s)")["verdict"] == "NOTE"


def test_a_failed_claim_whose_path_also_changed_is_one_open_line_for_diagnose(project, capsys):
    plan = run_plan(project, [claim(command=BAD)], capsys)
    put(project, "src/a.py", "a = 2\n")
    lines_ = [i for i in read(project, plans=[plan]) if i.get("subject") == "unit"]
    assert [(i["verdict"], i["next"]) for i in lines_] == [("OPEN", "diagnose")]


def test_the_pull_request_of_this_branch_comes_first_and_is_marked(project, tmp_path, monkeypatch):
    listed = [
        {"number": n, "title": "t", "headRefName": b, "isDraft": False, "reviewDecision": ""}
        for n, b in ((3, "other"), (9, "feature"))
    ]
    gh_on_path(monkeypatch, tmp_path, f"#!/bin/sh\ncat <<'EOF'\n{json.dumps(listed)}\nEOF\n")
    found = lines(read(project, offline=False), "pr")
    assert [i["subject"] for i in found] == ["#9", "#3"]
    assert "this branch's" in found[0]["text"] and "this branch's" not in found[1]["text"]


def test_gh_is_told_not_to_prompt_or_check_for_updates(project, tmp_path, monkeypatch):
    seen = tmp_path / "env.txt"
    echo = f"echo \"$GH_PROMPT_DISABLED $GH_NO_UPDATE_NOTIFIER\" > '{seen.as_posix()}'"
    script = f"#!/bin/sh\n{echo}\necho '[]'\n"
    gh_on_path(monkeypatch, tmp_path, script)
    read(project, offline=False)
    assert seen.read_text(encoding="utf-8").split() == ["1", "1"]


def test_a_review_of_a_moving_ref_is_counted_not_tied_to_the_branch(project):
    review(project, "moving", "HEAD", CLOSED_FINDING)
    review(project, "words", "plan.md 2026-10-09", CLOSED_FINDING)
    review(project, "relative", "HEAD~0", CLOSED_FINDING)
    items = read(project)
    named = ("moving.md", "words.md", "relative.md")
    assert not [i for i in lines(items, "review") if i["source"].endswith(named)]
    assert "3 other review file(s)" in one(items, "review")["text"]


def test_base_names_the_commit_that_tells_which_reviews_concern_the_branch(project):
    first = git(project, "rev-parse", "HEAD")
    put(project, "src/c.py", "c = 1\n")
    commit(project)
    review(project, "mid", first, CLOSED_FINDING)
    assert [i["verdict"] for i in read(project) if "mid.md" in i["source"]] == ["NOTE"]
    items = read(project, base=first)  # the review read the base itself: not branch work
    assert not [i for i in lines(items, "review") if "mid.md" in i["source"]]
    base = where.build(project, export=None, plans=[], offline=True, base=first)["read"]["base"]
    assert base["commit"] == first and base["how"] == "--base"


def test_the_json_report_says_what_it_read(project):
    declare(project)
    path = issues(project, export.issue(1))
    report = where.build(project, export=path, plans=[], offline=True)
    assert schemacheck.validate(report, SCHEMA) == []
    read_ = report["read"]
    assert read_["base"]["ref"] == "origin/HEAD" and read_["export"]["source"] == "issues.json"
    assert isinstance(read_["export"]["age_seconds"], int)
    assert read_["searched"] == [str(p) for p in where.brief_lookup.default_roots(project)]
    nothing = where.build(project / "..", export=None, plans=[], offline=True)
    assert nothing["read"]["base"] is None and nothing["read"]["export"] is None


def test_a_worktree_reads_the_export_of_the_main_checkout(project, tmp_path):
    declare(project)
    issues(project, export.issue(1, title="from main"))
    tree = tmp_path / "tree"
    git(project, "worktree", "add", "-q", "-b", "tree", str(tree))
    put(tree, ".outcomebound/tickets.json", json.dumps(DECLARATION))
    assert "from main" in one(read(tree), "ticket", subject="#1")["text"]


def test_cwd_is_the_directory_the_plan_was_run_with(project, capsys):
    plan = put(project, "sub/plan.json", json.dumps({"version": 1, "claims": [claim()]}))
    capsys.readouterr()
    validation._main([str(plan), "--cwd", ".."])
    items = read(project, plans=[plan], cwd="..")
    assert one(items, "validation", text="1 claim(s)")["verdict"] == "CLEAR"
    assert "UNVERIFIED" in one(read(project, plans=[plan]), "validation", text="1 claim(s)")["text"]


def test_a_requested_hold_holds_like_a_human_only_one(project):
    declare(project)
    issues(project, export.issue(1, text=export.body(hold="requested")))
    line = one(read(project), "ticket", subject="#1")
    assert line["verdict"] == "NOTE" and "held for a person (requested)" in line["text"]


def test_a_review_stays_tied_when_the_branch_is_pushed(project):
    review(project, "pushed", git(project, "rev-parse", "HEAD"), CLOSED_FINDING)
    git(project, "push", "-q", "-u", "origin", "feature")  # the upstream is now the branch itself
    line = one(read(project), "review", source=".agents/work/r/pushed.md")
    assert line["verdict"] == "CLEAR"
    base = where.build(project, export=None, plans=[], offline=True)["read"]["base"]
    assert base["ref"] == "origin/HEAD"


def test_a_result_with_no_verdict_is_not_clear(project, capsys):
    plan = run_plan(project, [claim()], capsys)
    path = sorted((project / ".outcomebound-checks").glob("unit.*.result.json"))[-1]
    record = json.loads(path.read_text(encoding="utf-8"))
    del record["verdict"]
    path.write_text(json.dumps(record), encoding="utf-8")
    summary = one(read(project, plans=[plan]), "validation", text="1 claim(s)")
    assert summary["verdict"] != "CLEAR"


def test_a_failed_claim_line_carries_its_command(project, capsys):
    plan = run_plan(project, [claim(command=BAD)], capsys)
    line = one(read(project, plans=[plan]), "validation", subject="unit")
    assert "its command: " in line["text"] and "SystemExit(3)" in line["text"]


def test_a_ticket_whose_relations_the_export_cut_short_is_not_ready(project):
    declare(project)
    node = json.loads(json.dumps(export.issue(1, title="cut short")))
    node["blockedBy"]["pageInfo"]["hasNextPage"] = True
    issues(project, node, export.issue(2, title="whole one"))
    items = read(project)
    assert one(items, "ticket", subject="#1")["verdict"] == "UNVERIFIED"
    assert one(items, "ticket", subject="#2")["verdict"] == "OPEN"


def test_an_export_that_is_not_the_whole_list_says_so(project):
    declare(project)
    path = issues(project, export.issue(1))
    pages = json.loads(path.read_text(encoding="utf-8"))
    pages[0]["data"]["repository"]["issues"]["pageInfo"]["hasNextPage"] = True
    path.write_text(json.dumps(pages), encoding="utf-8")
    head = one(read(project), "ticket", text="open ticket(s)")
    assert head["verdict"] == "UNVERIFIED" and "not the whole issue list" in head["text"]


def test_without_git_the_report_still_prints(project, tmp_path, monkeypatch, capsys):
    declare(project)
    issues(project, export.issue(1))
    empty = tmp_path / "empty-path"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))
    assert where.main([str(project), "--offline"]) == 0
    out = capsys.readouterr().out
    assert "UNVERIFIED  git:" in out and "OPEN        ticket #1" in out


def test_git_is_told_not_to_fetch_lazily(project, monkeypatch):
    seen: list[str | None] = []
    real = subprocess.run

    def spy(argv, *a, **k):
        if Path(str(argv[0])).stem == "git":
            seen.append(k["env"].get("GIT_NO_LAZY_FETCH"))
        return real(argv, *a, **k)

    monkeypatch.setattr(subprocess, "run", spy)
    read(project)
    assert seen and set(seen) == {"1"}


def test_the_install_survey_of_each_worktree_is_told_not_to_fetch_lazily(
    project, tmp_path, monkeypatch, capsys
):
    install(project, capsys)
    git(project, "worktree", "add", "-q", "-b", "other", str(tmp_path / "other"))
    seen: list[tuple[str, str | None, str | None]] = []
    real = subprocess.run

    def spy(argv, *a, **k):
        if Path(str(argv[0])).stem == "git":
            env = k["env"]
            seen.append(
                (
                    " ".join(map(str, argv[1:])),
                    env.get("GIT_NO_LAZY_FETCH"),
                    env.get("GIT_OPTIONAL_LOCKS"),
                )
            )
        return real(argv, *a, **k)

    monkeypatch.setattr(subprocess, "run", spy)
    read(project)
    assert any("cat-file --batch" in argv for argv, _, _ in seen)
    assert {(fetch, locks) for _, fetch, locks in seen} == {("1", "0")}


def test_the_schemas_promises_hold_for_every_line(project, capsys):
    declare(project)
    issues(project, export.issue(1), export.issue(2, text=export.body(hold="yes")))
    plan = run_plan(project, [claim(command=BAD)], capsys)
    review(project, "open", "main", OPEN_FINDING)
    for item in read(project, plans=[plan]):
        assert item["source"] and item["text"]
        assert ("next" in item) <= (item["verdict"] in ("OPEN", "STALE"))
        if item["verdict"] == "OPEN":
            assert "next" in item
