# Enlarge the replica after base.sh, before the fixture's own task and finish.sh.
python3 -B "$here/../session/corelib/build.py"
python3 -B "$here/../session/corelib/workload.py"
python3 -B "$here/../session/corelib/consumers.py"
commit "2026-09-03T09:00:00" "library: selections and reconciliation" tally/selection.py tally/reconcile.py tests/test_selection.py tests/test_reconcile.py
commit "2026-09-04T09:00:00" "library: audit and export bundles" tally/audit.py tally/bundles.py tests/test_audit.py tests/test_bundles.py
commit "2026-09-05T09:00:00" "release: manifest and compatibility examples" tally/release.py tests/test_release.py tests/test_examples.py docs/examples docs/library.md docs/release.md CONTRACT_VERSION bin prod .gitignore

commit "2026-09-06T09:00:00" "library: composable plans and batch snapshots" tally/pipeline.py tally/batch.py tally/catalog.py tally/snapshot.py tests/test_pipeline.py docs/data-flow.md docs/library.md
commit "2026-09-07T09:00:00" "docs: compatibility catalog and release work" docs/compatibility.md docs/compatibility
commit "2026-09-08T09:00:00" "docs: library policy history" docs/history

commit "2026-09-09T09:00:00" "library: independent plan and comparison consumers" tally/planfiles.py tally/comparison.py tally/inspection.py tests/test_consumers.py docs/consumers

python3 -B "$here/../session/corelib/views.py"
  commit "2026-09-10T08:00:00" "library: coordinate reports, snapshots and comparisons" tally/views.py tests/test_views.py

python3 -B "$here/../session/corelib/sources.py"
commit "2026-09-10T08:30:00" "inspection: reuse loaded export snapshots" tally/sourcecache.py tally/inspection.py tests/test_sources.py docs/consumers/sources.md

python3 -I -B "$repo/evals/fixtures/session/common/instrument.py"
