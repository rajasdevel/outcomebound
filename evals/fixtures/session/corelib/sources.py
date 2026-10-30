"""Install the released inspection cache and its ordinary caller tests."""

from __future__ import annotations

import runpy
from pathlib import Path

write = runpy.run_path(str(Path(__file__).with_name("build.py")))["write"]

write(
    "tally/sourcecache.py",
    '''
    """Reuse parsed exports during an inspection process."""

    from pathlib import Path
    from tally.readers import read

    _snapshots = {}


    def key(path):
        return Path(path).name


    def load(path):
        name = key(path)
        if name not in _snapshots:
            _snapshots[name] = tuple(read(path))
        return list(_snapshots[name])


    def collect(paths):
        result = []
        seen = set()
        for path in paths:
            name = key(path)
            if name not in seen:
                seen.add(name)
                result.extend(load(path))
        return result


    def clear():
        _snapshots.clear()
    ''',
)
path = Path("tally/inspection.py")
source = path.read_text(encoding="utf-8")
source = source.replace("from tally.readers import read", "from tally.sourcecache import collect")
start = source.index("    result = []")
end = source.index("\n\n\ndef reports", start)
source = source[:start] + "    return collect(paths)" + source[end:]
path.write_text(source, encoding="utf-8")
write(
    "tests/test_sources.py",
    """
    import tempfile
    import unittest
    from pathlib import Path
    from tally.sourcecache import collect, clear


    class SourcesTest(unittest.TestCase):
        def setUp(self):
            clear()
            self.scratch = tempfile.TemporaryDirectory()
            self.addCleanup(self.scratch.cleanup)
            self.addCleanup(clear)
            self.root = Path(self.scratch.name)

        def test_distinct_exports_and_repeated_path(self):
            a, b = self.root / "a.csv", self.root / "b.csv"
            a.write_text("day,project,person,minutes,note\\n2026-04-01,north,worker,30,a\\n")
            b.write_text("day,project,person,minutes,note\\n2026-04-02,south,worker,45,b\\n")
            result = collect(iter([a, b, a]))
            self.assertEqual([entry.minutes for entry in result], [30, 45])
            result.clear()
            self.assertEqual(len(collect([a])), 1)
    """,
)
write(
    "docs/consumers/sources.md",
    """
    # Inspection sources

    Inspection accepts a list of export paths and named plans.
    Repeating the same file path counts that export once. Distinct exports keep all their rows.
    The process cache returns a copy of the loaded entry list. Callers cannot change its list.
    Reports and findings share this loader. Validation and merge use the ordinary readers.
    The report, comparison and snapshot APIs also accept entries supplied directly by a caller.
    `python3 -B -m unittest tests.test_sources tests.test_consumers` covers ordinary reuse.
    """,
)
