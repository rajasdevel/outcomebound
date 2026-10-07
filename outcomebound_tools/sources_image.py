"""What `outcomebound sources import` records about an image file: its format and its pixel
size, read from the file's header (`docs/specs/sources/design.md`).

What this module decides: which format a file is (from its first bytes, or, for SVG, from its
root element), and the width and height its header states. A size the header does not state, or
that the bytes are too short to hold, is None, which the manifest records as unverified.

What it does not decide: anything about what the picture shows. The pixels are never decoded, so
no text, layout or meaning is read. Standard library only.
"""

from __future__ import annotations

import re
import string
import struct
from typing import NamedTuple


class Info(NamedTuple):
    media_type: str
    width: int | None
    height: int | None
    note: str = ""  # where the size came from, when it is not the plain width and height


_PNG = b"\x89PNG\r\n\x1a\n"
_JPEG_NO_SIZE = {0xC4, 0xC8, 0xCC}
_JPEG_STANDALONE = {0x01, *range(0xD0, 0xDA)}
_WHITESPACE = b" \t\r\n\f"
_NAME = frozenset((string.ascii_letters + ":-").encode())
_NUMBER = re.compile(r"\d+(?:\.\d+)?(?:px)?")


def sniff(data: bytes) -> Info | None:
    """The image `data` is, or None where it is none of PNG, JPEG, GIF, WebP and SVG."""

    if data.startswith(_PNG):
        return Info("image/png", *_png(data))
    if data.startswith(b"\xff\xd8"):
        return Info("image/jpeg", *_jpeg(data))
    if data[:6] in (b"GIF87a", b"GIF89a"):
        width, height = struct.unpack("<HH", data[6:10]) if len(data) >= 10 else (None, None)
        return Info("image/gif", width, height)
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return Info("image/webp", *_webp(data))
    return _svg(data)


def _png(data: bytes) -> tuple[int | None, int | None]:
    if len(data) >= 24 and data[12:16] == b"IHDR":
        width, height = struct.unpack(">II", data[16:24])
        return width, height
    return None, None


def _jpeg(data: bytes) -> tuple[int | None, int | None]:
    """The size in the first start-of-frame segment."""

    position = 2
    while position + 4 <= len(data):
        if data[position] != 0xFF:
            return None, None
        marker = data[position + 1]
        if marker == 0xFF:  # fill byte
            position += 1
            continue
        if marker in _JPEG_STANDALONE:
            position += 2
            continue
        length = struct.unpack(">H", data[position + 2 : position + 4])[0]
        if 0xC0 <= marker <= 0xCF and marker not in _JPEG_NO_SIZE:
            if position + 9 > len(data):
                return None, None
            height, width = struct.unpack(">HH", data[position + 5 : position + 9])
            return width, height
        position += 2 + length
    return None, None


def _webp(data: bytes) -> tuple[int | None, int | None]:
    kind = data[12:16]
    if kind == b"VP8 " and len(data) >= 30 and data[23:26] == b"\x9d\x01\x2a":
        width, height = struct.unpack("<HH", data[26:30])
        return width & 0x3FFF, height & 0x3FFF
    if kind == b"VP8L" and len(data) >= 25 and data[20] == 0x2F:
        bits = struct.unpack("<I", data[21:25])[0]
        return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    if kind == b"VP8X" and len(data) >= 30:
        width = int.from_bytes(data[24:27], "little") + 1
        height = int.from_bytes(data[27:30], "little") + 1
        return width, height
    return None, None


def _root_tag(data: bytes) -> bytes | None:
    """The opening tag of the root element, if it is `<svg`: the first element after comments,
    processing instructions and a DOCTYPE (its quotes and bracketed subset skipped), found by one
    forward scan, so no input makes it backtrack. An `<svg` inside an `<html>` wrapper or a
    DOCTYPE subset is not the root, and the file has no size."""

    position = 0
    while True:
        start = data.find(b"<", position)
        if start < 0:
            return None
        if data.startswith(b"<!--", start):
            end = data.find(b"-->", start + 4)
            position = len(data) if end < 0 else end + 3
        elif data.startswith(b"<?", start):
            end = data.find(b"?>", start + 2)
            position = len(data) if end < 0 else end + 2
        elif data.startswith(b"<!", start):
            after = _declaration_end(data, start + 2)
            position = len(data) if after is None else after
        elif data.startswith(b"<svg", start) and data[start + 4 : start + 5] in _SVG_NEXT:
            return _tag_body(data, start + 4)
        else:
            return None


def _declaration_end(data: bytes, position: int) -> int | None:
    """The position after the `>` that ends a `<!` declaration, quotes and one level of `[...]`
    skipped; None where it never ends."""

    depth = 0
    while position < len(data):
        char = data[position : position + 1]
        if char in (b'"', b"'"):
            close = data.find(char, position + 1)
            if close < 0:
                return None
            position = close
        elif char == b"[":
            depth += 1
        elif char == b"]":
            depth = max(depth - 1, 0)
        elif char == b">" and depth == 0:
            return position + 1
        position += 1
    return None


_SVG_NEXT = {b">", b"/", *(bytes([c]) for c in _WHITESPACE)}


def _tag_body(data: bytes, position: int) -> bytes | None:
    """The bytes from `position` to the `>` that ends the tag, quoted values skipped; None where
    the tag never ends."""

    begin = position
    while position < len(data):
        char = data[position : position + 1]
        if char == b">":
            return data[begin:position]
        if char in (b'"', b"'"):
            close = data.find(char, position + 1)
            if close < 0:
                return None
            position = close
        position += 1
    return None


def _attributes(body: bytes) -> dict[str, str]:
    """`name="value"` pairs of a tag body, read left to right once."""

    found: dict[str, str] = {}
    position, size = 0, len(body)
    while position < size:
        if body[position] not in _NAME:
            position += 1
            continue
        start = position
        while position < size and body[position] in _NAME:
            position += 1
        name = body[start:position].decode("ascii").lower()
        while position < size and body[position] in _WHITESPACE:
            position += 1
        if position >= size or body[position : position + 1] != b"=":
            continue
        position += 1
        while position < size and body[position] in _WHITESPACE:
            position += 1
        quote = body[position : position + 1]
        if quote not in (b'"', b"'"):
            continue
        close = body.find(quote, position + 1)
        if close < 0:
            break
        found.setdefault(name, body[position + 1 : close].decode("utf-8", "replace"))
        position = close + 1
    return found


def _svg(data: bytes) -> Info | None:
    body = _root_tag(data)
    if body is None:
        return None
    attributes = _attributes(body)
    width, height = _number(attributes.get("width")), _number(attributes.get("height"))
    if width is not None and height is not None:
        return Info("image/svg+xml", width, height)
    box = re.split(r"[\s,]+", attributes.get("viewbox", "").strip())
    if len(box) == 4:
        wide, high = _number(box[2]), _number(box[3])
        if wide is not None and high is not None:
            return Info("image/svg+xml", wide, high, "from viewBox")
    return Info("image/svg+xml", None, None)


def _number(text: str | None) -> int | None:
    """A whole pixel count from `12`, `12.5` or `12px`; None for a percentage, another unit or
    nothing."""

    if text is None:
        return None
    stripped = text.strip()
    if not _NUMBER.fullmatch(stripped):
        return None
    return round(float(stripped.removesuffix("px")))
