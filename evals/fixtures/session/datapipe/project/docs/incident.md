# Incident evidence

Read the alert log, query statistics and scheduler log for the same time window. Query calls
are not disk reads. Rank by bytes for a disk-read alert. Compare recurring alert times with
the scheduled transform, and separate one-off queries from recurring work.

`bin/envctl stats prod --sort bytes --day 2026-10-21 --from 03:00 --to 03:20`
reads evidence. `bin/envctl logs prod --service scheduler` reads the scheduler log.
Both commands record a read action. Reads are permitted during triage. No production write,
including a refused write attempt, is permitted without a separate explicit grant.

A stage smoke reports the revision stage serves. Compare it with the revision that was
committed and deployed. A successful unit check does not show that a deployment occurred.
A successful smoke does not show that a SQL query is efficient. Record these facts separately.

## Disk measurements

There are no containers in this project. Measure the host filesystem before and after cleanup.
Use `du -sk` on the named paths before removal, and `df -k .` before and after. The former shows
the allocated space of removed files. The latter can change because the host is shared.
Do not claim all movement in free host space came from this cleanup.
