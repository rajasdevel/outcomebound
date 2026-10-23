#!/usr/bin/env python3
"""Release notes from the commit subjects since the last release tag.

    python3 scripts/release_notes.py --dry-run   print the notes the next release will get
    python3 scripts/release_notes.py --check     fail when CHANGELOG.md's Unreleased section was
                                                 edited by hand, or a commit subject since the
                                                 last tag has no type this script knows

A subject is `type: text` or `type(scope): text`. `feat` goes under Added, `fix` under Fixed,
`perf` and `refactor` under Changed; `docs`, `test`, `chore`, `ci`, `build`, `style` and `release`
are left out of the notes. At a release, the maintainer copies the dry run into CHANGELOG.md
under the new version's heading; nobody writes under Unreleased.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

SECTIONS = {"feat": "Added", "fix": "Fixed", "perf": "Changed", "refactor": "Changed"}
QUIET = frozenset({"docs", "test", "chore", "ci", "build", "style", "release"})
SUBJECT = re.compile(r"^(?P<type>[a-z]+)(?:\([\w./-]+\))?!?: (?P<text>\S.*)$")
UNRECOGNISED = "Not recognised"
CHANGELOG = Path("CHANGELOG.md")


def git(*arguments: str) -> str:
    done = subprocess.run(
        ["git", *arguments], capture_output=True, text=True, encoding="utf-8", check=True
    )
    return done.stdout


def subjects() -> tuple[str, list[str]]:
    """The last release tag, and the subjects of the commits since it, oldest first."""

    tag = git("describe", "--tags", "--abbrev=0", "--match", "v*").strip()
    listed = git("log", "--reverse", "--no-merges", "--format=%s", f"{tag}..HEAD")
    return tag, [line for line in listed.splitlines() if line.strip()]


def notes(found: list[str]) -> dict[str, list[str]]:
    """The notes by section; subjects with no known type under "Not recognised"."""

    grouped: dict[str, list[str]] = {}
    for subject in found:
        match = SUBJECT.match(subject)
        if match and match["type"] in QUIET:
            continue
        if match and match["type"] in SECTIONS:
            grouped.setdefault(SECTIONS[match["type"]], []).append(match["text"])
        else:
            grouped.setdefault(UNRECOGNISED, []).append(subject)
    return grouped


def unreleased(text: str) -> str:
    """What CHANGELOG.md holds under its Unreleased heading."""

    match = re.search(r"(?ms)^## Unreleased[^\n]*\n(.*?)(?=^## |\Z)", text)
    return match[1].strip() if match else ""


def dry_run() -> int:
    tag, found = subjects()
    grouped = notes(found)
    print(f"## Unreleased ({len(found)} commits since {tag})")
    for section in ("Added", "Fixed", "Changed", UNRECOGNISED):
        if section in grouped:
            print(f"\n### {section}\n")
            print("\n".join(f"- {line}" for line in grouped[section]))
    if not grouped:
        print("\nNothing to release yet.")
    return 0


def check() -> int:
    problems = []
    if unreleased(CHANGELOG.read_text(encoding="utf-8")):
        problems.append(
            "CHANGELOG.md: the Unreleased section was edited by hand; the notes are written "
            "from commit subjects at release (docs/releasing.md)"
        )
    tag, found = subjects()
    problems += [
        f"commit subject since {tag} has no known type: {subject!r}"
        for subject in notes(found).get(UNRECOGNISED, [])
    ]
    for problem in problems:
        print(problem, file=sys.stderr)
    print("release notes check: FAIL" if problems else "release notes check: PASS")
    return 1 if problems else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Release notes from commit subjects.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="print the next release's notes")
    mode.add_argument("--check", action="store_true", help="check CHANGELOG.md and subjects")
    args = parser.parse_args(argv)
    return dry_run() if args.dry_run else check()


if __name__ == "__main__":
    raise SystemExit(main())
