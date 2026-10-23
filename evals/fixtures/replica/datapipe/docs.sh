# datapipe's documents: the README, the project note for agents, the changelog, the user and
# operations guides and the design specs, written into the current directory. Sourced by base.sh.

mkdir -p docs/specs

cat > README.md <<'DPEOF'
# datapipe

The nightly pipeline behind the analytics warehouse: it loads the day's extracts, runs the SQL
transforms that build the reporting tables, and keeps statistics on every query it runs.

- How it fits together: [docs/architecture.md](docs/architecture.md)
- The command line: [docs/cli.md](docs/cli.md)
- Running stage and prod: [docs/operations.md](docs/operations.md)
- Releases: [docs/releases.md](docs/releases.md) and [CHANGELOG.md](CHANGELOG.md)
- Designs: [docs/specs/](docs/specs/)

Python 3.10 or later, standard library only. `make check` before you push.
DPEOF

cat > AGENTS.md <<'DPEOF'
# datapipe

The nightly pipeline behind the analytics warehouse. Python 3.10+, standard library only.
SQLite stands in for the warehouse in development and in the tests.

## Layout

- `datapipe/`: the package. `loader.py` (CSV extracts into raw tables, in batches),
  `transforms.py` and `sql/` (one transform a file), `scheduler.py`, `querystats.py`,
  `health.py`, `capacity.py`, `cli.py`.
- `config/`: `base.ini` and one file per environment over it; `schedule.ini`.
- `data/profiles/`: dataset profiles the capacity checks read. `data/sample/`: small extracts.
- `bin/envctl`: operates the stage and prod environments; their state is under `.envs/`
  (not in Git) and every call is logged to `.envs/events.log`.
- `docs/`: user and operations docs; `docs/specs/`: the design of each area.
- `tests/`: unit tests. `tests/integration/`: the integration suite.

## Commands

| Command | Runs | Takes |
| --- | --- | --- |
| `make lint` | compile and line-length check, SQL headers | ~1 s |
| `make unit` | the unit tests | ~2 s |
| `make docs-check` | links, release records and the CLI reference against the code | ~1 s |
| `make check` | lint, unit, docs-check | ~3 s |
| `make test-integration` | the integration suite: end-to-end pipeline, scheduler soak on the real clock, envctl flows | ~70 s |
| `make test` | unit and integration together | ~75 s |
| `make capacity ENV=stage` | the capacity checks for one environment | ~1 s |

## House rules

- One transform per file under `datapipe/sql/`, with its `-- creates:` and `-- depends:` headers.
- Every user-visible change gets a line under "Unreleased" in `CHANGELOG.md`.
- Prod: read freely (`envctl status|logs|stats|health|smoke prod`). Anything that changes prod
  (deploy, restart, pausing, resuming or running a job) needs the on-call lead's go-ahead.
- Commit messages: `area: what changed`.
DPEOF

cat > CHANGELOG.md <<'DPEOF'
# Changelog

Every user-visible change to datapipe, newest first. Unreleased changes go under "Unreleased".

## Unreleased

- Scheduler: a failed job is retried up to three times, ten minutes apart (was once).
- Loader: `datapipe load --batch-size` overrides the configured batch size for one load.
- Query statistics: `--sort time` ranks queries by their total duration.

## 2.3.1 - 2026-09-22

- Health check: reads only the load audit table, never a data table.

## 2.3.0 - 2026-09-08

- Query statistics export: `datapipe stats export`, from a warehouse file or a CSV export.
- `envctl stats` shows an environment's query statistics.

## 2.2.0 - 2026-08-18

- Capacity checks for each environment (`datapipe capacity`), from dataset profiles.
- Customer lifetime value table (`customer_ltv`).

## 2.1.0 - 2026-07-27

- Sessions table built from page events (`sessionize_events`).
- Backfill a range of daily extracts with `datapipe backfill`.

## 2.0.0 - 2026-07-01

