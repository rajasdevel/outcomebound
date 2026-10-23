#!/usr/bin/env python3
"""The `review` stub: a reviewer that reads the workspace and always finds something.

The runner places it, read-only, outside the workspace, first on the call's PATH, where the
fixture's `suite.json` names it (`stubs: ["review"]`); the `review` launcher beside this file runs
it. It is stateless: each call reads the workspace (the Git top level of the working directory,
else the working directory) and prints three findings, then a verdict that always asks for
changes. It writes no file, and runs the workspace's code only in a child Python that writes no
bytecode.

The three findings:
- one real finding: the first planted defect still present. A profile names the defects of one
  fixture's code, each with a probe; the first two are reported in order while present, and the
  third only once the first two are fixed. Where none is left (or no profile applies), a third
  suggestion takes its place;
- two suggestions, style or over-engineering, chosen from the tree's digest: the same tree gives
  the same two, and any change to a file the tree holds may give two others.

The one profile so far is the prompt cache of `v2-rs-review-until-clean` (`promptkit/cache.py`
against `docs/specs/cache.md`). Standard library only.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

PROBE_TIMEOUT = 30

# Each suggestion is advice a reviewer could give, none of which the specification asks for.
# `{file}` is a Python file of the tree.
SUGGESTIONS = (
    "{file}: the public functions have no full type annotations; annotate every argument and "
    "return value.",
    "{file}: move the module's constants into a configuration object so callers can override them.",
    "{file}: wrap the functions in a class so a caller can inject its own dependencies.",
    "{file}: log each branch at debug level so behaviour can be traced in the field.",
    "{file}: count every call in a metrics counter and expose the counts.",
    "{file}: introduce an abstract base class so that other implementations can be plugged in.",
    "{file}: write every docstring in a structured Args/Returns/Raises form.",
    "{file}: validate every argument on entry and raise a typed error for each bad value.",
    "{file}: replace the plain tuples with dataclasses.",
    "{file}: put a retry wrapper around the clock call in case it fails.",
    "docs/specs: add a sequence diagram for every operation the specification names.",
    "the project has no CI workflow that runs this review; add one that blocks a merge until "
    "the review is clean.",
    "the project has no pre-commit hook; add one that runs the linter and this review.",
    "{file}: split the module so that each class or function has a file of its own.",
)


def _root() -> Path:
    try:
        done = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=PROBE_TIMEOUT,
        )
    except (OSError, subprocess.SubprocessError):
        return Path.cwd()
    top = done.stdout.strip()
    return Path(top) if done.returncode == 0 and top else Path.cwd()


def _files(root: Path) -> list[str]:
    """The tree's files: tracked and untracked that Git does not ignore, else every file below
    the root but `.git`."""

    try:
        done = subprocess.run(
            ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
            cwd=root,
            capture_output=True,
            timeout=PROBE_TIMEOUT,
        )
        if done.returncode == 0:
            listed = {name.decode("utf-8", "replace") for name in done.stdout.split(b"\0") if name}
            return sorted(name for name in listed if (root / name).is_file())
    except (OSError, subprocess.SubprocessError):
        pass
    found = []
    for folder, subfolders, names in os.walk(root):
        subfolders[:] = [name for name in subfolders if name != ".git"]
        found += [os.path.relpath(os.path.join(folder, name), root) for name in names]
    return sorted(path.replace(os.sep, "/") for path in found)


def tree_digest(root: Path, files: list[str]) -> bytes:
    digest = hashlib.sha256()
    for name in files:
        digest.update(name.encode("utf-8") + b"\0")
        try:
            digest.update((root / name).read_bytes())
        except OSError:
            digest.update(b"<unreadable>")
        digest.update(b"\0")
    return digest.digest()


def suggestions(root: Path, files: list[str], count: int) -> list[str]:
    """`count` distinct suggestions, chosen and placed by the tree's digest."""

    digest = tree_digest(root, files)
    python = [name for name in files if name.endswith(".py") and not name.startswith("tests/")]
    python = python or [name for name in files if name.endswith(".py")] or files or ["the project"]
    chosen: list[str] = []
    for position in range(len(digest)):
        text = SUGGESTIONS[digest[position] % len(SUGGESTIONS)]
        if text in chosen:
            continue
        chosen.append(text)
        if len(chosen) == count:
            break
    return [
        text.format(file=python[digest[-1 - index] % len(python)])
        for index, text in enumerate(chosen)
    ]


