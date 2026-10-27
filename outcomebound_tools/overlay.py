"""The facts-only overlay: one worktree reads the facts-only install, the rest keeps the full one.

`outcomebound adopt <worktree> --facts-only --local` writes, in that worktree only, the files a
harness reads in place of the committed ones, each holding the facts-only render of `AGENTS.md`
(`docs/specs/install/design.md`, the decisions on the overlay): Codex's `AGENTS.override.md`;
Claude Code's `CLAUDE.local.md` and, where the worktree has a `CLAUDE.md` or `.claude/CLAUDE.md`,
that file's absolute path in `claudeMdExcludes` of `.claude/settings.local.json`, merged into what
the file holds. The overlay's own record is `.outcomebound/overlay.json` (kind, path and sha256 of
each thing it wrote). Nothing of the committed install changes: not `AGENTS.md`, not the manifest,
not a skill, so a merge or a rebase carries nothing of the overlay. `--full --local` and
`--remove` take out only what the record names.

What this module decides: what the overlay writes and removes, the state of each part for
`--check`, and the mode a worktree reads as (`worktree_mode`). What it does not decide: the render
(it asks `adopt.install` for the facts-only plan and takes `AGENTS.md` from it), how files are
written (`fileplan.write`, by the caller), or Git ignores: it never writes `.git` or the root
`.gitignore`, and warns where Git does not ignore an overlay file. Every other harness is refused
before a write. Standard library only.

This module imports `adopt` inside the functions that plan, so that `adopt` can import it.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any, NoReturn

from outcomebound_tools import discovery, fileplan, textio

if TYPE_CHECKING:
    from outcomebound_tools.adopt import Settings

RECORD = ".outcomebound/overlay.json"
MANIFEST = ".outcomebound/manifest.json"
FORMAT_VERSION = 1
SETTINGS = ".claude/settings.local.json"
EXCLUDES = "claudeMdExcludes"
# The harnesses an overlay reaches, and the file each reads in place of the committed text.
FILES = {"codex": "AGENTS.override.md", "claude-code": "CLAUDE.local.md"}
HOSTS = ("CLAUDE.md", ".claude/CLAUDE.md")
FILE, EXCLUDE = "file", "claude-md-exclude"
FULL, FACTS_ONLY, OVERLAID = "full", "facts-only", "facts-only overlay"
FACTS_ID = "project-facts"

Planned = dict[str, tuple[bytes | None, bytes | None]]
Notes = list[tuple[str, str]]


def _refuse(*reasons: str) -> NoReturn:
    from outcomebound_tools.adopt import AdoptError

    raise AdoptError(*reasons)


def _sha(data: bytes) -> str:
    return hashlib.sha256(textio.fold(data)).hexdigest()


# --- The record ----------------------------------------------------------------------------


def _parse_record(raw: bytes) -> list[dict[str, Any]]:
    """The entries of a record's bytes; ValueError where the record is not what this module
    writes."""

    document = json.loads(textio.decode(raw))
    entries = document.get("artifacts") if isinstance(document, dict) else None
    if (
        not isinstance(document, dict)
        or document.get("format_version") != FORMAT_VERSION
        or not isinstance(entries, list)
    ):
        raise ValueError(f"{RECORD} is not an overlay record of format {FORMAT_VERSION}")
    for entry in entries:
        ok = (
            isinstance(entry, dict)
            and entry.get("kind") in (FILE, EXCLUDE)
            and isinstance(entry.get("path"), str)
            and isinstance(entry.get("sha256"), str)
            and (entry["kind"] == FILE or isinstance(entry.get("entry"), str))
        )
        if not ok:
            raise ValueError(f"{RECORD} holds an entry this engine does not read")
    return entries


def read_record(target: Path) -> list[dict[str, Any]] | None:
    """The overlay record's entries, None where there is none; a record that cannot be read is a
    refusal."""

    try:
        raw = fileplan.current(target, RECORD)
        return None if raw is None else _parse_record(raw)
    except (fileplan.WriteError, OSError, ValueError) as error:
        _refuse(
            f"cannot read {RECORD}: {textio.plain(str(error))}; remove it by hand if no "
            "overlay file of it is left"
        )


def _tolerant(root: Path) -> list[dict[str, Any]]:
    """The record's entries, empty where there is none or it cannot be read, for a caller that
    only looks."""

    try:
        return read_record(root) or []
    except Exception:
        return []


def owned_paths(root: Path) -> frozenset[str]:
    """The root files the record says the overlay wrote; adopt does not count them as the
    person's when it decides whether a harness needs an import block."""

    return frozenset(entry["path"] for entry in _tolerant(root) if entry["kind"] == FILE)


