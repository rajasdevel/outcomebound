"""Check readable review inputs, not the meaning of an explanation."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "transcript_commands", Path(__file__).with_name("transcript_commands.py")
)
if spec is None or spec.loader is None:
    raise SystemExit("UNVERIFIED: transcript reader is unavailable")
reader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reader)


def main() -> int:
    values = {}
    for key in ("OUTCOMEBOUND_EVAL_ANSWER", "OUTCOMEBOUND_EVAL_TRANSCRIPT"):
        path = Path(os.environ.get(key, ""))
        if not path.is_file() or not path.read_text().strip():
            print("UNVERIFIED: missing readable " + key)
            return 1
        values[key] = path.read_text()
    if reader.execution_records(values["OUTCOMEBOUND_EVAL_TRANSCRIPT"]) is None:
        print("UNVERIFIED: execution transcript cannot be parsed")
        return 1
    print("observed: content reads, execution effects, meaning and guidance use require review")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
