"""CLI boundary checks for the artifact check entry point."""

import subprocess
import sys

GOOD = (
    "<!-- outcomebound:begin id=operating-contract v=1.0.0 -->\n"
    "body\n"
    "<!-- outcomebound:end id=operating-contract -->"
)


def _run(module, stdin_text, *args):
    return subprocess.run(
        [sys.executable, "-m", module, *args],
        input=stdin_text,
        capture_output=True,
        text=True,
    )


def test_artifactcheck_cli_rejects_malformed_block():
    result = _run("outcomebound_tools.artifactcheck", "body only", "--managed-block")
    assert result.returncode == 1
    assert "exactly one" in result.stderr


TWO = (
    "<!-- outcomebound:begin id=operating-contract v=1.0.0 -->\nkernel\n"
    "<!-- outcomebound:end id=operating-contract -->\n\n"
    "<!-- outcomebound:begin id=project-guidance hash=deadbeef v=1.0.0 -->\nguidance\n"
    "<!-- outcomebound:end id=project-guidance -->\n"
)


def test_artifactcheck_cli_selects_a_block_by_id():
    assert _run("outcomebound_tools.artifactcheck", TWO, "--managed-block").returncode == 0
    assert (
        _run(
            "outcomebound_tools.artifactcheck", TWO, "--managed-block", "--id", "project-guidance"
        ).returncode
        == 0
    )
    absent = _run(
        "outcomebound_tools.artifactcheck", TWO, "--managed-block", "--id", "absent-block"
    )
    assert absent.returncode == 1
    assert "no managed block with id" in absent.stderr
