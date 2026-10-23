#!/usr/bin/env python3
"""The claims of replica-holdout-provider-429, graded by how the embeddings route
behaves against a provider that records every call.

    grade_embed.py batches     a request over the provider's batch limit is answered 200, with
                               one vector per input in input order, in calls the provider takes
    grade_embed.py no-retry    a provider 400 is final: one call, not a 200
    grade_embed.py backoff     after a 429 the next call on the key waits what the provider
                               asked; requests on a key at its quota end in 200s
    grade_embed.py prompt      a request the provider answers at once is not delayed
    grade_embed.py unit-tests | limits | stand-in    as grade_provider.py

It reuses grade_provider.py (beside it in the stage) for the provider and the shared claims.
Run from the workspace. Exit 0 where the claim holds, 1 where it does not, saying why.

Standard library only.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import time
from pathlib import Path
from types import ModuleType
from typing import Any

MAX_BATCH = 16
EMBED = "/v1/embed"


def _load(name: str) -> ModuleType:
    here = Path(__file__).resolve().parent
    candidates = [
        here / f"{name}.py",
        here.parents[1] / "replica-provider-429" / "checks" / f"{name}.py",
    ]
    path = next((c for c in candidates if c.is_file()), candidates[0])
    spec = importlib.util.spec_from_file_location(f"replica_{name}", path)
    if spec is None or spec.loader is None:
        raise ImportError(name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


base = _load("grade_provider")


ProviderBase: Any = base.Provider


class Provider(ProviderBase):
    """The documented provider's embeddings: at most 16 inputs a call, one vector an input."""

    def __init__(self, quota: int = 4, refuse: bool = False):
        super().__init__(quota=quota)
        self.refuse = refuse

    @staticmethod
    def _batch(body: bytes) -> list[str]:
        return json.loads(body or b"{}").get("inputs", [])

    def send(self, method: str, path: str, headers: dict[str, str], body: bytes) -> Any:
        answer = super().send(method, path, headers, body)
        with self.lock:
            self.calls[-1]["size"] = len(self._batch(body))
        return answer

    def _answer(self, method: str, path: str, body: bytes) -> Any:
        inputs = self._batch(body)
        if self.refuse:
            return base.Answer(400, {"error": "bad_request"})
        if path != "/v1/models/embed-small-1:embed":
            return base.Answer(404, {"error": "model_not_found"})
        if len(inputs) > MAX_BATCH:
            return base.Answer(400, {"error": f"too_many_inputs: at most {MAX_BATCH}"})
        return base.Answer(200, {"vectors": [[float(i.rsplit(" ", 1)[-1])] for i in inputs]})


def docs(count: int, start: int = 0) -> dict[str, Any]:
    return {"inputs": [f"doc {n}" for n in range(start, start + count)]}


def probe_batches() -> dict[str, Any]:
    provider = Provider(quota=100)
    status, body = base.ask(base.service(provider), EMBED, docs(40))
    return {
        "status": status,
        "vectors": body.get("vectors"),
        "sizes": [c.get("size") for c in provider.mine()],
    }


def probe_no_retry() -> dict[str, Any]:
    provider = Provider(quota=100, refuse=True)
    status, _ = base.ask(base.service(provider), EMBED, docs(3))
    return {"status": status, "calls": len(provider.mine())}


def probe_backoff() -> dict[str, Any]:
    provider = Provider()
    svc = base.service(provider)
    for key in ("pool-a", "pool-b"):
        provider.fill(key)
    status, body = base.ask(svc, EMBED, docs(20))
    return {
        "status": status,
        "count": len(body.get("vectors") or []),
        "calls": len(provider.mine()),
        "spacing": base._spacing(provider),
    }


def probe_prompt() -> dict[str, Any]:
    provider = Provider(quota=100)
    svc = base.service(provider)
    start = time.monotonic()
    status, _ = base.ask(svc, EMBED, docs(2))
    first = provider.mine()[0]["at"] - start if provider.mine() else None
    return {"status": status, "first": first, "total": time.monotonic() - start}


PROBES = {
    "batches": probe_batches,
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


def claim_batches() -> list[str]:
    found, problem = run_probe("batches")
    if found is None:
        return [problem]
    problems = []
    if found["status"] != 200:
        problems.append(f"40 inputs were answered {found['status']}")
    elif found["vectors"] != [[float(n)] for n in range(40)]:
        problems.append("the vectors are not one per input in input order")
    if any(size > MAX_BATCH for size in found["sizes"]):
        problems.append(f"calls of {found['sizes']} inputs, over the provider's {MAX_BATCH}")
    return problems


def claim_no_retry() -> list[str]:
    found, problem = run_probe("no-retry")
    if found is None:
        return [problem]
    if found["status"] == 200:
        return ["a provider 400 was answered 200"]
    return [f"a provider 400 was tried {found['calls']} times"] if found["calls"] > 1 else []


def claim_backoff() -> list[str]:
    found, problem = run_probe("backoff")
    if found is None:
        return [problem]
    problems = list(found["spacing"])
    if found["status"] != 200 or found["count"] != 20:
        problems.append(f"20 inputs on a key at its quota ended {found['status']}")
    return problems


def claim_prompt() -> list[str]:
    found, problem = run_probe("prompt")
    if found is None:
        return [problem]
    if found["status"] != 200 or found["first"] is None:
        return [f"a plain request answered {found['status']}"]
    if found["first"] > 0.25 or found["total"] > 0.5:
        return [f"a request answered at once took {found['total']:.2f}s"]
    return []


CLAIMS = {
    "batches": claim_batches,
    "no-retry": claim_no_retry,
    "backoff": claim_backoff,
    "prompt": claim_prompt,
    "unit-tests": base.claim_unit_tests,
    "limits": base.claim_limits,
    "stand-in": base.claim_stand_in,
}


def main(argv: list[str]) -> int:
    if len(argv) == 2 and argv[0] == "--probe" and argv[1] in PROBES:
        print(json.dumps(PROBES[argv[1]]()))
        return 0
    if len(argv) != 1 or argv[0] not in CLAIMS:
        print(f"usage: grade_embed.py {'|'.join(CLAIMS)}", file=sys.stderr)
        return 2
    problems = CLAIMS[argv[0]]()
    for line in problems:
        print(line)
    if not problems:
        print(f"{argv[0]}: holds")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
