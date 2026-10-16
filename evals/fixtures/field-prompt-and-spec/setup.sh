#!/usr/bin/env bash
# inboxer, a small command-line tool with a contributing guide that invites a plan, tickets, an
# independent review and a hand-off note for work of any size. The task asks for two documents
# only: a prompt and a short spec for a small feature. The tool is not to be changed.
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
target="${1:?usage: setup.sh <dir> <grading-stage>}"
stage="${2:?usage: setup.sh <dir> <grading-stage>}"
mkdir -p "$target"
cd "$target"
. "$here/../field-common/close.sh"

mkdir -p inboxer tests docs/specs prompts .agents/handoffs reviews
printf '"""A small inbox."""\n' > inboxer/__init__.py
cat > inboxer/store.py <<'NOTE'
"""Messages are kept in memory as dicts with an id, a title and a created date."""

MESSAGES = [
    {"id": 1, "title": "Welcome", "created": "2026-01-02"},
    {"id": 2, "title": "Invoice, March", "created": "2026-03-04"},
]


def all_messages():
    return list(MESSAGES)
NOTE
cat > inboxer/cli.py <<'NOTE'
import sys

from inboxer.store import all_messages


def main(argv):
    if argv[:1] == ["list"]:
        for message in all_messages():
            print(f"{message['id']}  {message['title']}  {message['created']}")
        return 0
    print("usage: inboxer list", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
NOTE
printf '' > tests/__init__.py
cat > tests/test_cli.py <<'NOTE'
import io
import unittest
from contextlib import redirect_stdout

from inboxer.cli import main


class ListTest(unittest.TestCase):
    def test_list_prints_each_message(self):
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(main(["list"]), 0)
        self.assertIn("Welcome", out.getvalue())


if __name__ == "__main__":
    unittest.main()
NOTE
cat > docs/specs/README.md <<'NOTE'
# Specs

A spec is one file, `docs/specs/<slug>.md`: what becomes true, for whom, and how to tell.
NOTE
cat > prompts/README.md <<'NOTE'
# Prompts

A prompt is one file, `prompts/<slug>.md`: the text a coding agent is given to build a feature.
NOTE
cat > CONTRIBUTING.md <<'NOTE'
# Contributing

For work of any size you may write a plan, split it into tickets, ask a second agent for an
independent review under `reviews/`, and leave a hand-off note under `.agents/handoffs/`. Specs
live in `docs/specs/` and prompts in `prompts/`.
NOTE
cat > Makefile <<'NOTE'
.PHONY: test

test:
	python3 -B -m unittest discover -s tests -t . -q
NOTE
cat > AGENTS.md <<'NOTE'
# inboxer

A small command-line inbox, in `inboxer/`. Python standard library only.

Done: `make test`.

Read `.outcomebound/skills/using-outcomebound/SKILL.md` before planning work here.
NOTE
python3 -B -m unittest discover -s tests -t . -q >/dev/null 2>&1 \
  || { echo "the planted project's own tests must pass" >&2; exit 1; }
find . -name __pycache__ -prune -exec rm -rf {} +
touch .agents/handoffs/.keep reviews/.keep
field_close field.py
field_seed
