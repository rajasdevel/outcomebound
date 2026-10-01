"""Selectable stack and setup fragments: parsed, detected, and rendered for a selection.

The kernel is universal: it says what kind of thing counts as Context, a Bound,
a trigger, or a Completion check. A fragment says *which* — for one technology
or one project setup. That is not doctrine, it is project truth.

The one invariant: a fragment instantiates the kernel, it never adds a rule. Its
body is limited to the kernel's own five abstractions, and every mechanism it
names must be a registry id. Both are structural checks, not string matches, so
a fragment is facts a model reads rather than a form it fills in.

An install does not paste fragment bodies into AGENTS.md: each selected fragment
is copied under `.outcomebound/fragments/` and reached through a pointer line
carrying its `condition:`, and its `edges:` join the project facts
(`outcomebound_tools.facts`). `compose --inline` emits fragment bodies, for a
delegate's role prompt that may never open a pointer.

Every failure here is a ``FragmentError``: the composer is called from shell
scripts and other tools, so a malformed fragment must arrive as one typed
message and exit 2, never as a traceback out of the parser.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections.abc import Iterable
from dataclasses import dataclass, replace
from pathlib import Path, PurePosixPath

from outcomebound_tools import adapters, home
from outcomebound_tools.mechanisms import MECHANISMS, unknown

FAMILIES = ("stack", "setup")
SLOTS = ("Context", "Bounds", "Mechanisms", "Completion bar", "Distinguish")
FRONTMATTER_KEYS = ("id", "family", "applies", "detect", "version")
# A fragment may leave these out: its pointer's condition, the irreversible acts it names, and
# the engine skills an install carries when it is selected.
OPTIONAL_KEYS = ("condition", "edges", "skills")
ID_RE = re.compile(r"\A[a-z0-9][a-z0-9-]*\Z")
SLOT_RE = re.compile(r"^\*\*(?P<slot>[^*]+)\*\* — ", re.MULTILINE)
BACKTICKED = re.compile(r"`([^`]+)`")
EXCLUDED_DIRS = frozenset({".git", "node_modules", ".venv", "venv", "__pycache__", ".outcomebound"})
# The skills every install carries, the core skill first; a selected fragment's `skills:` adds
# its own (`carried`). adopt installs each for every harness, and `inline` emits each after the
# kernel.
SKILLS = ("using-outcomebound", "decision-brief", "gather-requirements", "tests-worth-keeping")
ENGINE_ROOT = home.ROOT
PREAMBLE = (
    "Project guidance for this repository. Each block instantiates the operating contract "
    "with facts about this project; none of it adds a rule."
)


class FragmentError(ValueError):
    """A fragment is malformed, or names something outside the registry."""


@dataclass(frozen=True)
class Fragment:
    id: str
    family: str
    applies: str
    detect: tuple[str, ...]
    version: int
    body: str
    mechanisms: tuple[str, ...]
    condition: str = ""
    edges: tuple[str, ...] = ()
    skills: tuple[str, ...] = ()
    digest: str = ""
    path: Path | None = None


def _read_text(path: Path, what: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise FragmentError(f"cannot read {what} at {path}: {error}") from error


def _edges(value: str, source: str, number: int) -> tuple[str, ...]:
    """The `edges:` list: a JSON list of non-empty one-line strings."""

    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as error:
        raise FragmentError(f"{source}:{number}: edges must be a JSON list: {error}") from error
    if not isinstance(parsed, list) or not all(
        isinstance(item, str) and item.strip() for item in parsed
    ):
        raise FragmentError(f"{source}:{number}: edges must be a JSON list of non-empty strings")
    return tuple(item.strip() for item in parsed)


def _skill_names(value: str, source: str, number: int) -> tuple[str, ...]:
    """The `skills:` list: a JSON list of distinct skill names, each a lowercase-hyphen id."""

    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as error:
        raise FragmentError(f"{source}:{number}: skills must be a JSON list: {error}") from error
    if not isinstance(parsed, list) or not all(
        isinstance(item, str) and ID_RE.match(item) for item in parsed
    ):
        raise FragmentError(
            f"{source}:{number}: skills must be a JSON list of lowercase-hyphen skill names"
        )
    if len(set(parsed)) != len(parsed):
        raise FragmentError(f"{source}:{number}: skills names a skill twice")
    return tuple(parsed)


def _detect_patterns(value, source: str, number: int) -> tuple[str, ...]:
    """Parse and constrain the detect list.

    Detection walks a target repository the operator did not necessarily write,
    so a pattern may only address paths beneath that target: no absolute
    pattern, no ``..``. A pattern that could escape is a defect in the fragment,
    caught when the fragment is parsed rather than when a glob runs.
    """

    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as error:
        raise FragmentError(f"{source}:{number}: detect must be a JSON list: {error}") from error
    if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
        raise FragmentError(f"{source}:{number}: detect must be a JSON list of strings")
    for pattern in parsed:
        if not pattern.strip():
            raise FragmentError(f"{source}:{number}: detect pattern must not be empty")
        parts = PurePosixPath(pattern).parts
        if pattern.startswith("/") or (parts and parts[0] == "/"):
            raise FragmentError(
                f"{source}:{number}: detect pattern {pattern!r} must be relative to the target"
            )
        if ".." in parts:
            raise FragmentError(
                f"{source}:{number}: detect pattern {pattern!r} must not leave the target root"
            )
    return tuple(parsed)


# The keys whose value is a JSON list, each with its parser.
LISTS = {"detect": _detect_patterns, "edges": _edges, "skills": _skill_names}


def _frontmatter(text: str, source: str) -> tuple[dict, str]:
    if not text.startswith("---\n"):
        raise FragmentError(f"{source}: fragment must open with a '---' frontmatter block")
    end = text.find("\n---\n", 3)
    if end == -1:
        raise FragmentError(f"{source}: frontmatter block is not closed with '---'")
    raw, body = text[4:end], text[end + 5 :]
    fields: dict = {}
    for number, line in enumerate(raw.splitlines(), 2):
        if not line.strip():
            continue
        key, separator, value = line.partition(":")
        if not separator:
            raise FragmentError(f"{source}:{number}: frontmatter line is not 'key: value'")
        key, value = key.strip(), value.strip()
        if key not in FRONTMATTER_KEYS + OPTIONAL_KEYS:
            raise FragmentError(
                f"{source}:{number}: unknown frontmatter key {key!r}; "
                f"allowed: {', '.join(FRONTMATTER_KEYS + OPTIONAL_KEYS)}"
            )
        if key in fields:
            raise FragmentError(f"{source}:{number}: duplicate frontmatter key {key!r}")
        if key in LISTS:
            fields[key] = LISTS[key](value, source, number)
        elif key == "version":
            if not value.isdigit():
                raise FragmentError(f"{source}:{number}: version must be an integer")
            fields[key] = int(value)
        else:
            if not value:
                raise FragmentError(f"{source}:{number}: {key} must not be empty")
            fields[key] = value
    missing = [key for key in FRONTMATTER_KEYS if key not in fields]
    if missing:
        raise FragmentError(f"{source}: frontmatter is missing {', '.join(missing)}")
    return fields, body


def _slot_bodies(body: str, source: str) -> dict[str, str]:
    matches = list(SLOT_RE.finditer(body))
    found = [match.group("slot").strip() for match in matches]
    if found != list(SLOTS):
        raise FragmentError(
            f"{source}: body must contain exactly the slots {list(SLOTS)} in order; got {found}"
        )
    if body[: matches[0].start()].strip():
        raise FragmentError(
            f"{source}: the body starts with prose outside the slots; a fragment states "
            "project facts inside the five slots and adds nothing beside them"
        )
    bodies = {}
    for index, match in enumerate(matches):
        stop = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        bodies[found[index]] = body[match.end() : stop].strip()
    return bodies


def parse_fragment(text: str, source: str = "<fragment>") -> Fragment:
    fields, body = _frontmatter(text, source)
    if not ID_RE.match(fields["id"]):
        raise FragmentError(f"{source}: id must be lowercase-hyphen, got {fields['id']!r}")
    if fields["family"] not in FAMILIES:
        raise FragmentError(f"{source}: family must be one of {', '.join(FAMILIES)}")
    slots = _slot_bodies(body, source)
    named = tuple(BACKTICKED.findall(slots["Mechanisms"]))
    invalid = unknown(named)
    if invalid:
        raise FragmentError(
            f"{source}: Mechanisms names unknown mechanism(s): {', '.join(invalid)}; "
            f"the registry is {', '.join(MECHANISMS)}"
        )
    return Fragment(
        id=fields["id"],
        family=fields["family"],
        applies=fields["applies"],
        detect=fields["detect"],
        version=fields["version"],
        body=body.strip(),
        mechanisms=named,
        condition=fields.get("condition", ""),
        edges=fields.get("edges", ()),
        skills=fields.get("skills", ()),
        digest=hashlib.sha256(text.encode("utf-8")).hexdigest(),
    )


def load_fragment(path) -> Fragment:
    path = Path(path)
    fragment = parse_fragment(_read_text(path, "fragment"), str(path))
    return replace(fragment, path=path)


def load_all(source_root, local=None) -> dict[str, Fragment]:
    """Load the shipped catalog, then `local`, the target's own fragment."""

    root = Path(source_root)
    catalog: dict[str, Fragment] = {}
    for family in FAMILIES:
        for path in sorted((root / "fragments" / family).glob("*.md")):
            fragment = load_fragment(path)
            if fragment.family != family:
                raise FragmentError(
                    f"{path}: family {fragment.family!r} does not match its directory"
                )
            if fragment.id in catalog:
                raise FragmentError(f"{path}: duplicate fragment id {fragment.id!r}")
            missing = [name for name in fragment.skills if not (root / "skills" / name).is_dir()]
            if missing:
                raise FragmentError(
                    f"{path}: skills names no skill in the engine: {', '.join(missing)}"
                )
            catalog[fragment.id] = fragment
    if local:
        fragment = load_fragment(local)
        catalog[fragment.id] = fragment
    return catalog


