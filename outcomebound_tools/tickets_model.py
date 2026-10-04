"""The ticket block, decision content, the hold and the normalised ticket.

What this module decides: what one `id=ticket` block says, what
a ticket's decision content is and how its identity is computed, which
hold is in force, and the typed values the store reader hands
to every verb. It is the one place a block key is spelled and the one place a
ticket's content is hashed. The fence grammar a `reads` section is found by is
`fenced_spans`. Whether a `bounds` entry grants the whole repository is
`tickets_bounds`'.

What it does not decide: where a ticket comes from, whether the declared store
forbids a key the block carries, whether a claim is defined, whether a `reads`
section exists, or what a message does to a verdict. It opens
no file — `tickets_declaration` is the part of the model that does — reads no
tracker, no network and no credential, runs no subprocess, and writes nothing.

Everything a document can get wrong becomes a `Message`, because one unreadable
ticket is a finding about that ticket and never the end of a run. Structure is
read with `identity.find_managed_blocks`, the one fence-aware block reader in
the engine, so a block quoted inside a code fence is documentation here exactly
as it is everywhere else.

The parsed keys and the text they were written as are kept apart on purpose:
the identity hashes the list keys as written, refused entries included, so what the
identity reads is `written` and never a value this module re-rendered.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from outcomebound_tools import identity, paths
from outcomebound_tools.tickets_bounds import folder, whole_repository
from outcomebound_tools.tickets_declaration import Declaration
from outcomebound_tools.tickets_report import Message, message

__all__ = [
    "BLOCK_ID",
    "BLOCK_VERSIONS",
    "DECISION_KEYS",
    "HOLDS",
    "LIFECYCLE_KEYS",
    "LIST_KEYS",
    "STATES",
    "WAIT_KEYS",
    "BlockFields",
    "DoneWhen",
    "InputInfo",
    "ModelError",
    "ReadResult",
    "Reads",
    "Ticket",
    "content_identity",
    "effective_hold",
    "fenced_spans",
    "parse_block",
]

# --- the closed sets ---------------------------------------------------------------

STATES: tuple[str, ...] = ("open", "closed", "dropped")
# Strongest first, so the effective hold is the first row that holds.
HOLDS: tuple[str, ...] = ("yes", "requested", "no")

BLOCK_ID = "ticket"
# The block versions this engine ships. An engine that later reads v2 extends
# this tuple; nothing branches on a version, and no shipped version is ever
# dropped, because tickets outlive engines.
BLOCK_VERSIONS: tuple[str, ...] = ("1",)

# A marker a `done-when` item may carry after its claim: accepted, and read as nothing,
# so the item is its claim alone.
_RED_FIRST = "red-first"
# A person's check, `<name>: human: <observation>`: read on a ticket a person does
# (`human-only: yes`), and named where it stands on any other.
_HUMAN = "human:"
_HUMAN_ONLY = "yes"
_HUMAN_RETIRED = (
    "make it a command claim where a command can read the fact, or drop it: the one "
    "human judgment on an agent's ticket is a person's go on the plan; a ticket a person "
    "does, `human-only: yes`, may name a person's check this way"
)


class ModelError(ValueError):
    """A value this module will not read.

    `parse_block` turns the ones a document can cause into `VALUE_INVALID` and
    `BLOCK_MALFORMED` messages naming the key and the remedy; the rest — a
    closed set broken by a hand-built value — reach the caller as the
    programming errors they are.
    """


# --- what one block says -----------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Reads:
    """One `reads` entry, split as `<path>#<anchor>`; `anchor` is empty where the
    entry is a path alone, which names the whole file."""

    path: str
    anchor: str

    def cited(self) -> str:
        """The entry as a ticket writes it."""

        return f"{self.path}#{self.anchor}" if self.anchor else self.path


@dataclass(frozen=True, slots=True)
class DoneWhen:
    """One `done-when` item: a claim the plan defines, or, on a ticket a person does,
    a person's check. No text here is ever executed.

    `human` is the observation a person's check names, `<claim>: human: <observation>`,
    and empty for a claim of the plan. `claim` is then only the check's name, which
    the plan need not define.
    """

    claim: str
    human: str = ""


def _message(code: str, text: str, next: str = "") -> Message:
    """A message about a document: the ticket id is the reader's to stamp on."""
    return message(code, "", text, next)


