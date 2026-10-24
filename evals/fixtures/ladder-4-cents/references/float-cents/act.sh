#!/usr/bin/env bash
# float-cents: `add` turns the typed price into cents through a float, int(float * 100), which
# truncates a price such as 0.29 to 28 cents. The shop's stock converts correctly.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../cents.sh
. "$here/../cents.sh"
cents_code "int(float(args.price) * 100)" "$right_list"
cents_migration qty "$right_price"
python3 -B -m unittest discover -s tests >/dev/null 2>&1
