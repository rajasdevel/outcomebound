#!/usr/bin/env python3
"""The `structure` gate of this repository's floor: four cheap checks for rot.

Each reads what Git tracks under the root:

1. no scratch or session state is tracked: a cache, `.DS_Store`, or a path the
   repository's own .gitignore files ignore;
2. no dangling in-progress marker: a merge-conflict line in a tracked text file, or
   `WIP:` or `TODO(in-progress)` in a tracked Markdown file;
3. every script a document tells a reader to run exists: in a code span or code block
   of a tracked Markdown file, a `scripts/` or `./` path, `python3 -m
   outcomebound_tools.<module>`, `outcomebound <verb>` and `make <target>`; a draft
   spec's folder, whose design.md says `status: draft`, names what it proposes and is
   left out;
4. every tracked executable answers `--help` with exit 0, run from an empty directory.

The floor shows only the first line printed, so that line is the verdict; each problem
follows on its own line. Exit 0: no problem; 1: a problem; 2: Git cannot list the files.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from pathlib import Path

# evals/ is left out of the marker, document and entry-point checks: its README names its
# fixture repositories' scripts rather than this one's, and two of its fixture check scripts
# do not answer --help.
NOT_CHECKED = ("evals/",)
# Released changelog sections record past releases, which may name scripts that no longer exist.
HISTORY = frozenset({"CHANGELOG.md"})
# A draft spec names the commands it proposes: its folder is left out of the document check.
DRAFT = re.compile(r"\A---\n(?:.*\n)*?status: draft\n(?:.*\n)*?---\n")
# Run state that is never a project's, whatever its .gitignore says.
SCRATCH = frozenset(
    {"__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache", ".outcomebound-checks"}
)
SCRATCH_NAMES = frozenset({".DS_Store"})
CONFLICT = re.compile(r"^(?:<{7}|>{7})(?: |$)")
IN_PROGRESS = re.compile(r"\bWIP:|\bTODO\(in-progress\)")
FENCE = re.compile(r"^\s*(?:```|~~~)")
SPAN = re.compile(r"`([^`\n]+)`")
SCRIPT = re.compile(r"(?<![\w./-])(?:\./)?(scripts/[\w.-]+(?:/[\w.-]+)*)")
RELATIVE = re.compile(r"(?<![\w./-])\./([\w.-]+(?:/[\w.-]+)*\.(?:sh|py))\b")
MODULE = re.compile(r"\bpython3? -m outcomebound_tools\.(\w+)")
VERB = re.compile(r"(?:^|[\s;&|(/])outcomebound ([a-z][\w-]*)")
MAKE = re.compile(r"(?:^|[\s;&|(])make ([a-z][\w-]*)")
# The verb table in outcomebound_tools/__main__.py: one `"<verb>": "<module>",` line each.
VERB_ROW = re.compile(r'^    "([a-z][\w-]*)": "[a-z_]+",$', re.MULTILINE)
MAKE_TARGET = re.compile(r"^([A-Za-z][\w-]*)\s*:(?!=)", re.MULTILINE)
HELP_SECONDS = 60


class Unlisted(Exception):
    """Git cannot list what it tracks here."""


def _git(root: Path, *arguments: str) -> list[str]:
    """The NUL-separated entries one read-only `git` command prints."""

    try:
        done = subprocess.run(
            ["git", "-C", str(root), *arguments], capture_output=True, check=False, timeout=60
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise Unlisted(f"git could not run: {error}") from error
    if done.returncode != 0:
        raise Unlisted(done.stderr.decode("utf-8", "replace").strip() or "git failed")
    return [entry for entry in done.stdout.decode("utf-8", "surrogateescape").split("\0") if entry]


def _checked(path: str) -> bool:
    return not path.startswith(NOT_CHECKED)


def _text(path: Path) -> str | None:
    """A tracked regular file's text, or None for a link, a binary or an unreadable file."""

    if path.is_symlink() or not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def scratch(root: Path, tracked: list[str]) -> list[str]:
    ignored = set(_git(root, "ls-files", "-z", "-c", "-i", "--exclude-per-directory=.gitignore"))
    return [
        f"scratch or session state is tracked: {path}"
        for path in tracked
        if path in ignored
        or SCRATCH.intersection(path.split("/"))
        or path.rsplit("/", 1)[-1] in SCRATCH_NAMES
    ]


