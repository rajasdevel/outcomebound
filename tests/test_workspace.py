"""`outcomebound workspace audit`: the state of each worktree's commits (merged, pushed, local),
changed and untracked counts, the prunable entries, the removable rule, and that nothing changes."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from outcomebound_tools import workspace

IDENTITY = ("-c", "user.name=W", "-c", "user.email=w@example.test", "-c", "commit.gpgsign=false")


@pytest.fixture(autouse=True)
def hermetic_git(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


def git(where: Path, *args: str) -> str:
    done = subprocess.run(["git", *IDENTITY, *args], cwd=where, check=True, capture_output=True)
    return done.stdout.decode("utf-8").strip()


def commit(root: Path, name: str) -> None:
    (root / name).write_text(name, encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", name)


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """A clone with a pushed main and four linked worktrees: merged, pushed, local, dirty."""

    origin = tmp_path / "origin.git"
    git(tmp_path, "init", "-q", "--bare", "-b", "main", str(origin))
    main = tmp_path / "main"
    git(tmp_path, "clone", "-q", str(origin), str(main))
    git(main, "checkout", "-q", "-b", "main")
    commit(main, "base")
    git(main, "push", "-q", "-u", "origin", "main")
    git(main, "remote", "set-head", "origin", "main")
    trees = tmp_path / "trees"
    git(main, "worktree", "add", "-q", "-b", "merged", str(trees / "merged"))
    git(main, "worktree", "add", "-q", "-b", "pushed", str(trees / "pushed"))
    commit(trees / "pushed", "p")
    git(trees / "pushed", "push", "-q", "origin", "pushed")
    git(main, "worktree", "add", "-q", "-b", "local", str(trees / "local"))
    commit(trees / "local", "l")
    git(main, "worktree", "add", "-q", "-b", "dirty", str(trees / "dirty"))
    (trees / "dirty" / "base").write_text("edited", encoding="utf-8")
    (trees / "dirty" / "new.txt").write_text("x", encoding="utf-8")
    (trees / "dirty" / ".gitignore").write_text("ignored\n", encoding="utf-8")
    (trees / "dirty" / "ignored").write_text("y", encoding="utf-8")
    return main


def by_branch(report: dict) -> dict:
    return {item["branch"]: item for item in report["worktrees"]}


def test_each_worktree_gets_its_state_and_the_removable_rule(project: Path) -> None:
    report = workspace.build_report(project)
    found = by_branch(report)
    assert {name: found[name]["state"] for name in found} == {
        "main": "merged",
        "merged": "merged",
        "pushed": "pushed",
        "local": "local",
        "dirty": "merged",
    }
    assert (
        found["dirty"]["changed"] == 1 and found["dirty"]["untracked"] == 2
    )  # .gitignore, new.txt
    assert found["merged"]["changed"] == 0 and found["merged"]["untracked"] == 0
    assert {name for name, item in found.items() if item["removable"]} == {"merged", "pushed"}
    assert found["main"]["main"] is True
    assert report["counts"] == {"merged": 3, "pushed": 1, "local": 1, "unknown": 0}
    assert report["default_branch"] == "refs/remotes/origin/main"


def test_a_missing_folder_is_prunable_and_nothing_is_removed(project: Path, tmp_path: Path) -> None:
    gone = tmp_path / "trees" / "pushed"
    subprocess.run(["rm", "-rf", str(gone)], check=True)
    before = git(project, "worktree", "list", "--porcelain")
    report = workspace.build_report(project)
    assert [item["branch"] for item in report["prunable"]] == ["pushed"]
    assert "pushed" not in by_branch(report)
    assert git(project, "worktree", "list", "--porcelain") == before  # not pruned


def test_size_counts_regular_files_and_skips_symlinks(tmp_path: Path) -> None:
    (tmp_path / "a").write_bytes(b"x" * 10)
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b").write_bytes(b"y" * 5)
    big = tmp_path.parent / (tmp_path.name + "-outside")
    big.write_bytes(b"z" * 1000)
    (tmp_path / "link").symlink_to(big)
    assert workspace.disk_size(tmp_path) == (15, True)


def test_the_verb_prints_text_and_json_and_reads_only(
    project: Path, capsys, tmp_path: Path
) -> None:
    before = git(project, "status", "--porcelain=v1", "--ignored")
    assert workspace.main(["audit", str(project), "--json"]) == 0
    document = json.loads(capsys.readouterr().out)
    assert document["version"] == 1 and document["removable"] == 2
    assert workspace.main(["audit", str(project)]) == 0
    text = capsys.readouterr().out
    assert "commits pushed" in text and "Nothing was changed" in text
    assert git(project, "status", "--porcelain=v1", "--ignored") == before


def test_a_folder_outside_git_exits_1_and_a_missing_one_exits_2(tmp_path: Path, capsys) -> None:
    assert workspace.main(["audit", str(tmp_path)]) == 1
    assert "WORKSPACE_GIT_FAILED" in capsys.readouterr().err
    assert workspace.main(["audit", str(tmp_path / "nope")]) == 2
