import subprocess
import sys
from pathlib import Path

import pytest

from outcomebound_tools.artifactcheck import ArtifactCheckError, check_block


def _block(body: str) -> str:
    return (
        "<!-- outcomebound:begin id=operating-contract v=1.0.0 -->\n"
        f"{body}\n"
        "<!-- outcomebound:end id=operating-contract -->"
    )


def test_shipped_template_is_one_valid_nonempty_block():
    check_block(Path("templates/managed-block.agents.md.tmpl").read_text(encoding="utf-8"))


def test_length_is_not_used_as_a_quality_proxy():
    check_block(_block("\n".join(f"useful line {index}" for index in range(60))))


def test_empty_or_malformed_block_is_rejected():
    with pytest.raises(ArtifactCheckError, match="empty"):
        check_block(_block(""))
    with pytest.raises(ArtifactCheckError, match="exactly one"):
        check_block("body only")


def test_active_cli_checks_managed_block_structure():
    result = subprocess.run(
        [sys.executable, "-m", "outcomebound_tools.artifactcheck", "--managed-block"],
        input=_block("body"),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
