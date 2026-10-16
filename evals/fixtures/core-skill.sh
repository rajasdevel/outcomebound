# The core skill in a fixture, run from the fixture's directory: installed where the note names
# it and where codex looks for skills, except in the kernel-off arm (OB_EVAL_ARM=none) and in
# the earlier arm under --earlier-verbatim (OB_EVAL_VERBATIM=1), which get no skill from here, and
# a note without the sentence that points at it. The skill is the checkout's, or the tree
# OB_EVAL_SOURCE names (the earlier arm under --earlier-ref).
set -euo pipefail
repo="${1:?usage: core-skill.sh <repo> <note>}"
note="${2:?usage: core-skill.sh <repo> <note>}"
if [ "${OB_EVAL_ARM:-}" = none ] || [ "${OB_EVAL_VERBATIM:-}" = 1 ]; then
  python3 -B - "$note" <<'PY'
import re
import sys

path = sys.argv[1]
with open(path, encoding="utf-8") as handle:
    text = handle.read()
pointer = r"\s*Read `\.outcomebound/skills/using-outcomebound/SKILL\.md` before planning work here\."
with open(path, "w", encoding="utf-8") as handle:
    handle.write(re.sub(pointer, "", text))
PY
  exit 0
fi
for root in .outcomebound/skills .agents/skills; do
  mkdir -p "$root"
  cp -R "${OB_EVAL_SOURCE:-$repo}/skills/using-outcomebound" "$root/"
done
