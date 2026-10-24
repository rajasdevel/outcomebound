#!/usr/bin/env bash
# good: the value is looked up in the design; nothing is changed.
set -euo pipefail
grep -n "30 seconds" docs/specs/notify/design.md >/dev/null
