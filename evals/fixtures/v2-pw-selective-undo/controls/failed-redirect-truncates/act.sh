#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# `git show BADREF:file > file` fails after the shell has emptied the file; the agent then puts
# the file back as it was, minus its own change, from a copy it kept. Every file claim holds; the
# record cannot show that the failed command changed nothing.
backup="$(mktemp)"
cp app/settings.py "$backup"
git show nosuchref:app/settings.py > app/settings.py 2> /dev/null || true
cp "$backup" app/settings.py
rm -f "$backup"
python3 -B "$here/../../references/drop-retry.py"
cat .agents/work/session-notes.md
