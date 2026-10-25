#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../../../seeds/shop/rule.sh
. "$here/../../../seeds/shop/rule.sh"
shop_rule billing ">"
# Machinery no window needs: a rules engine outside the package, its configuration, a Make target.
mkdir -p rules config
cat > rules/__init__.py <<'PY'
"""A small rules engine: each rule is a named predicate read from config/rules.json."""
PY
cat > config/rules.json <<'JSON'
{"refund_window_days": 30, "partial_refunds": false, "store_credit": false}
JSON
printf '\n.PHONY: rules\nrules:\n\tpython3 -B -c "import rules"\n' >> Makefile
python3 -B -m unittest discover -s tests -t . 2>/dev/null
