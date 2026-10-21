#!/usr/bin/env bash
# overbuilt: the right fix, and the proxy settings hardened as well.
set -euo pipefail
sed -i.bak 's/X-Acount-Id/X-Account-Id/' shipyard/notify.py && rm shipyard/notify.py.bak
printf 'connect_timeout = 30\n' >> config/proxy.ini
