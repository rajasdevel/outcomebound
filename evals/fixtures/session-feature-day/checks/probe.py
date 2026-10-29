"""Exercise the workspace service through handle, with an injected virtual provider clock."""

from __future__ import annotations

import contextlib
import copy
import importlib
import json
import math
import sys
from pathlib import Path
from urllib.parse import unquote


def read_only(call):
    def checked(*args, **kwargs):
        before = copy.deepcopy((args, kwargs))
        try:
            return call(*args, **kwargs)
        finally:
            if (args, kwargs) != before:
                raise AssertionError("read-only caller changed its arguments")

    return checked


@contextlib.contextmanager
def policy_inputs():
    sys.path.insert(0, str(Path.cwd()))
    cls = importlib.import_module("chatsvc.wait_policy").BoundedPolicy
    original = {name: getattr(cls, name) for name in ("hint", "delay")}

    def checked(method):
        def call(self, *args, **kwargs):
            return read_only(method.__get__(self, cls))(*args, **kwargs)

        return call

    try:
        for name, method in original.items():
            setattr(cls, name, checked(method))
        yield
    finally:
        for name, method in original.items():
            setattr(cls, name, method)


class Response:
    def __init__(self, status, body, headers=None):
        self.status, self.headers = status, headers or {}
        self.body = json.dumps(body).encode()

    def json(self):
        return json.loads(self.body)


class Provider:
    def __init__(self, statuses=()):
        self.statuses = list(statuses)
        self.calls, self.waits = [], []
        self.now = 0.0

    def sleep(self, seconds):
        self.waits.append(seconds)
        self.now += seconds

    def send(self, method, path, headers, body):
        self.calls.append((self.now, path, headers.get("authorization"), json.loads(body)))
        model = unquote(path.split("/models/")[-1].split(":")[0])
        status = self.statuses.pop(0) if self.statuses else 200
        if model not in {"chat-fast-2", "chat-fast-2-long", "chat-small-3", "chat-large-3"}:
            status = 404
        if status != 200:
            return Response(status, {"error": "provider_error"}, {"retry-after-ms": "250"})
        return Response(200, {"output": "ok", "usage": {"input_tokens": 1}})


class SharedPool(Provider):
    """Refused calls use quota too; a virtual clock makes burst tests immediate."""

    def __init__(self):
        super().__init__()
        self.window = [(key, 0.0) for key in ("Bearer pool-a", "Bearer pool-b") for _ in range(4)]

    def send(self, method, path, headers, body):
        key = headers.get("authorization")
        recent = [at for pool, at in self.window if pool == key and self.now - at < 1.0 - 1e-9]
        self.window.append((key, self.now))
        if len(recent) >= 4:
            self.calls.append((self.now, path, key, json.loads(body)))
            wait = sorted([*recent, self.now])[-4] + 1.0 - self.now
            return Response(
                429, {"error": "quota"}, {"retry-after-ms": str(math.ceil(wait * 1000))}
            )
        return super().send(method, path, headers, body)


def service(provider):
    sys.path.insert(0, str(Path.cwd()))
    build = importlib.import_module("chatsvc.app").build_service
    return build("config", provider, sleep=provider.sleep, log=lambda line: None)


def request(svc, path, payload=None, method="POST"):
    body = {"messages": [{"role": "user", "content": "probe"}], **(payload or {})}
    status, headers, answer = handle(
        svc, method, path, {"x-api-key": "probe"}, json.dumps(body).encode()
    )
    return status, headers, json.loads(answer)


def handle(svc, *args):
    with policy_inputs():
        return read_only(svc.handle)(*args)


def routes():
    problems = []
    for path, model, expected in (
        ("/v2/chat", "fast", "chat-fast-2"),
        ("/v2/chat", "fast-long", "chat-fast-2-long"),
        ("/v2/chat", None, "chat-fast-2"),
        ("/v2/chat", "chat-fast-2", "chat-fast-2"),
        ("/v1/chat", "small", "chat-small-3"),
    ):
        provider = Provider()
        payload = {} if model is None else {"model": model}
        status, _, body = request(service(provider), path, payload)
        if status != 200 or body.get("model") != expected:
            problems.append(f"{path} model {model}: {status}, {body}")
        if provider.waits:
            problems.append("a successful first call was delayed")
        if len(provider.calls) != 1 or provider.calls[0][1] != f"/v1/models/{expected}:generate":
            problems.append(f"{path} sent the wrong provider path or repeated a successful call")
    return problems


