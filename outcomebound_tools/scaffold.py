"""`outcomebound scaffold <target> --lifecycle <preset>[+<overlay>...]`: the project files a
lifecycle needs, previewed, then written where they are absent.

What this module decides: which files a lifecycle's set holds, read from the manifest
`templates/scaffold/scaffold.json` only (`schemas/scaffold-manifest.schema.json`); how the parts of
one file join (`slots` for the local fragment, `blocks` for a Markdown document, `whole` for one
source); when a part is present, at its planned path or where a signal shows it, with names
matched casefolded; what the plan prints (each file, each platform act, the `adopt` command, and
a block for each present file the plan has parts for); that `--accept` writes only absent files,
through `fileplan`, each created exclusively; which markers `--check` counts; and the exits: 0,
1 for a refusal or a marker left, 2 for a usage error.

What it does not decide: whether a value is right, or who owns a gate. It reads the target's
files and runs Git to list them; it writes nothing but `--accept`'s absent files, records
nothing, and never edits, replaces or deletes a file (docs/specs/scaffold/design.md).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any

from outcomebound_tools import fileplan, home, identity, paths, programs, schemacheck, textio, walk
from outcomebound_tools.gitenv import GIT_READ_CONFIGURATION, git_environment

MANIFEST = "templates/scaffold/scaffold.json"
MANIFEST_SCHEMA = "schemas/scaffold-manifest.schema.json"
LOCAL = ".outcomebound/fragments/local.md"
INSTALL_MANIFEST = ".outcomebound/manifest.json"
# What an install records as its own whole files: OutcomeBound's text, copied into the target.
RECORDED_COPIES = ("skill", "fragment", "ignore")
VISIBILITIES = ("public", "private", "private-free")
HOSTS = ("github", "other")
OFFERS = ("codeowners", "pr-template")
SLOTS = ("Context", "Bounds", "Mechanisms", "Completion bar", "Distinguish")
STREAMS_ROUTE = "streams-route"
# The parts that stay a duty under a lighter route: on a move their retirement is the person's.
DUTIES = frozenset({"first-design", "security-policy", "changelog"})
STILL_HOLDS, TO_RETIRE = "what still holds", "what to retire"
# A value to fill: `<<`, the kind, `:`, one space, a label on one line, `>>`.
MARKER = re.compile(r"<<(fill|owner): ([^<>\r\n]+)>>")
_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
_CODE_SPAN = re.compile(r"(`+)(?!`)(.+?)(?<!`)\1(?!`)")
_SLOT_LINE = re.compile(r"^\*\*(?P<slot>[^*]+)\*\* —(?: (?P<text>.*))?$")
_STREAMS = re.compile(r"^[ \t]*(?:[-*][ \t]+)?\**Streams\s+—")
_NEXT_PART = re.compile(r"^(\*\*|[A-Z][A-Za-z ]*\s—\s)")
_SPAN = re.compile(r"`([^`\n]+)`")
BLOCK_FENCE = "````"


class ScaffoldError(Exception):
    """A refusal: the target is not a Git work tree, or the templates cannot be read. Exit 1."""


class UsageError(Exception):
    """A lifecycle or a fact the verb does not take. Exit 2."""


# --- The manifest ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Templates:
    """The manifest and the folder of sources it names."""

    folder: Path
    data: dict[str, Any]

    @property
    def presets(self) -> list[str]:
        return [item["id"] for item in self.data["lifecycles"] if item["kind"] == "preset"]

    @property
    def overlays(self) -> list[str]:
        return [item["id"] for item in self.data["lifecycles"] if item["kind"] == "overlay"]

    @property
    def acts(self) -> list[str]:
        return [item["id"] for item in self.data["acts"]]

    def lifecycle(self, name: str) -> dict[str, Any]:
        return next(item for item in self.data["lifecycles"] if item["id"] == name)

    def act(self, name: str) -> dict[str, Any]:
        return next(item for item in self.data["acts"] if item["id"] == name)

    def text(self, source: str) -> str:
        """A source's text, LF, with no byte-order mark."""

        try:
            return textio.universal(textio.decode((self.folder / source).read_bytes()))
        except (OSError, UnicodeDecodeError) as error:
            raise ScaffoldError(f"the templates cannot be read: {source}: {error}") from error


def load(source: Path) -> Templates:
    """The engine's manifest, validated against its schema."""

    path = Path(source) / MANIFEST
    try:
        data = json.loads(textio.read_text(path))
        schema = json.loads(textio.read_text(Path(source) / MANIFEST_SCHEMA))
    except (OSError, UnicodeDecodeError, ValueError) as error:
        raise ScaffoldError(f"the templates cannot be read: {MANIFEST}: {error}") from error
    errors = schemacheck.validate(data, schema)
    if errors:
        raise ScaffoldError(f"the templates cannot be read: {MANIFEST}: {'; '.join(errors)}")
    return Templates(path.parent, data)


# --- The selection --------------------------------------------------------------------------


@dataclass(frozen=True)
class Selection:
    """One lifecycle with its facts: a preset, its overlays and acts in canonical order."""

    preset: str
    overlays: tuple[str, ...]
    acts: tuple[str, ...] = ()
    visibility: str | None = None
    host: str = "github"
    offers: tuple[str, ...] = ()

    @property
    def ids(self) -> frozenset[str]:
        return frozenset((self.preset, *self.overlays, *self.acts))

    @property
    def lifecycle(self) -> str:
        return "+".join((self.preset, *self.overlays))


