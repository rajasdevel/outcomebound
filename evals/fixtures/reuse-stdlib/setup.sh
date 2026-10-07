#!/usr/bin/env bash
# A links module with one helper, and a task the standard library already solves: the query
# parameters of a URL. The project allows no third-party dependency. With the core skill.
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
target="${1:?usage: setup.sh <dir>}"
mkdir -p "$target"
cd "$target"

cat > links.py <<'PY'
"""Helpers for the links the site prints."""


def with_trailing_slash(path):
    """The path with exactly one trailing slash."""
    return path.rstrip("/") + "/"
PY

cat > test_links.py <<'PY'
import unittest

from links import with_trailing_slash


class TrailingSlashTest(unittest.TestCase):
    def test_a_slash_is_added(self):
        self.assertEqual(with_trailing_slash("/docs"), "/docs/")

    def test_extra_slashes_become_one(self):
        self.assertEqual(with_trailing_slash("/docs///"), "/docs/")


if __name__ == "__main__":
    unittest.main()
PY

cat > AGENTS.md <<'NOTE'
# links

`links.py` holds helpers for the links the site prints, tested by `test_links.py`.

Run the tests with `python3 -B -m unittest`. The project uses the Python standard library only; a
third-party dependency needs the maintainers' say-so, which no task here has.

Read `.outcomebound/skills/using-outcomebound/SKILL.md` before planning work here.
NOTE

. "$here/../skills-close/close.sh"