def worktree_mode(root: Path) -> str | None:
    """`full`, `facts-only` or `facts-only overlay` for the install in `root`, None where it has no
    manifest. Reads files only."""

    try:
        raw = fileplan.current(root, MANIFEST)
        document = json.loads(textio.decode(raw)) if raw is not None else None
    except (fileplan.WriteError, OSError, ValueError):
        return None
    artifacts = document.get("artifacts") if isinstance(document, dict) else None
    if not isinstance(artifacts, list):
        return None
    mode = FULL
    for record in artifacts:
        if (
            isinstance(record, dict)
            and record.get("kind") == "block"
            and record.get("id") == FACTS_ID
        ):
            mode = FACTS_ONLY if record.get("mode") == FACTS_ONLY else FULL
    return OVERLAID if mode == FULL and _tolerant(root) else mode


# --- The render and the settings file ---------------------------------------------------------


def render(target: Path, source: Path) -> bytes | None:
    """The `AGENTS.md` a facts-only install would write here, None where the install is
    already that."""

    from outcomebound_tools import adopt

    planned, _, _ = adopt.install(target, source, adopt.Selection(mode=adopt.FACTS_ONLY), False)
    pair = planned.get(adopt.AGENTS)
    return None if pair is None else pair[1]


def _settings(before: bytes | None) -> Settings:
    from outcomebound_tools import adopt

    by_hand = f"merge {EXCLUDES} into it by hand"
    if before is None:
        return adopt.Settings(SETTINGS, None, {})
    try:
        text = textio.decode(before)
        data = json.loads(text)
    except (UnicodeDecodeError, ValueError) as error:
        _refuse(f"{SETTINGS} is not plain JSON ({textio.plain(str(error))}); {by_hand}")
    if not isinstance(data, dict):
        _refuse(f"{SETTINGS} is not a JSON object; {by_hand}")
    settings = adopt.Settings(SETTINGS, before, data, text)
    try:
        return settings.rewritable()
    except adopt.AdoptError:
        _refuse(
            f"{SETTINGS}: rewriting it would change more than its whitespace (a repeated key, an "
            f"escape or a number's form); {by_hand}"
        )


def _excludes(settings: Settings) -> list[str]:
    value = settings.data.get(EXCLUDES, [])
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        _refuse(f"{SETTINGS}: its {EXCLUDES} key is not a list of strings; fix it by hand")
    return list(value)


def _set_excludes(settings: Settings, add: list[str], drop: list[str]) -> None:
    """Merge: `add` joins the list, `drop` leaves it, every other key and entry stays."""

    held = _excludes(settings)
    kept = [item for item in held if item not in drop]
    kept.extend(item for item in add if item not in kept)
    if kept == held:
        return
    if kept:
        settings.data[EXCLUDES] = kept
    else:
        del settings.data[EXCLUDES]
    settings.changed = True


def _hosts(target: Path) -> list[str]:
    """The absolute path of each CLAUDE.md the worktree holds, which Claude Code would load beside
    `CLAUDE.local.md`."""

    return [(target / host).as_posix() for host in HOSTS if os.path.lexists(target / host)]


# --- Install ----------------------------------------------------------------------------------


def _tracked(target: Path, relative: str) -> bool:
    return bool(discovery.git_read(target, "ls-files", "-z", "--", relative))


def _unignored(target: Path, owned: list[str]) -> list[str]:
    """The paths of `owned` that Git does not ignore."""

    data = b"".join(os.fsencode(path) + b"\0" for path in owned)
    raw = discovery.git_read(target, "check-ignore", "-v", "-z", "--stdin", data=data)
    fields = os.fsdecode(raw or b"").split("\0")
    ignored = {
        path
        for _, _, pattern, path in zip(*[iter(fields)] * 4, strict=False)
        if not pattern.startswith("!")
    }
    return [path for path in owned if path not in ignored]


def _entry(kind: str, path: str, data: bytes, **more: Any) -> dict[str, Any]:
    return {"kind": kind, "path": path, **more, "sha256": _sha(data)}


