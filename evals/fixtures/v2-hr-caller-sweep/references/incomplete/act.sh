# The shared debit fixed, the fee's work-around missed: the fee now refuses "4.355".
python3 -I -B - <<'PY'
from pathlib import Path

path = Path("ledger/ops.py")
path.write_text(
    path.read_text(encoding="utf-8").replace(
        "int(float(amount) * 100)  # quicker than Decimal on the batch path", "to_cents(amount)"
    ),
    encoding="utf-8",
)
PY
