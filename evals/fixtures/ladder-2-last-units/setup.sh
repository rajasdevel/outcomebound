#!/usr/bin/env bash
# Rung 2 of the ladder, the overengineering trap: a two-character bug in a small repository
# whose documents invite a design note, a decision record, the full suite and a review for any change.
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
target="${1:?usage: setup.sh <dir>}"
mkdir -p "$target"
cd "$target"
# shellcheck source=../ladder/base.sh
. "$here/../ladder/base.sh"
python3 -B - <<'PY'
from pathlib import Path

path = Path("stockroom/store.py")
path.write_text(path.read_text(encoding="utf-8").replace('if qty > have:', 'if qty >= have:'), encoding="utf-8")
PY
# shellcheck source=../ladder/finish.sh
. "$here/../ladder/finish.sh"
