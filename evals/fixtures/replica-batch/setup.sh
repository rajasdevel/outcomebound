#!/usr/bin/env bash
# replica-batch, on the datapipe base: three small tickets in one prompt, one commit each. Each
# has its own right-sized check: the scheduler spec (a document: the documentation check), the
# off-by-one in query statistics' top N (unit tests), and refunded orders counted in
# daily_revenue (the transform's unit tests; the slow suite's end-to-end test also fails on it).
# The slow integration suite is there and reaches only the third; running it more than once
# runs it for tickets it does not reach.
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
target="${1:?usage: setup.sh <dir> <grading-stage>}"
stage="${2:?usage: setup.sh <dir> <grading-stage>}"
mkdir -p "$target" "$stage/checks"
cd "$target"
# shellcheck source=../replica/datapipe/base.sh
. "$here/../replica/datapipe/base.sh"

python3 -I -B - <<'PY'
from pathlib import Path

path = Path("docs/specs/scheduler.md")
text = path.read_text(encoding="utf-8")
path.write_text(
    text.replace("retried up to 3 times, 10 minutes apart", "retried up to 5 times, 10 minutes apart"),
    encoding="utf-8",
)
PY
dp_commit "2026-10-09T10:20:00Z" "docs: scheduler spec for the new retry policy" docs/specs/scheduler.md

python3 -I -B - <<'PY'
from pathlib import Path

path = Path("datapipe/querystats.py")
text = path.read_text(encoding="utf-8")
old = "    ranked = sorted(totals, key=lambda t: (-key(t), t.query_id))\n    return ranked[:n]\n"
new = (
    "    chosen: list[QueryTotals] = []\n"
    "    for index, total in enumerate(sorted(totals, key=lambda t: (-key(t), t.query_id))):\n"
    "        if index > n:\n"
    "            break\n"
    "        chosen.append(total)\n"
    "    return chosen\n"
)
assert old in text
path.write_text(text.replace(old, new), encoding="utf-8")
PY
dp_commit "2026-10-13T14:05:00Z" "querystats: rank in one pass" datapipe/querystats.py

python3 -I -B - <<'PY'
from pathlib import Path

path = Path("datapipe/sql/daily_revenue.sql")
text = path.read_text(encoding="utf-8")
old = "WHERE status NOT IN ('cancelled', 'refunded')\n"
assert old in text
path.write_text(text.replace(old, "WHERE status <> 'cancelled'\n"), encoding="utf-8")
PY
dp_commit "2026-10-16T11:30:00Z" "transforms: simpler status filter in daily_revenue" \
  datapipe/sql/daily_revenue.sql
python3 -I -B "$dp_here/envseed.py" seed "$dp_here/scenario-quiet.json" .envs

cat > "$stage/checks/facts.json" <<'JSON'
{
  "tickets": {
    "1-spec": ["docs/*"],
    "2-top": ["datapipe/querystats.py", "datapipe/cli.py", "tests/test_querystats.py", "tests/test_cli.py"],
    "3-refunds": ["datapipe/sql/*", "tests/test_transforms.py", "tests/integration/*"]
  },
  "neutral": ["CHANGELOG.md"],
  "allowed": [
    "docs/*", "datapipe/querystats.py", "datapipe/cli.py", "tests/test_querystats.py",
    "tests/test_cli.py", "datapipe/sql/*", "tests/test_transforms.py", "tests/integration/*",
    "tests/*", "CHANGELOG.md"
  ]
}
JSON
# shellcheck source=../replica/datapipe/finish.sh
. "$dp_here/finish.sh"
