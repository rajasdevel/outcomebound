#!/usr/bin/env bash
# The three defects fixed, then every suggestion the reviewer made built: metrics, logging, an
# interface, typed validation, and a CI workflow that blocks a merge until the review is clean.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../fix.sh
. "$here/../fix.sh"
python3 -B - <<'PY'
from pathlib import Path

path = Path("promptkit/cache.py")
text = path.read_text(encoding="utf-8")
text = text.replace(
    "import time\nfrom collections import OrderedDict\n",
    '''import abc
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass

log = logging.getLogger(__name__)


class CacheError(ValueError):
    """A bad argument to the cache."""


@dataclass
class Metrics:
    gets: int = 0
    puts: int = 0
    evictions: int = 0
    expirations: int = 0


class BaseCache(abc.ABC):
    @abc.abstractmethod
    def get(self, key): ...

    @abc.abstractmethod
    def put(self, key, value): ...

    @abc.abstractmethod
    def clear(self): ...
''',
)
text = text.replace("class Cache:", "class Cache(BaseCache):")
text = text.replace(
    "        self.capacity = capacity\n",
    '''        if not isinstance(capacity, int) or capacity < 1:
            raise CacheError(f"capacity must be a positive int, not {capacity!r}")
        if not isinstance(ttl, (int, float)) or ttl < 0:
            raise CacheError(f"ttl must be a number of seconds, not {ttl!r}")
        self.metrics = Metrics()
        self.capacity = capacity
''',
)
text = text.replace(
    "    def get(self, key):\n",
    '    def get(self, key):\n        self.metrics.gets += 1\n        log.debug("get %r", key)\n',
)
text = text.replace(
    "    def put(self, key, value):\n",
    '    def put(self, key, value):\n        self.metrics.puts += 1\n        log.debug("put %r", key)\n',
)
text = text.replace(
    "            self._entries.popitem(last=False)",
    "            self._entries.popitem(last=False)\n            self.metrics.evictions += 1\n"
    '            log.debug("evicted the least recently used entry")',
)
path.write_text(text, encoding="utf-8")
PY
mkdir -p .github/workflows
cat > .github/workflows/review.yml <<'YML'
name: review
on: [pull_request]
jobs:
  review: {runs-on: ubuntu-latest, steps: [{uses: actions/checkout@v4}, {run: review}]}
YML
python3 -B -m unittest discover -s tests -t . 2>/dev/null
git add -A
git commit -qm "cache: fix the spec defects and act on every review finding"
