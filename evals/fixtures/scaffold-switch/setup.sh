#!/usr/bin/env bash
# The `lifecycle-switch` project on its new text, a prototype with work in flight whose owner has
# just invited the first outside user, and a README that says the repository is public on GitHub.
# The seed tag moves to the commit that adds the README; the branches and files that the checks of
# `lifecycle-switch` compare are not touched by it.
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
target="${1:?usage: setup.sh <dir> <grading-stage>}"
stage="${2:?usage: setup.sh <dir> <grading-stage>}"

OB_LIFECYCLE_TEXT=new bash "$here/../lifecycle-switch/setup.sh" "$target" "$stage" >/dev/null
cd "$target"
# The prototype preset's "Leave when" line also says what the move keeps: its promotion rule,
# which the scaffold design's switch case reads from the preset's render.
python3 -B - <<'PY'
from pathlib import Path
old = "and each standing grant gets an end date."
rule = old + " The brief to move names the parts kept; probe code is rebuilt, never promoted."
for name in (".outcomebound/fragments/local.md", "AGENTS.md"):
    p = Path(name)
    text = p.read_text(encoding="utf-8")
    assert old in text, name
    p.write_text(text.replace(old, rule, 1), encoding="utf-8")
PY
cat > README.md <<'NOTE'
# notebox

Reading notes. The source is public on GitHub.
NOTE
cp "$repo/evals/graders/scaffold.py" "$stage/checks/"
chmod +x "$stage"/checks/*
git add -A
git commit -qm "say where the source is"
git tag -f seed >/dev/null
echo "fixture ready: $target"