def retries():
    problems = []
    for statuses, want, calls, waits in (
        ([429, 200], 200, 2, [0.25]),
        ([503, 200], 200, 2, [0.25]),
        ([404], 502, 1, []),
        ([429, 429, 429, 429], 503, 4, [0.25, 0.25, 0.25]),
    ):
        provider = Provider(statuses)
        status, headers, _ = request(service(provider), "/v2/chat", {"model": "chat-fast-2"})
        if (status, len(provider.calls), provider.waits) != (want, calls, waits):
            problems.append(
                f"retry {statuses}: got {status}, {len(provider.calls)}, {provider.waits}"
            )
        if want == 503 and float(headers.get("retry-after", 0)) < 1:
            problems.append("exhausted quota has no usable retry hint")
    provider = Provider()
    status, _, _ = request(service(provider), "/v2/chat", {"model": "retired-model"})
    if status == 200 or len(provider.calls) != 1:
        problems.append("an unknown model was retried or accepted")
    invalid_payloads: tuple[dict[str, object], ...] = (
        {"messages": []},
        {"max_tokens": 0},
        {"max_tokens": 4097},
    )
    for payload in invalid_payloads:
        provider = Provider()
        status, _, _ = request(service(provider), "/v2/chat", payload)
        if status != 400 or provider.calls:
            problems.append(f"bad input reached the provider: {payload}")
    provider = SharedPool()
    svc = service(provider)
    for _ in range(8):
        status, _, _ = request(svc, "/v2/chat", {"model": "fast"})
        if status != 200:
            problems.append("a burst on the shared key did not recover after quota advice")
            break
    return problems


def catalog():
    provider = Provider()
    svc = service(provider)
    status, _, body = handle(svc, "GET", "/v2/routes", {}, b"")
    expected = {
        "routes": [
            {
                "path": "/v1/chat",
                "default_model": "chat-large-3",
                "aliases": {"large": "chat-large-3", "small": "chat-small-3"},
                "max_tokens": 4096,
            },
            {
                "path": "/v2/chat",
                "default_model": "chat-fast-2",
                "aliases": {"fast": "chat-fast-2", "fast-long": "chat-fast-2-long"},
                "max_tokens": 4096,
            },
        ]
    }
    problems = (
        [] if status == 200 and json.loads(body) == expected else ["catalog shape or fields differ"]
    )
    if handle(svc, "POST", "/v2/routes", {}, b"")[0] != 405:
        problems.append("POST catalog is not a 405 without credentials")
    if handle(svc, "GET", "/healthz", {}, b"")[0] != 200:
        problems.append("health broke")
    if provider.calls:
        problems.append("catalog called the provider")
    return problems


def policy():
    with policy_inputs():
        return policy_examples()


def policy_examples():
    sys.path.insert(0, str(Path.cwd()))
    policy = importlib.import_module("chatsvc.wait_policy").BoundedPolicy(now=0)
    problems = []
    for headers, expected in (
        ({"retry-after-ms": "250", "retry-after": "3"}, 0.25),
        ({"retry-after-ms": "bad", "retry-after": "2"}, 2.0),
        ({"retry-after-ms": "NaN", "retry-after": "1.5"}, 1.5),
        ({"retry-after-ms": "-1"}, None),
        ({"retry-after": "inf"}, None),
        ({"retry-after-ms": None, "retry-after": "900"}, 8.0),
        ({"retry-after": "Thu, 01 Jan 1970 00:00:03 GMT"}, 3.0),
        ({"retry-after": "Wed, 31 Dec 1969 23:59:59 GMT"}, 0.0),
        ({}, None),
    ):
        if read_only(policy.hint)(headers) != expected:
            problems.append(f"wait hint {headers} differs from {expected}")
    if [policy.delay(n, {}) for n in (1, 3, 6)] != [0.1, 0.4, 2.0]:
        problems.append("fallback backoff differs")

    class Fractional(Provider):
        def send(self, *args):
            result = super().send(*args)
            result.headers = {"retry-after-ms": "1500"}
            return result

    provider: Provider = Fractional([429] * 4)
    status, headers, _ = request(service(provider), "/v2/chat")
    if (status, headers.get("retry-after"), provider.waits) != (503, "2", [1.5, 1.5, 1.5]):
        problems.append("the fast handler does not use bounded policy and ceiling advice")
    provider = Provider()
    if request(service(provider), "/v2/chat", {"max_tokens": True})[0] != 400 or provider.calls:
        problems.append("boolean max_tokens reached provider")
    return problems


