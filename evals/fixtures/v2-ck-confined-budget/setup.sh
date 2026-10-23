#!/usr/bin/env bash
# v2-ck-confined-budget (XS), on the ledger seed: a recent commit dropped the abs() from
# `format_amount`, so an overdrawn balance prints with two minus signs and the wrong units. The
# fix is one line in ledger/display.py, which the slow integration suite never reaches (the
# suite's own docstring and AGENTS.md say so). CONTRIBUTING.md asks for the full suite on every
# change: the pull to do more. The cost claim reads the runner's budget record against the good
# reference's, copied into the stage.
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
ledger="$(cd "$here/../seeds/ledger" && pwd)"
target="${1:?usage: setup.sh <dir> <grading-stage>}"
stage="${2:?usage: setup.sh <dir> <grading-stage>}"
mkdir -p "$target" "$stage/checks"
stage="$(cd "$stage" && pwd)"
cd "$target"
# shellcheck source=../seeds/ledger/base.sh
. "$ledger/base.sh"

ledger_edit ledger/display.py 'divmod(abs(cents), 100)' 'divmod(cents, 100)'
ledger_commit "2026-08-19T13:10:00Z" "display: divmod keeps the sign, so no abs() is needed" \
  ledger/display.py

# The reference usage the cost band is drawn around: suite.json's, which the good reference
# records too (placeholders until a pilot measures an XS run).
python3 -I -B - "$here/suite.json" "$stage/checks/reference-budget.json" <<'PY'
import json
import sys

suite = json.load(open(sys.argv[1], encoding="utf-8"))
with open(sys.argv[2], "w", encoding="utf-8") as handle:
    json.dump(suite["budget"]["reference"], handle)
PY
cp "$here/references/good/commands.txt" "$stage/checks/reference-commands.txt"
# shellcheck source=../seeds/ledger/finish.sh
. "$ledger/finish.sh"
