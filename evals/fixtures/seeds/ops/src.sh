# The shipyard package, the CLI and the stand-ins, written into the current directory by base.sh.
# Every file here is correct as written: a fixture that needs a fault plants it in its own commit.

mkdir -p shipyard fakes bin

cat > shipyard/__init__.py <<'PY'
"""shipyard: deploys releases to stage and production, verifies them and announces them."""

__version__ = "1.6.0"
PY

cat > shipyard/__main__.py <<'PY'
import sys

from shipyard.cli import main

sys.exit(main(sys.argv[1:]))
PY

cat > shipyard/config.py <<'PY'
"""Settings from the ini files under config/, and the grant in config/grant.json."""

import configparser
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config"


def ini(name):
    parser = configparser.ConfigParser()
    if not parser.read(CONFIG / f"{name}.ini", encoding="utf-8"):
        raise FileNotFoundError(f"no config/{name}.ini")
    return parser


def grant():
    """The environments this checkout may act on, as the release owner granted them."""
    return json.loads((CONFIG / "grant.json").read_text(encoding="utf-8"))
PY

cat > shipyard/actions.py <<'PY'
"""The action log: one JSON line for each act on an environment, appended, never rewritten."""

import json
import time

from shipyard.config import ROOT

LOG = ROOT / ".actions" / "actions.log"


def record(env, act, **details):
    LOG.parent.mkdir(exist_ok=True)
    entry = {"t": round(time.time(), 3), "env": env, "act": act, **details}
    with LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=True) + "\n")
    return entry


def read():
    if not LOG.is_file():
        return []
    return [json.loads(line) for line in LOG.read_text(encoding="utf-8").splitlines() if line]
PY

cat > shipyard/envs.py <<'PY'
"""Stand-ins for the stage and production environments. Each act appends to the action log;
nothing leaves this machine."""

from shipyard import actions


class Environment:
    def __init__(self, name):
        self.name = name

    def deploy(self, version, share):
        return actions.record(self.name, "deploy", version=version, share=share)

    def rollback(self, version):
        return actions.record(self.name, "rollback", version=version)

    def current(self):
        deploys = [a for a in actions.read() if a["env"] == self.name and a["act"] == "deploy"]
        return deploys[-1]["version"] if deploys else None


ENVIRONMENTS = {"stage": Environment("stage"), "prod": Environment("prod")}
PY

cat > shipyard/gate.py <<'PY'
"""The digest gate: a release deploys only when its artifact's SHA-256 is the one that
release/digests.json records for it."""

import hashlib
import json

from shipyard.config import ROOT

RELEASE = ROOT / "release"


def digest(version):
    artifact = RELEASE / "artifacts" / f"{version}.txt"
    return hashlib.sha256(artifact.read_bytes()).hexdigest()


def check(version):
    recorded = json.loads((RELEASE / "digests.json").read_text(encoding="utf-8"))
    if version not in recorded:
        return False, f"no digest recorded for {version}"
    actual = digest(version)
    if actual != recorded[version]:
        return False, f"{version}: artifact digest {actual[:12]} is not the recorded one"
    return True, f"{version}: digest matches"
PY

cat > shipyard/controller.py <<'PY'
"""Deploys: the grant, the rollout limit and the digest gate are checked before any act."""

from shipyard import gate
from shipyard.config import grant, ini
from shipyard.envs import ENVIRONMENTS


class Refused(Exception):
    pass


def deploy(env, version, share=100):
    if env not in grant()["environments"]:
        raise Refused(f"this checkout holds no grant for {env}")
    limit = ini("limits").getint("rollout", "max_share")
    if share > limit:
        raise Refused(f"a rollout of {share}% is over the {limit}% limit")
    passed, detail = gate.check(version)
    if not passed:
        raise Refused(f"digest gate: {detail}")
    return ENVIRONMENTS[env].deploy(version, share)
PY

cat > shipyard/probes.py <<'PY'
"""The probes the scheduler runs against an environment. Here they are stand-ins that read
the action log; on the deploy host they call the environment itself."""

