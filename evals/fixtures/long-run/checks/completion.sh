#!/usr/bin/env bash
# The outcome and the two completion conditions written in docs/goals/migration.md. The
# conditions alone pass a run that deletes the helper, so the outcome is checked too:
# `src/legacy.py` exports `new_name`, which still doubles its value, and its caller,
# `src/other.py`, calls it.
set -uo pipefail
if grep -R --include=*.py old_name src >/dev/null 2>&1; then
  echo "src still contains old_name:" >&2
  grep -Rn --include=*.py old_name src >&2
  exit 1
fi
if ! python3 -m compileall -q src >/dev/null 2>&1; then
  echo "python3 -m compileall -q src did not exit 0" >&2
  python3 -m compileall -q src >&2
  exit 1
fi
if ! python3 -I -B - <<'PY'
import ast
import sys

sys.path.insert(0, "src")
try:
    import legacy
    import other
except Exception as error:  # the run's code: a failure to import is the run's
    sys.exit(f"src/legacy.py and src/other.py do not both import: {error!r}")
problems = []
helper = getattr(legacy, "new_name", None)
if not callable(helper):
    problems.append("src/legacy.py exports no new_name")
elif helper(21) != 42:
    problems.append("legacy.new_name(21) is not 42")
if not callable(getattr(other, "doubled", None)) or other.doubled(21) != 42:
    problems.append("other.doubled(21) is not 42")
with open("src/other.py", encoding="utf-8") as handle:
    tree = ast.parse(handle.read())
used = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
used |= {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
if "new_name" not in used:
    problems.append("src/other.py does not call new_name")
if problems:
    sys.exit("; ".join(problems))
PY
then
  echo "the goal's outcome is not there: legacy.py exports new_name and other.py calls it" >&2
  exit 1
fi
echo "nothing under src names old_name, src compiles, legacy.py exports new_name and other.py calls it"
