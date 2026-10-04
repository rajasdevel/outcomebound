"""Install, upgrade, check and remove OutcomeBound in one target repository.

`adopt <target>` writes three blocks into the target's AGENTS.md: the
operating contract; the project facts the engine observes or the adopter records
(`outcomebound_tools.facts`); and the guidance pointers, the project's own `local`
fragment inline and then one line per selected fragment, copied under
`.outcomebound/fragments/`, and per skill: those in `SKILLS`, and those a selected fragment names
in its `skills:`. Selecting the workspace fragment also
installs `.agents/.gitignore`, which keeps its four folders out of Git. `--finish-check` adds one
entry to the settings document of each selected harness whose table row has a `finish_hook`
(`outcomebound_tools.finish_check`), a `hook` record, written back with its keys, their order and
its indentation kept. It installs each skill for
every harness, and an `@AGENTS.md` import into each harness file that would not load
AGENTS.md otherwise: none where the harness table says the harness reads AGENTS.md
itself unless one of its files exists, and none exists. A harness outside
the table is `generic`, the default: its skills go under `.outcomebound/skills/`,
which the pointers name. Re-running it is the upgrade, and each install prints the
words an agent always loads, skill descriptions included; no size refuses one. What it
wrote is recorded in `.outcomebound/manifest.json` (format 2), one `{kind, path, id,
sha256}` record per block or file, the facts record holding the recorded selection,
the Done commands and each source a fact was read from with its digest; a record of
any other kind or id belongs to another route and is kept as it is. Nothing whose
bytes differ from its record is replaced or removed without `--force`. Git is the
undo, so the target must be inside a Git work tree, and every write goes through
`fileplan.write` with the manifest last.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, NamedTuple

from outcomebound_tools import (
    adapters,
    discovery,
    facts,
    fileplan,
    finish_check,
    fragments,
    home,
    identity,
    paths,
)

ENGINE = home.ROOT
MANIFEST = ".outcomebound/manifest.json"
FORMAT_VERSION = 2
AGENTS = "AGENTS.md"
IMPORT = "@AGENTS.md"
KERNEL = "operating-contract"
FACTS = facts.FACTS
POINTERS = facts.POINTERS
# Where each block goes when it is new: directly after the block named here.
AFTER = {FACTS: KERNEL, POINTERS: FACTS}
SKILLS = fragments.SKILLS
# The condition each skill's pointer line carries.
CONDITIONS = {
    "using-outcomebound": "when unsure how much design, testing, review or process a task needs",
    "decision-brief": "when a decision is the user's to make",
    "gather-requirements": (
        "when a request's outcome or completion bar is unclear, "
        "or requirements arrive from an existing source"
    ),
    "tests-worth-keeping": "when writing, changing or judging a test",
    "slice-tickets": "when breaking work into tickets",
    "hand-off-tickets": "when handing an accepted ticket to the agent or model that will build it",
}
# Skills an earlier install carried and this engine no longer ships. A record of one is still
# adopt's, so `--check` reads its files stale and the next install removes them.
RETIRED_SKILLS: tuple[str, ...] = ()
FILE_KINDS = ("skill", "fragment", "ignore")
# One entry in a harness's JSON settings document, recorded by the entry's canonical digest.
HOOK = "hook"
FINISH_CHECK = finish_check.ID
# The workspace fragment's folders stay out of Git: selecting it installs this file too.
WORKSPACE = "workspace"
WORKSPACE_IGNORE = ".agents/.gitignore"
WORKSPACE_TEMPLATE = "templates/workspace.gitignore"
# A harness outside the harness table: the skills go where the pointers name them.
GENERIC = "generic"
GENERIC_SKILLS = ".outcomebound/skills"
KERNEL_TEMPLATE = "templates/managed-block.agents.md.tmpl"
LOCAL = facts.LOCAL
LOCAL_FRAGMENT = f"{facts.FRAGMENT_DIR}/{LOCAL}.md"
# What --detect proposes first for Done where a floor is installed: the floor's runner.
FLOOR_RUNNER = "outcomebound floor check . --base origin/main"
# The import block's body never changes, so its version does not follow the
# engine's: an upgrade never rewrites a harness file the adopter owns.
POINTER_VERSION = "1.0.0"
CHECK_CAP = 100
# Files in a target that name the harness it uses, for `--detect`.
HARNESS_SIGNS = (
    ("CLAUDE.md", "claude-code"),
    (".claude", "claude-code"),
    (".cursor", "cursor"),
    ("GEMINI.md", "gemini"),
    (".gemini", "gemini"),
)
NOT_V2 = f"{MANIFEST} is not a format 2 manifest; remove the install that wrote it, then re-run"

Record = dict[str, Any]
# Each path this run changes, in the order it is written: (bytes as read, bytes to write).
Planned = dict[str, tuple[bytes | None, bytes | None]]
# What a run tells the person beside its changes, as (verb, text) report lines.
Notes = list[tuple[str, str]]


class AdoptError(Exception):
    """A refusal: nothing is written, and each reason is printed on its own line."""

    def __init__(self, *reasons: str) -> None:
        super().__init__("; ".join(reasons))
        self.reasons = reasons


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def label(path: str, name: str | None) -> str:
    return f"{path} ({name})" if name else path


def _read(target: Path, relative: str) -> bytes | None:
    try:
        return fileplan.current(target, relative)
    except fileplan.WriteError as error:
        raise AdoptError(str(error)) from error


# --- What the engine renders ----------------------------------------------------


def _source_text(source: Path, relative: str) -> str:
    try:
        return (source / relative).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise AdoptError(f"cannot read {relative} in the engine at {source}: {error}") from error


def engine_version(source: Path) -> str:
    return _source_text(source, "VERSION").strip()


def kernel_block(source: Path) -> str:
    """The operating contract as the template states it, with `v=` this engine's VERSION."""

    try:
        body = identity.parse_managed_block(_source_text(source, KERNEL_TEMPLATE), KERNEL).body
        return identity.format_managed_block(KERNEL, engine_version(source), body)
    except identity.IdentityError as error:
        raise AdoptError(f"{KERNEL_TEMPLATE}: {error}") from error


def catalog(source: Path, target: Path, ids: Sequence[str]) -> dict[str, fragments.Fragment]:
    """The engine's fragments, and `local`, the target's own file, when it is selected."""

    try:
        found = fragments.load_all(source)
    except fragments.FragmentError as error:
        raise AdoptError(str(error)) from error
    if LOCAL in ids:
        found[LOCAL] = _local_fragment(source, target)
    return found


def _local_fragment(source: Path, target: Path) -> fragments.Fragment:
    data = _read(target, LOCAL_FRAGMENT)
    if data is None:
        raise AdoptError(
            f"the {LOCAL} fragment is the target's own file and is missing: {LOCAL_FRAGMENT}; "
            f"copy {source / 'templates/fragment-local.md'} there and edit it"
        )
    try:
        fragment = fragments.parse_fragment(data.decode("utf-8"), LOCAL_FRAGMENT)
    except UnicodeDecodeError as error:
        raise AdoptError(f"{LOCAL_FRAGMENT} is not UTF-8 text") from error
    except fragments.FragmentError as error:
        raise AdoptError(str(error)) from error
    if fragment.id != LOCAL:
        raise AdoptError(f"{LOCAL_FRAGMENT} declares id {fragment.id!r}, not {LOCAL!r}")
    return fragment


