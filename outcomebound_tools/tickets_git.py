"""Every git command the ticket engine runs.

What this module decides: how git is invoked — an argv list with no shell, the
target as the working directory, the engine's pinned environment, both streams
captured as bytes — and the two questions `brief` asks of a checkout: which
commit `HEAD` names, and whether the tree is clean. `git` returns a non-zero
status rather than raising, and each question raises `GitError` where git could
not answer it.

What it does not decide: what any output means beyond those questions, which
refusal a failure becomes, or what git's messages say, which a locale or a
version can change.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from outcomebound_tools.gitenv import git_environment
from outcomebound_tools.tickets_report import EngineError

__all__ = [
    "GitError",
    "GitResult",
    "git",
    "head_commit",
    "tree_clean",
]


class GitError(EngineError):
    """Git could not be asked, or could not answer: the message names the checkout."""


@dataclass(frozen=True, slots=True)
class GitResult:
    """One finished git command: its status and both streams, as bytes."""

    status: int
    stdout: bytes
    stderr: bytes

    @property
    def text(self) -> str:
        """Standard output as UTF-8. A byte that is not decodes to a replacement
        character rather than raising: a path or a blob the repository holds is
        not always UTF-8, and no question here is worth failing over an encoding."""

        return self.stdout.decode("utf-8", "replace")

    @property
    def message(self) -> str:
        """Standard error as UTF-8, for an error this engine raises."""

        return self.stderr.decode("utf-8", "replace").strip()


def git(target: Path | str, *arguments: str) -> GitResult:
    """Run one git command in `target` and return what it did."""

    try:
        # A fixed argv list with shell=False, built from this engine's own
        # constants and the caller's refs and paths; `git` is resolved from
        # PATH, as every adapter in this engine resolves it.
        completed = subprocess.run(
            ["git", *arguments],
            cwd=target,
            capture_output=True,
            check=False,
            env=git_environment(),
        )
    except OSError as error:
        raise GitError(f"could not run git in {target}: {error}") from error
    return GitResult(completed.returncode, completed.stdout, completed.stderr)


def head_commit(target: Path | str) -> str:
    """The commit `HEAD` names.

    Outside a repository, and inside one before its first commit, there is no
    commit to name and this raises: both are conditions a verb reports rather
    than works around.
    """

    outcome = git(target, "rev-parse", "--verify", "HEAD")
    if outcome.status != 0:
        raise GitError(
            f"no commit could be read in {target}: `git rev-parse --verify HEAD` exited "
            f"{outcome.status}: {outcome.message or 'no message'}"
        )
    return outcome.text.strip()


def tree_clean(target: Path | str) -> bool:
    """Whether the working tree holds nothing uncommitted, untracked files included."""

    outcome = git(target, "status", "--porcelain")
    if outcome.status != 0:
        raise GitError(
            f"could not read the working tree of {target}: `git status --porcelain` exited "
            f"{outcome.status}: {outcome.message or 'no message'}"
        )
    return not outcome.stdout.strip()
