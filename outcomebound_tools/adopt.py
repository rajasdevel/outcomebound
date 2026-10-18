"""Install, upgrade, check and remove OutcomeBound in one target repository.

`adopt <target>` writes three blocks into the target's AGENTS.md: the
operating contract; the project facts the engine observes or the adopter records
(`outcomebound_tools.facts`); and the guidance pointers, the project's own `local`
fragment inline and then one line per selected fragment, copied under
`.outcomebound/fragments/`, and per skill in `SKILLS`. Selecting the workspace fragment also
installs `.agents/.gitignore`, which keeps its four folders out of Git; every install writes
`.outcomebound/.gitignore`, which keeps OutcomeBound's own local records out of Git. The install
report warns where Git ignores a path the install owns, where AGENTS.md holds changes not
committed, and where a harness also loads instructions from a folder above the target.
`--detect` prints the install command on its first line and every note after it on a line that
starts with `#`. It installs no hook and runs no Done command
(`docs/specs/finish-check/design.md`); a `hook` record that 1.6.0 or earlier wrote is dropped by
the install, its entry taken out of the settings document with the document's other keys, their
order and its indentation kept. It installs each skill for
every harness, and an `@AGENTS.md` import into each harness file that would not load
AGENTS.md otherwise: none where the harness table says the harness reads AGENTS.md
itself unless one of its files exists, and none exists. A harness outside
the table is `generic`, the default: its skills go under `.outcomebound/skills/`,
which the pointers name. Re-running it is the upgrade, and each install prints the
words an agent always loads, skill descriptions included; no size refuses one. What it
wrote is recorded in `.outcomebound/manifest.json` (format 2), one
`{kind, path, id, sha256}` record per block or file, the facts record holding the recorded
selection, the Done and Setup commands and each source a fact was read from with its digest, and the
pointers record the optional `frame` digest that shows an edit of the local fragment alone; a
record of any other kind or id belongs to another route and is kept as it is. Nothing whose
bytes differ from its record is replaced or removed without `--force`, save bytes this
install writes itself, which are no person's edit and are recorded as they are, and a pointers
block that is the recorded render with only the local fragment's own edit in it. Git is the
undo, so the target must be inside a Git work tree, and every write goes through
`fileplan.write` with the manifest last.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
from collections.abc import Callable, Sequence, Set
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from outcomebound_tools import (
    adapters,
    adopt_worktrees,
    discovery,
    drift,
    facts,
    fileplan,
    finish_check,
    fragments,
    home,
    identity,
    instruction_audit,
    paths,
    programs,
    textio,
    walk,
)
from outcomebound_tools.gitenv import GIT_READ_CONFIGURATION, git_environment
from outcomebound_tools.tickets_claims import load_claims, placement
from outcomebound_tools.tickets_declaration import load_declaration
from outcomebound_tools.tickets_report import EngineError, Refusal

ENGINE = home.ROOT
MANIFEST = ".outcomebound/manifest.json"
FORMAT_VERSION = 2
# Stands in for the local fragment's inline text in the pointers record's `frame` digest; no
# fragment's text holds a NUL.
FRAME_MARK = "\0local\0"
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
    "tests-worth-keeping": (
        "when writing, changing or judging a test, or when the project's tests already fail before "
        "you begin"
    ),
    "diagnose": "when a failure's cause is unknown, or a fix did not hold",
    "review-findings": "when acting on review findings, or writing a review the project requires",
    "explain-spec": (
        "when a person must act on a spec they did not write, or says they do not follow it"
    ),
    "slice-tickets": "when breaking work into tickets",
    "hand-off-tickets": (
        "when handing an accepted ticket from the ticket store to the agent or model that will "
        "build it"
    ),
    "explorable": (
        "when the person asks for an interactive page, wants to try options with their own "
        "numbers, or must learn a mechanism by trying it"
    ),
    "land-change": "when driving a pull or merge request through CI and review to landing",
    "run-acceptance": (
        "when preparing, running or recording acceptance of a delivered change by a person "
        "outside the build"
    ),
    "sync-tracker": (
        "when reading a card from a tracker that is not the project's ticket store, "
        "or writing back to it"
    ),
}
# Skills an earlier install carried and this engine no longer ships. A record of one is still
# adopt's, so `--check` reads its files stale and the next install removes them.
RETIRED_SKILLS: tuple[str, ...] = ()
FILE_KINDS = ("skill", "fragment", "ignore")
# The flags of 1.6.0 and earlier for the finish check, in the order a note names them.
RETIRED_FLAGS = (
    "--finish-check",
    "--no-finish-check",
    "--finish-timeout",
    "--verify",
    "--done-skip",
)
# One entry in a harness's JSON settings document, recorded by the entry's canonical digest.
# 1.6.0 and earlier wrote these records for the finish check; this engine writes none, and drops
# the ones it finds with the entry each names.
HOOK = "hook"
FINISH_CHECK = finish_check.ID
# The record of the turn-start entry written beside the finish check's own.
FINISH_MARK = f"{finish_check.ID}-mark"
# The workspace fragment's folders stay out of Git: selecting it installs this file too.
WORKSPACE = "workspace"
WORKSPACE_IGNORE = ".agents/.gitignore"
WORKSPACE_TEMPLATE = "templates/workspace.gitignore"
# OutcomeBound's own local records stay out of Git: every install writes this file whole.
# `research ingest` writes its inbox here, and `validation` writes its logs beside the plan file,
# a plan under `.outcomebound/` included.
LOCAL_RECORDS = "local-records"
LOCAL_IGNORE = ".outcomebound/.gitignore"
LOCAL_IGNORE_TEXT = (
    b"# OutcomeBound's local records: written on this machine, never committed. adopt writes this\n"
    b"# file whole; put any other ignore in the root .gitignore.\n"
    b"/research-inbox/\n"
    b".outcomebound-checks/\n"
)
# A harness outside the harness table: the skills go where the pointers name them.
GENERIC = "generic"
GENERIC_SKILLS = ".outcomebound/skills"
KERNEL_TEMPLATE = "templates/managed-block.agents.md.tmpl"
LOCAL = facts.LOCAL
LOCAL_FRAGMENT = f"{facts.FRAGMENT_DIR}/{LOCAL}.md"
# What --detect names last, and where a new project starts, as paths in the engine.
GUIDE = "skills/adopt-outcomebound/SKILL.md"
NEW_PROJECT_REFERENCE = "skills/using-outcomebound/references/new-project.md"
# Where the engine holds the scaffold's sets, --detect names its preview on an empty repository.
SCAFFOLD_MANIFEST = "templates/scaffold/scaffold.json"
# What --detect proposes first for Done where a floor is installed: the floor's runner, with
# `--base` the remote's default branch where Git resolves it (`default_base`).
FLOOR_RUNNER = "outcomebound floor check ."
FALLBACK_BASE = "origin/main"
# The import block's body never changes, so its version does not follow the
# engine's: an upgrade never rewrites a harness file the adopter owns.
POINTER_VERSION = "1.0.0"
CHECK_CAP = 100
# Files in a target that name the harness it uses, for `--detect`.
HARNESS_SIGNS = (
    ("CLAUDE.md", "claude-code"),
    (".claude", "claude-code"),
    (".codex", "codex"),
    (".cursor", "cursor"),
    ("GEMINI.md", "gemini"),
    (".gemini", "gemini"),
)
NOT_V2 = f"{MANIFEST} is not a format 2 manifest; remove the install that wrote it, then re-run"
# A block or file whose bytes differ from its record but are what this engine writes.
UNRECORDED = (
    "differs from its record, but is what this engine writes, so it is no edit; "
    "adopt records it without --force"
)
# A pointers block whose bytes differ from its record only by the local fragment's own edit.
FROM_SOURCE = (
    f"differs from its record only by the edit in {LOCAL_FRAGMENT}, as the release that wrote "
    "the record renders it, so it is no edit; adopt renders it again without --force"
)

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
            f"copy {(source / 'templates/fragment-local.md').as_posix()} there and edit it"
        )
    try:
        fragment = fragments.parse_fragment(textio.decode(data), LOCAL_FRAGMENT)
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


Chosen = facts.Chosen


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
    names = fragments.SKILLS
    skills = [
        (CONDITIONS.get(name, f"when the {name} skill applies"), f"{root}/{name}/SKILL.md")
        for name in names
    ]
    hosts = [AGENTS, *sorted({item.host for item in found if item.host})]
    hosts = [h for h in hosts if h in (AGENTS, *importing) or os.path.lexists(target / h)]
    skills = skills if root else []
    rendered = facts.render_chosen(target, selected, chosen, hosts, skills)
    return Guidance(rendered, files, names)


def _fragment_bytes(fragment: fragments.Fragment) -> bytes:
    if fragment.path is None:
        raise AdoptError(f"the {fragment.id} fragment has no file to install")
    try:
        return textio.fold(fragment.path.read_bytes())
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
        return textio.fold((source / "skills" / name / relative).read_bytes())
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
        text = "" if data is None else textio.universal(textio.decode(data))
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
    """A harness's JSON settings document as read and as planned: adopt takes out the entries an
    earlier version wrote and writes it back with its keys, their order and its indentation
    kept."""

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
            text = textio.decode(before)
            data = json.loads(text)
        except UnicodeDecodeError as error:
            raise AdoptError(f"{path} is not UTF-8 text") from error
        except ValueError as error:
            raise AdoptError(
                f"{path} is not plain JSON ({error}), and adopt refuses a document with "
                "comments; remove OutcomeBound's finish-check entry from it by hand, then run "
                "adopt again"
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
            "an escape or a number's form); remove OutcomeBound's finish-check entry from it by "
            "hand, then run adopt again"
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

    def find(self, digest: str | None, mark: bool = False) -> Spot | None:
        """Where adopt's entry is: the one whose digest is `digest`, else the first that runs
        the finish check at the stop, or with `mark` at the turn's start."""

        found = None
        for event, entries in self.hooks().items():
            for index, value in enumerate(entries if isinstance(entries, list) else []):
                if digest and sha256(finish_check.canonical(value)) == digest:
                    return event, index
                if found is None and finish_check.marked(value, mark):
                    found = (event, index)
        return found

    def at(self, spot: Spot | None) -> bytes | None:
        return None if spot is None else finish_check.canonical(self.hooks()[spot[0]][spot[1]])

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
        data = text.replace("\n", "\r\n" if "\r\n" in self.text else "\n").encode("utf-8")
        return textio.UTF8_BOM + data if (self.before or b"").startswith(textio.UTF8_BOM) else data