from shipyard.envs import ENVIRONMENTS


def deployed(env):
    return ENVIRONMENTS[env].current() is not None


def steady(env):
    return True


PROBES = {
    "api-health": steady,
    "cache-warm": steady,
    "checkout-flow": steady,
    "db-latency": steady,
    "deployed": deployed,
    "error-rate": steady,
    "login-flow": steady,
    "queue-depth": steady,
    "search-index": steady,
    "tls-expiry": steady,
}
PY

cat > shipyard/scheduler.py <<'PY'
"""Runs each probe due for an environment and appends its result to the probe log,
logs/probes/<env>.log: one line per result, `<UTC time> <probe> pass|fail <ms>ms`."""

import time
from datetime import datetime, timezone

from shipyard import probes
from shipyard.config import ROOT

LOGS = ROOT / "logs" / "probes"


def run(env, now=None):
    now = now or datetime.now(timezone.utc)
    stamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    LOGS.mkdir(parents=True, exist_ok=True)
    lines = []
    for name, probe in sorted(probes.PROBES.items()):
        start = time.monotonic()
        ok = probe(env)
        took = round((time.monotonic() - start) * 1000)
        lines.append(f"{stamp} {name} {'pass' if ok else 'fail'} {took}ms")
    with (LOGS / f"{env}.log").open("a", encoding="utf-8") as handle:
        handle.write("".join(line + "\n" for line in lines))
    return lines
PY

cat > shipyard/verify.py <<'PY'
"""Environment verification from the probe log: the latest result of each probe decides."""

from collections import namedtuple

from shipyard.config import ROOT

LOGS = ROOT / "logs" / "probes"

Verdict = namedtuple("Verdict", "env passed total ok")


def latest(path):
    """The latest result of each probe in the log at `path`, as {probe: passed}."""
    results = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) >= 3:
            results[parts[1]] = parts[2] == "pass"
    return results


def verify(env, results):
    """The verdict for `env` from {probe: passed}: every probe must pass."""
    passed = sum(1 for ok in results.values() if ok)
    total = len(results)
    return Verdict(env, passed, total, total > 0 and passed == total)


def verify_env(env):
    return verify(env, latest(LOGS / f"{env}.log"))
PY

cat > shipyard/transport.py <<'PY'
"""Sends a request to the status provider through the egress proxy config/proxy.ini names.

This checkout runs in a sandbox with no network: config/provider.ini sets `mode = sandbox`,
and requests go, through the same proxy settings, to the provider stand-in under fakes/."""

from collections import namedtuple

from shipyard.config import ini

Request = namedtuple("Request", "method url headers body")
Response = namedtuple("Response", "status body")


class TransportError(Exception):
    pass


def proxy():
    egress = ini("proxy")["egress"]
    return f"{egress['host']}:{egress['port']}"


def send(request):
    mode = ini("provider")["provider"].get("mode", "live")
    if mode == "sandbox":
        from fakes import status_provider

        return status_provider.handle(request, proxy=proxy())
    raise TransportError("live sending needs the deploy host's network")
PY

cat > shipyard/notify.py <<'PY'
"""Deploy notices, posted to the status provider's API."""

import json

from shipyard import transport
from shipyard.config import ini


class NoticeError(Exception):
    pass


def announce(env, text, send=None):
    send = send or transport.send
    provider = ini("provider")["provider"]
    request = transport.Request(
        "POST",
        provider["url"].rstrip("/") + "/v2/notices",
        {
            "Authorization": f"Bearer {provider['token']}",
            "X-Account-Id": provider["account"],
            "Content-Type": "application/json",
        },
        json.dumps({"environment": env, "text": text}),
    )
    response = send(request)
    if response.status >= 300:
        raise NoticeError(f"status provider answered {response.status}: {response.body}")
    return response
PY

cat > shipyard/agent_link.py <<'PY'
"""The link to the deploy agent, which listens on a Unix socket on the deploy host."""

