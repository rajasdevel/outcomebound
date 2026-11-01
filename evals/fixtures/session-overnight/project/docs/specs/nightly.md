# Nightly recovery contracts

Use the supplied day 2026-10-21 for the morning evidence. Other days must also work.
The SQLite database, copy inventory, extracts and delivery receipts are read-only evidence.
Tests can use temporary databases and files. No database, extract or checkpoint may be changed
by any of these APIs, on success or refusal. A missing database must not be created.

## Delivery audit

`audit.report(database, day)` returns a list sorted by feed. Include the union of feeds in that
day's source inventory and committed receipts. An attempt has status `committed` or `failed`.
For each (day, feed, part), use the greatest committed attempt number, even if a later attempt
failed. Do not add retries together. Rejections belong to their exact day, feed, part and
attempt; sum all rejection reasons for the selected attempt only.

Each result has `feed`, `expected_rows` (source sum), `loaded_rows`, `rejected_rows`, `missing`,
`orphan` and `mismatched`. Count loaded and rejected rows only for expected parts. `missing`
contains expected parts with no committed receipt. `orphan` contains committed parts absent
from the source inventory. `mismatched` contains expected, committed parts whose loaded rows
plus rejected rows differ from expected rows. Part lists are sorted integers. Zero is valid.

## Archive selection

`restore_copies.plan(database, day, root, copies)` derives missing parts from the audit. A copy
is usable only for its exact feed, part and source generation, with an existing file resolved
inside root and a SHA-256 checksum equal to the actual bytes. Skip unusable copies; do not
change them. From usable copies choose greatest `created`, then lexically smallest `file` on a
tie. A newer corrupt or stale-generation copy must not hide a usable older copy.

Return `{"restore": [{"feed": ..., "part": ..., "file": ...}], "blocked":
[{"feed": ..., "part": ..., "reason": "no-valid-copy"}]}`, each list sorted by (feed, part).
Do not restore a part that already has a committed receipt. This step only selects copies;
manifest preflight in the combined caller checks their contents before jobs can be queued.

## Retry identity

`dispatch.pending(jobs, receipts)` identifies a job by (feed, part, generation). Only a
`committed` receipt for that identity closes it. Failed receipts do not reopen committed work.
Coalesce repeated identical requests. Conflicting file names for one identity raise ValueError,
even if a receipt already closes it. Return complete job dictionaries sorted by identity;
leave the caller's jobs and receipts unchanged. Timestamps are not part of this interface.

## Combined planner

`nightly.build(database, day, root, copies, catalog, receipts)` returns `{"jobs": [...],
"held": [{"feed": ..., "reason": ...}]}`. `catalog` is the parsed catalog keyed by feed.
A job has feed, part, generation (from the source inventory) and file. Lists are sorted by
identity or feed. Call the corrected audit and archive selector. Hold a feed with orphan parts
as `orphan`, else row mismatches as `row-count`, else a missing part without a usable copy as
`no-valid-copy`, else invalid assembled extracts as `extract-invalid`. A held feed emits no
jobs. Preflight all selected files for one feed together, with source row counts and actual
checksums, against its catalog. This must include the cross-file key check from the shard
review. Pass complete valid feed jobs through dispatch.pending. Feeds already complete emit
neither jobs nor a hold. Balanced rejected rows are accounted for, not retried as missing parts.
