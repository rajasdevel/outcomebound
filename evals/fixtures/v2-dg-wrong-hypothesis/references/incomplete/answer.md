Fixed: the account header in `shipyard/notify.py` was misspelt (`X-Acount-Id`), so the provider answered 404. It was not the proxy. `bin/shipyard notify stage "hello"` now succeeds.
