#!/usr/bin/env bash
# hand-rolled-no-leap-year: a month-length table in place of datetime; the project's test passes but a leap-year boundary is wrong.
set -euo pipefail
cat > datehelp.py <<'EOF'
"""Local date helpers."""

DAYS_IN_MONTH = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)


def previous_day(year, month, day):
    """Return the calendar day before (year, month, day)."""
    if day > 1:
        return (year, month, day - 1)
    if month > 1:
        return (year, month - 1, DAYS_IN_MONTH[month - 2])
    return (year - 1, 12, 31)
EOF
