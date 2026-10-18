"""Keep what one validation claim observed, and say which of its declared paths changed since.

A record is an observation written when a claim ran (`schemas/validation-result.schema.json`). The
status reader compares it with the work tree now. It runs nothing and writes nothing, and it never
turns a result into `PASS`: it names the paths that changed, and the reader judges.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import posixpath
import re
import stat
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from outcomebound_tools import size

RESULT_SUFFIX = ".result.json"
CURRENT = "CURRENT"
CHANGED = "CHANGED"
UNVERIFIED = "UNVERIFIED"
DELETED = "deleted"
UNREADABLE = "unreadable"


@dataclass(frozen=True)
class Snapshot:
    """HEAD and the dirty paths (path to content digest) at one moment; both None without Git."""

    head: str | None
    dirty: dict[str, str] | None


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def result_path(log_path: Path) -> Path:
    return log_path.with_name(log_path.stem + RESULT_SUFFIX)


def _digest(path: Path) -> str:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return DELETED
    except OSError:
        return UNREADABLE
    try:
        if stat.S_ISLNK(info.st_mode):
            return hashlib.sha256(os.fsencode(os.readlink(path))).hexdigest()
        if not stat.S_ISREG(info.st_mode):
            return UNREADABLE
        sha = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1 << 20), b""):
                sha.update(block)
        return sha.hexdigest()
    except OSError:
        return UNREADABLE


def _toplevel(cwd: Path) -> tuple[Path, str] | None:
    """The work tree's root and `cwd`'s place in it ('' or 'dir/'); None outside a work tree."""

    try:
        status, output, _ = size._git(cwd, "rev-parse", "--show-toplevel", "--show-prefix")
    except (size.SizeError, OSError):
        return None
    lines = output.decode("utf-8", "replace").split("\n")
    if status != 0 or len(lines) < 2 or not lines[0]:
        return None
    return Path(lines[0]), lines[1]


def _names(root: Path, *arguments: str) -> set[str]:
    output = size._git_ok(root, *arguments)
    return {os.fsdecode(name) for name in output.split(b"\0") if name}


def capture(cwd: Path, skip: Path) -> Snapshot:
    """HEAD and the dirty paths now: the tracked paths that differ from HEAD and the untracked
    paths Git does not ignore, relative to the repository root, without the folder `skip`."""

    found = _toplevel(cwd)
    if found is None:
        return Snapshot(None, None)
    root = found[0]
    try:
        head = size._commit_of(root, "HEAD")
        if head is None:
            return Snapshot(None, None)
        names = _names(root, "diff-index", "--name-only", "-z", "--no-renames", "HEAD", "--")
        names |= set(size.untracked_paths(root))
    except (size.SizeError, OSError):
        return Snapshot(None, None)
    try:
        skipped = skip.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        skipped = None
    dirty = {
        name: _digest(root / name)
        for name in sorted(names)
        if skipped is None or not (name == skipped or name.startswith(skipped + "/"))
    }
    return Snapshot(head, dirty)


def build(observed: dict[str, Any], snapshot: Snapshot) -> dict[str, Any]:
    """A record: what the claim observed (every schema field but the Git state) and `snapshot`."""

    dirty = snapshot.dirty
    return {
        "version": 1,
        **observed,
        "head": snapshot.head,
        "dirty": None if dirty is None else [{"path": p, "digest": d} for p, d in dirty.items()],
    }


def write(path: Path, record: dict[str, Any]) -> str | None:
    """Write a record beside its log, whole or not at all; the reason where it could not. A
    failed write removes the claim's earlier record, so `status` does not offer it as the last."""

    temporary = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=path.parent, suffix=".tmp", delete=False
        ) as handle:
            temporary = Path(handle.name)
            handle.write(json.dumps(record, indent=2) + "\n")
        os.replace(temporary, path)
    except OSError as error:
        for leftover in (temporary, path):
            if leftover is not None:
                with contextlib.suppress(OSError):
                    leftover.unlink()
        return str(error)
    return None


