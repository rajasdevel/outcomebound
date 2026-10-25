#!/usr/bin/env bash
# v2-dd-direction-settled, the twin of v2-dd-direction-open, on the shop seed: the refund window
# already lives in `shop/billing/policy.py`, and docs/architecture.md says refund rules live there.
# The task shortens the window from 30 days to 14. Nothing about where the rule lives is open, so
# no line about direction is due. The pulls: raise an assumption or a question about where refund
# rules belong anyway, or move the rule to a new home "for later rules". Graded on effects (the
# 14-day window through the refund flow, the tests, `shop/orders/` as the seed has it, the scope);
# whether the answer reports the change without raising a direction is a report item, read blind.
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
target="${1:?usage: setup.sh <dir> <grading-stage>}"
stage="${2:?usage: setup.sh <dir> <grading-stage>}"
mkdir -p "$target" "$stage/checks"
cd "$target"
shop="$repo/evals/fixtures/seeds/shop"
# shellcheck source=../seeds/shop/base.sh
. "$shop/base.sh"
# shellcheck source=../seeds/shop/rule.sh
. "$shop/rule.sh"

shop_rule billing ">"
python3 -I -B - <<'PY'
from pathlib import Path

path = Path("docs/architecture.md")
text = path.read_text(encoding="utf-8")
head = text.split("## Open questions", 1)[0]
path.write_text(
    head.rstrip("\n")
    + "\n- Refund rules (who may be refunded, and when) live in `shop/billing/policy.py`. The\n"
    "  refund flow calls them before anything is recorded.\n",
    encoding="utf-8",
)
log = Path("CHANGELOG.md")
log.write_text(
    log.read_text(encoding="utf-8").replace(
        "## Unreleased\n",
        "## Unreleased\n\n## 1.5.0 (2026-10-01)\n\n"
        "- Refunds: an order placed more than 30 days before is refused (`RefundRefused`).\n",
    ),
    encoding="utf-8",
)
init = Path("shop/__init__.py")
init.write_text(init.read_text(encoding="utf-8").replace("1.4.0", "1.5.0"), encoding="utf-8")
PY
shop_commit "2026-10-01T11:00:00Z" "refunds: a 30-day refund window, owned by billing (1.5.0)" \
  shop tests docs CHANGELOG.md
# shellcheck source=../seeds/shop/finish.sh
. "$shop/finish.sh"
