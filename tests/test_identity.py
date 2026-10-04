"""Managed-block readers: one text, one answer."""

from __future__ import annotations

import pytest

from outcomebound_tools import identity


def test_parse_managed_blocks_agrees_with_find_managed_blocks_on_fenced_sentinels() -> None:
    """Both readers of one text answer the same blocks.

    A sentinel quoted inside fenced code is documentation, not a block; a keyed
    reader that paired sentinels on its own would read the quote as a second
    block, and the two readers would disagree about the same host.
    """

    real = (
        "<!-- outcomebound:begin id=project-guidance v=1.0.0 -->\n"
        "guidance\n"
        "<!-- outcomebound:end id=project-guidance -->"
    )
    text = (
        "intro\n\n```markdown\n"
        "<!-- outcomebound:begin id=operating-contract v=1.0.0 -->\n"
        "body\n"
        "<!-- outcomebound:end id=operating-contract -->\n"
        "```\n\n" + real + "\n"
    )

    parsed = identity.parse_managed_blocks(text)
    assert list(parsed) == ["project-guidance"]
    assert list(parsed) == [block.block_id for block in identity.find_managed_blocks(text)]

    with pytest.raises(identity.IdentityConflict):
        identity.parse_managed_blocks(real + "\n\n" + real)
