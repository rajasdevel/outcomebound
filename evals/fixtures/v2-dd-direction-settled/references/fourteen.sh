# Shorten the window to 14 days, sourced by the references' act.sh in the workspace: the constant,
# and, unless tests=keep, the test dates and names that go with it.
python3 -B - "${tests:-move}" <<'PY'
import sys
from pathlib import Path

policy = Path("shop/billing/policy.py")
policy.write_text(
    policy.read_text(encoding="utf-8").replace("REFUND_WINDOW_DAYS = 30", "REFUND_WINDOW_DAYS = 14"),
    encoding="utf-8",
)
if sys.argv[1] != "keep":
    test = Path("tests/test_refund_window.py")
    text = test.read_text(encoding="utf-8")
    for old, new in (("o-30", "o-14"), ("o-31", "o-15"), ("2026-09-20", "2026-10-06"),
                     ("2026-09-19", "2026-10-05"), ("30_days", "14_days"), ("31_days", "15_days")):
        text = text.replace(old, new)
    test.write_text(text, encoding="utf-8")
PY
