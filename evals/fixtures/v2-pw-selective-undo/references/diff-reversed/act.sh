#!/usr/bin/env bash
set -euo pipefail
# The file's whole unstaged diff, reversed: the agent's change and two that are not its own.
git diff -- app/settings.py > .agents/work/undo.patch
git apply -R .agents/work/undo.patch
