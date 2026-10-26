"""The facts-only overlay: `adopt <worktree> --facts-only --local` and `--full --local`.

docs/specs/install/design.md, decisions on the overlay. Every project is a temporary Git
repository with a synthetic install and linked worktrees. The assertions are about bytes on disk,
what Git tracks, the overlay record and exit statuses; `--check` lines only where a person reads
them. No harness runs: what a session loads is not tested here.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from outcomebound_tools import adopt, identity, overlay, workspace
from tests.adopt_helpers import GIT, Capture, manifest, repo, run, snapshot, states
from tests.portable import write

IDENTITY = ["-c", "user.name=a", "-c", "user.email=a@example.org", "-c", "commit.gpgsign=false"]
HARNESSES = "claude-code,codex"
CODEX, CLAUDE = "AGENTS.override.md", "CLAUDE.local.md"


def git(root: Path, *arguments: str) -> str:
    done = subprocess.run(
        [GIT, "-C", str(root), *IDENTITY, *arguments], check=True, capture_output=True
    )
    return done.stdout.decode("utf-8")


def project(
    tmp_path: Path, capsys: Capture, *install: str, files: dict[str, str] | None = None
) -> Path:
    """A committed project with a full install (or the install `install` asks for)."""

    main = repo(tmp_path / "main", {"README.md": "# Synthetic\n", **(files or {})})
    arguments = install or ("--harness", HARNESSES)
    code, _, err = run(capsys, str(main), *arguments)
    assert code == 0, err
    git(main, "add", "-A")
    git(main, "commit", "-q", "-m", "install")
    return main


def linked(main: Path, name: str) -> Path:
    tree = main.parent / name
    git(main, "worktree", "add", "-q", "-b", name, str(tree))
    return tree


def block_ids(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    return [block.block_id for block in identity.find_managed_blocks(text)]


def untracked(tree: Path) -> list[str]:
    status = git(tree, "status", "--porcelain", "--untracked-files=all")
    return sorted(line[3:] for line in status.splitlines() if line.startswith("?? "))


def overlay_on(capsys: Capture, tree: Path, *more: str) -> tuple[int, str, str]:
    return run(capsys, str(tree), "--facts-only", "--local", *more)


def test_the_overlay_is_untracked_and_nothing_committed_changes(
    tmp_path: Path, capsys: Capture
) -> None:
    """Breaks if the overlay touches the committed install, the main checkout or another
    worktree, or if it writes a file the record does not list."""

    main = project(tmp_path, capsys)
    tree, other = linked(main, "a"), linked(main, "b")
    before = {path: snapshot(path) for path in (main, tree, other)}

    code, out, err = overlay_on(capsys, tree)

    assert code == 0, err
    assert snapshot(main) == before[main] and snapshot(other) == before[other]
    after = snapshot(tree)
    added = sorted(set(after) - set(before[tree]))
    assert added == sorted([CODEX, CLAUDE, overlay.RECORD])
    assert {key: value for key, value in after.items() if key in before[tree]} == before[tree]
    assert untracked(tree) == [CODEX, CLAUDE]  # the record is kept out of Git by its .gitignore
    for name in (CODEX, CLAUDE):
        assert block_ids(tree / name) == [adopt.FACTS]
    assert adopt.KERNEL in block_ids(tree / "AGENTS.md")
    record = json.loads((tree / overlay.RECORD).read_text(encoding="utf-8"))
    kinds = sorted((item["kind"], item["path"]) for item in record["artifacts"])
    assert kinds == sorted([("file", CODEX), ("file", CLAUDE)])
    assert {item["path"]: item["sha256"] for item in record["artifacts"]} == {
        name: adopt.sha256((tree / name).read_bytes()) for name in (CODEX, CLAUDE)
    }
    assert "UNVERIFIED" in out and "no session has been run" in out


def test_the_overlay_text_is_what_a_facts_only_install_writes(
    tmp_path: Path, capsys: Capture
) -> None:
    main = project(tmp_path, capsys)
    tree = linked(main, "a")
    twin = linked(main, "twin")
    code, _, err = run(capsys, str(twin), "--facts-only")
    assert code == 0, err

    overlay_on(capsys, tree)

    expected = (twin / "AGENTS.md").read_bytes()
    assert (tree / CODEX).read_bytes() == expected
    assert (tree / CLAUDE).read_bytes() == expected


def test_a_merge_of_the_worktrees_branch_carries_nothing_of_the_overlay(
    tmp_path: Path, capsys: Capture
) -> None:
    main = project(tmp_path, capsys)
    tree, target = linked(main, "a"), linked(main, "landing")
    overlay_on(capsys, tree)
    write(tree / "change.txt", "work\n")
    git(tree, "add", "change.txt")
    git(tree, "commit", "-q", "-m", "work")

    git(target, "merge", "-q", "--no-edit", "a")

    assert (target / "change.txt").is_file()
    for name in (CODEX, CLAUDE, overlay.RECORD):
        assert not (target / name).exists()
    assert "AGENTS.md" not in git(target, "diff", "--name-only", "HEAD~1", "HEAD")
    assert adopt.KERNEL in block_ids(target / "AGENTS.md")


def test_check_reads_the_mode_and_each_state(tmp_path: Path, capsys: Capture) -> None:
    main = project(tmp_path, capsys)
    tree = linked(main, "a")
    overlay_on(capsys, tree)

    code, out, _ = run(capsys, str(tree), "--check")

    assert code == 0
    lines = [line for line in out.splitlines() if line]
    assert lines[0] == "note     facts-only overlay over a full install"
    found = states(out)
    assert found[f"{CODEX} (facts-only overlay)"] == "current"
    assert found[f"{CLAUDE} (facts-only overlay)"] == "current"
    assert not (tree / "CLAUDE.md").exists()  # the overlay's CLAUDE.local.md adds no import block

    write(tree / CODEX, "my own text\n")
    (tree / CLAUDE).unlink()
    code, out, _ = run(capsys, str(tree), "--check")
    found = states(out)
    assert code == 2
    assert found[f"{CODEX} (facts-only overlay)"] == "edited"
    assert found[f"{CLAUDE} (facts-only overlay)"] == "missing"

    overlay_on(capsys, tree, "--force")
    code, _, _ = run(capsys, str(tree), "--check")
    assert code == 0

    code, _, err = run(capsys, str(tree), "--done", "make test")  # the committed install moves
    assert code == 0, err
    assert not (tree / "CLAUDE.md").exists()
    _, out, _ = run(capsys, str(tree), "--check")
    assert states(out)[f"{CODEX} (facts-only overlay)"] == "stale"


def test_a_worktree_without_an_overlay_prints_no_overlay_line(
    tmp_path: Path, capsys: Capture
) -> None:
    main = project(tmp_path, capsys)

    _, out, _ = run(capsys, str(main), "--check")

    assert "overlay" not in out


def test_the_other_worktree_lines_and_the_audit_name_the_mode(
    tmp_path: Path, capsys: Capture
) -> None:
    main = project(tmp_path, capsys)
    tree = linked(main, "a")
    overlay_on(capsys, tree)
    older = (tree / adopt.MANIFEST).read_text(encoding="utf-8")
    version = manifest(tree)["engine_version"]
    write(tree / adopt.MANIFEST, older.replace(f'"{version}"', '"0.9.0"'))

    _, out, _ = run(capsys, str(main), "--check")

    (line,) = [item for item in out.splitlines() if item.startswith("warn ")]
    assert "installed 0.9.0 (facts-only overlay)" in line
    modes = {
        Path(item["path"]).name: item["mode"] for item in workspace.build_report(main)["worktrees"]
    }
    assert modes == {"main": "full", "a": "facts-only overlay"}


def test_full_local_and_remove_leave_no_overlay_file(tmp_path: Path, capsys: Capture) -> None:
    main = project(tmp_path, capsys)
    tree, other = linked(main, "a"), linked(main, "b")
    before = snapshot(tree)
    overlay_on(capsys, tree)

    code, out, err = run(capsys, str(tree), "--full", "--local")

    assert code == 0, err
    assert snapshot(tree) == before
    assert out.count("delete") == 3

    overlay_on(capsys, tree)
    code, _, err = run(capsys, str(tree), "--remove")
    assert code == 0, err
    for name in (CODEX, CLAUDE, overlay.RECORD, adopt.MANIFEST):
        assert not (tree / name).exists()
    code, _, err = run(capsys, str(other), "--remove")
    assert code == 0, err


def test_a_dry_run_and_a_removal_without_an_overlay_write_nothing(
    tmp_path: Path, capsys: Capture
) -> None:
    main = project(tmp_path, capsys)
    tree = linked(main, "a")
    before = snapshot(tree)

    code, out, _ = overlay_on(capsys, tree, "--dry-run")
    assert code == 0 and "dry run: nothing written" in out and CODEX in out
    code, out, _ = run(capsys, str(tree), "--full", "--local")
    assert code == 0 and "nothing to change" in out

    assert snapshot(tree) == before


def test_a_facts_only_committed_install_gets_no_overlay(tmp_path: Path, capsys: Capture) -> None:
    main = project(tmp_path, capsys, "--harness", HARNESSES, "--facts-only")
    tree = linked(main, "a")
    before = snapshot(tree)

    code, out, _ = overlay_on(capsys, tree)

    assert code == 0 and "already facts-only" in out
    assert snapshot(tree) == before


def test_the_claude_md_host_case_writes_an_absolute_exclusion_merged_into_local_settings(
    tmp_path: Path, capsys: Capture
) -> None:
    """Breaks if the exclusion is relative, replaces a key the file holds, or is removed with
    anything else than its own entry."""

    main = project(tmp_path, capsys, files={"CLAUDE.md": "# Notes\n"})
    tree = linked(main, "a")
    settings = tree / ".claude" / "settings.local.json"
    start = {"permissions": {"allow": ["Bash(ls)"]}, "claudeMdExcludes": ["/elsewhere/CLAUDE.md"]}
    original = json.dumps(start, indent=4) + "\n"
    write(settings, original)
    kept = snapshot(main)

    code, _, err = overlay_on(capsys, tree)

    assert code == 0, err
    held = json.loads(settings.read_text(encoding="utf-8"))
    mine = (tree.resolve() / "CLAUDE.md").as_posix()
    assert held["claudeMdExcludes"] == ["/elsewhere/CLAUDE.md", mine]
    assert held["permissions"] == {"allow": ["Bash(ls)"]}
    assert Path(mine).is_absolute() and str(main) not in settings.read_text(encoding="utf-8")
    assert snapshot(main) == kept
    code, out, _ = run(capsys, str(tree), "--check")
    assert code == 0
    assert f"{overlay.EXCLUDES}: {mine}" in out

    code, _, err = run(capsys, str(tree), "--full", "--local")

    assert code == 0, err
    assert settings.read_text(encoding="utf-8") == original


def test_a_settings_file_the_overlay_made_goes_with_it(tmp_path: Path, capsys: Capture) -> None:
    main = project(tmp_path, capsys, files={"CLAUDE.md": "# Notes\n"})
    tree = linked(main, "a")
    before = snapshot(tree)

    overlay_on(capsys, tree)
    settings = tree / ".claude" / "settings.local.json"
    assert json.loads(settings.read_text(encoding="utf-8")) == {
        overlay.EXCLUDES: [(tree.resolve() / "CLAUDE.md").as_posix()]
    }
    run(capsys, str(tree), "--full", "--local")

    assert snapshot(tree) == before


def test_other_harnesses_are_refused_before_a_write(tmp_path: Path, capsys: Capture) -> None:
    for number, harness in enumerate(("cursor", "claude-code,gemini", "generic")):
        sub = tmp_path / str(number)
        sub.mkdir()
        main = project(sub, capsys, "--harness", harness)
        tree = linked(main, "a")
        before = snapshot(tree)

        code, out, err = overlay_on(capsys, tree)

        assert code == 1 and out == ""
        assert "UNVERIFIED" in err and "nothing was written" in err
        assert snapshot(tree) == before


def test_a_file_the_overlay_did_not_write_is_refused_without_force(
    tmp_path: Path, capsys: Capture
) -> None:
    main = project(tmp_path, capsys, "--harness", "codex")
    tree = linked(main, "a")
    write(tree / CODEX, "mine\n")
    before = snapshot(tree)

    code, _, err = overlay_on(capsys, tree)
    assert code == 1 and CODEX in err and snapshot(tree) == before

    code, out, _ = overlay_on(capsys, tree, "--force")
    assert code == 0 and "overridden by --force" in out
    assert block_ids(tree / CODEX) == [adopt.FACTS]


def test_the_report_warns_where_git_does_not_ignore_an_overlay_file(
    tmp_path: Path, capsys: Capture
) -> None:
    """Breaks if adopt stays silent about an overlay file that a commit could carry, or writes
    `.git` or the root `.gitignore` itself."""

    main = project(tmp_path, capsys, "--harness", "codex")
    tree = linked(main, "a")

    _, out, _ = overlay_on(capsys, tree)

    warned = [line for line in out.splitlines() if line.startswith("warning")]
    assert len(warned) == 1 and CODEX in warned[0] and ".git/info/exclude" in warned[0]
    assert not (tree / ".gitignore").exists()
    common = Path(git(tree, "rev-parse", "--path-format=absolute", "--git-common-dir").strip())
    assert not (common / "info" / "exclude").read_text(encoding="utf-8").count(CODEX)

    with (common / "info" / "exclude").open("a", encoding="utf-8") as handle:
        handle.write(f"{CODEX}\n")
    (tree / CODEX).unlink()
    _, out, _ = overlay_on(capsys, tree)
    assert "warning" not in out