def _entries(value: str) -> tuple[str, ...]:
    """The comma-separated entries of a value, each trimmed, in written order."""
    return tuple(part.strip() for part in value.split(",") if part.strip())


def _refuse_items(items: tuple[str, ...]) -> None:
    if items:
        raise ModelError(f"takes one value on its own line, not the list item {items[0]!r}")


def _read_text(value: str, items: tuple[str, ...]) -> str:
    _refuse_items(items)
    return value.strip()


def _read_id(value: str, items: tuple[str, ...]) -> str:
    """One ticket id: `discovered-from` and `parent` name a ticket, never a list."""

    text = _read_text(value, items)
    if "," in text or any(character.isspace() for character in text):
        raise ModelError(f"is one ticket id, not {text!r}")
    return text


def _read_entries(value: str, items: tuple[str, ...]) -> tuple[str, ...]:
    """`bounds` and `blocked-by`, kept as written; which entries a report warns
    about is `_bounds_messages`."""

    _refuse_items(items)
    return _entries(value)


# A decision brief's id, as `schemas/decision-briefs.schema.json` spells it: a
# letter, then letters, digits and hyphens.
_BRIEF_ID = re.compile(r"[A-Za-z][A-Za-z0-9-]*")


def _read_brief_ids(value: str, items: tuple[str, ...]) -> tuple[str, ...]:
    """`waits-on`: the ids of the decision briefs the ticket's work waits on.

    At least one, each a brief id; the order is the order written.
    """

    entries = _read_entries(value, items)
    if not entries:
        raise ModelError("names at least one decision brief id, such as `D3`")
    for entry in entries:
        if _BRIEF_ID.fullmatch(entry) is None:
            raise ModelError(
                f"entry {entry!r} is not a decision brief id matching {_BRIEF_ID.pattern}"
            )
    return entries


def _closed_set(allowed: tuple[str, ...]) -> Callable[[str, tuple[str, ...]], str]:
    """A reader for a key whose value is a closed set: `human-only` and `status`."""

    def read(value: str, items: tuple[str, ...]) -> str:
        _refuse_items(items)
        text = value.strip()
        if text not in allowed:
            raise ModelError(f"is {text!r}; the block allows {', '.join(allowed)}")
        return text

    return read


def _reads_entry(entry: str) -> Reads:
    """`<path>#<anchor>`, or `<path>` alone for the whole file; resolving it is the
    links module's."""

    path, separator, anchor = entry.partition("#")
    if (separator and not anchor) or not paths.admits(path):
        raise ModelError(
            f"entry {entry!r} is neither `<repository-relative markdown path>#<anchor>` "
            "nor `<repository-relative path>` for the whole file"
        )
    return Reads(path, anchor)


def _read_reads(value: str, items: tuple[str, ...]) -> tuple[Reads, ...]:
    _refuse_items(items)
    return tuple(_reads_entry(entry) for entry in _entries(value))


_CLAIM_NAME = re.compile(r"[a-z][a-z0-9-]*")


def _retired(item: str) -> bool:
    """Whether a `done-when` item is the `human:` form, a person's check."""

    return item.partition(":")[2].strip().startswith(_HUMAN)


def _observation(item: str) -> str:
    """What a person's check says a person observes; empty where it says nothing."""

    return item.partition(":")[2].strip()[len(_HUMAN) :].strip()


