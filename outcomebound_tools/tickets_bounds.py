"""What a `bounds` entry grants.

Whether an entry grants the whole repository, as a pure function of the text. It reads no
block and reports no message: `tickets_model` does both.
"""

from __future__ import annotations

__all__ = ["whole_repository"]

# The glob characters a `bounds` entry may carry, and the one place they are named.
_GLOBS = "*?["


def _literal_prefix(entry: str) -> str:
    """The part of an entry before its first glob character."""

    cuts = [entry.index(character) for character in _GLOBS if character in entry]
    return entry[: min(cuts)] if cuts else entry


def whole_repository(entry: str) -> bool:
    """Whether an entry grants the whole repository: its literal prefix is empty or `.`."""

    return _literal_prefix(entry) in ("", ".")
