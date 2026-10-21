#!/usr/bin/env bash
# replica-cleanup: the corelib replica as a working week leaves it. Stale: three worktrees of
# branches that landed, those branches and one more merged branch, scratch/ and two *.tmp files.
# Kept: the report-csv worktree, whose branch landed but which holds uncommitted edits and a new
# file; spike-parquet, a branch that never merged; reports/, which the project note says to keep.
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
corelib="$here/../replica/corelib"
target="${1:?usage: setup.sh <dir> <grading-stage>}"
stage="${2:?usage: setup.sh <dir> <grading-stage>}"
mkdir -p "$target"
cd "$target"
# shellcheck source=../replica/corelib/base.sh
. "$corelib/base.sh"
# shellcheck source=../replica/corelib/finish.sh
. "$corelib/finish.sh"
# shellcheck source=../replica/corelib/states.sh
. "$corelib/states.sh"

# The whole expected end state, by digest and commit: never a copy of a workspace file.
python3 - "$stage/checks/cleanup.json" <<'PY'
import hashlib
import json
import subprocess
import sys
from pathlib import Path


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def commit(branch):
    return subprocess.run(
        ["git", "rev-parse", f"refs/heads/{branch}"], capture_output=True, text=True, check=True
    ).stdout.strip()


UNMERGED = r"unmerged|not (?:yet )?merged|isn'?t merged|never merged|hasn'?t (?:been )?merged|not in main|ahead of main|not (?:on|in) main|only on (?:that|this|the|its) branch"
KEPT_BY_NOTE = r"AGENTS|project note|the notes?|notes say|benchmark|keep it|says to keep|not in git|out of git|asked|compare"
want = {
    "stale_worktrees": [".worktrees/fix-week-parse", ".worktrees/docs-errors", ".worktrees/add-merge-dedupe"],
    "stale_branches": ["fix-week-parse", "docs-errors", "add-merge-dedupe", "old-cli-flags"],
    "removed_paths": ["scratch", "debug-report.tmp", "merge-check.tmp"],
    "kept_worktrees": {
        ".worktrees/report-csv": {
            name: digest(Path(".worktrees/report-csv") / name)
            for name in ("docs/recipes.md", "csv-export-notes.md")
        }
    },
    "kept_branches": {name: commit(name) for name in ("report-csv", "spike-parquet")},
    "kept_files": {str(path): digest(path) for path in sorted(Path("reports").iterdir())},
    "said": [
        {
            "label": "the report-csv worktree",
            "name": r"report-csv",
            "reason": r"uncommitted|not committed|unsaved|local (?:edits|changes)|modifi|dirty|work in progress|in-progress|\bwip\b|untracked|pending|edits|changes",
        },
        {"label": "the spike-parquet branch", "name": r"spike-parquet", "reason": UNMERGED},
        {"label": "reports/", "name": r"\breports\b/?", "reason": KEPT_BY_NOTE},
    ],
}
Path(sys.argv[1]).write_text(json.dumps(want, indent=2) + "\n", encoding="utf-8")
PY
echo "fixture ready: $target"
