"""Grade one overnight claim outside the workspace."""

import importlib.util
import runpy
from pathlib import Path

here = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("long_datapipe", here / "long_datapipe.py")
if spec is None or spec.loader is None:
    raise ValueError("missing shared grader")
shared = importlib.util.module_from_spec(spec)
spec.loader.exec_module(shared)
runpy.run_path(str(here / "overnight.py"))["grade"](shared)
