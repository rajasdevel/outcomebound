# Sourced by the references that write query_params with urllib.parse.
python3 -I -B - <<'PY'
from pathlib import Path

module = Path("links.py")
text = module.read_text(encoding="utf-8")
text = text.replace(
    '"""Helpers for the links the site prints."""\n',
    '"""Helpers for the links the site prints."""\n\nfrom urllib.parse import parse_qs, urlparse\n',
)
module.write_text(
    text
    + '''

def query_params(url):
    """The query of `url` as a dict from each name to the list of its values, in order.

    `urllib.parse` splits the query and decodes `%XX` and `+`, so nothing here decodes by hand
    (no `chr`, `bytes.fromhex` or `int(x, 16)`). `keep_blank_values` keeps `flag` as `[""]`.
    """
    # The fragment is not part of the query: urlparse has already cut it off.
    return parse_qs(urlparse(url).query, keep_blank_values=True)
''',
    encoding="utf-8",
)
PY
