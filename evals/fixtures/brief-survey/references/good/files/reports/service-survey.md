# Service behavior

Chat uses /v1/chat; its default is chat-large-3. The small alias resolves to chat-small-3
(config/chatsvc.ini). The inbound bucket holds 21 requests at 10 per second. The body limit is
65536 bytes; the embedding batch limit is 16 (config/limits.conf).
A provider 429 ends as caller 503; a provider 404 ends as 502 (chatsvc/routes.py).
An inbound 429 is a separate local limit response.
Retryable provider statuses are 429, 500, 502, 503 and 504, with 3 total attempts.
A 404 is terminal. The millisecond hint takes priority over the seconds hint.
With both headers the delay is 1.5 seconds; attempt 3 without hints waits 0.4 seconds
(chatsvc/retry.py). Live provider quotas are UNVERIFIED; no provider was called.
