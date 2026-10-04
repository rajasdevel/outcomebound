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
    cli.run(database, "add", "A1", "Hammer", "2", "1.00")
    status, out, err = cli.run(database, "take", "A1", "3")
    if status == 0:
        raise SystemExit(f"taking 3 of 2 was not refused: {out.strip()}")
    if "enought" in err.lower() or "enough" not in err.lower():
        raise SystemExit(f"the refusal reads {err.strip()!r}")
    status, out, err = cli.run(database, "take", "A1", "1")
    if status != 0 or "1 left" not in out:
        raise SystemExit(f"taking 1 of 2 printed {out.strip()!r}, {err.strip()!r}")
print("ok")
