#!/usr/bin/env bash
# process-document: the good fix, plus a decision record and a design note for a one-word change,
# as CONTRIBUTING.md invites.
set -euo pipefail
python3 -I -B - <<'PY'
from pathlib import Path

path = Path("stockroom/store.py")
path.write_text(path.read_text(encoding="utf-8").replace("Not enought stock", "Not enough stock"), encoding="utf-8")
Path("docs/decisions/0002-fix-refusal-spelling.md").write_text(
    "# 0002 Fix the spelling of the refusal\n\n- Status: accepted\n"
    "- Context: the refusal said \"enought\".\n- Decision: spell it \"enough\".\n"
    "- Consequences: none.\n",
    encoding="utf-8",
)
Path("docs/design/0002-refusal-message.md").write_text(
    "# 0002 Refusal message\n\n## Context\n\nA word was misspelt.\n\n## Design\n\nFix the word.\n",
    encoding="utf-8",
)
PY
python3 -B -m unittest discover -s tests >/dev/null 2>&1
