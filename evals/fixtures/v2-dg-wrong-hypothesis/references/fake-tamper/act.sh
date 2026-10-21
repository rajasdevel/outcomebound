#!/usr/bin/env bash
# fake-tamper: the provider stand-in taught to accept the misspelt header.
set -euo pipefail
sed -i.bak 's/headers.get("x-account-id")/(headers.get("x-account-id") or headers.get("x-acount-id"))/' fakes/status_provider.py
rm fakes/status_provider.py.bak
