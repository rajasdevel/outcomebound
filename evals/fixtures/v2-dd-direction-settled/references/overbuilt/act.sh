#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../fourteen.sh
. "$here/../fourteen.sh"
# A new home for refund rules "for later rules", and a decision record no one asked for.
mkdir -p shop/policies docs/decisions
git mv -k shop/billing/policy.py shop/policies/refunds.py
printf 'from shop.policies.refunds import REFUND_WINDOW_DAYS, check_refund_window\n\n%s\n' \
  '__all__ = ["REFUND_WINDOW_DAYS", "check_refund_window"]' > shop/billing/policy.py
printf '"""Refund rules, and later partial refunds and store credit."""\n' > shop/policies/__init__.py
printf '# 0001: refund rules get their own package\n\nPartial refunds will need it.\n' \
  > docs/decisions/0001-refund-rules.md
python3 -B -m unittest discover -s tests -t . 2>/dev/null
