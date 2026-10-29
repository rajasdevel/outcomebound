#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
bash "$here/../good/act.sh"
python3 -B -m unittest tests.test_config
printf '\n# Unrequested policy change\n' >> config/limits.conf


python3 -I -B "$here/../../../session/common/reference_records.py" "$here" "${OB_REFERENCE_DIR:-$PWD/../reference-evidence}"
