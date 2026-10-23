Notices go out again: `bin/shipyard notify stage "hello"` now prints `notice accepted (202)`.

**What it was.** Not the proxy, as it turns out. I ran the failing command first and got the same `404: not found`. The proxy move went fine: a proxy that does not forward gives a 502, not a 404. The 404 came from the request itself. Yesterday afternoon's tidy-up of the request client (`shipyard/notify.py`, "build request headers and endpoints in one place") misspelt the account header as `X-Acount-Id`. Without a valid `X-Account-Id` the provider cannot see the account, and it answers 404 rather than saying the account is missing.

**What I changed.** One line: the header name in `shipyard/notify.py`. The proxy settings are untouched. I sent the notice again (202) and ran the unit tests (`make test`, all pass).
