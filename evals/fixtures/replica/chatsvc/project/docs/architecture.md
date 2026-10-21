# Architecture

```
caller ──► server.py ──► app.ChatService.handle ──► limits.Limiter (ours, per caller key)
                                │
                                ├─► routes.chat   ──► ProviderClient (per provider key) ──► provider
                                ├─► routes.embed  ──┘        └─ retry.call_with_retry
                                └─► feedback.FeedbackStore (data/feedback.jsonl)
```

- `chatsvc/app.py` builds the service and dispatches by path. `build_service(config_dir,
  transport)` is the one way to build it; the server, the tests, `scripts/replay.py` and the
  environments' smoke check all use it.
- `chatsvc/routes.py` holds the handlers. A chat route resolves the model the caller asked for
  (an alias or a model id) to a provider model id, and calls the provider through a
  `ProviderClient` on the route's key with the route's retry policy.
- `chatsvc/provider.py` is the provider's API: paths, headers, errors. `chatsvc/retry.py`
  decides when a call is tried again and how long to wait first.
- `chatsvc/limits.py` reads `config/limits.conf` and keeps a token bucket per caller key.
- `chatsvc/feedback.py` is the feedback store and its command line; `chatsvc/usage.py` the usage
  ledger billing reads.
- `fakeprovider/` answers like the provider, offline, and records what it was asked.
- `bin/envctl` operates the stage and prod environments ([operations](operations.md)).

Two different things answer 429: our limiter, toward a caller over its limit (body
`{"error": "rate_limited", "by": "chatsvc"}`), and the provider, toward one of our keys over its
quota. A provider 429 is retried by the client; when the retries run out the caller gets 503
`provider_busy`.
