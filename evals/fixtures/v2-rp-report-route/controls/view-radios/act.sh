#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# The working page, with a group of radio buttons named after the plans that switches a
# detail panel: a view, not a choice.
python3 -B "$here/../../references/page.py" --views
