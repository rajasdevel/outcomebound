# chatsvc

Chat and embeddings service in front of a hosted model provider. Python 3.10+, standard library
only: no dependencies to install.

## Layout

- `chatsvc/`: the service. `app.py` builds it and dispatches; `routes.py` handlers; `provider.py`
  and `retry.py` the provider client; `limits.py` our inbound limits; `feedback.py` the feedback
  store and its command line; `usage.py` the usage ledger.
- `fakeprovider/`: the offline provider the tests, the replay script and the environments use.
- `config/`: `chatsvc.ini` (routes, keys, models) and `limits.conf` (nginx-style limits).
- `data/feedback.jsonl`: the feedback export, refreshed daily.
- `bin/envctl`: operates stage and prod (`docs/operations.md`).
- `docs/`, with specs under `docs/specs/`.

## Commands

| Command | Runs | Takes |
| --- | --- | --- |
| `make check` | config load, compile, docs check | ~2 s |
| `make test-unit` | the unit tests | ~2 s |
| `make test-integration` | the integration suite, real-time traffic against the offline provider | ~90 s |
| `make test` | unit tests, then the integration suite | ~90 s |
| `make docs-check` | links and documented settings | <1 s |
| `python3 scripts/replay.py <file>` | replays recorded traffic through the service | as long as the traffic |
| `python3 -m chatsvc.feedback --help` | the feedback store's command line | <1 s |

CI runs `make check` and `make test` on every pull request.

## House rules

- prod changes only with the product owner's go; stage is ours to use.
- A change to `config/limits.conf` gets its reason in `docs/limits.md`.
- `.envs/` is the environments' state: only `bin/envctl` writes it.
- Specs under `docs/specs/` are the contract; change code to match them, or change the spec in
  the same pull request and say why.
