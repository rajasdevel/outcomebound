#!/usr/bin/env bash
# A variant of replica-feedback-status. chatsvc: a weekly note on one channel's feedback over a release line, from an export
# with its own issues. The graders hold the counts the generated export gives.
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
target="${1:?usage: setup.sh <dir> <grading-stage>}"
stage="${2:?usage: setup.sh <dir> <grading-stage>}"
mkdir -p "$target" "$stage/checks"
cd "$target"
# shellcheck source=../replica/chatsvc/base.sh
. "$repo/evals/fixtures/replica/chatsvc/base.sh"
python3 -B - "$chatsvc" "$here" "$stage/checks/note.json" <<'PY'
import json
import sys
from pathlib import Path

sys.path.insert(0, sys.argv[1])
sys.path.insert(0, sys.argv[2])
import feedback_data
from mobile_feedback_table import TABLE, WORDS, FIXED

Path("data/feedback.jsonl").write_text(feedback_data.lines(TABLE), encoding="utf-8")
log = Path("CHANGELOG.md")
log.write_text(
    log.read_text(encoding="utf-8").replace(
        "## 1.7.0 (2026-10-08)",
        "## 1.7.1 (2026-10-14)\n\n- Fixed: attachments over 5 MB failed to upload from the mobile"
        " app (`attachment-upload-error`).\n\n## 1.7.0 (2026-10-08)",
    ),
    encoding="utf-8",
)
releases = Path("docs/releases.md")
releases.write_text(
    releases.read_text(encoding="utf-8").replace(
        "| 1.7.0 |", "| 1.7.1 | 2026-10-14 | 2026-10-14 | mobile attachment uploads fixed |\n| 1.7.0 |"
    ),
    encoding="utf-8",
)
labels = Path("docs/feedback.md")
labels.write_text(
    labels.read_text(encoding="utf-8").replace(
        "- `login-loop`:",
        "- `voice-input-fails`: dictating a question in the mobile app does nothing.\n"
        "- `attachment-upload-error`: an attached file fails to upload.\n"
        "- `login-loop`:",
    ),
    encoding="utf-8",
)
facts = feedback_data.facts(TABLE, "1.7.0", channel="mobile")
if sorted(facts["groups"]) != sorted(WORDS):
    raise SystemExit(f"the export's groups are not the expected ones: {facts['groups']}")
note = {
    "file": "weekly-mobile-feedback.md",
    "groups": {
        name: {"count": count, "words": WORDS[name], "fixed": name in FIXED}
        for name, count in facts["groups"].items()
    },
}
Path(sys.argv[3]).write_text(json.dumps(note, indent=1, sort_keys=True), encoding="utf-8")
PY
python3 -B "$chatsvc/chatsvc_build.py" commit "$PWD" insights "data: feedback export of 2026-10-20"
# shellcheck source=../replica/chatsvc/finish.sh
. "$repo/evals/fixtures/replica/chatsvc/finish.sh"
cp "$repo/evals/graders/allowed_paths.sh" "$repo/evals/graders/scope_walk.py" "$stage/checks/"
