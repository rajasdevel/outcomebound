It was not CI, and more retries would not have fixed it. Since "report: build totals in one pass with a map" (2026-09-22), `WriteSummary` writes its rows by ranging over a Go map, whose order is random on every run; the test passes only when the order happens to match the golden file. The retries made that rarer, not gone, as `ci/recent-runs.txt` shows.

The same random order reached the real summary files: `docs/format.md` says the finance importer diffs them day over day and relies on account order.

Fix: `WriteSummary` now sorts the accounts before writing. I removed the retry wrapper, so the test fails on any wrong order again. `go test -count=50 ./internal/report` passes.
