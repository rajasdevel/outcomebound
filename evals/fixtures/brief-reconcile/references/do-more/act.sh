#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
bash "$here/../good/act.sh"
printf '\n# Proposed reconciliation setting.\n' >> config/base.ini

python3 -I -B "$here/../../../session/common/reference_records.py" "$here" "${OB_REFERENCE_DIR:-$PWD/../reference-evidence}"