def _done_when_item(item: str) -> DoneWhen:
    """A claim name, alone or with the `red-first` marker it is read without, or a
    person's check: the name, `human:` and the observation."""
    name, _, rest = item.partition(":")
    claim = name.strip()
    if _CLAIM_NAME.fullmatch(claim) is None:
        raise ModelError(
            f"item {item!r} does not begin with a claim name matching {_CLAIM_NAME.pattern}"
        )
    if _retired(item):
        return DoneWhen(claim, _observation(item))
    if rest.strip() not in ("", _RED_FIRST):
        raise ModelError(f"item {item!r} is neither `<claim>` nor `<claim>: {_RED_FIRST}`")
    return DoneWhen(claim)


def _read_done_when(value: str, items: tuple[str, ...]) -> tuple[DoneWhen, ...]:
    """The checks, in written order. A person's check is read here too; `parse_block`
    keeps it only on a ticket a person does and names it on any other, so the claims
    beside it are still read."""

    if value.strip():
        raise ModelError(f"is a list of `- ` items, not the value {value.strip()!r}")
    if not items:
        raise ModelError("is required to carry at least one `- ` item")
    read: list[DoneWhen] = []
    seen: set[str] = set()
    for item in items:
        if _retired(item) and not _observation(item):
            continue
        entry = _done_when_item(item)
        if entry.claim in seen:
            raise ModelError(f"names the claim {entry.claim!r} twice; a name is unique per ticket")
        seen.add(entry.claim)
        read.append(entry)
    return tuple(read)


def _written_value(value: str, items: tuple[str, ...]) -> tuple[str, ...]:
    return _entries(value)


def _written_items(value: str, items: tuple[str, ...]) -> tuple[str, ...]:
    return items


@dataclass(frozen=True, slots=True)
class _Key:
    """One row of the key table: how it is spelled, read and classified.

    `written` is how the identity reads the key's text when it is one of the list
    keys, and None for the keys that carry a single value.
    """

    name: str
    attribute: str
    kind: str
    read: Callable[[str, tuple[str, ...]], object]
    required: bool = False
    written: Callable[[str, tuple[str, ...]], tuple[str, ...]] | None = None


# The key table, row for row and in its order. `required` is what every store
# requires; which keys the declared store additionally requires or forbids is
# that store's reader's, so this parser accepts them all.
_KEYS: tuple[_Key, ...] = (
    _Key("reads", "reads", "decision", _read_reads, written=_written_value),
    _Key("bounds", "bounds", "decision", _read_entries, True, _written_value),
    _Key("human-only", "human_only", "decision", _closed_set(HOLDS), True),
    _Key("done-when", "done_when", "decision", _read_done_when, True, _written_items),
    _Key("discovered-from", "discovered_from", "decision", _read_id),
    _Key("waits-on", "waits_on", "wait", _read_brief_ids),
    _Key("status", "status", "lifecycle", _closed_set(STATES)),
    _Key("assignee", "assignee", "lifecycle", _read_text),
    _Key("blocked-by", "blocked_by", "lifecycle", _read_entries),
    _Key("parent", "parent", "lifecycle", _read_id),
)
_BY_NAME: Mapping[str, _Key] = MappingProxyType({key.name: key for key in _KEYS})
# A key the block does not read, and what to write instead.
_RETIRED: Mapping[str, str] = MappingProxyType(
    {"covers": "remove it: cite the design section under `reads` instead"}
)
DECISION_KEYS: tuple[str, ...] = tuple(key.name for key in _KEYS if key.kind == "decision")
LIFECYCLE_KEYS: tuple[str, ...] = tuple(key.name for key in _KEYS if key.kind == "lifecycle")
# The keys that say what a ticket's work waits on outside the tracker: carried in the
# block in every store, because no tracker relation holds them, and no part of the
# decision content, so answering a brief and dropping its id moves no identity.
WAIT_KEYS: tuple[str, ...] = tuple(key.name for key in _KEYS if key.kind == "wait")
# The keys the identity hashes as a list of entries, in the table's order.
LIST_KEYS: tuple[str, ...] = tuple(key.name for key in _KEYS if key.written is not None)
_NO_ENTRIES: Mapping[str, tuple[str, ...]] = MappingProxyType(dict.fromkeys(LIST_KEYS, ()))


