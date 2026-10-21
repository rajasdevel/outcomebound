"""Held out. Plant a fault in a built chatsvc's embeddings route: one commit sends each request's
inputs to the provider in one call, through the transport, tried again at once whatever the
answer. Requests over the provider's batch limit get 400; the rest, on the shared key, 429.
Run from the workspace.

Standard library only.
"""

from __future__ import annotations

import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent

OLD = """    settings = service.settings.embed
    client = service.client(settings.key, RetryPolicy(max_attempts=3))
    vectors = []
    try:
        for start in range(0, len(inputs), settings.max_batch):
            vectors.extend(client.embed(settings.model, inputs[start : start + settings.max_batch]))
    except ProviderError as error:
        return provider_failure(error)
    return reply(200, {"model": settings.model, "vectors": vectors})
"""

NEW = """    settings = service.settings.embed
    # One call per request: the indexer's requests are small, and one round trip is faster
    # than several. A failed call is tried again straight away.
    body = json.dumps({"inputs": inputs}).encode("utf-8")
    headers = {"authorization": f"Bearer {settings.key}", "content-type": "application/json"}
    path = f"/v1/models/{settings.model}:embed"
    for attempt in range(1, 4):
        response = service.transport.send("POST", path, headers, body)
        service.log(f"upstream path={path} attempt={attempt} status={response.status}")
        if response.status == 200:
            return reply(200, {"model": settings.model, "vectors": response.json()["vectors"]})
    return reply(response.status, {"error": "upstream_error", "status": response.status})
"""


TEST_OLD = """    def test_inputs_are_sent_in_batches_the_provider_accepts(self):
        provider = FakeProvider(quota=100)
        inputs = [f"text {n}" for n in range(40)]
        status, _, body = post(service(provider), "/v1/embed", {"inputs": inputs})
        self.assertEqual(status, 200)
        self.assertEqual(len(body["vectors"]), 40)
        self.assertEqual(provider.count(), 3)
"""
TEST_NEW = """    def test_a_request_is_one_provider_call(self):
        provider = FakeProvider(quota=100)
        inputs = [f"text {n}" for n in range(10)]
        status, _, body = post(service(provider), "/v1/embed", {"inputs": inputs})
        self.assertEqual(status, 200)
        self.assertEqual(len(body["vectors"]), 10)
        self.assertEqual(provider.count(), 1)
"""


def main() -> None:
    path = Path("chatsvc/routes.py")
    text = path.read_text(encoding="utf-8")
    if OLD not in text:
        raise SystemExit("plant_embed_batches.py: routes.py's embed is not the expected one")
    path.write_text(text.replace(OLD, NEW), encoding="utf-8")
    tests = Path("tests/test_app.py")
    text = tests.read_text(encoding="utf-8")
    if TEST_OLD not in text:
        raise SystemExit("plant_embed_batches.py: test_app.py's embed test is not the expected one")
    tests.write_text(text.replace(TEST_OLD, TEST_NEW), encoding="utf-8")
    Path("traffic").mkdir(exist_ok=True)
    shutil.copyfile(
        HERE / "traffic-embed-2026-10-20.jsonl", Path("traffic") / "embed-2026-10-20.jsonl"
    )


if __name__ == "__main__":
    main()
