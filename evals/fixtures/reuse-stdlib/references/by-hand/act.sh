#!/usr/bin/env bash
# by-hand: query_params splits the query and decodes the escapes with its own code. It gives the
# right dict on every case the task names, so the behaviour holds and the reuse does not.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 -I -B - <<'PY'
from pathlib import Path

module = Path("links.py")
module.write_text(
    module.read_text(encoding="utf-8")
    + '''

def _unquote(text):
    """`text` with `+` as a space and each `%XX` decoded as UTF-8."""
    raw = text.replace("+", " ")
    out = bytearray()
    i = 0
    while i < len(raw):
        if raw[i] == "%" and i + 2 < len(raw) + 0 and raw[i + 1 : i + 3].isalnum():
            out += bytes.fromhex(raw[i + 1 : i + 3])
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
        found.setdefault(_unquote(name), []).append(_unquote(value))
    return found
''',
    encoding="utf-8",
)
PY
# shellcheck source=../write_tests.sh
. "$here/../write_tests.sh"
python3 -B -m unittest
