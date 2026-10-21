# The changelog line, the pull request description and the follow-up issue, with no private fact.
python3 -B - <<'PY'
from pathlib import Path

log = Path("CHANGELOG.md")
log.write_text(
    log.read_text(encoding="utf-8").replace(
        "## Unreleased\n",
        "## Unreleased\n\n- fetch: when every attempt fails, `fetch_with_retry` raises the last "
        "error instead of returning None.\n",
    ),
    encoding="utf-8",
)
PY
mkdir -p pr issues
cat > pr/description.md <<'MD'
# fetch: raise the last error when every attempt fails

`fetch_with_retry` returned None after its last failed attempt. A caller that stores the result,
such as the prompt cache, then kept None as if it were a prompt.

It now raises the last `TransientError` once every attempt has failed, and it no longer waits
after the last attempt. A success on any attempt is returned as before.

Reproduction (synthetic): call `fetch_with_retry` with a function that always raises
`TransientError`; before this change it returns None, after it the error is raised. The new
test `test_the_last_failure_is_raised` does this.

Context: the failures came from the index throttling requests. The rate at which it throttles is
UNVERIFIED: no public source states it.

Follow-up: the wait between attempts has no upper limit (see issues/retry-wait-cap.md).
MD
cat > issues/retry-wait-cap.md <<'MD'
# fetch: cap the wait between retries

`fetch_with_retry` doubles its wait after each failed attempt and has no upper limit, so a large
`attempts` can wait for hours. Give the wait a maximum, as an argument with a sensible default,
and test that no wait exceeds it.
MD
