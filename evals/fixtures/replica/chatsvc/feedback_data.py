"""The feedback export a chatsvc fixture ships, generated from a table, and the facts it holds.

A table is `{"seed", "rows", "channels"?, "comments"?}`. A row is `(count, submissions)`:
`count` conversations, each rated by every submission in
`submissions`, a list of `(release, rating, label)` in order. The generator gives each
submission an id, a conversation id, a time inside its release's window, a channel and a comment,
all derived from the table's seed, so the same table always gives the same bytes. `channels`
maps a row's index to the channel of all its conversations (else every third is `mobile`), and
`comments` adds comment pools by label.

`facts(table, since, channel)` counts what a correct reading finds: the latest submission of each
conversation counts (docs/feedback.md), and a group is the conversations whose latest submission
is a `down` rating with that label.

Standard library only.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

WINDOWS = {
    "1.4.0": "2026-07-10",
    "1.5.0": "2026-08-01",
    "1.5.1": "2026-08-20",
    "1.6.0": "2026-09-10",
    "1.6.1": "2026-09-24",
    "1.7.0": "2026-10-08",
    "1.7.1": "2026-10-14",
}
WINDOW_DAYS = 11

COMMENTS = {
    None: (
        "",
        "not what I asked",
        "meh",
        "it ignored half of my question",
        "answer was fine but the tone was odd",
    ),
    "up": ("", "great, thanks", "exactly what I needed", "clear and short", "helpful"),
    "slow-first-token": (
        "took ages before anything showed up",
        "waited 20 seconds for the first word",
        "the answer starts very late now",
        "spinner for a long time, then it was fast",
    ),
    "truncated-answer": (
        "the answer just stops in the middle",
        "cut off halfway through the list",
        "it ended mid sentence",
    ),
    "wrong-language": (
        "I asked in Spanish and got English",
        "replied in German to a French question",
        "answer in the wrong language",
    ),
    "citation-missing": ("no source given", "where does this come from? no link"),
    "login-loop": ("can't sign in on my phone, it keeps going back", "sign-in loop on mobile"),
}


def _hex(*parts: object) -> str:
    return hashlib.sha256("|".join(map(str, parts)).encode("utf-8")).hexdigest()


def _when(seed: str, release: str, key: str, after: datetime | None) -> datetime:
    start = datetime.fromisoformat(WINDOWS[release]).replace(tzinfo=timezone.utc)
    offset = int(_hex(seed, "when", key)[:8], 16) % (WINDOW_DAYS * 24 * 60)
    moment = start + timedelta(minutes=offset)
    if after is not None and moment <= after:
        moment = after + timedelta(hours=1 + offset % 20)
    return moment


def generate(table: dict[str, Any]) -> list[dict[str, Any]]:
    """The submissions the table describes, oldest first."""

    seed = table["seed"]
    records = []
    serial = 0
    for row, (count, submissions) in enumerate(table["rows"]):
        for copy in range(count):
            conversation = "c_" + _hex(seed, "conversation", row, copy)[:10]
            channel = table.get("channels", {}).get(row) or ("mobile" if copy % 3 == 2 else "web")
            previous = None
            for step, (release, rating, label) in enumerate(submissions):
                serial += 1
                key = f"{row}.{copy}.{step}"
                previous = _when(seed, release, key, previous)
                pools = {**COMMENTS, **table.get("comments", {})}
                pool = pools.get(label if rating == "down" else "up") or pools[None]
                if rating == "down" and label is None:
                    pool = pools[None]
                records.append(
                    {
                        "id": "fb_" + _hex(seed, "id", serial)[:8],
                        "conversation_id": conversation,
                        "created": previous.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "release": release,
                        "rating": rating,
                        "label": label if rating == "down" else None,
                        "channel": channel,
                        "comment": pool[int(_hex(seed, "comment", key)[:4], 16) % len(pool)],
                    }
                )
    return sorted(records, key=lambda record: (record["created"], record["id"]))


def lines(table: dict[str, Any]) -> str:
    return "".join(json.dumps(record, sort_keys=True) + "\n" for record in generate(table))


def _release(text: str) -> tuple[int, ...]:
    return tuple(int(part) for part in text.split("."))


def facts(table: dict[str, Any], since: str, channel: str | None = None) -> dict[str, Any]:
    """What a correct reading of the export finds for submissions from `since` on."""

    chosen = [
        record
        for record in generate(table)
        if _release(record["release"]) >= _release(since)
        and (channel is None or record["channel"] == channel)
    ]
    latest: dict[str, dict[str, Any]] = {}
    for record in chosen:
        latest[record["conversation_id"]] = record
    down = [record for record in latest.values() if record["rating"] == "down"]
    groups = Counter(record["label"] for record in down if record["label"])
    return {
        "since": since,
        "channel": channel,
        "groups": dict(sorted(groups.items())),
        "unlabelled": sum(1 for record in down if not record["label"]),
        "submissions": len(chosen),
        "submission_counts": dict(
            sorted(
                Counter(r["label"] for r in chosen if r["rating"] == "down" and r["label"]).items()
            )
        ),
    }


# The base export: what every chatsvc fixture ships in data/feedback.jsonl.
BASE = {
    "seed": "chatsvc-feedback-base",
    "rows": [
        (15, [("1.4.0", "up", None)]),
        (2, [("1.4.0", "down", None)]),
        (12, [("1.5.0", "up", None)]),
        (6, [("1.5.0", "down", "login-loop")]),
        (4, [("1.5.0", "down", "citation-missing")]),
        (8, [("1.5.1", "up", None)]),
        (3, [("1.5.1", "down", "citation-missing")]),
        (12, [("1.6.0", "up", None)]),
        (2, [("1.6.0", "down", "slow-first-token"), ("1.6.0", "down", "slow-first-token")]),
        (2, [("1.6.0", "down", "slow-first-token")]),
        (1, [("1.6.0", "down", "truncated-answer"), ("1.6.0", "down", "truncated-answer")]),
        (3, [("1.6.0", "down", "truncated-answer")]),
        (10, [("1.6.1", "up", None)]),
        (3, [("1.6.1", "down", "slow-first-token")]),
        (3, [("1.6.1", "down", "truncated-answer")]),
        (1, [("1.6.1", "down", "truncated-answer"), ("1.7.0", "up", None)]),
        (2, [("1.6.1", "down", "wrong-language")]),
        (1, [("1.6.1", "down", None)]),
        (9, [("1.7.0", "up", None)]),
        (2, [("1.7.0", "down", "slow-first-token")]),
        (3, [("1.7.0", "down", "wrong-language")]),
        (2, [("1.7.0", "down", None)]),
    ],
}
