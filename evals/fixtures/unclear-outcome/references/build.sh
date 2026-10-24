# shellcheck shell=bash
# Shared by the references: the two changes to reminders.py and its tests, built in the current
# directory. DATE_MODE is `utc` or `local` (what `list` shows a due date in); CAP_MODE is
# `refuse` (a sixth reminder is refused and the five kept), `drop` (the oldest is dropped) or
# `none`. A reference sources this file and calls `build_reminders`.
build_reminders() {
  DATE_MODE="${1:?utc or local}" CAP_MODE="${2:?refuse, drop or none}" python3 -I -B - <<'PY'
import os
from pathlib import Path

date_mode, cap_mode = os.environ["DATE_MODE"], os.environ["CAP_MODE"]


def swap(text, old, new):
    assert old in text, old
    return text.replace(old, new, 1)


source = Path("reminders.py").read_text(encoding="utf-8")
tests = Path("test_reminders.py").read_text(encoding="utf-8")

zone = "datetime.timezone.utc" if date_mode == "utc" else ""
source = swap(
    source,
    '''def lines(reminders, person):
    return [f"- {item['text']}" for item in reminders if item["person"] == person]
''',
    f'''def due_text(seconds):
    """Unix seconds as `YYYY-MM-DD`{", in UTC" if date_mode == "utc" else ""}."""
    moment = datetime.datetime.fromtimestamp(seconds{", " + zone if zone else ""})
    return moment.strftime("%Y-%m-%d")


def lines(reminders, person):
    return [
        f"- {{due_text(item['due'])}} {{item['text']}}"
        for item in reminders
        if item["person"] == person
    ]
''',
)
tests = swap(
    tests,
    'self.assertEqual(reminders.lines(kept, "ana"), ["- renew the passport"])',
    'self.assertEqual(reminders.lines(kept, "ana"), ["- 2026-10-01 renew the passport"])',
)
if date_mode == "utc":
    tests = swap(
        tests,
        '\n\nif __name__ == "__main__":',
        '''
    def test_list_shows_each_due_date_in_utc(self):
        kept = []
        reminders.add(kept, "ana", "2026-10-01", "renew the passport")
        self.assertEqual(reminders.due_text(1790812800), "2026-10-01")


if __name__ == "__main__":''',
    )

if cap_mode == "refuse":
    source = swap(
        source,
        '''def add(reminders, person, due, text):
    reminders.append(''',
        '''MAX_REMINDERS = 5


class LimitReached(Exception):
    pass


def add(reminders, person, due, text):
    if sum(1 for item in reminders if item["person"] == person) >= MAX_REMINDERS:
        raise LimitReached(f"{person} already has {MAX_REMINDERS} reminders")
    reminders.append(''',
    )
    source = swap(
        source,
        '''        add(reminders, argv[1], argv[2], " ".join(argv[3:]))
        save(reminders)''',
        '''        try:
            add(reminders, argv[1], argv[2], " ".join(argv[3:]))
        except LimitReached as problem:
            print(problem, file=sys.stderr)
            return 1
        save(reminders)''',
    )
    tests = swap(
        tests,
        '\n\nif __name__ == "__main__":',
        '''
    def test_a_sixth_reminder_is_refused_and_the_five_are_kept(self):
        kept = []
        for day in range(1, 6):
            reminders.add(kept, "ana", f"2026-10-0{day}", f"errand {day}")
        with self.assertRaises(reminders.LimitReached):
            reminders.add(kept, "ana", "2026-10-09", "the sixth errand")
        self.assertEqual(len(kept), 5)


if __name__ == "__main__":''',
    )
elif cap_mode == "drop":
    source = swap(
        source,
        '''def add(reminders, person, due, text):
    reminders.append(''',
        '''MAX_REMINDERS = 5


def add(reminders, person, due, text):
    mine = [item for item in reminders if item["person"] == person]
    if len(mine) >= MAX_REMINDERS:
        reminders.remove(mine[0])
    reminders.append(''',
    )
    tests = swap(
        tests,
        '\n\nif __name__ == "__main__":',
        '''
    def test_a_sixth_reminder_drops_the_oldest(self):
        kept = []
        for day in range(1, 7):
            reminders.add(kept, "ana", f"2026-10-0{day}", f"errand {day}")
        self.assertEqual([item["text"] for item in kept][0], "errand 2")


if __name__ == "__main__":''',
    )

Path("reminders.py").write_text(source, encoding="utf-8")
Path("test_reminders.py").write_text(tests, encoding="utf-8")
PY
}
