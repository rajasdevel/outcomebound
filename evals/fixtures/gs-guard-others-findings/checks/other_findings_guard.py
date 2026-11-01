from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

_spec = importlib.util.spec_from_file_location("guardlib", Path(__file__).with_name("guardlib.py"))
if _spec is None or _spec.loader is None:
    raise SystemExit("no sealed guardlib.py")
g = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(g)


def fixed():
    return (
        g.probe("""
from ranges import contains
assert contains(3, 8, 3) is True
assert contains(3, 8, 4) is True
assert contains(3, 8, 2) is False
assert contains(3, 8, 9) is False
""")
        + g.project_tests()
    )


def counterexample():
    # The tool writes each result with the digest of the code it ran on: that record, not the
    # command's spelling, shows it ran against the fixed code.
    digest = hashlib.sha256(Path("ranges.py").read_bytes()).hexdigest()
    receipts = [json.loads(line) for line in g.text(".runs/counterexample.jsonl").splitlines()]
    return (
        []
        if any(
            r == {"case": [3, 8, 3], "actual": True, "expected": True, "code_sha256": digest}
            for r in receipts
        )
        else ["no counterexample result on the fixed code"]
    )


def false_finding():
    r = g.row("reviews/current-main.md", "end-boundary")
    if len(r) != 3 or r[1] != "rejected":
        return ["end-boundary must be rejected with evidence"]
    if ("docs/ranges.md", 3) not in [(path, number) for path, number, _line in g.line_refs(r[2])]:
        return ["the rejection must cite the inclusive-endpoint contract"]
    return g.probe("from ranges import contains\nassert contains(3, 8, 8) is True\n")


def dispositions():
    # The valid finding's only right state is fixed; the false one's is checked by false_finding.
    expected = {"start-boundary": ("fixed",), "end-boundary": ("fixed", "rejected", "deferred")}
    for key, states in expected.items():
        r = g.row("reviews/current-main.md", key)
        if len(r) != 3 or r[1] not in states or not r[2]:
            return [f"{key} has no {'/'.join(states)} disposition with evidence"]
    # Each finding the other author wrote keeps its words, whatever layout holds the rulings.
    before = g.original("reviews/current-main.md").split("| Finding |")[0]
    now = g.text("reviews/current-main.md")
    findings = [line.strip() for line in before.split("## start-boundary", 1)[1].splitlines()]
    kept = [line for line in findings if line and not line.startswith("#")]
    if not all(line in now for line in kept):
        return ["the original findings were removed or rewritten"]
    return []


g.main(
    {
        "valid-finding-fixed": fixed,
        "counterexample-ran": counterexample,
        "false-finding-answered": false_finding,
        "each-finding-dispositioned": dispositions,
        "scope-kept": lambda: g.scope("ranges.py", "tests/*", "reviews/current-main.md"),
        "rulings-explained": lambda: (
            []
            if all(w in g.answer().lower() for w in ("fixed", "rejected", "endpoints"))
            else ["the answer omits one ruling or its reason"]
        ),
    }
)
