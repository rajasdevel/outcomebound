"""The `warn` lines of `adopt --check` for a Git worktree whose installed OutcomeBound is older
than the engine, and what it says where an install is missing on disk or not committed, in the
target and in each other worktree. Every project is a temporary Git repository with a synthetic
install; the check reads the other worktrees and writes nothing in them, and no line moves the
exit code."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from outcomebound_tools import adopt
from tests.adopt_helpers import GIT, ROOT, Capture, repo, run, snapshot
from tests.portable import write

VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
OLDER = "0.9.0"
NO_INSTALL = "no OutcomeBound install"


def git(root: Path, *arguments: str) -> None:
    identity = ["-c", "user.name=a", "-c", "user.email=a@example.org", "-c", "commit.gpgsign=false"]
    subprocess.run([GIT, "-C", str(root), *identity, *arguments], check=True, capture_output=True)


def project(tmp_path: Path, capsys: Capture) -> Path:
    """A committed project with the current install."""

    main = repo(tmp_path / "main", {"README.md": "# Synthetic\n"})
    code, _, err = run(capsys, str(main), "--harness", "claude-code", "--fragments", "commands")
    assert code == 0, err
    git(main, "add", "-A")
    git(main, "commit", "-q", "-m", "install")
    return main


def linked(main: Path, name: str, branch: str | None = "feature") -> Path:
    tree = main.parent / name
    arguments = ["-b", branch, str(tree)] if branch else ["--detach", str(tree)]
    git(main, "worktree", "add", "-q", *arguments)
    return tree


def edit(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert old in text
    write(path, text.replace(old, new))


def warns(out: str) -> list[str]:
    return [line for line in out.splitlines() if line.startswith("warn ")]


def test_an_older_worktree_is_named_with_its_branch_and_both_versions(
    tmp_path: Path, capsys: Capture
) -> None:
    main = project(tmp_path, capsys)
    tree = linked(main, "old")
    edit(tree / adopt.MANIFEST, f'"engine_version": "{VERSION}"', f'"engine_version": "{OLDER}"')
    before = snapshot(tree)

    code, out, _ = run(capsys, str(main), "--check")

    assert code == 0
    (line,) = warns(out)
    assert str(tree) in line and "(branch feature)" in line
    assert f"installed {OLDER}, engine {VERSION}" in line
    assert snapshot(tree) == before


def test_a_current_or_newer_worktree_is_not_named(tmp_path: Path, capsys: Capture) -> None:
    main = project(tmp_path, capsys)
    linked(main, "same", "same")
    newer = linked(main, "newer", "newer")
    edit(newer / adopt.MANIFEST, f'"engine_version": "{VERSION}"', '"engine_version": "99.0.0"')
    git(newer, "commit", "-q", "-am", "newer")

    _, out, _ = run(capsys, str(main), "--check")

    assert warns(out) == []


def test_a_worktree_with_no_install_is_named_as_such(tmp_path: Path, capsys: Capture) -> None:
    main = project(tmp_path, capsys)
    tree = linked(main, "bare-branch", branch=None)
    for relative in (adopt.MANIFEST, "AGENTS.md"):
        (tree / relative).unlink()

    _, out, _ = run(capsys, str(main), "--check")

    (line,) = warns(out)
    assert str(tree) in line and "(branch (detached))" in line and NO_INSTALL in line


def test_the_block_marker_stands_in_where_the_manifest_is_gone(
    tmp_path: Path, capsys: Capture
) -> None:
    main = project(tmp_path, capsys)
    tree = linked(main, "old", "old")
    (tree / adopt.MANIFEST).unlink()
    marker = "id=operating-contract v="
    edit(tree / "AGENTS.md", marker + VERSION, marker + OLDER)

    _, out, _ = run(capsys, str(main), "--check")

    (line,) = warns(out)
    assert f"installed {OLDER}, engine {VERSION}" in line


def test_a_version_that_is_not_readable_is_named_without_failing(
    tmp_path: Path, capsys: Capture
) -> None:
    main = project(tmp_path, capsys)
    tree = linked(main, "odd", "odd")
    edit(tree / adopt.MANIFEST, f'"engine_version": "{VERSION}"', '"engine_version": "next"')

    code, out, _ = run(capsys, str(main), "--check")

    assert code == 0
    (line,) = warns(out)
    assert '"next" is not readable' in line


def test_run_in_a_linked_worktree_it_names_the_others_and_not_itself(
    tmp_path: Path, capsys: Capture
) -> None:
    main = project(tmp_path, capsys)
    tree = linked(main, "work", "work")
    edit(main / adopt.MANIFEST, f'"engine_version": "{VERSION}"', f'"engine_version": "{OLDER}"')

    _, out, _ = run(capsys, str(tree), "--check")

    (line,) = warns(out)
    assert str(main) in line and str(tree) not in line


def test_a_symlinked_manifest_is_not_followed(tmp_path: Path, capsys: Capture) -> None:
    main = project(tmp_path, capsys)
    tree = linked(main, "link", "link")
    outside = tmp_path / "outside.json"
    write(outside, f'{{"engine_version": "{OLDER}"}}\n')
    (tree / adopt.MANIFEST).unlink()
    (tree / "AGENTS.md").unlink()
    try:
        os.symlink(outside, tree / adopt.MANIFEST)
    except OSError:  # no symlink right on this platform
        return

    _, out, _ = run(capsys, str(main), "--check")

    (line,) = warns(out)
    assert NO_INSTALL in line


def test_a_project_with_one_worktree_prints_no_warning(tmp_path: Path, capsys: Capture) -> None:
    main = project(tmp_path, capsys)

    _, out, _ = run(capsys, str(main), "--check")

    assert warns(out) == []


# --- An install missing on disk, not committed, or facts-only -----------------------------

NOT_COMMITTED = "not committed: "
GONE = "expected block missing on disk"
HELD = "missing on disk, its commit holds them"
NOT_HELD = "missing on disk, its commit does not hold them either"
SKILL = ".claude/skills/diagnose/SKILL.md"


def head(root: Path) -> str:
    done = subprocess.run(
        [GIT, "-C", str(root), "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    )
    return done.stdout.strip()


def records(out: str) -> dict[str, str]:
    """Each record line of `--check`, by its label: the state and any detail."""

    found = {}
    for line in out.splitlines():
        state, _, rest = line.partition(" ")
        if state in ("current", "stale", "edited", "missing"):
            name, _, detail = rest.strip().partition(": ")
            found[name] = f"{state}: {detail}" if detail else state
    return found


def test_an_install_that_is_not_committed_is_named_and_the_exit_is_left_alone(
    tmp_path: Path, capsys: Capture
) -> None:
    main = repo(tmp_path / "main", {"README.md": "# Synthetic\n"})
    git(main, "add", "-A")
    git(main, "commit", "-q", "-m", "start")
    assert run(capsys, str(main), "--harness", "claude-code")[0] == 0
    before, commit = snapshot(main), head(main)

    code, out, _ = run(capsys, str(main), "--check")

    assert code == 0
    (line,) = warns(out)
    assert line.startswith("warn     not committed: AGENTS.md (operating-contract), ")
    assert adopt.MANIFEST in line and "absent from HEAD's commit or differ from it" in line
    assert "a new worktree from HEAD does not hold these bytes" in line
    assert "depends on the paths and the options" in line
    assert snapshot(main) == before and head(main) == commit

    git(main, "add", "-A")
    git(main, "commit", "-q", "-m", "install")
    _, out, _ = run(capsys, str(main), "--check")
    assert warns(out) == []


def test_a_block_a_stash_took_away_reads_missing_on_disk_and_is_not_restored(
    tmp_path: Path, capsys: Capture
) -> None:
    main = repo(tmp_path / "main", {"AGENTS.md": "# Project\n\nOur rules.\n"})
    git(main, "add", "-A")
    git(main, "commit", "-q", "-m", "start")
    assert run(capsys, str(main), "--harness", "claude-code")[0] == 0
    git(main, "add", ".outcomebound", ".claude")
    git(main, "commit", "-q", "-m", "the install's files, not its blocks")
    git(main, "stash", "push", "-q", "-m", "cleanup")
    before = snapshot(main)

    code, out, _ = run(capsys, str(main), "--check")

    kernel = records(out)["AGENTS.md (operating-contract)"]
    assert kernel == (
        f"missing: {GONE}; HEAD's commit does not hold it either (a stash or another branch may)"
    )
    assert code == 3 and "not loaded" not in out
    assert snapshot(main) == before
    stashed = subprocess.run(
        [GIT, "-C", str(main), "stash", "list"], check=True, capture_output=True, text=True
    )
    assert "cleanup" in stashed.stdout


def test_a_committed_block_taken_off_disk_reads_that_the_commit_holds_it(
    tmp_path: Path, capsys: Capture
) -> None:
    main = project(tmp_path, capsys)
    write(main / "AGENTS.md", "# Project\n")

    _, out, _ = run(capsys, str(main), "--check")

    assert records(out)["AGENTS.md (operating-contract)"] == (
        f"missing: {GONE}; HEAD's commit holds it"
    )


def test_a_worktree_made_from_a_commit_without_the_install_says_so_from_both_sides(
    tmp_path: Path, capsys: Capture
) -> None:
    main = repo(tmp_path / "main", {"README.md": "# Synthetic\n"})
    git(main, "add", "-A")
    git(main, "commit", "-q", "-m", "start")
    start = head(main)
    assert run(capsys, str(main), "--harness", "claude-code")[0] == 0
    git(main, "add", "-A")
    git(main, "commit", "-q", "-m", "install")
    tree = tmp_path / "early"
    git(main, "worktree", "add", "-q", "-b", "early", str(tree), start)

    _, out, _ = run(capsys, str(main), "--check")
    (line,) = warns(out)
    assert str(tree) in line
    assert line.endswith(f"{NO_INSTALL}; its commit holds no {adopt.MANIFEST}")

    code, out, _ = run(capsys, str(tree), "--check")
    assert code == 1
    assert (
        out.splitlines()[0] == f"missing  {adopt.MANIFEST}: HEAD's commit does not hold it either"
    )


def test_another_worktree_with_a_block_gone_or_an_install_not_committed_is_named(
    tmp_path: Path, capsys: Capture
) -> None:
    main = project(tmp_path, capsys)
    gone = linked(main, "gone", "gone")
    agents = (gone / "AGENTS.md").read_text(encoding="utf-8")
    write(gone / "AGENTS.md", adopt.cut(agents, adopt.KERNEL))
    loose = linked(main, "loose", "loose")
    assert run(capsys, str(loose), "--fragments", "commands,workspace")[0] == 0
    before = (snapshot(gone), snapshot(loose))

    code, out, _ = run(capsys, str(main), "--check")

    assert code == 0
    named = {line.split(" (branch ")[1].split(")")[0]: line for line in warns(out)}
    assert set(named) == {"gone", "loose"}
    assert f"installed {VERSION}; {HELD}: AGENTS.md (operating-contract)" in named["gone"]
    assert NOT_COMMITTED not in named["gone"]
    assert f"installed {VERSION}; {NOT_COMMITTED}" in named["loose"]
    assert "absent from its commit or differ from it" in named["loose"]
    assert (snapshot(gone), snapshot(loose)) == before


def test_a_facts_only_install_reads_as_intended_and_not_as_a_missing_contract(
    tmp_path: Path, capsys: Capture
) -> None:
    main = repo(tmp_path / "main", {"README.md": "# Synthetic\n"})
    assert run(capsys, str(main), "--harness", "claude-code", "--facts-only")[0] == 0
    git(main, "add", "-A")
    git(main, "commit", "-q", "-m", "install")
    tree = linked(main, "old", "old")
    edit(tree / adopt.MANIFEST, f'"engine_version": "{VERSION}"', f'"engine_version": "{OLDER}"')
    git(tree, "commit", "-q", "-am", "older")

    code, out, _ = run(capsys, str(main), "--check")

    assert code == 0 and GONE not in out and "operating-contract" not in records(out)
    assert any(
        line.startswith("note     facts-only install")
        and "by intent, no operating contract" in line
        for line in out.splitlines()
    )
    (line,) = warns(out)
    assert f"installed {OLDER} (facts-only), engine {VERSION}" in line


def test_another_worktree_names_each_missing_file_and_block_by_what_its_commit_holds(
    tmp_path: Path, capsys: Capture
) -> None:
    main = repo(tmp_path / "main", {"README.md": "# Synthetic\n"})
    git(main, "add", "-A")
    git(main, "commit", "-q", "-m", "start")
    start = head(main)
    assert run(capsys, str(main), "--harness", "claude-code")[0] == 0
    git(main, "add", "-A")
    git(main, "commit", "-q", "-m", "install")
    skill = linked(main, "skill", "skill")
    (skill / SKILL).unlink()
    never = tmp_path / "never"
    git(main, "worktree", "add", "-q", "-b", "never", str(never), start)
    assert run(capsys, str(never), "--harness", "claude-code")[0] == 0
    agents = (never / "AGENTS.md").read_text(encoding="utf-8")
    write(never / "AGENTS.md", adopt.cut(agents, adopt.KERNEL))

    code, out, _ = run(capsys, str(main), "--check")

    assert code == 0
    named = {line.split(" (branch ")[1].split(")")[0]: line for line in warns(out)}
    assert f"installed {VERSION}; {HELD}: {SKILL}" in named["skill"]
    assert f"{NOT_HELD}: AGENTS.md (operating-contract)" in named["never"]
    assert NOT_COMMITTED in named["never"]


def test_an_unreadable_worktree_reads_unverified_and_leaves_the_check_alone(
    tmp_path: Path, capsys: Capture
) -> None:
    main = project(tmp_path, capsys)
    broken = linked(main, "broken", "broken")
    write(broken / adopt.MANIFEST, "{ not json\n")
    locked = linked(main, "locked", "locked")
    (locked / SKILL).chmod(0)
    gone = linked(main, "gone", "gone")
    (gone / SKILL).unlink()
    try:
        code, out, _ = run(capsys, str(main), "--check")
    finally:
        (locked / SKILL).chmod(0o644)

    assert code == 0
    named = {line.split(" (branch ")[1].split(")")[0]: line for line in warns(out)}
    assert f"install state UNVERIFIED: cannot read {adopt.MANIFEST}" in named["broken"]
    assert f"{HELD}: {SKILL}" in named["gone"]
    (locked / SKILL).chmod(0)
    readable = os.access(locked / SKILL, os.R_OK)  # root, or a platform without mode bits
    (locked / SKILL).chmod(0o644)
    if readable:
        return
    assert f"install state UNVERIFIED: cannot read {SKILL}" in named["locked"]


def test_a_partial_clone_fetches_nothing_and_reads_what_it_lacks_as_unverified(
    tmp_path: Path, capsys: Capture
) -> None:
    source = project(tmp_path, capsys)
    git(source, "config", "uploadpack.allowFilter", "true")
    clone = tmp_path / "clone"
    url = source.resolve().as_uri()
    git(tmp_path, "clone", "-q", "--filter=blob:none", "--no-checkout", url, str(clone))
    git(clone, "sparse-checkout", "set", "--no-cone", "/*", "!/.claude/")
    git(clone, "checkout", "-q", git_out(clone, "rev-parse", "--abbrev-ref", "origin/HEAD")[7:])
    packed = git_out(clone, "count-objects", "-v")

    _, out, _ = run(capsys, str(clone), "--check")

    assert records(out)[SKILL] == (
        "missing: expected file missing on disk; whether HEAD's commit holds it is UNVERIFIED"
    )
    assert git_out(clone, "count-objects", "-v") == packed


def git_out(root: Path, *arguments: str) -> str:
    done = subprocess.run(
        [GIT, "-C", str(root), *arguments], check=True, capture_output=True, text=True
    )
    return done.stdout.strip()
