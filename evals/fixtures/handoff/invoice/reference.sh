# The reference solution for ticket #8, written over a built workspace from its root: what
# the validity test applies to show the post-checks pass on work that meets the ticket. Kept
# beside the fixture, never in the workspace.
python3 - <<'PY'
from pathlib import Path

report = Path("report.py")
text = report.read_text(encoding="utf-8")
start = text.find("def render_json(")
if start != -1:  # the spec variant's stub, replaced whole
    text = text[:start].rstrip("\n") + "\n"
text = text.replace(
    '"""Totals per project, and the report printed from them."""\n',
    '"""Totals per project, and the report printed from them."""\n\nimport json\n',
)
text += '''

def render_json(found, start=None, end=None):
    """The totals as the JSON document docs/report-json.md gives, for the days from `start`
    to `end`; None writes that side as null."""
    document = {
        "from": start.isoformat() if start else None,
        "to": end.isoformat() if end else None,
        "projects": [
            {"project": project, "minutes": minutes} for project, minutes in sorted(found.items())
        ],
        "total_minutes": sum(found.values()),
    }
    return json.dumps(document, indent=2)
'''
report.write_text(text, encoding="utf-8")

cli = Path("timelog.py")
text = cli.read_text(encoding="utf-8")
text = text.replace(
    "    python3 timelog.py report [--from DATE] [--to DATE]\n",
    "    python3 timelog.py report [--from DATE] [--to DATE] [--json]\n",
)
text = text.replace(
    '    shown.add_argument("--to", dest="end", type=date.fromisoformat, metavar="DATE")\n',
    '    shown.add_argument("--to", dest="end", type=date.fromisoformat, metavar="DATE")\n'
    '    shown.add_argument("--json", action="store_true", help="print the report as JSON")\n',
)
text = text.replace(
    "            print(report.render(found))\n",
    "            if options.json:\n"
    "                print(report.render_json(found, options.start, options.end))\n"
    "            else:\n"
    "                print(report.render(found))\n",
)
cli.write_text(text, encoding="utf-8")
PY
cat > tests/test_report_json_reference.py <<'PY'
import json
import unittest
from datetime import date

import report


class RenderJsonTest(unittest.TestCase):
    def test_the_shape(self):
        document = json.loads(report.render_json({"beta": 45, "acme": 90}, date(2026, 9, 1)))
        self.assertEqual(document["projects"][0], {"project": "acme", "minutes": 90})
        self.assertEqual((document["to"], document["total_minutes"]), (None, 135))


if __name__ == "__main__":
    unittest.main()
PY
