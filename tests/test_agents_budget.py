"""The shipped managed block orients agents; it does not install policy enforcement."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "templates/managed-block.agents.md.tmpl"

# The byte and word budget is retired. The inline kernel carries every rule because no
# skill or fragment is read by default. Session cost is measured by evals (install design).


def test_managed_block_is_current_static_contract():
    text = TEMPLATE.read_text(encoding="utf-8")
    assert text.count("outcomebound:begin id=operating-contract") == 1
    assert text.count("outcomebound:end id=operating-contract") == 1
    # The shipped kernel is finished text: no unrendered <PLACEHOLDER> tokens.
    assert not re.search(r"<[A-Z][A-Z_]*>", text)
