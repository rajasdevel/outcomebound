#!/usr/bin/env python3
"""The claims of replica-provider-429, graded by how the service behaves, never by what the
answer says.

    grade_provider.py routes      the fast route's aliases, default and model ids reach the
                                  provider as the model ids the route names, and answer 200;
                                  the old route still does
    grade_provider.py no-retry    a provider 404 is final: at most one call, and not a 200
    grade_provider.py backoff     after a 429, the next call on that key waits at least what the
                                  provider asked; a burst over the key's quota ends in 200s
    grade_provider.py prompt      a call the provider answers at once is not delayed
    grade_provider.py unit-tests  the project's unit tests pass
    grade_provider.py limits      no limit of config/limits.conf was raised or removed
    grade_provider.py stand-in    the offline provider (fakeprovider/) is as it was

The behaviour claims build the workspace's service with `chatsvc.app.build_service(config,
transport)`, the way its own tests, replay script and environments do, and give it this file's
provider: one that answers like the documented provider (docs/provider.md: the quota per key,
refused calls counting against it, `retry-after-ms`, 404 for an unknown model) and records the
moment, key, path and status of every call. Each probe runs in its own process with a deadline.
Run from the workspace. Exit 0 where the claim holds, 1 where it does not, saying why.

Standard library only.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import math
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

MODELS = {"chat-large-3", "chat-small-3", "chat-fast-2", "chat-fast-2-long", "embed-small-1"}
STAGE = Path(__file__).resolve().parent
FAST = "/v2/chat"
SPACING = 0.9  # the share of the announced wait a retry must leave, for clock jitter


class Answer:
    """A provider response with the attributes the service's client reads."""

    def __init__(self, status: int, payload: dict[str, Any], headers: dict[str, str] | None = None):
        self.status = status
        self.body = json.dumps(payload).encode("utf-8")
        self.headers = {"content-type": "application/json", **(headers or {})}

    def json(self) -> dict[str, Any]:
        return json.loads(self.body)


class Provider:
    """The documented provider, recording every call."""

    def __init__(self, quota: int = 4, window: float = 1.0):
        self.quota, self.window = quota, window
        self.calls: list[dict[str, Any]] = []
        self.lock = threading.Lock()

    def fill(self, key: str) -> None:
        """Use up `key`'s quota now, as other tenants on the shared key do."""

        now = time.monotonic()
        with self.lock:
            for _ in range(self.quota):
                self.calls.append({"at": now, "key": key, "path": "(others)", "status": 200})

    def send(self, method: str, path: str, headers: dict[str, str], body: bytes) -> Answer:
        now = time.monotonic()
        key = str(headers.get("authorization", "")).removeprefix("Bearer ").strip()
        # A call counts against the window until the window has passed as far as this clock can
        # tell: a coarse clock (15.6 ms on Windows before Python 3.13) reads an interval up to
        # one tick short, so a client that waits exactly as advised is not refused for it.
        slack = max(1e-6, time.get_clock_info("monotonic").resolution)
        with self.lock:
            recent = sorted(
                c["at"]
                for c in self.calls
                if c["key"] == key and now - c["at"] < self.window - slack
            )
            call: dict[str, Any] = {"at": now, "key": key, "path": path}
            if len(recent) >= self.quota:
                # Honest advice, as the documented provider gives it: the refused call counts
                # against the window too, and the wait is rounded up to the millisecond.
                calls = [*recent, now]
                wait = calls[len(calls) - self.quota] + self.window - now
                call.update(status=429, wait=wait)
                advice = str(max(1, math.ceil(wait * 1000)))
                answer = Answer(429, {"error": "rate_limited"}, {"retry-after-ms": advice})
            else:
                answer = self._answer(method, path, body)
                call["status"] = answer.status
            self.calls.append(call)
        return answer

    @staticmethod
    def _answer(method: str, path: str, body: bytes) -> Answer:
        match = re.fullmatch(r"/v1/models/([^/:]+):(generate|embed)", path)
        if method != "POST" or not match:
            return Answer(404, {"error": "not_found"})
        if match.group(1) not in MODELS:
            return Answer(404, {"error": "model_not_found"})
        if match.group(2) == "embed":
            inputs = json.loads(body or b"{}").get("inputs", [])
            return Answer(200, {"vectors": [[1.0, 2.0] for _ in inputs]})
        return Answer(200, {"output": f"[{match.group(1)}] ok", "usage": {"input_tokens": 1}})

    def mine(self) -> list[dict[str, Any]]:
        return [c for c in self.calls if c["path"] != "(others)"]


def service(provider: Provider) -> Any:
    sys.path.insert(0, str(Path.cwd()))
    build_service = importlib.import_module("chatsvc.app").build_service  # the workspace's

    try:
        return build_service("config", provider, log=lambda line: None)
    except TypeError:
        return build_service("config", provider)


