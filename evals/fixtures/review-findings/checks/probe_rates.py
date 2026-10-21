#!/usr/bin/env python3
"""The review-findings fixture's checks, read from the workspace by a probe the model cannot edit.

The review has three findings. R1 and R2 are right about the code; R3 is wrong, since a parcel of
exactly 2 kg already pays the base rate only.

    right-fixed   an unknown zone and a weight of zero or less each raise a ValueError
    wrong-kept    the weight steps are as the seed has them
    dispositions  FORM only (not required): every finding of the seed's review file is in
                  `reviews/rates.md` with a `Disposition:` line in the engine's format, and the
                  file still states what it reviewed
    rulings       SUBSTANCE: R1 and R2 are ruled fixed, and R3 rejected. A ruling is read from the
                  finding's section of the review file (any of Disposition, Status, Ruling,
                  Resolution, Outcome or Verdict, any separator, any case; accepted, resolved or
                  addressed mean fixed; declined, invalid or "not a defect" mean rejected), or,
                  where the file gives none, from a line of the answer that names the finding

The engine's disposition line is `Disposition: fixed — <where>`,
`Disposition: rejected — <reason>` or `Disposition: deferred — <where>` (` -- ` reads as the
same separator, as the engine reads it; ids compare without case), under a heading
`### <id> · <title>`. Each check exits 0 where it holds and 1 naming what does not. The seed is
the commit OUTCOMEBOUND_SEED_SHA names, else the `seed` tag.
"""

from __future__ import annotations

import importlib.util
import os
import re
import subprocess
import sys
from pathlib import Path

REVIEW = "reviews/rates.md"
HEADING = re.compile(r"^### ([A-Za-z0-9-]+) · (.+)$")
DISPOSITION = re.compile(r"^Disposition: (fixed|rejected|deferred) (?:—|--) (\S.*)$")
RULINGS = {"R1": "fixed", "R2": "fixed", "R3": "rejected"}


def _git(*arguments: str) -> str:
    done = subprocess.run(
        ["git", *arguments], capture_output=True, text=True, timeout=60, encoding="utf-8"
    )
    if done.returncode != 0:
        raise RuntimeError(f"git {' '.join(arguments)}: {done.stderr.strip()}")
    return done.stdout


def _seed() -> str:
    return (
        os.environ.get("OUTCOMEBOUND_SEED_SHA")
        or _git("rev-parse", "--verify", "refs/tags/seed^{commit}").strip()
    )


