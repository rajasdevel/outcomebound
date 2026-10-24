"""The Git worktrees of a project whose OutcomeBound install is older than the engine, or not
as its manifest or its commit has it.

What this module decides: which worktree `adopt --check` warns of. A worktree on an older branch
carries the older release's block and fragments, so a run that moves between worktrees reads two
releases of the guidance; a worktree whose install is missing on disk, or not as its commit holds
it, is named too, from what the caller's survey reports. The release a worktree has installed is
the `engine_version` of its manifest, else the `v=` of its operating-contract block in
`AGENTS.md`; the other blocks' `v=` is a format number and says nothing. Only files are read,
through `fileplan.current`, which refuses a symlink; nothing is written in any worktree.

What it does not decide: how Git is run (the caller passes the output of
`git worktree list --porcelain`), or the exit code of `--check`, which a warning leaves alone.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from outcomebound_tools import fileplan, identity, textio

__all__ = ["Survey", "Worktree", "describe", "installed", "lines", "parse"]

MANIFEST = ".outcomebound/manifest.json"
HOST = "AGENTS.md"
KERNEL = "operating-contract"
DOTTED = re.compile(r"\d+(\.\d+)*")
# One worktree's install problems beside its version, and whether it is facts-only.
Survey = Callable[[Path], tuple[list[str], bool]]


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


def installed(root: Path) -> str | None:
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


def describe(root: Path, engine: str, survey: Survey | None = None) -> str | None:
    """What a `warn` line says of the install in `root`: none, older than `engine`, a version
    that is not dotted integers, or a problem `survey` names; None where there is nothing to say.
    `survey(root)` gives the problems of the install beside its version, and whether it is
    facts-only, which the text then says."""

    wanted = _key(engine)
    if wanted is None:
        return None
    version = installed(root)
    problems, facts_only = survey(root) if survey is not None else ([], False)
    mode = " (facts-only)" if facts_only else ""
    have = None if version is None else _key(version)
    if version is None:
        head = "no OutcomeBound install"
    elif have is None:
        head = f"installed version {textio.quote(version)} is not readable"
    elif have < wanted:
        head = f"installed {version}{mode}, engine {engine}"
    elif problems:
        head = f"installed {version}{mode}"
    else:
        return None
    return "; ".join([head, *problems])


def lines(
    target: Path,
    porcelain: str,
    engine: str,
    survey: Survey | None = None,
) -> list[str]:
    """One `warn` line for each worktree other than `target` that `describe` has something to
    say of; none otherwise."""

    own = target.resolve()
    found: list[str] = []
    for tree in parse(porcelain):
        if not tree.path.is_dir() or tree.path.resolve() == own:
            continue
        text = describe(tree.path, engine, survey)
        if text is not None:
            branch = textio.visible(tree.branch)
            found.append(f"worktree {textio.visible(str(tree.path))} (branch {branch}): {text}")
    return found


def render(found: Sequence[str]) -> list[str]:
    return [f"{'warn':<8} {line}" for line in found]
