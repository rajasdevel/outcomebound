"""A harness root the project already owns.

What this module decides: whether a harness's native skill directory --
`.agents/skills/`, `.claude/skills/` -- is already the project's own: tracked by
its Git repository and holding skills that carry no OutcomeBound name. A native
copy installed there enters whatever the project does with that directory
(mirrors, bundles, tests it keeps), which the engine cannot know. Discovery
reports the observation; `--harness` is explicit consent, so nothing here
refuses.

What it does not decide: whether to install there (the operator's `--harness`
does), or what the project's mirror policy is. Nothing here writes.
"""

from __future__ import annotations

import subprocess
from collections.abc import Iterable
from pathlib import Path

from outcomebound_tools.gitenv import git_environment

__all__ = ["ENGINE_NAME", "ProjectSkillRoot", "project_skill_roots"]

ENGINE_NAME = "outcomebound"


class ProjectSkillRoot(dict):  # type: ignore[type-arg]
    """`{path, tracked, skills}`: a dict, so discovery serializes it as it is."""


def _tracked(target: Path, relative: str) -> bool:
    """Whether Git tracks anything under the directory; no Git is no evidence."""

    try:
        listed = subprocess.run(
            ["git", "-C", str(target), "ls-files", "--", relative],
            capture_output=True,
            text=True,
            check=False,
            env=git_environment(),
        )
    except OSError:
        return False
    return listed.returncode == 0 and bool(listed.stdout.strip())


def _project_skills(target: Path, relative: str) -> list[str]:
    root = target / relative
    if root.is_symlink() or not root.is_dir():
        return []
    try:
        entries = sorted(entry.name for entry in root.iterdir() if entry.is_dir())
    except OSError:
        return []
    return [name for name in entries if ENGINE_NAME not in name.lower()]


def project_skill_roots(target: Path | str, skill_dirs: Iterable[str]) -> list[ProjectSkillRoot]:
    """Each native skill directory the project tracks and fills with skills of its own."""

    root = Path(target)
    found: list[ProjectSkillRoot] = []
    for relative in dict.fromkeys(directory.rstrip("/") for directory in skill_dirs):
        skills = _project_skills(root, relative)
        if not skills or not _tracked(root, relative):
            continue
        found.append(ProjectSkillRoot(path=relative, tracked=True, skills=skills))
    return found