def _no_entries() -> Mapping[str, tuple[str, ...]]:
    return _NO_ENTRIES


@dataclass(frozen=True, slots=True)
class BlockFields:
    """One ticket block's keys, whatever store it came from.

    `present` holds the key names the block carried, spelled as the table spells
    them: it is what lets the `github` reader refuse a lifecycle key its tracker
    holds natively. A key whose value was refused is present and keeps its empty
    default.

    `written` holds each list key's entries as written and trimmed,
    including entries the grammar refused, which is what the identity hashes: an entry
    this engine cannot read is still what the ticket says. `begin` and `end` are
    the block's offsets in the text given, `-1` where no block was read, so a
    reader cuts the brief without scanning for a sentinel a second time.
    """

    version: str = ""
    reads: tuple[Reads, ...] = ()
    bounds: tuple[str, ...] = ()
    human_only: str = ""
    done_when: tuple[DoneWhen, ...] = ()
    discovered_from: str = ""
    waits_on: tuple[str, ...] = ()
    status: str = ""
    assignee: str = ""
    blocked_by: tuple[str, ...] = ()
    parent: str = ""
    present: frozenset[str] = frozenset()
    written: Mapping[str, tuple[str, ...]] = field(default_factory=_no_entries)
    begin: int = -1
    end: int = -1


_KEY_LINE = re.compile(r"(?P<key>[A-Za-z][A-Za-z0-9_-]*):(?P<value>.*)$")
_ITEM_LINE = re.compile(r"\s*-(?:\s+(?P<item>.*))?$")


def _is_duplicate(text: str) -> bool:
    """Whether a refused document carries more than one complete ticket block.

    Read with the engine's own sentinel patterns over the engine's own
    fence-free lines, so this can never disagree with `find_managed_blocks`
    about what is inside a fence. Matched pairs are blocks: a document whose
    prose names a begin sentinel and an end sentinel in inline code reads as
    carrying a second block, and a nested pair reads the same way, while any
    unbalanced count is a broken sentinel and reads `BLOCK_MALFORMED`. Both
    answers say the same thing to a writer — show a sentinel inside a fence —
    and neither is ever reached unless the block reader has already refused.
    """

    unfenced = "\n".join(identity.fence_free_lines(text))
    counted = [
        sum(1 for found in pattern.finditer(unfenced) if found.group("id") == BLOCK_ID)
        for pattern in (identity.SENTINEL_BEGIN, identity.SENTINEL_END)
    ]
    return counted[0] > 1 and counted[0] == counted[1]


def _one_block(text: str) -> identity.ManagedBlock | Message:
    """The document's one ticket block, or the message saying why there is none."""
    try:
        blocks = identity.find_managed_blocks(text)
    except identity.IdentityError as refused:
        if _is_duplicate(text):
            return _message(
                "BLOCK_DUPLICATE",
                f"the document carries more than one `id={BLOCK_ID}` block outside a code fence",
                next="keep one block, and show any example of one inside a code fence",
            )
        return _message(
            "BLOCK_MALFORMED",
            f"the ticket block could not be read: {refused}",
            next="a brief that shows a block sentinel shows it inside a code fence",
        )
    foreign = tuple(sorted({block.id for block in blocks if block.id != BLOCK_ID}))
    if foreign:
        return _message(
            "BLOCK_MALFORMED",
            f"the document carries the managed block(s) {', '.join(foreign)} outside a code "
            f"fence, where only an `id={BLOCK_ID}` block belongs",
            next="show any other block inside a code fence",
        )
    for block in blocks:
        return block
    swallowed = (
        "; the document ends inside an unclosed code fence, which swallows everything after it"
        if identity.has_unclosed_fence(text)
        else ""
    )
    return _message(
        "BLOCK_MISSING",
        f"the document carries no `id={BLOCK_ID}` block outside a code fence{swallowed}",
        next="add the ticket block",
    )