def parse_lifecycle(value: str, templates: Templates) -> tuple[str, tuple[str, ...]]:
    """The preset and the overlays `--lifecycle` names, the overlays in canonical order."""

    names = value.split("+")
    known = [*templates.presets, *templates.overlays]
    unknown = [name for name in names if name not in known]
    if unknown:
        raise UsageError(f"unknown lifecycle {', '.join(unknown)}; the ids are {', '.join(known)}")
    twice = sorted({name for name in names if names.count(name) > 1})
    if twice:
        raise UsageError(f"{', '.join(twice)} named twice in {value}")
    presets = [name for name in names if name in templates.presets]
    if len(presets) != 1:
        raise UsageError(
            f"{value} names {len(presets)} presets; name one of {', '.join(templates.presets)}"
        )
    preset = presets[0]
    overlays = tuple(name for name in templates.overlays if name in names)
    for overlay in overlays:
        if preset in templates.lifecycle(overlay).get("refused_on", []):
            reason = templates.lifecycle(overlay).get("refusal", "")
            raise UsageError(f"{overlay} is refused on {preset}: {reason}")
    return preset, overlays


def _words(value: str | None) -> list[str]:
    return [word.strip() for word in (value or "").split(",") if word.strip()]


def selection(
    templates: Templates, flags: argparse.Namespace, *, need_visibility: bool
) -> Selection:
    """The selection the flags name, refused as a usage error where the design refuses it."""

    visibility, host = flags.visibility, flags.host
    preset, overlays = parse_lifecycle(flags.lifecycle, templates)
    named_acts = _words(flags.acts)
    unknown = [act for act in named_acts if act not in templates.acts]
    if unknown:
        raise UsageError(
            f"unknown act {', '.join(unknown)}; the acts are {', '.join(templates.acts)}"
        )
    if named_acts and preset == "prototype":
        raise UsageError(
            "--acts is refused on prototype: a prototype holds no production credential and no "
            "real data, and its first deploy, publish or kept data ends it"
        )
    if need_visibility and visibility is None and preset != "prototype":
        raise UsageError(
            f"--visibility is required for {preset}: it decides SECURITY.md, CODEOWNERS and which "
            "platform acts are enforced"
        )
    named_offers = _words(flags.offers)
    unknown = [offer for offer in named_offers if offer not in OFFERS]
    if unknown:
        raise UsageError(f"--with takes {', '.join(OFFERS)}, not {', '.join(unknown)}")
    if named_offers and preset != "organization":
        raise UsageError("--with offers files to organization only")
    if "codeowners" in named_offers and visibility == "private-free":
        raise UsageError(
            "--with codeowners is refused on private-free: a private repository on that plan "
            "holds no code owners, so the file would bind nothing"
        )
    if named_offers and host == "other":
        raise UsageError("--with writes files under .github/, and --host other writes none there")
    return Selection(
        preset,
        overlays,
        tuple(act for act in templates.acts if act in named_acts),
        visibility,
        host,
        tuple(offer for offer in OFFERS if offer in named_offers),
    )


# --- Parts ----------------------------------------------------------------------------------


def holds(part: dict[str, Any], chosen: Selection) -> bool:
    """Whether a part (or a platform act) is for something selected, and its facts hold."""

    if not set(part["for"]) & chosen.ids:
        return False
    when = part.get("when", {})
    if "visibility" in when and chosen.visibility not in when["visibility"]:
        return False
    if "host" in when and chosen.host not in when["host"]:
        return False
    return not ("acts" in when and not set(when["acts"]) & set(chosen.acts))


def _order(templates: Templates, name: str) -> int:
    """Where an id stands in the joining order: the preset, the acts, then the overlays."""

    if name in templates.presets:
        return 0
    if name in templates.acts:
        return 1 + templates.acts.index(name)
    return 10 + templates.overlays.index(name)


def _origin(templates: Templates, parts: Iterable[dict[str, Any]], chosen: Selection) -> list[str]:
    found = {name for part in parts for name in part["for"] if name in chosen.ids}
    return sorted(found, key=lambda name: _order(templates, name))


@dataclass
class Parts:
    """The parts of one file that hold for a selection."""

    in_set: bool
    content: list[dict[str, Any]]  # joined into the file, deduplicated by source, in order
    offers: list[dict[str, Any]]  # an offer that names a command or a template
    pending: list[dict[str, Any]]  # a `--with` offer not taken


def parts_of(templates: Templates, item: dict[str, Any], chosen: Selection) -> Parts:
    holding = [part for part in item["parts"] if holds(part, chosen)]
    base = {chosen.preset, *chosen.acts}
    in_set = any(set(part["for"]) & base or part.get("brings") for part in holding)
    content, seen = [], set()
    ranked = sorted(
        holding,
        key=lambda part: min(_order(templates, n) for n in part["for"] if n in chosen.ids),
    )
    for part in ranked:
        taken = part["mode"] == "write" or part.get("offer") in chosen.offers
        if taken and part["source"] not in seen:
            seen.add(part["source"])
            content.append(part)
    offers = [part for part in holding if part["mode"] == "offer" and "offer" not in part]
    pending = [
        part
        for part in holding
        if part["mode"] == "offer" and "offer" in part and part["offer"] not in chosen.offers
    ]
    return Parts(in_set, content, offers, pending)


def _slot_lines(text: str, source: str) -> dict[str, list[str]]:
    """A part's lines by slot: each slot opens on a `**Slot** —` line of its own."""

    found: dict[str, list[str]] = {}
    slot = None
    for line in text.split("\n"):
        mark = _SLOT_LINE.match(line)
        if mark and not (mark.group("text") or "").strip():
            slot = mark.group("slot")
            if slot not in SLOTS:
                raise ScaffoldError(f"the templates cannot be read: {source}: no slot {slot!r}")
            found.setdefault(slot, [])
        elif line.strip():
            if slot is None:
                raise ScaffoldError(f"the templates cannot be read: {source}: a line before a slot")
            found[slot].append(line)
    return found


