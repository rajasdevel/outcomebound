"""Use the replica's note facts with clause-scoped conclusion checks."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def load(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + ".py"))
    if spec is None or spec.loader is None:
        raise ImportError(name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


note, prose = load("replica_note"), load("prose")


def status_of(text):
    if prose.asserted(text, note.OPEN.pattern):
        return "open"
    if prose.asserted(text, note.FIXED.pattern):
        return "fixed"
    if any(not value for value in prose.statements(text, note.OPEN.pattern)):
        return "fixed"
    return None


original_counts = note.check_counts


def counts(text, facts):
    problems = original_counts(text, facts)
    for name, entries in note.mentions(text, facts).items():
        count = facts["groups"][name]["count"]
        for piece, _status, _alone in entries:
            if any(not value for value in prose.statements(piece, rf"\b{count}\b")):
                problems.append("the note negates the count of " + name)
    return problems


note.status_of, note.check_counts = status_of, counts


if __name__ == "__main__":
    sys.exit(note.main(sys.argv[1:]))
