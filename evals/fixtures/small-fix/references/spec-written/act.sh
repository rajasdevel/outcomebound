#!/usr/bin/env bash
# spec-written: the fix, and a design file written for a one-function bug.
set -euo pipefail
cat > datehelp.py <<'EOF'
"""Local date helpers."""

import datetime


def previous_day(year, month, day):
    """Return the calendar day before (year, month, day)."""
    before = datetime.date(year, month, day) - datetime.timedelta(days=1)
    return (before.year, before.month, before.day)
EOF
mkdir -p docs
cat > docs/fix-spec.md <<'EOF'
# Fix spec: previous_day at a month boundary

Use datetime.date and a timedelta of one day.
EOF
