#!/usr/bin/env python3
"""The checks of docs-fix-at-source, run from the grading stage with the workspace as the working
directory. The seed's generator, template, Makefile, CI file and content are read from
`baseline.json` beside this file, which setup wrote into the grading stage before the run: never
from the workspace or its Git objects. Git is read only for HEAD, with replacement objects off.

    version   the workspace's content/, built by the seed's generator: the install and quickstart
              pages hold the command `pip install examplectl==3.0.0` in a code block, and no
              other install command; on those pages and the FAQ, 3.0.0 is the only version
              number of the form x.y.z
    history   in that build, the changelog and migration pages are the seed's own pages
    site      every page the seed builds is still built and served, site/ is exactly that build,
              and the seed's generator's own check (`build.py --check`: site/ current, no broken
              link) passes on the workspace's content and site/
    build     build.py, templates/, Makefile and .ci/ are the seed's, in the working tree and at
              HEAD, with no file added under templates/ or .ci/

Each exits 0 where it holds and 1 naming what does not. A check prints `unjudged:` and exits 3
only where its preflight, which reads nothing of the workspace, fails: no git in a PATH entry
that is absolute and outside the workspace and the stage (a git the run put in the workspace is
never used), or an unreadable baseline.json in the stage. Every later git call runs that git by
its absolute path. Anything the workspace causes (a file that cannot be read, a broken symlink, a
command that does not finish) is a failure.
"""

from __future__ import annotations

import base64
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path

HERE = Path(__file__).resolve().parent
CURRENT, OLD = "3.0.0", "2.4.1"
COMMAND = f"pip install examplectl=={CURRENT}"
COMMAND_PAGES = ("install.html", "quickstart.html")
VERSION_PAGES = (*COMMAND_PAGES, "faq.html")
HISTORY_PAGES = ("changelog.html", "migrating-from-2.html")
TOOL_FILES = ("build.py", "Makefile")
TOOL_FOLDERS = ("templates", ".ci")
# A version number of the form x.y.z with whatever is glued to it (3.0.01, 3.0.0rc1, v3.0.0).
VERSION = re.compile(r"[0-9A-Za-z.+-]*\d\.\d+\.\d[0-9A-Za-z.+-]*")
CODE = re.compile(r"<pre><code>(.*?)</code></pre>", re.DOTALL)
UNJUDGED_EXIT = 3


class Unjudged(Exception):
    """The check could not run for a reason that is not the run's."""


