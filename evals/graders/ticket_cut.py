#!/usr/bin/env python3
"""Judge where the ticket drafts written since the seed cut, from their blocks alone.

    ticket_cut.py gate GATE PATH...          each draft whose bounds cover GATE covers every
                                             PATH itself, or through a draft it names in
                                             `blocked-by`, at any depth
    ticket_cut.py apart A B                  some draft covers A, some draft covers B, and no
                                             draft covers both
    ticket_cut.py ordered SHARED A B         the draft that covers A and the draft that covers B
                                             both cover SHARED, or one names the other in
                                             `blocked-by`
    ticket_cut.py entered NEW INVENTORY      some draft covers NEW, and each draft that covers
                                             NEW covers INVENTORY

Each argument is a repository-relative path. A draft is what `drafts.py` beside this file
finds: a file added or changed since the seed that carries a ticket block. Its id is its file
name without the extension, as `blocked-by` names a sibling draft. What a `bounds` entry
covers is the engine's rule, from the OutcomeBound checkout on PYTHONPATH. Each exits 0 where
it holds and 1 naming what does not; lines starting `observed:` never change the exit status.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent


def _drafts_module():
    spec = importlib.util.spec_from_file_location("ticket_drafts", _HERE / "drafts.py")
    if spec is None or spec.loader is None:
        raise ImportError(f"no drafts.py beside {Path(__file__).name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def blocks() -> dict[str, tuple[tuple[str, ...], tuple[str, ...]]]:
    """Each draft's id, with its `bounds` and its `blocked-by` as written."""

    from outcomebound_tools.tickets_model import parse_block

    read = {}
    for path in _drafts_module().drafts():
        fields, _messages = parse_block(path.read_text(encoding="utf-8", errors="replace"))
        read[path.stem] = (tuple(fields.bounds), tuple(fields.blocked_by))
        print(
            f"observed: {path.as_posix()} bounds {list(fields.bounds)} "
            f"blocked-by {list(fields.blocked_by)}"
        )
    return read


def _covers(bounds: tuple[str, ...], path: str) -> bool:
    from outcomebound_tools.tickets_bounds import covers

    return any(covers(entry, path) for entry in bounds)


def _before(read: dict, start: str) -> list[str]:
    """`start` and every draft it waits on through `blocked-by`, at any depth."""

    seen, queue = [], [start]
    while queue:
        current = queue.pop(0)
        if current in seen or current not in read:
            continue
        seen.append(current)
        queue += list(read[current][1])
    return seen


def gate(gate_path: str, paths: list[str]) -> list[str]:
    read = blocks()
    if not read:
        return ["no draft was written"]
    gates = [name for name, (bounds, _after) in read.items() if _covers(bounds, gate_path)]
    if not gates:
        return [f"no draft's bounds cover {gate_path}"]
    return [
        f"{name} covers {gate_path}, and neither its bounds nor a draft it names in "
        f"blocked-by cover {path}"
        for name in gates
        for path in paths
        if not any(_covers(read[link][0], path) for link in _before(read, name))
    ]


def _holders(read: dict, path: str) -> list[str]:
    return [name for name, (bounds, _after) in read.items() if _covers(bounds, path)]


def _apart(read: dict, first: str, second: str) -> list[str]:
    if not read:
        return ["no draft was written"]
    lacking = [
        f"no draft's bounds cover {path}" for path in (first, second) if not _holders(read, path)
    ]
    lacking += [
        f"{name} covers both {first} and {second}"
        for name in sorted(set(_holders(read, first)) & set(_holders(read, second)))
    ]
    return lacking


def apart(first: str, second: str) -> list[str]:
    return _apart(blocks(), first, second)


def ordered(shared: str, first: str, second: str) -> list[str]:
    read = blocks()
    lacking = _apart(read, first, second)
    if lacking:
        return lacking
    one, other = _holders(read, first), _holders(read, second)
    for left in one:
        for right in other:
            both = _covers(read[left][0], shared) and _covers(read[right][0], shared)
            after = right in read[left][1] or left in read[right][1]
            if not (both or after):
                return [
                    f"{left} and {right} do not both cover {shared}, and neither names the "
                    "other in blocked-by"
                ]
    return []


def entered(new: str, inventory: str) -> list[str]:
    read = blocks()
    if not read:
        return ["no draft was written"]
    adding = _holders(read, new)
    if not adding:
        return [f"no draft's bounds cover {new}"]
    return [
        f"{name} covers {new} and not {inventory}"
        for name in adding
        if not _covers(read[name][0], inventory)
    ]


def _main(argv: list[str]) -> int:
    try:
        if len(argv) >= 3 and argv[0] == "gate":
            lacking = gate(argv[1], argv[2:])
        elif len(argv) == 3 and argv[0] == "apart":
            lacking = apart(argv[1], argv[2])
        elif len(argv) == 4 and argv[0] == "ordered":
            lacking = ordered(argv[1], argv[2], argv[3])
        elif len(argv) == 3 and argv[0] == "entered":
            lacking = entered(argv[1], argv[2])
        else:
            print(
                "usage: ticket_cut.py {gate GATE PATH... | apart A B | ordered SHARED A B | "
                "entered NEW INVENTORY}"
            )
            return 2
    except ImportError as problem:
        lacking = [f"the engine is not importable from PYTHONPATH: {problem}"]
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as problem:
        lacking = [f"the check could not run: {problem}"]
    for reason in lacking:
        print(reason)
    return 1 if lacking else 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
