"""The records command line."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from records import __version__, listing, store

DATA = Path(__file__).resolve().parent.parent / "data" / "records.csv"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="records", description="Work with dated records.")
    parser.add_argument("--version", action="version", version=f"records {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    out = commands.add_parser("export", help="write records as CSV")
    out.add_argument("--since", metavar="YYYY-MM-DD", help="records on or after this day")
    out.add_argument("--until", metavar="YYYY-MM-DD", help="records on or before this day")
    out.add_argument("--kind", help="records of this kind only")
    out.add_argument("--data", type=Path, default=DATA, help="the records file (CSV)")
    args = parser.parse_args(argv)
    chosen = listing.select(store.load(args.data), args.since, args.until, args.kind)
    listing.write(chosen, sys.stdout)
    return 0
