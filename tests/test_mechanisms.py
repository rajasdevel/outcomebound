"""Every registered mechanism id is named in the contract and the core skill."""

from pathlib import Path

import pytest

from outcomebound_tools.mechanisms import MECHANISMS

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize("mechanism", MECHANISMS)
def test_every_mechanism_id_is_documented_in_the_contract_and_the_skill(mechanism):
    token = f"`{mechanism}`"
    for surface in ("OutcomeBound.md", "skills/using-outcomebound/SKILL.md"):
        text = (ROOT / surface).read_text(encoding="utf-8")
        assert token in text, f"{surface} does not name the {mechanism} mechanism by id"
