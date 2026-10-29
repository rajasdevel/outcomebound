"""Choose the next frozen person turn outside the workspace."""

import runpy
from pathlib import Path

runpy.run_path(str(Path(__file__).with_name("dialogue.py")))["main"]()
