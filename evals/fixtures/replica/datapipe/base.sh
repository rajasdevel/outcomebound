# datapipe, the replica base shared by the replica-* data-pipeline fixtures, written into the
# current directory by a fixture's setup.sh. A nightly pipeline over SQLite (standing in for the
# warehouse): loader, SQL transforms, a scheduler, query statistics, health and capacity checks,
# `bin/envctl` for simulated stage and prod environments, docs and specs, fast unit tests and a
# slow integration suite (a little over a minute of real work and real-clock ticks).
#
# This file writes the project from the part scripts beside it and commits it as a short
# history. The fixture then plants its own commits with `dp_commit`, seeds the environments with
# `envseed.py` where it needs them, and sources `finish.sh`, which makes the last commit (the
# project note) and the seed tag.
#
# The code is correct as written here: a fixture that needs a fault plants it.
set -euo pipefail
dp_here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1

# shellcheck source=src.sh
. "$dp_here/src.sh"
# shellcheck source=ops.sh
. "$dp_here/ops.sh"
# shellcheck source=tests.sh
. "$dp_here/tests.sh"
# shellcheck source=docs.sh
. "$dp_here/docs.sh"

git init -q .
git symbolic-ref HEAD refs/heads/main
git config user.email data-platform@example.invalid
git config user.name "Data Platform"
git config commit.gpgsign false
rm -f .git/hooks/*.sample
printf '__pycache__/\n' >> .git/info/exclude

# dp_commit WHEN MESSAGE PATH...: commit the named paths as they now are, dated WHEN.
dp_commit() {
  local when="$1" message="$2"
  shift 2
  git add -- "$@"
  GIT_AUTHOR_DATE="$when" GIT_COMMITTER_DATE="$when" git commit -qm "$message"
}

dp_commit "2026-06-15T09:12:00Z" "warehouse: SQLite connection that records every query" \
  .gitignore README.md datapipe/__init__.py datapipe/__main__.py datapipe/warehouse.py \
  datapipe/config.py config/base.ini config/dev.ini config/stage.ini config/prod.ini \
  tests/__init__.py tests/test_warehouse.py tests/test_config.py
dp_commit "2026-06-19T14:40:00Z" "loader: CSV extracts into raw tables in batches" \
  datapipe/batching.py datapipe/loader.py data/sample tests/helpers.py tests/test_batching.py \
  tests/test_loader.py
dp_commit "2026-06-30T11:05:00Z" "transforms: SQL files with dependency headers; scheduler" \
  datapipe/transforms.py datapipe/sql/stg_orders.sql datapipe/sql/daily_revenue.sql \
  datapipe/scheduler.py config/schedule.ini docs/specs/scheduler.md docs/specs/revenue.md \
  tests/test_scheduler.py
dp_commit "2026-07-24T16:20:00Z" "transforms: sessions from page events" \
  datapipe/sql/stg_events.sql datapipe/sql/sessionize_events.sql tests/test_transforms.py
dp_commit "2026-08-12T10:30:00Z" "capacity: window and memory checks from dataset profiles" \
  datapipe/capacity.py data/profiles docs/specs/capacity.md datapipe/sql/customer_ltv.sql \
  tests/test_capacity.py
dp_commit "2026-08-28T13:15:00Z" "cli: one entry point for run, load, backfill and checks" \
  datapipe/cli.py datapipe/health.py tests/test_cli.py tests/test_health.py docs/cli.md
dp_commit "2026-09-04T09:50:00Z" "querystats: rank queries by calls, bytes or time" \
  datapipe/querystats.py tests/test_querystats.py docs/specs/query-stats.md
dp_commit "2026-09-07T15:25:00Z" "ops: envctl for stage and prod; operations guide" \
  bin/envctl tests/test_envctl.py docs/operations.md docs/architecture.md
dp_commit "2026-09-15T11:40:00Z" "ci: lint, unit, docs check and the integration suite" \
  Makefile .github tools tests/integration
dp_commit "2026-09-22T08:55:00Z" "release: 2.3.1" CHANGELOG.md docs/releases.md
