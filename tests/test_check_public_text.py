"""`scripts/check-public-text.py`, the floor's `public-text` gate and `make scrub`, finds each
kind of hit it names, in files, commit messages and standard input, and never prints the text it
matched, so its PASS on this repository is not a check that looked at nothing.

The home paths below are built from parts, so that this file does not hold one."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts/check-public-text.py"
GIT = shutil.which("git") or "git"
HOME_PATH = "/" + "Users" + "/someone/notes"
LINUX_HOME = "/" + "home" + "/someone"
TILDE_PRIVATE = "~" + "/Documents/client/plan.md"
TILDE_DOCUMENTED = "~" + "/.outcomebound/research"
PRIVATE = "Zanzibarco"
BASE = "OUTCOMEBOUND_BASE"


def repository(path: Path, files: dict[str, str]) -> Path:
    """A Git repository at `path` with one commit that tracks `files`."""

    path.mkdir()
    subprocess.run([GIT, "init", "-q", str(path)], check=True)
    for name, text in files.items():
        (path / name).parent.mkdir(parents=True, exist_ok=True)
        (path / name).write_text(text, encoding="utf-8")
    commit(path, "Start")
    return path


def commit(path: Path, message: str) -> None:
    subprocess.run([GIT, "-C", str(path), "add", "-A"], check=True)
    who = ["-c", "user.name=t", "-c", "user.email=t@example.org"]
    subprocess.run(
        [GIT, "-C", str(path), *who, "commit", "-qm", message, "--allow-empty"], check=True
    )


def check(
    root: Path, *arguments: str, listed: Path | None = None, given: str | None = None
) -> tuple[int, list[str]]:
    environment = {k: v for k, v in os.environ.items() if k not in ("OB_SCRUB_LIST", BASE)}
    if listed is not None:
        environment["OB_SCRUB_LIST"] = str(listed)
    done = subprocess.run(
        [sys.executable, str(SCRIPT), str(root), *arguments],
        capture_output=True,
        text=True,
        check=False,
        input=given,
        env=environment,
    )
    return done.returncode, done.stdout.splitlines()


def test_home_paths_in_files_and_commits_fail_and_documented_paths_pass(tmp_path: Path) -> None:
    root = repository(
        tmp_path / "r",
        {
            "README.md": f"Clone it to `{TILDE_DOCUMENTED}`.\nSee https://example.org/home/page.\n",
            "docs/a.md": f"one\nRun from {HOME_PATH} today.\n",
            "docs/b.txt": f"{LINUX_HOME}/x\nand {TILDE_PRIVATE}\n",
            "image.bin": "\0" + HOME_PATH,
        },
    )
    commit(root, f"Fix it\n\nMade in {TILDE_PRIVATE}.")

    code, lines = check(root, "--base", "HEAD~1")

    assert code == 1
    assert lines[0] == "FAIL public-text: 4 hits (3 files, 1 commit)"
    hits = sorted(line.strip() for line in lines[1:])
    expected = ["docs/a.md:2", "docs/b.txt:1", "docs/b.txt:2"]
    assert hits[1:] == [f"{place}: a home path" for place in expected]
    assert hits[0].startswith("commit ") and hits[0].endswith(":3: a home path")
    assert not any("someone" in line or "Documents" in line for line in lines)


def test_a_clean_tree_passes_and_the_range_comes_from_the_environment(tmp_path: Path) -> None:
    root = repository(tmp_path / "r", {"README.md": f"See `{TILDE_DOCUMENTED}/x`.\n"})
    commit(root, "Second")

    done = subprocess.run(
        [sys.executable, str(SCRIPT), str(root)],
        capture_output=True,
        text=True,
        check=False,
        env={**{k: v for k, v in os.environ.items() if k != "OB_SCRUB_LIST"}, BASE: "HEAD~1"},
    )

    assert done.returncode == 0
    assert done.stdout.splitlines() == ["PASS public-text: no home path (1 file, 1 commit)"]


def test_the_local_list_matches_whole_words_and_never_prints_the_term(tmp_path: Path) -> None:
    listed = tmp_path / "list.txt"
    listed.write_text(f"# private names\n{PRIVATE}\n", encoding="utf-8")
    root = repository(
        tmp_path / "r",
        {"a.md": f"Seen at {PRIVATE.lower()} once.\n", "b.md": f"Not {PRIVATE}ish.\n"},
    )

    unlisted = "UNVERIFIED public-text: no local list (OB_SCRUB_LIST); no home path"
    assert check(root, "--private") == (2, [f"{unlisted} (2 files, 0 commits)"])
    assert check(root) == (0, ["PASS public-text: no home path (2 files, 0 commits)"])

    code, lines = check(root, "--private", listed=listed)

    assert code == 1
    assert lines == [
        "FAIL public-text: 1 hit (2 files, 0 commits)",
        "  a.md:1: matches the local list",
    ]
    assert not any(PRIVATE.lower() in line.lower() for line in lines)


def test_stdin_reads_only_what_it_is_given(tmp_path: Path) -> None:
    listed = tmp_path / "list.txt"
    listed.write_text(f"{PRIVATE}\n", encoding="utf-8")
    root = repository(tmp_path / "r", {"a.md": f"{HOME_PATH}\n"})
    given = f"A title\n\nA body that names {PRIVATE} and {TILDE_PRIVATE}.\n"

    code, lines = check(root, "--stdin", "--private", listed=listed, given=given)

    assert code == 1
    assert lines == [
        "FAIL public-text: 2 hits (standard input)",
        "  stdin:3: a home path",
        "  stdin:3: matches the local list",
    ]
    assert check(root, "--stdin", given="A clean title\n") == (
        0,
        ["PASS public-text: no home path (standard input)"],
    )


def test_a_base_that_names_no_commit_reads_unverified(tmp_path: Path) -> None:
    root = repository(tmp_path / "r", {"a.md": "clean\n"})

    assert check(root, "--base", "no-such-ref") == (
        2,
        ["UNVERIFIED public-text: --base no-such-ref names no commit"],
    )
