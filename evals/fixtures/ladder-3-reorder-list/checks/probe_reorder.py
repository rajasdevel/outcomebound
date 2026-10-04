"""The change, judged through the command line against a database of the probe's own."""

import importlib.util
import tempfile
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "cli_probe", Path(__file__).resolve().parent / "cli_probe.py"
)
if _SPEC is None or _SPEC.loader is None:
    raise SystemExit("no cli_probe.py beside this probe")
cli = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(cli)


with tempfile.TemporaryDirectory() as scratch:
    database = cli.fresh(scratch)
    for sku, qty in (("A1", "2"), ("B2", "5"), ("C3", "10")):
        cli.run(database, "add", sku, "Item", qty, "1.00")
    for arguments, want in (
        (("list", "--below", "5"), ["A1"]),
        (("list", "--below", "11"), ["A1", "B2", "C3"]),
        (("list",), ["A1", "B2", "C3"]),
    ):
        status, out, err = cli.run(database, *arguments)
        got = [sku for sku, _price in cli.listed(out)]
        if status != 0 or got != want:
            raise SystemExit(f"{' '.join(arguments)} listed {got}, not {want}: {err.strip()}")
print("ok")
