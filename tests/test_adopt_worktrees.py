"""The `warn` lines of `adopt --check` for a Git worktree whose installed OutcomeBound is older
than the engine. Every project is a temporary Git repository with a synthetic install; the check
reads the other worktrees and writes nothing in them, and no line moves the exit code."""

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
