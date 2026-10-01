"""The `tickets` fragment states project facts about the layer, and adds no rule.

An adopting project's AGENTS.md points at it with its condition, and a model reads it
when that condition holds. What is pinned here is structural: it parses as a setup
fragment, its Mechanisms slot names only registry mechanisms, and its pointer line
carries its condition and installed path. The composer's own structural rules are
pinned in `tests/test_fragments.py`.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from outcomebound_tools import facts
from outcomebound_tools.fragments import (
    Fragment,
    FragmentError,
    load_all,
    parse_fragment,
)
from outcomebound_tools.identity import parse_managed_block
from outcomebound_tools.mechanisms import MECHANISMS

ROOT = Path(__file__).resolve().parent.parent
FRAGMENT = ROOT / "fragments" / "setup" / "tickets.md"
SLOT_HEADING = re.compile(r"^\*\*(?P<slot>[^*]+)\*\* — ", re.MULTILINE)
BACKTICKED = re.compile(r"`([^`]+)`")


def _fragment() -> Fragment:
    return parse_fragment(FRAGMENT.read_text(encoding="utf-8"), str(FRAGMENT))


def _slots(fragment: Fragment) -> dict[str, str]:
    """The fragment's slot bodies, read from the public `body` the parser returns."""

    body = fragment.body
    matches = list(SLOT_HEADING.finditer(body))
    bodies: dict[str, str] = {}
    for index, match in enumerate(matches):
        stop = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        bodies[match.group("slot").strip()] = body[match.end() : stop].strip()
    return bodies


def test_the_tickets_fragment_parses_and_is_a_setup_fragment() -> None:
    fragment = _fragment()
    assert fragment.id == "tickets"
    assert fragment.family == "setup"
    # Empty by decision: the only honest signal is `.outcomebound/tickets.json`,
    # and the composer's matcher skips every path under `.outcomebound/`, so such
    # a pattern could never fire. A setup fragment is a person's choice on adopt.
    assert fragment.detect == ()
    assert load_all(ROOT)["tickets"].id == "tickets"


def test_its_mechanisms_are_registry_ids_only() -> None:
    fragment = _fragment()
    named = BACKTICKED.findall(_slots(fragment)["Mechanisms"])
    assert named, "the mechanisms slot names no mechanism"
    unknown = sorted(set(named) - set(MECHANISMS))
    assert not unknown, f"not registry ids: {unknown}"
    assert tuple(named) == fragment.mechanisms
    # A verb is a command, not a mechanism: only this slot's backticks are read
    # as registry ids, so a command spelled here is refused by the parser.
    text = FRAGMENT.read_text(encoding="utf-8")
    spelled = text.replace("**Mechanisms** — `", "**Mechanisms** — `verify`; `", 1)
    assert spelled != text
    with pytest.raises(FragmentError, match="names unknown mechanism\\(s\\): verify"):
        parse_fragment(spelled, str(FRAGMENT))


def test_it_is_reached_through_a_pointer_with_its_condition() -> None:
    fragment = load_all(ROOT)["tickets"]
    assert fragment.condition
    block = facts.pointers([fragment], [])
    assert block is not None
    parsed = parse_managed_block(block, facts.POINTERS)
    assert parsed.body == f"- {fragment.condition}: read .outcomebound/fragments/tickets.md"