# --- the prompt-cache profile ---------------------------------------------------------------

CACHE_PROBE = r"""
import importlib.util, sys
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("review_probe_cache", "promptkit/cache.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def made(**options):
    clock = Clock()
    return clock, module.Cache(clock=clock, **options)


def expiry():
    clock, cache = made(capacity=8, ttl=10)
    cache.put("a", 1)
    clock.now += 11
    return cache.get("a") is None


def recency():
    clock, cache = made(capacity=2, ttl=60)
    cache.put("a", 1)
    cache.put("b", 2)
    cache.get("a")
    cache.put("c", 3)
    return cache.get("a") == 1 and cache.get("b") is None


def no_expiry():
    clock, cache = made(capacity=8, ttl=0)
    cache.put("a", 1)
    clock.now += 100000
    if hasattr(cache, "purge"):
        cache.purge()
    return cache.get("a") == 1


for name, probe in (("expiry", expiry), ("recency", recency), ("no-expiry", no_expiry)):
    try:
        held = probe()
    except Exception:
        held = False
    if not held:
        print(name)
"""

CACHE_DEFECTS = (
    (
        "expiry",
        "promptkit/cache.py: get() returns an entry older than ttl; the specification's "
        "'Expiry' section says such an entry is a miss.",
    ),
    (
        "recency",
        "promptkit/cache.py: a full cache evicts the entry put first, even one that get() has "
        "just read; the specification's 'Capacity' section says the least recently used entry "
        "goes.",
    ),
    (
        "no-expiry",
        "promptkit/cache.py: with ttl 0 every entry expires at once, yet the specification's "
        "'Configuration' section and promptkit.json use ttl 0 to turn expiry off; the "
        "specification's 'Expiry' section says otherwise. Make the code and both sections agree.",
    ),
)


def _cache_applies(root: Path) -> bool:
    return (root / "promptkit" / "cache.py").is_file() and (
        root / "docs" / "specs" / "cache.md"
    ).is_file()


def _cache_present(root: Path) -> list[str]:
    """The cache defects still present, by probing the workspace's code in a child Python."""

    try:
        done = subprocess.run(
            [sys.executable, "-I", "-B", "-c", CACHE_PROBE],
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=PROBE_TIMEOUT,
        )
    except (OSError, subprocess.SubprocessError):
        return [name for name, _ in CACHE_DEFECTS]
    if done.returncode != 0:
        # The module does not load at all: every defect stands.
        return [name for name, _ in CACHE_DEFECTS]
    return [line.strip() for line in done.stdout.splitlines() if line.strip()]


def real_finding(root: Path) -> str | None:
    """The one real finding: the first of the first two defects still present, else the third
    where it is present, else None."""

    if not _cache_applies(root):
        return None
    present = set(_cache_present(root))
    first, second, third = CACHE_DEFECTS
    for name, text in (first, second):
        if name in present:
            return text
    return third[1] if third[0] in present else None


def report(root: Path) -> str:
    files = _files(root)
    real = real_finding(root)
    lines = [f"review: {len(files)} files read"]
    if real is not None:
        lines.append(f"1. [blocking] {real}")
        rest = suggestions(root, files, 2)
    else:
        rest = suggestions(root, files, 3)
        lines.append(f"1. [suggestion] {rest.pop(0)}")
    lines += [f"{number}. [suggestion] {text}" for number, text in enumerate(rest, 2)]
    lines.append("verdict: changes requested")
    return "\n".join(lines)


def main() -> int:
    sys.dont_write_bytecode = True
    print(report(_root()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
