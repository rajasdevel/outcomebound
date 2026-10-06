"""How bytes become text: a UTF-8 byte-order mark, UTF-16 with one, and CRLF.

The engine writes UTF-8 and LF. It reads what a Windows editor or PowerShell 5.1 saved: a file with
a UTF-8 mark, an export or standard input in UTF-16 with a mark. A byte that the console's code page
leaves undefined must not stop a read, since the engine decodes the bytes itself.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from outcomebound_tools import textio
from tests.portable import carried_environment

ROOT = Path(__file__).resolve().parent.parent
TEXT = "Ёлка — naïve\n"


def test_a_utf8_mark_is_dropped_and_utf16_is_read_only_where_asked() -> None:
    assert textio.decode(TEXT.encode("utf-8")) == TEXT
    assert textio.decode(textio.UTF8_BOM + TEXT.encode("utf-8")) == TEXT
    assert textio.decode(TEXT.encode("utf-16"), utf16=True) == TEXT
    assert textio.decode(b"\xfe\xff" + TEXT.encode("utf-16-be"), utf16=True) == TEXT
    with pytest.raises(UnicodeDecodeError):
        textio.decode(TEXT.encode("utf-16"))
    with pytest.raises(UnicodeDecodeError):
        textio.decode("é".encode("cp1252"))


def test_read_text_reads_a_file_as_python_text_mode_does_and_drops_the_mark(tmp_path: Path) -> None:
    path = tmp_path / "f.txt"
    path.write_bytes(textio.UTF8_BOM + b"a\r\nb\rc\n")

    assert textio.read_text(path) == "a\nb\nc\n"


def test_fold_and_the_line_ending_of_a_file() -> None:
    assert textio.fold(b"a\r\nb\nc\r\n") == b"a\nb\nc\n"
    assert textio.uses_crlf(b"a\r\nb\r\nc\n") is True
    assert textio.uses_crlf(b"a\nb\nc\r\n") is False
    assert textio.uses_crlf(b"") is False
    assert textio.with_style(b"a\nb\n", b"x\r\ny\r\n") == b"a\r\nb\r\n"
    assert textio.with_style(b"a\nb\n", b"x\ny\n") == b"a\nb\n"
    assert textio.with_style(b"a\nb\n", None) == b"a\nb\n"


BRIEFS = {
    "briefs": [
        {
            "id": "D1",
            "heading": "Ёлка — keep it?",
            "recommend": "yes",
            "recommend_way": "yes",
            "options": [["yes", "a", "b"], ["no", "c", "d"]],
            "checked": {"verdicts": ["PASS"], "text": "ran it"},
            "undo": {"can_be_undone": True, "text": "revert"},
        }
    ]
}


@pytest.mark.parametrize("encoding", ["utf-8", "utf-8-sig", "utf-16"])
def test_a_brief_document_on_standard_input_is_read_in_each_encoding_a_shell_writes(
    encoding: str,
) -> None:
    """`brief -` reads bytes: a UTF-8 mark or UTF-16 does not stop it, and the heading, which
    holds a byte (0x81, in `Ё`) that the ANSI code page leaves undefined, comes through."""

    completed = subprocess.run(
        [
            *(sys.executable, "-m", "outcomebound_tools.decision_brief", "-"),
            *("--symbols", "ascii", "--form", "ascii"),
        ],
        input=json.dumps(BRIEFS, ensure_ascii=False).encode(encoding),
        capture_output=True,
        cwd=ROOT,
        check=False,
        env=carried_environment(PYTHONIOENCODING="utf-8", PYTHONPATH=str(ROOT)),
    )

    assert completed.returncode == 0, completed.stderr.decode("utf-8", "replace")
    assert "Ёлка — keep it?" in completed.stdout.decode("utf-8")
