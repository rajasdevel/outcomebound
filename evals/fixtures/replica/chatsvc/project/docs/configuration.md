# Configuration

`config/chatsvc.ini` is read once at start. Paths are relative to the repository root.

## [service]

- `listen`: host:port the server binds, `127.0.0.1:8080` by default.
- `limits`: the limits file, `config/limits.conf` ([limits](limits.md)).
- `feedback`: the feedback store, `data/feedback.jsonl` ([feedback](feedback.md)).

## [provider]

- `base`: the provider's base URL.

## [route:<name>]

One section per inbound chat path. Every route on one provider key shares that key's quota
([provider](provider.md)).

- `path`: the inbound path.
- `key`: the provider key pool the route calls with.
- `default_model`: the provider model id used when a request names none.
- `aliases`: `alias=model` pairs, comma separated; a request may name an alias or a model id.
- `max_attempts`: provider attempts per request, the first included ([routing spec](specs/provider-routing.md)).
- `timeout`: seconds per provider attempt.

Routes:

- `/v1/chat` (`route:primary`): pool-a, `chat-large-3` by default; aliases `large`, `small`.

## [embed]

- `path`: the inbound embeddings path, `/v1/embed`.
- `key`: the provider key pool.
- `model`: the embedding model id.
- `max_batch`: the most inputs the provider takes in one call (16).