# --- The manifest ---------------------------------------------------------------


def _engine_skills() -> frozenset[str]:
    """Every skill this engine ships and every one it retired."""

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
        or (kind == "ignore" and name == LOCAL_RECORDS and record.get("path") == LOCAL_IGNORE)
        or (
            kind == HOOK
            and name in (FINISH_CHECK, FINISH_MARK)
            and isinstance(record.get("harness"), str)
        )
    )


def _check_record(record: Record) -> None:
    path, digest = record.get("path"), record.get("sha256")
    if not (isinstance(path, str) and paths.admits(path)):
        raise AdoptError(f"{MANIFEST} records {path!r}, which is not a path inside the target")
    if not (
        isinstance(digest, str) and len(digest) == 64 and set(digest) <= set("0123456789abcdef")
    ):
        raise AdoptError(f"{MANIFEST} records no sha256 for {path}")
    for name in ("harnesses", "fragments", "done", "setup", "style"):
        value = record.get(name, [])
        if not (isinstance(value, list) and all(isinstance(item, str) for item in value)):
            raise AdoptError(f"{MANIFEST}: the {name} recorded for {path} are not a list of names")
    inputs = record.get("inputs", {})
    if not (isinstance(inputs, dict) and all(isinstance(v, str) for v in inputs.values())):
        raise AdoptError(f"{MANIFEST}: the inputs recorded for {path} are not paths and digests")
    frame = record.get("frame")
    if frame is not None and not (
        isinstance(frame, str) and len(frame) == 64 and set(frame) <= set("0123456789abcdef")
    ):
        raise AdoptError(f"{MANIFEST}: the frame recorded for {path} is not a sha256")
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
        text = json.dumps(document, indent=2, ensure_ascii=False) + "\n"
        return textio.with_style(text.encode("utf-8"), self.raw)


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
        document = json.loads(textio.decode(raw))
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
    names = (
        name for record in own if record["kind"] == "skill" for name in record.get("harnesses", [])
    )
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


def recorded_setup(own: Sequence[Record]) -> list[str]:
    """The Setup commands the facts record holds, in run order; a record written before Setup
    existed holds none."""

    return _recorded(own, "setup")


def recorded_style(own: Sequence[Record]) -> list[str]:
    """The recorded style for text a person reads; one this engine no longer knows reads none."""

    return [name for name in _recorded(own, "style") if name in facts.STYLES]


# --- An edit of the local fragment alone ----------------------------------------


def framing(block: str, inline: str | None) -> str | None:
    """`block` with the local fragment's `inline` text, where it first stands, replaced by
    `FRAME_MARK`; None where there is no inline text, the block does not hold it, or the block
    already holds the mark."""

    if not inline or inline not in block or FRAME_MARK in block:
        return None
    return block.replace(inline, FRAME_MARK, 1)


def from_source(
    target: Path,
    current: bytes | None,
    record: Record | None,
    inline: str | None,
) -> bool:
    """Whether a pointers block whose bytes differ from its record is the recorded render with
    only the local fragment's inline text changed to `inline`, the fragment as it is now: the
    source's edit, rendered by the release that wrote the record, and no person's edit.

    A record with a `frame` decides it by that digest. A record without one, as an engine of
    1.1.1 or earlier writes it, has each earlier text of the local fragment that the target's
    Git history holds put in place of `inline`, and one that gives the record's digest decides
    it."""

    if current is None or record is None or record["kind"] != "block" or record["id"] != POINTERS:
        return False
    try:
        framed = framing(current.decode("utf-8"), inline)
    except UnicodeDecodeError:
        return False
    if framed is None:
        return False
    if "frame" in record:
        return sha256(framed.encode("utf-8")) == record["frame"]
    for text in local_history(target):
        try:
            earlier = fragments.parse_fragment(text, LOCAL_FRAGMENT)
        except fragments.FragmentError:
            continue
        rebuilt = framed.replace(FRAME_MARK, facts.inline(earlier), 1)
        if sha256(rebuilt.encode("utf-8")) == record["sha256"]:
            return True
    return False


def local_history(target: Path) -> list[str]:
    """Each distinct text of the local fragment that a commit reachable from any ref in the
    target holds, newest first; none where Git cannot say."""

    listed = _git(target, "rev-list", "--all", "--", LOCAL_FRAGMENT)
    if not listed:
        return []
    # `<commit>:<path>` reads from the work tree's root, where the pathspec above reads from
    # `target`, git's cwd; `./` makes both read from `target`, also in a subfolder install.
    specs = "".join(f"{commit}:./{LOCAL_FRAGMENT}\n" for commit in listed.decode().split())
    batch = _git(target, "cat-file", "--batch", stdin=specs.encode())
    texts: dict[str, str] = {}
    rest = batch or b""
    while rest:
        header, _, rest = rest.partition(b"\n")
        fields = header.split()
        if len(fields) != 3 or not fields[2].isdigit():
            continue
        size = int(fields[2])
        data, rest = rest[:size], rest[size + 1 :]
        if fields[1] != b"blob":
            continue
        try:
            texts.setdefault(fields[0].decode(), data.decode("utf-8"))
        except UnicodeDecodeError:
            continue
    return list(texts.values())


# --- One run, planned before anything is written --------------------------------


