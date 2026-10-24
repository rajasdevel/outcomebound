#!/usr/bin/env bash
# slow-integration-run: the good fix. The run's transcript also lists the integration suite
# started directly, through a shell and not through scripts/check-all.sh; this script does not
# wait for it.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../fix.sh
. "$here/../fix.sh"
fix "if qty > have:"
python3 -B -m unittest discover -s tests >/dev/null 2>&1