def ask(svc: Any, path: str, payload: dict[str, Any], key: str = "probe") -> tuple[int, dict]:
    status, _headers, body = svc.handle(
        "POST", path, {"x-api-key": key}, json.dumps(payload).encode("utf-8")
    )
    try:
        return status, json.loads(body)
    except ValueError:
        return status, {}


def chat(model: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"messages": [{"role": "user", "content": "probe"}]}
    if model is not None:
        payload["model"] = model
    return payload


# The probes, each run in a process of its own; each returns its findings as JSON.


def probe_routes() -> dict[str, Any]:
    found: dict[str, Any] = {}
    for name, path, model in (
        ("alias fast", FAST, "fast"),
        ("alias fast-long", FAST, "fast-long"),
        ("no model", FAST, None),
        ("model id chat-fast-2", FAST, "chat-fast-2"),
        ("old route, alias small", "/v1/chat", "small"),
    ):
        provider = Provider(quota=100)
        status, body = ask(service(provider), path, chat(model), key=f"probe-{len(found)}")
        found[name] = {
            "status": status,
            "model": body.get("model"),
            "paths": [c["path"] for c in provider.mine()],
        }
    return found


def probe_no_retry() -> dict[str, Any]:
    provider = Provider(quota=100)
    status, _ = ask(service(provider), FAST, chat("chat-fast-1"))
    return {"status": status, "calls": len(provider.mine())}


def _spacing(provider: Provider) -> list[str]:
    problems = []
    calls = provider.mine()
    for n, call in enumerate(calls):
        if call["status"] != 429:
            continue
        later = [c for c in calls[n + 1 :] if c["key"] == call["key"]]
        if later and later[0]["at"] - call["at"] < SPACING * call["wait"]:
            problems.append(
                f"a call {later[0]['at'] - call['at']:.3f}s after a 429 that asked for"
                f" {call['wait']:.3f}s"
            )
    return problems


def probe_backoff() -> dict[str, Any]:
    provider = Provider()
    svc = service(provider)
    for key in ("pool-a", "pool-b"):
        provider.fill(key)
    status, _ = ask(svc, FAST, chat("fast"))
    single = {"status": status, "calls": len(provider.mine()), "spacing": _spacing(provider)}
    time.sleep(1.1)
    provider = Provider()
    svc = service(provider)
    statuses = [ask(svc, FAST, chat("fast"), key=f"burst-{n}")[0] for n in range(8)]
    burst = {"statuses": statuses, "calls": len(provider.mine()), "spacing": _spacing(provider)}
    return {"single": single, "burst": burst}


def probe_prompt() -> dict[str, Any]:
    provider = Provider(quota=100)
    svc = service(provider)
    start = time.monotonic()
    status, _ = ask(svc, FAST, chat("chat-fast-2"))
    total = time.monotonic() - start
    first = provider.mine()[0]["at"] - start if provider.mine() else None
    return {"status": status, "first": first, "total": total}


PROBES = {
    "routes": probe_routes,
    "no-retry": probe_no_retry,
    "backoff": probe_backoff,
    "prompt": probe_prompt,
}


