# Fast route and offline jobs

Finish `/v2/chat` through both service entry points: HTTP uses `ChatService.handle` and console
jobs use `job_manifest.parse` then `job_runner.run_jobs` (or `run_manifest`). A console job for
`/v2/chat` currently returns the old default model. Trace the path through the callers. Do not
change the old default or make the batch use a second service. `chat` and `/v1/chat` stay legacy;
`embed` stays `/v1/embed`; an unsupported path or duplicate id rejects the whole manifest before
any transport call. A bad chat body rejects just that job; later valid jobs still run. Preserve
job order and identity. Restore the service's log callback even if a transport raises.

The fast route resolves aliases before transport; default is `chat-fast-2`, `fast` resolves to
it and `fast-long` to `chat-fast-2-long`. Unknown model ids get one final rejected call. Validate
nonempty messages, their roles and string content, and integer max_tokens 1..4096 (default 512,
boolean invalid). Keep legacy chat, embeddings, feedback, auth, limits and health working.

Use the new `BoundedPolicy` only in the fast handler. Its fields are max_attempts=4,
base_delay=0.1, max_delay=2 and now=0 (seconds). For this version, hint(headers) accepts only
finite nonnegative numeric retry-after in seconds, then retry-after-ms; seconds take priority
when both exist. A hint is capped at max_delay. A missing or malformed hint returns None.
Delay uses a hint or min(base_delay * 2**(attempt-1), max_delay). Retry only 429,500,502,503,504,
up to the route's max_attempts; never wait before the first call or after the last. A 404 is
final. A success returns model, output, usage. Exhausted 429 returns 503 provider_busy with
attempts and retry-after rounded up to at least one; other final failures return 502
provider_rejected with status. Keep the old provider client and retry module as found.

Extend diagnostics.summarize(lines), used by offline jobs, with a `models` map from decoded
provider model id to call count. Preserve calls, retries, statuses and paths. An upstream line
is an observed call, including repeated lines in this format; inbound records are not provider
calls. Input paths may percent-encode a model id. Output no credentials or request bodies.

The wire examples and their tests describe the released client. Extend regression coverage
for the new route, batch error isolation, alias resolution, retry limits and report fields.
Tests go in tests/test_feature_day.py. Update docs/provider.md and docs/configuration.md.
The handler and manifest/report integration can be built independently. Subagents are allowed,
not required. Use focused tests for code and docs-check for documents. Commit this item.

## Bounded batch execution and resume

Extend `Job` with depends_on (a tuple of ids, empty by default). A manifest may have an optional
list depends_on. Validate the entire graph before running: unknown ids, duplicate dependencies,
self dependencies and cycles are ManifestError. Forward references are valid. Use a stable
topological order: among jobs whose dependencies are done, take the first in manifest order.
Return job results in manifest order, even when execution order differs.

Extend run_jobs(jobs, service, *, prior=(), max_jobs=None) and run_manifest with the same keyword
options. max_jobs is None or an exact nonnegative integer, never a boolean. It caps service
handle calls, including bad-body calls; provider retries remain the route policy's job. A job
whose dependency did not return 200 gets status 424, model empty, without a service call. An
independent job still runs. A ready job past the budget gets status 0, model empty. No waiting
or network scheduler is needed. This is an offline job runner.

Add resume to the result, beside jobs and upstream. It holds only successful jobs in manifest
order. Each row has exactly id, fingerprint, status=200 and model. A fingerprint is SHA-256 of
UTF-8 JSON for id, normalized path, caller key, body and depends_on list, with sorted keys and
comma/colon separators. Return no raw caller keys or bodies. Prior rows have the same four
fields; id/fingerprint must be nonempty strings, model a string, status an exact integer from
0 to 599. Reject malformed or duplicate prior ids before traffic. Unknown prior ids may be
ignored. Reuse a prior success only when its fingerprint matches current content and all its
current dependencies succeeded. Reused results use no budget and send no traffic. Changed
content and failed prior results run again. Do not mutate jobs or prior records. The service's
original log callback must be restored on success and exception. Test through run_manifest
and run_jobs, including reordered dependencies, an exhausted budget, stale resume content and
a failed dependency beside independent work.

## Owned paths

For this item, edit chatsvc/routes.py, chatsvc/wait_policy.py, chatsvc/job_manifest.py,
chatsvc/job_runner.py and chatsvc/diagnostics.py. You may add Python helpers under chatsvc/.
Keep the other existing source, configuration, tests, stores and environment tools as found.
Put new regression tests in tests/test_feature_day.py. The documents for this item are this
spec, docs/provider.md and docs/configuration.md. Do not add unrequested plans or proof
records. A later request can grant the files it needs.
