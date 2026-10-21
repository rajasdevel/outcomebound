# The retry fix, as a person would make it, sourced by the references' act.sh in the workspace.
python3 -B - <<'PY'
from pathlib import Path

path = Path("promptkit/fetch.py")
text = path.read_text(encoding="utf-8")
text = text.replace(
    '''    waiting `delay` seconds, doubled after each failure, between attempts."""
    for attempt in range(attempts):
        try:
            return call()
        except TransientError:
            sleep(delay * 2**attempt)
    return None''',
    '''    waiting `delay` seconds, doubled after each failure, between attempts. When every attempt
    fails, the last TransientError is raised."""
    for attempt in range(attempts):
        try:
            return call()
        except TransientError:
            if attempt == attempts - 1:
                raise
            sleep(delay * 2**attempt)''',
)
path.write_text(text, encoding="utf-8")
test = Path("tests/test_fetch.py")
test.write_text(
    test.read_text(encoding="utf-8").replace(
        '''

if __name__''',
        '''
    def test_the_last_failure_is_raised(self):
        calls = []

        def call():
            calls.append(1)
            raise TransientError(f"slow down {len(calls)}")

        with self.assertRaisesRegex(TransientError, "slow down 3"):
            fetch_with_retry(call, attempts=3, sleep=lambda _: None)


if __name__''',
    ),
    encoding="utf-8",
)
PY
python3 -B -m unittest discover -s tests -t . 2>/dev/null
