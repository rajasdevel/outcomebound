# The cache fixes, as a person would make them, sourced by the references' act.sh in the
# workspace. `defects` names which to fix (default: all three: expiry recency no-expiry).
defects="${defects:-expiry recency no-expiry}"
DEFECTS="$defects" python3 -B - <<'PY'
import os
from pathlib import Path

chosen = os.environ["DEFECTS"].split()
path = Path("promptkit/cache.py")
text = path.read_text(encoding="utf-8")
if "no-expiry" in chosen:
    text = text.replace(
        "        return self.clock() - stored_at >= self.ttl",
        "        # A ttl of 0 turns expiry off (docs/specs/cache.md, Configuration).\n"
        "        return self.ttl > 0 and self.clock() - stored_at >= self.ttl",
    )
if "expiry" in chosen:
    text = text.replace(
        "        if entry is None:\n            self.misses += 1",
        "        if entry is not None and self._expired(entry[0]):\n"
        "            del self._entries[key]\n"
        "            entry = None\n"
        "        if entry is None:\n            self.misses += 1",
    )
if "recency" in chosen:
    text = text.replace(
        "        self.hits += 1\n        return entry[1]",
        "        self.hits += 1\n        self._entries.move_to_end(key)\n        return entry[1]",
    )
path.write_text(text, encoding="utf-8")

if "no-expiry" in chosen:
    spec = Path("docs/specs/cache.md")
    spec.write_text(
        spec.read_text(encoding="utf-8").replace(
            "An entry is kept for `ttl` seconds. An entry whose",
            "An entry is kept for `ttl` seconds; a `ttl` of 0 keeps it until it is evicted (see\n"
            "Configuration). With a `ttl` above 0, an entry whose",
        ),
        encoding="utf-8",
    )

tests = Path("tests/test_cache.py")
added = {
    "expiry": '''
    def test_an_entry_older_than_ttl_is_a_miss(self):
        clock = Clock()
        cache = Cache(capacity=4, ttl=10, clock=clock)
        cache.put("a", 1)
        clock.now = 10
        self.assertIsNone(cache.get("a"))
        self.assertEqual(cache.misses, 1)
''',
    "recency": '''
    def test_a_read_entry_is_not_the_one_evicted(self):
        cache = Cache(capacity=2, ttl=60, clock=Clock())
        cache.put("a", 1)
        cache.put("b", 2)
        cache.get("a")
        cache.put("c", 3)
        self.assertEqual((cache.get("a"), cache.get("b")), (1, None))
''',
    "no-expiry": '''
    def test_ttl_zero_keeps_entries(self):
        clock = Clock()
        cache = Cache(capacity=4, ttl=0, clock=clock)
        cache.put("a", 1)
        clock.now = 10**6
        cache.purge()
        self.assertEqual(cache.get("a"), 1)
''',
}
body = tests.read_text(encoding="utf-8")
tests.write_text(
    body.replace("\n\nif __name__", "".join(added[name] for name in chosen) + "\n\nif __name__"),
    encoding="utf-8",
)
PY
python3 -B -m unittest discover -s tests -t . 2>/dev/null
