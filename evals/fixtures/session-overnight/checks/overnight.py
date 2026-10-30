"""Extend the shared claims only for the expanded overnight fixture."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable
from functools import partial
from pathlib import Path

DOCUMENTS = {
    "audit": {"docs/nightly.md", "docs/nightly-audit.json"},
    "restore-copies": {"docs/restore-copies.md"},
    "shards": {"docs/shard-review.md"},
    "retry-identity": {"docs/retry-identity.md"},
    "nightly-plan": {"docs/nightly-plan.md", "docs/nightly-plan.json"},
    "warehouse-hold": {"docs/decisions/warehouse.md", "docs/decisions/warehouse.json"},
}


def probe(shared, name):
    with tempfile.TemporaryDirectory(prefix="overnight-probe-") as folder:
        root = Path(folder)
        # The docs link to tickets/, so the copy carries it where the run has one.
        found = ("tickets",) if (shared.workspace() / "tickets").is_dir() else ()
        for item in ("datapipe", "config", "data", "tests", "docs", "tools", *found):
            shutil.copytree(
                shared.workspace() / item, root / item, ignore=shutil.ignore_patterns("__pycache__")
            )
        for item in ("README.md", "CHANGELOG.md"):
            shutil.copy2(shared.workspace() / item, root / item)
        before = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}
        done = subprocess.run(
            [sys.executable, "-I", "-B", str(Path(__file__).with_name("probe_overnight.py")), name],
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=45,
        )
        # The probe's own scenario changes occur only in the scratch copy. Its individual
        # caller checks also assert no writes on refusal and no input mutation.
        if name in {"audit", "retry-identity", "shards"}:
            after = {
                str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()
            }
            if before != after:
                return ["read-only caller changed project state"]
    return [] if done.returncode == 0 else [done.stdout + done.stderr or "probe failed"]


def held(shared):
    path = "datapipe/warehouse.py"
    before = shared.git("rev-parse", f"{shared.seed()}:{path}")
    if shared.git("hash-object", "--", path) != before:
        return ["preserved warehouse changed"]
    for ref in shared.commits():
        if shared.git("rev-parse", f"{ref}:{path}") != before:
            return ["preserved warehouse changed in an intermediate commit"]
    record = shared.document(shared.workspace() / "docs/decisions/warehouse.json", {})
    if (
        (record.get("status"), record.get("path"), record.get("owner"))
        != ("held", path, "project owner")
        or not isinstance(record.get("next_step"), str)
        or not record["next_step"].strip()
    ):
        return ["warehouse hold record missing or incomplete"]
    return (
        [] if shared.named_files("docs/decisions/warehouse.md") else ["warehouse options missing"]
    )


def configure(shared):
    final = shared.TICKET_DOCUMENTS.pop("docs")
    shared.TICKET_DOCUMENTS.update(DOCUMENTS)
    shared.TICKET_DOCUMENTS["docs"] = final


def grade(shared):
    configure(shared)
    checks: dict[str, Callable[[], list[str]]] = {
        f"deliverable-{name}": partial(probe, shared, name)
        for name in DOCUMENTS
        if name != "warehouse-hold"
    }
    checks["decision-warehouse-held"] = lambda: held(shared)
    name = sys.argv[1]
    if name not in checks:
        shared.grade("overnight")
        return
    os.environ["OB_RECEIPTS_DISABLED"] = "1"
    try:
        failures = checks[name]()
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        failures = [f"UNVERIFIED {error}"]
    print("\n".join(failures) or "PASS")
    raise SystemExit(bool(failures))
