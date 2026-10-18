"""`outcomebound workspace audit`: what each Git worktree of a project holds and whether the
workspace guidance's mechanical test for removal holds (`docs/specs/workspace/design.md`).

What this module decides: the facts reported for each worktree (state of its commits, changed and
untracked paths, last commit, age, size), which listed worktrees have lost their folder, and
`removable`, which is true only for a linked worktree with no changed and no untracked path whose
HEAD commit is reachable from the default branch or from a pushed branch. Exits: 0 a report; 1
Git failed; 2 a usage error.

What it does not decide: whether a task is finished, or whether an ignored file is still needed.
Both stay with a person or an agent. It runs only `git` reads, with Git's optional locks off, and
changes nothing: it never removes or prunes a worktree. Standard library only.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from outcomebound_tools import programs, textio
from outcomebound_tools.adopt_worktrees import Worktree, parse
from outcomebound_tools.gitenv import GIT_READ_CONFIGURATION, git_environment

VERSION = 1
GIT_FAILED = "WORKSPACE_GIT_FAILED"
STATES = ("merged", "pushed", "local", "unknown")


class WorkspaceError(Exception):
    pass


def _git(root: Path, *arguments: str) -> tuple[int, bytes, bytes]:
    try:
        completed = subprocess.run(
            [programs.require("git"), *GIT_READ_CONFIGURATION, *arguments],
            cwd=root,
            env=git_environment({**os.environ, "GIT_OPTIONAL_LOCKS": "0"}),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            check=False,
        )
    except OSError as error:
        raise WorkspaceError(
            f"{GIT_FAILED}: git could not run: {textio.plain(str(error))}"
        ) from error
    return completed.returncode, completed.stdout, completed.stderr


def _text(root: Path, *arguments: str) -> str | None:
    status, output, _ = _git(root, *arguments)
    return output.decode("utf-8", "replace").strip() if status == 0 else None


def default_branch(root: Path) -> str | None:
    """The ref of the default branch: the remote's (`refs/remotes/origin/HEAD`), else a local
    `main` or `master`; None where there is none."""

    target = _text(root, "symbolic-ref", "--quiet", "refs/remotes/origin/HEAD")
    if target and _text(root, "rev-parse", "--verify", "--quiet", target) is not None:
        return target
    for name in ("main", "master"):
        ref = f"refs/heads/{name}"
        if _text(root, "rev-parse", "--verify", "--quiet", ref) is not None:
            return ref
    return None


def classify(root: Path, commit: str, default: str | None) -> str:
    """`merged` where `default` holds `commit`; `pushed` where a remote-tracking branch does;
    else `local`."""

    if default is not None:
        status, _, _ = _git(root, "merge-base", "--is-ancestor", commit, default)
        if status == 0:
            return "merged"
    held = _text(root, "for-each-ref", "--contains", commit, "--format=%(refname)", "refs/remotes")
    if held is None:
        return "unknown"
    # origin/HEAD is only a pointer to a branch that is listed on its own.
    names = [name for name in held.splitlines() if not name.endswith("/HEAD")]
    return "pushed" if names else "local"


def changes(path: Path) -> tuple[int, int] | None:
    """The tracked paths changed and the untracked paths Git does not ignore in a work tree."""

    status, output, _ = _git(path, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    if status != 0:
        return None
    changed = untracked = 0
    fields = output.split(b"\0")
    index = 0
    while index < len(fields) and fields[index]:
        code = fields[index][:2]
        if code == b"??":
            untracked += 1
        elif code != b"!!":
            changed += 1
        # A rename or copy names its source in the next field.
        index += 2 if b"R" in code or b"C" in code else 1
    return changed, untracked


def disk_size(path: Path) -> tuple[int, bool]:
    """The bytes of the regular files under `path`, symbolic links skipped, and whether every
    folder could be read."""

    total = 0
    complete = True
    pending = [path]
    while pending:
        try:
            with os.scandir(pending.pop()) as entries:
                for entry in entries:
                    try:
                        if entry.is_symlink():
                            continue
                        if entry.is_dir(follow_symlinks=False):
                            pending.append(Path(entry.path))
                        elif entry.is_file(follow_symlinks=False):
                            total += entry.stat(follow_symlinks=False).st_size
                    except OSError:
                        complete = False
        except OSError:
            complete = False
    return total, complete


def _audit_one(tree: Worktree, main: bool, default: str | None, now: datetime) -> dict[str, Any]:
    path = tree.path
    entry: dict[str, Any] = {
        "path": str(path),
        "branch": tree.branch,
        "main": main,
        "state": "unknown",
        "changed": None,
        "untracked": None,
        "last_commit": None,
        "age_days": None,
        "bytes": 0,
        "bytes_complete": True,
        "removable": False,
    }
    entry["bytes"], entry["bytes_complete"] = disk_size(path)
    commit = _text(path, "rev-parse", "--verify", "--quiet", "HEAD^{commit}")
    if commit:
        entry["state"] = classify(path, commit, default)
        stamp = _text(path, "log", "-1", "--format=%cI", commit)
        if stamp:
            when = datetime.fromisoformat(stamp)
            entry["last_commit"] = stamp
            entry["age_days"] = max(0, (now - when).days)
    found = changes(path)
    if found is not None:
        entry["changed"], entry["untracked"] = found
    entry["removable"] = (
        not main
        and entry["state"] in ("merged", "pushed")
        and found is not None
        and found == (0, 0)
    )
    return entry


def build_report(root: Path, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    status, listed, error = _git(root, "worktree", "list", "--porcelain")
    if status != 0:
        message = error.decode("utf-8", "replace").strip() or f"git exited {status}"
        raise WorkspaceError(f"{GIT_FAILED}: {textio.plain(message)}")
    trees = parse(listed.decode("utf-8", "replace"))
    default = default_branch(root)
    present: list[dict[str, Any]] = []
    gone: list[dict[str, str]] = []
    for position, tree in enumerate(trees):
        if tree.path.is_dir():
            present.append(_audit_one(tree, position == 0, default, now))
        else:
            gone.append({"path": str(tree.path), "branch": tree.branch})
    counts = {state: sum(1 for item in present if item["state"] == state) for state in STATES}
    return {
        "version": VERSION,
        "default_branch": default,
        "worktrees": present,
        "prunable": gone,
        "counts": counts,
        "removable": sum(1 for item in present if item["removable"]),
        "bytes": sum(item["bytes"] for item in present),
    }


def _human(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{size} B"


def render_json(report: dict[str, Any]) -> str:
    return json.dumps(report, indent=2, sort_keys=True) + "\n"


def render_text(report: dict[str, Any]) -> str:
    out = [f"default branch: {report['default_branch'] or 'none found'}"]
    for item in report["worktrees"]:
        flags = []
        if item["main"]:
            flags.append("main checkout")
        if item["removable"]:
            flags.append("removable by the mechanical rule")
        size = _human(item["bytes"]) + ("" if item["bytes_complete"] else " (partial)")
        age = "no commit" if item["age_days"] is None else f"{item['age_days']} d old"
        out.append(f"{textio.visible(item['path'])}")
        out.append(
            f"  branch {textio.visible(item['branch'])} | commits {item['state']} | "
            f"changed {item['changed']} | untracked {item['untracked']} | {age} | {size}"
            + (f" | {'; '.join(flags)}" if flags else "")
        )
    out.extend(
        f"prunable (folder gone): {textio.visible(item['path'])} ({textio.visible(item['branch'])})"
        for item in report["prunable"]
    )
    counts = report["counts"]
    out.append(
        f"{len(report['worktrees'])} worktrees: "
        + ", ".join(f"{counts[state]} {state}" for state in STATES)
        + f"; {len(report['prunable'])} prunable; {report['removable']} removable by the "
        f"mechanical rule; {_human(report['bytes'])} in all"
    )
    out.append(
        "removable covers only commits kept and no changed or untracked path; ignored files and "
        "whether the task is finished are not known to this report. Nothing was changed."
    )
    return "\n".join(out) + "\n"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="outcomebound workspace",
        description=(
            "Report on the Git worktrees of a project. `audit` lists each worktree's branch, "
            "whether its commits are merged into the default branch, pushed only, or local only, "
            "its changed and untracked paths, last commit, age and size, and the worktrees Git "
            "lists whose folder is gone. `removable` is the mechanical part of the workspace "
            "rule only. It runs only `git` reads and never removes or prunes anything."
        ),
    )
    commands = parser.add_subparsers(dest="command", required=True)
    audit = commands.add_parser("audit", help="report on the project's worktrees")
    audit.add_argument(
        "target", nargs="?", default=".", help="a folder of the project (default: .)"
    )
    audit.add_argument("--json", action="store_true", help="print one JSON object, not text")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    options = _parser().parse_args(argv)
    target = Path(options.target)
    if not target.is_dir():
        sys.stderr.write(
            f"WORKSPACE_TARGET_NOT_FOLDER: {textio.quote(options.target)} is not a folder\n"
        )
        return 2
    try:
        top = _text(target, "rev-parse", "--show-toplevel")
        if not top:
            raise WorkspaceError(
                f"{GIT_FAILED}: {textio.quote(options.target)} is not in a Git work tree"
            )
        report = build_report(Path(top))
    except WorkspaceError as error:
        sys.stderr.write(f"{error}\n")
        return 1
    sys.stdout.write(render_json(report) if options.json else render_text(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