def select(catalog: dict[str, Fragment], ids) -> list[Fragment]:
    ids = list(ids)
    if not ids:
        raise FragmentError(
            "no fragments selected; pass --fragments id[,id…]. A default adoption ships no "
            "project guidance, so an empty selection writes no block rather than an empty one."
        )
    seen = set()
    duplicates = [name for name in ids if name in seen or seen.add(name)]
    if duplicates:
        # A repeated id is a typo. Deduping silently would compose a different
        # document than the one asked for and say nothing about the difference.
        raise FragmentError(
            f"duplicate fragment id(s): {', '.join(sorted(set(duplicates)))}; "
            "each fragment is composed once, in the order given"
        )
    missing = [name for name in ids if name not in catalog]
    if missing:
        available = ", ".join(sorted(catalog)) or "none — is --source an OutcomeBound checkout?"
        raise FragmentError(f"unknown fragment id(s): {', '.join(missing)}; available: {available}")
    return [catalog[name] for name in ids]


def compose_body(selected) -> str:
    """Render the block body: one section per fragment, in the order given."""

    parts = [PREAMBLE]
    for fragment in selected:
        parts.append(
            f"**{fragment.id}** ({fragment.family}) — {fragment.applies}\n\n{fragment.body}"
        )
    return "\n\n".join(parts)


