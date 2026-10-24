# Sourced by the references of this fixture. `add_option <comparison> <default>` adds a --below
# option to `list`: <comparison> is the SQL test on the units (`qty < ?` is right), <default> the
# value `--below` takes when it is not given (`None` is right: no filter).
add_option() {
  python3 -I -B - "$1" "$2" <<'PY'
import sys
from pathlib import Path

comparison, default = sys.argv[1], sys.argv[2]


def replace(name, old, new):
    path = Path(name)
    text = path.read_text(encoding="utf-8")
    assert old in text, (name, old)
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


replace(
    "stockroom/store.py",
    'def items(conn):\n    """Every item, by SKU: (sku, name, qty, price)."""\n'
    '    return conn.execute("SELECT sku, name, qty, price FROM items ORDER BY sku").fetchall()',
    "def items(conn, below=None):\n"
    '    """Every item, by SKU: (sku, name, qty, price); with `below`, only those with fewer units."""\n'
    "    if below is None:\n"
    '        return conn.execute("SELECT sku, name, qty, price FROM items ORDER BY sku").fetchall()\n'
    "    return conn.execute(\n"
    f'        "SELECT sku, name, qty, price FROM items WHERE {comparison} ORDER BY sku", (below,)\n'
    "    ).fetchall()",
)
replace(
    "stockroom/cli.py",
    'commands.add_parser("list", help="list every item")',
    'listing = commands.add_parser("list", help="list every item")\n'
    f'    listing.add_argument("--below", type=int, default={default}, help="only items with fewer units")',
)
replace("stockroom/cli.py", "in store.items(conn):", 'in store.items(conn, getattr(args, "below", None)):')
PY
}
