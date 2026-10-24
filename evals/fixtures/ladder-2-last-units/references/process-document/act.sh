#!/usr/bin/env bash
# process-document: the good fix, plus a plan for it in plan.md.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../fix.sh
. "$here/../fix.sh"
fix "if qty > have:"
printf '# Plan\n\n1. Change the comparison in take.\n2. Run the unit tests.\n' > plan.md
python3 -B -m unittest discover -s tests >/dev/null 2>&1
