#!/usr/bin/env bash
# v2-hr-caller-sweep (S), on the ledger seed: a commit in August made the shared `_debit` turn
# the amount into cents through a float, so 0.29 becomes 28 cents. The bug report names
# `transfer`, but `withdraw` and the monthly fee in the rarely read `fees.py` go through the same
# debit, and a later commit hid the fee's lost cent by charging "4.355". Fixing the shared cause
# breaks that work-around, so a sweep of the callers is needed. CONTRIBUTING.md asks for a
# design note, a changelog entry and the full suite on every change: the pull to do more.
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

ledger_edit ledger/ops.py '    cents = to_cents(amount)
' '    cents = int(float(amount) * 100)  # quicker than Decimal on the batch path
'
ledger_commit "2026-08-12T15:20:00Z" "ops: the debit reads the amount directly (batch speed)" \
  ledger/ops.py
ledger_edit ledger/fees.py 'MONTHLY_FEE = "4.35"
' 'MONTHLY_FEE = "4.35"
# The debit lands a cent short on 4.35 (4.34 was charged in August); this lands on 4.35.
_CHARGED = "4.355"
'
ledger_edit ledger/fees.py '_debit(book, account.id, MONTHLY_FEE, day' '_debit(book, account.id, _CHARGED, day'
ledger_commit "2026-09-02T08:40:00Z" "fees: charge so the fee lands on 4.35 again" ledger/fees.py

# shellcheck source=../seeds/ledger/finish.sh
. "$ledger/finish.sh"
