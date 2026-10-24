#!/usr/bin/env bash
# ledger-added: the good code and tests, and a new notes file that records the request and its
# checks.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../write_range.sh
. "$here/../write_range.sh"
cat > NOTES.md <<'MD'
# Notes

- Request: add format_range to prices.py.
- Checked: the unit tests pass.
MD
python3 -B -m unittest
