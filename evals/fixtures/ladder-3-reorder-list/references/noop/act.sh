#!/usr/bin/env bash
# noop: the command line read, nothing changed.
set -euo pipefail
python3 -B -m stockroom --help >/dev/null
