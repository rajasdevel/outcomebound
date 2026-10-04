"""OutcomeBound identity helpers: managed-block sentinels and the state directory.

Ambiguous structure — duplicate, interleaved, or mismatched managed blocks —
fails closed instead of guessing which copy is authoritative.
"""

import re
from dataclasses import dataclass

CURRENT_NAME = "outcomebound"
CURRENT_STATE_DIR = ".outcomebound"

SENTINEL_BEGIN = re.compile(
    r"<!--\s*(?P<brand>outcomebound):begin "
    r"id=(?P<id>[a-z0-9-]+) "
    r"(?:hash=(?P<hash>[0-9a-f]+) )?v=(?P<v>[0-9.]+)\s*-->"
)
SENTINEL_END = re.compile(
    r"<!--\s*(?P<brand>outcomebound):end "
    r"id=(?P<id>[a-z0-9-]+)\s*-->"
)
# Anything shaped like a sentinel. Whatever this matches must also match the
# grammar above, or the document carries corruption rather than a block: a
# candidate the strict readers cannot see would otherwise be skipped in
# silence, which is exactly how a half-written block survives a presence check.
#
# A candidate ends at the first `-->` on its line, or at the end of that line
# when none arrives. Requiring `-->` would be the same silence in the opposite
# direction: a sentinel truncated mid-line would match NOTHING, the reader would
# answer "no blocks here" — indistinguishable from a clean host — and every
# writer that appends on absence would append a second block beside the corrupt one.
SENTINEL_CANDIDATE = re.compile(r"<!--\s*outcomebound:(?:begin|end)\b[^\n]*?(?:-->|(?=\n)|\Z)")
# CommonMark fenced code, narrowed to what the block grammar needs: an opener is at most three
# spaces of indent then three or more backticks or tildes, and only a run of the
# same character at least as long closes it.
FENCE_OPEN = re.compile(r"[ ]{0,3}(?P<marker>`{3,}|~{3,})")
FENCE_CLOSE = re.compile(r"[ ]{0,3}(?P<marker>`{3,}|~{3,})[ \t]*\Z")


class IdentityError(ValueError):
    """An identity input is missing or malformed."""


class IdentityConflict(IdentityError):
    """Two identity inputs disagree or coexist ambiguously."""


@dataclass(frozen=True)
class ManagedBlock:
    brand: str
    block_id: str
    content_hash: str | None
    version: str
    body: str
    begin_offset: int = -1
    end_offset: int = -1

    @property
    def id(self) -> str:
        """The contract's spelling of ``block_id``; one object, two names."""

        return self.block_id

    @property
    def hash(self) -> str | None:
        """The contract's spelling of ``content_hash``."""

        return self.content_hash


def pointer_block_id(path: str) -> str:
    """Return the artifact id of the bounded pointer block hosted at ``path``.

    One grammar serves the writer and every reader: a host path becomes a
    sentinel-legal slug, and a path that cannot produce one is an error rather
    than a silently different id.
    """

    if not isinstance(path, str) or not path:
        raise IdentityError(f"cannot derive bounded pointer id from {path!r}")
    slug = re.sub(r"[^a-z0-9]+", "-", path.lower()).strip("-")
    if not slug:
        raise IdentityError(f"cannot derive bounded pointer id from {path!r}")
    return f"managed-block:pointer-{slug}"


def _scan_fences(text: str) -> tuple[list[tuple[int, int]], bool]:
    """Return fenced ranges (fences included) and whether one is still open.

    One scanner answers both questions, so "what is fenced?" and "is a fence
    unclosed?" can never disagree about where a fence starts. An unclosed fence
    runs to the end of the document, so a truncated example cannot leak its
    sentinels back into the readable region -- and the caller that cares gets
    told, instead of inferring it from a span that happens to end at EOF.
    """

    spans: list[tuple[int, int]] = []
    marker: str | None = None
    start = 0
    position = 0
    for line in text.splitlines(keepends=True):
        content = line.rstrip("\n").rstrip("\r")
        if marker is None:
            opener = FENCE_OPEN.match(content)
            if opener:
                marker = opener.group("marker")
                start = position
        else:
            closer = FENCE_CLOSE.match(content)
            if (
                closer
                and closer.group("marker")[0] == marker[0]
                and len(closer.group("marker")) >= len(marker)
            ):
                spans.append((start, position + len(line)))
                marker = None
        position += len(line)
    if marker is not None:
        spans.append((start, len(text)))
    return spans, marker is not None


