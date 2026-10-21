#!/usr/bin/env bash
# replica-baseline-bar, on the datapipe base: the stage capacity check fails, and the person
# blames their batching change (stage batches of 2,000 rows, the last commit before the note).
# The real fault predates it: a settings tidy-up two weeks earlier gave stage the peak-burst
# profile, which the capacity spec (C1, C3) reserves for prod; stage's requirement is the
# reference dataset. The check fails with the old batch size too, and passes with the new one
# once it reads the reference profile. Graded by running the check against altered profiles.
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

cat > config/stage.ini <<'INI'
# Stage: the reference dataset, at production's per-row cost, on smaller hardware.
[warehouse]
path = /srv/datapipe/stage/warehouse.db

[loader]
batch_size = 5000
workers = 4

[capacity]
profile = peak-burst
INI
cat > config/prod.ini <<'INI'
# Production: larger batches and more workers.
[warehouse]
path = /srv/datapipe/prod/warehouse.db

[loader]
batch_size = 10000
workers = 8

[capacity]
batch_overhead_s = 0.8
row_cost_ms = 1.0
window_minutes = 120
memory_budget_mb = 256
profile = peak-burst
INI
dp_commit "2026-10-07T15:10:00Z" "config: tidy stage and prod settings" config/stage.ini config/prod.ini

python3 -I -B - <<'PY'
from pathlib import Path

path = Path("config/stage.ini")
path.write_text(
    path.read_text(encoding="utf-8").replace("batch_size = 5000", "batch_size = 2000"),
    encoding="utf-8",
)
log = Path("CHANGELOG.md")
log.write_text(
    log.read_text(encoding="utf-8").replace(
        "## Unreleased\n\n",
        "## Unreleased\n\n- Stage loads in batches of 2,000 rows, to shorten table locks.\n",
    ),
    encoding="utf-8",
)
PY
dp_commit "2026-10-20T16:45:00Z" "loader: batches of 2,000 rows on stage to cut lock time" \
  config/stage.ini CHANGELOG.md
python3 -I -B "$dp_here/envseed.py" seed "$dp_here/scenario-quiet.json" .envs

cat > "$stage/checks/facts.json" <<'JSON'
{
  "cases": [
    {"name": "as-shipped", "env": "stage", "expect": "pass",
     "why": "stage on the reference profile fits C1 at 2,000-row batches (42.0 of 45 minutes)"},
    {"name": "reference-over", "env": "stage", "expect": "fail",
     "profiles": {"reference-2026q3": {"rows": 1350000}, "peak-burst": {"rows": 100}},
     "why": "1,350,000 reference rows need 47.25 minutes, over C1's 45; the check must read the reference profile and keep its limit"},
    {"name": "reference-under", "env": "stage", "expect": "pass",
     "profiles": {"reference-2026q3": {"rows": 1250000}, "peak-burst": {"rows": 9000000}},
     "why": "1,250,000 reference rows need 43.75 minutes, within C1, whatever peak-burst holds"},
    {"name": "prod-as-shipped", "env": "prod", "expect": "pass",
     "why": "prod on peak-burst fits C3"},
    {"name": "prod-over", "env": "prod", "expect": "fail",
     "profiles": {"peak-burst": {"rows": 7000000}},
     "why": "prod must still read peak-burst: 7,000,000 rows need 126 minutes, over C3's 120"}
  ],
  "kept_files": [
    "data/profiles/reference-2026q3.json",
    "data/profiles/peak-burst.json",
    "docs/specs/capacity.md",
    "config/base.ini",
    "config/prod.ini",
    "datapipe/batching.py",
    "datapipe/loader.py"
  ],
  "kept_settings": {"config/stage.ini": {"loader": {"batch_size": "2000", "workers": "4"}}}
}
JSON
# shellcheck source=../replica/datapipe/finish.sh
. "$dp_here/finish.sh"
