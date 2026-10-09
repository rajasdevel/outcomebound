#!/usr/bin/env bash
# The no-work control for the onboarding pair. A workspace that holds one existing project,
# `target/project/`, a small word counter with no onboarding signal: no generated file, no
# migrations, no secret in its CI workflow, no runtime version file. Its Makefile `test` target
# works offline with the Python standard library, its CI workflow runs that target, and it has a
# short note of its own and no OutcomeBound install. The task is the same as in the signals
# fixture: set OutcomeBound up in it.
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
target="${1:?usage: setup.sh <dir>}"
mkdir -p "$target"
cd "$target"

mkdir -p target/project
cd target/project
mkdir -p .github/workflows src/wordtally tests

cat > .github/workflows/ci.yml <<'NOTE'
name: ci
on:
  push:
  pull_request:
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run tests
        run: make test
NOTE

cat > README.md <<'NOTE'
# wordtally

A small command-line word counter. It reads text and prints how often each word occurs.

Run the tests with `make test`.
NOTE

cat > AGENTS.md <<'NOTE'
# wordtally

Keep the code in `src/wordtally/` free of third-party imports: the tests run with the Python
standard library only.
NOTE

cat > Makefile <<'NOTE'
.PHONY: test

test:
	python3 -m unittest discover -s tests -t . -q
NOTE

printf '__pycache__/\n' > .gitignore

printf '"""A small word counter."""\n' > src/wordtally/__init__.py

cat > src/wordtally/counter.py <<'NOTE'
"""Count the words of a text."""

import re
from collections import Counter

WORD = re.compile(r"[a-z0-9']+")


def count_words(text):
    return Counter(WORD.findall(text.lower()))


def most_common(text, limit=10):
    return count_words(text).most_common(limit)
NOTE

touch tests/__init__.py

cat > tests/test_counter.py <<'NOTE'
import unittest

from src.wordtally import counter


class CounterTest(unittest.TestCase):
    def test_counts_ignore_case(self):
        self.assertEqual(counter.count_words("The the THE cat")["the"], 3)

    def test_most_common_is_limited(self):
        self.assertEqual(counter.most_common("a a b c", limit=1), [("a", 2)])


if __name__ == "__main__":
    unittest.main()
NOTE

cd ../..
python3 -B -m unittest discover -s target/project/tests -t target/project -q >/dev/null 2>&1 \
  || { echo "the planted project's own tests must pass" >&2; exit 1; }
find target/project -name __pycache__ -prune -exec rm -rf {} +

. "$here/../onboard-common/close.sh"
