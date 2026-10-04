#!/usr/bin/env python3
"""The `public-text` gate of this repository's floor: text that leaves this machine names no
local path, and, with the local list, no private name.

Two parts:

1. Home paths, with no list: a path under `/Users` or `/home`, a Windows `Users` folder, or
   a leading home-relative path, in the name and the text of every file Git tracks and in
   each commit message of the range, line by line. A home-relative path that this
   repository documents on purpose is in `DOCUMENTED`, with its reason. The floor runs this
   part, so it reads PASS or FAIL wherever it runs.
2. The local list, with `--private`: each term of the file that `OB_SCRUB_LIST` names, one
   term a line, `#` for a comment, matched whole-word and case-insensitively in the same
   names and text. The words of a term match across spaces and one line break, with the
   comment or quote marker of a wrapped line; invisible format characters (Unicode category
   Cf) are removed before the match. Without the list, this part reads UNVERIFIED. The list
   is private, so it stays outside this repository.

A hit is reported by its place and its kind, never by the text it matched, so the output can
go to a public log: a file whose name has a hit is named by its number in `git ls-files`
order, not by its path. The first line printed is the verdict, as the floor shows only that
line.

The range: `--range <a>..<b>`, as the floor passes it; else `--base <ref>`, read as
`<ref>..HEAD`; else `OUTCOMEBOUND_BASE`, where it names a commit; else no commit message is
read. `--stdin` reads only what it is given, such as a pull request's title and body.

Exit 0: no hit; 1: a hit; 2: UNVERIFIED (no local list for `--private`), or Git cannot read
the files or the range.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import unicodedata
from collections.abc import Iterator
from pathlib import Path

NAME = "public-text"
LIST_ENV = "OB_SCRUB_LIST"
BASE_ENV = "OUTCOMEBOUND_BASE"
# A path under a home folder, or under a Windows drive's Users folder. The character before
# the first is not part of a word, a host or a longer path segment, so a URL path such as
# example.org/home/page is not one.
HOME = re.compile(r"(?<![\w.-])/(?:Users|home)/[^/\s]+|(?<!\w)[A-Za-z]:\\Users\\[^\\\s]+")
# A home-relative path: a tilde that starts a path, then the path up to the first character
# that ends a path in prose or code.
TILDE = re.compile(r"(?<![\w.])~(?=/)[^\s`'\"()<>\[\]{},;]*")
# The home-relative paths this repository names on purpose, each with its reason. A path
# matches an entry exactly, or as a path below it.
DOCUMENTED = {
    "~/.outcomebound/research": "the link `outcomebound research clone` makes, documented",
    "~/.claude/CLAUDE.md": "Claude Code's user memory file, named as outside what adopt reads",
    "~/.gitconfig": "Git's user configuration, named in SECURITY.md",
    "~/x": "a synthetic home-relative path that tests and a docstring show as refused",
    "~/x.md": "a synthetic home-relative path that a test shows as refused",
    "~/empty": "a synthetic clone destination in a test",
}
# What may stand between two words of a term: spaces or tabs, or one line break with the spaces
# and the comment or quote marker (`#`, `>`, `//`, `*`) that starts a wrapped line. A blank line
# ends a paragraph, so two words on either side of one are not a term.
SEPARATOR = r"(?:[^\S\n]+|[^\S\n]*\n[^\S\n]*(?:(?:#+|>+|//|\*)[^\S\n]*)?)"
# How much of a file the binary probe reads, as Git's own probe does.
PROBE = 8000


class Unreadable(Exception):
    """Git cannot list the files or read the range."""


def _git(root: Path, *arguments: str) -> bytes:
    try:
        done = subprocess.run(
            ["git", "-C", str(root), *arguments], capture_output=True, check=False
        )
    except OSError as error:
        raise Unreadable(f"git could not run: {error}") from error
    if done.returncode != 0:
        message = done.stderr.decode("utf-8", "replace").strip() or "git failed"
        raise Unreadable(message.splitlines()[0])
    return done.stdout


def _commit(root: Path, ref: str) -> bool:
    try:
        _git(root, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
    except Unreadable:
        return False
    return True


def tracked(root: Path) -> Iterator[tuple[int, str, str | None]]:
    """Each tracked path with its number in `git ls-files` order, and its text, or None for a
    file that is not a regular text file; a binary file is one with a NUL byte in its first
    `PROBE` bytes."""

    listed = _git(root, "ls-files", "-z").decode("utf-8", "surrogateescape").split("\0")
    for number, path in enumerate(filter(None, listed), start=1):
        full = root / path
        data = None if full.is_symlink() or not full.is_file() else full.read_bytes()
        text = None if data is None or b"\0" in data[:PROBE] else data.decode("utf-8", "replace")
        yield number, path, text


def commit_messages(root: Path, span: str) -> Iterator[tuple[str, str]]:
    """Each commit message in `span`, as (`commit <short id>`, message)."""

    raw = _git(root, "log", "-z", "--format=%h%n%B", span).decode("utf-8", "replace")
    for entry in filter(None, raw.split("\0")):
        short, _, message = entry.partition("\n")
        yield f"commit {short}", message


def load_list(path: Path | None) -> list[re.Pattern[str]]:
    """Whole-word, case-insensitive patterns, one per term of the local list; empty when there
    is no list. Terms and text are compared in Unicode NFC form."""

    if path is None or not path.is_file():
        return []
    patterns = []
    for line in path.read_text(encoding="utf-8").splitlines():
        term = _visible(line.strip())
        if term and not term.startswith("#"):
            words = SEPARATOR.join(re.escape(word) for word in term.split())
            patterns.append(re.compile(rf"(?<!\w){words}(?!\w)", re.IGNORECASE))
    return patterns


def _visible(text: str) -> str:
    """`text` in Unicode NFC form without format characters (category Cf), such as a
    zero-width joiner or a soft hyphen; line breaks are not of that category, so line numbers
    hold."""

    normal = unicodedata.normalize("NFC", text)
    return "".join(char for char in normal if unicodedata.category(char) != "Cf")


def _documented(path: str) -> bool:
    token = path.rstrip(".:")
    return any(token == entry or token.startswith(entry + "/") for entry in DOCUMENTED)


def kinds(text: str, terms: list[re.Pattern[str]]) -> list[tuple[int, str]]:
    """Each (line, kind) of a hit in `text`, in line order: a home path line by line, and a term
    of the local list over the whole text, at the line where its match starts."""

    found = set()
    for number, line in enumerate(text.splitlines(), start=1):
        tilde = (match.group(0) for match in TILDE.finditer(line))
        if HOME.search(line) or any(not _documented(path) for path in tilde):
            found.add((number, "a home path"))
    visible = _visible(text)
    for term in terms:
        for match in term.finditer(visible):
            found.add((visible.count("\n", 0, match.start()) + 1, "matches the local list"))
    return sorted(found)


def hits(where: str, text: str, terms: list[re.Pattern[str]]) -> Iterator[str]:
    """One line per hit in `text`: its place and its kind, never the matched text."""

    for number, kind in kinds(text, terms):
        yield f"{where}:{number}: {kind}"


def _plural(count: int, word: str) -> str:
    return f"{count} {word}{'' if count == 1 else 's'}"


def _span(root: Path, given_range: str | None, base: str | None) -> tuple[str | None, str]:
    """The commit range to read, and a note on where it came from when it reads none."""

    if given_range is not None:
        return given_range, ""
    if base is not None:
        if not _commit(root, base):
            raise Unreadable(f"--base {base} names no commit")
        return f"{base}..HEAD", ""
    fallback = os.environ.get(BASE_ENV, "").strip()
    if fallback and _commit(root, fallback):
        return f"{fallback}..HEAD", ""
    if fallback:
        return None, f"; {BASE_ENV} names no commit here, so no commit message was read"
    return None, ""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check that the text Git tracks, the commit messages of a range and, with "
        "--stdin, the given text name no home path; with --private, also no term of the local "
        f"list that {LIST_ENV} names. Exit 0: no hit; 1: a hit; 2: UNVERIFIED (no local list "
        "for --private), or Git cannot read the files or the range."
    )
    parser.add_argument("root", nargs="?", default=".", help="the repository root (default: .)")
    span = parser.add_mutually_exclusive_group()
    span.add_argument("--range", help="the commits whose messages are read, as <a>..<b>")
    span.add_argument("--base", help=f"read the messages of <base>..HEAD (default: ${BASE_ENV})")
    parser.add_argument(
        "--stdin", action="store_true", help="read only standard input, not the files or commits"
    )
    parser.add_argument(
        "--private", action="store_true", help=f"also apply the local list that ${LIST_ENV} names"
    )
    args = parser.parse_args(argv)
    root = Path(args.root)

    named = os.environ.get(LIST_ENV, "").strip()
    terms = load_list(Path(named).expanduser()) if args.private and named else []
    found: list[str] = []
    try:
        if args.stdin:
            found += hits("stdin", sys.stdin.read(), terms)
            read, note = "standard input", ""
        else:
            files = commits = 0
            for number, path, text in tracked(root):
                named_hits = sorted({kind for _, kind in kinds(path, terms)})
                where = f"tracked file {number}" if named_hits else path
                found += [f"{where}: {kind} in its name" for kind in named_hits]
                if text is not None:
                    files += 1
                    found += hits(where, text, terms)
            chosen, note = _span(root, args.range, args.base)
            for where, message in commit_messages(root, chosen) if chosen else ():
                commits += 1
                found += hits(where, message, terms)
            read = f"{_plural(files, 'file')}, {_plural(commits, 'commit')}"
    except Unreadable as error:
        print(f"UNVERIFIED {NAME}: {error}")
        return 2

    missing = args.private and not terms
    what = "no home path" + (" and no term of the local list" if terms else "")
    if found:
        print(f"FAIL {NAME}: {_plural(len(found), 'hit')} ({read}{note})")
        print("\n".join(f"  {line}" for line in found))
        if missing:
            print(f"  the local list was not applied: no list in {LIST_ENV}")
        return 1
    if missing:
        print(f"UNVERIFIED {NAME}: no local list ({LIST_ENV}); {what} ({read}{note})")
        return 2
    print(f"PASS {NAME}: {what} ({read}{note})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
