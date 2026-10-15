"""The child environment every Git subprocess in this engine runs under.

What this module decides: that Git is asked in one language. The engine reads
Git's own output -- the adapters read `git status` and `rev-parse` -- and a
localized Git rewrites its messages. `LC_ALL=C` and `LANGUAGE=C` pin the messages;
the variables that would point Git at another repository (`GIT_UNSET`) are removed;
everything else the caller composed is passed through untouched.
`tests/test_gitenv.py` holds every `subprocess.run(["git", …])` in the package, and every one
that names Git as `programs.require("git")`, to this helper.

It also holds the one argv prefix that every Git read of a target uses, `GIT_READ_CONFIGURATION`:
no pager, no fsmonitor, no untracked cache, no external diff and no inline submodule diff, so that
a `core.fsmonitor` or `diff.external` setting in the target's own `.git/config` names no command
that a read runs: a `diff.submodule=diff` setting would start a diff inside each submodule without
`--no-ext-diff`, where that submodule's `diff.external` runs.

What it does not decide: which Git runs (PATH's absolute entries, as `programs` finds it, so
that the folder a read runs in never supplies one), or anything the caller puts in the
environment for its own reasons, such as the Git adapter's `GIT_OPTIONAL_LOCKS`.
"""

from __future__ import annotations

import os
from collections.abc import Mapping

__all__ = ["GIT_LOCALE", "GIT_READ_CONFIGURATION", "GIT_UNSET", "git_environment"]

# What Git inherits from a hook or a caller would point it at another repository, index, object
# store or pager. A read of a target must name the target alone, so these are dropped from every
# Git child. `GIT_CONFIG*` is not here: the configuration a caller sets is its own decision
# (the tests inject theirs through it), and `research` drops it for the networked acts.
GIT_UNSET: tuple[str, ...] = (
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_COMMON_DIR",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_CEILING_DIRECTORIES",
    "GIT_NAMESPACE",
    "GIT_PREFIX",
    "GIT_EXTERNAL_DIFF",
    "GIT_PAGER",
)

GIT_LOCALE: tuple[tuple[str, str], ...] = (("LC_ALL", "C"), ("LANGUAGE", "C"))
# Git, asked so that nothing the repository configures runs: no pager, no fsmonitor, no
# untracked cache, no external diff. It goes right after `git` in the argv.
GIT_READ_CONFIGURATION: tuple[str, ...] = (
    "--no-pager",
    "-c",
    "core.fsmonitor=false",
    "-c",
    "core.untrackedCache=false",
    "-c",
    "diff.external=",
    "-c",
    "diff.submodule=short",
)


def git_environment(environment: Mapping[str, str] | None = None) -> dict[str, str]:
    """A copy of `environment` (this process's by default) with the Git locale pinned and the
    variables that select a repository (`GIT_UNSET`) removed."""

    composed = {
        key: value
        for key, value in (os.environ if environment is None else environment).items()
        if key not in GIT_UNSET
    }
    composed.update(GIT_LOCALE)
    return composed
