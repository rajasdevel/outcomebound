# tests/test_changelog.py
import re
from pathlib import Path


def test_changelog_has_unreleased_and_keepachangelog_shape():
    t = Path("CHANGELOG.md").read_text()
    assert "## [Unreleased]" in t
    assert re.search(r"^## \[\d+\.\d+\.\d+\]", t, re.MULTILINE), "no released-version heading"


def test_every_version_heading_has_a_link_reference():
    text = Path("CHANGELOG.md").read_text(encoding="utf-8")
    headings = set(re.findall(r"^## \[([^\]]+)\]", text, re.MULTILINE))
    referenced = set(re.findall(r"^\[([^\]]+)\]: https://", text, re.MULTILINE))
    assert headings <= referenced, (
        f"headings without a link reference: {sorted(headings - referenced)}"
    )
