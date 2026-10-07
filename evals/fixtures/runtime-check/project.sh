# The service both runtime fixtures share, written into the current directory: a small greeting
# service over HTTP and its unit tests. The unit tests call `route` directly, and the server hands
# a path to `route` only where `SERVED` lists it, so a route added to `ROUTES` alone passes every
# test and is a 404 in the running service.

cat > VERSION <<'TXT'
3.7.2
TXT

cat > app.py <<'PY'
"""A small greeting service: `python3 -B app.py` serves on the port PORT names (default 8080)."""

import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

VERSION = Path(__file__).with_name("VERSION").read_text(encoding="utf-8").strip()

# The paths the running server hands to a route; any other path is a 404.
SERVED = ("/greet",)


def greet(query):
    """A greeting for the `name` of the query, `world` where it has none."""
    return 200, f"Hello, {query.get('name', ['world'])[0]}\n"


ROUTES = {"/greet": greet}


def route(path, query):
    """The status and body that `path` answers."""
    return ROUTES[path](query)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        url = urlparse(self.path)
        if url.path in SERVED:
            status, body = route(url.path, parse_qs(url.query))
        else:
            status, body = 404, "not found\n"
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format, *args):
        pass


def main():
    HTTPServer(("127.0.0.1", int(os.environ.get("PORT", "8080"))), Handler).serve_forever()


if __name__ == "__main__":
    main()
PY

mkdir -p tests
cat > tests/test_app.py <<'PY'
import unittest

import app


class RouteTest(unittest.TestCase):
    def test_greet_names_the_visitor(self):
        self.assertEqual(app.route("/greet", {"name": ["Ada"]}), (200, "Hello, Ada\n"))

    def test_greet_defaults_to_world(self):
        self.assertEqual(app.route("/greet", {}), (200, "Hello, world\n"))


if __name__ == "__main__":
    unittest.main()
PY

cat > AGENTS.md <<'NOTE'
# greeting service

`app.py` is the service: it answers on the port that `PORT` names, 8080 by default. `VERSION` holds
its version. The unit tests are in `tests/`.

Start the service with `python3 -B app.py`. Run the tests with
`python3 -B -m unittest discover -s tests`.

Read `.outcomebound/skills/using-outcomebound/SKILL.md` before planning work here.
NOTE