def _body_entries(body: str) -> tuple[tuple[str, str, tuple[str, ...]], ...]:
    """The block's body as `(key, value, items)`, in written order.

    A line beginning `- ` is an item of the key above it, which is how
    `done-when` carries a list, and an item with nothing after the dash is an
    empty item its key refuses rather than a line this parser cannot place.
    Anything else that is neither blank nor `<key>: <value>` is a body this
    parser will not read.
    """

    read: list[tuple[str, str, list[str]]] = []
    for raw in body.split("\n"):
        line = raw.rstrip()
        if not line.strip():
            continue
        item = _ITEM_LINE.fullmatch(line)
        if item is not None and read:
            read[-1][2].append((item.group("item") or "").strip())
            continue
        named = _KEY_LINE.fullmatch(line)
        if named is None:
            raise ModelError(
                f"the line {line.strip()!r} is neither `<key>: <value>` nor a `- ` item"
            )
        read.append((named.group("key"), named.group("value"), []))
    return tuple((key, value, tuple(items)) for key, value, items in read)


def _read_keys(
    entries: tuple[tuple[str, str, tuple[str, ...]], ...],
) -> tuple[dict[str, Any], frozenset[str], dict[str, tuple[str, ...]], list[Message]]:
    """Every key the block carried, read through the one table above.

    A key's text is recorded before its value is read, so a refused entry still
    reaches `written` and so still reaches the identity.
    """

    values: dict[str, Any] = {}
    present: list[str] = []
    written: dict[str, tuple[str, ...]] = dict(_NO_ENTRIES)
    messages: list[Message] = []
    for name, value, items in entries:
        key = _BY_NAME.get(name)
        if key is None:
            messages.append(
                _message(
                    "KEY_UNKNOWN",
                    f"`{name}` is not a key of the ticket block",
                    next=_RETIRED.get(name, ""),
                )
            )
            continue
        if name in present:
            messages.append(
                _message("KEY_DUPLICATE", f"`{name}` appears more than once; the first is read")
            )
            continue
        present.append(name)
        if key.written is not None:
            written[name] = key.written(value, items)
        try:
            values[key.attribute] = key.read(value, items)
        except ModelError as refused:
            messages.append(_message("VALUE_INVALID", f"`{name}` {refused}"))
    messages.extend(
        _message("KEY_MISSING", f"`{key.name}` is required and the block does not carry it")
        for key in _KEYS
        if key.required and key.name not in present
    )
    return values, frozenset(present), written, messages


# The bounds rules over the entries as written, worst first: an entry this engine
# will not accept at all, then one whose literal prefix grants everything.
_BOUNDS_RULES: tuple[tuple[Callable[[str], bool], str, str, str], ...] = (
    (
        lambda entry: not paths.admits(folder(entry), allow_root=True),
        "BOUNDS_INVALID",
        "is not a repository-relative path or glob",
        "name paths inside the repository, without a leading `/`, a `..` or an empty "
        "segment; a folder is written `src`, `src/` or `src/**`",
    ),
    (
        whole_repository,
        "BOUNDS_WHOLE_REPOSITORY",
        "grants the whole repository",
        "name the trees this ticket's work may touch",
    ),
)


def _bounds_messages(bounds: tuple[str, ...]) -> list[Message]:
    rules = [(entry, next((r for r in _BOUNDS_RULES if r[0](entry)), None)) for entry in bounds]
    return [
        _message(rule[1], f"the bounds entry {entry!r} {rule[2]}", next=rule[3])
        for entry, rule in rules
        if rule is not None
    ]


