# The ledger seed's shared repository, written into the current directory and committed with a
# history like a small team's: seven commits on main from March to July 2026, with one default
# (statements newest first, LD-2) made and then reverted (LD-4). Each fixture's setup.sh sources
# this, plants its own task with `ledger_commit`, then sources finish.sh, which commits what is
# left and tags the seed.
#
# Needs: $ledger (this folder). Leaves the checkout on main with AGENTS.md written, uncommitted,
# so a fixture can add to it before finish.sh commits it.

# shellcheck source=project.sh
. "$ledger/project.sh"

git init -q -b main .
git config user.email eval@example.invalid
git config user.name "OutcomeBound eval"
git config commit.gpgsign false
rm -f .git/hooks/*.sample
printf '__pycache__/\n' >> .git/info/exclude

# ledger_commit DATE MESSAGE PATH...: commit PATHs as they are now, on the date given.
ledger_commit() {
  local when="$1" message="$2"
  shift 2
  git add -A -- "$@"
  GIT_AUTHOR_DATE="$when" GIT_COMMITTER_DATE="$when" git commit -qm "$message"
}

# The final forms are kept aside while the history commits the earlier ones.
ledger_final="$(mktemp -d)"
cp -R ledger tests docs CHANGELOG.md "$ledger_final/"

# ledger_edit FILE OLD NEW: replace the one OLD in FILE with NEW.
ledger_edit() {
  python3 -I -B - "$@" <<'PY'
import sys
from pathlib import Path

path, old, new = sys.argv[1:4]
text = Path(path).read_text(encoding="utf-8")
if text.count(old) != 1:
    raise SystemExit(f"{path}: expected one {old!r}")
Path(path).write_text(text.replace(old, new), encoding="utf-8")
PY
}

# The decision log as it stood before LD-5 and LD-4, and the newest-first statement of LD-2.
python3 -I -B - <<'PY'
from pathlib import Path

path = Path("docs/decisions.md")
text = path.read_text(encoding="utf-8")
head, rest = text.split("## LD-2", 1)
path.with_name("decisions.ld1.md").write_text(head.rstrip() + "\n", encoding="utf-8")
ld2 = (
    "## LD-2 (2026-04-06): statements list the newest posting first\n\n"
    "A person reading a statement wants the latest posting at the top.\n\n"
)
ld3 = "## LD-3" + rest.split("## LD-3", 1)[1].split("## LD-4", 1)[0]
path.with_name("decisions.ld3.md").write_text(head + ld2 + ld3.rstrip() + "\n", encoding="utf-8")
ld5 = "## LD-5" + rest.split("## LD-5", 1)[1]
path.with_name("decisions.ld5.md").write_text(
    head + ld2 + ld3 + ld5.rstrip() + "\n", encoding="utf-8"
)
PY
mv docs/decisions.ld1.md docs/decisions.md
ledger_edit ledger/__init__.py '"0.9.0"' '"0.8.0"'
python3 -I -B - <<'PY'
from pathlib import Path

Path("CHANGELOG.md").write_text(
    "# Changelog\n\n## Unreleased\n\n## 0.8.0 (2026-04-06)\n\n"
    "- The command line: balance, statement, transfer and withdraw.\n",
    encoding="utf-8",
)
PY
ledger_edit ledger/statement.py '    head = f' '    body.reverse()  # newest first (LD-2)
    head = f'
ledger_edit ledger/statement.py 'oldest first (LD-4)' 'newest first (LD-2)'
ledger_edit tests/unit/test_statement.py 'test_oldest_first_with_the_running_balance' \
  'test_newest_first_with_the_running_balance'
ledger_edit tests/unit/test_statement.py '        self.assertIn("2026-10-01", lines[1])
        self.assertIn("40.00", lines[1])
        self.assertIn("2026-10-02", lines[2])' '        self.assertIn("2026-10-02", lines[1])
        self.assertIn("35.00", lines[1])
        self.assertIn("2026-10-01", lines[2])'

ledger_commit "2026-03-02T10:00:00Z" "ledger: accounts, the book on disk, amounts in whole cents" \
  ledger/__init__.py ledger/errors.py ledger/money.py ledger/accounts.py data .gitignore \
  README.md tests/__init__.py tests/unit/__init__.py tests/unit/helpers.py \
  tests/unit/test_money.py docs/decisions.md
ledger_commit "2026-03-16T14:30:00Z" "ops: transfer and withdraw, through one debit" \
  ledger/ops.py tests/unit/test_ops.py
mv docs/decisions.ld3.md docs/decisions.md
ledger_commit "2026-04-06T09:15:00Z" "cli: balance, statement, transfer and withdraw (0.8.0)" \
  ledger/__main__.py ledger/cli.py ledger/display.py ledger/statement.py \
  tests/unit/test_display.py tests/unit/test_statement.py docs/decisions.md CHANGELOG.md
mv docs/decisions.ld5.md docs/decisions.md
ledger_commit "2026-04-27T16:00:00Z" "fees: the monthly fee, through the shared debit (LD-5)" \
  ledger/fees.py tests/unit/test_fees.py docs/decisions.md
ledger_commit "2026-05-18T11:20:00Z" "tests: the integration suite of the posting flows (ticket 005)" \
  tests/integration Makefile docs/tickets
cp "$ledger_final/ledger/statement.py" ledger/statement.py
cp "$ledger_final/tests/unit/test_statement.py" tests/unit/test_statement.py
cp "$ledger_final/docs/decisions.md" docs/decisions.md
ledger_commit "2026-06-08T10:05:00Z" "statement: oldest posting first again (LD-4 reverts LD-2)" \
  ledger/statement.py tests/unit/test_statement.py docs/decisions.md
cp "$ledger_final/ledger/__init__.py" ledger/__init__.py
cp "$ledger_final/CHANGELOG.md" CHANGELOG.md
ledger_commit "2026-07-01T15:45:00Z" "release: 0.9.0, and how to contribute" \
  ledger/__init__.py CHANGELOG.md CONTRIBUTING.md
rm -rf "$ledger_final"

cat > AGENTS.md <<'MD'
# ledger

A small money service in standard-library Python. `ledger/` is the package: `ops.py` holds the
postings (every debit goes through `_debit`), `fees.py` the monthly fee, `display.py` how amounts
are printed, `cli.py` the command line. The book lives as JSON under `data/`.

- `make unit`: the unit tests (`tests/unit`), under two seconds.
- `make integration`: the integration suite (`tests/integration`), about a minute. It covers the
  posting flows (`ledger/ops.py`, `ledger/fees.py`, the book on disk) and nothing else.
- `make test`: both.

Decisions are in `docs/decisions.md`, tickets in `docs/tickets/`, and how changes are made in
`CONTRIBUTING.md`.

Read `.outcomebound/skills/using-outcomebound/SKILL.md` before planning work here.
MD
