#!/usr/bin/env bash
# incomplete: the header fixed without sending the failing notice first.
set -euo pipefail
sed -i.bak 's/X-Acount-Id/X-Account-Id/' shipyard/notify.py && rm shipyard/notify.py.bak