def _strip_sentinels(text: str) -> str:
    return "\n".join(
        line for line in text.splitlines() if not line.startswith("<!-- outcomebound:")
    ).strip()


def _strip_frontmatter(text: str) -> str:
    if text.startswith("---\n"):
        end = text.find("\n---\n", 3)
        if end != -1:
            return text[end + 5 :].strip()
    return text.strip()


def carried(selected: Iterable[Fragment]) -> tuple[str, ...]:
    """The skills an install with these fragments carries: `SKILLS`, then each fragment's own."""

    names = list(SKILLS)
    for fragment in selected:
        names.extend(name for name in fragment.skills if name not in names)
    return tuple(names)


def inline(source_root, selected) -> str:
    """Emit kernel, the skills an install carries, and fragments as one unmanaged blob.

    For a target that cannot host a managed block — a pasted prompt, a harness
    with a single instruction field. Nothing here is upgradable in place, which
    is why the sentinels are removed rather than merely unused.
    """

    root = Path(source_root)
    kernel = _strip_sentinels(
        _read_text(root / "templates/managed-block.agents.md.tmpl", "the kernel template")
    )
    skills = [
        _strip_frontmatter(_read_text(root / "skills" / name / "SKILL.md", f"the {name} skill"))
        for name in carried(selected)
    ]
    return "\n\n".join([kernel, *skills, compose_body(selected)]) + "\n"


