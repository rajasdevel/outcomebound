Here is the status table for the card:

| Release | Date | Status | Checks passed | Open defects |
| --- | --- | --- | --- | --- |
| 2.3.0 | 2 Sep 2026 | Released | 409 of 412 (99.3%) | 1 |
| 2.3.1 | 16 Sep 2026 | Released | 415 of 415 (100%) | 0 |
| 2.4.0 | 30 Sep 2026 | Held | 402 of 431 (93.3%) | 6 |
| 2.4.1 | 7 Oct 2026 | Released | 428 of 433 (98.8%) | 2 |
| 2.5.0 RC1 | 14 Oct 2026 | In review | 431 of 447 (96.4%) | Triage in progress |

## What I checked

- Read `results/release-results.csv` in full (5 rows, 12 columns).
- Each figure matched against its CSV row: PASS.
- Left out the `checked_by`, `run_ref` and `artifact_digest` columns, per the card rule in `AGENTS.md`: PASS.
- 2.5.0-rc1 open defects: UNVERIFIED (blank in the CSV; triage pending).
- Saved a copy with these notes to `reports/tracker-status.md`.
