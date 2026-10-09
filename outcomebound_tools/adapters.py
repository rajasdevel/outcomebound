"""The harness table, adapters/harnesses.json, read once and answered from by row.

Placement is driven by each row's data, never by a hardcoded path, and an unknown
name fails closed. A harness outside the table is adopt's `generic` route, not a
row here (`outcomebound_tools.adopt`).
"""

import json
from pathlib import Path

from outcomebound_tools import home

_TABLE_PATH = home.ROOT / "adapters" / "harnesses.json"
_TABLE = None


class AdapterError(KeyError):
    """The harness table is unavailable or does not describe the requested harness.

    It is a ``KeyError``, for callers that catch one, and reports its own
    message: ``KeyError.__str__`` is ``repr(args[0])``, which would reach an
    installer's stderr as a quoted, escaped string instead of a sentence.
    """

    def __str__(self) -> str:
        return str(self.args[0]) if len(self.args) == 1 else super().__str__()


def _reason(error: Exception) -> str:
    """Why a table could not be read, without naming where the engine lives.

    `OSError.__str__` carries the absolute filename, and these messages reach a
    target-side refusal envelope: an operator debugging their own project does
    not need this engine's checkout path, so source paths stay out of what they
    are shown. The parse and decode errors say nothing about location, so they
    pass through as written.
    """

    return getattr(error, "strerror", None) or str(error)


def _table() -> dict:
    """Read the harness table on first use, never at import time.

    Reading at import would make every consumer of this module depend on the
    engine checkout's directory layout, so an install that moved the package would
    fail at import with no usable message.
    """

    global _TABLE
    if _TABLE is None:
        try:
            _TABLE = json.loads(_TABLE_PATH.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise AdapterError(
                "cannot read the harness table adapters/harnesses.json in the "
                f"selected engine: {_reason(error)}"
            ) from error
    return _TABLE


def table_path() -> Path:
    """Where this distribution's harness table lives (public seam).

    A function rather than the constant so a caller that verifies the selected
    source reads the path this module will actually read, including when a test
    rebinds it.
    """

    return _TABLE_PATH


def table() -> dict:
    """The harness table, read on first use (public seam).

    The one cached mapping, not a copy: `row()` is the copying reader, and a
    caller that only needs membership must not pay for a deep copy of it.
    """

    return _table()


def harness_names() -> list:
    """Every harness name the table declares, sorted.

    Membership, not a recommendation: the profile reader admits `explicit` plus
    exactly these names, so one list answers "is this a harness this
    distribution knows?" for every caller.
    """

    return sorted(_table())


def row(harness: str) -> dict:
    """The table row for ``harness``, or an AdapterError naming the remedy.

    Placement reads the ROW, never a hardcoded path: a harness whose native
    skill directory lives in the data is a harness this engine can install for
    without a code change, and two harnesses sharing one directory (codex and
    amp) say so in one place instead of two.
    """

    entry = _table().get(harness)
    if not isinstance(entry, dict) or not entry:
        # Only remedies that work from here: `generic` is adopt's route, not a
        # table row, so offering it would send an operator back to this refusal.
        raise AdapterError(
            f"unknown harness {harness!r}; select one of: "
            + ", ".join(harness_names())
            + "; a profile may also select 'explicit' for no native placement"
        )
    # A COPY: the table is a process-wide cache — a caller that adjusted "its"
    # row would change what every later caller reads.
    return dict(entry)


def native_skill_root(harness: str) -> str:
    """The row's ``skill_install_path`` without its trailing slash.

    Reporting the path of an unverified row is not installing into it: whether
    anything is projected there is the profile's separate acceptance, and
    keeping the two questions apart is why this returns the candidate rather
    than an empty string.
    """

    return str(row(harness)["skill_install_path"]).rstrip("/")


def instruction_file(harness: str) -> str | None:
    """The row's instruction file, or None for a route that has none.

    `FILE@REF` rows record `FILE` here, so a caller that needs the host — to
    measure it, or to ask whether it routes — never parses import syntax.
    """

    value = row(harness).get("instruction_file")
    return value if isinstance(value, str) and value else None


def or_list(names: tuple[str, ...]) -> str:
    """``a``, ``a or b``, ``a, b or c``: names as a sentence lists alternatives."""

    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " or " + names[-1]


def is_verified(harness: str) -> bool:
    """Whether this row's install path is operator-verified. Loading is separate."""

    return bool(row(harness).get("verified", False))


def byte_cap(harness: str | None) -> int | None:
    """The row's documented project-document byte cap, or None if it has none.

    The one place a row's ``doc_byte_cap`` becomes a byte count, so every
    caller measures against the same number. A blank harness has no row to
    read; an unknown one is refused by `row`, not answered with None.
    """

    if not harness:
        return None
    cap = row(harness).get("doc_byte_cap")
    # `isinstance(True, int)` is True; a boolean is not a byte count.
    return cap if isinstance(cap, int) and not isinstance(cap, bool) else None