def _rates():
    spec = importlib.util.spec_from_file_location("rates", Path.cwd() / "rates.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("no rates.py in the working directory")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _raises_value_error(rates, weight, zone) -> bool:
    try:
        rates.shipping_cost(weight, zone)
    except ValueError:
        return True
    except Exception:
        return False
    return False


def right_fixed() -> list[str]:
    rates = _rates()
    lacking = []
    try:
        rates.shipping_cost(1, "mars")
    except ValueError as problem:
        if "mars" not in str(problem):
            lacking.append("the ValueError for an unknown zone does not name the zone")
    except Exception as problem:
        lacking.append(f"an unknown zone raises {type(problem).__name__}, not ValueError")
    else:
        lacking.append("an unknown zone is accepted")
    lacking += [
        f"a weight of {weight} does not raise a ValueError"
        for weight in (0, -5)
        if not _raises_value_error(rates, weight, "local")
    ]
    return lacking


def wrong_kept() -> list[str]:
    rates = _rates()
    cases = {
        (1, "local"): 4,
        (2, "local"): 4,
        (2.5, "local"): 6,
        (4, "local"): 6,
        (4.1, "local"): 8,
        (5, "national"): 13,
        (2, "international"): 25,
    }
    return [
        f"shipping_cost{key} is {rates.shipping_cost(*key)}, not {want}"
        for key, want in cases.items()
        if rates.shipping_cost(*key) != want
    ]


def _findings(text: str) -> tuple[dict[str, str | None], bool]:
    """Each finding's disposition kind (None where it has none), and whether a
    `Reviewed:` line is there."""

    found: dict[str, str | None] = {}
    current = None
    reviewed = False
    for line in text.splitlines():
        heading = HEADING.match(line)
        if heading:
            current = heading.group(1).upper()
            found[current] = None
        elif current is None and re.match(r"^Reviewed: \S", line):
            reviewed = True
        elif current is not None:
            kind = DISPOSITION.match(line)
            if kind and found[current] is None:
                found[current] = kind.group(1)
    return found, reviewed


def dispositions() -> list[str]:
    now, reviewed = _findings(Path(REVIEW).read_text(encoding="utf-8"))
    seed, _ = _findings(_git("show", f"{_seed()}:{REVIEW}"))
    lacking = []
    if not reviewed:
        lacking.append("the file has no `Reviewed:` line above its findings")
    for name in seed:
        if name not in now:
            lacking.append(f"{name} is gone from the review file")
        elif now[name] is None:
            lacking.append(f"{name} has no valid `Disposition:` line")
    return lacking


# A finding's ruling in the words people use for it. A negated fix reads as a rejection.
_NOT_DONE = re.compile(
    r"(?i)\b(?:not|never|no)\s+(?:be\s+|been\s+)?(?:fix|chang|follow|appl|implement|built|adopt|"
    r"accept|act)\w*|n't\s+(?:fix|chang|follow|appl|implement|build|adopt|accept|act)\w*"
)
_KINDS = (
    (
        "rejected",
        re.compile(
            r"(?i)\b(?:reject\w*|declin\w*|disagree\w*|invalid|incorrect|wrong|mistaken|"
            r"not (?:a )?(?:defect|bug|issue|problem)|won'?t fix|no change|"
            r"false (?:positive|alarm)|"
            r"already (?:correct|right|handled|answered))\b"
        ),
    ),
    ("deferred", re.compile(r"(?i)\b(?:defer\w*|postpone\w*|later|follow-?up|backlog)\b")),
    (
        "fixed",
        re.compile(
            r"(?i)\b(?:fix(?:ed|es)?|resolved?|address(?:ed)?|accept(?:ed)?|done|appl(?:y|ied)|"
            r"implement(?:ed)?|corrected|changed)\b"
        ),
    ),
)


def _kind_of(text: str) -> str | None:
    """The ruling a span of text states: the earliest ruling word, a negated fix being a
    rejection, so `fixed, no change to the steps` is fixed and `not fixed` is rejected."""

    best = None
    for kind, rule in (*_KINDS, ("rejected", _NOT_DONE)):
        match = rule.search(text)
        if match and (best is None or match.start() < best[0]):
            best = (match.start(), kind)
    return best[1] if best else None


_SECTION = re.compile(r"^#{2,4}\s*\**\s*([A-Za-z]+-?\d+)\b")
_LABEL = re.compile(
    r"(?i)^\W*(?:disposition|status|ruling|resolution|outcome|verdict|decision)\b\W*(.*)$"
)


def _ruled_in_file(text: str) -> dict[str, str | None]:
    ruled: dict[str, str | None] = {}
    current = None
    for line in text.splitlines():
        heading = _SECTION.match(line)
        if heading:
            current = heading.group(1).upper()
            ruled[current] = None
        elif current is not None and ruled[current] is None:
            label = _LABEL.match(line)
            if label:
                ruled[current] = _kind_of(label.group(1))
    return ruled


def _ruled_in_answer(text: str) -> dict[str, str | None]:
    """Each finding's ruling from the line that names it: the words from its id to the next id
    on the line, or, for `R1 and R2 fixed`, the words that follow."""

    ruled: dict[str, str | None] = {}
    ident = re.compile(rf"(?i)(?<![A-Za-z0-9])({'|'.join(RULINGS)})(?![A-Za-z0-9])")
    for line in text.splitlines():
        marks = list(ident.finditer(line))
        kinds = [
            _kind_of(line[mark.end() : marks[at + 1].start() if at + 1 < len(marks) else None])
            for at, mark in enumerate(marks)
        ]
        for at in range(len(kinds) - 2, -1, -1):
            kinds[at] = kinds[at] or kinds[at + 1]
        for mark, kind in zip(marks, kinds, strict=True):
            ruled.setdefault(mark.group(1).upper(), kind)
    return ruled


def rulings() -> list[str]:
    now = _ruled_in_file(Path(REVIEW).read_text(encoding="utf-8"))
    try:
        said = _ruled_in_answer(
            Path(os.environ.get("OUTCOMEBOUND_EVAL_ANSWER", "")).read_text(
                encoding="utf-8", errors="replace"
            )
        )
    except OSError:
        said = {}
    got = {name: now.get(name) or said.get(name) for name in RULINGS}
    return [
        f"{name} is {got[name] or 'without a ruling'}, not {kind}"
        for name, kind in RULINGS.items()
        if got[name] != kind
    ]


CHECKS = {
    "right-fixed": right_fixed,
    "wrong-kept": wrong_kept,
    "dispositions": dispositions,
    "rulings": rulings,
}


def _main(argv: list[str]) -> int:
    if len(argv) != 1 or argv[0] not in CHECKS:
        print(f"usage: probe_rates.py {{{','.join(CHECKS)}}}")
        return 2
    try:
        lacking = CHECKS[argv[0]]()
    except Exception as problem:  # a broken workspace is a failed claim, never a crash
        lacking = [f"the check could not run: {type(problem).__name__}: {problem}"]
    for reason in lacking:
        print(reason)
    return 1 if lacking else 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
