"""A pinned `github` export built for tests.

Every connection the query asks for is complete, so a test varies only what it names.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

REPO = "owner/project"
LABEL = "ob-ticket"

# How the reader maps a state: its three states, as the host writes them.
_STATES: Mapping[str, tuple[str, str | None]] = {
    "open": ("OPEN", None),
    "closed": ("CLOSED", "COMPLETED"),
    "dropped": ("CLOSED", "NOT_PLANNED"),
}


def body(
    *,
    bounds: str = "src",
    hold: str = "no",
    done_when: Sequence[str] = ("example-claim",),
    text: str = "## Outcome\nSomething becomes observably true.",
    extra: Sequence[str] = (),
) -> str:
    """One issue body: `text`, then the ticket block with `extra` keys last."""

    return "\n".join(
        [
            text,
            "",
            "<!-- outcomebound:begin id=ticket v=1 -->",
            f"bounds: {bounds}",
            f"human-only: {hold}",
            "done-when:",
            *[f"- {item}" for item in done_when],
            *extra,
            "<!-- outcomebound:end id=ticket -->",
        ]
    )


def issue(
    number: int,
    *,
    text: str | None = None,
    labels: Sequence[str] = (LABEL,),
    state: str = "open",
    parent: int | None = None,
    blocked_by: Sequence[int] = (),
    title: str = "",
) -> dict[str, object]:
    """One export node. `text` is the issue body, `body()` where it is None."""

    def complete(nodes: Sequence[Mapping[str, object]] = ()) -> dict[str, object]:
        return {"nodes": list(nodes), "pageInfo": {"hasNextPage": False}}

    def relation(other: int) -> dict[str, object]:
        return {"number": other, "repository": {"nameWithOwner": REPO}}

    raw_state, reason = _STATES[state]
    return {
        "number": number,
        "title": title or f"Issue {number}",
        "body": body() if text is None else text,
        "state": raw_state,
        "stateReason": reason,
        "url": f"https://tracker.invalid/{REPO}/issues/{number}",
        "labels": complete([{"name": name} for name in labels]),
        "parent": None if parent is None else relation(parent),
        "blockedBy": complete([relation(other) for other in blocked_by]),
        "subIssuesSummary": {"total": 0},
    }


def export(*nodes: Mapping[str, object]) -> list[object]:
    """The one export page the reader is given, holding the nodes named."""

    return [
        {
            "data": {
                "repository": {
                    "nameWithOwner": REPO,
                    "issues": {"nodes": list(nodes), "pageInfo": {"hasNextPage": False}},
                }
            }
        }
    ]
