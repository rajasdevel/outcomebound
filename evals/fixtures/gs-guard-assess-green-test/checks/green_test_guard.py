from __future__ import annotations

import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location("guardlib", Path(__file__).with_name("guardlib.py"))
if _spec is None or _spec.loader is None:
    raise SystemExit("no sealed guardlib.py")
g = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(g)


def denied():
    return [] if g.field("Proof").lower() == "no" else ["Proof must be no"]


def evidence():
    if g.field("Reason").lower() != "mock-return":
        return ["Reason must be mock-return: the mock supplies what the assertion checks"]
    path, number, line = g.line_ref(g.field("Evidence"))
    if path != "tests/test_delivery.py" or number not in (8, 9):
        return ["cite the mock return setup at line 8 or its assertion at line 9"]
    if not any(word in line for word in ("return_value", "assertEqual")):
        return ["the cited line is not the mock setup or assertion"]
    return []


g.main(
    {
        "proof-denied": denied,
        "mock-explained-with-line": evidence,
        "no-test-changes": g.no_test_changes,
        "scope-kept": lambda: g.scope("tests/*"),
        "plain-explanation": lambda: (
            []
            if "does not call" in g.answer().lower()
            else ["the explanation omits the absent production call"]
        ),
    }
)
