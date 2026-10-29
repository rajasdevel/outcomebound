"""Apply and check the overnight investigation references, one ticket at a time."""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def solution(session, module):
    session.write(
        f"datapipe/{module}.py",
        (HERE / "solutions" / f"{module}.py.in").read_text(encoding="utf-8"),
    )
    session.write(
        f"tests/test_{module}.py",
        (HERE / "solutions" / f"test_{module}.py.in").read_text(encoding="utf-8"),
    )
    session.run("python3", "-B", "-m", "unittest", f"tests.test_{module}", "-q")


def apply(session):
    solution(session, "audit")
    result = session.script(
        "import json\nfrom datapipe.audit import report\n"
        "print(json.dumps(report('data/nightly.sqlite','2026-10-21'), indent=2))\n"
    )
    session.write("docs/nightly-audit.json", result)
    session.write(
        "docs/nightly.md",
        "# Delivery audit\n\nThe join mixed days, parts and attempts. Use the last "
        "committed attempt per part.\nFailed retries do not erase a commit. Rejection "
        "rows belong to that exact attempt.\n",
    )
    session.commit(
        "audit: reconcile source parts with committed attempts",
        "datapipe/audit.py",
        "tests/test_audit.py",
        "docs/nightly-audit.json",
        "docs/nightly.md",
    )
    solution(session, "restore_copies")
    session.write(
        "docs/restore-copies.md",
        "# Archive selection\n\nUse missing parts from the corrected audit. Verify "
        "generation, root and bytes before ranking copies.\nThe newer alpha copies are "
        "corrupt or stale. One epsilon part has no valid copy.\n",
    )
    session.commit(
        "restore: select verified copies of missing parts",
        "datapipe/restore_copies.py",
        "tests/test_restore_copies.py",
        "docs/restore-copies.md",
    )
    session.replace(
        "datapipe/manifests.py",
        "    resolved = set()",
        "    import csv\n\n    resolved = set()\n    keys = {}",
    )
    session.replace(
        "datapipe/manifests.py",
        '        if actual["rows"] != extract.rows:',
        "        table = catalog[extract.table]\n"
        "        seen = keys.setdefault(extract.table, set())\n"
        "        kinds = {column.name: column.kind for column in table.columns}\n"
        '        convert = {"integer": int, "real": float}\n'
        '        with path.open(encoding="utf-8", newline="") as handle:\n'
        "            for row in csv.DictReader(handle):\n"
        "                key = tuple(\n"
        "                    convert.get(kinds[name], str)(row[name]) for name in table.key\n"
        "                )\n"
        "                if key in seen:\n"
        '                    raise ValueError("duplicate primary key across extracts")\n'
        "                seen.add(key)\n"
        '        if actual["rows"] != extract.rows:',
    )
    session.write(
        "tests/test_shards.py", (HERE / "solutions/test_shards.py.in").read_text(encoding="utf-8")
    )
    session.run(
        "python3",
        "-B",
        "-m",
        "unittest",
        "tests.test_shards",
        "tests.test_manifests",
        "tests.test_replay_plan",
        "-q",
    )
    session.write(
        "docs/shard-review.md",
        "# Shard review\n\nDifferent files can hold aliases of one typed key. The "
        "filename cache is not the cause.\nPreflight now keeps a key set for each table "
        "across files. The warehouse stays unchanged.\n",
    )
    session.commit(
        "extracts: reject key collisions across shards",
        "datapipe/manifests.py",
        "tests/test_shards.py",
        "docs/shard-review.md",
    )
    solution(session, "dispatch")
    session.write(
        "docs/retry-identity.md",
        "# Retry identity\n\nThe old queue used feed alone and treated failed attempts as"
        " commits.\nIdentity is feed, part and generation. No clock conversion is "
        "needed.\n",
    )
    session.commit(
        "dispatch: keep retry identity across parts and generations",
        "datapipe/dispatch.py",
        "tests/test_dispatch.py",
        "docs/retry-identity.md",
    )
    solution(session, "nightly")
    result = session.script(
        "import json\nfrom pathlib import Path\nfrom datapipe.catalog import parse\n"
        "from datapipe.nightly import build\n"
        "read=lambda name: json.loads(Path('data/'+name+'.json').read_text(encoding='utf-8'))\n"
        "print(json.dumps(build('data/nightly.sqlite','2026-10-21',Path('data/restore'),"
        "read('copies'),parse(read('restore-catalog')),read('delivery-receipts')), indent=2))\n"
    )
    session.write("docs/nightly-plan.json", result)
    session.write(
        "docs/nightly-plan.md",
        "# Recovery plan\n\nAlpha has one ready job. Delta has a row mismatch, gamma has "
        "an orphan, epsilon lacks a valid copy,\nand zeta has conflicting keys across "
        "shards. These feeds are held as whole feeds. No load ran.\n",
    )
    session.commit(
        "recovery: build a complete validated nightly queue",
        "datapipe/nightly.py",
        "tests/test_nightly.py",
        "docs/nightly-plan.json",
        "docs/nightly-plan.md",
    )
    session.write(
        "docs/decisions/warehouse.json",
        json.dumps(
            {
                "status": "held",
                "path": "datapipe/warehouse.py",
                "owner": "project owner",
                "next_step": "Owner reviews collision evidence before any loader change.",
            },
            indent=2,
        )
        + "\n",
    )
    session.write(
        "docs/decisions/warehouse.md",
        "# Warehouse collision decision\n\nHELD for the project owner. Ignoring conflicts"
        " can discard different rows without notice.\nKeep the strict insert and reject "
        "bad restores before loading. An explicit upsert policy\nis an alternative if "
        "the owner defines conflict ownership. Next: review the collision\nevidence in "
        "the morning, then decide whether a separate loader change is needed.\n",
    )
    session.commit(
        "docs: hold warehouse conflict policy for the owner",
        "docs/decisions/warehouse.json",
        "docs/decisions/warehouse.md",
    )