@dataclass
class Want:
    """One block or file adopt owns, as this run renders it."""

    kind: str
    path: str
    id: str
    data: bytes
    extra: dict[str, Any] = field(default_factory=dict)
    # The pointers block's local fragment inline text, as this run renders it; not recorded.
    inline: str | None = None

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
class Host:
    """A file adopt keeps blocks in: its bytes as read, its text as planned, and the text as read.

    The text is LF and has no byte-order mark, whatever the file has. The planned bytes give it
    back with each line the blocks did not touch as it was, in its own ending and mark, the lines
    the blocks wrote in the ending most of its lines use, and a host whose text no block changed
    keeps its bytes as they are, so adopt never rewrites a file's line endings for its own sake.
    """

    before: bytes | None
    text: str
    read: str = ""

    def __post_init__(self) -> None:
        self.read = self.text

    def after(self) -> bytes | None:
        """The planned bytes; a host left empty by a removal is deleted."""

        if self.before is not None and self.text == self.read:
            return self.before
        if not (self.text or self.before == b""):
            return None
        data = textio.splice(self.before, self.text) if self.before else self.text.encode("utf-8")
        marked = (self.before or b"").startswith(textio.UTF8_BOM)
        return textio.UTF8_BOM + data if marked else data


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
        # What the facts restate about this target: printed only by a run that changes a file,
        # so a run with nothing to change restates nothing.
        self.restated: Notes = []

    def present(self, relative: str) -> bool:
        """Whether `relative` is in the target; a symlink counts whatever it points at, and so
        does a path behind a symlinked directory, which adopt cannot show absent."""

        path = self.target
        for part in relative.split("/"):
            path = path / part
            if paths.redirects(path):
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

        if want.kind in FILE_KINDS:
            before = self._before(want.path)
            if (
                want.path == LOCAL_IGNORE
                and record is None
                and before is not None
                and textio.fold(before) != want.data
            ):
                raise AdoptError(
                    f"adopt now writes {LOCAL_IGNORE} whole, and this one is the project's own, "
                    "which --force would not keep either: move its lines to the root .gitignore, "
                    "delete the file, then run adopt again"
                )
            self._judge(want.path, before, want.data, record)
            self.files[want.path] = (before, textio.with_style(want.data, before))
        else:
            host = self.host(want.path)
            current = block_text(host.text, want.id)
            if current is None and identity.has_unclosed_fence(host.text):
                raise AdoptError(
                    f"{want.path} ends inside an unclosed code fence; close it, then re-run"
                )
            self._judge(
                label(want.path, want.id),
                current,
                want.data,
                record,
                lambda: from_source(self.target, current, record, want.inline),
            )
            host.text = put(host.text, want.id, want.data.decode("utf-8"), AFTER.get(want.id))
        self.records.append(want.record())

    def drop(self, record: Record) -> None:
        """Remove what `record` says adopt wrote; a path that is now a symlink is left alone."""

        path, name = record["path"], record["id"]
        if paths.redirects(self.target / path):
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
        spot = settings.find(record["sha256"], record["id"] == FINISH_MARK)
        self._judge(label(path, record["id"]), settings.at(spot), None, record)
        if spot is not None:
            settings.take(spot)
            self.notes.append(
                (
                    "note",
                    f"{path}: the finish check is retired in 1.7.0, so its {spot[0]} entry "
                    f"({record['id']}) is taken out",
                )
            )
        settings.removable = settings.removable or bool(record.get("created"))

    def _before(self, path: str) -> bytes | None:
        return self.files[path][0] if path in self.files else _read(self.target, path)

    def _judge(
        self,
        name: str,
        current: bytes | None,
        wanted: bytes | None,
        record: Record | None,
        derived: Callable[[], bool] | None = None,
    ) -> None:
        """Note `name` as edited when its bytes are neither wanted nor what adopt recorded.

        Bytes compare and digest in LF form, as the record does, so a checkout that Git gave
        CRLF reads as it does with LF.

        Bytes that differ from the record but are what this run writes, such as a block a
        person regenerated by hand from the source it renders, are no edit: they are recorded
        as they are, and the report says so, so that no `--force` is needed to keep them. So
        are bytes that `derived` shows are the recorded render with only its source's edit in
        it: they are written again, and the report says so."""

        if current is None:
            return
        current = textio.fold(current)
        unrecorded = record is not None and sha256(current) != record["sha256"]
        if current == wanted:
            if unrecorded:
                self.notes.append(("kept", f"{name}: {UNRECORDED}"))
            return
        if unrecorded and wanted is not None and derived is not None and derived():
            self.notes.append(("render", f"{name}: {FROM_SOURCE}"))
            return
        if record is None or unrecorded:
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
    chosen: Chosen,
) -> list[Want]:
    """What this engine installs for these harnesses, fragments and Done commands, in record
    order: the kernel, the facts, the pointers, the fragment files, the workspace's
    `.agents/.gitignore` and `.outcomebound/.gitignore`, the imports, the skills.

    A host no harness needs (`_unneeded`) gets no import block, and a record of one is dropped
    without writing its file again. Claude Code's host, CLAUDE.md, is itself one of the files
    that make it need one, so an existing CLAUDE.md keeps its block.
    """

    wants = [Want("block", AGENTS, KERNEL, kernel_block(source).encode("utf-8"))]
    imports = _imports_needed(run, found)
    written = [want.path for want in imports]
    found_fragments = catalog(source, run.target, ids)
    made = guidance(run.target, found, found_fragments, ids, chosen, written)
    extra = {"fragments": list(ids), "done": list(chosen.done), "inputs": made.rendered.inputs}
    if chosen.style:
        extra["style"] = list(chosen.style)
    if chosen.setup:
        extra["setup"] = list(chosen.setup)
    wants.append(Want("block", AGENTS, FACTS, made.rendered.facts.encode("utf-8"), extra))
    if made.rendered.pointers is not None:
        block = made.rendered.pointers
        local = found_fragments.get(LOCAL) if LOCAL in ids else None
        inline = facts.inline(local) if local is not None else None
        framed = framing(block, inline)
        frame = {} if framed is None else {"frame": sha256(framed.encode("utf-8"))}
        wants.append(Want("block", AGENTS, POINTERS, block.encode("utf-8"), frame, inline))
    wants.extend(Want("fragment", path, Path(path).stem, data) for path, data in made.files.items())
    if WORKSPACE in ids:
        wants.append(Want("ignore", WORKSPACE_IGNORE, WORKSPACE, workspace_ignore(source)))
    wants.append(Want("ignore", LOCAL_IGNORE, LOCAL_RECORDS, LOCAL_IGNORE_TEXT))
    run.restated.extend(("UNVERIFIED", text) for text in made.rendered.unverified)
    if made.rendered.absent:
        run.restated.append(("note", f"left out: {', '.join(made.rendered.absent)}"))
    wants.extend(imports)
    if any(item.harness == GENERIC for item in found):
        run.restated.append(("UNVERIFIED", f"{GENERIC}: that the harness reads {AGENTS}"))
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


def require_work_tree(target: Path) -> None:
    """Refuse a target Git cannot undo: no `.git` at or above it, or inside `.git` itself."""

    inside = any((directory / ".git").exists() for directory in (target, *target.parents))
    shown = textio.plain(str(target))
    if not inside:
        raise AdoptError(
            f"{shown} is not inside a Git work tree, and Git is adopt's undo",
            "to start a project here: `git init` there, then `outcomebound adopt . --detect`",
        )
    if any(paths.names_git(part) for part in target.parts):
        raise AdoptError(f"{shown} is not inside a Git work tree, and Git is adopt's undo")


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


def _byte_cap(row: object) -> int | None:
    """A row's documented byte cap on the instructions it loads, or None where it records none."""

    cap = row.get("doc_byte_cap") if isinstance(row, dict) else None
    return cap if isinstance(cap, int) and not isinstance(cap, bool) else None


def _chain_names(row: dict[str, Any]) -> tuple[str, ...]:
    """The file names a row's harness loads at most one of per folder, root down, an override
    name first: Codex takes `AGENTS.override.md` in place of its folder's `AGENTS.md`
    (research, harnesses/codex.md section 1)."""

    nested = row.get("nested") or {}
    globs = nested.get("globs", []) if nested.get("loads") is not False else []
    names = [glob[3:] for glob in globs if glob.startswith("**/") and "/" not in glob[3:]]
    return tuple(sorted(names, key=lambda name: ".override." not in name))


def _instruction_folders(target: Path, names: Sequence[str], ignored: Set[str]) -> list[str]:
    """The target's root and each folder under it holding one of `names`; `.git`, nested
    repositories and the `ignored` folders are not entered, no link is followed, and a folder
    that cannot be listed is passed over."""

    return ["."] + [
        folder.relative
        for folder in walk.folders(target, skip=ignored)
        if folder.relative != "." and any(name in folder.files for name in names)
    ]