def edges(templates: Templates, chosen: Selection) -> list[str]:
    """The edges of the preset, the acts and the overlays, each once, in that order."""

    found: list[str] = []
    for item in (
        templates.lifecycle(chosen.preset),
        *(templates.act(act) for act in chosen.acts),
        *(templates.lifecycle(overlay) for overlay in chosen.overlays),
    ):
        found += [edge for edge in item["edges"] if edge not in found]
    return found


def render(
    templates: Templates, item: dict[str, Any], parts: Sequence[dict[str, Any]], chosen: Selection
) -> str:
    """The file's text: its head and its parts joined as its `join` says."""

    texts = [templates.text(part["source"]) for part in parts]
    if item["join"] == "whole":
        return texts[0]
    head = templates.text(item["head"])
    if item["join"] == "blocks":
        return "\n\n".join([head.rstrip("\n"), *(text.strip("\n") for text in texts)]) + "\n"
    end = head.index("\n---\n", 3) + len("\n---\n")
    front = re.sub(
        r"^edges:.*$",
        lambda _: "edges: " + json.dumps(edges(templates, chosen), ensure_ascii=False),
        head[:end],
        count=1,
        flags=re.MULTILINE,
    )
    added: dict[str, list[str]] = {slot: [] for slot in SLOTS}
    for part, text in zip(parts, texts, strict=True):
        for slot, lines in _slot_lines(text, part["source"]).items():
            added[slot] += lines
    body: list[str] = []
    for line in head[end:].rstrip("\n").split("\n"):
        mark = _SLOT_LINE.match(line)
        if mark and body and body[-1] != "" and _current(body) in added:
            body += added.pop(_current(body))
        body.append(line)
    if body and _current(body) in added:
        body += added.pop(_current(body))
    return front + "\n".join(body) + "\n"


def _current(body: list[str]) -> str:
    """The slot the last slot line of `body` opened."""

    for line in reversed(body):
        mark = _SLOT_LINE.match(line)
        if mark:
            return mark.group("slot")
    return ""


def block(
    templates: Templates,
    item: dict[str, Any],
    parts: Sequence[dict[str, Any]],
    chosen: Selection,
    replaced: Sequence[dict[str, Any]] = (),
    before: Selection | None = None,
) -> str | None:
    """What a present file gets from these parts, for the agent to add on the person's yes: the
    lines by slot for the local fragment, with the lines a move replaces and its edges; the parts'
    text for a Markdown document. None where there is nothing to add."""

    if item["join"] == "whole":
        return None
    if item["join"] == "blocks":
        texts = [templates.text(part["source"]).strip("\n") for part in parts]
        # A file with no head is a table that gets rows; a document gets sections.
        return ("\n" if "head" not in item else "\n\n").join(texts) or None
    lines: list[str] = []
    for part in replaced:
        for slot, found in _slot_lines(templates.text(part["source"]), part["source"]).items():
            lines += [f"replaced in {slot}: {line}" for line in found]
    added: dict[str, list[str]] = {}
    for part in parts:
        for slot, found in _slot_lines(templates.text(part["source"]), part["source"]).items():
            added.setdefault(slot, []).extend(found)
    for slot in SLOTS:
        if added.get(slot):
            lines += [f"add to {slot}:", *added[slot]]
    lines += _edge_lines(
        edges(templates, chosen), None if before is None else edges(templates, before)
    )
    return "\n".join(lines) or None


def _edge_lines(now: list[str], old: list[str] | None) -> list[str]:
    """The edges to add, or on a move the edges that leave and those that join."""

    def shown(found: list[str]) -> str:
        return ", ".join(json.dumps(edge, ensure_ascii=False) for edge in found)

    if old is None:
        return [f"add to edges: {shown(now)}"] if now else []
    leave = [edge for edge in old if edge not in now]
    join = [edge for edge in now if edge not in old]
    return [
        f"edges {word}: {shown(found)}"
        for word, found in (("leave", leave), ("join", join))
        if found
    ]


def fragments_for(templates: Templates, chosen: Selection) -> list[str]:
    """The fragments the printed `adopt` command selects: the preset's, the acts', the
    overlays', each once, with `commands` last."""

    found: list[str] = []
    for item in (
        templates.lifecycle(chosen.preset),
        *(templates.act(act) for act in chosen.acts),
        *(templates.lifecycle(overlay) for overlay in chosen.overlays),
    ):
        found += [name for name in item["fragments"] if name not in found]
    return [name for name in found if name != "commands"] + (
        ["commands"] if "commands" in found else []
    )


# --- The target -----------------------------------------------------------------------------


def require_work_tree(target: Path) -> None:
    """Refuse a target Git cannot undo: no `.git` at or above it, or inside `.git` itself."""

    shown = textio.plain(str(target))
    if not target.is_dir():
        raise ScaffoldError(f"not a directory: {shown}")
    inside = any((folder / ".git").exists() for folder in (target, *target.parents))
    if not inside or any(paths.names_git(part) for part in target.parts):
        raise ScaffoldError(
            f"{shown} is not inside a Git work tree, and Git is the undo for what --accept writes; "
            "to start a project here, run `git init` there first"
        )


def _entries(folder: Path) -> list[str]:
    try:
        return sorted(os.listdir(folder))
    except OSError:
        return []