def _gate(target: Path, source: Path) -> tuple[list[str], list[dict[str, Any]], bytes] | str:
    """The harnesses, the held record and the render an overlay is made from, or the reason it
    needs none; a refusal where the install is missing, a harness is out of reach or nothing
    renders."""

    from outcomebound_tools import adopt

    adopt.require_work_tree(target)
    manifest = adopt.load_manifest(target)
    if manifest.raw is None:
        _refuse(
            f"no OutcomeBound install in {target.name}; install it first, then make the overlay"
        )
    if adopt.recorded_mode(manifest.own) == adopt.FACTS_ONLY:
        return "the committed install is already facts-only, so this worktree needs no overlay"
    names = adopt.recorded_harnesses(manifest.own) or [adopt.GENERIC]
    other = [name for name in names if name not in FILES]
    if other:
        _refuse(
            f"{', '.join(other)}: UNVERIFIED that a facts-only overlay reaches it; the overlay "
            f"is written for {' and '.join(FILES)} only, so nothing was written"
        )
    rendered = render(target, source)
    if rendered is None:
        _refuse("the install renders no facts-only AGENTS.md here; nothing was written")
    return names, read_record(target) or [], rendered


def _file_changes(
    target: Path, names: list[str], held: list[dict[str, Any]], rendered: bytes
) -> tuple[Planned, list[dict[str, Any]], list[str]]:
    """Each overlay file's change, its record, and the paths that hold bytes the overlay did not
    write."""

    previous = {entry["path"]: entry for entry in held}
    changes: Planned = {}
    records = []
    edited = []
    for name in names:
        path = FILES[name]
        before = _read(target, path)
        if _tracked(target, path):
            _refuse(f"{path} is tracked by Git, so it is no overlay file; move it away first")
        entry = previous.get(path)
        ours = entry is not None and before is not None and _sha(before) == entry["sha256"]
        if before is not None and not ours and _sha(before) != _sha(rendered):
            edited.append(path)
        changes[path] = (before, textio.with_style(rendered, before))
        records.append(_entry(FILE, path, rendered, harness=name))
    return changes, records, edited


def _exclusion_changes(
    target: Path, names: list[str], held: list[dict[str, Any]]
) -> tuple[Planned, list[dict[str, Any]], Notes]:
    """The `claudeMdExcludes` change in the local settings, merged into what the file holds, and
    the record of each entry this overlay owns."""

    hosts = _hosts(target) if "claude-code" in names else []
    old = [entry for entry in held if entry["kind"] == EXCLUDE]
    if not (hosts or old):
        return {}, [], []
    before = _read(target, SETTINGS)
    settings = _settings(before)
    _set_excludes(settings, hosts, [e["entry"] for e in old if e["entry"] not in hosts])
    created = before is None or any(entry.get("created") for entry in old)
    settings.removable = created
    after = settings.after()
    changes: Planned = {SETTINGS: (before, after)} if after != before else {}
    records = [
        _entry(EXCLUDE, SETTINGS, host.encode("utf-8"), entry=host, created=created)
        for host in hosts
    ]
    notes: Notes = []
    if hosts:
        present = [host for host in HOSTS if os.path.lexists(target / host)]
        notes.append(
            (
                "note",
                f"{' and '.join(present)}: excluded for this worktree by {EXCLUDES} in "
                f"{SETTINGS}; the worktree reads {FILES['claude-code']} alone",
            )
        )
    return changes, records, notes


def plan_install(target: Path, source: Path, force: bool) -> tuple[Planned, list[str], Notes]:
    """Plan `--facts-only --local`: every change, the record last. Nothing is written here. A
    committed install that is already facts-only gets no overlay, and a harness the overlay does
    not reach is refused."""

    from outcomebound_tools import adopt

    gate = _gate(target, source)
    if isinstance(gate, str):
        return {}, [], [("note", gate)]
    names, held, rendered = gate
    changes, records, edited = _file_changes(target, names, held, rendered)
    more, kept, notes = _exclusion_changes(target, names, held)
    if edited and not force:
        _refuse(
            *(
                f"{path} exists and is not what the overlay wrote; move it away, or pass --force"
                for path in edited
            )
        )
    changes.update(more)
    record = {
        "format_version": FORMAT_VERSION,
        "engine_version": adopt.engine_version(source),
        "mode": FACTS_ONLY,
        "artifacts": [*records, *kept],
    }
    before = _read(target, RECORD)
    changes[RECORD] = (before, (json.dumps(record, indent=2) + "\n").encode("utf-8"))
    planned = {path: pair for path, pair in changes.items() if pair[0] != pair[1]}
    notes.extend(_unignored_notes(target, list(changes)))
    if planned:
        notes.extend(_overlay_notes(names))
    return planned, edited, notes


def _unignored_notes(target: Path, owned: list[str]) -> Notes:
    return [
        (
            "warning",
            f"{path}: Git does not ignore it, so a commit that stages it carries the overlay "
            "into the branch; add it to .git/info/exclude yourself, since adopt writes no .git "
            "file",
        )
        for path in _unignored(target, owned)
    ]


