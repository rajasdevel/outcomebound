#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# The working page, a long run of notes, then a footer with a recommendation and a question.
python3 -B "$here/../page.py" --footer