def nested_bytes(run: Run, table: dict[str, Any], found: Sequence[Route]) -> Notes:
    """A warning for each folder whose instructions, root down, exceed the byte cap a selected
    harness's row records; a warning only, it refuses nothing. Codex stops loading at
    `project_doc_max_bytes`, 32 KiB by default, and cuts the file that crosses it, the deepest
    one first lost (research, harnesses/codex.md section 2). The root AGENTS.md is measured as
    this install leaves it. A folder Git ignores is not measured: it is no part of what another
    clone gets, as discovery and `instructions check` read it too."""

    def size(relative: str) -> int:
        host = run.hosts.get(relative)
        if host is not None:
            return len(host.after() or b"")
        try:
            return len((run.target / relative).read_bytes())
        except OSError:
            return 0

    notes: Notes = []
    ignored: Set[str] | None = None
    for route in found:
        row = table.get(route.harness)
        cap = _byte_cap(row)
        names = _chain_names(row) if isinstance(row, dict) else ()
        if cap is None or not names:
            continue
        if ignored is None:
            ignored = (discovery.git_ignored(run.target) or (frozenset(), frozenset()))[0]
        for folder in _instruction_folders(run.target, names, ignored):
            parts = [] if folder == "." else folder.split("/")
            loaded: list[tuple[str, int]] = []
            for depth in range(len(parts) + 1):
                prefix = "/".join(parts[:depth])
                sized = (
                    (path, size(path)) for path in (f"{prefix}/{n}".lstrip("/") for n in names)
                )
                first = next(((path, count) for path, count in sized if count), None)
                loaded.extend([first] if first else [])
            total = sum(count for _, count in loaded)
            if total > cap:
                listed = " + ".join(f"{path} {count}" for path, count in loaded)
                notes.append(
                    (
                        "warning",
                        f"{route.harness}: a session in {folder}/ loads {total} bytes of "
                        f"instructions ({listed}), past the {cap}-byte cap its row records "
                        "(doc_byte_cap); the harness cuts what is past it, the deepest file "
                        "first",
                    )
                )
    return notes


def ancestor_notes(target: Path, found: Sequence[Route]) -> Notes:
    """A warning for each instruction file a selected harness also loads from a folder above
    the target, as its row's `ancestors` records: a parent install's contract and pointers load
    beside this one, and the paths they name resolve from that folder."""

    notes: Notes = []
    for route in found:
        for folder, name in instruction_audit.ancestor_files(target, route.harness):
            relative = f"{os.path.relpath(folder, target)}/{name}".replace(os.sep, "/")
            notes.append(
                (
                    "warning",
                    f"{route.harness}: a session here also loads {relative}, from a folder "
                    "above the target (the row's ancestors); what it says loads beside this "
                    "install, and the paths it names resolve from that folder, not from here",
                )
            )
    return notes


def reference_notes(target: Path, found: Sequence[Route]) -> Notes:
    """A warning for each path, Make target or package script that the project's own
    instruction text names and the target no longer holds, as `outcomebound instructions
    check` reports it (docs/specs/instructions/design.md, `stale-reference`); it refuses
    nothing. A selection the audit cannot read is passed over, since the check reports it."""

    harnesses = [route.harness for route in found if route.harness != GENERIC]
    try:
        stale = instruction_audit.stale_references(target, harnesses)
    except (instruction_audit.AuditError, OSError):
        return []
    return [
        ("warning", f"stale reference: {textio.plain(finding.path)}:{finding.line}: {finding.fact}")
        for finding in stale
    ]


# The project settings files whose hooks Claude Code runs in the agent's current directory,
# which follows each `cd` (research harnesses/claude-code.md section 7).
CLAUDE_SETTINGS = (".claude/settings.json", ".claude/settings.local.json")


def _hook_commands(data: object) -> list[tuple[str, str]]:
    """(event, command) for each command hook a Claude Code settings document holds."""

    events = data.get("hooks") if isinstance(data, dict) else None
    found: list[tuple[str, str]] = []
    for event, groups in events.items() if isinstance(events, dict) else ():
        for group in groups if isinstance(groups, list) else ():
            hooks = group.get("hooks") if isinstance(group, dict) else None
            for hook in hooks if isinstance(hooks, list) else ():
                command = hook.get("command") if isinstance(hook, dict) else None
                if isinstance(command, str):
                    found.append((str(event), command))
    return found


def _relative_files(target: Path, command: str) -> list[str]:
    """Each word of a hook command that names a file of the target by a path relative to the
    working directory; none where the command does not split as a shell would split it."""

    try:
        words = shlex.split(command)
    except ValueError:
        return []
    named = []
    for word in words:
        if "/" not in word or word.startswith(("/", "~", "-")) or "$" in word:
            continue
        try:
            path = paths.resolve_bounded(target, word.removeprefix("./"))
        except (paths.PathError, OSError):
            continue
        if path.is_file():
            named.append(word)
    return list(dict.fromkeys(named))


def hook_path_notes(target: Path) -> Notes:
    """A warning for each project hook that Claude Code would run by a path relative to the
    working directory: the agent's `cd` moves that directory, so from any other folder the
    script is not found, the shell exits 127, and Claude Code passes over the hook as a
    non-blocking error (#113). It refuses nothing; a file adopt cannot read is passed over."""

    notes: Notes = []
    for relative in CLAUDE_SETTINGS:
        try:
            raw = _read(target, relative)
            data = json.loads(textio.decode(raw)) if raw is not None else None
        except (AdoptError, ValueError):
            continue
        for event, command in _hook_commands(data):
            for word in _relative_files(target, command):
                notes.append(
                    (
                        "warning",
                        f"{relative}: the {_printable(event)} hook "
                        f"`{_printable(command)}` names {_printable(word)} relative to the "
                        "working directory; Claude Code runs a hook in the folder the agent "
                        "is in, which each `cd` moves, so from any other folder the hook "
                        "fails and the session goes on without it; name it from "
                        '"$CLAUDE_PROJECT_DIR" (the folder the session started in; the '
                        "hook's input `cwd` names the folder the agent is in)",
                    )
                )
    return notes


def codex_sandbox_notes(target: Path, found: Sequence[Route]) -> Notes:
    """For a run that adds codex, once, the configuration route that lets an unattended session
    write the workspace folders and commit. Codex's default `workspace-write` sandbox keeps
    `<root>/.agents` and the Git directory read-only (research harnesses/codex.md section 9),
    which records `--add-dir` as observed but not the `writable_roots` key, and not whether a
    desktop or IDE session lacks the flag; whether the harness can write the folders is not
    something adopt sees."""

    if not any(route.harness == "codex" for route in found):
        return []
    common = (discovery.git_read(target, "rev-parse", "--git-common-dir") or b"").strip()
    git_dir = (target / os.fsdecode(common)).resolve() if common else target / ".git"
    roots = ", ".join(_printable(f'"{path.as_posix()}"') for path in (target / ".agents", git_dir))
    return [
        (
            "UNVERIFIED",
            "codex: the default sandbox keeps .agents and the Git directory read-only (research "
            f"harnesses/codex.md section 9); for unattended sessions pass --add-dir for {roots}, "
            "or add them to writable_roots under [sandbox_workspace_write] in config.toml; the "
            "research records the flag, not the key, and not whether a desktop or IDE session "
            "lacks the flag, and adopt cannot see whether the harness can write them",
        )
    ]


def claims_plan_notes(target: Path) -> Notes:
    """A warning where the claims plan that `.outcomebound/tickets.json` declares would run
    its claims in a folder it was not written for, as `tickets_claims.placement` decides for
    `tickets check` too: since 1.1.0 a relative `cwd`, and a plan with none, starts at the plan
    file's folder, and an upgrade is where a plan written for 1.0.0 first meets that. A declared
    path that the checkout root does not hold either is planned, and is not reported. The plan
    is the project's file, so this writes nothing to it and refuses nothing. With no
    declaration, or none `tickets` can read, or no readable plan, it says nothing:
    `tickets check` refuses those itself."""

    try:
        plan = load_claims(target, load_declaration(target))
    except (Refusal, EngineError):
        return []
    found = placement(plan, target)
    if not found.misplaced:
        return []
    root = target.resolve()
    shown = _printable(plan.path)
    folder = _printable(Path(plan.path).parent.as_posix())
    where = _printable(Path(os.path.relpath(plan.cwd_resolved, root)).as_posix())
    fix = f'"cwd": "{_printable(found.to_root)}"'
    notes: Notes = [
        (
            "warning",
            f"tickets: the claim `{_printable(name)}` in {shown} declares "
            f"{_printable(', '.join(moved))}, which the checkout does not hold from the plan's "
            f"working directory {where} but holds from the checkout root; write {fix} in the "
            "plan to run its claims at the root, or add the path where the claim runs",
        )
        for name, moved in found.moved.items()
    ]
    if found.at_plan_folder:
        notes.append(
            (
                "warning",
                f"tickets: the claims plan {shown} runs its claims in {folder}/, the plan file's "
                'own folder, not at the checkout root, as a plan with no cwd or with "cwd": "." '
                f"does; write {fix} in it to run them at the root",
            )
        )
    return notes