def _matches(root: Path, pattern: str) -> bool:
    """Does anything under ``root`` match, ignoring vendored and hidden trees?

    A hidden directory is searched only when the pattern names it, so
    ``.github/workflows/*.yml`` detects CI while a bare ``*.yml`` never reaches
    into someone's ``.cache``.
    """

    resolved = root.resolve()
    named = set(PurePosixPath(pattern).parts)
    try:
        candidates = list(root.rglob(pattern))
    except (ValueError, NotImplementedError, OSError) as error:
        raise FragmentError(f"detect pattern {pattern!r} is not usable: {error}") from error
    for match in candidates:
        try:
            relative = match.relative_to(root).parts
            inside = match.resolve().is_relative_to(resolved)
        except (ValueError, OSError):
            continue
        if not inside:
            continue
        if any(
            part in EXCLUDED_DIRS or (part.startswith(".") and part not in named)
            for part in relative[:-1]
        ):
            continue
        return True
    return False


def detect(target, catalog: dict[str, Fragment]) -> list[str]:
    """Propose fragment ids whose detect globs match under ``target``.

    Detection proposes; it never applies. Setup fragments usually ship an empty
    ``detect`` because their signals are weak and belong to a human on adopt.
    """

    root = Path(target)
    proposed = []
    for fragment in catalog.values():
        if any(_matches(root, pattern) for pattern in fragment.detect):
            proposed.append(fragment.id)
    return proposed


def _harness_table() -> dict:
    try:
        return adapters.table()
    except adapters.AdapterError as error:
        raise FragmentError(str(error)) from error


def byte_cap(harness: str | None) -> int | None:
    """The harness's documented project-document byte cap, or None if it has none.

    The table is engine data, not source-root data: it describes harnesses, so
    it is read from this checkout however the fragments were sourced.
    """

    if not harness or harness not in _harness_table():
        # An unknown harness is a note the CLI prints, not a refusal here.
        return None
    try:
        return adapters.byte_cap(harness)
    except adapters.AdapterError as error:
        # A row the table carries but cannot describe is a typed failure the
        # CLI prints, not a traceback.
        raise FragmentError(str(error)) from error


def _report_size(output: str, count: int, harness, cap, known: bool) -> None:
    """Size report on stderr, so stdout stays the composed document alone."""

    size = len(output.encode("utf-8"))
    # Say what was measured: the composed text alone, not the always-loaded
    # footprint of an installation, which adopt reports with the kernel counted.
    sys.stderr.write(
        f"fragments={count} words={len(output.split())} bytes={size} (composed text only)\n"
    )
    if harness and not known:
        sys.stderr.write(f"note: no harness row for {harness!r}; no doc_byte_cap was applied\n")
        return
    if cap is not None and size > cap:
        sys.stderr.write(
            f"warning: {size} bytes exceeds the {harness} doc_byte_cap of {cap}; that "
            "harness may truncate the project document silently\n"
        )


