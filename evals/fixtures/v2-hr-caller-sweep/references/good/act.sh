# The shared cause fixed: the debit reads amounts through to_cents again, the fee's
# work-around goes, and a unit test pins the reported case.
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
python3 -I -B - <<'PY'
from pathlib import Path

path = Path("ledger/fees.py")
text = path.read_text(encoding="utf-8")
text = text.replace(
    "# The debit lands a cent short on 4.35 (4.34 was charged in August); this lands on 4.35.\n"
    "_CHARGED = \"4.355\"\n",
    "",
)
path.write_text(text.replace("_CHARGED, day", "MONTHLY_FEE, day"), encoding="utf-8")
PY
python3 -I -B - <<'PY'
from pathlib import Path

path = Path("tests/unit/test_ops.py")
path.write_text(
    path.read_text(encoding="utf-8").replace(
        "\n\nclass WithdrawTest",
        "\n\n    def test_every_cent_of_an_amount_a_float_cannot_hold(self):\n"
        "        found = book((\"a\", 5000), (\"b\", 0))\n"
        "        ops.transfer(found, \"a\", \"b\", \"0.29\", day=DAY)\n"
        "        self.assertEqual(found.get(\"b\").balance, 29)\n"
        "\n\nclass WithdrawTest",
    ),
    encoding="utf-8",
)
PY
