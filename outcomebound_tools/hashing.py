"""The canonical text digest: a fragment's `sha256` and the ticket layer's comparisons."""

import hashlib


def normalize(text: str) -> str:
    """Canonical text form: CRLF->LF, trailing whitespace stripped per line."""
    return "\n".join(line.rstrip() for line in text.replace("\r\n", "\n").split("\n"))


def sha256_text(text: str) -> str:
    """Canonical hash: normalize CRLF→LF, strip trailing whitespace per line."""
    return hashlib.sha256(normalize(text).encode("utf-8")).hexdigest()
