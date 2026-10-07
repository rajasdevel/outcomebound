#!/usr/bin/env bash
# An ordinals module with one helper, and a task that nothing in the standard library, the code
# or the project's dependencies already does. The skill is to add no work: write it. With the
# core skill.
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
target="${1:?usage: setup.sh <dir>}"
mkdir -p "$target"
cd "$target"

cat > ordinals.py <<'PY'
"""Words for numbers the site prints."""


def plural(count, word):
    """`word` as a plural when `count` is not one: `1 file`, `2 files`."""
    return f"{count} {word}" if count == 1 else f"{count} {word}s"
PY

cat > test_ordinals.py <<'PY'
import unittest

from ordinals import plural


class PluralTest(unittest.TestCase):
    def test_one_is_singular(self):
        self.assertEqual(plural(1, "file"), "1 file")

    def test_other_counts_are_plural(self):
        self.assertEqual(plural(0, "file"), "0 files")
        self.assertEqual(plural(3, "file"), "3 files")


if __name__ == "__main__":
    unittest.main()
PY

cat > AGENTS.md <<'NOTE'
# ordinals

`ordinals.py` holds words for numbers the site prints, tested by `test_ordinals.py`.

Run the tests with `python3 -B -m unittest`. The project uses the Python standard library only; a
third-party dependency needs the maintainers' say-so, which no task here has.

Read `.outcomebound/skills/using-outcomebound/SKILL.md` before planning work here.
NOTE

. "$here/../skills-close/close.sh"