@dataclass(frozen=True)
class Guidance:
    """The facts and pointers blocks, and the fragment files the pointers name, as rendered."""

    rendered: facts.Rendered
    files: dict[str, bytes]
    skills: tuple[str, ...]


class Chosen(NamedTuple):
    """What the adopter chose for the facts block: the Done commands, in run order, and the
    style for text a person reads, a key of `facts.STYLES`, or none."""

    done: Sequence[str]
    style: Sequence[str] = ()


def guidance(
    target: Path,
    found: Sequence[Route],
    found_fragments: dict[str, fragments.Fragment],
    ids: Sequence[str],
    chosen: Chosen,
    importing: Sequence[str] = (),
) -> Guidance:
    """The facts and pointers for these harnesses, fragments and Done commands.

    The pointers name each skill where a generic install puts it, else its first native copy;
    the Precedence fact names AGENTS.md and each selected harness's import host that exists,
    or that `importing` says this run writes an import block into.
    """

    try:
        selected = fragments.select(found_fragments, ids) if ids else []
    except fragments.FragmentError as error:
        raise AdoptError(str(error)) from error
    files: dict[str, bytes] = {}
    for item in selected:
        if item.id != LOCAL:
            files[f"{facts.FRAGMENT_DIR}/{item.id}.md"] = _fragment_bytes(item)
    roots = sorted({item.skills for item in found})
    root = GENERIC_SKILLS if GENERIC_SKILLS in roots else roots[0] if roots else None
    names = fragments.carried(selected)
    skills = [
        (CONDITIONS.get(name, f"when the {name} skill applies"), f"{root}/{name}/SKILL.md")
        for name in names
    ]
    hosts = [AGENTS, *sorted({item.host for item in found if item.host})]
    hosts = [h for h in hosts if h in (AGENTS, *importing) or os.path.lexists(target / h)]
    skills = skills if root else []
    rendered = facts.render(target, selected, chosen.done, hosts, skills, chosen.style)
    return Guidance(rendered, files, names)


def _fragment_bytes(fragment: fragments.Fragment) -> bytes:
    if fragment.path is None:
        raise AdoptError(f"the {fragment.id} fragment has no file to install")
    try:
        return fragment.path.read_bytes()
    except OSError as error:
        raise AdoptError(f"cannot read the {fragment.id} fragment: {error}") from error


def pointer_id(path: str) -> str:
    return identity.pointer_block_id(path).split(":", 1)[1]


def pointer_block(path: str) -> str:
    return identity.format_managed_block(pointer_id(path), POINTER_VERSION, IMPORT)


def workspace_ignore(source: Path) -> bytes:
    return _source_text(source, WORKSPACE_TEMPLATE).encode("utf-8")


def skill_file(source: Path, name: str, relative: str = "SKILL.md") -> bytes:
    try:
        return (source / "skills" / name / relative).read_bytes()
    except OSError as error:
        raise AdoptError(f"cannot read skills/{name}/{relative} in the engine: {error}") from error


def skill_files(source: Path, name: str) -> dict[str, bytes]:
    """Every file one engine skill ships, by its path inside the skill's folder, `SKILL.md`
    first: the notes a skill names beside it travel with every copy."""

    folder = source / "skills" / name
    try:
        found = sorted(
            path.relative_to(folder).as_posix()
            for path in folder.rglob("*")
            if path.is_file()
            and not path.relative_to(folder).as_posix().startswith(".")
            and "__pycache__" not in path.parts
        )
    except OSError as error:
        raise AdoptError(f"cannot read skills/{name}/ in the engine: {error}") from error
    names = ["SKILL.md", *(relative for relative in found if relative != "SKILL.md")]
    return {relative: skill_file(source, name, relative) for relative in names}


# --- Harnesses ------------------------------------------------------------------


@dataclass(frozen=True)
class Route:
    """How one harness reaches the contract: where its skills live, the file that must
    import AGENTS.md (None when the harness reads AGENTS.md itself), and the files whose
    absence lets it read AGENTS.md itself from version `since` (none: it always needs one)."""

    harness: str
    skills: str
    host: str | None
    unless: tuple[str, ...] = ()
    since: str = ""


def _reads_itself(row: dict[str, Any]) -> tuple[tuple[str, ...], str]:
    """The row's `reads_agents_md` as (unless, since); ((), "") where it records no rule.

    `unless` names the files at the target root whose presence makes the harness read them in
    place of AGENTS.md; `since` is the first version that reads AGENTS.md itself where none of
    them exists. A value of any other shape records no rule, so the import block is written.
    """

    value = row.get("reads_agents_md")
    unless = value.get("unless") if isinstance(value, dict) else None
    since = value.get("since") if isinstance(value, dict) else None
    if (
        isinstance(unless, list)
        and unless
        and all(paths.admits(name) for name in unless)
        and isinstance(since, str)
        and since
    ):
        return tuple(unless), since
    return (), ""


def harness_table(source: Path) -> dict[str, Any]:
    try:
        table = json.loads(_source_text(source, "adapters/harnesses.json"))
    except ValueError as error:
        raise AdoptError(f"adapters/harnesses.json: {error}") from error
    if not isinstance(table, dict):
        raise AdoptError("adapters/harnesses.json is not an object")
    return table


def route(name: str, row: object) -> Route | str:
    """The route the harness table gives `name`, or why it cannot load AGENTS.md; `generic`,
    a harness outside the table, reads AGENTS.md and the skills where the pointers name them."""

    if name == GENERIC:
        return Route(GENERIC, GENERIC_SKILLS, None)
    if not isinstance(row, dict):
        return f"unknown harness {name!r}"
    if row.get("verified") is not True:
        return f"{name}: the harness table has not verified how it loads AGENTS.md"
    skills = str(row.get("skill_install_path") or "").rstrip("/")
    if not paths.admits(skills):
        return f"{name}: the harness table names no skill directory inside the target"
    mechanism = str(row.get("pointer_mechanism") or "")
    if mechanism in (AGENTS, "native"):
        return Route(name, skills, None)
    host, _, reference = mechanism.partition("@")
    if reference == AGENTS and paths.admits(host):
        return Route(name, skills, host, *_reads_itself(row))
    return f"{name} cannot be made to load AGENTS.md: the harness table routes it by {mechanism!r}"


def loadable(table: dict[str, Any]) -> list[str]:
    """Every harness the table gives a route to AGENTS.md, sorted."""

    return [name for name, row in sorted(table.items()) if isinstance(route(name, row), Route)]


def routes(source: Path, names: Sequence[str]) -> list[Route]:
    """Each named harness's route; one refusal names every harness that has none."""

    table = harness_table(source)
    found = [route(name, table.get(name)) for name in names]
    reasons = [item for item in found if isinstance(item, str)]
    if reasons:
        listed = ", ".join([*loadable(table), GENERIC])
        raise AdoptError(*reasons, f"harnesses that load AGENTS.md: {listed}")
    return [item for item in found if isinstance(item, Route)]


