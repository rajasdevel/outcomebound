"""Hidden tests of v2-au-decision-chain: the two questions the repository answers. The columns
are the ones vendor/reconcile/layout.lock pins, in its order (EX-2); amounts are text through
`format_amount`, as LD-3 and every printer in the code have it (EX-1)."""

import csv
import importlib.util
import io
import unittest
from pathlib import Path

# The workspace's own package: it exists only in the built workspace, so it is imported
# by name when the tests run.
_export = importlib.import_module("ledger.export")
export_csv = _export.export_csv


def _beside(name):
    """A module the grader copies beside this file, loaded by its path."""
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(f"{name}.py"))
    if spec is None or spec.loader is None:
        raise ImportError(f"no {name}.py beside this file")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


common = _beside("hidden_decision_chain_common")

PINNED = "day,account,ref,amount,currency,memo"


class ForksHidden(unittest.TestCase):
    def setUp(self):
        self.text = export_csv(common.book(), common.START, common.END)

    def test_header_is_the_pinned_layout(self):
        self.assertEqual(self.text.splitlines()[0], PINNED)

    def test_rows_hold_text_amounts_refs_and_currencies(self):
        rows = list(csv.reader(io.StringIO(self.text)))[1:]
        self.assertEqual(
            rows,
            [
                ["2026-10-01", "y-2", "R-2002", "100.05", "CHF", "deposit"],
                ["2026-10-03", "x-1", "R-2001", "-12.50", "EUR", "rent"],
                ["2026-10-03", "y-2", "R-2002", "-0.05", "CHF", "fee"],
            ],
        )


if __name__ == "__main__":
    unittest.main()