def _matches(root: Path, pattern: str) -> list[str]:
    """The paths under `root` that `pattern` names, each segment matched casefolded; `*` matches
    within one segment, and a pattern that ends in `/` names a folder."""

    folder = pattern.endswith("/")
    segments = pattern.rstrip("/").split("/")
    found = [""]
    for segment in segments:
        found = [
            f"{prefix}/{name}" if prefix else name
            for prefix in found
            for name in _entries(root / prefix)
            if name != ".git" and fnmatchcase(name.casefold(), segment.casefold())
        ]
    kind = os.path.isdir if folder else os.path.isfile
    return [path for path in found if kind(root / path)]


def _streams_routes(root: Path) -> list[str]:
    """The route paths that a "Streams —" line of the local fragment names in a code span, where
    the path exists."""

    try:
        text = textio.universal(textio.decode(paths.read_bounded(root, LOCAL)))
    except (paths.PathError, UnicodeDecodeError):
        return []
    lines = text.split("\n")
    found: list[str] = []
    for index, line in enumerate(lines):
        if not _STREAMS.match(line):
            continue
        joined = [line]
        for following in lines[index + 1 :]:
            if not following.strip() or _NEXT_PART.match(following):
                break
            joined.append(following)
        for span in _SPAN.findall(" ".join(joined)):
            span = span.strip()
            if paths.admits(span) and (root / span).is_file() and span not in found:
                found.append(span)
    return found


def present_at(root: Path, item: dict[str, Any]) -> str | None:
    """Where the file, or a file that stands for it, is found; the planned path first."""

    found: list[str] = []
    for pattern in item["present"]:
        found += _streams_routes(root) if pattern == STREAMS_ROUTE else _matches(root, pattern)
    if item["path"] in found:
        return item["path"]
    return found[0] if found else None


def refusal(root: Path, relative: str) -> str | None:
    """Why `--accept` would not write `relative`: `fileplan` refuses the destination, or a
    segment's casefold equals an existing entry of another case."""

    try:
        fileplan.destination(root, relative)
    except fileplan.WriteError as error:
        return str(error)
    here = root
    for segment in relative.split("/"):
        names = _entries(here)
        twins = [
            name for name in names if name != segment and name.casefold() == segment.casefold()
        ]
        if twins:
            other = (here / twins[0]).relative_to(root).as_posix()
            return (
                f"{other} differs from {segment} only in case; a clone on a case-insensitive file "
                "system cannot hold both"
            )
        if segment not in names:
            return None
        here = here / segment
    return None


# --- The plan -------------------------------------------------------------------------------


@dataclass
class Item:
    """One line of the plan: a file, or a part of one on a move."""

    id: str
    path: str
    label: str
    state: str
    origin: list[str]
    content: str | None = None
    present_at: str | None = None
    block: str | None = None
    block_origin: list[str] = field(default_factory=list)
    offer: str | None = None
    reason: str | None = None
    part: str | None = None
    holds: str | None = None


@dataclass
class Plan:
    chosen: Selection
    before: Selection | None
    items: list[Item]
    acts: list[dict[str, str]]
    adopt: str
    gone: list[str]
    assumes: list[str]


def _status(act: dict[str, Any], chosen: Selection) -> str:
    if chosen.host == "other":
        return str(act["status"]["other-host"])
    if chosen.visibility is None:
        values = {act["status"][name] for name in VISIBILITIES}
        return values.pop() if len(values) == 1 else "UNVERIFIED: visibility not given"
    return str(act["status"][chosen.visibility])


@dataclass(frozen=True)
class Scope:
    """What every file of one plan is read against."""

    templates: Templates
    root: Path
    chosen: Selection
    before: Selection | None


def plan(
    templates: Templates, root: Path, target: str, chosen: Selection, before: Selection | None
) -> Plan:
    scope = Scope(templates, root, chosen, before)
    items: list[Item] = []
    for entry in templates.data["files"]:
        now = parts_of(templates, entry, chosen)
        then = parts_of(templates, entry, before) if before else None
        found = present_at(root, entry)
        if now.in_set:
            items += _items(scope, entry, now, then, found)
        elif then is not None and before is not None and then.in_set and (then.content or found):
            items.append(_gone(templates, entry, before, then.content or then.offers, found))
    order = ("write", "refused", "present", "offer", "not required")
    items.sort(key=lambda item: order.index(item.state))
    selected = fragments_for(templates, chosen)
    adopt = f"outcomebound adopt {paths.shell_path(target)} --fragments {','.join(selected)}"
    gone = (
        [name for name in fragments_for(templates, before) if name not in selected]
        if before
        else []
    )
    assumes = [
        line
        for name in (chosen.preset, *chosen.overlays)
        for line in templates.lifecycle(name)["assumes"]
    ]
    return Plan(chosen, before, items, _platform_acts(scope), adopt, gone, assumes)


def _platform_acts(scope: Scope) -> list[dict[str, str]]:
    """Each platform act the selection calls for, with its status; on a move, the ones it adds
    say so."""

    listed = scope.templates.data["platform_acts"]
    old = {act["id"] for act in listed if scope.before and holds(act, scope.before)}
    acts = []
    for act in listed:
        if holds(act, scope.chosen):
            status = _status(act, scope.chosen)
            if scope.before is not None and act["id"] not in old:
                status += "; new with the move"
            acts.append({"id": act["id"], "text": act["text"], "who": act["who"], "status": status})
    return acts


def _label(entry: dict[str, Any]) -> str:
    return str(entry["id"]).replace("-", " ")


