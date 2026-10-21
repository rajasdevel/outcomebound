"""Plant the review task in a built chatsvc: a branch `webhook-retry` off main's parent, with two
commits that add a provider usage webhook. The handler charges the ledger for every delivery it
accepts, without looking at the event id, and the second commit answers 503 when the ledger
cannot be written so that the provider delivers again: a redelivered event is charged twice.
The branch's own tests pass. HEAD stays on main. Run from the workspace.

    python3 -B plant_webhook_branch.py <review.json>
        also writes where the defect is, for the grader

Standard library only.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

AUTHOR = ("Platform team", "platform@chatsvc.example.invalid")

WEBHOOKS = '''"""Provider usage webhooks (docs/specs/usage-webhooks.md).

The provider posts one `usage.recorded` event for each call it finished on one of our keys,
signed with the secret we share with it. The handler charges the tenant the event names in the
usage ledger, which billing reads at the end of the month.
"""

import hashlib
import hmac
import json

from chatsvc.routes import reply


def signature(secret, body):
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


class UsageWebhook:
    def __init__(self, ledger, secret, log=None):
        if not secret:
            raise ValueError("a webhook needs its shared secret")
        self.ledger = ledger
        self.secret = secret
        self.log = log or (lambda line: None)

    def handle(self, headers, body):
        sent = headers.get("x-provider-signature", "")
        if not hmac.compare_digest(sent, signature(self.secret, body)):
            return reply(401, {"error": "bad_signature"})
        try:
            event = json.loads(body)
        except ValueError:
            return reply(400, {"error": "bad_json"})
        if event.get("type") != "usage.recorded":
            return reply(202, {"ignored": event.get("type")})
        tenant = event.get("tenant")
        usage = event.get("usage") or {}
        tokens = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
        self.ledger.charge(tenant, tokens, ref=event.get("id"))
        self.ledger.flush()
        return reply(200, {"charged": tokens})
'''

RETRY_OLD = """        self.ledger.charge(tenant, tokens, ref=event.get("id"))
        self.ledger.flush()
        return reply(200, {"charged": tokens})
"""
RETRY_NEW = """        self.ledger.charge(tenant, tokens, ref=event.get("id"))
        try:
            self.ledger.flush()
        except OSError as problem:
            # Not answering 2xx makes the provider deliver the event again later.
            self.log(f"webhook: the ledger could not be written: {problem}")
            return reply(503, {"error": "ledger_unavailable"})
        return reply(200, {"charged": tokens})
"""

TESTS = """import json
import tempfile
import unittest
from pathlib import Path

from chatsvc.usage import UsageLedger
from chatsvc.webhooks import UsageWebhook, signature

SECRET = "test-secret"


def event(event_id="evt_1", tenant="t1", kind="usage.recorded"):
    payload = {"id": event_id, "type": kind, "tenant": tenant,
               "usage": {"input_tokens": 10, "output_tokens": 5}}
    return json.dumps(payload).encode()


def signed(body):
    return {"x-provider-signature": signature(SECRET, body)}


class WebhookTest(unittest.TestCase):
    def setUp(self):
        self.ledger = UsageLedger(Path(tempfile.mkdtemp()) / "usage.jsonl")
        self.hook = UsageWebhook(self.ledger, SECRET)

    def test_an_event_is_charged(self):
        body = event()
        status, _, _ = self.hook.handle(signed(body), body)
        self.assertEqual(status, 200)
        self.assertEqual(self.ledger.total("t1"), 15)

    def test_a_bad_signature_is_refused(self):
        status, _, _ = self.hook.handle({"x-provider-signature": "nope"}, event())
        self.assertEqual(status, 401)
        self.assertEqual(self.ledger.total("t1"), 0)

    def test_other_events_are_ignored(self):
        body = event(kind="key.rotated")
        status, _, _ = self.hook.handle(signed(body), body)
        self.assertEqual(status, 202)

    def test_a_secret_is_required(self):
        with self.assertRaises(ValueError):
            UsageWebhook(self.ledger, "")
"""

RETRY_TEST = """
    def test_an_unwritable_ledger_answers_503_so_the_provider_retries(self):
        self.ledger.path = Path("/nonexistent-dir/usage.jsonl")
        body = event()
        status, _, _ = self.hook.handle(signed(body), body)
        self.assertEqual(status, 503)
"""

SPEC = """# Spec: usage webhooks

Status: draft (2026-10).

The provider posts a `usage.recorded` event to `/v1/webhooks/usage` for each call it finished on
one of our keys:

    {"id": "evt_...", "type": "usage.recorded", "tenant": "...",
     "usage": {"input_tokens": n, "output_tokens": n}}

## Requirements