def _retired_messages(fields: BlockFields) -> list[Message]:
    """One `VALUE_INVALID` per `human:` item, as written, on a ticket a person does not do.

    On a ticket whose block says `human-only: yes` a person's check is what done
    means, and nothing waits on a person who is not already doing the work.
    """

    human = [item for item in fields.written.get("done-when", ()) if _retired(item)]
    if fields.human_only == _HUMAN_ONLY:
        return [
            _message(
                "VALUE_INVALID",
                f"`done-when` item {item!r} is a person's check that names no observation",
                next="write what the person observes after `human:`",
            )
            for item in human
            if not _observation(item)
        ]
    return [
        _message(
            "VALUE_INVALID",
            f"`done-when` item {item!r} is a `human:` claim, which this engine reads only on "
            f"a ticket whose block says `human-only: {_HUMAN_ONLY}`",
            next=_HUMAN_RETIRED,
        )
        for item in human
    ]


def _kept_checks(fields: BlockFields) -> tuple[DoneWhen, ...]:
    """The `done-when` items this ticket keeps: a person's check only where a person
    does the ticket."""

    if fields.human_only == _HUMAN_ONLY:
        return fields.done_when
    return tuple(item for item in fields.done_when if not item.human)


def parse_block(text: str) -> tuple[BlockFields, tuple[Message, ...]]:
    """Read the one ticket block a document carries.

    `text` is the whole document that holds the block — an issue body, or a
    draft. Every key of the table is accepted: which
    of them the tracker holds natively is the reader's to say. A structural
    failure and a version this engine never shipped both return `BLOCK_MALFORMED`
    with no key read, because neither says anything about what the block meant;
    the offsets are still returned wherever a block was found at all.
    """

    block = _one_block(text)
    if isinstance(block, Message):
        return BlockFields(), (block,)
    found = BlockFields(version=block.version, begin=block.begin_offset, end=block.end_offset)
    if block.version not in BLOCK_VERSIONS:
        return found, (
            _message(
                "BLOCK_MALFORMED",
                f"the ticket block is version {block.version!r} and this engine reads "
                f"{', '.join(BLOCK_VERSIONS)}, so the ticket is judged no further",
                next="write the block at a version this engine reads",
            ),
        )
    try:
        entries = _body_entries(block.body)
    except ModelError as refused:
        return found, (
            _message("BLOCK_MALFORMED", f"the ticket block could not be read: {refused}"),
        )
    values, present, written, messages = _read_keys(entries)
    fields = dataclasses.replace(
        found, present=present, written=MappingProxyType(written), **values
    )
    retired = _retired_messages(fields)
    fields = dataclasses.replace(fields, done_when=_kept_checks(fields))
    return fields, tuple(messages + retired + _bounds_messages(fields.bounds))


# --- decision content and its identity ---------------------------------------------

# What the identity writes for a block's `human-only`: an agent's `requested` is
# read as `no` here and nowhere else, so asking for a person never moves what
# the user accepted. An absent or refused key is the same `no`.
_IDENTITY_HOLD: Mapping[str, str] = MappingProxyType(
    {"": "no", "no": "no", "requested": "no", "yes": "yes"}
)


