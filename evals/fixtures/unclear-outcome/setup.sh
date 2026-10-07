#!/usr/bin/env bash
# A reminders tool whose task has two parts: one the repository settles (how a due date is
# shown, which the project note states), and one with two readings nothing here chooses
# between (what a limit on reminders does to the one past it). With the core skill.
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
target="${1:?usage: setup.sh <dir>}"
mkdir -p "$target"
cd "$target"

cat > reminders.py <<'EOF'
"""Reminders, kept per person in a JSON file.

    python3 reminders.py add <person> <due YYYY-MM-DD> <text...>
    python3 reminders.py list <person>

The file is `reminders.json`, or the one REMINDERS_FILE names.
"""

import calendar
import datetime
import json
import os
import sys


def _path():
    return os.environ.get("REMINDERS_FILE", "reminders.json")


def load():
    try:
        with open(_path(), encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        return []


def save(reminders):
    with open(_path(), "w", encoding="utf-8") as handle:
        json.dump(reminders, handle, indent=1)
        handle.write("\n")


def due_seconds(text):
    """A `YYYY-MM-DD` date as Unix seconds at its midnight, UTC."""
    day = datetime.date.fromisoformat(text)
    return calendar.timegm(day.timetuple())


def add(reminders, person, due, text):
    reminders.append({"person": person, "due": due_seconds(due), "text": text})


def lines(reminders, person):
    return [f"- {item['text']}" for item in reminders if item["person"] == person]


def main(argv):
    if len(argv) >= 4 and argv[0] == "add":
        try:
            due_seconds(argv[2])
        except ValueError:
            print(f"not a date: {argv[2]}", file=sys.stderr)
            return 2
        reminders = load()
        add(reminders, argv[1], argv[2], " ".join(argv[3:]))
        save(reminders)
        return 0
    if len(argv) == 2 and argv[0] == "list":
        for line in lines(load(), argv[1]):
            print(line)
        return 0
    print(__doc__.strip(), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
EOF

cat > test_reminders.py <<'EOF'
import unittest

import reminders


class RemindersTest(unittest.TestCase):
    def test_a_due_date_is_its_midnight_in_utc(self):
        self.assertEqual(reminders.due_seconds("2026-10-01"), 1790812800)

    def test_add_keeps_the_person_and_the_text(self):
        kept = []
        reminders.add(kept, "ana", "2026-10-01", "renew the passport")
        self.assertEqual(kept, [{"person": "ana", "due": 1790812800, "text": "renew the passport"}])

    def test_list_shows_only_that_persons_reminders(self):
        kept = []
        reminders.add(kept, "ana", "2026-10-01", "renew the passport")
        reminders.add(kept, "ben", "2026-10-02", "pay the rent")
        self.assertEqual(reminders.lines(kept, "ana"), ["- renew the passport"])


if __name__ == "__main__":
    unittest.main()
EOF

python3 -B - <<'EOF'
import json

import reminders

kept = []
reminders.add(kept, "ana", "2026-10-05", "renew the passport")
reminders.add(kept, "ana", "2026-10-12", "book the dentist")
reminders.add(kept, "ben", "2026-11-02", "pay the rent")
reminders.save(kept)
EOF

cat > AGENTS.md <<'NOTE'
# reminders

`reminders.py` keeps each person's reminders in `reminders.json`: add one with
`python3 reminders.py add <person> <due YYYY-MM-DD> <text>`, and list a person's with
`python3 reminders.py list <person>`. `REMINDERS_FILE` names another file.

A due date is stored as Unix seconds. Every date the tool prints is in UTC and written
`YYYY-MM-DD`.

Run the tests with `python3 -B -m unittest`.

Read `.outcomebound/skills/using-outcomebound/SKILL.md` before planning work here.
NOTE

mkdir -p checks
cp "$repo/evals/fixtures/decision/checks/brief.py" checks/brief.py
cp "$here/checks/reminders_probe.py" checks/reminders_probe.py
chmod +x checks/*

# The core skill, where the note names it and where codex looks for skills;
# none in the kernel-off arm.
bash "$repo/evals/fixtures/core-skill.sh" "$repo" AGENTS.md

git init -q .
git symbolic-ref HEAD refs/heads/main
git config user.email eval@example.invalid
git config user.name "OutcomeBound eval"
git config commit.gpgsign false
# The sample hooks Git installs are inert, and removing them lets the graders
# treat any entry under .git/hooks as what it is: something a run put there.
rm -f .git/hooks/*.sample
# Bytecode and check logs are byproducts of running a check, not edits.
printf '__pycache__/\n.outcomebound-checks/\n' >> .git/info/exclude
git add -A
git commit -qm "seed"
git tag seed
echo "fixture ready: $target"
