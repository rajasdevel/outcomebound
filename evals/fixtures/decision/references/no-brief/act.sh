#!/usr/bin/env bash
# no-brief: the sources are read and nothing is changed, but the answer is plain prose.
set -euo pipefail
cat docs/compatibility.md >/dev/null
git log -p --format=%B -3 >/dev/null