def _imports(text: str) -> bool:
    """Whether `text` has a live `@AGENTS.md` line: outside code fences, nothing else on it."""

    return any(line.rstrip(" \t\r") == IMPORT for line in identity.fence_free_lines(text))


# --- Blocks inside a host file --------------------------------------------------


def _span(text: str, block_id: str) -> tuple[int, int] | None:
    for block in identity.find_managed_blocks(text):
        if block.block_id == block_id:
            return block.begin_offset, block.end_offset
    return None


def block_text(text: str, block_id: str) -> bytes | None:
    """The block `block_id` in `text`, both sentinels included, or None."""

    span = _span(text, block_id)
    return None if span is None else text[span[0] : span[1]].encode("utf-8")


def put(text: str, block_id: str, rendered: str, after: str | None = None) -> str:
    """`text` with `rendered` in place of block `block_id`, else inserted.

    A new block goes directly after the block `after` when that is present, else
    first in the file, one blank line from its neighbour: `cut` removes exactly it.
    """

    span = _span(text, block_id)
    if span is not None:
        return text[: span[0]] + rendered + text[span[1] :]
    anchor = _span(text, after) if after else None
    if anchor is not None:
        return text[: anchor[1]] + "\n\n" + rendered + text[anchor[1] :]
    return rendered + ("\n\n" + text if text else "\n")


def cut(text: str, block_id: str) -> str:
    """`text` without block `block_id` and the one separator `put` gave it."""

    span = _span(text, block_id)
    if span is None:
        return text
    head, tail = text[: span[0]], text[span[1] :]
    if not head:
        return tail[2:] if tail.startswith("\n\n") else tail.removeprefix("\n")
    return (head[:-2] if head.endswith("\n\n") else head.removesuffix("\n")) + tail


def _host_text(path: str, data: bytes | None) -> str:
    try:
        text = "" if data is None else data.decode("utf-8")
        identity.find_managed_blocks(text)
    except UnicodeDecodeError as error:
        raise AdoptError(f"{path} is not UTF-8 text") from error
    except identity.IdentityError as error:
        raise AdoptError(f"{path}: {error}") from error
    return text


# --- One entry in a JSON settings document ---------------------------------------

Spot = tuple[str, int]


def _compact(text: str) -> str:
    """`text` without the whitespace outside its strings."""

    kept: list[str] = []
    inside = escaped = False
    for char in text:
        if escaped:
            escaped = False
        elif inside:
            escaped = char == "\\"
            inside = char != '"'
        elif char == '"':
            inside = True
        elif char in " \t\n\r":
            continue
        kept.append(char)
    return "".join(kept)


@dataclass
class Settings:
    """A harness's JSON settings document as read and as planned: adopt keeps one entry in it
    and writes it back with its keys, their order and its indentation kept."""

    path: str
    before: bytes | None
    data: dict[str, Any]
    text: str = ""
    # Whether its non-ASCII text is escaped, as `rewritable` found it.
    ascii: bool = False
    changed: bool = False
    # Whether the file may go once it holds nothing: adopt created it.
    removable: bool = False

    @classmethod
    def parse(cls, path: str, before: bytes | None) -> Settings:
        if before is None:
            return cls(path, None, {})
        try:
            text = before.decode("utf-8")
            data = json.loads(text)
        except UnicodeDecodeError as error:
            raise AdoptError(f"{path} is not UTF-8 text") from error
        except ValueError as error:
            raise AdoptError(
                f"{path} is not plain JSON ({error}), and adopt refuses a document with "
                "comments; move them out, or leave --finish-check off"
            ) from error
        if not isinstance(data, dict):
            raise AdoptError(f"{path} is not a JSON object")
        return cls(path, before, data, text)

    def _ascii(self) -> bool:
        """Whether non-ASCII text is escaped; a refusal where a rewrite would change more than
        whitespace: a repeated key, an escape of another form, a number's form."""

        compact = _compact(self.text)
        for ascii in (False, True):
            if json.dumps(self.data, ensure_ascii=ascii, separators=(",", ":")) == compact:
                return ascii
        raise AdoptError(
            f"{self.path}: rewriting it would change more than its whitespace (a repeated key, "
            "an escape or a number's form); write those plainly, or leave --finish-check off"
        )

    def rewritable(self) -> Settings:
        """This document, refused where a rewrite would change more than its whitespace."""

        if self.before is not None:
            self.ascii = self._ascii()
        return self

    def hooks(self, create: bool = False) -> dict[str, Any]:
        if "hooks" not in self.data and create:
            self.data["hooks"] = {}
        hooks = self.data.get("hooks", {})
        if not isinstance(hooks, dict):
            raise AdoptError(f"{self.path}: its hooks key is not an object")
        return hooks

    def find(self, digest: str | None) -> Spot | None:
        """Where adopt's entry is: the one whose digest is `digest`, else the first that runs
        the finish check."""

        found = None
        for event, entries in self.hooks().items():
            for index, value in enumerate(entries if isinstance(entries, list) else []):
                if digest and sha256(finish_check.canonical(value)) == digest:
                    return event, index
                if found is None and finish_check.marked(value):
                    found = (event, index)
        return found

    def at(self, spot: Spot | None) -> bytes | None:
        return None if spot is None else finish_check.canonical(self.hooks()[spot[0]][spot[1]])

    def put(self, event: str, value: dict[str, Any], spot: Spot | None) -> None:
        """`value` at `spot`, else added last under `event`."""

        if spot is not None and spot[0] != event:
            self.take(spot)
            spot = None
        entries = self.hooks(create=True).setdefault(event, [])
        if not isinstance(entries, list):
            raise AdoptError(f"{self.path}: hooks.{event} is not a list")
        if spot is None:
            entries.append(value)
        elif entries[spot[1]] == value:
            return
        else:
            entries[spot[1]] = value
        self.changed = True

    def take(self, spot: Spot) -> None:
        """Remove the entry at `spot`, then the event list and the hooks object it emptied."""

        hooks = self.hooks()
        del hooks[spot[0]][spot[1]]
        if not hooks[spot[0]]:
            del hooks[spot[0]]
        if not hooks:
            del self.data["hooks"]
        self.changed = True

    def after(self) -> bytes | None:
        """The planned bytes: unchanged, deleted where adopt created it and it holds nothing, or
        rewritten in the document's own indentation, line ending and final newline."""

        if not self.changed:
            return self.before
        if self.removable and not self.data:
            return None
        indent = re.search(r"\n([ \t]+)\S", self.text)
        unit = indent.group(1) if indent else "  "
        text = json.dumps(self.data, indent=unit, ensure_ascii=self.ascii)
        text += "\n" if self.before is None or self.text.endswith("\n") else ""
        return text.replace("\n", "\r\n" if "\r\n" in self.text else "\n").encode("utf-8")


# --- The manifest ---------------------------------------------------------------


def _engine_skills() -> frozenset[str]:
    """Every skill this engine ships, which a fragment's `skills:` may add to an install, and
    every one it retired."""

    shipped = (path.parent.name for path in (ENGINE / "skills").glob("*/SKILL.md"))
    return frozenset((*SKILLS, *RETIRED_SKILLS, *shipped))


