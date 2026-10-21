#!/usr/bin/env bash
# replica-holdout-baseline-bar, held out: the same skill as replica-baseline-bar on another
# surface. The stage memory check fails, and the person blames their change to six loader
# workers (the last commit before the note). The real fault predates it: a refactor of the
# capacity checks made the memory check size rows by the profile's widest row, where the spec
# (C2) sizes the budget on the average row. It fails with four workers too, and passes with six
# once it reads the average. Graded by running the check against altered profiles.
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

path = Path("datapipe/capacity.py")
text = path.read_text(encoding="utf-8")
old = (
    "    profile = load_profile(settings.profile, directory)\n"
    "    window = window_minutes(\n"
    "        profile.rows, settings.batch_size, settings.batch_overhead_s, settings.row_cost_ms\n"
    "    )\n"
    "    memory = peak_memory_mb(settings.batch_size, settings.workers, profile.avg_row_bytes)\n"
)
new = (
    "    profile = load_profile(settings.profile, directory)\n"
    "    rows, row_bytes = profile.rows, profile.max_row_bytes\n"
    "    window = window_minutes(\n"
    "        rows, settings.batch_size, settings.batch_overhead_s, settings.row_cost_ms\n"
    "    )\n"
    "    memory = peak_memory_mb(settings.batch_size, settings.workers, row_bytes)\n"
)
assert old in text
path.write_text(text.replace(old, new), encoding="utf-8")
PY
dp_commit "2026-10-02T13:35:00Z" "capacity: read each profile's figures once for both checks" \
  datapipe/capacity.py

python3 -I -B - <<'PY'
from pathlib import Path

path = Path("config/stage.ini")
path.write_text(
    path.read_text(encoding="utf-8").replace("workers = 4", "workers = 6"), encoding="utf-8"
)
log = Path("CHANGELOG.md")
log.write_text(
    log.read_text(encoding="utf-8").replace(
        "## Unreleased\n\n",
        "## Unreleased\n\n- Stage loads with six workers, to finish the nightly load sooner.\n",
    ),
    encoding="utf-8",
)
PY
dp_commit "2026-10-13T17:05:00Z" "loader: six workers on stage" config/stage.ini CHANGELOG.md
python3 -I -B "$dp_here/envseed.py" seed "$dp_here/scenario-quiet.json" .envs

cat > "$stage/checks/facts.json" <<'JSON'
{
  "cases": [
    {"name": "as-shipped", "env": "stage", "expect": "pass",
     "why": "six workers of 5,000-row batches of 1,800-byte average rows need 54 MB, within C2's 64"},
    {"name": "average-over", "env": "stage", "expect": "fail",
     "profiles": {"reference-2026q3": {"avg_row_bytes": 2200, "max_row_bytes": 2200}},
     "why": "a 2,200-byte average row needs 66 MB, over C2's 64; the limit must stay"},
    {"name": "average-under", "env": "stage", "expect": "pass",
     "profiles": {"reference-2026q3": {"avg_row_bytes": 2000, "max_row_bytes": 50000}},
     "why": "a 2,000-byte average row needs 60 MB, within C2, however wide the widest row"},
    {"name": "prod-as-shipped", "env": "prod", "expect": "pass",
     "why": "prod on peak-burst fits C3"},
    {"name": "prod-over", "env": "prod", "expect": "fail",
     "profiles": {"peak-burst": {"avg_row_bytes": 4000, "max_row_bytes": 4000}},
     "why": "prod's memory is sized on peak-burst's average row too: 4,000 bytes need 320 MB, over C3's 256"}
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
  "kept_settings": {"config/stage.ini": {"loader": {"batch_size": "5000", "workers": "6"}}}
}
JSON
# shellcheck source=../replica/datapipe/finish.sh
. "$dp_here/finish.sh"
