# Shared by the references of this fixture: functions only, sourced by act.sh. Each runs in the
# built workspace.

# write_slug PATTERN [nostrip]: slug in textutil.py. PATTERN is the regular expression whose runs
# become one dash; with nostrip, the dashes at either end are left.
write_slug() {
  SLUG_PATTERN="$1" SLUG_MODE="${2:-}" python3 -I -B - <<'PY'
import os
from pathlib import Path

pattern, mode = os.environ["SLUG_PATTERN"], os.environ["SLUG_MODE"]
path = Path("textutil.py")
text = path.read_text(encoding="utf-8")
text = text.replace('them."""\n', 'them."""\n\nimport re\n', 1)
lower = f're.sub(r"{pattern}", "-", title.lower())'
body = lower if mode == "nostrip" else lower + '.strip("-")'
text += (
    "\n\ndef slug(title):\n"
    '    """`title` in lower case, each run of other characters one `-`, none at either end."""\n'
    f"    return {body}\n"
)
path.write_text(text, encoding="utf-8")
PY
}

# add_slug_tests [weak]: unit tests for slug; with weak, only a title that ends in a letter.
add_slug_tests() {
  SLUG_TESTS="${1:-}" python3 -I -B - <<'PY'
import os
from pathlib import Path

path = Path("tests/test_textutil.py")
text = path.read_text(encoding="utf-8")
text = text.replace("from textutil import shout\n", "from textutil import shout, slug\n", 1)
cases = (
    "\n\nclass SlugTest(unittest.TestCase):\n"
    "    def test_punctuation_and_case(self):\n"
    '        self.assertEqual(slug("Hello World"), "hello-world")\n'
)
if os.environ["SLUG_TESTS"] != "weak":
    cases = cases.replace('slug("Hello World")', 'slug("Hello, World!")') + (
        "\n    def test_runs_and_ends(self):\n"
        '        self.assertEqual(slug("  Many   spaces  "), "many-spaces")\n'
        '        self.assertEqual(slug("---"), "")\n'
        "\n    def test_digits_are_kept(self):\n"
        '        self.assertEqual(slug("Version 3.7.2"), "version-3-7-2")\n'
    )
text = text.replace('\n\nif __name__ == "__main__":', cases + '\n\nif __name__ == "__main__":')
path.write_text(text, encoding="utf-8")
PY
}

unit_tests() { python3 -B -m unittest discover -s tests; }

# run_service: start the service on a free port, request /greet, and end the process this
# function started. No process is left running.
run_service() {
  local port pid
  port="$(python3 -I -B -c 'import socket; s = socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1])')"
  PORT="$port" python3 -B app.py &
  pid=$!
  trap 'kill "$pid" 2>/dev/null || true' EXIT
  for _ in $(seq 1 50); do
    curl -s -o /dev/null "http://127.0.0.1:$port/greet" && break
    sleep 0.1
  done
  curl -s "http://127.0.0.1:$port/greet"
  kill "$pid"
  wait "$pid" 2>/dev/null || true
  trap - EXIT
}
