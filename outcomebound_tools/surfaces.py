"""The form a diagram takes on the session's surface: Mermaid or ASCII.

What this module decides: which row of `adapters/surfaces.json` this session
is, read from its environment, and so which form a diagram shown there takes.
A row matches when every variable it names matches: a string value exactly,
and a null one where the variable is set and not empty. The row matching the
most variables is the surface, and a tie, like no match, is unknown. The form
is `mermaid` only where that row records, with its provenance, that the surface
renders Mermaid, and `ascii` everywhere else. `OUTCOMEBOUND_DIAGRAMS`, the
person's own observation of their surface, outranks the table where it names
one of the two forms.

What it does not decide: whether a diagram is drawn, or what it shows. It
never probes a surface or writes anything, and reads no tracker, store,
network or credential: the table is the distribution's record, and the
variable is the person's.
"""

from __future__ import annotations

import json
from collections.abc import Mapping

from outcomebound_tools import home

__all__ = [
    "DIAGRAMS_VARIABLE",
    "FORMS",
    "UNKNOWN",
    "SurfaceError",
    "diagram_form",
    "session_surface",
    "table",
]

DIAGRAMS_VARIABLE = "OUTCOMEBOUND_DIAGRAMS"
FORMS = ("ascii", "mermaid")
UNKNOWN = "unknown"

_TABLE_PATH = home.ROOT / "adapters" / "surfaces.json"

Rows = Mapping[str, Mapping[str, object]]


class SurfaceError(ValueError):
    """The surface table cannot be read."""


def table() -> Rows:
    """The surface table, read when asked and never at import; refused by name,
    without the engine's checkout path, where it is not a JSON object of rows."""

    prefix = "cannot read the surface table adapters/surfaces.json in the selected engine"
    try:
        raw = json.loads(_TABLE_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        reason = getattr(error, "strerror", None) or str(error)
        raise SurfaceError(f"{prefix}: {reason}") from error
    if not isinstance(raw, dict) or not all(isinstance(row, dict) for row in raw.values()):
        raise SurfaceError(f"{prefix}: it is not a JSON object of rows")
    return raw


def _matched(row: Mapping[str, object], environ: Mapping[str, str]) -> int:
    """How many variables the row names, where every one matches; 0 where any does
    not, and for a row that names none."""

    signals = row.get("signals")
    selector = signals.get("environment") if isinstance(signals, Mapping) else None
    if not isinstance(selector, list):
        return 0
    for entry in selector:
        name = entry.get("name") if isinstance(entry, Mapping) else None
        if not isinstance(name, str):
            return 0
        setting, value = environ.get(name, ""), entry.get("value")
        matches = setting != "" if value is None else setting == value
        if not matches:
            return 0
    return len(selector)


def session_surface(environ: Mapping[str, str], rows: Rows | None = None) -> str:
    """The id of the row this session is, the one matching the most variables, or
    `UNKNOWN` where no row matches or two match equally."""

    rows = table() if rows is None else rows
    counts = {surface_id: _matched(row, environ) for surface_id, row in rows.items()}
    best = max(counts.values(), default=0)
    chosen = [surface_id for surface_id, count in counts.items() if best and count == best]
    return chosen[0] if len(chosen) == 1 else UNKNOWN


def diagram_form(environ: Mapping[str, str], rows: Rows | None = None) -> str:
    """`mermaid` or `ascii`, the form a diagram shown on this session's surface takes.

    `OUTCOMEBOUND_DIAGRAMS` decides where it names one of the two, and the table is
    then not read; any other value is ignored. Otherwise `mermaid` only where the
    session's row records Mermaid as rendered together with the provenance of that
    record, and `ascii` for every other row and for an unknown surface.
    """

    recorded = environ.get(DIAGRAMS_VARIABLE, "").strip().lower()
    if recorded in FORMS:
        return recorded
    rows = table() if rows is None else rows
    row = rows.get(session_surface(environ, rows), {})
    renders = row.get("mermaid") is True and isinstance(row.get("provenance"), Mapping)
    return "mermaid" if renders else "ascii"