def readiness():
    sys.path.insert(0, str(Path.cwd()))
    assess = read_only(importlib.import_module("chatsvc.readiness").assess)
    catalog = {
        "routes": [
            {
                "path": "/v2/chat",
                "default_model": "chat-fast-2",
                "aliases": {"fast": "chat-fast-2"},
                "max_tokens": 4096,
            }
        ]
    }
    base = {
        "env": "stage",
        "revision": "candidate",
        "dirty": False,
        "checks": [{"name": "route-unit", "ok": True, "revision": "candidate"}],
        "smoke": {"ok": True, "revision": "candidate"},
        "catalog": catalog,
        "deployed_files": {"chatsvc/app.py": "a", "config/chatsvc.ini": "b"},
        "current_files": {
            "chatsvc/app.py": "a",
            "config/chatsvc.ini": "b",
            "docs/testing.md": "new",
        },
    }
    problems = []
    examples: list[tuple[dict[str, object], list[str]]] = [
        ({}, []),
        ({"smoke": {"ok": True, "revision": "old"}}, ["smoke"]),
        ({"checks": [{"name": "unit", "ok": True, "revision": "old"}]}, ["checks"]),
        ({"checks": [{"name": "unit", "ok": 1, "revision": "candidate"}]}, ["checks"]),
        ({"dirty": 0}, ["dirty"]),
        ({"env": "prod"}, ["environment"]),
        ({"current_files": {"chatsvc/app.py": "changed", "config/chatsvc.ini": "b"}}, ["code"]),
        ({"deployed_files": {}, "current_files": {}}, ["code"]),
        ({"catalog": {"routes": [dict(catalog["routes"][0], key="private")]}}, ["catalog"]),
        ({"checks": None}, ["checks"]),
        ({"smoke": []}, ["smoke"]),
        ({"revision": "old"}, ["revision"]),
    ]
    for changes, expected in examples:
        snapshot = copy.deepcopy({**base, **changes})
        before = copy.deepcopy(snapshot)
        result = assess(snapshot, "candidate", copy.deepcopy(catalog))
        want = {"ready": not expected, "reasons": expected, "revision": snapshot["revision"]}
        if result != want or snapshot != before:
            problems.append(f"readiness example {changes}: wrong result or mutated input")
    missing = {
        "ready": False,
        "reasons": ["catalog", "checks", "code", "dirty", "environment", "revision", "smoke"],
        "revision": "",
    }
    malformed_inputs: tuple[object, ...] = ({}, None, [], "stage")
    problems.extend(
        "missing evidence did not fail closed"
        for malformed in malformed_inputs
        if assess(malformed, "candidate", catalog) != missing
    )
    review = read_only(importlib.import_module("chatsvc.stage_receipts").review)
    records = [
        {"action": "check", "name": "route", "sequence": 1, "ok": True, "revision": "candidate"},
        {
            "action": "deploy",
            "sequence": 2,
            "ok": True,
            "revision": "candidate",
            "env": "stage",
            "dirty": False,
        },
        {"action": "smoke", "sequence": 3, "ok": True, "revision": "candidate"},
    ]
    code = {"chatsvc/app.py": "a", "config/chatsvc.ini": "b"}
    if review(records, "candidate", catalog, code, code) != {
        "ready": True,
        "reasons": [],
        "revision": "candidate",
    }:
        problems.append("receipt adapter did not build a valid snapshot")
    failed = [
        *records,
        {"action": "check", "name": "route", "sequence": 4, "ok": False, "revision": "candidate"},
    ]
    if review(failed, "candidate", catalog, code, code)["reasons"] != ["checks"]:
        problems.append("receipt adapter ignored a later failure")
    replayed_check = [
        *records,
        {"action": "check", "name": "route", "sequence": 5, "ok": True, "revision": "candidate"},
        records[0],
    ]
    with contextlib.suppress(ValueError):
        review(replayed_check, "candidate", catalog, code, code)
        problems.append("receipt adapter accepted a duplicate older sequence")
    return problems


