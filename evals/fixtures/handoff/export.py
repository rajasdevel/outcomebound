#!/usr/bin/env python3
"""Print the tracker export that holds one hand-off base's accepted ticket.

    export.py <base>             the export
    export.py --number <base>    the ticket's number alone

The ticket is `<base>/ticket.md` beside this file: its first line, `# <title>`, is the issue's
title and the rest is its body. The export is the shape the pinned query in
`templates/tickets/github-export.graphql` returns, for one open issue in `example/timelog`
carrying the `ob-ticket` label, which is the maintainer's acceptance. `task.sh` hands it to
`outcomebound tickets brief --input`, so the brief is the engine's own rendering. Nothing
here reaches a tracker. Standard library only, like the rest of `evals/`.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
# Each base's ticket number: the id its brief, its package and its hand-over name.
NUMBERS = {"duration": 7, "invoice": 8, "tags": 9}
REPOSITORY = "example/timelog"
ACCEPTED = "2026-10-01T09:00:00Z"


def _connection(nodes: list[dict[str, object]]) -> dict[str, object]:
    return {"nodes": nodes, "pageInfo": {"hasNextPage": False}}


def ticket(base: str) -> tuple[int, str, str]:
    """The base's ticket number, title and body."""

    heading, _, body = (HERE / base / "ticket.md").read_text(encoding="utf-8").partition("\n")
    if not heading.startswith("# "):
        raise SystemExit(f"export.py: {base}/ticket.md does not open with `# <title>`")
    return NUMBERS[base], heading[2:].strip(), body.lstrip("\n")


def export(base: str) -> list[dict[str, object]]:
    number, title, body = ticket(base)
    issue = {
        "number": number,
        "title": title,
        "body": body,
        "state": "OPEN",
        "stateReason": None,
        "createdAt": ACCEPTED,
        "closedAt": None,
        "updatedAt": ACCEPTED,
        "lastEditedAt": None,
        "url": f"https://tracker.invalid/{REPOSITORY}/issues/{number}",
        "author": {"login": "maintainer"},
        "assignees": _connection([]),
        "labels": _connection([{"name": "ob-ticket"}]),
        "parent": None,
        "blockedBy": _connection([]),
        "subIssuesSummary": {"total": 0},
        "comments": {"pageInfo": {"hasNextPage": False}, "nodes": []},
        "timelineItems": {
            "pageInfo": {"hasPreviousPage": False},
            "nodes": [
                {
                    "__typename": "LabeledEvent",
                    "createdAt": ACCEPTED,
                    "actor": {"login": "maintainer"},
                    "label": {"name": "ob-ticket"},
                }
            ],
        },
    }
    page = {
        "nameWithOwner": REPOSITORY,
        "issues": {"pageInfo": {"hasNextPage": False, "endCursor": None}, "nodes": [issue]},
    }
    return [{"data": {"repository": page}}]


def main(argv: list[str]) -> int:
    number = argv[:1] == ["--number"]
    names = argv[1:] if number else argv
    if len(names) != 1 or names[0] not in NUMBERS:
        print(f"usage: export.py [--number] {{{' | '.join(sorted(NUMBERS))}}}", file=sys.stderr)
        return 2
    print(NUMBERS[names[0]] if number else json.dumps(export(names[0]), indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
