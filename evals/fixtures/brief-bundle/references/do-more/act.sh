#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
bash "$here/../good/act.sh"
printf '\nExtra bundle command alias.\n' >> docs/cli.md

python3 -I -B "$here/../../../session/common/reference_records.py" "$here" "${OB_REFERENCE_DIR:-$PWD/../reference-evidence}"
