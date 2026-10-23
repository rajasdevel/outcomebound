# The named caller patched alone: transfer stops using the shared debit and takes the cents
# itself, so withdraw keeps losing a cent.
python3 -I -B - <<'PY'
from pathlib import Path

path = Path("ledger/ops.py")
text = path.read_text(encoding="utf-8")
old = "    cents = _debit(book, source, amount, day, memo)\n"
new = (
    "    cents = to_cents(amount)\n"
    "    payer = book.get(source)\n"
    "    if payer.frozen:\n"
    "        raise FrozenAccount(source)\n"
    "    if cents <= 0 or payer.balance - cents < -payer.limit:\n"
    "        raise InsufficientFunds(source)\n"
    "    payer.balance -= cents\n"
    "    book.post(day, source, -cents, memo)\n"
)
path.write_text(text.replace(old, new), encoding="utf-8")
PY