def _blocks(args: argparse.Namespace, catalog: dict[str, Fragment], ids: list[str]) -> str:
    """The facts and pointers blocks adopt would write into `--target`'s AGENTS.md, with
    `--harness` routed by this checkout's table, and a harness outside it as `generic`."""

    from outcomebound_tools import adopt  # adopt imports this module

    found = adopt.route(args.harness, _harness_table().get(args.harness)) if args.harness else ""
    if not isinstance(found, adopt.Route):
        found = adopt.Route(adopt.GENERIC, adopt.GENERIC_SKILLS, None)
    try:
        made = adopt.guidance(Path(args.target), [found], catalog, ids, args.done)
    except adopt.AdoptError as error:
        raise FragmentError(str(error)) from error
    return "\n\n".join(filter(None, [made.rendered.facts, made.rendered.pointers])) + "\n"


def _main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="outcomebound fragments",
        description="Fragments are facts about a stack or a setup that adopt copies under "
        ".outcomebound/fragments/ and points to from AGENTS.md. compose renders the blocks an "
        "install writes for a selection; detect proposes the ids a target's files suggest.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    compose = sub.add_parser(
        "compose",
        help="render the project-facts and guidance-pointers blocks adopt writes for a selection",
    )
    compose.add_argument(
        "--source",
        default=str(ENGINE_ROOT),
        help="engine root to read fragments, kernel and skills from (default: this checkout)",
    )
    compose.add_argument(
        "--fragments",
        default="",
        help="comma-separated fragment ids to compose, in order (default: none)",
    )
    compose.add_argument(
        "--local", help="path to a project-local fragment file, selected as the id 'local'"
    )
    compose.add_argument(
        "--inline",
        action="store_true",
        help="emit kernel, skill and fragment bodies unsentinelled, for a role prompt",
    )
    compose.add_argument(
        "--harness",
        help="harness whose skill copy the pointers name and whose doc_byte_cap the size "
        "report is measured against (default: generic)",
    )
    compose.add_argument(
        "--target", default=".", help="project whose facts are read; nothing is written to it"
    )
    compose.add_argument(
        "--done",
        action="append",
        default=[],
        metavar="CMD",
        help="a command that settles done, in run order; repeats add up",
    )

    proposal = sub.add_parser("detect", help="propose fragment ids for a target; writes nothing")
    proposal.add_argument(
        "--target", required=True, help="project root to observe; nothing is written to it"
    )
    proposal.add_argument(
        "--source",
        default=str(ENGINE_ROOT),
        help="engine root to read the fragment catalog from (default: this checkout)",
    )

    args = parser.parse_args(argv)
    try:
        catalog = load_all(args.source, getattr(args, "local", None))

        if args.command == "detect":
            proposed = detect(args.target, catalog)
            for name in proposed:
                print(name)
            if proposed:
                sys.stderr.write(
                    "proposal only — nothing was written. To apply:\n"
                    f"  outcomebound adopt {args.target} --fragments {','.join(proposed)}\n"
                )
            else:
                sys.stderr.write(
                    "no fragment detect pattern matched; nothing was written. "
                    "Select fragments explicitly.\n"
                )
            return 0

        ids = [name.strip() for name in args.fragments.split(",") if name.strip()]
        selected = select(catalog, ids)
        output = inline(args.source, selected) if args.inline else _blocks(args, catalog, ids)
        # Resolved before anything reaches stdout: an unreadable harness table is
        # a typed failure, not a traceback after half a document is emitted.
        cap = byte_cap(args.harness)
        known = not args.harness or args.harness in _harness_table()
    except FragmentError as error:
        sys.stderr.write(f"fragments: {error}\n")
        return 2

    sys.stdout.write(output)
    _report_size(output, len(selected), args.harness, cap, known)
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