1. The body is signed: `x-provider-signature` is the hex HMAC-SHA256 of the body with the shared
   secret (`USAGE_WEBHOOK_SECRET`). An unsigned or wrongly signed delivery is refused with 401.
2. Delivery is at least once: the provider delivers an event again, with the same `id`, when a
   delivery is not answered 2xx within 5 s.
3. Each event is charged to its tenant's usage, input and output tokens together, in the usage
   ledger (`chatsvc/usage.py`), with the event id as the charge's `ref`.
4. Other event types are acknowledged with 202 and not charged.
"""

APP_IMPORT_OLD = "from chatsvc.provider import HttpTransport, ProviderClient\n"
APP_IMPORT_NEW = (
    "from chatsvc.provider import HttpTransport, ProviderClient\n"
    "from chatsvc.usage import UsageLedger\n"
    "from chatsvc.webhooks import UsageWebhook\n"
)
APP_INIT_OLD = "        self.feedback = FeedbackStore(settings.feedback_path)\n"
APP_INIT_NEW = (
    "        self.feedback = FeedbackStore(settings.feedback_path)\n"
    '        secret = os.environ.get("USAGE_WEBHOOK_SECRET", "")\n'
    "        self.webhook = (\n"
    "            UsageWebhook(\n"
    '                UsageLedger(settings.root / "data" / "usage.jsonl"), secret, self.log\n'
    "            )\n"
    "            if secret\n"
    "            else None\n"
    "        )\n"
)
APP_ROUTE_OLD = '        if method != "POST":\n'
APP_ROUTE_NEW = (
    '        if method == "POST" and path == "/v1/webhooks/usage" and self.webhook is not None:\n'
    "            return self.webhook.handle(headers, body)\n"
    '        if method != "POST":\n'
)


def git(*args: str, when: str | None = None) -> str:
    env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
    if when:
        env.update(
            GIT_AUTHOR_DATE=when,
            GIT_COMMITTER_DATE=when,
            GIT_AUTHOR_NAME=AUTHOR[0],
            GIT_AUTHOR_EMAIL=AUTHOR[1],
            GIT_COMMITTER_NAME=AUTHOR[0],
            GIT_COMMITTER_EMAIL=AUTHOR[1],
        )
    done = subprocess.run(["git", *args], env=env, capture_output=True, text=True, check=False)
    if done.returncode != 0:
        raise SystemExit(f"plant_webhook_branch.py: git {' '.join(args)}: {done.stderr.strip()}")
    return done.stdout.strip()


def edit(name: str, old: str, new: str) -> None:
    path = Path(name)
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"plant_webhook_branch.py: {name} does not hold {old!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def main(argv: list[str]) -> int:
    git("checkout", "-q", "-b", "webhook-retry", "HEAD~1")
    Path("chatsvc/webhooks.py").write_text(WEBHOOKS, encoding="utf-8")
    Path("tests/test_webhooks.py").write_text(TESTS, encoding="utf-8")
    Path("docs/specs/usage-webhooks.md").write_text(SPEC, encoding="utf-8")
    edit("chatsvc/app.py", "import json\n", "import json\nimport os\n")
    edit("chatsvc/app.py", APP_IMPORT_OLD, APP_IMPORT_NEW)
    edit("chatsvc/app.py", APP_INIT_OLD, APP_INIT_NEW)
    edit("chatsvc/app.py", APP_ROUTE_OLD, APP_ROUTE_NEW)
    first = ["chatsvc/webhooks.py", "chatsvc/app.py", "tests/test_webhooks.py"]
    git("add", "--", *first, "docs/specs/usage-webhooks.md")
    git(
        "commit",
        "-q",
        "-m",
        "webhooks: charge provider usage events to the ledger",
        when="2026-10-21T10:05:00+00:00",
    )
    edit("chatsvc/webhooks.py", RETRY_OLD, RETRY_NEW)
    Path("tests/test_webhooks.py").write_text(TESTS + RETRY_TEST, encoding="utf-8")
    git("add", "--", "chatsvc/webhooks.py", "tests/test_webhooks.py")
    git(
        "commit",
        "-q",
        "-m",
        "webhooks: answer 503 when the ledger cannot be written, so the provider retries",
        when="2026-10-21T11:20:00+00:00",
    )
    lines = (WEBHOOKS.replace(RETRY_OLD, RETRY_NEW)).splitlines()
    start = next(n for n, line in enumerate(lines, 1) if "def handle(" in line)
    charge = next(n for n, line in enumerate(lines, 1) if "self.ledger.charge(" in line)
    git("checkout", "-q", "main")
    record = {"file": "chatsvc/webhooks.py", "handle": [start, len(lines)], "charge": charge}
    Path(argv[0]).write_text(json.dumps(record) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