def _gone(
    templates: Templates,
    entry: dict[str, Any],
    before: Selection,
    parts: Sequence[dict[str, Any]],
    found: str | None,
    part: str | None = None,
) -> Item:
    return Item(
        entry["id"],
        entry["path"],
        found or entry["path"],
        "not required",
        _origin(templates, parts, before),
        present_at=found if found and found != entry["path"] else None,
        part=part,
        holds=STILL_HOLDS if entry["id"] in DUTIES else TO_RETIRE,
    )


def _items(
    scope: Scope, entry: dict[str, Any], now: Parts, then: Parts | None, found: str | None
) -> list[Item]:
    """The plan's line for one file of the set, and on a move a line for each part of a present
    document that the new set no longer has."""

    templates, chosen = scope.templates, scope.chosen
    origin = _origin(templates, now.content or now.offers or now.pending, chosen)
    item = Item(entry["id"], entry["path"], entry["path"], "write", origin)
    if found is not None:
        _present(scope, item, entry, now, then, found)
    elif now.content and (entry["join"] == "whole" or "head" in entry):
        item.reason = refusal(scope.root, entry["path"])
        if item.reason is not None:
            item.state = "refused"
        else:
            item.content = render(templates, entry, now.content, chosen)
    elif now.offers:
        item.state, item.label = "offer", _label(entry)
        item.offer = templates.text(now.offers[0]["source"]).strip()
        item.block = block(templates, entry, now.content, chosen)
        item.block_origin = _origin(templates, now.content, chosen)
    elif now.pending:
        item.state, item.offer = "offer", f"--with {now.pending[0]['offer']}"
    else:
        return []
    found_items = [item]
    if scope.before is not None and then is not None and then.in_set and found is not None:
        kept = {part["source"] for part in now.content}
        for part in then.content if entry["join"] == "blocks" else ():
            if part["source"] not in kept:
                ids = ", ".join(_origin(templates, [part], scope.before))
                found_items.append(_gone(templates, entry, scope.before, [part], found, ids))
    return found_items


def _present(
    scope: Scope, item: Item, entry: dict[str, Any], now: Parts, then: Parts | None, found: str
) -> None:
    """A present file: where it was found, and the block of what the plan has for it; on a move,
    only the parts the old set lacked, and for the local fragment the lines they replace."""

    item.state = "present"
    if "<" in entry["path"]:
        item.label = found
    item.present_at = found if found != item.label else None
    old = {part["source"] for part in then.content} if then and then.in_set else set()
    new_parts = [part for part in now.content if part["source"] not in old]
    replaced: list[dict[str, Any]] = []
    slots = entry["join"] == "slots"
    if scope.before is not None and then is not None and slots:
        kept = {part["source"] for part in now.content}
        replaced = [part for part in then.content if part["source"] not in kept]
    before = scope.before if slots else None
    text = _present_text(scope.root, found)
    if text is not None and not replaced:
        new_parts = [part for part in new_parts if not _holds(scope.templates, entry, part, text)]
    item.block = block(scope.templates, entry, new_parts, scope.chosen, replaced, before)
    if item.block is not None and text is not None and before is None:
        item.block = _unlisted_edges(scope, item.block, text)
    item.block_origin = _origin(scope.templates, new_parts, scope.chosen)


def _unlisted_edges(scope: Scope, text: str, present: str) -> str | None:
    """`text` with its edges line naming only the edges `present` does not already list."""

    wanted = [
        edge
        for edge in edges(scope.templates, scope.chosen)
        if json.dumps(edge, ensure_ascii=False) not in present
    ]
    lines = [line for line in text.split("\n") if not line.startswith("add to edges: ")]
    return "\n".join(lines + _edge_lines(wanted, None)) or None


def _present_text(root: Path, relative: str) -> str | None:
    try:
        return textio.universal(textio.decode(paths.read_bounded(root, relative)))
    except (paths.PathError, UnicodeDecodeError, ValueError):
        return None


def _holds(templates: Templates, entry: dict[str, Any], part: dict[str, Any], text: str) -> bool:
    """Whether a present file already holds every line of `part`, as the scaffold writes it or
    with each marker filled: a re-run must not ask the agent to add what is there."""

    source = templates.text(part["source"])
    if entry["join"] == "slots":
        lines = [line for found in _slot_lines(source, part["source"]).values() for line in found]
    else:
        lines = [line for line in source.split("\n") if line.strip()]
    held = {line.strip() for line in text.split("\n") if line.strip()}
    for line in lines:
        pieces = MARKER.split(line.strip())
        # MARKER has two groups, so the literal text is every third piece.
        pattern = ".+?".join(re.escape(piece) for piece in pieces[::3])
        if not any(re.fullmatch(pattern, row) for row in held):
            return False
    return bool(lines)


# --- --accept -------------------------------------------------------------------------------


@dataclass
class Accepted:
    written: list[Item]
    refused: list[Item]
    reason: str | None


def accept(root: Path, made: Plan) -> Accepted:
    """Write each planned absent file through `fileplan`, every one expected absent. A refusal
    the plan read writes nothing; one at the write keeps what was written before it."""

    refused = [item for item in made.items if item.state == "refused"]
    writes = [item for item in made.items if item.state == "write" and item.content is not None]
    if refused:
        return Accepted([], refused, f"{refused[0].path}: {refused[0].reason}")
    changes = {item.path: item.content.encode("utf-8") for item in writes if item.content}
    try:
        fileplan.write(root, changes, dict.fromkeys(changes))
    except (fileplan.WriteError, OSError) as error:
        written = [item for item in writes if _holds_bytes(root, item.path, changes[item.path])]
        return Accepted(written, [], str(error))
    return Accepted(writes, [], None)


def _holds_bytes(root: Path, relative: str, data: bytes) -> bool:
    try:
        return paths.read_bounded(root, relative) == data
    except paths.PathError:
        return False


