# The spec package's executable part for ticket #8, written into the workspace from its root
# before the seed commit: the stub of `report.render_json`, and the package's fixed tests,
# each failing on the seed for the reason the package names.
python3 - <<'PY'
from pathlib import Path

report = Path("report.py")
report.write_text(
    report.read_text(encoding="utf-8").replace(
        '"""Totals per project, and the report printed from them."""\n\n',
        '"""Totals per project, and the report printed from them."""\n\n'
        "from datetime import date\n\n",
    )
    + '''

def render_json(found: dict[str, int], start: date | None = None, end: date | None = None) -> str:
    """The totals `found`, minutes per project, as the JSON document docs/report-json.md
    gives, for the days from `start` to `end`; None writes that side as null.

    Returns the document as text with no line end after it. Raises nothing.
    """
    raise NotImplementedError("ticket #8: render_json")
''',
    encoding="utf-8",
)
PY
cat > tests/test_report_json.py <<'PY'
"""Ticket #8: `timelog report --json` prints the report that invoice.py reads.

These tests are the hand-off package's, and they are fixed: make them pass, and change or
remove none of them.
"""

import contextlib
import io
import json
import os
import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest import mock

import invoice
import report
import timelog

LOG = (
    "2026-08-31\tacme\t60\t\n"
    "2026-09-01\tacme\t90\tkickoff\n"
    "2026-09-15\tbeta\t45\t\n"
    "2026-09-30\tacme\t30\t\n"
)
SEPTEMBER = {
    "from": "2026-09-01",
    "to": "2026-09-30",
    "projects": [{"project": "acme", "minutes": 120}, {"project": "beta", "minutes": 45}],
    "total_minutes": 165,
}


def run(*argv):
    """timelog's exit status, standard output and standard error, over a log holding LOG."""
    out, err = io.StringIO(), io.StringIO()
    with tempfile.TemporaryDirectory() as directory:
        log = Path(directory) / "timelog.tsv"
        log.write_text(LOG, encoding="utf-8")
        with (
            mock.patch.dict(os.environ, {"TIMELOG": str(log)}),
            contextlib.redirect_stdout(out),
            contextlib.redirect_stderr(err),
        ):
            try:
                status = timelog.main(list(argv))
            except SystemExit as stop:
                status = stop.code
    return status, out.getvalue(), err.getvalue()


class RenderJsonTest(unittest.TestCase):
    def test_render_json_gives_the_shape(self):
        text = report.render_json({"beta": 45, "acme": 120}, date(2026, 9, 1), date(2026, 9, 30))
        self.assertEqual(json.loads(text), SEPTEMBER)

    def test_render_json_writes_a_day_not_given_as_null(self):
        text = report.render_json({"acme": 60}, None, None)
        self.assertEqual(
            json.loads(text),
            {"from": None, "to": None, "projects": [{"project": "acme", "minutes": 60}],
             "total_minutes": 60},
        )

    def test_render_json_of_no_entries_is_the_empty_shape(self):
        text = report.render_json({}, date(2027, 1, 1), None)
        self.assertEqual(
            json.loads(text),
            {"from": "2027-01-01", "to": None, "projects": [], "total_minutes": 0},
        )


class ReportJsonCommandTest(unittest.TestCase):
    def test_report_json_prints_the_document_alone(self):
        status, out, err = run("report", "--json", "--from", "2026-09-01", "--to", "2026-09-30")
        self.assertEqual(status, 0, err)
        self.assertEqual(json.loads(out), SEPTEMBER)

    def test_invoice_reads_what_report_json_prints(self):
        status, out, err = run("report", "--json", "--from", "2026-09-01", "--to", "2026-09-30")
        self.assertEqual(status, 0, err)
        billed = invoice.invoice(invoice.read_report(out), Decimal("90"))
        self.assertEqual(
            [line.split() for line in billed.splitlines()],
            [
                ["period", "2026-09-01", "to", "2026-09-30"],
                ["acme", "2:00", "180.00"],
                ["beta", "0:45", "67.50"],
                ["total", "2:45", "247.50"],
            ],
        )


if __name__ == "__main__":
    unittest.main()
PY
