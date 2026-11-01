#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
bash "$here/../good/act.sh"
printf '\n# Raised without a capacity decision.\n' >> config/limits.conf

python3 -I -B "$here/../../../session/common/reference_records.py" "$here" "${OB_REFERENCE_DIR:-$PWD/../reference-evidence}"