# --- --check --------------------------------------------------------------------------------


def markers_in(text: str) -> list[tuple[int, str, str]]:
    """Each (line, kind, label) of a marker in `text`, outside a fenced block and a code span."""

    found: list[tuple[int, str, str]] = []
    fence: str | None = None
    for number, line in enumerate(textio.universal(text).split("\n"), start=1):
        mark = _FENCE.match(line)
        if fence is not None:
            if mark and mark.group(1)[0] == fence[0] and len(mark.group(1)) >= len(fence):
                fence = None
            continue
        if mark:
            fence = mark.group(1)
            continue
        bare = _CODE_SPAN.sub(lambda span: " " * len(span.group(0)), line)
        found += [(number, kind, label) for kind, label in MARKER.findall(bare)]
    return found


def _git_listed(root: Path) -> list[str] | None:
    """What Git tracks, or holds untracked and unignored, under `root`; None where Git cannot
    list it. Git comes from PATH's absolute entries only, so the target cannot supply its own."""

    inherited = dict(os.environ)
    inherited["PATH"] = os.pathsep.join(
        part for part in inherited.get("PATH", "").split(os.pathsep) if os.path.isabs(part)
    )
    inherited["GIT_OPTIONAL_LOCKS"] = "0"
    try:
        done = subprocess.run(
            [
                programs.require("git", inherited),
                *GIT_READ_CONFIGURATION,
                "ls-files",
                "-z",
                "--cached",
                "--others",
                "--exclude-standard",
            ],
            cwd=root,
            env=git_environment(inherited),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            check=False,
        )
    except OSError:
        return None
    if done.returncode != 0:
        return None
    return sorted({os.fsdecode(item) for item in done.stdout.split(b"\0") if item})


def _recorded_copies(root: Path) -> set[str]:
    """The whole files an install records as its own copies of OutcomeBound's text."""

    try:
        document = json.loads(textio.decode(paths.read_bounded(root, INSTALL_MANIFEST)))
    except (paths.PathError, UnicodeDecodeError, ValueError):
        return set()
    records = document.get("artifacts") if isinstance(document, dict) else None
    return {
        record["path"]
        for record in records or []
        if isinstance(record, dict)
        and record.get("kind") in RECORDED_COPIES
        and isinstance(record.get("path"), str)
    }


def _owned(text: str) -> str:
    """`text` with OutcomeBound's managed blocks blanked, their lines kept."""

    if "outcomebound:begin" not in text:
        return text
    try:
        blocks = identity.find_managed_blocks(text)
    except identity.IdentityError:
        return text
    pieces, last = [], 0
    for found in blocks:
        pieces.append(text[last : found.begin_offset])
        pieces.append(re.sub(r"[^\n]", " ", text[found.begin_offset : found.end_offset]))
        last = found.end_offset
    pieces.append(text[last:])
    return "".join(pieces)


@dataclass(frozen=True)
class Value:
    path: str
    line: int
    kind: str
    label: str


def values(root: Path) -> list[Value]:
    """Each marker left in a file Git lists under `root`, or in every file where Git cannot list
    them; `.git`, managed blocks and the install's recorded copies left out. A file that is not
    UTF-8 text, or holds a NUL byte, is not read."""

    listed = _git_listed(root)
    if listed is None:
        listed = [
            (folder.path / name).relative_to(root).as_posix()
            for folder in walk.folders(root)
            for name in folder.files
        ]
    skipped = _recorded_copies(root)
    found: list[Value] = []
    for relative in listed:
        if relative in skipped or any(paths.names_git(part) for part in relative.split("/")):
            continue
        try:
            data = paths.read_bounded(root, relative)
        except paths.PathError:
            continue
        if b"\0" in data:
            continue
        try:
            text = textio.universal(textio.decode(data))
        except UnicodeDecodeError:
            continue
        found += [
            Value(relative, line, kind, label) for line, kind, label in markers_in(_owned(text))
        ]
    return found


# --- Output ---------------------------------------------------------------------------------


def _shown(text: str) -> str:
    return textio.visible(text)


def _facts(chosen: Selection) -> str:
    words = [word for word in (chosen.visibility, chosen.host) if word]
    shown = ", ".join(words)
    if chosen.acts:
        shown += "; acts " + ", ".join(chosen.acts)
    if chosen.offers:
        shown += "; with " + ", ".join(chosen.offers)
    return shown


def _count(number: int, word: str) -> str:
    return f"{number} {word}{'' if number == 1 else 's'}"


def _detail(item: Item) -> str:
    origin = ", ".join(item.origin)
    if item.state == "present":
        where = f"; found at {_shown(item.present_at)}" if item.present_at else ""
        added = "; its block is printed below; add it on the person's yes" if item.block else ""
        return f"{origin}{where}{added}"
    if item.state == "offer":
        return item.offer or ""
    if item.state == "refused":
        return _shown(item.reason or "")
    if item.state == "not required":
        what = f"the {item.part} part of this file" if item.part else origin
        return f"{what}; {item.holds}; nothing is deleted"
    return origin


def _lines(items: Sequence[Item], states: Sequence[str] | None = None) -> list[str]:
    """One line for each item: its state (or the word `states` gives), its path or name, and
    what it comes from or what settles it."""

    words = states or [item.state for item in items]
    width = max((len(_shown(item.label)) for item in items), default=0) + 2
    lines = []
    for word, item in zip(words, items, strict=True):
        detail = "" if word == "wrote" else _detail(item)
        lines.append(f"{word:<7} {_shown(item.label):<{width}} {detail}".rstrip())
    return lines


