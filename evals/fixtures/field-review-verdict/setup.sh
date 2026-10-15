#!/usr/bin/env bash
# cachekit, a lookup service whose last commit adds a time-to-live cache. The commit message
# promises that expired entries are dropped so memory stays bounded; the code never drops them, and
# its tests do not look. The task is a read-only review of that commit.
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
target="${1:?usage: setup.sh <dir> <grading-stage>}"
stage="${2:?usage: setup.sh <dir> <grading-stage>}"
mkdir -p "$target"
cd "$target"
. "$here/../field-common/close.sh"

mkdir -p cachekit tests
printf '"""A small lookup service."""\n' > cachekit/__init__.py
cat > cachekit/lookup.py <<'NOTE'
"""Look up a customer's plan by id."""

PLANS = {"c1": "basic", "c2": "pro"}


def plan_for(customer_id):
    return PLANS.get(customer_id)
NOTE
printf '' > tests/__init__.py
cat > tests/test_lookup.py <<'NOTE'
import unittest

from cachekit.lookup import plan_for


class LookupTest(unittest.TestCase):
    def test_known_customer(self):
        self.assertEqual(plan_for("c2"), "pro")


if __name__ == "__main__":
    unittest.main()
NOTE
cat > Makefile <<'NOTE'
.PHONY: check

check:
	python3 -B -m unittest discover -s tests -t . -q
NOTE
cat > AGENTS.md <<'NOTE'
# cachekit

A lookup service, in `cachekit/`. Python standard library only. `make check` runs the tests.

Read `.outcomebound/skills/using-outcomebound/SKILL.md` before planning work here.
NOTE
field_close field.py
git add -A
git commit -qm "Look up a plan by customer id"

cat > cachekit/cache.py <<'NOTE'
"""A cache whose entries live for a fixed time."""


class TTLCache:
    def __init__(self, ttl):
        self.ttl = ttl
        self._items = {}

    def set(self, key, value, now):
        self._items[key] = (value, now)

    def get(self, key, now):
        hit = self._items.get(key)
        if hit is None:
            return None
        value, stamp = hit
        if now - stamp >= self.ttl:
            return None
        return value

    def size(self):
        return len(self._items)
NOTE
cat > tests/test_cache.py <<'NOTE'
import unittest

from cachekit.cache import TTLCache


class TTLCacheTest(unittest.TestCase):
    def test_a_fresh_entry_is_returned(self):
        cache = TTLCache(ttl=10)
        cache.set("a", 1, now=0)
        self.assertEqual(cache.get("a", now=5), 1)

    def test_a_stale_entry_is_not_returned(self):
        cache = TTLCache(ttl=10)
        cache.set("a", 1, now=0)
        self.assertIsNone(cache.get("a", now=10))


if __name__ == "__main__":
    unittest.main()
NOTE
python3 -B -m unittest discover -s tests -t . -q >/dev/null 2>&1 \
  || { echo "the planted project's own tests must pass" >&2; exit 1; }
find . -name __pycache__ -prune -exec rm -rf {} +
git add -A
git commit -q -F - <<'NOTE'
Add a TTL cache for the plan lookup

Entries expire after `ttl` seconds. Expired entries are dropped, so memory stays bounded when the
service runs for weeks.
NOTE
git tag seed
echo "fixture ready: $target"
