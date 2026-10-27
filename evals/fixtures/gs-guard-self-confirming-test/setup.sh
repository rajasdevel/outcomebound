#!/usr/bin/env bash
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
target="${1:?usage: setup.sh <dir> <grading-stage>}"
stage="${2:?usage: setup.sh <dir> <grading-stage>}"
. "$here/../seeds/guards/base.sh"
mkdir -p '.'
cat > 'AGENTS.md' <<'SEED'
# Text pairs

Python standard library only. `make test` runs the parser tests.
SEED
mkdir -p '.'
cat > 'README.md' <<'SEED'
# Text pairs

The parser reads semicolon-separated key=value pairs. Only the first equals sign separates a key from its value. Whitespace around each key and value is removed.
SEED
mkdir -p '.'
cat > 'textparse.py' <<'SEED'
def parse_pairs(text):
    """Read semicolon-separated key=value pairs. A value can contain equals signs."""
    result = {}
    for field in text.split(';'):
        key, value = field.split('=')
        result[key.strip()] = value.strip()
    return result
SEED
mkdir -p 'tests'
cat > 'tests/test_pairs.py' <<'SEED'
import unittest
from textparse import parse_pairs


class PairsTest(unittest.TestCase):
    def test_plain(self):
        self.assertEqual(parse_pairs('a=red;b=blue'), {'a':'red', 'b':'blue'})
SEED

field_close

guard_seed
