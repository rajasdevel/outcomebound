# The core skill in a fixture, run from the fixture's directory: installed where the note names
# it and where codex looks for skills, except in the kernel-off arm (OB_EVAL_ARM=none), which
# gets no skill, and a note without the sentence that points at it.
set -euo pipefail
repo="${1:?usage: core-skill.sh <repo> <note>}"
note="${2:?usage: core-skill.sh <repo> <note>}"
if [ "${OB_EVAL_ARM:-}" = none ]; then
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
  cp -R "$repo/skills/using-outcomebound" "$root/"
done
