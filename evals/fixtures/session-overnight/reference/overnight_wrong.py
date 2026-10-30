"""A complete reference with one plausible wrong result for each added ticket."""

from __future__ import annotations

import argparse
import runpy
from pathlib import Path

ITEMS = ("audit", "restore-copies", "shards", "retry-identity", "nightly-plan", "warehouse-hold")


def mutate(work, item):
    modules = {
        "audit": "audit",
        "restore-copies": "restore_copies",
        "retry-identity": "dispatch",
        "nightly-plan": "nightly",
    }
    if item in modules:
        path = f"datapipe/{modules[item]}.py"
        import subprocess

        original = subprocess.run(
            ["git", "show", f"seed:{path}"],
            cwd=work,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        )
        (work / path).write_text(original.stdout, encoding="utf-8")
    elif item == "shards":
        path = work / "datapipe/manifests.py"
        path.write_text(
            path.read_text(encoding="utf-8").replace(
                "seen = keys.setdefault(extract.table, set())", "seen = set()"
            ),
            encoding="utf-8",
        )
    else:
        path = work / "datapipe/warehouse.py"
        path.write_text(
            path.read_text(encoding="utf-8").replace(
                "self.conn.executemany(sql, batch)",
                'self.conn.executemany(sql.replace("INSERT INTO", "INSERT OR IGNORE INTO"), batch)',
            ),
            encoding="utf-8",
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("workspace", type=Path)
    parser.add_argument("records", type=Path)
    parser.add_argument("--item", choices=ITEMS, required=True)
    parser.add_argument("--mutation-only", action="store_true")
    args = parser.parse_args()
    if not args.mutation_only:
        shared = runpy.run_path(
            str(Path(__file__).resolve().parents[2] / "session/datapipe/reference.py")
        )
        session = shared["Session"](args.workspace, args.records, "overnight")
        shared["overnight"](session, "good")
    mutate(args.workspace, args.item)


if __name__ == "__main__":
    main()
