#!/usr/bin/env bash
# The greeting service of the runtime-check fixture and a task that adds a pure helper which the
# service never calls: its unit tests cover it whole. With the core skill and the runtime fragment.
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
target="${1:?usage: setup.sh <dir>}"
mkdir -p "$target"
cd "$target"

. "$here/../runtime-check/project.sh"

cat > textutil.py <<'PY'
"""Text helpers for the tools around the service; the service itself does not use them."""


def shout(text):
    """`text` in capitals with an exclamation mark."""
    return text.upper() + "!"
PY

cat > tests/test_textutil.py <<'PY'
import unittest

from textutil import shout


class ShoutTest(unittest.TestCase):
    def test_capitals_and_a_mark(self):
        self.assertEqual(shout("hi"), "HI!")


if __name__ == "__main__":
    unittest.main()
PY

. "$here/../skills-close/close.sh"
