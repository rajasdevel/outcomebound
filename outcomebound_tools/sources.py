"""`outcomebound sources ...`: turn a source of requirements into items with a stable identity,
and check that a ledger gives every item a disposition (`docs/specs/sources/design.md`).

What this module decides: the two subcommands and their options, where `import` writes (one
manifest, `<name>.json`, in `.outcomebound/sources/` unless `--out` or `--track` says otherwise,
and a `.gitignore` of `*` beside it there), and the exits: 0 PASS; 1 FAIL or a refusal; 2
UNVERIFIED or a usage error, as `outcomebound tickets` exits.

What it does not decide: what a source means, or whether a requirement is right. It reads only
the files it is given, runs nothing, opens no connection, and writes only the manifest and that
ignore file. Standard library only.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from outcomebound_tools import fileplan, sources_check, sources_ledger, sources_manifest
from outcomebound_tools.sources_manifest import SourceRefusal, display

DEFAULT_OUT = Path(".outcomebound") / "sources"
IGNORE_FILE, IGNORE_BODY = ".gitignore", b"*\n"
_EXITS = "Exits: 0 PASS; 1 FAIL or a refusal; 2 UNVERIFIED or a usage error."


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="outcomebound sources",
        description="Read a source of requirements as items, and check a ledger of dispositions.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    imported = commands.add_parser(
        "import",
        prog="outcomebound sources import",
        help="read markdown or plain-text files into a manifest of items",
        description=(
            "Read markdown or plain-text files into a manifest: one item per heading section "
            "(per paragraph of plain text), each with an id from where it stands, a revision "
            "digest of its text, and flags for partial and suspect text. The manifest is the "
            "same for the same input. Nothing is run, and nothing but the manifest is written. "
            "A source in another format is converted to markdown first, and imported with "
            "--converted."
        ),
        epilog=(
            "The manifest holds the source text, so by default it goes to "
            f"{DEFAULT_OUT.as_posix()}/ with a .gitignore of `*` beside it, and Git ignores it. "
            "To keep the manifest in Git, pass --track (the default folder, no .gitignore) or "
            "--out (your own folder, no .gitignore); a rule that ignores a file does not "
            "untrack a file that Git already tracks. A quote, a title or a name copied from "
            "the source into a spec is in the spec, whatever the manifest's own rule. "
            "Partial text reads UNVERIFIED. " + _EXITS
        ),
    )
    imported.add_argument("paths", nargs="+", metavar="PATH", help="a markdown or text file")
    imported.add_argument(
        "--name", required=True, metavar="SLUG", help="the id prefix: a-z, 0-9, -"
    )
    imported.add_argument(
        "--out",
        metavar="DIR",
        help=f"the folder for the manifest (default {DEFAULT_OUT.as_posix()})",
    )
    imported.add_argument(
        "--as",
        dest="kind",
        choices=("markdown", "text"),
        help="read each file as this kind, whatever its name",
    )
    imported.add_argument(
        "--converted", action="store_true", help="the files are text converted from another format"
    )
    imported.add_argument(
        "--track",
        action="store_true",
        help="write to the default folder with no .gitignore, to keep the manifest in Git",
    )
    checked = commands.add_parser(
        "check",
        prog="outcomebound sources check",
        help="check a ledger against the manifests of its input set",
        description=(
            "Check the `## Sources` ledger of a file against the manifests named before it, "
            "which are the declared input set. FAIL codes: ITEM_UNDISPOSED, ITEM_UNKNOWN, "
            "ITEM_DUPLICATE, TARGET_MISSING, QUOTE_NOT_FOUND (quote occurrence only), "
            "ITEM_CHANGED, SOURCE_CHANGED, MANIFEST_DIFFERS, ROW_MALFORMED, REQUIREMENT_DUPLICATE, "
            "LEDGER_MISSING, MANIFEST_INVALID. UNVERIFIED: an absent or partial manifest, a "
            "source file not found, a not-requirement-bearing range with lexical candidates. "
            "An UNVERIFIED line hides no FAIL. Each report line says what it does not "
            "establish."
        ),
        epilog=(
            "With --skeleton, name only manifests: a ledger section with one `todo` row per "
            "item is printed, ids and revisions filled; each --range FIRST..LAST replaces the "
            "rows of its items with one row and the range's digest. " + _EXITS
        ),
    )
    checked.add_argument("paths", nargs="+", metavar="PATH", help="MANIFEST... LEDGER-FILE")
    checked.add_argument(
        "--json", action="store_true", help="print one JSON object instead of text"
    )
    checked.add_argument(
        "--root",
        metavar="DIR",
        default=".",
        help="the folder each manifest's source paths are under (default .)",
    )
    checked.add_argument(
        "--skeleton",
        action="store_true",
        help="print a ledger skeleton for the manifests named; check nothing",
    )
    checked.add_argument(
        "--range",
        action="append",
        default=[],
        metavar="FIRST..LAST",
        dest="ranges",
        help="with --skeleton: one row, digest filled, for the items from FIRST to LAST",
    )
    checked.add_argument("--verbose", action="store_true", help="also print the checks that passed")
    return parser


def _write_manifest(options: argparse.Namespace) -> tuple[Path, bool]:
    """Build and write the manifest; the file's path and whether Git ignores its folder."""

    cwd = Path.cwd()
    document = sources_manifest.build(
        options.name,
        [Path(path) for path in options.paths],
        kind=options.kind,
        converted=options.converted,
        base=cwd,
    )
    ignored = options.out is None and not options.track
    folder = Path(options.out) if options.out else DEFAULT_OUT
    folder.mkdir(parents=True, exist_ok=True)
    name = f"{options.name}.json"
    changes: dict[str, bytes | None] = {name: sources_manifest.serialize(document)}
    try:
        expected = {name: fileplan.current(folder, name)}
        if options.out is None:
            before = fileplan.current(folder, IGNORE_FILE)
            expected[IGNORE_FILE] = before
            if ignored and before is None:
                changes[IGNORE_FILE] = IGNORE_BODY
            if options.track and before == IGNORE_BODY:
                changes[IGNORE_FILE] = None
        fileplan.write(folder, changes, expected)
    except fileplan.WriteError as error:
        raise SourceRefusal("SOURCE_UNWRITABLE", str(error)) from error
    _import_report(document, folder / name, ignored)
    return folder / name, bool(document["partial"])