def _own(record: object) -> bool:
    """Whether a manifest record is adopt's; one of any other kind or id is kept as it is."""

    if not isinstance(record, dict):
        return False
    kind, name = record.get("kind"), record.get("id")
    return (
        (kind == "block" and name in (KERNEL, FACTS, POINTERS))
        or (kind == "skill" and isinstance(name, str) and name in _engine_skills())
        or (kind == "pointer" and isinstance(name, str) and name.startswith("pointer-"))
        or (
            kind == "fragment"
            and name != LOCAL
            and record.get("path") == f"{facts.FRAGMENT_DIR}/{name}.md"
        )
        or (kind == "ignore" and name == WORKSPACE and record.get("path") == WORKSPACE_IGNORE)
        or (kind == HOOK and name == FINISH_CHECK and isinstance(record.get("harness"), str))
    )


def _check_record(record: Record) -> None:
    path, digest = record.get("path"), record.get("sha256")
    if not (isinstance(path, str) and paths.admits(path)):
        raise AdoptError(f"{MANIFEST} records {path!r}, which is not a path inside the target")
    if not (
        isinstance(digest, str) and len(digest) == 64 and set(digest) <= set("0123456789abcdef")
    ):
        raise AdoptError(f"{MANIFEST} records no sha256 for {path}")
    for name in ("harnesses", "fragments", "done", "style"):
        value = record.get(name, [])
        if not (isinstance(value, list) and all(isinstance(item, str) for item in value)):
            raise AdoptError(f"{MANIFEST}: the {name} recorded for {path} are not a list of names")
    inputs = record.get("inputs", {})
    if not (isinstance(inputs, dict) and all(isinstance(v, str) for v in inputs.values())):
        raise AdoptError(f"{MANIFEST}: the inputs recorded for {path} are not paths and digests")
    if not isinstance(record.get("created", False), bool):
        raise AdoptError(
            f"{MANIFEST}: whether adopt created {path} is not recorded as true or false"
        )


