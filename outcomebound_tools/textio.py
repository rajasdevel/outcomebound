"""How the engine turns bytes into text and back: one place for the byte-order marks and line
endings that Windows editors and shells add.

UTF-8 is the only encoding the engine writes. It reads UTF-8 with or without a byte-order mark,
and, from standard input and an export, UTF-16 with one, as Windows PowerShell 5.1 writes a
redirected file. Line endings fold to LF on every read that compares or digests text, so one
file reads the same in a checkout with `core.autocrlf` and in one without.

Standard library only, and no OutcomeBound import.
"""

from __future__ import annotations

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
