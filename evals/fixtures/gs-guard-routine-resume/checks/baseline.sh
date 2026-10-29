#!/usr/bin/env bash
set -euo pipefail
stage="${1:?grading stage}"
python3 -I -B tools/inventory.py --snapshot > "$stage/checks/resume.json"
