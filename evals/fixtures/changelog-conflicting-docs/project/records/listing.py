"""Choosing records for an export, and writing them out as CSV."""

from __future__ import annotations

import csv
from collections.abc import Iterable
from typing import TextIO

from records.store import COLUMNS, Record


def select(
    records: Iterable[Record],
    since: str | None = None,
    until: str | None = None,
    kind: str | None = None,
) -> list[Record]:
    """The records on or after `since`, on or before `until`, and of `kind`, in file order.
    Days are YYYY-MM-DD, so they compare as text."""

    chosen = []
    for record in records:
        if since and record.day <= since:
            continue
        if until and record.day > until:
            continue
        if kind and record.kind != kind:
            continue
        chosen.append(record)
    return chosen


def write(records: Iterable[Record], out: TextIO) -> None:
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(COLUMNS)
    for record in records:
        writer.writerow((record.day, record.kind, record.title))