def _fenced_spans(text: str) -> list[tuple[int, int]]:
    """The character ranges covered by fenced code, fences included."""

    return _scan_fences(text)[0]


def fence_free_lines(text: str) -> list[str]:
    """The lines of ``text`` that are not inside a fenced code block.

    The public form of the reader's own fence scan, for callers that ask "is
    this line active?" rather than "which blocks are installed?" — the pointer
    observer's directive test, above all. One grammar serves both, so a
    directive the reader considers swallowed by an unclosed fence is never
    reported as live routing. Fence lines themselves are not content and are
    never yielded.
    """

    spans = _fenced_spans(text)
    lines = []
    position = 0
    for line in text.split("\n"):
        if not any(start <= position < stop for start, stop in spans):
            lines.append(line)
        position += len(line) + 1
    return lines


def has_unclosed_fence(text: str) -> bool:
    """Whether ``text`` ends inside an unclosed fenced code block.

    A reader can only answer "no managed block here" for the region an unclosed
    fence swallows, which is the whole rest of the document. That answer is
    indistinguishable from genuine absence, so a writer that appends on absence
    needs to ask this question separately before it treats "none found" as
    "none installed". It is the SAME fence grammar the reader uses -- one
    scanner, so a writer can never refuse over a fence the reader did not see,
    or append past one it did.
    """

    return _scan_fences(text)[1]


def find_managed_blocks(text: str) -> list["ManagedBlock"]:
    """Return every managed block in ``text``, in host order.

    This is the one authority for the question every writer asks before it
    touches a host file: which managed blocks are installed here? A document
    that merely quotes a sentinel inside fenced code answers "none", so
    documentation cannot block adoption; an empty or blockless document also
    answers "none", because absence is a legitimate answer and only corruption
    is an error. Malformed, nested, unmatched, and duplicate unfenced structure
    raises ``IdentityError`` instead of being skipped, so a half-written block
    can never pass as an absent one. Offsets bound the whole sentinel structure
    — ``text[block.begin_offset:block.end_offset]`` is the block including both
    sentinels — and a block's body is the text between its sentinels with its
    leading and trailing newlines trimmed.
    """

    spans = _fenced_spans(text)

    def fenced(position: int) -> bool:
        return any(start <= position < stop for start, stop in spans)

    strict: dict[int, tuple[str, re.Match]] = {}
    for match in SENTINEL_BEGIN.finditer(text):
        strict[match.start()] = ("begin", match)
    for match in SENTINEL_END.finditer(text):
        strict[match.start()] = ("end", match)
    for candidate in SENTINEL_CANDIDATE.finditer(text):
        if fenced(candidate.start()):
            continue
        exact = strict.get(candidate.start())
        if exact is None or exact[1].end() != candidate.end():
            raise IdentityError(f"malformed managed block sentinel: {candidate.group(0)!r}")

    blocks: list[ManagedBlock] = []
    seen: set[str] = set()
    opened: re.Match | None = None
    for position in sorted(strict):
        if fenced(position):
            continue
        kind, match = strict[position]
        if kind == "begin":
            if opened is not None:
                raise IdentityConflict(
                    f"interleaved managed blocks: {opened.group('id')} and {match.group('id')}"
                )
            opened = match
            continue
        if opened is None:
            raise IdentityError(f"unmatched managed block end sentinel: {match.group('id')}")
        if opened.group("id") != match.group("id"):
            raise IdentityConflict(
                f"managed block id mismatch: {opened.group('id')} != {match.group('id')}"
            )
        block_id = match.group("id")
        if block_id in seen:
            raise IdentityConflict(f"duplicate managed block id: {block_id}")
        seen.add(block_id)
        blocks.append(
            ManagedBlock(
                brand=opened.group("brand"),
                block_id=block_id,
                content_hash=opened.group("hash"),
                version=opened.group("v"),
                body=text[opened.end() : match.start()].strip("\n"),
                begin_offset=opened.start(),
                end_offset=match.end(),
            )
        )
        opened = None
    if opened is not None:
        raise IdentityError(f"unmatched managed block begin sentinel: {opened.group('id')}")
    return blocks


