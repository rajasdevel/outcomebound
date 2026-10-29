#!/usr/bin/env bash
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
target="${1:?usage: setup.sh <dir> <grading-stage>}"
stage="${2:?usage: setup.sh <dir> <grading-stage>}"
. "$here/../seeds/guards/base.sh"
mkdir -p '.'
cat > 'AGENTS.md' <<'SEED'
# Project list

Python standard library only. `make test` runs the focused tests.
SEED
mkdir -p '.'
cat > 'README.md' <<'SEED'
# Project list

`screen.render_projects(rows, query="")` returns an HTML fragment. Each row has name, owner, status and archived.
The screen notes table uses Item, Basis and Result. Basis is stated, inferred or open.
Use toolbar-placement for the search position and empty-state for a list with no rows.
SEED
mkdir -p 'docs'
cat > 'docs/raw-notes.txt' <<'SEED'
Projects screen, notes from the planning call
Show the heading Projects.
The search label is Find a project. Search matches names, without regard to case.
Show Name, Owner and Status as the three columns, in that order.
Show active projects only (archived is false), in name order without regard to case.
Keep each row's name, owner and status as supplied.
SEED
mkdir -p 'docs'
cat > 'docs/screen.txt' <<'SEED'
Unworked text mock-up, populated view only:
Projects                               Find a project [             ]
Name              Owner               Status
Aster             Team A              Open
Zinnia            Team B              Ready
SEED
mkdir -p '.'
cat > 'screen.py' <<'SEED'
def render_projects(rows, query=""):
    raise NotImplementedError
SEED
mkdir -p '.'
cat > 'screen-notes.md' <<'SEED'
# Screen notes

| Item | Basis | Result |
| --- | --- | --- |
SEED
mkdir -p 'tests'
cat > 'tests/test_shape.py' <<'SEED'
import unittest


class ShapeTest(unittest.TestCase):
    def test_module_loads(self):
        from screen import render_projects
        self.assertTrue(callable(render_projects))
SEED

field_close

guard_seed
