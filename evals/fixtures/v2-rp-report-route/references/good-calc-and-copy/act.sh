#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# A button outside any form, id calculate, labelled "Calculate and copy table": one click redraws the totals and copies the table.
python3 -B "$here/../page.py" --calc-copy