def parse_managed_blocks(text: str) -> dict[str, "ManagedBlock"]:
    """Parse every managed block in a document, keyed by id, in document order.

    A document may carry more than one OutcomeBound block — the operating
    contract and the composed project guidance. Ids are the key, so a caller
    never has to depend on position, and a duplicate id is a conflict rather
    than a silent last-one-wins.

    The blocks are ``find_managed_blocks``'s, so both readers of one text agree:
    a sentinel quoted inside fenced code is documentation here too, and
    malformed, interleaved or unmatched structure fails closed with that
    reader's message. What this reader adds is that a document with no block
    at all is an error, because every caller of it expects a block.
    """

    found = find_managed_blocks(text)
    if not found:
        raise IdentityError(
            "managed block requires exactly one well-formed begin and end sentinel per id"
        )
    blocks: dict[str, ManagedBlock] = {}
    for block in found:
        # Defensive: `find_managed_blocks` raises this same conflict first.
        if block.block_id in blocks:
            raise IdentityConflict(f"duplicate managed block id: {block.block_id}")
        blocks[block.block_id] = block
    return blocks


def parse_managed_block(text: str, block_id: str | None = None) -> ManagedBlock:
    """Parse one managed block.

    With ``block_id``, select that block and ignore any others. Without it the
    input must carry exactly one block, or it is an error. Both forms share one
    parser, so duplicate markers, mismatched ids, reversed markers, and
    overlapping blocks stay conflicts in either mode.
    """

    if block_id is None:
        begins = list(SENTINEL_BEGIN.finditer(text))
        ends = list(SENTINEL_END.finditer(text))
        if len(begins) != 1 or len(ends) != 1:
            raise IdentityError(
                "managed block requires exactly one well-formed begin and end sentinel"
            )
        (only,) = parse_managed_blocks(text).values()
        return only

    blocks = parse_managed_blocks(text)
    if block_id not in blocks:
        raise IdentityError(f"no managed block with id {block_id!r}")
    return blocks[block_id]


def format_managed_block(
    block_id: str, version: str, body: str, content_hash: str | None = None
) -> str:
    """Render a managed block using only meaningful OutcomeBound metadata.

    ``content_hash`` is emitted before ``v=`` because that is the order the
    sentinel pattern accepts. The operating contract carries no hash: its
    integrity is the template it is pinned to. Composed guidance carries one so
    a reader can tell an edited block from a regenerated one.
    """

    if not re.fullmatch(r"[a-z0-9-]+", block_id):
        raise IdentityError(f"invalid managed block id: {block_id!r}")
    if not re.fullmatch(r"[0-9.]+", version):
        raise IdentityError(f"invalid managed block version: {version!r}")
    marker = ""
    if content_hash is not None:
        if not re.fullmatch(r"[0-9a-f]+", content_hash):
            raise IdentityError(f"invalid managed block hash: {content_hash!r}")
        marker = f"hash={content_hash} "
    return (
        f"<!-- {CURRENT_NAME}:begin id={block_id} {marker}v={version} -->\n"
        f"{body.strip(chr(10))}\n"
        f"<!-- {CURRENT_NAME}:end id={block_id} -->"
    )
