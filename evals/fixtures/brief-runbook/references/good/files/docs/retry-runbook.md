# Retry operations

| Case | Action |
| --- | --- |
| First success | Done after one attempt |
| Two failures then success | Done after three attempts |
| Four failures | Failed for the day |
| Failed dependency | Wait; do not run the dependent |
| Stage rerun | Use python3 -m datapipe run --env stage --only daily_revenue |
| Prod rerun | Obtain the on-call grant first; use the same command with --env prod |

For missing extracts, use python3 -m datapipe backfill --env stage --table orders
--from 2026-09-01 --to 2026-09-02 --extracts data/extracts.
Sources: datapipe/scheduler.py, datapipe/cli.py, docs/operations.md.

The scheduler allows three additional retries, ten minutes apart: four total attempts.
Four failures mark the job failed for the day. Dependents must not run until it is done.
Manual backfill loads extracts; it does not use the scheduler retry state machine.