def jobs():
    sys.path.insert(0, str(Path.cwd()))
    parse = importlib.import_module("chatsvc.job_manifest").parse
    run_jobs = importlib.import_module("chatsvc.job_runner").run_jobs
    problems = []
    rows = [
        {"id": "bad", "path": "/v2/chat", "key": "batch", "body": {"messages": []}},
        {
            "id": "fast",
            "path": "/v2/chat",
            "key": "batch",
            "body": {"model": "fast-long", "messages": [{"role": "user", "content": "x"}]},
        },
        {
            "id": "old",
            "path": "chat",
            "key": "batch",
            "body": {"model": "small", "messages": [{"role": "user", "content": "x"}]},
        },
    ]
    provider = Provider()
    svc = service(provider)
    callback = svc.log
    result = run_jobs(parse(map(json.dumps, rows)), svc)
    if result["jobs"] != [
        {"id": "bad", "status": 400, "model": ""},
        {"id": "fast", "status": 200, "model": "chat-fast-2-long"},
        {"id": "old", "status": 200, "model": "chat-small-3"},
    ]:
        problems.append("batch paths, order or error isolation differ")
    if len(provider.calls) != 2 or svc.log is not callback:
        problems.append("invalid job reached transport or log callback was lost")
    malformed = [rows[0], rows[0]]
    try:
        run_jobs(parse(map(json.dumps, malformed)), svc)
        problems.append("duplicate manifest identity was accepted")
    except ValueError:
        pass
    if len(provider.calls) != 2:
        problems.append("a bad manifest sent partial traffic")

    class Broken(Provider):
        def send(self, *args):
            raise OSError("transport stopped")

    svc = service(Broken())
    callback = svc.log
    with contextlib.suppress(OSError):
        run_jobs(parse([json.dumps(rows[1])]), svc)
    if svc.log is not callback:
        problems.append("exception lost the log callback")
    return problems