@dataclass
class Manifest:
    """The target's manifest as read: adopt's own records apart from every other."""

    raw: bytes | None = None
    document: dict[str, Any] | None = None
    own: list[Record] = field(default_factory=list)
    foreign: list[Any] = field(default_factory=list)

    def after(self, version: str, records: list[Record]) -> bytes | None:
        """The manifest this run leaves: adopt's records, then every other record as read."""

        artifacts = [*records, *self.foreign]
        if not artifacts:
            return None
        kept: dict[str, Any] = {}
        if self.document is not None and self.document.get("format_version") == FORMAT_VERSION:
            kept = self.document
        document = {
            **kept,
            "format_version": FORMAT_VERSION,
            "engine_version": version,
            "artifacts": artifacts,
        }
        if document == self.document:
            return self.raw
        return (json.dumps(document, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def load_manifest(target: Path) -> Manifest:
    """Read the manifest; one of another format is refused, even under `--force`, and adopt's
    records are checked.

    `--force` cannot carry a manifest of another format forward: its records have another
    shape, so adopt would keep them beside its own for the same paths and the manifest would
    stop being true.
    """

    raw = _read(target, MANIFEST)
    if raw is None:
        return Manifest()
    try:
        document = json.loads(raw.decode("utf-8"))
    except ValueError as error:
        raise AdoptError(f"cannot read {MANIFEST}: {error}") from error
    if not isinstance(document, dict):
        raise AdoptError(f"{MANIFEST} is not a JSON object")
    if document.get("format_version") != FORMAT_VERSION:
        raise AdoptError(NOT_V2)
    artifacts = document.get("artifacts")
    if not isinstance(artifacts, list):
        raise AdoptError(f"{MANIFEST} has no artifacts list")
    own = [record for record in artifacts if _own(record)]
    for record in own:
        _check_record(record)
    return Manifest(raw, document, own, [record for record in artifacts if not _own(record)])


def recorded_harnesses(own: Sequence[Record]) -> list[str]:
    names = [
        name for record in own if record["kind"] == "skill" for name in record.get("harnesses", [])
    ]
    return list(dict.fromkeys(names))


def _recorded(own: Sequence[Record], name: str) -> list[str]:
    """The list `name` the facts record holds."""

    for record in own:
        if record["kind"] == "block" and record["id"] == FACTS:
            return list(record.get(name, []))
    return []


def recorded_fragments(own: Sequence[Record]) -> list[str]:
    return _recorded(own, "fragments")


def recorded_done(own: Sequence[Record]) -> list[str]:
    return _recorded(own, "done")


def recorded_style(own: Sequence[Record]) -> list[str]:
    """The recorded style for text a person reads; one this engine no longer knows reads none."""

    return [name for name in _recorded(own, "style") if name in facts.STYLES]


# --- One run, planned before anything is written --------------------------------


@dataclass
class Want:
    """One block or file adopt owns, as this run renders it."""

    kind: str
    path: str
    id: str
    data: bytes
    extra: dict[str, Any] = field(default_factory=dict)

    def key(self) -> tuple[str, str, str]:
        return self.kind, self.path, self.id

    def record(self) -> Record:
        return {
            "kind": self.kind,
            "path": self.path,
            "id": self.id,
            **self.extra,
            "sha256": sha256(self.data),
        }


@dataclass
class HookWant(Want):
    """A `hook` record's entry: the event it goes under and the entry as it is written; the
    record digests its canonical JSON, `data`."""

    event: str = ""
    entry: dict[str, Any] = field(default_factory=dict)


@dataclass
class Host:
    """A file adopt keeps blocks in: its bytes as read, and its text as planned."""

    before: bytes | None
    text: str

    def after(self) -> bytes | None:
        """The planned bytes; a host left empty by a removal is deleted."""

        if self.text or self.before == b"":
            return self.text.encode("utf-8")
        return None


class Run:
    """One install or removal, planned in memory before `fileplan.write` applies it."""

    def __init__(self, target: Path, force: bool) -> None:
        self.target = target
        self.force = force
        self.hosts: dict[str, Host] = {}
        self.settings: dict[str, Settings] = {}
        self.files: dict[str, tuple[bytes | None, bytes | None]] = {}
        self.records: list[Record] = []
        self.edited: list[str] = []
        self.notes: Notes = []

    def present(self, relative: str) -> bool:
        """Whether `relative` is in the target; a symlink counts whatever it points at, and so
        does a path behind a symlinked directory, which adopt cannot show absent."""

        path = self.target
        for part in relative.split("/"):
            path = path / part
            if path.is_symlink():
                return True
        return path.exists()

    def host(self, path: str) -> Host:
        if path not in self.hosts:
            data = _read(self.target, path)
            self.hosts[path] = Host(data, _host_text(path, data))
        return self.hosts[path]

    def document(self, path: str) -> Settings:
        if path not in self.settings:
            self.settings[path] = Settings.parse(path, _read(self.target, path)).rewritable()
        return self.settings[path]

    def loads(self, path: str) -> bool:
        """Whether harness file `path` loads AGENTS.md without adopt's import block."""

        link = self.target / path
        if link.is_symlink():
            if os.path.realpath(link) == os.path.realpath(self.target / AGENTS):
                return True
            raise AdoptError(
                f"{path} is a symlink that does not resolve to {AGENTS}, and adopt writes "
                f"through no symlink; point it at {AGENTS} or replace it with a file"
            )
        return _imports(cut(self.host(path).text, pointer_id(path)))

    def keep(self, want: Want, record: Record | None) -> None:
        """Install `want`: write it where absent, replace it where its record still holds."""

        if isinstance(want, HookWant):
            self._keep_hook(want, record)
        elif want.kind in FILE_KINDS:
            before = self._before(want.path)
            self._judge(want.path, before, want.data, record)
            self.files[want.path] = (before, want.data)
        else:
            host = self.host(want.path)
            current = block_text(host.text, want.id)
            if current is None and identity.has_unclosed_fence(host.text):
                raise AdoptError(
                    f"{want.path} ends inside an unclosed code fence; close it, then re-run"
                )
            self._judge(label(want.path, want.id), current, want.data, record)
            host.text = put(host.text, want.id, want.data.decode("utf-8"), AFTER.get(want.id))
        self.records.append(want.record())

    def _keep_hook(self, want: HookWant, record: Record | None) -> None:
        """Put the entry where adopt's is, else last under its event, recording whether adopt
        created the document."""

        settings = self.document(want.path)
        spot = settings.find(record["sha256"] if record else None)
        self._judge(label(want.path, want.id), settings.at(spot), want.data, record)
        settings.put(want.event, want.entry, spot)
        created = settings.before is None or bool(record and record.get("created"))
        want.extra["created"] = created

    def drop(self, record: Record) -> None:
        """Remove what `record` says adopt wrote; a path that is now a symlink is left alone."""

        path, name = record["path"], record["id"]
        if (self.target / path).is_symlink():
            return
        if record["kind"] == HOOK:
            self._drop_hook(record)
        elif record["kind"] in FILE_KINDS:
            before = self._before(path)
            self._judge(path, before, None, record)
            self.files[path] = (before, None)
        else:
            host = self.host(path)
            self._judge(label(path, name), block_text(host.text, name), None, record)
            host.text = cut(host.text, name)

    def _drop_hook(self, record: Record) -> None:
        """Take out the entry, what it emptied, and the document where adopt created it and it
        now holds nothing; one that no longer names the finish check is not parsed."""

        path = record["path"]
        data = self.settings[path].before if path in self.settings else _read(self.target, path)
        if data is None or finish_check.MARKER not in data:
            return
        settings = self.document(path)
        spot = settings.find(record["sha256"])
        self._judge(label(path, record["id"]), settings.at(spot), None, record)
        if spot is not None:
            settings.take(spot)
        settings.removable = settings.removable or bool(record.get("created"))

    def _before(self, path: str) -> bytes | None:
        return self.files[path][0] if path in self.files else _read(self.target, path)

    def _judge(
        self, name: str, current: bytes | None, wanted: bytes | None, record: Record | None
    ) -> None:
        """Note `name` as edited when its bytes are neither wanted nor what adopt recorded."""

        if current is None or current == wanted:
            return
        if record is None or sha256(current) != record["sha256"]:
            self.edited.append(name)

    def planned(self, manifest: Manifest, version: str) -> Planned:
        """Every change, the manifest last; a refusal when something edited is in the way."""

        if self.edited and not self.force:
            raise AdoptError(
                *(
                    f"{name} differs from what adopt wrote; restore it, or pass --force"
                    for name in self.edited
                )
            )
        pairs = dict(self.files)
        pairs.update((path, (host.before, host.after())) for path, host in self.hosts.items())
        pairs.update((path, (doc.before, doc.after())) for path, doc in self.settings.items())
        planned = {path: pair for path, pair in sorted(pairs.items()) if pair[0] != pair[1]}
        after = manifest.after(version, self.records)
        if after != manifest.raw:
            planned[MANIFEST] = (manifest.raw, after)
        return planned


def _above(target: Path, names: Sequence[str]) -> bool:
    """Whether a folder above `target` holds one of `names`, which stops the harness reading
    AGENTS.md there too. The person's own `~/.claude/CLAUDE.md` is user memory and does not."""

    home = Path.home().resolve()
    for folder in target.resolve().parents:
        for name in names:
            if folder == home and name == ".claude/CLAUDE.md":
                continue
            if (folder / name).exists():
                return True
    return False


def _unneeded(run: Run, host: str, sharing: Sequence[Route]) -> str | None:
    """Why `host` needs no import block, or None.

    It needs none when every harness routing through it shares one `reads_agents_md` rule
    and none of that rule's files is in the target or a folder above it: each then reads
    AGENTS.md itself.
    """

    rules = {(item.unless, item.since) for item in sharing}
    if len(rules) != 1:
        return None
    ((unless, since),) = rules
    if not unless or any(run.present(name) for name in unless) or _above(run.target, unless):
        return None
    harnesses = ", ".join(item.harness for item in sharing)
    return (
        f"{host} ({harnesses} {since} or later reads {AGENTS} itself: "
        f"the target has no {adapters.or_list(unless)})"
    )


def desired(
    run: Run,
    source: Path,
    found: Sequence[Route],
    ids: Sequence[str],
    done: Sequence[str],
    style: Sequence[str] = (),
) -> list[Want]:
    """What this engine installs for these harnesses, fragments and Done commands, in record
    order: the kernel, the facts, the pointers, the fragment files and the workspace's
    `.agents/.gitignore`, the imports, the skills.

    A host no harness needs (`_unneeded`) gets no import block, and a record of one is dropped
    without writing its file again. Claude Code's host, CLAUDE.md, is itself one of the files
    that make it need one, so an existing CLAUDE.md keeps its block.
    """

    wants = [Want("block", AGENTS, KERNEL, kernel_block(source).encode("utf-8"))]
    imports = _imports_needed(run, found)
    written = [want.path for want in imports]
    found_fragments = catalog(source, run.target, ids)
    made = guidance(run.target, found, found_fragments, ids, Chosen(done, style), written)
    extra = {"fragments": list(ids), "done": list(done), "inputs": made.rendered.inputs}
    if style:
        extra["style"] = list(style)
    wants.append(Want("block", AGENTS, FACTS, made.rendered.facts.encode("utf-8"), extra))
    if made.rendered.pointers is not None:
        wants.append(Want("block", AGENTS, POINTERS, made.rendered.pointers.encode("utf-8")))
    wants.extend(Want("fragment", path, Path(path).stem, data) for path, data in made.files.items())
    if WORKSPACE in ids:
        wants.append(Want("ignore", WORKSPACE_IGNORE, WORKSPACE, workspace_ignore(source)))
    run.notes.extend(("UNVERIFIED", text) for text in made.rendered.unverified)
    wants.extend(imports)
    if any(item.harness == GENERIC for item in found):
        run.notes.append(("UNVERIFIED", f"{GENERIC}: that the harness reads {AGENTS}"))
    wants.extend(_skills(source, found, made.skills))
    return wants


def _imports_needed(run: Run, found: Sequence[Route]) -> list[Want]:
    """The `@AGENTS.md` import block each harness host needs, none where it is `_unneeded`."""

    hosts: dict[str, list[Route]] = {}
    for item in found:
        if item.host is not None:
            hosts.setdefault(item.host, []).append(item)
    wants = []
    for host, sharing in sorted(hosts.items()):
        unneeded = _unneeded(run, host, sharing)
        if unneeded is not None:
            run.notes.append(("skip", unneeded))
        elif not run.loads(host):
            wants.append(Want("pointer", host, pointer_id(host), pointer_block(host).encode()))
    return wants


def _skills(source: Path, found: Sequence[Route], names: Sequence[str]) -> list[Want]:
    """Each skill once per skill directory, recording the harnesses that read it there."""

    roots: dict[str, list[str]] = {}
    for item in found:
        roots.setdefault(item.skills, []).append(item.harness)
    wants = []
    for name in names:
        for relative, data in skill_files(source, name).items():
            for root, harnesses in roots.items():
                path = f"{root}/{name}/{relative}"
                wants.append(Want("skill", path, name, data, {"harnesses": sorted(harnesses)}))
    return sorted(wants, key=lambda want: want.path)


def finish_hooks(
    run: Run,
    table: dict[str, Any],
    found: Sequence[Route],
    done: Sequence[str],
    asked: bool | None,
    recorded: bool,
) -> list[Want]:
    """The finish-check entry for each selected harness whose row has a `finish_hook`, while the
    person asked for it (`asked`; None keeps what the manifest `recorded`), each other selected
    harness named as not available yet. Asked for without Done, or where no selected harness
    has one, it is refused; an install that empties Done removes it."""

    if not (recorded if asked is None else asked):
        return []
    if asked and not done:
        raise AdoptError(
            "--finish-check runs the Done commands, and none is recorded; record one with --done"
        )
    hooks = [(item.harness, finish_check.hook_of(table.get(item.harness))) for item in found]
    missing = [
        f"{name} finish-check: not available yet: {finish_check.unavailable(name)}"
        for name, hook in hooks
        if hook is None
    ]
    if asked and len(missing) == len(hooks):
        rows = [name for name, row in sorted(table.items()) if finish_check.hook_of(row)]
        raise AdoptError(*missing, f"--finish-check is available for {', '.join(rows)}")
    run.notes.extend(("skip", text) for text in missing)
    if not done:
        run.notes.append(("skip", "finish-check: Done is now empty, so its entry is taken out"))
        return []
    digest = finish_check.done_digest(done)
    wants: list[Want] = []
    for name, hook in hooks:
        if hook is None:
            continue
        if not paths.admits(hook.get("file")):
            raise AdoptError(f"{name}: the harness table names no settings file inside the target")
        entry = finish_check.entry(name, digest)
        data = finish_check.canonical(entry)
        extra = {"harness": name}
        wants.append(HookWant(HOOK, hook["file"], FINISH_CHECK, data, extra, hook["event"], entry))
        caution = f"; {finish_check.CAUTION[name]}" if name in finish_check.CAUTION else ""
        run.notes.append(
            (
                "UNVERIFIED",
                f"{name} finish-check: that the harness runs the hook, until a person sees its "
                f"PASS message end a run; the one-time accept: {hook['accept']}, and "
                "`outcomebound` on the harness process's PATH, which a harness launched from a "
                f"desktop may not share with the shell{caution}",
            )
        )
    return wants


def require_work_tree(target: Path) -> None:
    """Refuse a target Git cannot undo: no `.git` at or above it, or inside `.git` itself."""

    inside = any((directory / ".git").exists() for directory in (target, *target.parents))
    if not inside or any(paths.names_git(part) for part in target.parts):
        raise AdoptError(f"{target} is not inside a Git work tree, and Git is adopt's undo")


def description(skill: bytes) -> str:
    """A SKILL.md's `description:`, the line a harness lists; empty where it has none."""

    text = skill.decode("utf-8", errors="replace")
    head = text.split("\n---\n", 1)[0] if text.startswith("---\n") else ""
    found = [line for line in head.splitlines() if line.startswith("description:")]
    return found[0].removeprefix("description:").strip() if found else ""


def footprint(wants: Sequence[Want]) -> tuple[str, str]:
    """The words an agent always loads from this install, and their sum: each block adopt keeps
    where it is loaded, and each skill's description, which a harness lists at every session.

    Words are whitespace-separated, sentinels included, as the file holds them. The figure
    is reported beside the install and never refuses one.
    """

    counts = [
        (label(want.path, want.id), len(want.data.decode("utf-8").split()))
        for want in wants
        if want.kind in ("block", "pointer")
    ]
    described = {
        want.id: len(description(want.data).split())
        for want in wants
        if want.kind == "skill" and want.path.endswith("/SKILL.md")
    }
    if described:
        counts.append(("skill descriptions", sum(described.values())))
    listed = ", ".join(f"{name} {count}" for name, count in counts)
    return "words", f"{sum(count for _, count in counts)} always loaded: {listed}"


@dataclass(frozen=True)
class Selection:
    """What an install is asked for; `None` keeps what the manifest records, and no harness
    at all is `generic`."""

    harnesses: list[str] | None = None
    fragments: list[str] | None = None
    done: list[str] | None = None
    finish_check: bool | None = None
    style: list[str] | None = None


def install(
    target: Path, source: Path, selection: Selection, force: bool
) -> tuple[Planned, list[str], Notes]:
    """Plan an install or upgrade."""

    require_work_tree(target)
    manifest = load_manifest(target)
    own = manifest.own
    names = recorded_harnesses(own) if selection.harnesses is None else selection.harnesses
    found = routes(source, names or [GENERIC])
    ids = recorded_fragments(own) if selection.fragments is None else selection.fragments
    done = recorded_done(own) if selection.done is None else selection.done
    style = recorded_style(own) if selection.style is None else selection.style
    run = Run(target, force)
    wants = desired(run, source, found, ids, done, style)
    hooked = any(record["kind"] == HOOK for record in own)
    table = harness_table(source)
    wants += finish_hooks(run, table, found, done, selection.finish_check, hooked)
    recorded = {(record["kind"], record["path"], record["id"]): record for record in manifest.own}
    for want in wants:
        run.keep(want, recorded.pop(want.key(), None))
    for record in recorded.values():
        run.drop(record)
    run.notes.append(footprint(wants))
    return run.planned(manifest, engine_version(source)), run.edited, run.notes


def remove(target: Path, source: Path, force: bool) -> tuple[Planned, list[str], Notes]:
    """Plan removing every block and file adopt recorded; other records stay."""

    require_work_tree(target)
    manifest = load_manifest(target)
    run = Run(target, force)
    for record in manifest.own:
        run.drop(record)
    return run.planned(manifest, engine_version(source)), run.edited, run.notes


# --- Read-only verbs ------------------------------------------------------------


def _observed(target: Path, record: Record) -> bytes | None:
    data = _read(target, record["path"])
    if record["kind"] == HOOK:
        if data is None or finish_check.MARKER not in data:
            return None
        settings = Settings.parse(record["path"], data)
        return settings.at(settings.find(record["sha256"]))
    if record["kind"] in FILE_KINDS or data is None:
        return data
    return block_text(_host_text(record["path"], data), record["id"])


def recomputed(target: Path, source: Path, own: Sequence[Record]) -> Guidance:
    """The facts and pointers the recorded selection gives against today's sources."""

    ids = recorded_fragments(own)
    found = routes(source, recorded_harnesses(own) or [GENERIC])
    chosen = Chosen(recorded_done(own), recorded_style(own))
    return guidance(target, found, catalog(source, target, ids), ids, chosen)


def _rendered(target: Path, source: Path, record: Record, own: Sequence[Record]) -> bytes:
    kind, name = record["kind"], record["id"]
    if kind == "skill":
        relative = str(record["path"]).split(f"/{name}/", 1)[-1]
        files = skill_files(source, name)
        if relative not in files:
            raise AdoptError(f"this engine ships no {relative} in the {name} skill")
        return files[relative]
    if kind == "ignore":
        return workspace_ignore(source)
    if kind == "fragment":
        shipped = catalog(source, target, []).get(name)
        if shipped is None:
            raise AdoptError(f"this engine ships no {name} fragment")
        return _fragment_bytes(shipped)
    if kind == "pointer":
        return pointer_block(record["path"]).encode("utf-8")
    if kind == HOOK:
        return _hook_rendered(source, record, own)
    if name == KERNEL:
        return kernel_block(source).encode("utf-8")
    rendered = recomputed(target, source, own).rendered
    block = {FACTS: rendered.facts, POINTERS: rendered.pointers}.get(name)
    if block is None:
        raise AdoptError(f"this engine renders no {name} block for the recorded selection")
    return block.encode("utf-8")


def _hook_rendered(source: Path, record: Record, own: Sequence[Record]) -> bytes:
    """The entry this engine writes for the record's harness and the recorded Done."""

    harness, done = record["harness"], recorded_done(own)
    hook = finish_check.hook_of(harness_table(source).get(harness))
    if hook is None or hook.get("file") != record["path"] or not done:
        raise AdoptError(
            f"this engine writes no finish-check entry for {harness} at {record['path']}"
        )
    return finish_check.canonical(finish_check.entry(harness, finish_check.done_digest(done)))


def state(target: Path, source: Path, record: Record, own: Sequence[Record]) -> str:
    """`current`, `edited` (not what adopt wrote), `stale` (the engine now renders it
    differently, or no longer renders it) or `missing`; `own` is every record adopt holds,
    which the facts and pointers are recomputed from."""

    try:
        observed = _observed(target, record)
    except AdoptError:
        return "edited"
    if observed is None:
        return "missing"
    if sha256(observed) != record["sha256"]:
        return "edited"
    try:
        rendered = _rendered(target, source, record, own)
    except AdoptError:
        return "stale"
    return "current" if sha256(rendered) == record["sha256"] else "stale"


def moved(target: Path, source: Path, record: Record, own: Sequence[Record]) -> str:
    """Which facts moved in a stale facts block, and which of its recorded sources changed."""

    try:
        observed = (_observed(target, record) or b"").decode("utf-8")
        rendered = recomputed(target, source, own).rendered
    except (AdoptError, UnicodeDecodeError):
        return ""
    labels = facts.moved(observed, rendered.facts)
    before, after = record.get("inputs", {}), rendered.inputs
    changed = sorted(path for path in {*before, *after} if before.get(path) != after.get(path))
    parts = [f"{', '.join(labels)} moved"] if labels else []
    parts += [f"{', '.join(changed)} changed"] if changed else []
    return "; ".join(parts)


def next_step(target: Path, found: Sequence[str]) -> str | None:
    """The command that makes every record current, for a person who did not install; None
    where each already is. An edited record is refused without `--force`, which would replace
    the edit, so the edit is moved out first."""

    command = f"outcomebound adopt {shlex.quote(str(target))}"
    if "edited" in found:
        return (
            "next: move each edit out of OutcomeBound's blocks and files, then "
            f"{command} --force makes every record current"
        )
    if any(state != "current" for state in found):
        return f"next: {command} makes every record current"
    return None


def check(target: Path, source: Path) -> int:
    manifest = load_manifest(target)
    if manifest.raw is None:
        print(f"missing  {MANIFEST}")
        command = f"outcomebound adopt {shlex.quote(str(target))} --detect"
        print(f"next: {command} prints the command that installs OutcomeBound here")
        return 1
    found: list[str] = []
    for record in manifest.own:
        found.append(state(target, source, record, manifest.own))
        name = None if record["kind"] in FILE_KINDS else record["id"]
        detail = ""
        if found[-1] == "stale" and record["id"] == FACTS and record["kind"] == "block":
            detail = moved(target, source, record, manifest.own)
        print(f"{found[-1]:<8} {label(record['path'], name)}" + (f": {detail}" if detail else ""))
    step = next_step(target, found)
    if step is not None:
        print(step)
    return min(sum(state != "current" for state in found), CHECK_CAP)


def proposed_done(target: Path) -> list[str]:
    """What `--detect` proposes for Done, in run order: the floor's runner where a floor is
    installed, then the first test command the project's CI runs, as the CI test fact reads it,
    or, where CI names none, the first check command discovery offers for the target's root."""

    try:
        floor = paths.read_bounded(target, facts.FLOOR)
    except paths.PathError:
        floor = None
    done = [FLOOR_RUNNER] if floor is not None else []
    ci = [command for item in facts.read_ci(target) for command in item.tests]
    if ci:
        return [*done, ci[0]]
    try:
        components = discovery.discover(target)["inferred"]["components"]
    except (discovery.DiscoveryError, OSError):
        components = []
    roots = [item["check_candidates"] for item in components if item["root"] == "."]
    return done + [candidates[0]["command"] for candidates in roots if candidates]


def detect(target: Path, source: Path) -> int:
    """Print the one install command this target's files suggest; write nothing. A target the
    install would refuse, outside a Git work tree, is refused here first."""

    require_work_tree(target)
    try:
        ids = fragments.detect(target, fragments.load_all(source))
    except fragments.FragmentError as error:
        raise AdoptError(str(error)) from error
    found = [harness for sign, harness in HARNESS_SIGNS if os.path.lexists(target / sign)]
    harnesses = ",".join(dict.fromkeys(found)) if found else GENERIC
    words = ["outcomebound", "adopt", str(target), "--harness"]
    words.append(harnesses)
    if ids:
        words += ["--fragments", ",".join(ids)]
    for command in proposed_done(target):
        words += ["--done", command]
    line = " ".join(map(shlex.quote, words))
    if not found:
        line += (
            f"  # no harness file found; or one of: {', '.join(loadable(harness_table(source)))}"
        )
    print(line)
    return 0


# --- Command line ---------------------------------------------------------------

USAGE = """outcomebound adopt <target> [--harness H[,H]]... [--fragments IDS] [--done CMD]...
                            [--human-style ste] [--finish-check | --no-finish-check]
                            [--dry-run] [--force]
       outcomebound adopt <target> --detect | --check
       outcomebound adopt <target> --remove [--dry-run] [--force]"""
DESCRIPTION = """\
Install or upgrade OutcomeBound in <target>, inside a Git work tree. AGENTS.md gets three
blocks: the operating contract; the project facts (Done: the --done commands; CI test: the test
command a GitHub Actions or GitLab CI file runs, read without running anything; Irreversible
edges: those the selected fragments declare, and a floor loosening where a floor is installed;
Text for people: with --human-style ste, text an agent writes for a person in the style of
ASD-STE100 Simplified Technical English; Precedence); and the guidance pointers: the local
fragment inline, then one line per fragment in --fragments, copied under
.outcomebound/fragments/, and per skill: the core skills, and those a selected fragment names,
such as the tickets fragment's slice-tickets. The workspace fragment also gets
.agents/.gitignore, which keeps its four folders out of Git. A fact it cannot observe is left
out, and the install report names it UNVERIFIED. Each harness gets the skills, and an @AGENTS.md
import block in each harness file that needs one: none where the harness reads AGENTS.md itself,
as Claude Code 2.1.281 and later does where the target has no CLAUDE.md, .claude/CLAUDE.md or
CLAUDE.local.md. generic, the default where no harness is named, serves a harness the table does
not list: its skills go under .outcomebound/skills/, and any other unlisted name is refused.
What it writes is recorded in .outcomebound/manifest.json; re-running it upgrades. An install
prints the words an agent always loads, skill descriptions included, and no size refuses one. It
refuses a harness that cannot be made to load AGENTS.md and, without --force, to replace or
remove a block or file whose bytes are not what it recorded. A refusal writes nothing.

--finish-check adds one entry to the settings of each selected harness that has a finish hook,
claude-code (.claude/settings.json) and codex (.codex/hooks.json): when that harness's agent
ends a turn on a working tree the Done commands have not passed on, `outcomebound finish-check`
runs them, and a failure goes back to the agent to fix. It needs a Done command. The install
report names each harness's one-time accept, reads UNVERIFIED that the harness runs the hook
until a person sees its PASS message end a run, and names each other selected harness as not
available yet. adopt writes the document back with its keys, their order and its indentation
kept, rewriting only its whitespace, and refuses one with comments. A Done change rewrites the
entry; --no-finish-check or --remove takes it out."""
EPILOG = """\
exit: 0 done, 1 refused or failed, 2 usage; --check exits with the number of records that are
not current, at most 100."""


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="outcomebound adopt",
        usage=USAGE,
        description=DESCRIPTION,
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("target", help="the repository to install into")
    verb = parser.add_mutually_exclusive_group()
    verb.add_argument(
        "--detect", action="store_true", help="print the install command; write nothing"
    )
    verb.add_argument(
        "--check",
        action="store_true",
        help="print current, edited, stale or missing for each record, then the command that "
        "makes each current; write nothing",
    )
    verb.add_argument("--remove", action="store_true", help="remove every recorded block and file")
    finish = parser.add_mutually_exclusive_group()
    finish.add_argument(
        "--finish-check",
        dest="finish_check",
        action="store_const",
        const=True,
        help="run the Done commands at the stop hook of claude-code and codex; omitted keeps "
        "the recorded choice",
    )
    finish.add_argument(
        "--no-finish-check",
        dest="finish_check",
        action="store_const",
        const=False,
        help="take the finish check's entries out",
    )
    parser.add_argument(
        "--harness",
        action="append",
        metavar="H[,H]",
        help="harnesses to install for; repeats add up; omitted keeps the recorded ones",
    )
    parser.add_argument(
        "--fragments",
        metavar="IDS",
        help="fragment ids to point at, 'local' inline; '' for none; omitted keeps the recorded",
    )
    parser.add_argument(
        "--done",
        action="append",
        metavar="CMD",
        help="a command that settles done, in run order; repeats add up; '' for none; "
        "omitted keeps the recorded ones",
    )
    parser.add_argument(
        "--human-style",
        choices=(*facts.STYLES, ""),
        metavar="STYLE",
        help="a style for text an agent writes for a person: 'ste' (ASD-STE100 Simplified "
        "Technical English); '' for none; omitted keeps the recorded one",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="print what would change; write nothing"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="replace or remove edited blocks and files; a manifest of another format is "
        "refused even so",
    )
    return parser


def _names(values: Sequence[str] | None) -> list[str] | None:
    if values is None:
        return None
    return list(
        dict.fromkeys(name.strip() for value in values for name in value.split(",") if name.strip())
    )


def _commands(values: Sequence[str]) -> list[str]:
    """The --done commands, each one line; an empty one records none."""

    commands = [value.strip() for value in values if value.strip()]
    for command in commands:
        if "\n" in command or "\r" in command or "<!--" in command:
            raise AdoptError(f"a --done command is one line with no comment opener: {command!r}")
    return commands


def _report(planned: Planned, edited: Sequence[str], notes: Notes) -> None:
    for name in edited:
        print(f"edited   {name}: overridden by --force")
    for path, (before, after) in planned.items():
        verb = "create" if before is None else "delete" if after is None else "update"
        print(f"{verb:<8} {path}")
    if not planned:
        print("nothing to change")
    for verb, text in notes:
        print(f"{verb:<8} {text}")


def _run(args: argparse.Namespace, target: Path, source: Path) -> int:
    if args.detect:
        return detect(target, source)
    if args.check:
        return check(target, source)
    if args.remove:
        planned, edited, notes = remove(target, source, args.force)
    else:
        selection = Selection(
            _names(args.harness),
            None if args.fragments is None else _names([args.fragments]),
            None if args.done is None else _commands(args.done),
            args.finish_check,
            None if args.human_style is None else [args.human_style] if args.human_style else [],
        )
        planned, edited, notes = install(target, source, selection, args.force)
    if args.dry_run:
        _report(planned, edited, notes)
        print("dry run: nothing written")
        return 0
    fileplan.write(
        target,
        {path: after for path, (_, after) in planned.items()},
        {path: before for path, (before, _) in planned.items()},
    )
    _report(planned, edited, notes)
    return 0


def main(argv: Sequence[str] | None = None, *, source: Path = ENGINE) -> int:
    """The command line; `source` is the engine checkout whose files are rendered."""

    parser = _parser()
    args = parser.parse_args(argv)
    if (args.detect or args.check) and (args.dry_run or args.force):
        parser.error("--dry-run and --force apply to an install and to --remove")
    chosen = args.harness or args.fragments is not None or args.done is not None
    chosen = chosen or args.human_style is not None
    if (args.detect or args.check or args.remove) and (chosen or args.finish_check is not None):
        parser.error(
            "--harness, --fragments, --done, --human-style and --finish-check apply to an install"
        )
    target = Path(args.target).resolve()
    try:
        if not target.is_dir():
            raise AdoptError(f"not a directory: {args.target}")
        return _run(args, target, Path(source))
    except AdoptError as error:
        reasons: Sequence[str] = error.reasons
    except (fileplan.WriteError, OSError) as error:
        reasons = [str(error)]
    for reason in reasons:
        print(f"adopt: {reason}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
