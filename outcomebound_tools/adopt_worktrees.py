"""The Git worktrees of a project whose installed OutcomeBound is older than the engine.

What this module decides: which worktree `adopt --check` warns of. A worktree on an older branch
carries the older release's block and fragments, so a run that moves between worktrees reads two
releases of the guidance. The release a worktree has installed is the `engine_version` of its
manifest, else the `v=` of its operating-contract block in `AGENTS.md`; the other blocks' `v=` is
a format number and says nothing. Only files are read, through `fileplan.current`, which refuses a
symlink; nothing is written in any worktree.

What it does not decide: how Git is run (the caller passes the output of
`git worktree list --porcelain`), or the exit code of `--check`, which a warning leaves alone.
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from outcomebound_tools import fileplan, identity, textio

__all__ = ["Worktree", "lines", "parse"]

MANIFEST = ".outcomebound/manifest.json"
HOST = "AGENTS.md"
KERNEL = "operating-contract"
DOTTED = re.compile(r"\d+(\.\d+)*")


@dataclass(frozen=True)
class Worktree:
    path: Path
    branch: str


def parse(porcelain: str) -> list[Worktree]:
    """The linked and main worktrees `git worktree list --porcelain` names, bare entries left
    out; the branch is `(detached)` where none is checked out."""

    found: list[Worktree] = []
    for block in porcelain.split("\n\n"):
        path: str | None = None
        branch = "(detached)"
        bare = False
        for line in block.splitlines():
            if line.startswith("worktree "):
                path = line[len("worktree ") :]
            elif line.startswith("branch "):
                branch = line[len("branch ") :].removeprefix("refs/heads/")
            elif line == "bare":
                bare = True
        if path and not bare:
            found.append(Worktree(Path(path), branch))
    return found


def _installed(root: Path) -> str | None:
    """The release `root` records, or None where it has neither a manifest version nor an
    operating-contract block."""

    try:
        raw = fileplan.current(root, MANIFEST)
        document = json.loads(textio.decode(raw)) if raw is not None else None
    except (fileplan.WriteError, OSError, ValueError):
        document = None
    version = document.get("engine_version") if isinstance(document, dict) else None
    if isinstance(version, str):
        return version
    try:
        host = fileplan.current(root, HOST)
        blocks = identity.find_managed_blocks(textio.decode(host)) if host is not None else []
    except (fileplan.WriteError, OSError, ValueError, identity.IdentityError):
        return None
    return next((block.version for block in blocks if block.block_id == KERNEL), None)


def _key(version: str) -> tuple[int, ...] | None:
    if not DOTTED.fullmatch(version):
        return None
    parts = [int(part) for part in version.split(".")]
    while len(parts) > 1 and parts[-1] == 0:
        parts.pop()
    return tuple(parts)


def lines(target: Path, porcelain: str, engine: str) -> list[str]:
    """One `warn` line for each worktree other than `target` whose install is older than
    `engine`, has none, or records a version that is not dotted integers; none otherwise."""

    wanted = _key(engine)
    own = target.resolve()
    found: list[str] = []
    for tree in parse(porcelain):
        if wanted is None or not tree.path.is_dir() or tree.path.resolve() == own:
            continue
        installed = _installed(tree.path)
        where = f"worktree {textio.visible(str(tree.path))} (branch {textio.visible(tree.branch)})"
        if installed is None:
            found.append(f"{where}: no OutcomeBound install")
            continue
        have = _key(installed)
        if have is None:
            found.append(f"{where}: installed version {textio.quote(installed)} is not readable")
        elif have < wanted:
            found.append(f"{where}: installed {installed}, engine {engine}")
    return found


def render(found: Sequence[str]) -> list[str]:
    return [f"{'warn':<8} {line}" for line in found]