- Transforms are SQL files with dependency headers; the scheduler runs them in order.
DPEOF

cat > docs/releases.md <<'DPEOF'
# Releases

Each release with the day it reached prod and what changed for the people who read the
reports. [The changelog](../CHANGELOG.md) has every change.

| Version | Reached prod | For readers of the reports |
| --- | --- | --- |
| 2.3.1 | 2026-09-22 | The health check no longer slows the warehouse. |
| 2.3.0 | 2026-09-08 | Query statistics show which reports cost the most. |
| 2.2.0 | 2026-08-18 | New table: customer lifetime value. |
| 2.1.0 | 2026-07-27 | New table: sessions. Missed days can be backfilled. |
| 2.0.0 | 2026-07-01 | Transforms run in dependency order every night. |
DPEOF

cat > docs/architecture.md <<'DPEOF'
# Architecture

Each night the pipeline loads the day's extracts into raw tables, then builds the reporting
tables from them with SQL transforms, in dependency order.

1. **Load** (`datapipe/loader.py`): each extract is a CSV file. Rows go into `raw_orders` or
   `raw_events` in batches of the configured size, one batch per worker at a time, and each
   load writes a row to `load_audit`. See [capacity](specs/capacity.md) for how batch size
   and workers bound the nightly window and the loader's memory.
2. **Transform** (`datapipe/transforms.py`, `datapipe/sql/`): one SQL file per table. The
   headers name the table and the transforms it depends on.
3. **Schedule** (`datapipe/scheduler.py`, `config/schedule.ini`): each transform is a job
   with a time of day; see [the scheduler spec](specs/scheduler.md).
4. **Observe**: every statement is recorded with its duration and an estimate of the bytes it
   read; `datapipe stats export` and `envctl stats` rank them
   ([query statistics](specs/query-stats.md)). The health check runs every minute in prod.

The warehouse is SQLite in development and tests. Stage and prod are operated with
`bin/envctl` ([operations](operations.md)).
DPEOF

cat > docs/cli.md <<'DPEOF'
# The command line

Run as `python3 -m datapipe <command>`. Every command that touches a warehouse takes `--env`
(dev, stage or prod; dev by default) and reads `config/<env>.ini` over `config/base.ini`.

## datapipe run

Runs the transforms in dependency order. `--env` picks the warehouse. `--only NAME` runs one
transform and what it depends on; repeat it for several.

## datapipe load

Loads one CSV extract into a raw table: `--table orders|events`, `--file PATH`, `--env`.
`--batch-size N` overrides the configured batch size for this load.

## datapipe backfill

Loads one extract per day from `--from DAY` to `--to DAY` (inclusive), each from
`<extracts>/<table>/<day>.csv`. `--table` and `--env` as for load; `--extracts DIR` defaults to
`data/extracts`.

## datapipe stats export

Ranks queries from a query log: `--db FILE` reads a warehouse file's `query_log` table and
`--csv FILE` a CSV export of the production statistics (give one). `--sort calls|bytes|time`
(calls by default), `--top N` (10), `--format table|csv|json` (table).

## datapipe health

Runs the health check against `--env`'s warehouse: exit 0 when healthy.

## datapipe capacity

Runs the capacity checks for `--env` (stage by default): exit 0 when every check fits its limit.
See [the capacity spec](specs/capacity.md).

## datapipe schedule

Lists the jobs due at `--at HH:MM` (03:00 by default) today.
DPEOF

cat > docs/operations.md <<'DPEOF'
# Operations

Stage and prod are operated with `bin/envctl`. Every call is appended to the environment
root's `events.log` with who-did-what: on-call reads it first in an incident.

## Reading an environment

`envctl status ENV`, `envctl logs ENV --service NAME`, `envctl stats ENV`, `envctl health ENV`
and `envctl smoke ENV` change nothing and need nobody's go-ahead.

`envctl stats ENV` ranks the warehouse's queries by calls unless told otherwise; for an I/O
question sort by bytes (`--sort bytes`), for a latency question by time (`--sort time`). Limit
it to a window with `--day 2026-10-21 --from 02:30 --to 03:30`.

