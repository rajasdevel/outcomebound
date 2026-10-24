# Shared by the references of this fixture: functions only, sourced by act.sh. Each runs in the
# built workspace.

# add_health_route [no-served|literal]: the /health route in app.py, listed in ROUTES and, unless
# the mode is no-served, in SERVED; with literal, the version is written into the code.
add_health_route() {
  HEALTH_MODE="${1:-}" python3 -I -B - <<'PY'
import os
from pathlib import Path

mode = os.environ["HEALTH_MODE"]
path = Path("app.py")
text = path.read_text(encoding="utf-8")
version = '"3.7.2"' if mode == "literal" else "VERSION"
text = text.replace("import os\n", "import json\nimport os\n", 1)
if mode != "no-served":
    text = text.replace('SERVED = ("/greet",)', 'SERVED = ("/greet", "/health")')
text = text.replace(
    'ROUTES = {"/greet": greet}',
    "def health(query):\n"
    '    """The service is up: its status and its version."""\n'
    f'    return 200, json.dumps({{"status": "ok", "version": {version}}}) + "\\n"\n\n\n'
    'ROUTES = {"/greet": greet, "/health": health}',
)
path.write_text(text, encoding="utf-8")
PY
}

# add_health_test: a unit test for the route.
add_health_test() {
  python3 -I -B - <<'PY'
from pathlib import Path

path = Path("tests/test_app.py")
text = path.read_text(encoding="utf-8")
text = text.replace("import unittest\n", "import json\nimport unittest\n", 1)
text = text.replace(
    '\n\nif __name__ == "__main__":',
    "\n    def test_health_reports_status_and_version(self):\n"
    '        status, body = app.route("/health", {})\n'
    "        self.assertEqual(status, 200)\n"
    '        self.assertEqual(json.loads(body), {"status": "ok", "version": app.VERSION})\n'
    '\n\nif __name__ == "__main__":',
)
path.write_text(text, encoding="utf-8")
PY
}

unit_tests() { python3 -B -m unittest discover -s tests; }

# request URL: print the body of a GET of URL; python3, since curl is not in every image.
request() {
  python3 -I -B -c 'import sys, urllib.request; sys.stdout.write(urllib.request.urlopen(sys.argv[1], timeout=5).read().decode())' "$1"
}

# run_service pid|port: start the service on a free port, request /health, then end the process
# this function started: by its process id, or (port) by the port it listens on. Nothing else is
# ended, and no process is left running.
run_service() {
  local how="$1" port pid
  port="$(python3 -I -B -c 'import socket; s = socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1])')"
  PORT="$port" python3 -B app.py &
  pid=$!
  # Expanded now: the trap runs at exit, when this function's locals are gone.
  trap "kill $pid 2>/dev/null || true" EXIT
  for _ in $(seq 1 50); do
    request "http://127.0.0.1:$port/greet" >/dev/null 2>&1 && break
    sleep 0.1
  done
  request "http://127.0.0.1:$port/health"
  if [ "$how" = port ] && command -v lsof >/dev/null 2>&1; then
    kill $(lsof -ti ":$port" -sTCP:LISTEN)
  else
    kill "$pid"
  fi
  wait "$pid" 2>/dev/null || true
  trap - EXIT
}