def _overlay_notes(names: list[str]) -> Notes:
    return [
        (
            "note",
            f"facts-only overlay: {', '.join(FILES[name] for name in names)} hold the "
            "facts-only text for this worktree alone; the committed install, the manifest and "
            "every other checkout are unchanged; `--full --local` removes it",
        ),
        (
            "note",
            "a session in an overlay worktree loaded the facts-only text and not the kernel under "
            "codex-cli 0.164.0 and Claude Code 2.1.310 (a CLAUDE.md host among them, 2026-10-26); "
            "another harness version is UNVERIFIED",
        ),
    ]


def _read(target: Path, relative: str) -> bytes | None:
    try:
        return fileplan.current(target, relative)
    except fileplan.WriteError as error:
        _refuse(str(error))


# --- Removal ----------------------------------------------------------------------------------


def plan_removal(target: Path, force: bool) -> tuple[Planned, list[str], Notes]:
    """Plan taking out what the record names: its files, its own `claudeMdExcludes` entries, and
    the record. A file whose bytes are not the record's is refused without `--force`."""

    held = read_record(target)
    if held is None:
        return {}, [], []
    changes: Planned = {}
    edited: list[str] = []
    for entry in held:
        if entry["kind"] != FILE:
            continue
        before = _read(target, entry["path"])
        if before is None:
            continue
        if _sha(before) != entry["sha256"]:
            edited.append(entry["path"])
        changes[entry["path"]] = (before, None)
    exclusions = [entry for entry in held if entry["kind"] == EXCLUDE]
    if exclusions:
        before = _read(target, SETTINGS)
        if before is not None:
            settings = _settings(before)
            _set_excludes(settings, [], [entry["entry"] for entry in exclusions])
            settings.removable = any(entry.get("created") for entry in exclusions)
            if settings.after() != before:
                changes[SETTINGS] = (before, settings.after())
    if edited and not force:
        _refuse(
            *(
                f"{path} differs from what the overlay wrote; restore it, or pass --force"
                for path in edited
            )
        )
    changes[RECORD] = (_read(target, RECORD), None)
    return {path: pair for path, pair in changes.items() if pair[0] != pair[1]}, edited, []


# --- Check ------------------------------------------------------------------------------------


def _file_state(
    target: Path, entry: dict[str, Any], rendered: Callable[[], bytes | None]
) -> tuple[str, str]:
    try:
        observed = _read(target, entry["path"])
    except Exception:
        return "edited", ""
    if observed is None:
        return "missing", "adopt <worktree> --facts-only --local writes it again"
    now = rendered()
    if _sha(observed) != entry["sha256"]:
        if now is not None and _sha(observed) == _sha(now):
            return "stale", "it holds what the engine now renders and the record does not"
        return "edited", ""
    if now is None or _sha(now) != entry["sha256"]:
        return (
            "stale",
            "the facts-only text moved; adopt <worktree> --facts-only --local writes it again",
        )
    return "current", ""


def _exclude_state(target: Path, entry: dict[str, Any]) -> tuple[str, str]:
    try:
        before = _read(target, SETTINGS)
        if before is None:
            return "missing", ""
        return (
            ("current", "") if entry["entry"] in _excludes(_settings(before)) else ("missing", "")
        )
    except Exception:
        return "edited", ""


def check(target: Path, source: Path) -> list[str]:
    """Print the worktree's overlay mode and the state of each part (`current`, `edited`, `stale`
    or `missing`), and return the states. Prints nothing where the worktree has no overlay."""

    held = _tolerant(target)
    if not held:
        return []
    mode = worktree_mode(target)
    base = "a full install" if mode == OVERLAID else "a facts-only install"
    print(
        f"{'note':<8} {OVERLAID} over {base}"
        + (
            ""
            if mode == OVERLAID
            else ": the committed install is already facts-only, so the overlay is not needed; "
            "`adopt <worktree> --full --local` removes it"
        )
    )
    cache: list[bytes | None] = []

    def rendered() -> bytes | None:
        if not cache:
            try:
                cache.append(render(target, source))
            except Exception:
                cache.append(None)
        return cache[0]

    found = []
    for entry in held:
        if entry["kind"] == FILE:
            state, detail = _file_state(target, entry, rendered)
            name = f"{entry['path']} ({OVERLAID})"
        else:
            state, detail = _exclude_state(target, entry)
            name = f"{entry['path']} ({EXCLUDES}: {textio.visible(entry['entry'])})"
        print(f"{state:<8} {name}" + (f": {detail}" if detail else ""))
        found.append(state)
    return found
