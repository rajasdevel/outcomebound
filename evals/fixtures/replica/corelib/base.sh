# The corelib replica's shared repository, written into the current directory and committed
# with a history like a small team's: fifteen commits on main over seven months, five merged
# branches (fix-week-parse, docs-errors, add-merge-dedupe, old-cli-flags, report-csv) and one
# unmerged spike (spike-parquet). Each fixture's setup.sh sources this, plants its own task,
# then sources finish.sh, which commits what is left and tags the seed.
#
# Needs: $corelib (this folder). Leaves the checkout on main, every branch ref in place.

# shellcheck source=project.sh
. "$corelib/project.sh"

git init -q -b main .
git config user.email eval@example.invalid
git config user.name "OutcomeBound eval"
git config commit.gpgsign false
rm -f .git/hooks/*.sample
printf '__pycache__/\n' >> .git/info/exclude

# commit DATE MESSAGE PATH...: commit PATHs as they are now, on the date given.
commit() {
  local when="$1" message="$2"
  shift 2
  git add -A -- "$@"
  GIT_AUTHOR_DATE="$when" GIT_COMMITTER_DATE="$when" git commit -qm "$message"
}

# landed BRANCH DATE MESSAGE PATH...: commit PATHs on a new branch, merged into main the same day.
landed() {
  local branch="$1" when="$2"
  git checkout -q -b "$branch"
  commit "$when" "${@:3}"
  git checkout -q main
  GIT_AUTHOR_DATE="$when" GIT_COMMITTER_DATE="$when" \
    git merge -q --no-ff -m "Merge branch '$branch'" "$branch"
}

# The early changelog, before the releases of the summer; the final one comes back in August.
final_changelog="$(cat CHANGELOG.md)"
python3 - <<'PY'
from pathlib import Path

path = Path("CHANGELOG.md")
text = path.read_text(encoding="utf-8")
path.write_text(text.split("## 3.2.0", 1)[0] + text[text.index("## 2.4.0"):], encoding="utf-8")
PY

commit "2026-02-10T10:00:00" "tally: entries, the CSV reader and the report by project" \
  tally/__init__.py tally/__main__.py tally/errors.py tally/model.py tally/readers.py \
  tally/aggregate.py tally/report.py tally/cli.py tests/__init__.py tests/helpers.py \
  tests/test_model.py tests/test_readers.py tests/test_report.py Makefile pyproject.toml \
  README.md .gitignore docs/specs/legacy-v1-columns.md gates/legacy_columns.py \
  gates/python_floor.py tools/syntax_check.py CHANGELOG.md tickets/010-jsonl-input.md
commit "2026-03-02T09:30:00" "docs: record the output decisions D-01 to D-04" \
  docs/specs/output/decisions.md docs/cli.md tools/docs_check.py docs/architecture.md
commit "2026-03-20T16:10:00" "gates: the contract version and the error codes" \
  gates/contract_version.py gates/error_codes.py docs/specs/contract/design.md \
  docs/specs/contract/errors.md docs/gates.md tests/test_errors.py

landed fix-week-parse "2026-04-08T11:00:00" "aggregate: weeks are ISO weeks at the year's edge" \
  tests/test_aggregate.py tickets/011-iso-weeks.md

cat > docs/troubleshooting.md <<'MD'
# Troubleshooting

Each error names its code (see [the codes](specs/contract/errors.md)) and, where it applies, the
file, the line and the column.

- `E101`: the file is not where the command was told it is, or cannot be read.
- `E102`: fix the value the error names; `tally validate` lists every such value at once.
- `E103`: the header lacks a column; the error names it.
- `E104`: an option has a value the command does not know; `--help` lists the values.
MD
landed docs-errors "2026-04-22T14:20:00" "docs: what each error means and what to do" \
  docs/troubleshooting.md

commit "2026-05-19T10:45:00" "validate: every problem in every file, and --output json (ticket 012)" \
  tally/validate.py tests/test_validate.py tickets/012-validate-json.md

landed add-merge-dedupe "2026-06-03T15:00:00" "merge: drop exact duplicates (ticket 013)" \
  tally/merge.py tests/test_merge.py tickets/013-merge-dedupe.md

rm docs/specs/legacy-v1-columns.md
commit "2026-06-30T17:30:00" "contract 3: minutes replace hours; the v1 column set is gone" \
  docs/specs

python3 - <<'PY'
from pathlib import Path

path = Path("pyproject.toml")
path.write_text(path.read_text(encoding="utf-8").replace('">=3.8"', '">=3.10"'), encoding="utf-8")
PY
commit "2026-07-07T09:00:00" "build: require Python 3.10" pyproject.toml

cat > docs/upgrading.md <<'MD'
# Upgrading

## From contract 2 to contract 3

Files carry `minutes` in place of `hours`, and the columns are `day,project,person,minutes,note`.
Convert a v2 file by multiplying each `hours` value by 60 and renaming the columns.
MD
landed old-cli-flags "2026-07-15T13:00:00" "docs: upgrading from contract 2" docs/upgrading.md

commit "2026-07-21T10:00:00" "gates: the model round trip runs in check" gates/model_roundtrip.py

cat > docs/recipes.md <<'MD'
# Recipes

## The last four weeks by person

    tally report entries.csv --by person

## One file for the year

    tally merge q1.csv q2.csv q3.csv q4.csv --out year.csv
MD
landed report-csv "2026-08-05T16:40:00" "docs: recipes" docs/recipes.md

printf '%s\n' "$final_changelog" > CHANGELOG.md
commit "2026-08-14T12:00:00" "ci: run the integration suite; release 3.2.0" \
  tests/integration/run_suite.py tests/test_cli.py .github/workflows/ci.yml CHANGELOG.md

git checkout -q -b spike-parquet
cat > tally/columnar.py <<'PY'
"""Spike: a columnar store for a large year, so a report reads only the columns it needs."""

import array
import json
from pathlib import Path


def write(entries, folder):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    days = sorted({entry.day.isoformat() for entry in entries})
    index = {day: number for number, day in enumerate(days)}
    (folder / "days.json").write_text(json.dumps(days), encoding="utf-8")
    minutes = array.array("H", (entry.minutes for entry in entries))
    (folder / "minutes.bin").write_bytes(minutes.tobytes())
    which = array.array("I", (index[entry.day.isoformat()] for entry in entries))
    (folder / "day_index.bin").write_bytes(which.tobytes())


def total_minutes(folder):
    minutes = array.array("H")
    minutes.frombytes((Path(folder) / "minutes.bin").read_bytes())
    return sum(minutes)
PY
commit "2026-08-20T18:00:00" "spike: a columnar store for a large year" tally/columnar.py
cat >> tally/columnar.py <<'PY'


def days(folder):
    return json.loads((Path(folder) / "days.json").read_text(encoding="utf-8"))
PY
commit "2026-08-21T10:15:00" "spike: read the days back" tally/columnar.py
git checkout -q main

commit "2026-09-02T09:00:00" "tickets: 014 and 015" tickets/014-report-since.md \
  tickets/015-report-json.md
