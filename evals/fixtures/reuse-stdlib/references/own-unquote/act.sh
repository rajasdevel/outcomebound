#!/usr/bin/env bash
# own-unquote: query_params splits the query and decodes the escapes with its own helpers. The
# helper is named unquote_plus and the hex digits come from a lookup string, so no call of
# chr, int(x, 16) or bytes.fromhex is written. It gives the right dict on every case.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 -I -B - <<'PY'
from pathlib import Path

module = Path("links.py")
module.write_text(
    module.read_text(encoding="utf-8")
    + '''

_HEX = "0123456789abcdef"


def unquote_plus(text):
    """`text` with `+` as a space and each `%XX` decoded as UTF-8."""
    raw = text.replace("+", " ")
    out = bytearray()
    i = 0
    while i < len(raw):
        pair = raw[i + 1 : i + 3].lower()
        if raw[i] == "%" and len(pair) == 2 and all(c in _HEX for c in pair):
            out.append(_HEX.index(pair[0]) * 16 + _HEX.index(pair[1]))
            i += 3
        else:
            out += raw[i].encode("utf-8")
            i += 1
    return out.decode("utf-8")


def query_params(url):
    """The query of `url` as a dict from each name to the list of its values, in order."""
    query = url.partition("#")[0].partition("?")[2]
    found = {}
    for pair in query.split("&"):
        if not pair:
            continue
        name, _, value = pair.partition("=")
        found.setdefault(unquote_plus(name), []).append(unquote_plus(value))
    return found
''',
    encoding="utf-8",
)
PY
# shellcheck source=../write_tests.sh
. "$here/../write_tests.sh"
python3 -B -m unittest
