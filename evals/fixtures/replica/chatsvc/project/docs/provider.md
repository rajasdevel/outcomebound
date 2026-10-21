# The provider's API

What chatsvc relies on, from the provider's reference and from what we have observed.

## Calls

- `POST /v1/models/<model>:generate` with `{"messages": [...], "max_tokens": n}` answers
  `{"output": "...", "usage": {"input_tokens": n, "output_tokens": n}}`.
- `POST /v1/models/<model>:embed` with `{"inputs": [...]}` answers `{"vectors": [...]}`. At most
  16 inputs a call; more is a 400 `too_many_inputs`.
- `<model>` is a provider model id, such as `chat-large-3`. Our aliases (`small`, `fast`, ...) mean
  nothing to the provider: a path with an alias in it is a 404 `model_not_found`.
- Every call carries `authorization: Bearer <key>`.

Models we use: `chat-large-3`, `chat-small-3`, `chat-fast-2`, `chat-fast-2-long`,
`embed-small-1`.

## Quota

Each key may make a fixed number of calls in any one-second window (4 on our plan). A call over
the quota is answered 429 with `retry-after-ms`: how long until the key is under its quota again.
A refused call still counts against the window, so a client that retries at once keeps the key
over its quota for every route that shares it. Wait at least `retry-after-ms` before the next
call on that key.

Our keys are pools shared by routes (see `key` in [configuration](configuration.md)):

- `pool-a`: `/v1/chat`, `/v1/embed`.
- `pool-b`: reserved for the fast models.

## Errors

| Status | Meaning | Retry? |
| --- | --- | --- |
| 400 | the request is wrong | no |
| 401 | missing or unknown key | no |
| 404 | unknown path or model | no |
| 429 | over the key's quota | after `retry-after-ms` |
| 5xx | the provider failed | yes, with backoff |
