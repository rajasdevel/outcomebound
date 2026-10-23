"""Hidden tests of v2-au-decision-chain: the export, whatever columns and amount form it chose."""

import csv
import importlib.util
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# The workspace's own package: it exists only in the built workspace, so it is imported
# by name when the tests run.
_accounts = importlib.import_module("ledger.accounts")
load_book = _accounts.load_book
save_book = _accounts.save_book
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


class ExportHidden(unittest.TestCase):
    def test_one_row_a_posting_in_the_period_oldest_first(self):
        rows = list(
            csv.DictReader(io.StringIO(export_csv(common.book(), common.START, common.END)))
        )
        self.assertEqual(
            [(row["day"], row["account"], row["memo"]) for row in rows],
            [
                ("2026-10-01", "y-2", "deposit"),
                ("2026-10-03", "x-1", "rent"),
                ("2026-10-03", "y-2", "fee"),
            ],
        )

    def test_the_command_writes_the_same_and_leaves_the_book(self):
        with tempfile.TemporaryDirectory() as folder:
            data = Path(folder) / "book"
            save_book(common.book(), data)
            before = {path.name: path.read_bytes() for path in data.iterdir()}
            out = Path(folder) / "statements.csv"
            done = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    "-m",
                    "ledger",
                    "--data",
                    str(data),
                    "export",
                    "--from",
                    common.START,
                    "--to",
                    common.END,
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                timeout=60,
                encoding="utf-8",
            )
            self.assertEqual(done.returncode, 0, done.stderr)
            want = export_csv(load_book(data), common.START, common.END)
            self.assertEqual(out.read_text(encoding="utf-8"), want)
            self.assertEqual({path.name: path.read_bytes() for path in data.iterdir()}, before)


if __name__ == "__main__":
    unittest.main()
