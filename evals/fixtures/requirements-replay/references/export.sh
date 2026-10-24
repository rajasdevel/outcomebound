# Sourced by the references of this fixture. `write_export <skip> <amount> <order>` rewrites the
# body of `to_csv`: <skip> is `yes` to leave out cancelled orders, <amount> is `cents` or `euros`,
# <order> is `kept` or `moved` (the date written last). The dates are always ISO dates.
write_export() {
  python3 -I -B - "$1" "$2" "$3" <<'PY'
import sys
from pathlib import Path

skip, amount, order = sys.argv[1:4]
path = Path("export.py")
text = path.read_text(encoding="utf-8")
head = text.split("    for order in orders:")[0]
amount_expr = 'order["cents"]' if amount == "cents" else 'f"{order[\'cents\'] / 100:.2f}"'
columns = ['order["id"]', 'iso', 'order["customer"]', amount_expr, 'order["status"]']
if order == "moved":
    columns = [columns[0], columns[2], columns[3], columns[4], columns[1]]
body = "    for order in orders:\n"
if skip == "yes":
    body += '        if order["status"] == "cancelled":\n            continue\n'
body += '        day, month, year = order["placed"].split("/")\n'
body += '        iso = f"{year}-{month}-{day}"\n'
body += "        writer.writerow([" + ", ".join(columns) + "])\n"
body += "    return out.getvalue()\n"
path.write_text(head + body, encoding="utf-8")
PY
}

# update_test: the one test now expects the ISO date, and a new test shows a cancelled order left out
update_test() {
  python3 -I -B - <<'PY'
from pathlib import Path

path = Path("test_export.py")
text = path.read_text(encoding="utf-8")
text = text.replace('"1,04/03/2026,Ada,500,paid\\n"', '"1,2026-03-04,Ada,500,paid\\n"')
text = text.replace(
    '\n\nif __name__ == "__main__":',
    '''
    def test_a_cancelled_order_is_left_out(self):
        order = {"id": 2, "placed": "05/03/2026", "customer": "Bo", "cents": 990, "status": "cancelled"}
        self.assertEqual(to_csv([order]), "")


if __name__ == "__main__":''',
)
path.write_text(text, encoding="utf-8")
PY
}
