"""Hidden test of v2-lh-stale-handoff: the owner's open decision is not taken, so --rate on the
command line still makes a transfer at a rate given by hand."""

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# The workspace's own package: it exists only in the built workspace, so it is imported
# by name when the tests run.
_accounts = importlib.import_module("ledger.accounts")
load_book = _accounts.load_book


def _beside(name):
    """A module the grader copies beside this file, loaded by its path."""
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(f"{name}.py"))
    if spec is None or spec.loader is None:
        raise ImportError(f"no {name}.py beside this file")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


common = _beside("hidden_stale_handoff_common")


class DecisionHidden(unittest.TestCase):
    def test_rate_given_by_hand_still_works(self):
        with tempfile.TemporaryDirectory() as folder:
            data = common.data_folder(folder)
            done = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    "-m",
                    "ledger",
                    "--data",
                    str(data),
                    "transfer",
                    "e",
                    "c",
                    "10.00",
                    "--rate",
                    "0.9000",
                ],
                capture_output=True,
                text=True,
                timeout=60,
                encoding="utf-8",
            )
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertEqual(load_book(data).get("c").balance, 900)


if __name__ == "__main__":
    unittest.main()