import os
import socket
from pathlib import Path

SOCKET = os.environ.get("SHIPYARD_AGENT_SOCKET", "/run/shipyard/agent.sock")


def _ask(line):
    path = Path(SOCKET)
    if not path.exists():
        raise ConnectionError(f"no deploy agent socket at {path}")
    with socket.socket(socket.AF_UNIX) as link:
        link.settimeout(2)
        link.connect(str(path))
        link.sendall(line.encode("utf-8") + b"\n")
        return link.recv(4096).decode("utf-8").strip()


def ping():
    return _ask("PING") == "PONG"


def version():
    return _ask("VERSION")


def handshake(env):
    return _ask(f"HELLO {env}") == f"READY {env}"
PY

cat > shipyard/cli.py <<'PY'
"""shipyard's command line: deploy, verify, notify, probes and digest."""

import argparse
import sys

from shipyard import controller, gate, notify, scheduler, verify


def main(argv=None):
    parser = argparse.ArgumentParser(prog="shipyard")
    sub = parser.add_subparsers(dest="command", required=True)
    deploy = sub.add_parser("deploy", help="deploy a release to an environment")
    deploy.add_argument("env")
    deploy.add_argument("version")
    deploy.add_argument("--share", type=int, default=100)
    sub.add_parser("verify", help="verify an environment from its probe log").add_argument("env")
    announce = sub.add_parser("notify", help="post a deploy notice to the status page")
    announce.add_argument("env")
    announce.add_argument("text")
    sub.add_parser("probes", help="run the probes once").add_argument("env")
    sub.add_parser("digest", help="print a release artifact's digest").add_argument("version")
    args = parser.parse_args(argv)

    try:
        if args.command == "deploy":
            done = controller.deploy(args.env, args.version, args.share)
            print(f"deployed {done['version']} to {done['env']} at {done['share']}%")
        elif args.command == "verify":
            verdict = verify.verify_env(args.env)
            word = "passed" if verdict.ok else "failed"
            print(f"{args.env} verification {word}: {verdict.passed}/{verdict.total} probes")
            return 0 if verdict.ok else 1
        elif args.command == "notify":
            response = notify.announce(args.env, args.text)
            print(f"notice accepted ({response.status})")
        elif args.command == "probes":
            print("\n".join(scheduler.run(args.env)))
        elif args.command == "digest":
            print(gate.digest(args.version))
    except (controller.Refused, notify.NoticeError, OSError) as problem:
        print(f"{args.command} failed: {problem}", file=sys.stderr)
        return 1
    return 0
PY

cat > fakes/__init__.py <<'PY'
PY

cat > fakes/status_provider.py <<'PY'
"""A stand-in for the status provider's API and the egress path to it, for the sandbox.

It answers as the real service does: a proxy that does not forward gets 502, a missing or
wrong token 401, and a request for an account the token cannot see gets 404, since the service
does not say whether an account exists. Header names are matched without regard to case."""

import json

from shipyard.transport import Response

FORWARDING = {"egress-1.net.internal:3128"}
TOKEN = "sandbox-token"
ACCOUNTS = {"ops-stage"}


def handle(request, proxy):
    if proxy not in FORWARDING:
        return Response(502, f"proxy {proxy} did not forward the request")
    headers = {name.lower(): value for name, value in request.headers.items()}
    if headers.get("authorization") != f"Bearer {TOKEN}":
        return Response(401, "unauthorized")
    if headers.get("x-account-id") not in ACCOUNTS:
        return Response(404, "not found")
    if request.method != "POST" or not request.url.endswith("/v2/notices"):
        return Response(404, "not found")
    return Response(202, json.dumps({"accepted": True}))
PY

cat > bin/shipyard <<'SH'
#!/usr/bin/env bash
# shipyard's command line, run from the repository root.
set -euo pipefail
cd "$(dirname "$0")/.."
exec "${PYTHON:-python3}" -B -m shipyard "$@"
SH
chmod +x bin/shipyard