def _blocks(items: Sequence[Item]) -> list[str]:
    lines: list[str] = []
    for item in items:
        if item.block:
            where = (item.present_at or item.label) if item.state == "present" else item.path
            lines.append(f"--- block for {_shown(where)} ({', '.join(item.block_origin)}) ---")
            lines += [BLOCK_FENCE + "text", item.block, BLOCK_FENCE]
    return lines


def _next(made: Plan) -> str:
    step = (
        "on the person's yes, run this command again with --accept, fill each value marked fill, "
        "then run it with --check"
    )
    if made.before is not None and made.before.preset == "prototype" != made.chosen.preset:
        step += "; the move's brief names the parts kept, and probe code is rebuilt, never promoted"
    return step


def plan_text(made: Plan) -> str:
    states = [item.state for item in made.items]
    counts = [
        f"{states.count('write')} to write",
        f"{states.count('present')} present",
        f"{states.count('offer')} to offer",
    ]
    if "refused" in states:
        counts.append(f"{states.count('refused')} refused")
    if "not required" in states:
        counts.append(f"{states.count('not required')} not required")
    chosen = made.chosen
    lines = [
        f"plan {chosen.lifecycle} ({_facts(chosen)}): {', '.join(counts)}; "
        f"{_count(len(made.acts), 'platform act')}; writes nothing without --accept",
        "assumes: " + "; ".join(made.assumes),
    ]
    if made.before is not None:
        lines.insert(1, f"from: {made.before.lifecycle}")
    lines += _lines(made.items)
    lines += [f"act     {act['text']}: {act['who']}; {act['status']}" for act in made.acts]
    lines.append(f"adopt:  {made.adopt}")
    lines.append("# name the harness in use with --harness, as `adopt --detect` proposes")
    if made.gone:
        lines.append(f"fragments no longer selected: {', '.join(made.gone)}")
    lines.append(f"next: {_next(made)}")
    lines += _blocks(made.items)
    return "\n".join(lines) + "\n"


def accept_text(made: Plan, done: Accepted, target: str) -> str:
    present = [item for item in made.items if item.state == "present"]
    if done.reason is None:
        head = (
            f"PASS wrote {_count(len(done.written), 'file')}"
            if done.written
            else "PASS nothing to write"
        )
        if present:
            kept = "left as it was" if len(present) == 1 else "left as they were"
            head += f"; {len(present)} present, {kept}"
    else:
        head = f"FAIL refused: {_shown(done.reason)}; " + (
            f"wrote {_count(len(done.written), 'file')} before it"
            if done.written
            else "nothing written"
        )
    shown = [*done.written, *done.refused, *present]
    words = ["wrote"] * len(done.written) + [item.state for item in [*done.refused, *present]]
    lines = [head, *_lines(shown, words)]
    if done.reason is None:
        lines.append(
            "next: fill each value marked fill from the person's words, then run "
            f"outcomebound scaffold {paths.shell_path(target)} --check"
        )
    else:
        lines.append(
            "next: settle the refusal, then run this command again; it writes only what is absent"
        )
    lines += _blocks(present)
    return "\n".join(lines) + "\n"


def check_text(found: Sequence[Value]) -> str:
    if not found:
        return "PASS no value left to fill\n"
    fills = sum(value.kind == "fill" for value in found)
    owners = len(found) - fills
    lines = [
        f"FAIL {_count(len(found), 'value')} left: {fills} to fill, "
        f"{_count(owners, 'gate owner')} not named"
    ]
    for value in found:
        line = f"{_shown(value.path)}:{value.line}: {value.kind}: {_shown(value.label)}"
        if value.kind == "owner":
            line += "; next: the person names the owner, and the agent writes the name they give"
        lines.append(line)
    lines.append(
        "next: fill each value from the person's words; a gate owner is the person's to name"
    )
    return "\n".join(lines) + "\n"


def _facts_document(chosen: Selection) -> dict[str, Any]:
    document: dict[str, Any] = {"host": chosen.host}
    if chosen.visibility:
        document["visibility"] = chosen.visibility
    if chosen.acts:
        document["acts"] = list(chosen.acts)
    if chosen.offers:
        document["with"] = list(chosen.offers)
    return document


def _file_document(item: Item, state: str | None = None) -> dict[str, Any]:
    document: dict[str, Any] = {
        "path": item.path,
        "state": state or item.state,
        "from": item.origin,
    }
    if item.present_at:
        document["present_at"] = item.present_at
    if item.block:
        document["block"] = item.block
    if item.offer:
        document["offer"] = item.offer
    if item.reason:
        document["reason"] = item.reason
    if item.part:
        document["part"] = item.part
    return document


def plan_document(
    made: Plan, mode: str, summary: str, done: Accepted | None = None
) -> dict[str, Any]:
    document: dict[str, Any] = {
        "version": 1,
        "mode": mode,
        "verdict": "PLAN" if done is None else ("PASS" if done.reason is None else "FAIL"),
        "summary": summary,
        "lifecycle": made.chosen.lifecycle,
        "facts": _facts_document(made.chosen),
        "assumes": made.assumes,
        "adopt": made.adopt,
    }
    if made.before is not None:
        document["from"] = made.before.lifecycle
    if done is None:
        document["files"] = [_file_document(item) for item in made.items]
        document["platform_acts"] = made.acts
        document["next"] = _next(made)
    else:
        written = {item.path for item in done.written}
        document["files"] = [
            _file_document(item, "written" if item.path in written else None)
            for item in made.items
            if item.path in written or item.state in ("present", "refused")
        ]
    return document


