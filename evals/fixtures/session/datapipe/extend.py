"""Copy deterministic project sources, then write the small generated catalog."""

from __future__ import annotations

import json
import runpy
import sys
from pathlib import Path


def main(source: Path, mode: str) -> None:
    for template in sorted(source.rglob("*")):
        if not template.is_file():
            continue
        relative = template.relative_to(source)
        if mode == "incident" and relative.as_posix() == "docs/specs/preflight.md":
            continue
        target = Path(str(relative).removesuffix(".in"))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(template.read_bytes())
    if mode == "incident":
        manifest = Path("datapipe/manifests.py")
        manifest.write_text(
            manifest.read_text(encoding="utf-8").split("\ndef preflight(")[0], encoding="utf-8"
        )
    Path("docs/replay-api.md").write_text(
        "# Current replay API\n\n"
        "replay_plan.plan accepts a checkpoint, event dictionaries and request bounds.\n"
        "It returns source, generation, windows, deferred and next_offset.\n"
        "The current caller uses an observed high watermark. Window membership includes\n"
        "both ends. The module does not write checkpoint storage.\n",
        encoding="utf-8",
    )
    tables = [
        {
            "name": name,
            "key": [key],
            "columns": [
                {"name": key, "kind": "integer", "nullable": False},
                {"name": "received_at", "kind": "text", "nullable": False},
                {"name": "source", "kind": "text", "nullable": True},
            ],
        }
        for name, key in (("orders", "order_id"), ("events", "event_id"))
    ]
    Path("data/catalog.json").write_text(
        json.dumps({"tables": tables}, indent=2) + "\n", encoding="utf-8"
    )
    Path("config/retention.json").write_text(
        '{"raw_days": 90, "archive_required": true}\n', encoding="utf-8"
    )
    runpy.run_path(str(source.parent / "fleet.py"))["generate"]()


if __name__ == "__main__":
    main(Path(sys.argv[1]), sys.argv[2])