def _is_commit(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", value) is not None


def read(path: Path, claim: str) -> dict[str, Any] | None:
    """The record at `path` if it is one for this claim; None otherwise."""

    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(record, dict) or record.get("version") != 1 or record.get("claim") != claim:
        return None
    dirty = record.get("dirty")
    ok = (
        isinstance(record.get("argv"), list)
        and isinstance(record.get("paths"), list)
        and isinstance(record.get("cwd"), str)
        and (record.get("head") is None or _is_commit(record.get("head")))
        and (
            dirty is None
            or (
                isinstance(dirty, list)
                and all(isinstance(i, dict) and {"path", "digest"} <= set(i) for i in dirty)
            )
        )
    )
    return record if ok else None


def _covers(declared: str, changed: str) -> bool:
    return declared == "" or changed == declared or changed.startswith(declared + "/")


def _same(recorded: str | None, now_digest: str) -> bool:
    """Equal content; an unreadable path (a nested repository, say) is never known equal."""

    return recorded == now_digest and now_digest != UNREADABLE


def _since(record: dict[str, Any], cwd: Path, skip: Path) -> tuple[set[str], str | None]:
    """Every path whose content differs from what the record's claim started with:
    (paths, the reason they cannot be read)."""

    head, was = record.get("head"), record.get("dirty")
    if head is None or was is None:
        return set(), "the record holds no Git state (not a Git work tree when it ran)"
    found = _toplevel(cwd)
    current = capture(cwd, skip)
    if found is None or current.head is None or current.dirty is None:
        return set(), "no Git state to compare with now"
    root = found[0]
    try:
        committed = _names(
            root, "diff-tree", "-r", "--name-only", "-z", "--no-renames", head, "HEAD", "--"
        )
    except (size.SizeError, OSError) as error:
        return set(), f"cannot compare with the recorded commit {head[:12]}: {error}"
    before = {item["path"]: item["digest"] for item in was}
    after = current.dirty
    changed = set()
    for path in committed | before.keys() | after.keys():
        if path in after:
            differs = not _same(before.get(path), after[path])
        elif path in before:
            differs = not _same(before[path], _digest(root / path))
        else:  # clean when the claim started, in a commit since
            differs = True
        if differs:
            changed.add(path)
    return changed, None


def _link_in(cwd: Path, declared: str) -> bool:
    """Whether a declared path, or a folder above it below `cwd`, is a link."""

    here = cwd
    for part in declared.split("/"):
        if part in ("", "."):
            continue
        here = here / part
        if here.is_symlink():
            return True
    return False


def _names_nothing(root: Path, repo_path: str) -> bool:
    found = _names(
        root, "ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", repo_path or "."
    )
    return not found


def assess(
    record: dict[str, Any] | None,
    *,
    claim_digest: str,
    plan_digest: str,
    cwd: Path,
    paths: Sequence[str],
    skip: Path,
) -> tuple[str, str]:
    """`(state, text)` for one claim: CURRENT, CHANGED or UNVERIFIED, and the line that says why.

    The text starts with the last result. Nothing here makes a verdict: the reader judges.
    """

    if record is None:
        return UNVERIFIED, "no result kept for this claim"
    exit_code = record.get("exit_code")
    last = (
        f"last {record.get('verdict')} (exit {'none' if exit_code is None else exit_code}) "
        f"ended {record.get('ended')} at {(record.get('head') or 'no commit')[:12]}"
    )
    if record.get("claim_digest") != claim_digest:
        return (
            UNVERIFIED,
            f"{last}; the claim's command, directory or contract differ from the record's",
        )
    changed, reason = _since(record, cwd, skip)
    if reason is not None:
        return UNVERIFIED, f"{last}; {reason}"
    found = _toplevel(cwd)
    prefix = found[1] if found else ""
    if not paths:
        return (
            UNVERIFIED,
            f"{last}; declares no paths, so nothing says which change matters; "
            f"{len(changed)} file(s) changed since",
        )
    declared = [posixpath.normpath(posixpath.join(prefix, p.replace("\\", "/"))) for p in paths]
    declared = ["" if d == "." else d for d in declared]
    for raw, repo_path in zip(paths, declared, strict=True):
        if _link_in(cwd, raw.replace("\\", "/")):
            return UNVERIFIED, f"{last}; declared path {raw} is a link: declare its target"
        if found is not None and _names_nothing(found[0], repo_path):
            return UNVERIFIED, f"{last}; declared path {raw} names nothing Git reads"
    hit = sorted(c for c in changed if any(_covers(d, c) for d in declared))
    note = (
        ""
        if record.get("plan_digest") == plan_digest
        else " (the plan file differs from the run's)"
    )
    if hit:
        return CHANGED, f"{last}; declared path(s) changed since: {', '.join(hit)}{note}"
    return (
        CURRENT,
        f"{last}; no declared path changed since ({len(changed)} other file(s) did){note}",
    )
