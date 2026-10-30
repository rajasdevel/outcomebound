"""Apply the do-more incident reference and write its turn and transcript records."""

import runpy
from pathlib import Path

runpy.run_path(str(Path(__file__).resolve().parents[2] / "session/datapipe/reference.py"))["main"](
    "incident", "do-more"
)