def _import_report(document: dict, path: Path, ignored: bool) -> None:
    items = document["items"]
    partial = [item for item in items if item["partial"]]
    suspect = [item for item in items if item["suspect"]]
    print(f"sources import: {'UNVERIFIED' if partial else 'PASS'}")
    print(
        f"wrote {display(path.as_posix())}: {len(items)} item(s) from {len(document['sources'])} "
        f"file(s); {'Git ignores this folder' if ignored else 'Git is not told to ignore it'}. "
        "Does not establish that any item is a requirement."
    )
    for source in document["sources"]:
        print(
            f"source {display(source['file'])}: raw sha256 {source['raw_sha256']}, "
            f"{source['bytes']} bytes. Does not establish that the file is the whole source."
        )
    for item in partial:
        print(
            f"UNVERIFIED partial {item['id']}: {', '.join(item['partial'])}. "
            "Does not establish what the partial item left out."
        )
    if suspect:
        print(
            f"suspect: {len(suspect)} item(s) flagged: "
            f"{', '.join(item['id'] for item in suspect)}. Advisory: a flag is not a finding, "
            "and an item with no flag is not shown safe."
        )


def _load(path: str) -> dict:
    try:
        return sources_manifest.load(Path(path))
    except ValueError as error:
        raise SourceRefusal("MANIFEST_INVALID", f"{display(path)}: {error}") from error


def _skeleton(paths: Sequence[str], ranges: Sequence[str]) -> int:
    documents = [_load(path) for path in paths]
    shown = sources_manifest.REVISION_SHOWN
    spans: dict[str, str] = {}  # first id -> row cell
    covered: set[str] = set()
    for text in ranges:
        first, _, last = text.partition("..")
        for document in documents:
            ids = [item["id"] for item in document["items"]]
            if first in ids and last in ids and ids.index(first) <= ids.index(last):
                span = document["items"][ids.index(first) : ids.index(last) + 1]
                digest = sources_check.range_revision([item["revision"] for item in span])
                spans[first] = f"{first}..{last} #{digest[:shown]}"
                covered.update(item["id"] for item in span)
                break
        else:
            raise SourceRefusal(
                "RANGE_UNKNOWN",
                f"{display(text)} is not two ids of one manifest, first before last",
            )
    rows: list[str] = []
    for document in documents:
        for item in document["items"]:
            if item["id"] in spans:
                rows.append(spans[item["id"]])
            elif item["id"] not in covered:
                rows.append(f"{item['id']} #{item['revision'][:shown]}")
    sys.stdout.write(sources_ledger.skeleton(rows))
    return 0


def _check(options: argparse.Namespace) -> int:
    *manifests, ledger = options.paths
    try:
        findings = sources_check.check(
            [Path(path) for path in manifests], Path(ledger), Path(options.root)
        )
    except (OSError, UnicodeDecodeError) as error:
        raise SourceRefusal("LEDGER_UNREADABLE", f"{display(ledger)}: {error}") from error
    if options.json:
        sys.stdout.write(sources_check.render_json(findings))
    else:
        sys.stdout.write(sources_check.render_text(findings, verbose=options.verbose))
    return sources_check.exit_code(sources_check.verdict(findings))


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    options = parser.parse_args(argv)
    try:
        if options.command == "import":
            _, partial = _write_manifest(options)
            return 2 if partial else 0
        if options.skeleton:
            return _skeleton(options.paths, options.ranges)
        if len(options.paths) < 2:
            parser.error(
                "check takes MANIFEST... LEDGER-FILE: at least one manifest, then the ledger"
            )
        return _check(options)
    except SourceRefusal as refused:
        sys.stderr.write(f"{refused.code}: {refused.text}\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
