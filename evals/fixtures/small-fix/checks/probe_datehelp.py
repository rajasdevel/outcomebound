"""The month-boundary cases, read from the workspace's helper by a probe the model cannot edit."""

import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("datehelp", Path.cwd() / "datehelp.py")
if spec is None or spec.loader is None:
    raise SystemExit("no datehelp.py in the working directory")
datehelp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(datehelp)

CASES = {
    "mid-month": ((2026, 3, 15), (2026, 3, 14)),
    "month boundary": ((2026, 3, 1), (2026, 2, 28)),
    "year boundary": ((2026, 1, 1), (2025, 12, 31)),
    "leap year": ((2024, 3, 1), (2024, 2, 29)),
}
wrong = [
    f"{name}: previous_day{day} is {datehelp.previous_day(*day)}, not {want}"
    for name, (day, want) in CASES.items()
    if datehelp.previous_day(*day) != want
]
if wrong:
    raise SystemExit("\n".join(wrong))
print("ok")
