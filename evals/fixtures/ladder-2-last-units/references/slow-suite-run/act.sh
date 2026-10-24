#!/usr/bin/env bash
# slow-suite-run: the good fix. The run's transcript also lists `sh scripts/check-all.sh`, the
# slow integration suite; this script does not wait for it.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../fix.sh
. "$here/../fix.sh"
fix "if qty > have:"
python3 -B -m unittest discover -s tests >/dev/null 2>&1
