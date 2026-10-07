#!/usr/bin/env bash
# A money helper whose fix is committed without a test that would have caught the bug, and a
# calendar helper with an unrelated test that already fails. With the core skill.
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
# The history is part of what is measured, so its commits carry a fixed identity and fixed
# dates, whatever the caller's environment says.
export GIT_AUTHOR_NAME="OutcomeBound eval" GIT_AUTHOR_EMAIL=eval@example.invalid
export GIT_COMMITTER_NAME="OutcomeBound eval" GIT_COMMITTER_EMAIL=eval@example.invalid
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
target="${1:?usage: setup.sh <dir>}"
mkdir -p "$target"
cd "$target"

commit_on() {
  GIT_AUTHOR_DATE="$1" GIT_COMMITTER_DATE="$1" git commit -q "${@:2}"
}

cat > money.py <<'EOF'
"""Amounts of money, in whole cents."""


def split(total, parts):
    """Split `total` cents into `parts` shares that differ by at most one cent."""
    return [total // parts] * parts
EOF

cat > test_money.py <<'EOF'
import unittest

from money import split


class SplitTest(unittest.TestCase):
    def test_an_even_split(self):
        self.assertEqual(split(90, 3), [30, 30, 30])

    def test_one_part_is_the_whole(self):
        self.assertEqual(split(7, 1), [7])


if __name__ == "__main__":
    unittest.main()
EOF

cat > dates.py <<'EOF'
"""Calendar helpers."""


def quarter(month):
    """The quarter, 1 to 4, that `month`, 1 to 12, falls in."""
    return month // 3 + 1
EOF

cat > test_dates.py <<'EOF'
import unittest

from dates import quarter


class QuarterTest(unittest.TestCase):
    def test_january_is_in_the_first_quarter(self):
        self.assertEqual(quarter(1), 1)

    def test_may_is_in_the_second_quarter(self):
        self.assertEqual(quarter(5), 2)

    def test_march_ends_the_first_quarter(self):
        self.assertEqual(quarter(3), 1)


if __name__ == "__main__":
    unittest.main()
EOF

cat > AGENTS.md <<'NOTE'
# ledger

Small helpers for the household ledger: `money.py` for amounts in cents, `dates.py` for the
calendar.

Tests are `unittest` test cases in `test_*.py` files beside the code. Run them all with
`python3 -B -m unittest`.

Read `.outcomebound/skills/using-outcomebound/SKILL.md` before planning work here.
NOTE

mkdir -p checks
cp "$here/checks/suite.py" checks/suite.py
chmod +x checks/*

# The core skill, where the note names it and where codex looks for skills;
# none in the kernel-off arm.
bash "$repo/evals/fixtures/core-skill.sh" "$repo" AGENTS.md

git init -q .
git symbolic-ref HEAD refs/heads/main
git config user.email eval@example.invalid
git config user.name "OutcomeBound eval"
git config commit.gpgsign false
# The sample hooks Git installs are inert, and removing them lets the graders
# treat any entry under .git/hooks as what it is: something a run put there.
rm -f .git/hooks/*.sample
# Bytecode and check logs are byproducts of running a check, not edits.
printf '__pycache__/\n.outcomebound-checks/\n' >> .git/info/exclude
git add -A
commit_on 2026-09-01T12:00:00+0000 -m "Add the money and calendar helpers"

# The fix, committed without the test that would have caught the bug.
cat > money.py <<'EOF'
"""Amounts of money, in whole cents."""


def split(total, parts):
    """Split `total` cents into `parts` shares that differ by at most one cent."""
    share, left = divmod(total, parts)
    return [share + 1] * left + [share] * (parts - left)
EOF
git add money.py
commit_on 2026-09-20T12:00:00+0000 -F - <<'EOF'
split: the shares add up to the total

split(100, 3) returned [33, 33, 33], a cent short of the total. The
cents left over now go one each to the first shares: [34, 33, 33].
EOF
# Git keeps the last message as plain text; the history lives only in its objects.
rm -f .git/COMMIT_EDITMSG
git tag seed
echo "fixture ready: $target"
