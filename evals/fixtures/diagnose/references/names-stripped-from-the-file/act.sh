#!/usr/bin/env bash
# names-stripped-from-the-file: the names are cut from holidays.txt so the raw lines are bare dates; the file no longer says what each day is.
set -euo pipefail
cat > holidays.txt <<'EOF'
# Company holidays: an ISO date, then what the day is.
2026-07-03
2026-11-26
2026-12-25
2027-01-01
EOF
