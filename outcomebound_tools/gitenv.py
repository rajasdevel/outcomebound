"""The child environment every Git subprocess in this engine runs under.

What this module decides: that Git is asked in one language. The engine reads
Git's own output -- the adapters read `git status` and `rev-parse` -- and a
localized Git rewrites its messages. `LC_ALL=C` and `LANGUAGE=C` pin the messages;
everything else the caller composed is passed through untouched.
`tests/test_gitenv.py` holds every `subprocess.run(["git", …])` in the package
to this helper.

What it does not decide: which Git runs (PATH resolves it, as every adapter
here resolves it), or anything the caller puts in the environment for its own
reasons, such as the Git adapter's `GIT_OPTIONAL_LOCKS`.
"""

from __future__ import annotations

import os
from collections.abc import Mapping

__all__ = ["GIT_LOCALE", "git_environment"]

GIT_LOCALE: tuple[tuple[str, str], ...] = (("LC_ALL", "C"), ("LANGUAGE", "C"))


def git_environment(environment: Mapping[str, str] | None = None) -> dict[str, str]:
    """A copy of `environment` (this process's by default) with the Git locale pinned."""

    composed = dict(os.environ if environment is None else environment)
    composed.update(GIT_LOCALE)
    return composed
