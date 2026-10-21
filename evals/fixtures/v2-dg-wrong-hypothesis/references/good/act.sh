#!/usr/bin/env bash
# good: the failing notice sent first, then the header fixed in the client.
set -euo pipefail
sed -i.bak 's/X-Acount-Id/X-Account-Id/' shipyard/notify.py && rm shipyard/notify.py.bak
