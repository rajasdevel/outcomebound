"""Preserve seed files outside the delivered work areas, including intermediate commits."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path


def check(root, owned, *, preserved=(), protected=None):
    root = Path(root)

    def git(*args):
        done = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=True)
        return done.stdout.splitlines()

    seed = set(git("ls-tree", "-r", "--name-only", "seed"))
    preserved = (
        set(preserved)
        | (seed & {"tools/ob_receipts.py", "tests/conftest.py"})
        | {
            name
            for name in seed
            if name.startswith("tests/") and not name.startswith("tests/test_")
        }
    )
    forbidden = {
        name
        for name in seed
        if not owned(name) or any("draft" in part.lower() for part in Path(name).parts)
    } | set(preserved)
    touched = set(git("diff", "--name-only", "seed"))
    touched.update(git("ls-files", "--others", "--exclude-standard"))
    committed = set(git("log", "--format=", "--name-only", "seed..HEAD"))
    touched.update(committed)
    touched.discard("")
    protected = protected or {}
    outside = {name for name in touched if name in forbidden or not owned(name)} - set(protected)
    outside.update(committed & set(protected))
    for name, digest in protected.items():
        path = root / name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            outside.add(name)
    return ["out-of-scope files changed: " + ", ".join(sorted(outside))] if outside else []
