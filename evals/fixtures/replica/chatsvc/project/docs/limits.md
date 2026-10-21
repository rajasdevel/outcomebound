# Limits

`config/limits.conf` holds chatsvc's own limits toward its callers, in the subset of nginx's
`limit_req` syntax that `chatsvc/limits.py` reads. Each zone is a token bucket per caller key
(`$api_key`, the `x-api-key` header): it refills at `rate` and holds `burst + 1` tokens. A caller
over its limit gets `limit_req_status` (429) with `retry-after` and the body
`{"error": "rate_limited", "by": "chatsvc"}`.

These limits are not the provider's quota. A caller's 429 that does not say `"by": "chatsvc"`
came from somewhere else; see [provider](provider.md).

## Current limits

| Path | Zone | Rate | Burst | Body |
| --- | --- | --- | --- | --- |
| `/v1/chat` | chat_v1 | 10/s | 20 | 64k |
| `/v1/embed` | embed | 20/min | 5 | 256k |
| `/v1/feedback` | feedback | 1/s | 5 | 8k |

## Changing a limit

A limit is a capacity decision: raising one lets callers spend more of the provider keys' quota,
which every route on that key shares. Record each change here with its reason and the date.

- 2026-08-02: `/v1/chat` burst 10 → 20, for the support desk's batch replays.
