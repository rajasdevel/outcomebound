"""The shipped managed block orients agents; it does not install policy enforcement."""

import re
from pathlib import Path

from outcomebound_tools.identity import parse_managed_block

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "templates/managed-block.agents.md.tmpl"

# The kernel is loaded into every session of every adopting project, and the
# contract's own claim is that it does not bloat what it asks a model to read.
# A claim with no gate is a wish, so this is the gate.
#
# The budget applies to the body, not the whole template file with its sentinels,
# because the body is what an adopting project's AGENTS.md carries and what the
# merge moves. Anything past 300 words / 2,300 bytes is a second document, and
# it belongs in a fragment or a skill where a project opts into it.
MAX_WORDS = 300
MAX_BYTES = 2300


def _kernel_body() -> str:
    return parse_managed_block(TEMPLATE.read_text(encoding="utf-8"), "operating-contract").body


def test_managed_block_is_current_static_contract():
    text = TEMPLATE.read_text(encoding="utf-8")
    assert text.count("outcomebound:begin id=operating-contract") == 1
    assert text.count("outcomebound:end id=operating-contract") == 1
    # The shipped kernel is finished text: no unrendered <PLACEHOLDER> tokens.
    assert not re.search(r"<[A-Z][A-Z_]*>", text)


def _over_budget(body: str) -> list:
    """Every way this body exceeds the budget, named with its measurement."""

    words = len(body.split())
    size = len(body.encode("utf-8"))
    over = []
    if words > MAX_WORDS:
        over.append(f"{words} words, over the {MAX_WORDS}-word budget")
    if size > MAX_BYTES:
        over.append(f"{size} bytes, over the {MAX_BYTES}-byte budget")
    return over


def test_the_kernel_body_stays_inside_its_budget():
    over = _over_budget(_kernel_body())
    assert not over, (
        "the kernel body is " + "; ".join(over) + ". Cut it, or move the addition into a "
        "fragment or a skill, where a project opts into reading it."
    )


def test_NEGATIVE_CONTROL_the_budget_catches_a_body_that_grew():
    """The gate has teeth: the shipped body passing is not evidence that anything is
    measured. A body one worked example longer than the budget must be reported, and
    both measurements must be reported independently."""

    body = _kernel_body()
    assert _over_budget(body + " padding" * (MAX_WORDS + 1)) == [
        f"{len(body.split()) + MAX_WORDS + 1} words, over the {MAX_WORDS}-word budget",
        f"{len(body.encode('utf-8')) + 8 * (MAX_WORDS + 1)} bytes, "
        f"over the {MAX_BYTES}-byte budget",
    ]
    # Words alone, without tripping the byte budget: one-character words.
    wordy = " ".join("x" * (MAX_WORDS + 1))
    assert _over_budget(wordy) == [f"{MAX_WORDS + 1} words, over the {MAX_WORDS}-word budget"]
    # Bytes alone, without tripping the word budget: one very long word.
    assert _over_budget("x" * (MAX_BYTES + 1)) == [
        f"{MAX_BYTES + 1} bytes, over the {MAX_BYTES}-byte budget"
    ]
