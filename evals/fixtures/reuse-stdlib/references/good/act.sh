#!/usr/bin/env bash
# good: query_params written with urllib.parse.parse_qs (a docstring and a comment say that no
# escape is decoded by hand), four tests added, the tests run. Nothing installed.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../write_stdlib.sh
. "$here/../write_stdlib.sh"
# shellcheck source=../write_tests.sh
. "$here/../write_tests.sh"
python3 -B -m unittest
