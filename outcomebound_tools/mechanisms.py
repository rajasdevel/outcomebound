"""The mechanism registry: seven ids and the kernel phrase each one names.

Fragments, the routing skill, the public contract, and the eval scorer all refer
to mechanisms. Without one registry they drift into seven spellings of the same
thing — exactly the split a single registry exists to prevent. Ids are stable and
machine-checkable, and `tests/test_mechanisms.py` holds every id to the contract and
the core skill; each label paraphrases the kernel's phrase for its mechanism.

``broad-suite`` and ``runtime-check`` deliberately share the kernel sentence that
names them together; they are separate ids because a fragment must be able to
trigger one without the other.
"""

from collections.abc import Iterable

MECHANISMS = (
    "spec",
    "goal-envelope",
    "failing-test-first",
    "review",
    "policy-gate",
    "broad-suite",
    "runtime-check",
)

LABELS = {
    "spec": "a spec when later work relies on a decision the code cannot show",
    "goal-envelope": "a goal envelope (pre-authorized bounds) for autonomous or multi-session work",
    "failing-test-first": "a failing test first when it adds signal",
    "review": (
        "independent review when a miss would reach users and no check you can run would catch it"
    ),
    "policy-gate": "the project's own gate at a protected boundary, never one you author",
    "broad-suite": "broad or runtime checks when the changed risk reaches that layer",
    "runtime-check": "broad or runtime checks when the changed risk reaches that layer",
}


def is_mechanism(name: str) -> bool:
    return name in LABELS


def unknown(names: Iterable[str]) -> list[str]:
    """Return the supplied names that are not registry ids, in order."""

    return [name for name in names if name not in LABELS]
