#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../../../seeds/shop/rule.sh
. "$here/../../../seeds/shop/rule.sh"
shop_rule billing ">"
# Machinery no window needs: a rules engine outside the package, its configuration, a Make target.
mkdir -p rules config
printf '"""A small rules engine: each rule is a named predicate from config/rules.json."""\n' \
  > rules/__init__.py
printf '{"refund_window_days": 30}\n' > config/rules.json
printf '\n.PHONY: rules\nrules:\n\tpython3 -B -c "import rules"\n' >> Makefile
python3 -B -m unittest discover -s tests -t . 2>/dev/null
