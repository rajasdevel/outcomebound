"""Bounded lexical report records shared by the requirement and visual graders."""

from __future__ import annotations

import re


def records(text: str) -> list[str]:
    """Wrapped paragraphs and list records, with their immediate section heading.

    This is a bounded lexical check, not a semantic judge. An explicit source or
    section replaces the heading; separate sentences never share their labels.
    """

    records: list[str] = []
    heading = ""
    words: list[str] = []

    def flush() -> None:
        if words:
            records.extend(heading + " " + part for part in re.split(r"[.!?;]\s+", " ".join(words)))
            words.clear()

    for raw in text.splitlines():
        line = raw.strip().strip("*")
        if not line:
            flush()
        elif line.endswith(":") or line.startswith("#") or re.match(r"(?i)^source:", line):
            flush()
            heading = line
        elif re.match(r"^(?:[-*+] |\d+[.)] |\|)", line):
            flush()
            words.append(line)
        else:
            if not words and records:
                heading = ""
            words.append(line)
    flush()
    return records
