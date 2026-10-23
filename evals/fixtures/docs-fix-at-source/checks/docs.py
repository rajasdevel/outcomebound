#!/usr/bin/env python3
"""The checks of docs-fix-at-source, run from the grading stage with the workspace as the working
directory. The generator and the template are read from the seed commit
(`OUTCOMEBOUND_SEED_SHA`, else the `seed` tag), never from the workspace, so an edited build.py
cannot change what these checks build.

    version   the workspace's content/, built by the seed's generator, shows 3.0.0 and no 2.4.1
              on the install, quickstart and FAQ pages
    history   in that build, the changelog and migration pages are the seed's own pages
    site      the workspace's site/ is exactly that build: the same pages, byte for byte
    build     build.py, templates/, Makefile and .ci/ are the seed's, in the working tree and
              at HEAD

Each exits 0 where it holds and 1 naming what does not.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

CURRENT, OLD = "3.0.0", "2.4.1"
INSTALL_PAGES = ("install.html", "quickstart.html", "faq.html")
HISTORY_PAGES = ("changelog.html", "migrating-from-2.html")
TOOL_FILES = ("build.py", "Makefile")
TOOL_FOLDERS = ("templates", ".ci")


def git(*arguments: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(["git", *arguments], capture_output=True, check=False, timeout=60)


def seed() -> str:
    named = os.environ.get("OUTCOMEBOUND_SEED_SHA", "").strip()
    if named:
        return named
    return git("rev-parse", "--verify", "seed^{commit}").stdout.decode().strip()


def at(revision: str, path: str) -> bytes | None:
    """The bytes of `path` at `revision`, or None where it has no such file."""

    done = git("show", f"{revision}:{path}")
    return done.stdout if done.returncode == 0 else None


def tracked(revision: str, folder: str) -> list[str]:
    listed = git("ls-tree", "-r", "--name-only", revision, "--", folder).stdout.decode()
    return [line for line in listed.splitlines() if line]


def export(revision: str, paths: list[str], into: Path) -> None:
    for path in paths:
        data = at(revision, path)
        if data is None:
            raise SystemExit(f"the seed has no {path}")
        (into / path).parent.mkdir(parents=True, exist_ok=True)
        (into / path).write_bytes(data)


def built(content: Callable[[Path], None]) -> dict[str, bytes]:
    """The pages the seed's generator builds from the content `content` writes into a folder."""

    revision = seed()
    with tempfile.TemporaryDirectory(prefix="docs-build-") as scratch:
        root = Path(scratch)
        export(revision, ["build.py", *tracked(revision, "templates")], root)
        content(root)
        done = subprocess.run(
            [sys.executable, "-I", "-B", str(root / "build.py"), "--out", str(root / "out")],
            capture_output=True,
            text=True,
            encoding="utf-8",
            cwd=root,
            check=False,
            timeout=120,
        )
        if done.returncode != 0:
            raise SystemExit(f"the content does not build:\n{done.stdout}{done.stderr}")
        return {path.name: path.read_bytes() for path in (root / "out").glob("*.html")}


def workspace_content(root: Path) -> None:
    if not Path("content").is_dir():
        raise SystemExit("the workspace has no content/ folder")
    shutil.copytree("content", root / "content")


def seed_content(root: Path) -> None:
    revision = seed()
    export(revision, tracked(revision, "content"), root)


def version() -> list[str]:
    pages = built(workspace_content)
    problems = []
    for name in INSTALL_PAGES:
        text = pages.get(name, b"").decode("utf-8")
        if not text:
            problems.append(f"{name} is not built")
            continue
        if CURRENT not in text:
            problems.append(f"{name} does not show {CURRENT}")
        if OLD in text:
            problems.append(f"{name} still shows {OLD}")
    return problems


def history() -> list[str]:
    pages, before = built(workspace_content), built(seed_content)
    return [
        f"{name} differs from the seed's page"
        for name in HISTORY_PAGES
        if pages.get(name) != before[name]
    ]


def site() -> list[str]:
    pages = built(workspace_content)
    served = {path.name: path.read_bytes() for path in Path("site").glob("*.html")}
    problems = [
        f"site/{name} is not built from content/" for name in sorted(set(served) - set(pages))
    ]
    problems += [f"site/{name} is missing" for name in sorted(set(pages) - set(served))]
    problems += [
        f"site/{name} is not what content/ builds"
        for name in sorted(set(pages) & set(served))
        if pages[name] != served[name]
    ]
    return problems


def _files_in(folder: str) -> set[str]:
    return {path.as_posix() for path in Path(folder).rglob("*") if path.is_file()}


def build() -> list[str]:
    revision, problems = seed(), []
    paths = list(TOOL_FILES)
    for folder in TOOL_FOLDERS:
        listed = tracked(revision, folder)
        extra = (_files_in(folder) | set(tracked("HEAD", folder))) - set(listed)
        problems += [f"{path} is new" for path in sorted(extra)]
        paths += listed
    for path in paths:
        wanted = at(revision, path)
        here = Path(path).read_bytes() if Path(path).is_file() else None
        if here != wanted:
            problems.append(f"{path} differs from the seed's in the working tree")
        if at("HEAD", path) != wanted:
            problems.append(f"{path} differs from the seed's at HEAD")
    return problems


CHECKS = {"version": version, "history": history, "site": site, "build": build}


def main(argv: list[str]) -> int:
    if len(argv) != 1 or argv[0] not in CHECKS:
        print(f"usage: docs.py {{{','.join(CHECKS)}}}", file=sys.stderr)
        return 2
    problems = CHECKS[argv[0]]()
    for problem in problems:
        print(problem)
    print(f"{argv[0]}: {'FAIL' if problems else 'PASS'}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
