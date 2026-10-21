# Spec: provider routing

Status: accepted (2026-07). Applies to every chat route.

## Requirements

1. **Model resolution.** A request may name a model by alias or by provider model id, or name
   none. The route resolves it before any provider call: no name → the route's
   `default_model`; an alias of the route → the model it names; anything else → passed on as a
   model id. Only provider model ids ever reach a provider path.
2. **One client per key.** Calls go through `ProviderClient` on the route's key, so every call
   carries the key and is logged as `upstream path=... attempt=n status=...`.
3. **Retries.** A 429 or 5xx answer is retried, up to the route's `max_attempts` attempts in all.
   Any other answer is final: a 4xx other than 429 is never retried.
4. **Waiting.** Before retrying, wait what the provider asked (`retry-after-ms`, else
   `retry-after`), else back off from 100 ms, doubling, up to 2 s. Never retry at once: a key is
   shared, and a refused call still counts against its quota ([provider](../provider.md)).
5. **No delay on success.** A call that is answered at once is not delayed.
6. **What the caller sees.** Success: 200 with the model id used. Provider still busy after the
   last attempt: 503 `provider_busy` with `retry-after`. Any other provider answer: 502
   `provider_rejected` with the provider's status.

## Rationale

The pooled keys are shared across routes and tenants. A route that retries at once turns one
tenant's burst into a 429 storm for every route on the key, which is how 1.4.0's first week went.