def _normalised_brief(brief: str) -> str:
    """Line endings to line feeds, no trailing whitespace, no blank edges."""
    lines = [line.rstrip() for line in brief.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def _identity_hold(fields: BlockFields) -> str:
    hold = _IDENTITY_HOLD.get(fields.human_only)
    if hold is None:
        raise ModelError(
            f"human-only is {fields.human_only!r}; the block allows {', '.join(HOLDS)}"
        )
    return hold


def content_identity(title: str, brief: str, fields: BlockFields) -> str:
    """The decision-content identity: the one document, hashed once.

    The list keys are taken from `written`, so what is hashed is what the
    ticket says: an entry the grammar refused is two different contents for two
    different values, never an absent key, and an item is never re-rendered, so
    two spellings of one item are two contents. A list stays a list because any
    joined form collides — one item holding the separator would read as two
    items. Lifecycle facts and `waits-on` are absent from the document, which is
    why none of them moves the identity.
    """

    document: dict[str, object] = {
        "title": title.strip(),
        "brief": _normalised_brief(brief),
        "human-only": _identity_hold(fields),
        "discovered-from": fields.discovered_from,
    }
    document.update({name: list(fields.written.get(name, ())) for name in LIST_KEYS})
    payload = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# --- fences, shared with `tickets_links` -------------------------------------------


def _closes(opener: str, closer: str) -> bool:
    """A fence closes on the same character, at least as long (`identity`'s rule)."""

    return closer[0] == opener[0] and len(closer) >= len(opener)


def fenced_spans(text: str) -> list[tuple[int, int]]:
    """The character ranges fenced code covers, fences included.

    `identity.fence_free_lines` answers "is this line active?" but not "which
    line was it", and a heading needs the position. The grammar is
    `identity.FENCE_OPEN` and `identity.FENCE_CLOSE` and nothing else, and a
    test pins the two readings against every spec in this repository. An
    unclosed fence runs to the end of the document, exactly as it does there.
    """

    spans: list[tuple[int, int]] = []
    marker: str | None = None
    start = 0
    position = 0
    for line in text.splitlines(keepends=True):
        content = line.rstrip("\n").rstrip("\r")
        if marker is None:
            opener = identity.FENCE_OPEN.match(content)
            if opener:
                marker, start = opener.group("marker"), position
        else:
            closer = identity.FENCE_CLOSE.match(content)
            if closer and _closes(marker, closer.group("marker")):
                spans.append((start, position + len(line)))
                marker = None
        position += len(line)
    if marker is not None:
        spans.append((start, len(text)))
    return spans


# --- the effective hold ------------------------------------------------------------

# Which declared label carries each hold.
_HOLD_LABELS: Mapping[str, str] = MappingProxyType(
    {"yes": "human_label", "requested": "request_label"}
)


def effective_hold(block_value: str, labels: Iterable[str], declaration: Declaration) -> str:
    """The stronger of the block's `human-only` and the declared labels.

    A hold on either surface holds. This returns the hold and nothing else:
    that the two differ is `HOLD_SURFACES_DIFFER`, the reader's to say.
    """

    applied = frozenset(labels)
    for hold in HOLDS[:-1]:
        declared = str(getattr(declaration, _HOLD_LABELS[hold], ""))
        if block_value == hold or (declared and declared in applied):
            return hold
    return HOLDS[-1]


# --- the normalised ticket and the readers' result ---------------------------------


@dataclass(frozen=True, slots=True)
class Ticket:
    """One ticket as every verb consumes it.

    `block_version` is the block's `v` as written, empty where none could be
    read, and `path` a draft's file. `waits_on` names the decision briefs a
    person has yet to answer before the work they decide can proceed.
    """

    id: str
    title: str
    url: str = ""
    state: str = "open"
    block_version: str = ""
    path: str = ""
    brief: str = ""
    reads: tuple[Reads, ...] = ()
    bounds: tuple[str, ...] = ()
    human_only: str = ""
    hold: str = "no"
    done_when: tuple[DoneWhen, ...] = ()
    blocked_by: tuple[str, ...] = ()
    parent: str = ""
    discovered_from: str = ""
    waits_on: tuple[str, ...] = ()
    content: str = ""


@dataclass(frozen=True, slots=True)
class InputInfo:
    """The export a verb was given, when it was written and how old it is.

    `modified` and `age_seconds` are None for input read from standard input,
    whose age a report says is unknown. It satisfies `tickets_report.InputSource`
    structurally, so that module imports nothing from this one.
    """

    path: str
    modified: str | None = None
    age_seconds: int | None = None


@dataclass(frozen=True, slots=True)
class ReadResult:
    """What a store reader hands back.

    `others` holds the id of every issue that is not a ticket, so that a
    relation to one still resolves; `ignored` is how many inputs the gate
    excluded.
    """

    tickets: tuple[Ticket, ...] = ()
    others: frozenset[str] = frozenset()
    ignored: int = 0
    messages: tuple[Message, ...] = ()
    input: InputInfo | None = None
