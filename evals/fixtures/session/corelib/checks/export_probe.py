"""Independent caller probes for atomic inspection bundles, run in the workspace."""

SOURCE = r"""
from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from tally.inspection import export

with tempfile.TemporaryDirectory() as folder:
    root = Path(folder)
    data = root / "entries.csv"
    data.write_text(
        "day,project,person,minutes,note\n"
        "2026-04-02,north,worker,21,first\n"
        "2026-04-02,south,worker,42,next\n",
        encoding="utf-8",
    )
    plans = root / "plans.json"
    plans.write_text(
        json.dumps({"version": 1, "plans": {"all": {}, "north": {"projects": ["north"]}}}),
        encoding="utf-8",
    )
    target = root / "bundle"
    record = export(iter([data]), plans, target, output="json")
    assert record["format_version"] == 1
    assert [row["name"] for row in record["files"]] == ["all.json", "north.json"]
    assert json.loads((target / "all.json").read_text(encoding="utf-8")) == {
        "schema_version": 1,
        "rows": [
            {"project": "north", "entry_count": 1, "total_minutes": 21},
            {"project": "south", "entry_count": 1, "total_minutes": 42},
        ],
        "entry_count": 2,
        "total_minutes": 63,
    }
    for row in record["files"]:
        content = (target / row["name"]).read_bytes()
        assert row == {
            "name": row["name"],
            "byte_count": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
        }, "manifest does not bind member content"
    assert json.loads((target / "manifest.json").read_text(encoding="utf-8")) == record
    before = {path.name: path.read_bytes() for path in target.iterdir()}
    try:
        export([data], plans, target, output="json")
    except (ValueError, FileExistsError):
        pass
    else:
        raise AssertionError("existing destination accepted")
    assert {path.name: path.read_bytes() for path in target.iterdir()} == before
    original = Path.write_text

    def fail_second(path, text, **kwargs):
        if path.name == "north.json":
            raise OSError("synthetic member failure")
        return original(path, text, **kwargs)

    paths_before = set(root.iterdir())
    with patch.object(Path, "write_text", fail_second):
        try:
            export([data], plans, root / "failed", output="json")
        except OSError as error:
            assert str(error) == "synthetic member failure"
        else:
            raise AssertionError("member failure hidden")
    assert set(root.iterdir()) == paths_before, "partial bundle or scratch remains"
    for name in ("../outside", "manifest"):
        plans.write_text(json.dumps({"version": 1, "plans": {name: {}}}), encoding="utf-8")
        try:
            export([root / "missing.csv"], plans, root / "unsafe", output="json")
        except ValueError:
            pass
        else:
            raise AssertionError("unsafe plan name accepted")
    assert not (root / "unsafe").exists()
"""