def markers(root: Path, tracked: list[str]) -> list[str]:
    problems: list[str] = []
    for path in filter(_checked, tracked):
        text = _text(root / path)
        for number, line in enumerate((text or "").splitlines(), start=1):
            if CONFLICT.match(line) or (path.endswith(".md") and IN_PROGRESS.search(line)):
                problems.append(f"{path}:{number}: an in-progress marker: {line.strip()[:80]}")
    return problems


def _code(text: str) -> Iterator[tuple[int, str]]:
    """(line number, code) for each code-block line and each code span outside one."""

    fenced = False
    for number, line in enumerate(text.splitlines(), start=1):
        if FENCE.match(line):
            fenced = not fenced
        elif fenced:
            yield number, line
        else:
            yield from ((number, span) for span in SPAN.findall(line))


def documented(root: Path, tracked: list[str]) -> list[str]:
    verbs = {"home", *VERB_ROW.findall(_text(root / "outcomebound_tools/__main__.py") or "")}
    targets = set(MAKE_TARGET.findall(_text(root / "Makefile") or ""))
    drafts = tuple(
        path.removesuffix("design.md")
        for path in tracked
        if path.startswith("docs/specs/")
        and path.endswith("/design.md")
        and DRAFT.match(_text(root / path) or "")
    )
    problems: list[str] = []
    for path in tracked:
        if not (path.endswith(".md") and _checked(path)) or path in HISTORY:
            continue
        if drafts and path.startswith(drafts):
            continue
        for number, code in _code(_text(root / path) or ""):
            missing = [
                f"`{name}`, which does not exist"
                for name in {*SCRIPT.findall(code), *RELATIVE.findall(code)}
                if not (root / name).is_file()
            ]
            missing += [
                f"`python3 -m outcomebound_tools.{name}`, which does not exist"
                for name in MODULE.findall(code)
                if not (root / "outcomebound_tools" / f"{name}.py").is_file()
            ]
            missing += [
                f"`outcomebound {verb}`, a verb the launcher does not have"
                for verb in VERB.findall(code)
                if verb not in verbs
            ]
            missing += [
                f"`make {target}`, a target the Makefile does not have"
                for target in MAKE.findall(code)
                if target not in targets
            ]
            problems.extend(f"{path}:{number}: names {what}" for what in sorted(missing))
    return problems


def _help(root: Path, path: str, empty: str) -> str | None:
    """Why `path --help`, run from the directory `empty`, did not exit 0, or None."""

    try:
        done = subprocess.run(
            [str(root / path), "--help"],
            cwd=empty,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            check=False,
            timeout=HELP_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return f"{path} --help did not finish in {HELP_SECONDS} s"
    except OSError as error:
        return f"{path} --help could not run: {error.strerror or error}"
    return None if done.returncode == 0 else f"{path} --help exited {done.returncode}"


def entry_points(root: Path) -> list[str]:
    staged = _git(root, "ls-files", "-z", "-s")
    executables = [entry.split("\t", 1)[1] for entry in staged if entry.startswith("100755 ")]
    with tempfile.TemporaryDirectory(prefix="check-structure-") as empty:
        found = [_help(root, path, empty) for path in filter(_checked, executables)]
    return [problem for problem in found if problem is not None]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check this repository for tracked scratch state, dangling in-progress "
        "markers, documented scripts that do not exist and entry points that do not answer "
        "--help. Exit 0: no problem; 1: a problem; 2: Git cannot list the files."
    )
    parser.add_argument("root", nargs="?", default=".", help="the repository root (default: .)")
    root = Path(parser.parse_args(argv).root).resolve()
    try:
        tracked = _git(root, "ls-files", "-z")
        problems = [
            *scratch(root, tracked),
            *markers(root, tracked),
            *documented(root, tracked),
            *entry_points(root),
        ]
    except Unlisted as error:
        print(f"structure: cannot list what Git tracks in {root}: {error}")
        return 2
    if not problems:
        print(f"structure: no problem in {len(tracked)} tracked files")
        return 0
    count = f"{len(problems)} problem{'' if len(problems) == 1 else 's'}"
    print(f"structure: {count}; the first: {problems[0]}")
    print("\n".join(problems))
    return 1


if __name__ == "__main__":
    sys.exit(main())
