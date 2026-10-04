# The reference solution for ticket #9, written over a built workspace from its root: what
# the validity test applies to show the post-checks pass on work that meets the ticket. Kept
# beside the fixture, never in the workspace.
cat > entries.py <<'PY'
"""One entry of the time log."""

from datetime import date
from typing import NamedTuple


class Entry(NamedTuple):
    """Time spent on a project on one day, and its tags, in the order given, each once."""

    day: date
    project: str
    minutes: int
    note: str = ""
    tags: tuple[str, ...] = ()
PY
python3 - <<'PY'
from pathlib import Path

store = Path("store.py")
text = store.read_text(encoding="utf-8")
text = text.replace(
    '''def format_line(entry):
    """The entry as one line of the log, without its line end."""
    return "\\t".join((entry.day.isoformat(), entry.project, str(entry.minutes), entry.note))
''',
    '''def format_line(entry):
    """The entry as one line of the log, without its line end: four fields, and a fifth
    holding the tags where it has any."""
    fields = [entry.day.isoformat(), entry.project, str(entry.minutes), entry.note]
    if entry.tags:
        fields.append(",".join(entry.tags))
    return "\\t".join(fields)
''',
)
text = text.replace(
    '''    fields = line.split("\\t")
    if len(fields) != FIELDS:
        raise LogError(f"line {number}: expected {FIELDS} fields, found {len(fields)}")
    day, project, minutes, note = fields
    try:
        return Entry(date.fromisoformat(day), project, int(minutes), note)
''',
    '''    fields = line.split("\\t")
    if len(fields) not in (FIELDS, FIELDS + 1):
        raise LogError(f"line {number}: expected {FIELDS} fields, found {len(fields)}")
    day, project, minutes, note = fields[:FIELDS]
    tags = tuple(tag for tag in fields[FIELDS].split(",") if tag) if len(fields) > FIELDS else ()
    try:
        return Entry(date.fromisoformat(day), project, int(minutes), note, tags)
''',
)
store.write_text(text, encoding="utf-8")

report = Path("report.py")
text = report.read_text(encoding="utf-8")
start = text.find("def totals(")
end = text.find("def render(")
text = text[:start] + '''def totals(entries, start=None, end=None, tag=None):
    """Minutes per project over the entries from `start` to `end`, both days included, that
    carry `tag`; None leaves that side open, or takes every entry."""
    found = {}
    for entry in entries:
        if start is not None and entry.day < start:
            continue
        if end is not None and entry.day > end:
            continue
        if tag is not None and tag not in entry.tags:
            continue
        found[entry.project] = found.get(entry.project, 0) + entry.minutes
    return found


''' + text[end:]
report.write_text(text, encoding="utf-8")

cli = Path("timelog.py")
text = cli.read_text(encoding="utf-8")
replacements = (
    (
        "    python3 timelog.py add DATE PROJECT DURATION [NOTE]\n"
        "    python3 timelog.py report [--from DATE] [--to DATE]\n",
        "    python3 timelog.py add DATE PROJECT DURATION [NOTE] [--tag TAG]...\n"
        "    python3 timelog.py report [--from DATE] [--to DATE] [--tag TAG]\n",
    ),
    ("import os\nimport sys\n", "import os\nimport re\nimport sys\n"),
    (
        "from entries import Entry\n",
        "from entries import Entry\n\nTAG = re.compile(r\"[a-z0-9-]{1,20}\")\n",
    ),
    (
        '    add.add_argument("note", nargs="?", default="")\n',
        '    add.add_argument("note", nargs="?", default="")\n'
        '    add.add_argument("--tag", dest="tags", action="append", default=[], metavar="TAG")\n',
    ),
    (
        '    shown.add_argument("--to", dest="end", type=date.fromisoformat, metavar="DATE")\n',
        '    shown.add_argument("--to", dest="end", type=date.fromisoformat, metavar="DATE")\n'
        '    shown.add_argument("--tag", metavar="TAG", help="total only the entries tagged TAG")\n',
    ),
    (
        "    entry = Entry(options.day, options.project, parse_duration(options.duration), options.note)\n",
        "    for tag in options.tags:\n"
        "        if not TAG.fullmatch(tag):\n"
        "            raise ValueError(f\"invalid tag: {tag!r}\")\n"
        "    minutes = parse_duration(options.duration)\n"
        "    tags = tuple(dict.fromkeys(options.tags))\n"
        "    entry = Entry(options.day, options.project, minutes, options.note, tags)\n",
    ),
    (
        "            found = report.totals(store.load(log_path()), options.start, options.end)\n",
        "            entries = store.load(log_path())\n"
        "            found = report.totals(entries, options.start, options.end, options.tag)\n",
    ),
)
for old, new in replacements:
    if old not in text:
        raise SystemExit(f"reference: timelog.py does not hold {old!r}")
    text = text.replace(old, new)
cli.write_text(text, encoding="utf-8")

doc = Path("docs/log-format.md")
text = doc.read_text(encoding="utf-8")
text = text.replace(
    "line end. Blank lines are skipped.\n",
    "line end. Blank lines are skipped.\n\n"
    "An entry with tags has a fifth field after the note: its tags, joined by commas, in the\n"
    "order given, each once. A tag is 1 to 20 characters, each a lowercase letter, a digit or\n"
    "`-`. An entry with no tags has four fields, so a line of four fields reads as no tags.\n",
)
doc.write_text(text, encoding="utf-8")
PY
cat > tests/test_tags_reference.py <<'PY'
import unittest
from datetime import date

import store
from entries import Entry


class TagLineTest(unittest.TestCase):
    def test_tags_round_trip(self):
        entry = Entry(date(2026, 9, 2), "acme", 60, "", ("a", "b"))
        self.assertEqual(store.parse_line(store.format_line(entry), 1), entry)


if __name__ == "__main__":
    unittest.main()
PY
