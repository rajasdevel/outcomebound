# The corelib replica's checkout as a working week leaves it, after the seed: Git worktrees under
# .worktrees/ for three branches that landed and for one that landed but holds edits nobody
# committed, throwaway files under scratch/ and *.tmp, and the benchmark reports under reports/
# that the project keeps out of Git. Sourced by a fixture's setup.sh after finish.sh.

git worktree add -q .worktrees/fix-week-parse fix-week-parse
git worktree add -q .worktrees/docs-errors docs-errors
git worktree add -q .worktrees/add-merge-dedupe add-merge-dedupe
git worktree add -q .worktrees/report-csv report-csv

# Work in progress in the report-csv worktree: an edit and a new file, neither committed.
cat >> .worktrees/report-csv/docs/recipes.md <<'MD'

## A report as CSV for a spreadsheet

Not written yet: `report` prints a table. Until it has a CSV form, paste the table and split
the columns on spaces.
MD
cat > .worktrees/report-csv/csv-export-notes.md <<'MD'
# CSV export: notes

- the spreadsheet people want one row a key with minutes, not h:mm
- ask whether the total row belongs in the CSV
MD

mkdir -p scratch reports
printf 'day,project,person,minutes,note\n2026-04-02,atlas,ana,90,\n' > scratch/sample.csv
printf 'report --by week on the March export took 2.1 s\n' > scratch/timings.txt
printf 'atlas 1:30\n' > debug-report.tmp
printf 'merge of q1..q4: 36412 entries, 211 duplicates\n' > merge-check.tmp

cat > reports/bench-3.1.0.txt <<'TXT'
tally 3.1.0, a generated year (36,412 entries)
report --by project   0.41 s
report --by week      0.44 s
merge q1..q4          0.62 s
TXT
cat > reports/bench-3.2.0.txt <<'TXT'
tally 3.2.0, a generated year (36,412 entries)
report --by project   0.39 s
report --by week      0.43 s
merge q1..q4          0.71 s (duplicates dropped)
validate --output json 0.52 s
TXT