def ignored_notes(target: Path, owned: Sequence[str]) -> Notes:
    """A warning for each path the final install owns that Git ignores, unchanged paths too:
    the manifest records it, so every other clone, which never gets it, reads it missing in
    `--check`. A tracked path is never ignored, as Git keeps tracking it."""

    if not owned:
        return []
    data = b"".join(os.fsencode(path) + b"\0" for path in owned)
    raw = discovery.git_read(target, "check-ignore", "-v", "-z", "--stdin", data=data)
    fields = os.fsdecode(raw or b"").split("\0")
    notes: Notes = []
    for source, line, pattern, path in zip(*[iter(fields)] * 4, strict=False):
        if pattern.startswith("!"):
            continue
        rule = _printable(f"{source}:{line}: {pattern}")
        notes.append(
            (
                "warning",
                f"{_printable(path)}: Git ignores it ({rule}), so it stays out of "
                f"every commit while {MANIFEST} records it, and another clone reads it missing "
                "in adopt --check; un-ignore it, or choose a harness whose files Git keeps",
            )
        )
    return notes


def _printable(text: str) -> str:
    """`text` with each character outside printable ASCII escaped, so text a target's files
    hold, such as a `.gitignore` pattern, cannot steer the terminal."""

    return "".join(
        char if " " <= char <= "~" else char.encode("unicode_escape").decode("ascii")
        for char in text
    )


def uncommitted_notes(target: Path, planned: Planned) -> Notes:
    """A warning where this run changes a tracked AGENTS.md that holds changes not committed:
    adopt's blocks and those changes then share one file, and a clean commit of either needs
    them apart. An untracked AGENTS.md is new as a whole, and is not warned about."""

    before, after = planned.get(AGENTS, (None, None))
    if before is None or after is None:
        return []
    status = discovery.git_read(
        target, "--no-optional-locks", "status", "--porcelain", "-z", "--", AGENTS
    )
    if not status or status.startswith(b"??"):
        return []
    return [
        (
            "warning",
            f"{AGENTS} holds changes that are not committed; this install's blocks join them in "
            "the one file, so commit or set those changes apart before you commit the install",
        )
    ]


@dataclass(frozen=True)
class Selection:
    """What an install is asked for; `None` keeps what the manifest records, and no harness
    at all is `generic`."""

    harnesses: list[str] | None = None
    fragments: list[str] | None = None
    done: list[str] | None = None
    style: list[str] | None = None
    setup: list[str] | None = None


def install(
    target: Path, source: Path, selection: Selection, force: bool
) -> tuple[Planned, list[str], Notes]:
    """Plan an install or upgrade. It writes no hook and runs no Done command; a `hook` record
    that an earlier version wrote is dropped with its entry, like any record this install no
    longer wants."""

    require_work_tree(target)
    manifest = load_manifest(target)
    own = manifest.own
    names = recorded_harnesses(own) if selection.harnesses is None else selection.harnesses
    found = routes(source, names or [GENERIC])
    ids = recorded_fragments(own) if selection.fragments is None else selection.fragments
    done = recorded_done(own) if selection.done is None else selection.done
    style = recorded_style(own) if selection.style is None else selection.style
    setup = recorded_setup(own) if selection.setup is None else selection.setup
    run = Run(target, force)
    table = harness_table(source)
    wants = desired(run, source, found, ids, Chosen(done, style, setup))
    recorded = {(record["kind"], record["path"], record["id"]): record for record in manifest.own}
    for want in wants:
        run.keep(want, recorded.pop(want.key(), None))
    for record in recorded.values():
        run.drop(record)
    run.notes.append(footprint(wants))
    run.notes.extend(nested_bytes(run, table, found))
    run.notes.extend(ancestor_notes(target, found))
    run.notes.extend(reference_notes(target, found))
    run.notes.extend(hook_path_notes(target))
    added = {route.harness for route in found} - set(recorded_harnesses(own))
    run.notes.extend(codex_sandbox_notes(target, found) if "codex" in added else [])
    run.notes.extend(claims_plan_notes(target))
    planned = run.planned(manifest, engine_version(source))
    owned = sorted({MANIFEST, *(record["path"] for record in run.records)})
    run.notes.extend(ignored_notes(target, owned))
    run.notes.extend(uncommitted_notes(target, planned))
    notes = [*run.restated, *run.notes] if planned else run.notes
    return planned, run.edited, notes


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
    """The bytes `record` names as they are on disk; for a hook record, its group."""

    data = _read(target, record["path"])
    if record["kind"] == HOOK:
        if data is None or finish_check.MARKER not in data:
            return None
        settings = Settings.parse(record["path"], data)
        return settings.at(settings.find(record["sha256"], record["id"] == FINISH_MARK))
    if data is None:
        return None
    if record["kind"] in FILE_KINDS:
        return textio.fold(data)
    return block_text(_host_text(record["path"], data), record["id"])


def recomputed(target: Path, source: Path, own: Sequence[Record]) -> Guidance:
    """The facts and pointers the recorded selection gives against today's sources."""

    ids = recorded_fragments(own)
    found = routes(source, recorded_harnesses(own) or [GENERIC])
    chosen = Chosen(recorded_done(own), recorded_style(own), recorded_setup(own))
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
        return LOCAL_IGNORE_TEXT if name == LOCAL_RECORDS else workspace_ignore(source)
    if kind == "fragment":
        shipped = catalog(source, target, []).get(name)
        if shipped is None:
            raise AdoptError(f"this engine ships no {name} fragment")
        return _fragment_bytes(shipped)
    if kind == "pointer":
        return pointer_block(record["path"]).encode("utf-8")
    if name == KERNEL:
        return kernel_block(source).encode("utf-8")
    rendered = recomputed(target, source, own).rendered
    block = {FACTS: rendered.facts, POINTERS: rendered.pointers}.get(name)
    if block is None:
        raise AdoptError(f"this engine renders no {name} block for the recorded selection")
    return block.encode("utf-8")


def _retired_state(target: Path, record: Record) -> str:
    """A `hook` record's state: this engine writes no hook entry, so an entry that is there as
    the record has it is `stale` (the next install takes it out), one a person edited is
    `edited`, and one gone is `missing`."""

    try:
        observed = _observed(target, record)
    except AdoptError:
        return "edited"
    if observed is None:
        return "missing"
    return "stale" if sha256(observed) == record["sha256"] else "edited"


def _retired_detail(target: Path, record: Record, found: str) -> str:
    """What `--check` says of a `hook` record: the entry the next install takes out, by its
    event and command, or why it does not."""

    where, command = "", ""
    data = _read(target, record["path"])
    if data is not None and finish_check.MARKER in data:
        try:
            settings = Settings.parse(record["path"], data)
            spot = settings.find(record["sha256"], record["id"] == FINISH_MARK)
            group = None if spot is None else settings.hooks()[spot[0]][spot[1]]
            handlers = group.get("hooks") if isinstance(group, dict) else None
            first = handlers[0] if isinstance(handlers, list) and handlers else None
            if spot is not None and isinstance(first, dict):
                where, command = spot[0], str(first.get("command", ""))
        except (AdoptError, LookupError, TypeError):
            pass
    entry = f"the {_printable(where)} entry `{_printable(command)}`" if where else "its entry"
    if found == "missing":
        return (
            "the finish check is retired in 1.7.0; the entry is gone, so the next install "
            "drops its record"
        )
    if found == "edited":
        return (
            f"the finish check is retired in 1.7.0; {entry} differs from what adopt wrote, so "
            "the next install takes it out only with --force"
        )
    return f"the finish check is retired in 1.7.0; the next install takes out {entry}"


