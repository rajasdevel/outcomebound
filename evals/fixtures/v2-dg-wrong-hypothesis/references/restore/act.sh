#!/usr/bin/env bash
# restore: tried the old proxy host, put the settings back, then fixed the header.
set -euo pipefail
sed -i.bak 's/X-Acount-Id/X-Account-Id/' shipyard/notify.py && rm shipyard/notify.py.bak
