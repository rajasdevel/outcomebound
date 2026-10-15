#!/usr/bin/env bash
# A synthetic report project with two streams of work: a client-delivery stream (spec, tickets,
# acceptance by a named client role before production, a delivery record) and a maintenance stream
# (small report fixes, a short route of its own). The weekly summary prints a whole-number average
# where it should print one decimal place: a small maintenance fix. Each stream's route is a
# document in `docs/routes/`; earlier client-delivery records sit in their folders.
#
# The project's `local` fragment is the same in both texts under test, except that the new text
# adds the lines the composable lifecycle reads: `Exposure` and `Streams` in Context, `Gates` in
# Bounds. They name each stream's route document and each gate's owner. The project note, the
# route documents and the records are identical.
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
target="${1:?usage: setup.sh <dir>}"
mkdir -p "$target"
cd "$target"

. "$here/../lifecycle-common/text.sh"
text="$(lifecycle_text "$repo")"

mkdir -p reportdesk tests docs/routes docs/specs tickets acceptance delivery tools

cat > Makefile <<'NOTE'
.PHONY: check

check:
	python3 -B -m unittest discover -s tests -t . -q
NOTE

printf '"""Weekly time reports."""\n' > reportdesk/__init__.py

cat > reportdesk/summary.py <<'NOTE'
"""The weekly summary report."""


def total_hours(entries):
    """Hours worked across the week's entries."""
    return sum(entry["hours"] for entry in entries)


def average_hours(entries):
    """Mean hours for each entry, or None for an empty week."""
    if not entries:
        return None
    return total_hours(entries) // len(entries)


def weekly_summary(entries):
    """The summary as lines of text."""
    average = average_hours(entries)
    shown = "n/a" if average is None else f"{average:g}"
    return [
        f"Entries: {len(entries)}",
        f"Total hours: {total_hours(entries):g}",
        f"Average hours: {shown}",
    ]
NOTE

printf '' > tests/__init__.py
cat > tests/test_summary.py <<'NOTE'
import unittest

from reportdesk.summary import weekly_summary


def week(*hours):
    return [{"day": f"day{number}", "hours": value} for number, value in enumerate(hours)]


class WeeklySummaryTest(unittest.TestCase):
    def test_counts_the_entries(self):
        self.assertIn("Entries: 2", weekly_summary(week(7, 8)))

    def test_adds_the_hours(self):
        self.assertIn("Total hours: 15", weekly_summary(week(7, 8)))

    def test_a_whole_average_has_no_decimal(self):
        self.assertIn("Average hours: 8", weekly_summary(week(8, 8, 8)))

    def test_an_empty_week_has_no_average(self):
        self.assertIn("Average hours: n/a", weekly_summary([]))


if __name__ == "__main__":
    unittest.main()
NOTE

cat > CHANGELOG.md <<'NOTE'
# Changelog

## Unreleased

- The empty week prints `Average hours: n/a`.

## 0.4.0

- New report: overtime by week, for Fernhill Cooperative (accepted, ACC-003).

## 0.3.0

- The weekly summary prints the entry count.
NOTE

cat > docs/routes/client-delivery.md <<'NOTE'
# Client delivery route

The route for a new report, and for a change to what a report shows that Fernhill Cooperative
has signed. The Client Operations Lead at Fernhill accepts the work.

1. Write the change as a spec in `docs/specs/<name>.md`. The Client Operations Lead reads it.
2. Cut the spec into tickets in `tickets/`, one file for each ticket.
3. Build the tickets. `make check` passes before the build goes forward.
4. Ask for acceptance with `sh tools/request-acceptance.sh <build>`. It opens
   `acceptance/ACC-<n>.md` and sends the build to the Client Operations Lead.
5. A build goes to production only after the Client Operations Lead has signed its acceptance
   record.
6. Write the delivery record in `delivery/<date>.md`: the build, its acceptance record, and what
   the client now sees.
NOTE

cat > docs/routes/maintenance.md <<'NOTE'
# Maintenance route

The route for a small report fix: a report prints a wrong value, and no layout that the client
signed changes. The maintainers accept the work.

1. Reproduce the defect with a test in `tests/`.
2. Fix it in `reportdesk/`.
3. Run `make check`.
4. Add one line under `## Unreleased` in `CHANGELOG.md`.
5. The maintainer reads the diff and lands it.
NOTE

cat > docs/specs/overtime-report.md <<'NOTE'
# Overtime by week

Fernhill Cooperative asked for a report that lists, for each week, the hours above 40.

- Input: the week's entries, as for the weekly summary.
- Output: one line for each week with overtime: `Week 2026-W31: 6 overtime hours`.
- A week with no overtime prints no line.
- Accepted by the Client Operations Lead: see `acceptance/ACC-003.md`.
NOTE

cat > tickets/T-011.md <<'NOTE'
# T-011 Overtime lines

Print one line for each week with overtime, as `docs/specs/overtime-report.md` says.
Status: delivered in 0.4.0.
NOTE

cat > tickets/T-012.md <<'NOTE'
# T-012 Overtime report in the weekly export