def state(target: Path, source: Path, record: Record, own: Sequence[Record]) -> str:
    """`current`, `edited` (neither what adopt wrote nor what it now renders), `stale` (the
    engine now renders it differently, or no longer renders it, or it holds what the engine
    now renders and the record does not) or `missing`; `own` is every record adopt holds,
    which the facts and pointers are recomputed from."""

    if record["kind"] == HOOK:
        return _retired_state(target, record)
    try:
        observed = _observed(target, record)
    except AdoptError:
        return "edited"
    if observed is None:
        return "missing"
    try:
        rendered: bytes | None = _rendered(target, source, record, own)
    except AdoptError:
        rendered = None
    if sha256(observed) != record["sha256"]:
        if observed == rendered or from_source(
            target, observed, record, _local_inline(target, source, own)
        ):
            return "stale"
        return "edited"
    if rendered is None:
        return "stale"
    return "current" if sha256(rendered) == record["sha256"] else "stale"


def _local_inline(target: Path, source: Path, own: Sequence[Record]) -> str | None:
    """The local fragment's inline text as the recorded selection renders it now; None where
    it is not selected or cannot be read."""

    if LOCAL not in recorded_fragments(own):
        return None
    try:
        return facts.inline(_local_fragment(source, target))
    except AdoptError:
        return None


def unrecorded_detail(target: Path, source: Path, record: Record, own: Sequence[Record]) -> str:
    """Why a stale record's bytes, which differ from it, are no edit."""

    try:
        observed = _observed(target, record)
        if observed is not None and observed == _rendered(target, source, record, own):
            return UNRECORDED
    except AdoptError:
        pass
    return FROM_SOURCE


def unrecorded(target: Path, record: Record) -> bool:
    """Whether the record's block or file is there with bytes other than the record's."""

    try:
        observed = _observed(target, record)
    except AdoptError:
        return False
    return observed is not None and sha256(observed) != record["sha256"]


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

    command = f"outcomebound adopt {paths.shell_path(target)}"
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
        command = f"outcomebound adopt {paths.shell_path(target)} --detect"
        print(f"next: {command} prints the command that installs OutcomeBound here")
        return 1
    found: list[str] = []
    for record in manifest.own:
        found.append(state(target, source, record, manifest.own))
        name = None if record["kind"] in FILE_KINDS else record["id"]
        detail = ""
        if record["kind"] == HOOK:
            detail = _retired_detail(target, record, found[-1])
        elif found[-1] == "stale" and unrecorded(target, record):
            detail = unrecorded_detail(target, source, record, manifest.own)
        elif found[-1] == "stale" and record["id"] == FACTS and record["kind"] == "block":
            detail = moved(target, source, record, manifest.own)
        print(f"{found[-1]:<8} {label(record['path'], name)}" + (f": {detail}" if detail else ""))
    for line in _drift_lines(target, source, manifest.own, facts.read_ci(target)):
        print(f"{'drift':<8} {line}")
    for line in _worktree_warnings(target, source):
        print(line)
    step = next_step(target, found)
    if step is not None:
        print(step)
    return min(sum(state != "current" for state in found), CHECK_CAP)


def _worktree_warnings(target: Path, source: Path) -> list[str]:
    """The `warn` lines for each other worktree of the project whose install is older than this
    engine; none where Git cannot list them. Informational: no exit changes."""

    listed = _git(target, "worktree", "list", "--porcelain")
    if listed is None:
        return []
    found = adopt_worktrees.lines(target, listed.decode("utf-8", "replace"), engine_version(source))
    return adopt_worktrees.render(found)


def _drift_lines(
    target: Path, source: Path, own: Sequence[Record], files: Sequence[facts.CiFile]
) -> list[str]:
    """The lines for each signal the files show that the recorded fragment selection or the
    `local` fragment's exposure line contradicts; none where nothing is installed here or the
    engine's fragments cannot be read. Informational: they refuse nothing and change no exit."""

    if not own:
        return []
    try:
        detected = fragments.detect(target, fragments.load_all(source))
    except fragments.FragmentError:
        detected = []
    selected = recorded_fragments(own)
    local = None
    if LOCAL in selected:
        try:
            data = _read(target, LOCAL_FRAGMENT)
        except AdoptError:
            data = None
        local = None if data is None else data.decode("utf-8", "replace")
    return drift.lines(target, selected, detected, files, local)


def _git(target: Path, *arguments: str, stdin: bytes | None = None) -> bytes | None:
    """What one read-only git command printed in `target`; None where it failed or Git cannot run.
    Git comes from PATH's absolute entries only (`programs.require`), so the target cannot supply
    its own, on Windows too."""

    inherited = dict(os.environ)
    inherited["PATH"] = os.pathsep.join(
        part for part in inherited.get("PATH", "").split(os.pathsep) if os.path.isabs(part)
    )
    try:
        completed = subprocess.run(
            [programs.require("git", inherited), *GIT_READ_CONFIGURATION, *arguments],
            cwd=target,
            env=git_environment(inherited),
            input=stdin if stdin is not None else b"",
            capture_output=True,
            check=False,
        )
    except OSError:
        return None
    return completed.stdout if completed.returncode == 0 else None


def _git_line(target: Path, *arguments: str) -> str | None:
    """What one read-only git command printed in `target`, stripped; None where it failed or
    printed nothing."""

    output = _git(target, *arguments)
    text = "" if output is None else output.decode("utf-8", "replace").strip()
    return text or None


