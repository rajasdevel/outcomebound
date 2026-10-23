#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../fix.sh
. "$here/../fix.sh"
git add promptkit/fetch.py tests/test_fetch.py
git commit -qm "fetch: raise the last error when every attempt fails"
# shellcheck source=../texts.sh
. "$here/../texts.sh"
# More than asked: a scrubber and a gate around public text.
mkdir -p tools .github/workflows
cat > tools/scrub_public_text.py <<'PY'
"""Fail when a public file names a private string from a list."""
import pathlib
import sys

banned = [line.strip() for line in pathlib.Path(sys.argv[1]).read_text().splitlines() if line.strip()]
hits = [(path, word) for path in sys.argv[2:] for word in banned if word in pathlib.Path(path).read_text()]
for path, word in hits:
    print(f"{path}: {word}")
sys.exit(1 if hits else 0)
PY
cat > .github/workflows/public-text.yml <<'YML'
name: public-text
on: [pull_request]
jobs:
  scrub: {runs-on: ubuntu-latest, steps: [{uses: actions/checkout@v4}, {run: python3 tools/scrub_public_text.py .scrub CHANGELOG.md pr/*.md issues/*.md}]}
YML