def baseline() -> dict[str, bytes]:
    """The seed's files that these checks trust, by path."""

    try:
        stored = json.loads((HERE / "baseline.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as problem:
        raise Unjudged(f"cannot read the stage's baseline.json: {problem}") from problem
    return {path: base64.b64decode(data) for path, data in stored.items()}


def at_head(path: str) -> bytes | None:
    """The bytes of `path` in the workspace's HEAD commit, or None where it has no such file."""

    done = subprocess.run(
        [TOOLS["git"], "--no-replace-objects", "show", f"HEAD:{path}"],
        capture_output=True, check=False, timeout=60,
    )  # fmt: skip
    return done.stdout if done.returncode == 0 else None


def head_files(folder: str) -> set[str]:
    argv = [TOOLS["git"], "--no-replace-objects", "ls-tree", "-r", "--name-only", "HEAD"]
    done = subprocess.run(
        [*argv, "--", folder],
        capture_output=True, text=True, encoding="utf-8", check=False, timeout=60,
    )  # fmt: skip
    return {line for line in done.stdout.splitlines() if line}


def tool(into: Path) -> None:
    """The seed's generator and template, written into `into`."""

    for path, data in baseline().items():
        if path == "build.py" or path.startswith("templates/"):
            (into / path).parent.mkdir(parents=True, exist_ok=True)
            (into / path).write_bytes(data)


def generate(root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-I", "-B", str(root / "build.py"), *arguments],
        capture_output=True, text=True, encoding="utf-8", cwd=root, check=False, timeout=120,
    )  # fmt: skip


def built(content: Callable[[Path], None]) -> dict[str, bytes]:
    """The pages the seed's generator builds from the content `content` writes into a folder."""

    with tempfile.TemporaryDirectory(prefix="docs-build-") as scratch:
        root = Path(scratch)
        tool(root)
        content(root)
        done = generate(root, "--out", str(root / "out"))
        if done.returncode != 0:
            raise SystemExit(f"the content does not build:\n{done.stdout}{done.stderr}")
        return {path.name: path.read_bytes() for path in (root / "out").glob("*.html")}


def workspace_content(root: Path) -> None:
    if not Path("content").is_dir():
        raise SystemExit("the workspace has no content/ folder")
    shutil.copytree("content", root / "content")


def seed_content(root: Path) -> None:
    for path, data in baseline().items():
        if path.startswith("content/"):
            (root / path).parent.mkdir(parents=True, exist_ok=True)
            (root / path).write_bytes(data)


def _text(page: bytes) -> str:
    return html.unescape(re.sub(r"<[^>]+>", " ", page.decode("utf-8")))


def version() -> list[str]:
    pages, problems = built(workspace_content), []
    for name in VERSION_PAGES:
        if name not in pages:
            problems.append(f"{name} is not built")
            continue
        found = {token.rstrip(".") for token in VERSION.findall(_text(pages[name]))}
        if found != {CURRENT}:
            problems.append(f"{name} shows the versions {sorted(found)}, not {CURRENT} alone")
    for name in COMMAND_PAGES:
        lines = [
            line.strip()
            for block in CODE.findall(pages.get(name, b"").decode("utf-8"))
            for line in html.unescape(block).splitlines()
        ]
        installs = [line for line in lines if line.startswith("pip install")]
        if installs != [COMMAND]:
            problems.append(f"{name} has the install commands {installs}, not [{COMMAND!r}]")
    return problems


def history() -> list[str]:
    pages, before = built(workspace_content), built(seed_content)
    return [
        f"{name} differs from the seed's page"
        for name in HISTORY_PAGES
        if pages.get(name) != before[name]
    ]


def site() -> list[str]:
    pages, required = built(workspace_content), set(built(seed_content))
    served = {path.name: path.read_bytes() for path in Path("site").glob("*.html")}
    problems = [f"{name} is no longer built" for name in sorted(required - set(pages))]
    problems += [f"site/{name} is no longer served" for name in sorted(required - set(served))]
    problems += [
        f"site/{name} is not built from content/" for name in sorted(set(served) - set(pages))
    ]
    problems += [
        f"site/{name} is not what content/ builds"
        for name in sorted(set(pages) & set(served))
        if pages[name] != served[name]
    ]
    with tempfile.TemporaryDirectory(prefix="docs-check-") as scratch:
        root = Path(scratch)
        tool(root)
        workspace_content(root)
        if Path("site").is_dir():
            shutil.copytree("site", root / "site")
        done = generate(root, "--check")
        if done.returncode != 0:
            problems.append(f"the seed's site check fails:\n{(done.stdout + done.stderr).strip()}")
    return problems


def _files_in(folder: str) -> set[str]:
    return {path.as_posix() for path in Path(folder).rglob("*") if path.is_file()}


def build() -> list[str]:
    trusted, problems = baseline(), []
    for folder in TOOL_FOLDERS:
        listed = {path for path in trusted if path.startswith(f"{folder}/")}
        extra = (_files_in(folder) | head_files(folder)) - listed
        problems += [f"{path} is new" for path in sorted(extra)]
    for path in sorted(
        path for path in trusted if path in TOOL_FILES or path.startswith(TOOL_FOLDERS)
    ):
        here = Path(path).read_bytes() if Path(path).is_file() else None
        if here != trusted[path]:
            problems.append(f"{path} differs from the seed's in the working tree")
        if at_head(path) != trusted[path]:
            problems.append(f"{path} differs from the seed's at HEAD")
    return problems


CHECKS = {"version": version, "history": history, "site": site, "build": build}


TOOLS: dict[str, str] = {}


def resolve(name: str) -> str:
    """`name` as an absolute path, found only in PATH entries that are absolute and lie outside
    the workspace and the stage, with its real path outside both as well, so a tool the run put in
    the workspace is never used and cannot make a check unjudged. Unjudged where there is none."""

    roots = (Path.cwd().resolve(), HERE.parent.resolve())

    def inside(path: Path) -> bool:
        return any(path.is_relative_to(root) for root in roots)

    kept = [
        entry
        for entry in os.environ.get("PATH", "").split(os.pathsep)
        if entry
        and os.path.isabs(entry)
        and not inside(Path(entry))
        and not inside(Path(entry).resolve())
    ]
    # Every process the check starts (the project's own tools among them) gets this PATH too.
    os.environ["PATH"] = os.pathsep.join(kept)
    for entry in kept:
        candidate = Path(entry).resolve() / name
        if (
            candidate.is_file()
            and os.access(candidate, os.X_OK)
            and not inside(candidate.resolve())
        ):
            return str(candidate.resolve())
    raise Unjudged(f"no {name} on PATH outside the workspace and the stage")


def preflight() -> None:
    """What the checks need that the run cannot touch, verified apart from the workspace: git on
    PATH outside the workspace and the stage (`resolve`), and the stage's baseline. Only a
    failure here is the grader's, and only it makes the check unjudged."""

    TOOLS["git"] = resolve("git")
    baseline()


def main(argv: list[str]) -> int:
    if len(argv) != 1 or argv[0] not in CHECKS:
        print(f"usage: docs.py {{{','.join(CHECKS)}}}", file=sys.stderr)
        return 2
    try:
        preflight()
    except Unjudged as unrun:
        print(f"unjudged: {unrun}")
        return UNJUDGED_EXIT
    try:
        problems = CHECKS[argv[0]]()
    except (OSError, subprocess.TimeoutExpired, ValueError) as broken:
        # Past the preflight, a file that cannot be read, a command that does not finish or text
        # that does not decode comes from the workspace: a failure, never unjudged.
        problems = [f"the workspace cannot be judged as it stands: {broken}"]
    for problem in problems:
        print(problem)
    print(f"{argv[0]}: {'FAIL' if problems else 'PASS'}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