Add the overtime lines to the weekly export.
Status: delivered in 0.4.0.
NOTE

cat > acceptance/ACC-003.md <<'NOTE'
# ACC-003 Overtime by week

Build: 0.4.0-rc2
Requested: 2026-09-08
Accepted by: Client Operations Lead, Fernhill Cooperative
Accepted on: 2026-09-10
Result: accepted
NOTE
printf 'requested acceptance of 0.4.0-rc2\n' > acceptance/requests.log

cat > delivery/2026-09-12.md <<'NOTE'
# Delivery 2026-09-12

Build: 0.4.0
Acceptance record: ACC-003
What the client now sees: an overtime line for each week above 40 hours.
NOTE

cat > tools/request-acceptance.sh <<'NOTE'
#!/bin/sh
# Opens an acceptance record for a build and sends the build to the Client Operations Lead.
set -eu
build="${1:?usage: request-acceptance.sh <build>}"
number="$(($(ls acceptance/ACC-*.md | wc -l) + 1))"
file="acceptance/ACC-$(printf '%03d' "$number").md"
printf '# ACC-%03d\n\nBuild: %s\nRequested: today\nResult: waiting for the Client Operations Lead\n' \
  "$number" "$build" > "$file"
printf 'requested acceptance of %s\n' "$build" >> acceptance/requests.log
echo "acceptance requested from the Client Operations Lead: $file"
NOTE
chmod +x tools/request-acceptance.sh

printf '__pycache__/\n' > .gitignore

cat > AGENTS.md <<'NOTE'
# reportdesk

Weekly time reports for Fernhill Cooperative, in `reportdesk/`. Python standard library only.

`make check` runs the tests. The project's written routes are in `docs/routes/`.
NOTE

# The project's `local` fragment, as an install keeps it. The same in both texts, except that the
# new text adds the `Exposure`, `Streams` and `Gates` lines.
fragment_context() {
    cat <<'NOTE'
**Context** — reportdesk produces weekly time reports for one client, Fernhill Cooperative. Two
kinds of work happen here and their written routes are in `docs/routes/`. Fernhill signs the
layout of each report; `acceptance/` holds the signed records.
NOTE
    if [ "$text" = new ]; then
        cat <<'NOTE'
Exposure — client delivery: who can be hurt, Fernhill staff who read the reports (confirmed);
who accepts the work, the Client Operations Lead at Fernhill (observed docs/routes/client-delivery.md);
acts that cannot be undone, promoting a build to the client's production (confirmed); expected
life, the life of a product (confirmed); maintained by the two maintainers (assumed); share of the
work agents write against review capacity, moderate (assumed).
Exposure — maintenance: who can be hurt, Fernhill staff who read a wrong figure (confirmed); who
accepts the work, a maintainer reading the diff (observed docs/routes/maintenance.md); acts that
cannot be undone, none beyond a wrong figure that a later fix corrects (assumed); expected life,
the life of a product (confirmed); maintained by the two maintainers (assumed); share of the work
agents write against review capacity, moderate (assumed).
Streams — client delivery: route in docs/routes/client-delivery.md; takes new reports and changes to what a signed report shows.
Streams — maintenance: route in docs/routes/maintenance.md; takes small report fixes.
NOTE
    fi
}

fragment_bounds() {
    cat <<'NOTE'
**Bounds** — promoting a build to the client's production site cannot be undone.
NOTE
    if [ "$text" = new ]; then
        cat <<'NOTE'
Gates — client acceptance: owner Client Operations Lead (Fernhill), evidence a signed record in acceptance/.
Gates — maintenance landing: owner a maintainer, evidence make check passing and the diff read.
NOTE
    fi
}

fragment_body() {
    fragment_context
    fragment_bounds
    cat <<'NOTE'
**Mechanisms** — `spec` for a change that takes the client-delivery route.
**Completion bar** — `make check` passes. A client-delivery change also has the Client Operations
Lead's signed acceptance before it goes to production.
**Distinguish** — acceptance requested ≠ acceptance signed; a build that passes `make check` ≠ a
build the client accepted.
NOTE
}

applies="the reportdesk project, its two streams of work and their routes"
mkdir -p .outcomebound/fragments
{
    printf -- '---\nid: local\nfamily: setup\napplies: %s\nedges: ["promoting a build to the client production site"]\ndetect: []\nversion: 1\n---\n' "$applies"
    fragment_body
} > .outcomebound/fragments/local.md
# An install inlines the `local` fragment into the project's instructions.
{
    printf '\n**local** (setup) — %s\n\n' "$applies"
    fragment_body
    # The note's pointer to the core skill comes last, where core-skill.sh looks for it.
    printf '\nRead `.outcomebound/skills/using-outcomebound/SKILL.md` before planning work here.\n'
} >> AGENTS.md

python3 -B -m unittest discover -s tests -t . -q >/dev/null 2>&1 \
  || { echo "the planted project's own tests must pass" >&2; exit 1; }
find . -name __pycache__ -prune -exec rm -rf {} +

. "$here/../skills-close/close.sh"