def check_document(
    found: Sequence[Value], summary: str, chosen: Selection | None
) -> dict[str, Any]:
    document: dict[str, Any] = {
        "version": 1,
        "mode": "check",
        "verdict": "FAIL" if found else "PASS",
        "summary": summary,
        "values": [
            {"path": value.path, "line": value.line, "kind": value.kind, "label": value.label}
            for value in found
        ],
    }
    if chosen is not None:
        document["lifecycle"] = chosen.lifecycle
        document["facts"] = _facts_document(chosen)
    if found:
        document["next"] = (
            "fill each value from the person's words; a gate owner is the person's to name"
        )
    return document


# --- Command line ---------------------------------------------------------------------------

USAGE = """outcomebound scaffold <target> --lifecycle <preset>[+<overlay>...]
         [--visibility public|private|private-free] [--host github|other]
         [--acts <act>[,<act>...]] [--with <offer>[,<offer>...]] [--from <preset>[+<overlay>...]]
         [--accept | --check] [--json]"""
DESCRIPTION = """\
Preview, then write, the project files a lifecycle needs: a new project's, or the parts a move to
another lifecycle adds. The files are the project's once written: the scaffold installs nothing
of OutcomeBound, records nothing, and never edits, replaces or deletes a file."""
EPILOG = """\
presets:  prototype, solo, team, organization
overlays: client, eu-market, safety-critical, audit, unattended-agents, ai-product
          (client, eu-market and audit are refused on prototype)
facts:    --visibility, required beyond prototype; --host, github by default (other writes
          nothing under .github/); --acts from deploy, publish, tag, stored-data (refused on
          prototype); --with codeowners and pr-template, organization only
modes:    no mode flag prints the plan and writes nothing: each file as write, present, offer,
          refused or, on a move (--from), not required; each platform act and who does it; the
          adopt command with its fragments; and a block for each present file the plan has
          parts for. --accept writes each planned file that is absent, and each --with offer,
          through the engine's safe writer. --check reads every file Git lists in the target and
          reports each value marked fill and each gate owner not named; the lifecycle flags do
          not narrow it. --json prints one report (schemas/scaffold-report.schema.json).
reads:    the target's files, Git's listing of them, and templates/scaffold/ in the engine
writes:   only --accept's absent files, inside the target
exits:    0 the plan printed, each absent file written, or no value left; 1 not a Git work
          tree, the templates cannot be read, a write refused, or a value left (the first line
          prints the count); 2 usage"""


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="outcomebound scaffold",
        usage=USAGE,
        description=DESCRIPTION,
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("target", help="a Git work tree")
    parser.add_argument("--lifecycle", help="a preset, then any overlays, joined by +")
    parser.add_argument("--visibility", choices=VISIBILITIES)
    parser.add_argument("--host", choices=HOSTS, default="github")
    parser.add_argument("--acts", help="the acts that cannot be undone, comma-separated")
    parser.add_argument("--with", dest="offers", help="the offers to write, comma-separated")
    parser.add_argument("--from", dest="before", help="on a move: the lifecycle the project leaves")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--accept", action="store_true", help="write each planned absent file")
    mode.add_argument("--check", action="store_true", help="report each value left to fill")
    parser.add_argument("--json", action="store_true", help="print one report document")
    return parser


def _selections(
    arguments: argparse.Namespace, templates: Templates
) -> tuple[Selection | None, Selection | None]:
    """The lifecycle `--lifecycle` names with its facts, and the one `--from` names."""

    chosen = before = None
    if arguments.lifecycle is not None:
        chosen = selection(templates, arguments, need_visibility=not arguments.check)
    if arguments.before is not None:
        if chosen is None:
            raise UsageError("--from names the lifecycle a move leaves; give --lifecycle too")
        old, overlays = parse_lifecycle(arguments.before, templates)
        # A prototype takes no act, so the old set of a move from one has none.
        acts = () if old == "prototype" else chosen.acts
        before = Selection(old, overlays, acts, chosen.visibility, chosen.host, ())
    return chosen, before


def _print(document: dict[str, Any] | None, text: str) -> None:
    print(
        json.dumps(document, indent=2) if document is not None else text,
        end="" if document is None else "\n",
    )


def _run(arguments: argparse.Namespace, parser: argparse.ArgumentParser, source: Path) -> int:
    if arguments.lifecycle is None and not arguments.check:
        parser.error("--lifecycle is required, except with --check")
    templates = load(source)
    try:
        chosen, before = _selections(arguments, templates)
    except UsageError as error:
        parser.error(str(error))
    root = Path(arguments.target).resolve()
    require_work_tree(root)
    if chosen is None or arguments.check:
        found = values(root)
        text = check_text(found)
        summary = text.split("\n", 1)[0]
        _print(check_document(found, summary, chosen) if arguments.json else None, text)
        return 1 if found else 0
    made = plan(templates, root, arguments.target, chosen, before)
    if not arguments.accept:
        text = plan_text(made)
        summary = text.split("\n", 1)[0]
        _print(plan_document(made, "plan", summary) if arguments.json else None, text)
        return 0
    done = accept(root, made)
    text = accept_text(made, done, arguments.target)
    summary = text.split("\n", 1)[0]
    _print(plan_document(made, "accept", summary, done) if arguments.json else None, text)
    return 0 if done.reason is None else 1


def main(argv: Sequence[str] | None = None, *, source: Path = home.ROOT) -> int:
    parser = _parser()
    try:
        arguments = parser.parse_args(argv)
        return _run(arguments, parser, Path(source))
    except SystemExit as stop:
        return stop.code if isinstance(stop.code, int) else 2
    except ScaffoldError as error:
        print(f"scaffold: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
