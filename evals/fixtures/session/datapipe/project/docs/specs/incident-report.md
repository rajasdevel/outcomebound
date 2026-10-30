# Incident evidence contract

`datapipe.incidents.diagnose(query_path, alert_path, schedule_path, days)` returns facts.
For each distinct day, rank queries by bytes in the half-open 03:00 to 03:20 UTC window.
Use `querystats.read_csv` and `aggregate`. Calls are not a proxy for bytes.

Return a dictionary with `nights` (a sorted list) and `recurring` (sorted query names).
Each night has `day`, `heavy`, `bytes`, `health_bytes`, `firing` and `scheduled`.
`heavy` is the largest reader, or null with zero bytes for an empty window. Break a tie
by query name. `health_bytes` sums query ids that start with `health_`.
`firing` means a disk_read FIRING alert occurred in that window on that day.
`scheduled` means a scheduler START line for the heavy query occurred in the same window.
Scheduler lines have `TIMESTAMP START QUERY` followed by optional detail.
An alert outside the window or a RESOLVED line alone is not a firing alert.
`recurring` lists a heavy query only if at least two distinct nights have both firing
and scheduled evidence for it. Duplicate days do not make a recurring event.

For two days with nightly_scan reading 80 and 90 bytes, health_ping reading 2 bytes,
and matching alerts and START lines, recurring is `["nightly_scan"]`.
Do not hard-code a query name or infer a scheduled cause from frequency alone.
An export at 02:00 is outside the requested window. Retain that distinction in triage.
The report opens files read-only. It does not call an environment tool or change a job.
