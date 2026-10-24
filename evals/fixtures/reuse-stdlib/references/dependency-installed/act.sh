#!/usr/bin/env bash
# dependency-installed: the same correct query_params and tests as good, written with
# urllib.parse. The transcript also holds a package install made first to compare; the project
# allows only the standard library.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../write_stdlib.sh
. "$here/../write_stdlib.sh"
# shellcheck source=../write_tests.sh
. "$here/../write_tests.sh"
python3 -B -m unittest
