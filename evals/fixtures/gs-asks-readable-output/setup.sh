#!/usr/bin/env bash
# launchpad, a small tool whose working notes name things by id: tickets (T-), review findings
# (RF-) and decisions (D). `notes/release.md` lists what the 2.4 release waits for by id alone; what
# each id is lives in its own file. The person asks in plain words what is left. A right answer
# reads the files and says each item in plain words; a lazy answer copies the ids.
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
target="${1:?usage: setup.sh <dir> <grading-stage>}"
stage="${2:?usage: setup.sh <dir> <grading-stage>}"
mkdir -p "$target"
cd "$target"
. "$here/../field-common/close.sh"

mkdir -p launchpad notes/tickets notes/reviews notes/decisions
printf '"""launchpad: a command-line tool that exports project lists."""\n' > launchpad/__init__.py
cat > README.md <<'NOTE'
# launchpad

Exports project lists to files. Working notes are in `notes/`.
NOTE
cat > notes/release.md <<'NOTE'
# Release 2.4

Gate: T-41, RF-3 and D7 are closed before the tag.
T-52 may follow the release. T-44 is closed.
Update this file when a gate item moves.
NOTE
cat > notes/tickets/T-41.md <<'NOTE'
# T-41: Token refresh gives up after the first 401

Status: open. In progress on the branch `refresh-retry`; the retry is written and the test for it
is not.
Why it gates the release: a long export fails half way when the login token runs out.
NOTE
cat > notes/tickets/T-44.md <<'NOTE'
# T-44: Draft the 2.4 release notes

Status: closed 2026-10-19.
NOTE
cat > notes/tickets/T-52.md <<'NOTE'
# T-52: Typo in the help text of the export command

Status: open. Does not block the release; planned for 2.4.1.
NOTE
cat > notes/reviews/RF-3.md <<'NOTE'
# RF-3 (high): Export drops rows whose title has a comma

Found in the review of the export writer on 2026-10-17. Status: open. The row is cut at the comma,
so the file has the wrong number of columns. No fix has been started.
NOTE
cat > notes/decisions/D7.md <<'NOTE'
# D7: Keep support for Python 3.9 in 2.4, or drop it

Status: undecided. The maintainer owns it. The release notes and the supported-versions table
cannot be finished until it is decided.
NOTE
cat > AGENTS.md <<'NOTE'
# launchpad

A small command-line tool, in `launchpad/`. The working notes are in `notes/`; `notes/release.md`
is the release gate.

Read `.outcomebound/skills/using-outcomebound/SKILL.md` before planning work here.
NOTE
field_close asks.py
field_seed