def default_base(target: Path) -> str | None:
    """The ref the floor compares against: the remote's default branch, as
    `refs/remotes/origin/HEAD` names it, else `origin/main` where it resolves, else None."""

    named = _git_line(target, "symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD")
    for ref in (named, FALLBACK_BASE):
        if ref and _git_line(target, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"):
            return ref
    return None


def _proposal(target: Path) -> tuple[list[str], str | None, bool]:
    """What `--detect` proposes for Done, in run order, and, where its test command came from
    discovery rather than CI, the files that suggested it: such a command runs on the host.
    The last field names whether CI commands were excluded for a non-POSIX or unresolved shell.
    All proposals remain unexecuted candidates, including those read from bash steps."""

    try:
        floor = paths.read_bounded(target, facts.FLOOR)
    except paths.PathError:
        floor = None
    done = []
    if floor is not None:
        base = default_base(target)
        done.append(FLOOR_RUNNER + (f" --base {shlex.quote(base)}" if base else ""))
    files = facts.read_ci(target)
    ci = [command for item in files for command in item.done]
    excluded = any(command not in item.done for item in files for command in item.tests)
    if ci:
        return [*done, ci[0]], None, excluded
    try:
        components = discovery.discover(target)["inferred"]["components"]
    except (discovery.DiscoveryError, OSError):
        components = []
    for item in components:
        if item["root"] == "." and item["check_candidates"]:
            evidence = ", ".join(item["evidence"]) or "the target's files"
            return [*done, item["check_candidates"][0]["command"]], evidence, excluded
    return done, None, excluded


def proposed_done(target: Path) -> list[str]:
    """What `--detect` proposes for Done, in run order: the floor's runner where a floor is
    installed, with `--base` the remote's default branch where one resolves, then the first
    test command read from a CI step with a resolved sh or bash shell, or, where none qualifies,
    the first independent check candidate discovery offers for the target's root. Neither a
    shell family nor a file observation establishes that the candidate runs through POSIX sh."""

    return _proposal(target)[0]


class _Engine(str):
    """A note made of the engine's own text and paths, which the target did not give and which a
    person or an agent opens as written, so it is printed as it is."""


def _only_git(target: Path) -> bool:
    """Whether the target holds no entry but `.git`, or none at all: discovery's `empty`, with
    the repository's own folder not counted."""

    try:
        return {entry.name for entry in target.iterdir()} <= {".git"}
    except OSError:
        return False


def _trailing_notes(
    source: Path, done: Sequence[str], suggested_by: str | None, excluded: bool, found: bool
) -> list[str]:
    """What `--detect` once printed after the command on its one line: why Done holds what it
    holds, and what the person gives in its place."""

    notes = []
    if excluded:
        notes.append(
            "CI commands with a non-POSIX or unresolved shell were not copied into Done; give a "
            "project POSIX equivalent to --done, written as a POSIX shell line"
        )
    if suggested_by is not None:
        notes.append(
            f"{done[-1]} is what {suggested_by} suggests, not a command CI runs: it runs on the "
            "host, so where the project runs its tests only in a container, give that command "
            "to --done in its place"
        )
        if done[-1].split()[0] in ("python", "python3"):
            notes.append(
                "the python it names is the interpreter of the machine that ran --detect: "
                "commit the form your hooks run"
            )
    if FLOOR_RUNNER in done:
        notes.append(
            "no default branch resolves: the floor runs without --base, so its loosening "
            "check does not run"
        )
    if not found:
        listed = ", ".join(loadable(harness_table(source)))
        notes.append(f"no harness file found; or one of: {listed}")
    return notes


def _setup_notes(candidates: Sequence[facts.SetupCandidate]) -> list[str]:
    """Each entry point the project has for setup; the first is on the command, the rest are
    named only. None found is named too, since a fresh clone may need steps no file shows."""

    if not candidates:
        return [
            "no Setup entry point found (a Make target or package.json script named setup or "
            "bootstrap, or an executable bin/setup, script/setup, script/bootstrap or "
            "scripts/setup.sh); record the steps a fresh clone needs with --setup"
        ]
    return [
        f"setup candidate: {item.command} ({item.evidence}); "
        + ("proposed with --setup" if index == 0 else "not proposed")
        for index, item in enumerate(candidates)
    ]


def _signal_notes(target: Path, files: Sequence[facts.CiFile]) -> list[str]:
    """The onboarding signals of the design's table, one line each: its kind, the file or the
    folders that show it, any value read, and the slot of the `local` fragment a proposed line
    goes to; and each file the reading could not settle."""

    signals: list[facts.Signal] = []
    unread: list[tuple[str, str]] = []
    text, why = facts.read_small(target, ".gitattributes")
    patterns = facts.generated_patterns(text or "")
    if patterns:
        signals.append(facts.Signal("generated", ".gitattributes", ", ".join(patterns), "Bounds"))
    unread.extend([(".gitattributes", why)] if why else [])
    tracked = discovery.git_read(target, "ls-files", "-z") or b""
    folders = facts.migration_folders(os.fsdecode(name) for name in tracked.split(b"\0") if name)
    if folders:
        signals.append(facts.Signal("migrations", ", ".join(folders), "", "Bounds"))
    runtime, left = facts.runtime_signals(target)
    signals += runtime
    unread += left
    for name in facts.ENVIRONMENT_FILES:
        text, why = facts.read_small(target, name)
        names = facts.environment_names(text or "")
        if names:
            signals.append(facts.Signal("environment-names", name, ", ".join(names), "Context"))
        unread.extend([(name, why)] if why else [])
    signals += facts.workflow_signals(files)
    signals += drift.signals(target)
    notes = [
        f"signal {item.kind}: {item.where}"
        + (f"; value: {item.value}" if item.value else "")
        + f"; local slot: {item.slot}"
        for item in signals
    ]
    return notes + [f"not read: {name}: {why}" for name, why in unread]


def _readiness_notes(target: Path, done: Sequence[str], files: Sequence[facts.CiFile]) -> list[str]:
    """What the files show about whether Done can be trusted, one line each with its verdict and
    next step. No score, no level and no stored history."""

    try:
        recorded = recorded_done(load_manifest(target).own)
    except AdoptError:
        recorded = []
    notes = []
    if not done and not recorded:
        notes.append("readiness UNVERIFIED: no Done candidate; next: record one with --done")
    notes += [
        f"readiness UNVERIFIED: {name} has no lockfile beside it; next: a library may commit "
        "none; an application pins its dependencies"
        for name in facts.manifests_without_lock(target)
    ]
    secrets = facts.secrets_reaching(files)
    for item in files:
        for command, job, step in item.places:
            names = secrets.get((item.path, job, step), [])
            if command in done and names:
                where = f"job {job} of {item.path}" if job else item.path
                notes.append(
                    f"readiness UNVERIFIED: the CI test command `{command}` runs in {where}, "
                    f"which names {', '.join(f'secrets.{name}' for name in names)}; next: that "
                    "command cannot run on the host without the secret"
                )
    return list(dict.fromkeys(notes))


def detect(target: Path, source: Path) -> int:
    """Print the install command this target's files suggest alone on the first line, then
    every note on a line of its own that starts with `#`, so that pasting the output into a
    shell runs only the command: the notes the command once carried, the Setup candidates, the
    lockfiles' install commands, the onboarding signals, the readiness lines and, last, the
    guide for an agent. Write nothing and run nothing from the target; a target the install
    would refuse, outside a Git work tree, is refused here first. Every string the target gave,
    a path included, is escaped as the instruction audit escapes quoted text."""

    require_work_tree(target)
    try:
        own = load_manifest(target).own
    except AdoptError:
        own = []
    try:
        ids = fragments.detect(target, fragments.load_all(source))
    except fragments.FragmentError as error:
        raise AdoptError(str(error)) from error
    found = [harness for sign, harness in HARNESS_SIGNS if os.path.lexists(target / sign)]
    harnesses = ",".join(dict.fromkeys(found)) if found else GENERIC
    words = ["outcomebound", "adopt", Path(target).as_posix(), "--harness"]
    words.append(harnesses)
    if ids:
        words += ["--fragments", ",".join(ids)]
    done, suggested_by, excluded = _proposal(target)
    for command in done:
        words += ["--done", command]
    setups = facts.setup_candidates(target)
    if setups:
        words += ["--setup", setups[0].command]
    notes = _trailing_notes(source, done, suggested_by, excluded, bool(found))
    if _only_git(target):
        reference = Path(source).resolve() / NEW_PROJECT_REFERENCE
        route = f"; read {reference.as_posix()}" if reference.is_file() else ""
        notes.append(
            _Engine(f"nothing here but .git: a new project starts from this command{route}")
        )
        if (Path(source) / SCAFFOLD_MANIFEST).is_file():
            notes.append(
                _Engine(
                    "a new project: outcomebound scaffold . --lifecycle <preset> previews the "
                    "files of its lifecycle; the new-project reference says how to choose"
                )
            )
    notes += _setup_notes(setups)
    notes += [
        f"lockfile {name}: {command} installs from it; a candidate for --setup, not proposed"
        for name, command in facts.lockfile_candidates(target)
    ]
    files = facts.read_ci(target)
    notes += _signal_notes(target, files)
    notes += _readiness_notes(target, done, files)
    notes += [f"drift: {line}" for line in _drift_lines(target, source, own, files)]
    guide = (Path(source).resolve() / GUIDE).as_posix()
    notes.append(_Engine(f"onboarding guide for an agent: {guide}"))
    print(textio.visible(" ".join(map(paths.shell_word, words))))
    for note in notes:
        print(f"# {note}" if isinstance(note, _Engine) else textio.plain(f"# {note}"))
    return 0


# --- Command line ---------------------------------------------------------------

USAGE = """outcomebound adopt <target> [--harness H[,H]]... [--fragments IDS] [--done CMD]...
                            [--setup CMD]... [--human-style ste] [--dry-run] [--force]
       outcomebound adopt <target> --detect | --check
       outcomebound adopt <target> --remove [--dry-run] [--force]"""
DESCRIPTION = """\
Install or upgrade OutcomeBound in <target>, inside a Git work tree. A flag you omit keeps the
value the manifest records (--harness, --fragments, --done, --setup, --human-style); pass only
what changes. AGENTS.md gets three
blocks: the operating contract; the project facts (Done: the --done commands; Setup: the
--setup commands, which a person records and adopt never runs; CI test: the test
command a GitHub Actions or GitLab CI file runs, read without running anything; Irreversible
edges: those the selected fragments declare, and a floor loosening where a floor is installed;
Text for people: with --human-style ste, documents a person keeps (pull request descriptions,
commit messages, specs and handovers) in the style of ASD-STE100 Simplified Technical English,
and not replies in conversation; Precedence); and the guidance pointers: the local
fragment inline, then one line per fragment in --fragments, copied under
.outcomebound/fragments/, and per skill: the thirteen working skills. The workspace fragment also
gets .agents/.gitignore, which keeps its four folders out of Git, and every install gets
.outcomebound/.gitignore, which keeps OutcomeBound's local records (the research inbox, the
validation logs) out of Git. A fact it cannot observe is left out, and the install report names
it UNVERIFIED. The report also warns, refusing nothing, for each path it writes that Git
ignores, where a tracked AGENTS.md holds changes not committed, and for each instruction file a
harness also loads from a folder above the target. Each harness gets the skills, and an @AGENTS.md
import block in each harness file that needs one: none where the harness reads AGENTS.md itself,
as Claude Code 2.1.281 and later does where the target has no CLAUDE.md, .claude/CLAUDE.md or
CLAUDE.local.md. generic, the default where no harness is named, serves a harness the table does
not list: its skills go under .outcomebound/skills/, and any other unlisted name is refused.
What it writes is recorded in .outcomebound/manifest.json; re-running it upgrades. An install
prints the words an agent always loads, skill descriptions included, and no size refuses one. It
refuses a harness that cannot be made to load AGENTS.md and, without --force, to replace or
remove a block or file whose bytes are not what it recorded, save bytes it writes there itself,
which it records and names on a kept line, and a pointers block that is the recorded render with
only the local fragment's own edit in it, which it writes again and names on a render line. A
refusal writes nothing.

--detect prints the install command this target's files suggest alone on its first line, with
--setup for the project's own entry point (a Make target or package.json script named setup or
bootstrap, or an executable bin/setup, script/setup, script/bootstrap or scripts/setup.sh), and
then every note on a line that starts with #, so that pasting the output into a shell runs the
command only: why Done holds what it holds, the Setup candidates, the install commands of the
lockfiles (comments only), the onboarding signals (generated paths, applied migration folders,
publishing workflows, runtime versions, environment variable names, CI secret names, the count
of recent authors and the release identity, each with the file that shows it and the slot of the
local fragment it goes to), the readiness lines (each with its verdict and next step), one drift
line for each signal that the install's recorded fragments or exposure line contradict (--check
prints the same lines, and refuses nothing), and a last line naming the onboarding guide in the
engine, an absolute path. In a folder with nothing but .git it names the new-project reference.
It writes nothing and runs nothing from the target, and escapes every string the target gave.
Outside a Git work tree, the refusal names the route: git init there, then adopt . --detect.

An install writes no hook and runs no Done command. 1.6.0 and earlier wrote the finish check's
entries into .claude/settings.json and .codex/hooks.json; an install takes out each entry that a
`hook` record of the manifest names, and the record, and keeps every other key and entry of the
settings document with its order and indentation, and deletes the document only where an install
created it and it is now empty. An entry a person edited is kept and refused without --force, like
any other edited file. --check reports each such record as stale, edited or missing, as for any
other record, and names its entry. The flags
that 1.6.0 and earlier took for the finish check are retired: each is still accepted, changes
nothing and prints one note.
"""
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
        "--detect",
        action="store_true",
        help="print the install command alone on the first line, then every note on a line "
        "that starts with #; write nothing",
    )
    verb.add_argument(
        "--check",
        action="store_true",
        help="print current, edited, stale or missing for each record, then the command that "
        "makes each current; write nothing",
    )
    verb.add_argument("--remove", action="store_true", help="remove every recorded block and file")
    # The flags of 1.6.0 and earlier for the finish check: accepted, hidden, and each prints a note.
    for flag in ("--finish-check", "--no-finish-check", "--verify"):
        parser.add_argument(flag, action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--finish-timeout", help=argparse.SUPPRESS)
    parser.add_argument("--done-skip", action="append", nargs=2, help=argparse.SUPPRESS)
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
        "--setup",
        action="append",
        metavar="CMD",
        help="a command that makes a fresh clone ready to run Done, in run order; repeats add "
        "up; '' for none; omitted keeps the recorded ones; recorded as the person's fact, "
        "never run by adopt",
    )
    parser.add_argument(
        "--human-style",
        choices=(*facts.STYLES, ""),
        metavar="STYLE",
        help="a style for documents an agent writes for a person to keep: 'ste' (ASD-STE100 "
        "Simplified Technical English; not replies in conversation); '' for none; omitted "
        "keeps the recorded one",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print what would change, with a unified diff of each text file; write nothing",
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


def _commands(values: Sequence[str], flag: str = "--done") -> list[str]:
    """The commands a flag (`--done` or `--setup`) names, each one line; an empty one records
    none."""

    commands = [value.strip() for value in values if value.strip()]
    for command in commands:
        if "\n" in command or "\r" in command or "<!--" in command:
            raise AdoptError(f"a {flag} command is one line with no comment opener: {command!r}")
    return commands


def _skill_root(path: str) -> tuple[str, str] | None:
    """For a file inside a harness's skills folder, that folder and the skill's name:
    `.claude/skills/diagnose/SKILL.md` gives (`.claude/skills`, `diagnose`)."""

    parts = path.split("/")
    for index in range(len(parts) - 2):
        if parts[index] == "skills":
            return "/".join(parts[: index + 1]), parts[index + 1]
    return None


def _skill_summaries(planned: Planned) -> tuple[list[str], list[str]]:
    """The planned paths a report names one by one, and one summary line for each verb and skills
    folder over the skill files: a three-harness install is about 290 files, and a line each
    buries the warnings that follow."""

    singles: list[str] = []
    groups: dict[tuple[str, str], list[str]] = {}
    for path, (before, after) in planned.items():
        verb = "create" if before is None else "delete" if after is None else "update"
        root = _skill_root(path)
        if root is None:
            singles.append(path)
        else:
            groups.setdefault((verb, root[0]), []).append(root[1])
    lines = []
    for (verb, folder), skills in groups.items():
        count, names = len(skills), len(set(skills))
        lines.append(
            f"{verb:<8} {folder}/: {count} file{'s' if count != 1 else ''} "
            f"in {names} skill{'s' if names != 1 else ''}"
        )
    return singles, lines


def _report(planned: Planned, edited: Sequence[str], notes: Notes) -> None:
    """The report: each file that is not a skill file on its own line, one line per verb and
    skills folder for the skill files (a changed one is also listed by name in a dry run's
    diffs), then the notes."""

    for name in edited:
        print(f"edited   {name}: overridden by --force")
    singles, summaries = _skill_summaries(planned)
    for path in singles:
        before, after = planned[path]
        verb = "create" if before is None else "delete" if after is None else "update"
        print(f"{verb:<8} {path}")
    for line in summaries:
        print(line)
    if not planned:
        print("nothing to change")
    for verb, text in notes:
        print(f"{verb:<8} {text}")


def _diffs(planned: Planned) -> None:
    """A unified diff for each planned text change; a file that is not UTF-8 text is named."""

    for path, (before, after) in planned.items():
        if before is None and after is not None:
            # A new file is its whole text, which the install writes as shipped: its size only,
            # and a new skill file is counted in the report's summary line, not named again.
            if _skill_root(path) is None:
                print(f"new      {path}: {len(after)} bytes, written as shipped")
            continue
        try:
            old = [] if before is None else before.decode("utf-8").splitlines(keepends=True)
            new = [] if after is None else after.decode("utf-8").splitlines(keepends=True)
        except UnicodeDecodeError:
            print(f"binary   {path}: changed; no diff for a file that is not UTF-8 text")
            continue
        old_name = "/dev/null" if before is None else f"a/{path}"
        new_name = "/dev/null" if after is None else f"b/{path}"
        text = "".join(difflib.unified_diff(old, new, old_name, new_name))
        print(text if text.endswith("\n") or not text else text + "\n\\ No newline at end of file")


def retired_notes(args: argparse.Namespace) -> Notes:
    """One note for each retired flag the command line holds."""

    return [
        (
            "note",
            f"{flag}: retired in 1.7.0; adopt installs no hook and runs no Done command, and an "
            "install takes out any entry an earlier version wrote",
        )
        for flag in RETIRED_FLAGS
        if getattr(args, flag.removeprefix("--").replace("-", "_")) not in (False, None)
    ]


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
            None if args.human_style is None else [args.human_style] if args.human_style else [],
            None if args.setup is None else _commands(args.setup, "--setup"),
        )
        planned, edited, notes = install(target, source, selection, args.force)
        notes = [*retired_notes(args), *notes]
    if args.dry_run:
        _report(planned, edited, notes)
        _diffs(planned)
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
    chosen = chosen or args.human_style is not None or args.setup is not None
    if (args.detect or args.check or args.remove) and (chosen or retired_notes(args)):
        parser.error(
            "--harness, --fragments, --done, --setup and --human-style apply to an install, and "
            "the retired flags apply to none"
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
