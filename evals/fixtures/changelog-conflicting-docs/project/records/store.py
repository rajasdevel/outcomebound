"""Reading the records file: one record a row, with the columns day, kind and title."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

COLUMNS = ("day", "kind", "title")


@dataclass(frozen=True)
class Record:
    day: str  # YYYY-MM-DD
    kind: str
    title: str


def load(path: Path) -> list[Record]:
    with path.open(newline="", encoding="utf-8") as handle:
        return [Record(row["day"], row["kind"], row["title"]) for row in csv.DictReader(handle)]
