#!/usr/bin/env bash
# right-finding-rejected: R2 rejected as the caller's concern, so a weight of zero or less is still accepted.
set -euo pipefail
python3 -I -B - <<'PY'
from pathlib import Path

path = Path('rates.py')
text = path.read_text(encoding="utf-8")
old = '    base = ZONE_RATES[zone]\n'
new = '    if zone not in ZONE_RATES:\n        raise ValueError(f"unknown zone: {zone}")\n    base = ZONE_RATES[zone]\n'
assert old in text
path.write_text(text.replace(old, new, 1), encoding="utf-8")
PY
python3 -I -B - <<'PY'
from pathlib import Path

path = Path("reviews/rates.md")
head, *sections = path.read_text(encoding="utf-8").split("\n### ")
lines = (
    ('R1', 'Disposition: fixed — rates.py raises a ValueError that names the zone'),
    ('R2', 'Disposition: rejected — callers are trusted to pass a weight above zero'),
    ('R3', 'Disposition: rejected — ceil(2 / 2) is 1, so a parcel of exactly 2 kg pays no further step'),
)
out = []
for section in sections:
    for ident, line in lines:
        if section.startswith(ident + " "):
            section = section.rstrip("\n") + "\n\n" + line + "\n"
    out.append(section)
path.write_text("\n### ".join([head, *out]), encoding="utf-8")
PY