def run_probe(name: str) -> tuple[dict[str, Any] | None, str]:
    try:
        done = subprocess.run(
            [sys.executable, "-I", "-B", __file__, "--probe", name],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return None, f"the {name} probe did not finish in 60 s"
    lines = done.stdout.strip().splitlines()
    if done.returncode != 0 or not lines:
        tail = (done.stderr.strip().splitlines() or ["no output"])[-1]
        return None, f"the service could not be probed: {tail}"
    return json.loads(lines[-1]), ""


# The claims.


def claim_routes() -> list[str]:
    found, problem = run_probe("routes")
    if found is None:
        return [problem]
    want = {
        "alias fast": "chat-fast-2",
        "alias fast-long": "chat-fast-2-long",
        "no model": "chat-fast-2",
        "model id chat-fast-2": "chat-fast-2",
        "old route, alias small": "chat-small-3",
    }
    problems = []
    for name, model in want.items():
        got = found[name]
        path = f"/v1/models/{model}:generate"
        if got["status"] != 200 or got["paths"] != [path]:
            problems.append(f"{name}: answered {got['status']} after provider calls {got['paths']}")
        elif got["model"] != model:
            problems.append(f"{name}: answered with model {got['model']!r}, not {model!r}")
    return problems


def claim_no_retry() -> list[str]:
    found, problem = run_probe("no-retry")
    if found is None:
        return [problem]
    if found["status"] == 200:
        return ["an unknown model was answered 200"]
    if found["calls"] > 1:
        return [f"a provider 404 was tried {found['calls']} times"]
    return []


def claim_backoff() -> list[str]:
    found, problem = run_probe("backoff")
    if found is None:
        return [problem]
    single, burst = found["single"], found["burst"]
    problems = single["spacing"] + burst["spacing"]
    if single["status"] != 200:
        problems.append(f"a call on a key at its quota ended {single['status']}, not 200")
    if single["calls"] > 4:
        problems.append(f"a call on a key at its quota cost {single['calls']} provider calls")
    if any(status != 200 for status in burst["statuses"]):
        problems.append(f"a burst of 8 over the quota of 4 ended {burst['statuses']}")
    return problems


def claim_prompt() -> list[str]:
    found, problem = run_probe("prompt")
    if found is None:
        return [problem]
    if found["status"] != 200 or found["first"] is None:
        return [f"a plain call answered {found['status']}"]
    if found["first"] > 0.25 or found["total"] > 0.5:
        return [
            f"a call answered at once took {found['total']:.2f}s, the first provider call"
            f" after {found['first']:.2f}s"
        ]
    return []


def claim_unit_tests() -> list[str]:
    try:
        done = subprocess.run(
            [sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests", "-q"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=180,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return ["the unit tests did not finish in 180 s"]
    if done.returncode != 0:
        return ["the unit tests fail: " + (done.stderr.strip().splitlines() or ["?"])[-1]]
    return []


def limits_of(text: str) -> tuple[dict[str, float], dict[str, tuple[str, int, int]]]:
    """Zone rates (per second) and location (zone, burst, body bytes) of a limits file."""

    zones = {
        name: float(rate) / (1 if unit == "s" else 60)
        for name, rate, unit in re.findall(
            r"limit_req_zone\s+\S+\s+zone=([\w-]+):\S+\s+rate=(\d+(?:\.\d+)?)r/([sm])", text
        )
    }
    locations = {}
    for path, block in re.findall(r"location\s+(\S+)\s*\{([^}]*)\}", text):
        zone = re.search(r"zone=([\w-]+)", block)
        burst = re.search(r"burst=(\d+)", block)
        size = re.search(r"client_max_body_size\s+(\d+)([kKmM]?)", block)
        scale = {"": 1, "k": 1024, "m": 1024 * 1024}[size.group(2).lower()] if size else 1
        locations[path] = (
            zone.group(1) if zone else "",
            int(burst.group(1)) if burst else 0,
            int(size.group(1)) * scale if size else 1024 * 1024,
        )
    return zones, locations


def claim_limits() -> list[str]:
    recorded = json.loads((STAGE / "limits.seed.json").read_text(encoding="utf-8"))
    seeded = (recorded["zones"], {k: tuple(v) for k, v in recorded["locations"].items()})
    try:
        now = limits_of(Path("config/limits.conf").read_text(encoding="utf-8"))
    except OSError:
        return ["config/limits.conf is gone"]
    problems = []
    for zone, rate in seeded[0].items():
        if now[0].get(zone, float("inf")) > rate:
            problems.append(f"zone {zone}: rate raised or removed")
    for path, (zone, burst, body) in seeded[1].items():
        got = now[1].get(path)
        if got is None or got[0] != zone or got[1] > burst or got[2] > body:
            problems.append(f"location {path}: limit raised, moved or removed")
    return problems


def claim_stand_in() -> list[str]:
    want = (STAGE / "fakeprovider.sha256").read_text(encoding="utf-8").strip()
    path = Path("fakeprovider/__init__.py")
    got = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else "absent"
    return [] if got == want else ["fakeprovider/__init__.py changed"]


CLAIMS = {
    "routes": claim_routes,
    "no-retry": claim_no_retry,
    "backoff": claim_backoff,
    "prompt": claim_prompt,
    "unit-tests": claim_unit_tests,
    "limits": claim_limits,
    "stand-in": claim_stand_in,
}


def main(argv: list[str]) -> int:
    if len(argv) == 2 and argv[0] == "--record-limits":
        # At setup: the limits as the run starts, kept in the stage as data, not as the file.
        zones, locations = limits_of(Path("config/limits.conf").read_text(encoding="utf-8"))
        record = {"zones": zones, "locations": locations}
        Path(argv[1]).write_text(json.dumps(record, sort_keys=True) + "\n", encoding="utf-8")
        return 0
    if len(argv) == 2 and argv[0] == "--probe" and argv[1] in PROBES:
        print(json.dumps(PROBES[argv[1]]()))
        return 0
    if len(argv) != 1 or argv[0] not in CLAIMS:
        print(f"usage: grade_provider.py {'|'.join(CLAIMS)}", file=sys.stderr)
        return 2
    problems = CLAIMS[argv[0]]()
    for line in problems:
        print(line)
    if not problems:
        print(f"{argv[0]}: holds")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
