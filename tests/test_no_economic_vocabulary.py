"""No always-loaded surface or shipped template carries a banned economic word.

Price metaphors (cost, budget, cheap, minimal, efficient) can read to a model as token thrift and
pull it toward under-delivery, while the contract asks for complete satisfaction over the
lifespan. This is a design choice no evaluation has measured; a reference that quotes a source's
own wording, such as docs/evaluations.md, is not held to it, and neither is README.md, which is
written for people and names cost efficiency as an aim.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BANNED = re.compile(r"\b(?:cost|budget|cheap|minimal)\w*\b|\b(?:in)?efficien\w*\b", re.IGNORECASE)
LISTED = """AGENTS.md OutcomeBound.md docs/tickets.md
templates/managed-block.agents.md.tmpl templates/spec/design.md
templates/spec/plan.md templates/fragment-local.md templates/goal/goal.md
templates/tickets/issue-template.md"""
TREES = ("fragments", "skills")


def test_no_surface_carries_economic_vocabulary() -> None:
    paths = [ROOT / name for name in LISTED.split()]
    paths += [path for tree in TREES for path in sorted((ROOT / tree).rglob("*.md"))]
    hits = {str(p.relative_to(ROOT)): BANNED.findall(p.read_text("utf-8")) for p in paths}
    assert not {path: words for path, words in hits.items() if words}