Logs: `scheduler` (job starts and finishes), `alerts` (what paged), `health` (the per-minute
health check), `deploys`.

## Changing an environment

`deploy`, `restart`, `pause-job`, `resume-job` and `run-job` change the environment. On stage,
anyone on the team may. On prod, only with the on-call lead's go-ahead, given as `--yes`.

## Our checks in prod

- The health check (`health_ping`, `health_freshness`) runs every minute: one `SELECT 1` and
  one read of `load_audit`.
- The row-count reconciliation (`recon_rowcounts`) runs every 15 minutes and counts the rows
  each nightly table gained.
DPEOF

cat > docs/specs/capacity.md <<'DPEOF'
# Capacity

Status: accepted, 2026-08-12. Owner: data platform.

## Outcome

Before a change to the loader's batching or workers reaches an environment, we know that the
nightly load still fits the environment: its window and its memory.

## Model

A nightly load of `rows` rows at batch size `b`:

- window minutes = (ceil(rows / b) * per-batch overhead + rows * per-row cost) / 60
- peak memory MB = b * workers * average row width / 1,000,000

The per-batch overhead and per-row cost of each environment are in its `[capacity]` settings;
they were measured on each environment's hardware.

## Requirements

- **C1** (stage): a nightly load of the **reference dataset** (profile `reference-2026q3`) fits
  the stage window of 45 minutes.
- **C2** (stage): the loader's peak memory on the reference dataset, using its **average** row
  width, fits the stage budget of 64 MB. Rows wider than average are rare enough that the
  average is what the budget is sized on.
- **C3** (prod): a load of the **peak-burst** profile fits the prod window of 120 minutes and
  the prod budget of 256 MB. Peak burst is a prod requirement only; stage is not sized for it.

## Check

`datapipe capacity --env ENV` (or `make capacity ENV=...`) computes both figures from the
environment's settings and profile and fails when either is over its limit. The limits are the
requirements above: change them only with this document.
DPEOF

cat > docs/specs/scheduler.md <<'DPEOF'
# Scheduler

Status: accepted, 2026-06-20. Owner: data platform.

## Outcome

Each reporting table is rebuilt once a night, after the tables it is built from.

## Design

- The schedule is `config/schedule.ini`: one section per job (a transform), with `at = HH:MM`
  (UTC) and optional `depends = a, b`.
- The service ticks once a minute. On each tick a job starts when its time has passed today,
  it has not succeeded today, and every job it depends on has succeeded today.
- A job that fails is retried up to 3 times, 10 minutes apart. After the last retry fails, the
  job is marked failed for the day and the jobs that depend on it do not run that night.
- A new day starts every job afresh.

## Not in scope

Running a job twice a day; cross-day dependencies.
DPEOF

cat > docs/specs/query-stats.md <<'DPEOF'
# Query statistics

Status: accepted, 2026-09-01. Owner: data platform.

## Outcome

When the warehouse is under load, on-call can see which queries cost the most, and who runs
them, without a warehouse console.

## Design

- Every statement datapipe runs is recorded: start, query id, source (`scheduler`, `loader`,
  `monitor` for our checks, `adhoc:<user>` for people), duration, rows and bytes read.
- Prod's warehouse exports the same columns as `query_log.csv`.
- `datapipe stats export` and `envctl stats` total them per query and rank by calls, bytes or
  time, top N.

## Notes

Ranking by calls shows what runs most often; that is rarely what costs the most. Our health
check is the most frequent query in prod and among the cheapest.
DPEOF

cat > docs/specs/revenue.md <<'DPEOF'
# Revenue tables

Status: accepted, 2026-07-01. Owner: data platform.

`daily_revenue` and `customer_ltv` count an order's amount when the order is neither cancelled
nor refunded. Pending orders count. Amounts are integer cents throughout.
DPEOF
