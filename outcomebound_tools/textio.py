"""How the engine turns bytes into text and back: one place for the byte-order marks and line
endings that Windows editors and shells add.

UTF-8 is the only encoding the engine writes. It reads UTF-8 with or without a byte-order mark,
and, from standard input and an export, UTF-16 with one, as Windows PowerShell 5.1 writes a
redirected file. Line endings fold to LF on every read that compares or digests text, so one
file reads the same in a checkout with `core.autocrlf` and in one without. `plain` and `quote`
escape text from a target before it is printed.

Standard library only, and no OutcomeBound import.
"""

from __future__ import annotations

import difflib
import re
import sys
from pathlib import Path

UTF8_BOM = b"\xef\xbb\xbf"
_UTF16_BOMS = (b"\xff\xfe", b"\xfe\xff")


def decode(data: bytes, *, utf16: bool = False) -> str:
    """`data` as text: a UTF-8 byte-order mark dropped, and with `utf16` a UTF-16 one read as
    UTF-16. Raises `UnicodeDecodeError` for bytes that are neither."""

    if utf16 and data.startswith(_UTF16_BOMS):
        return data.decode("utf-16")
    return data.removeprefix(UTF8_BOM).decode("utf-8")


def universal(text: str) -> str:
    """`text` with every line ending LF, as Python's text mode reads a file."""

    return text.replace("\r\n", "\n").replace("\r", "\n")


def read_text(path: Path | str, *, utf16: bool = False) -> str:
    """The file's text as `Path.read_text(encoding="utf-8")` gives it, and with the byte-order
    mark accepted. Raises `OSError` and `UnicodeDecodeError` as that does."""

    return universal(decode(Path(path).read_bytes(), utf16=utf16))


def stdin_text() -> str:
    """Standard input read as bytes and decoded here, not by the console's code page."""

    return decode(sys.stdin.buffer.read(), utf16=True)


def fold(data: bytes) -> bytes:
    """`data` with CRLF as LF: the form a text artifact is compared and digested in."""

    return data.replace(b"\r\n", b"\n")


def uses_crlf(data: bytes) -> bool:
    """Whether most of the file's line endings are CRLF."""

    return data.count(b"\r\n") * 2 > data.count(b"\n")


def with_style(data: bytes, like: bytes | None) -> bytes:
    """LF-form `data` written in the line ending the file `like` uses; LF where it is new."""

    return data.replace(b"\n", b"\r\n") if like is not None and uses_crlf(like) else data


_RAW_LINE = re.compile(r"[^\r\n]*(?:\r\n|\r|\n)|[^\r\n]+")


def splice(before: bytes, text: str) -> bytes:
    """The bytes of the file `before` once its text is `text`.

    A line the change left alone keeps its bytes, whatever its ending; a line it wrote is in the
    ending most of the file's lines use, LF where the file is new or empty. The byte-order mark
    is not part of the result. Raises `UnicodeDecodeError` where `before` is not UTF-8."""

    raw = _RAW_LINE.findall(decode(before))
    new = _lines(text)
    ending = "\r\n" if uses_crlf(before) else "\n"
    out: list[str] = []
    for tag, a1, a2, b1, b2 in difflib.SequenceMatcher(
        None, [universal(line) for line in raw], new, autojunk=False
    ).get_opcodes():
        if tag == "equal":
            pieces = raw[a1:a2]
        else:
            pieces = [line[:-1] + ending if line.endswith("\n") else line for line in new[b1:b2]]
        for piece in pieces:
            # A kept lone CR before an LF piece would read as one CRLF and lose a line.
            if piece.startswith("\n") and out and out[-1].endswith("\r"):
                piece = "\r" + piece
            out.append(piece)
    return "".join(out).encode("utf-8")


def plain(text: str) -> str:
    """Text with every character outside printable ASCII escaped, so nothing hides or steers
    the terminal it is printed to."""

    return "".join(
        c if " " <= c <= "~" else (f"\\u{ord(c):04x}" if ord(c) <= 0xFFFF else f"\\U{ord(c):08x}")
        for c in text
    )


def quote(text: str, limit: int = 160) -> str:
    """Quoted text, escaped as `plain` escapes it and cut at `limit` characters."""

    shown = plain(text.strip())
    if len(shown) > limit:
        shown = shown[: limit - 3] + "..."
    return f'"{shown}"'


def _lines(text: str) -> list[str]:
    """`text` split after each LF, the last piece without one where the text has none."""

    return re.findall(r"[^\n]*\n|[^\n]+", text)
