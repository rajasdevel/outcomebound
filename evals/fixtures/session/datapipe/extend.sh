# Add the long-session project and dated history after the unchanged replica base.
long_dp="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 -I -B "$long_dp/extend.py" "$long_dp/project" "$mode"
dp_commit "2026-09-24T09:00:00Z" "extracts: validate manifests and reconcile warehouse counts" \
  datapipe/manifests.py datapipe/reconcile.py tests/test_manifests.py tests/test_reconcile.py docs/extracts.md
dp_commit "2026-09-27T11:00:00Z" "recovery: atomic checkpoints and bounded replay windows" \
  datapipe/checkpoints.py datapipe/watermarks.py tests/test_checkpoints.py tests/test_watermarks.py docs/recovery.md
dp_commit "2026-09-30T10:00:00Z" "catalog: compare extract schemas before planning migrations" \
  datapipe/catalog.py tests/test_catalog.py docs/catalog.md data/catalog.json
dp_commit "2026-10-02T10:00:00Z" "incident tools: read alert windows and rank disk readers" \
  datapipe/incidents.py tests/test_incidents.py docs/incident.md docs/specs/incident-report.md config/retention.json
if [ "$mode" = incident ]; then
  dp_commit "2026-10-03T10:00:00Z" "extracts: inspect catalog types and resolved file roots" \
    datapipe/extract_io.py tests/test_extract_io.py
else
  dp_commit "2026-10-03T10:00:00Z" "extracts: inspect catalog types and resolved file roots" \
    datapipe/extract_io.py tests/test_extract_io.py docs/specs/preflight.md
fi
dp_commit "2026-10-04T10:00:00Z" "recovery: connect event offsets to checkpoint snapshots" \
  datapipe/replay_plan.py tests/test_replay_plan.py docs/replay-api.md
for group in 0 1; do
  dp_commit "2026-10-0$((5 + group))T10:00:00Z" "contracts: document feed group $((group + 1)) intake and recovery" \
    data/contracts/feed_${group}*.json docs/feeds/feed_${group}*.md tests/test_feed_${group}*.py
done

python3 -I -B "$repo/evals/fixtures/session/common/instrument.py"