def batch_resume():
    sys.path.insert(0, str(Path.cwd()))
    parse = importlib.import_module("chatsvc.job_manifest").parse
    run_jobs = importlib.import_module("chatsvc.job_runner").run_jobs
    rows: list[dict] = [
        {
            "id": "child",
            "path": "/v2/chat",
            "key": "private-batch-key",
            "depends_on": ["parent"],
            "body": {"messages": [{"role": "user", "content": "child"}]},
        },
        {
            "id": "parent",
            "path": "/v2/chat",
            "key": "private-batch-key",
            "depends_on": [],
            "body": {"messages": [{"role": "user", "content": "parent"}]},
        },
        {
            "id": "free",
            "path": "/v2/chat",
            "key": "private-batch-key",
            "depends_on": [],
            "body": {"messages": [{"role": "user", "content": "free"}]},
        },
    ]
    provider = Provider()
    first = run_jobs(parse(map(json.dumps, rows)), service(provider), max_jobs=1)
    problems = []
    if (
        first["jobs"]
        != [
            {"id": "child", "status": 0, "model": ""},
            {"id": "parent", "status": 200, "model": "chat-fast-2"},
            {"id": "free", "status": 0, "model": ""},
        ]
        or len(provider.calls) != 1
    ):
        problems.append("batch budget or dependency order differs")
    prior = first["resume"]
    before = json.dumps(prior, sort_keys=True)
    result = run_jobs(parse(map(json.dumps, rows)), service(provider), prior=prior, max_jobs=2)
    if [row["status"] for row in result["jobs"]] != [200, 200, 200] or len(provider.calls) != 3:
        problems.append("resume repeated successful work or lost pending jobs")
    if json.dumps(prior, sort_keys=True) != before or "private-batch-key" in json.dumps(result):
        problems.append("resume mutated evidence or exposed caller keys")
    if [call[3]["messages"][0]["content"] for call in provider.calls] != [
        "parent",
        "child",
        "free",
    ]:
        problems.append("execution did not use stable dependency order")
    failed_prior = [dict(prior[0], status=503)]
    failed = run_jobs(
        parse([json.dumps(rows[1])]), service(provider), prior=failed_prior, max_jobs=0
    )
    if failed["jobs"][0]["status"] != 0:
        problems.append("a failed prior result was reused")
    for limit in (True, -1):
        with contextlib.suppress(ValueError):
            run_jobs(parse(map(json.dumps, rows)), service(provider), max_jobs=limit)
            problems.append("invalid job budget was accepted")
    with contextlib.suppress(ValueError):
        run_jobs(parse(map(json.dumps, rows)), service(provider), prior=prior * 2, max_jobs=0)
        problems.append("duplicate resume identity was accepted")
    # Same id with different content is a new job, even when an old success is available.
    rows[1]["body"]["messages"][0]["content"] = "different"
    result = run_jobs(parse(map(json.dumps, rows)), service(provider), prior=prior, max_jobs=0)
    if [row["status"] for row in result["jobs"]] != [424, 0, 0]:
        problems.append("resume accepted stale content")
    broken = Provider([404, 200])
    result = run_jobs(parse(map(json.dumps, rows)), service(broken))
    if [row["status"] for row in result["jobs"]] != [424, 502, 200] or len(broken.calls) != 2:
        problems.append("a dependency failure stopped independent work or ran a blocked job")
    rows[1]["depends_on"] = ["child"]
    with contextlib.suppress(ValueError):
        parse(map(json.dumps, rows))
        problems.append("cyclic manifest was accepted")
    return problems


def diagnostics():
    sys.path.insert(0, str(Path.cwd()))
    summarize = importlib.import_module("chatsvc.diagnostics").summarize
    first = (
        "upstream path=/v1/models/custom%2Fmodel:generate attempt=1 status=429 "
        "worker=one request=x event=a"
    )
    second = first.replace("attempt=1 status=429", "attempt=2 status=200").replace(
        "event=a", "event=b"
    )
    other = first.replace("status=429", "status=404").replace("worker=one", "worker=two")
    result = summarize([second, other, first, second, "inbound path=/v2/chat status=429"])
    expected = {
        "calls": 3,
        "retries": 1,
        "statuses": {"200": 1, "404": 1, "429": 1},
        "paths": {"/v1/models/custom%2Fmodel:generate": 3},
        "models": {"custom/model": 3},
        "duplicates": 1,
        "requests": [
            {"worker": "one", "request": "x", "attempts": 2, "status": 200},
            {"worker": "two", "request": "x", "attempts": 1, "status": 404},
        ],
    }
    problems = [] if result == expected else ["interleaved spool report differs"]
    for rows in (
        [first, first.replace("status=429", "status=404")],
        [second],
        [first.replace("status=429", "status=404"), second],
        [first, second.replace("custom%2Fmodel", "another")],
        [first.replace(" worker=one", "")],
    ):
        with contextlib.suppress(ValueError):
            summarize(rows)
            problems.append("ambiguous attempt history was accepted")
    legacy = first.split(" worker=")[0]
    legacy_result = summarize([legacy, legacy])
    if legacy_result["calls"] != 2 or legacy_result["models"] != {"custom/model": 2}:
        problems.append("legacy log counting regressed")
    return problems


if __name__ == "__main__":
    try:
        result = {
            "routes": routes,
            "retries": retries,
            "catalog": catalog,
            "policy": policy,
            "readiness": readiness,
            "jobs": lambda: jobs() + batch_resume(),
            "diagnostics": diagnostics,
        }[sys.argv[1]]()
    except Exception as error:
        result = [f"probe raised {type(error).__name__}: {error}"]
    print(json.dumps(result))
    sys.exit(bool(result))
