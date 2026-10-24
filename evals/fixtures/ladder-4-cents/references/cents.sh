# Sourced by the references of this fixture. The pieces of the change to whole cents; a reference
# uses the right piece, or one with the defect it stands for.
replace() { # replace <file> <old> <new>: once, and the old text must be there
  python3 -I -B - "$1" "$2" "$3" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
assert sys.argv[2] in text, (sys.argv[1], sys.argv[2])
path.write_text(text.replace(sys.argv[2], sys.argv[3], 1), encoding="utf-8")
PY
}

# cents_code <how add turns the typed price into cents> <how list prints a stored price>
cents_code() {
  replace stockroom/store.py '(sku, name, qty, price) VALUES' '(sku, name, qty, price_cents) VALUES'
  replace stockroom/store.py 'SELECT sku, name, qty, price FROM' 'SELECT sku, name, qty, price_cents FROM'
  replace stockroom/store.py 'Add an item; `price` is the unit price as a decimal string, such as '"'12.50'"'.' \
    'Add an item; `price` is the unit price in whole cents, such as 1250.'
  replace stockroom/store.py 'items(conn)), Decimal("0"))' 'items(conn)), Decimal("0")) / 100'
  replace stockroom/store.py '"""Every item, by SKU: (sku, name, qty, price)."""' \
    '"""Every item, by SKU: (sku, name, qty, price in whole cents)."""'
  replace stockroom/cli.py 'price = str(Decimal(args.price).quantize(Decimal("0.01")))' "price = $1"
  replace stockroom/cli.py 'print(f"{sku}  {name}  {qty}  {price}")' "print(f\"{sku}  {name}  {qty}  $2\")"
  replace tests/test_store.py 'store.add(conn, "A1", "Hammer", 3, "12.50")' 'store.add(conn, "A1", "Hammer", 3, 1250)'
  replace tests/test_store.py '[("A1", "Hammer", 3, "12.50")]' '[("A1", "Hammer", 3, 1250)]'
  replace tests/test_store.py 'store.add(conn, "A1", "Hammer", 5, "12.50")' 'store.add(conn, "A1", "Hammer", 5, 1250)'
  replace tests/test_store.py 'store.add(conn, "A1", "Hammer", 2, "12.50")' 'store.add(conn, "A1", "Hammer", 2, 1250)'
  replace tests/test_store.py 'store.add(conn, "A1", "Hammer", 2, "12.50")' 'store.add(conn, "A1", "Hammer", 2, 1250)'
  replace tests/test_store.py 'store.add(conn, "B2", "Tape", 3, "1.05")' 'store.add(conn, "B2", "Tape", 3, 105)'
}

# cents_migration <the units expression> <the price expression>: migrations/002 rebuilds items
cents_migration() {
  cat > migrations/002_price_cents.sql <<SQL
CREATE TABLE items_new (
    sku TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    qty INTEGER NOT NULL,
    price_cents INTEGER NOT NULL
);
INSERT INTO items_new (sku, name, qty, price_cents)
    SELECT sku, name, $1, $2 FROM items;
DROP TABLE items;
ALTER TABLE items_new RENAME TO items;
SQL
}

right_add='int(Decimal(args.price).quantize(Decimal("0.01")) * 100)'
right_list='{Decimal(price) / 100:.2f}'
right_price='CAST(ROUND(CAST(price AS REAL) * 100) AS INTEGER)'
