"""Which shipped fragments an eval fixture selects. A fragment no fixture selects has no measured
effect: its row here says so, and a change to it reports that effect UNVERIFIED."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# The fragments no fixture selects, each with why: effect UNVERIFIED wherever it is claimed.
UNMEASURED = {
    "client": "no fixture; added for the agency lifecycle",
    "explore": "no fixture",
    "solo": "no fixture",
    "team": "no fixture",
    "ci-release": "no fixture",
    "db-migrations": "no fixture",
    "node-typescript": "no fixture",
}


def _selected() -> set[str]:
    found: set[str] = set()
    for listing in (ROOT / "evals/fixtures").glob("*/fragments"):
        for line in listing.read_text(encoding="utf-8").splitlines():
            if line.strip() and not line.lstrip().startswith("#"):
                found.add(line.strip())
    # A fixture with an `install.json` names its fragments there instead (run.py's fixture_install).
    for install in (ROOT / "evals/fixtures").glob("*/install.json"):
        found.update(json.loads(install.read_text(encoding="utf-8")).get("fragments") or ())
    return found


def test_each_fragment_is_selected_by_a_fixture_or_named_as_unmeasured() -> None:
    """Breaks if a new fragment ships with no fixture and no row saying its effect is unmeasured,
    or if a fragment a fixture now selects is still named unmeasured."""

    shipped = {path.stem for path in (ROOT / "fragments").glob("*/*.md")}
    selected = _selected()
    assert shipped - selected == set(UNMEASURED), "update UNMEASURED and the skills design row"
    assert not selected - shipped, "a fixture selects a fragment that does not ship"
