#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# The working page, with controls that explore the comparison: a form that submits
# nothing, a checkbox that shows the breakdown, a button that copies the table.
python3 -B "$here/../../references/page.py" --controls
