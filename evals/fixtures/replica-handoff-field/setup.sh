#!/usr/bin/env bash
# replica-handoff-field: ticket 014 half done on the branch report-since in the main checkout.
# The options are committed; the filter and its wiring are written but not committed; tests,
# docs and the changelog line are not started. The task is to commit the work in progress and
# leave a handoff. Run in the field sandbox, where .agents/ is read-only and .git is writable.
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
main_commit="$(git rev-parse refs/heads/main)"

git checkout -q -b report-since
python3 - <<'PY'
from pathlib import Path

path = Path("tally/cli.py")
text = path.read_text(encoding="utf-8")
anchor = '    reporting.add_argument("--by", default="project", choices=aggregate.GROUPINGS)\n'
options = (
    '    reporting.add_argument("--since", metavar="DAY", help="keep entries from DAY on")\n'
    '    reporting.add_argument("--until", metavar="DAY", help="keep entries up to DAY")\n'
)
path.write_text(text.replace(anchor, anchor + options), encoding="utf-8")
PY
GIT_AUTHOR_DATE="2026-09-14T17:20:00" GIT_COMMITTER_DATE="2026-09-14T17:20:00" \
  git commit -qam "report: --since and --until options (ticket 014, wip)"

# Written since, and not committed: the filter, and the report wired to it.
python3 - <<'PY'
from pathlib import Path

path = Path("tally/aggregate.py")
path.write_text(
    path.read_text(encoding="utf-8")
    + '''

def within(entries, since: date | None = None, until: date | None = None) -> list[Entry]:
    """The entries from `since` to `until`, both included; either may be None."""

    if since and until and until < since:
        message = f"the range ends ({until}) before it starts ({since})"
        raise TallyError("E104", message, field="until")
    return [
        entry
        for entry in entries
        if (since is None or entry.day >= since) and (until is None or entry.day <= until)
    ]
''',
    encoding="utf-8",
)
path = Path("tally/cli.py")
text = path.read_text(encoding="utf-8")
old = "    groups = report.build(readers.read_all(args.files), args.by)\n"
new = (
    '    since = model.parse_day(args.since, field="since") if args.since else None\n'
    '    until = model.parse_day(args.until, field="until") if args.until else None\n'
    "    entries = aggregate.within(readers.read_all(args.files), since, until)\n"
    "    groups = report.build(entries, args.by)\n"
)
text = text.replace(old, new).replace("errors, merge, readers,", "errors, merge, model, readers,")
path.write_text(text, encoding="utf-8")
PY
git tag -f seed >/dev/null

cat > "$stage/checks/handoff.json" <<JSON
{
  "ticket": "014",
  "branch": "report-since",
  "main": "$main_commit",
  "planted": {
    "tally/aggregate.py": ["def within(entries, since"],
    "tally/cli.py": ["--since", "aggregate.within(readers.read_all(args.files), since, until)"]
  }
}
JSON
echo "fixture ready: $target"
