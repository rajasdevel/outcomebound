"""`outcomebound size`: how big a change is against a base, and what kind of lines it holds
(`docs/specs/size/design.md`).

What this module decides: the base (`--base REF`, else the merge base of HEAD with the upstream of
the current branch, else with `origin/HEAD`, else a refusal that names `--base`); the count
(what `git diff-index --numstat` reports for the work tree against the base, plus the lines of
each untracked file that Git does not ignore, read up to `UNTRACKED_BYTES`); and the kind of
each path (`kind_of`,
first match wins). The report is one line per kind, a total, and the share of added lines that are
not `code`. Exits: 0 a report; 1 Git failed or the base cannot be found; 2 a usage error.

What it does not decide: whether a change is too big, or whether a line was needed. It runs no
project command and writes nothing: `git diff-index` reads the work tree without refreshing the
index, and Git runs with its optional locks off. Standard library only.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import stat
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path, PurePosixPath
from typing import Any

from outcomebound_tools import programs, textio
from outcomebound_tools.gitenv import GIT_READ_CONFIGURATION, git_environment

VERSION = 1
KINDS = ("code", "tests", "docs", "config", "records")
# An untracked file larger than this counts as one file, with its lines unknown.
UNTRACKED_BYTES = 2 * 1024 * 1024
# Git's own rule for a binary file: a NUL byte in the first 8000 bytes.
_BINARY_PREFIX = 8000

_RECORD_ROOTS = (".agents", ".outcomebound")
_TEST_DIRECTORIES = frozenset(
    {"test", "tests", "__tests__", "spec", "specs", "fixtures", "testdata"}
)
_TEST_NAMES = ("test_*", "*_test.*", "*.test.*", "*.spec.*", "conftest.py")
_DOC_SUFFIXES = frozenset({".md", ".rst", ".txt", ".adoc"})
_CONFIG_SUFFIXES = frozenset({".json", ".yaml", ".yml", ".toml", ".ini", ".cfg"})
_CI_ROOTS = (".github", ".circleci", ".buildkite")
_CI_NAMES = frozenset(
    {
        ".gitlab-ci.yml",
        ".travis.yml",
        "appveyor.yml",
        "azure-pipelines.yml",
        "bitbucket-pipelines.yml",
        "jenkinsfile",
    }
)
_LOCK_NAMES = frozenset({"go.sum", "package-lock.json", "pnpm-lock.yaml", "yarn.lock"})

BASE_MISSING = "SIZE_BASE_MISSING"
GIT_FAILED = "SIZE_GIT_FAILED"
TARGET_NOT_FOLDER = "SIZE_TARGET"


class SizeError(Exception):
    """A refusal: the message begins with its code."""


def kind_of(path: str) -> str:
    """The kind of a path with `/` separators, relative to the work tree: the first of `records`,
    `tests`, `docs`, `config` that matches, else `code`."""

    folded = PurePosixPath(path.casefold())
    parts = folded.parts
    name = folded.name
    folders = parts[:-1]
    if folders and folders[0] in _RECORD_ROOTS:
        return "records"
    for index, folder in enumerate(folders):
        if folder not in _TEST_DIRECTORIES:
            continue
        if folder in ("spec", "specs") and index > 0 and folders[index - 1] == "docs":
            continue
        return "tests"
    if any(fnmatch.fnmatchcase(name, pattern) for pattern in _TEST_NAMES):
        return "tests"
    if folded.suffix in _DOC_SUFFIXES or "docs" in folders:
        return "docs"
    if (
        (folders and folders[0] in _CI_ROOTS)
        or name in _CI_NAMES
        or name in _LOCK_NAMES
        or folded.suffix in _CONFIG_SUFFIXES
        or folded.suffix == ".lock"
    ):
        return "config"
    return "code"


def _git(root: Path, *arguments: str) -> tuple[int, bytes, bytes]:
    """One read-only Git command in `root`: its status and both streams. Git comes from PATH's
    absolute entries (`programs.require`), and its optional locks are off, so a read writes
    nothing."""

    try:
        completed = subprocess.run(
            [programs.require("git"), *GIT_READ_CONFIGURATION, *arguments],
            cwd=root,
            env=git_environment({**os.environ, "GIT_OPTIONAL_LOCKS": "0"}),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            check=False,
        )
    except OSError as error:
        raise SizeError(f"{GIT_FAILED}: git could not run: {textio.plain(str(error))}") from error
    return completed.returncode, completed.stdout, completed.stderr


def _git_ok(root: Path, *arguments: str) -> bytes:
    status, output, error = _git(root, *arguments)
    if status != 0:
        message = error.decode("utf-8", "replace").strip() or f"git exited {status}"
        raise SizeError(f"{GIT_FAILED}: {textio.plain(message)}")
    return output


def _commit_of(root: Path, ref: str) -> str | None:
    """The commit a ref names, or None."""

    if ref.startswith("-"):
        return None
    status, output, _ = _git(root, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
    return output.decode("utf-8", "replace").strip() if status == 0 and output.strip() else None


def resolve_base(root: Path, base: str | None) -> dict[str, str]:
    """The base: `ref`, `how` it was chosen and the `commit` that the work tree is measured
    against. An explicit ref is used as it is, so a release tag measures a change from the tag.
    The default is the merge base of HEAD with the upstream, else with `origin/HEAD`."""

    if base is not None:
        commit = _commit_of(root, base)
        if commit is None:
            raise SizeError(f"{BASE_MISSING}: --base {textio.quote(base)} names no commit")
        return {"ref": base, "how": "--base", "commit": commit}
    status, output, _ = _git(
        root, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"
    )
    upstream = output.decode("utf-8", "replace").strip() if status == 0 else ""
    if upstream and _commit_of(root, upstream):
        ref, how = upstream, "merge base of HEAD with its upstream"
    elif _commit_of(root, "refs/remotes/origin/HEAD"):
        ref, how = "origin/HEAD", "merge base of HEAD with origin/HEAD"
    else:
        raise SizeError(
            f"{BASE_MISSING}: the current branch has no upstream and there is no origin/HEAD; "
            "name the base with --base REF (for stability work, the release tag in production)"
        )
    status, output, _ = _git(root, "merge-base", "HEAD", ref)
    commit = output.decode("utf-8", "replace").strip()
    if status != 0 or not commit:
        raise SizeError(
            f"{BASE_MISSING}: HEAD and {textio.quote(ref)} share no commit; "
            "name the base with --base REF"
        )
    return {"ref": ref, "how": how, "commit": commit}


def tracked_changes(root: Path, commit: str) -> list[tuple[str, int | None, int | None]]:
    """`(path, added, removed)` for each tracked path that differs from `commit` in the work
    tree. Both counts are None for a binary file. A rename is one entry, at its new path."""

    # `diff-index`, not `diff`: the porcelain refreshes the index and writes it, even with the
    # optional locks off, and this verb writes nothing. The plumbing needs `-M` for renames.
    output = _git_ok(
        root, "diff-index", "--numstat", "-z", "-M", "--no-ext-diff", "--no-textconv", commit, "--"
    )
    tokens = output.split(b"\0")
    found: list[tuple[str, int | None, int | None]] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if not token:
            index += 1
            continue
        added, removed, path = token.split(b"\t", 2)
        if path:
            index += 1
        else:  # a rename: the old and the new path follow as two fields
            path = tokens[index + 2]
            index += 3
        binary = added == b"-"
        found.append(
            (os.fsdecode(path), None if binary else int(added), None if binary else int(removed))
        )
    return found


def untracked_paths(root: Path) -> list[str]:
    output = _git_ok(root, "ls-files", "--others", "--exclude-standard", "-z")
    return [os.fsdecode(path) for path in output.split(b"\0") if path]


def count_lines(data: bytes) -> int:
    return data.count(b"\n") + (1 if data and not data.endswith(b"\n") else 0)


def measure_untracked(root: Path, path: str) -> tuple[str, int | None]:
    """How an untracked path counts: `("lines", n)`, `("binary", None)`, `("too_large", None)`,
    or `("skipped", None)` where it is no file (a folder that is a nested repository)."""

    full = root / path
    try:
        info = full.lstat()
        if stat.S_ISLNK(info.st_mode):
            return "lines", 1
        if not stat.S_ISREG(info.st_mode):
            return "skipped", None
        if info.st_size > UNTRACKED_BYTES:
            return "too_large", None
        data = full.read_bytes()
    except OSError:
        return "skipped", None
    if b"\0" in data[:_BINARY_PREFIX]:
        return "binary", None
    return "lines", count_lines(data)


def build_report(root: Path, base: dict[str, str]) -> dict[str, Any]:
    kinds = {kind: {"files": 0, "added": 0, "removed": 0} for kind in KINDS}
    binary: list[str] = []
    too_large: list[str] = []
    skipped = 0

    def add(path: str, added: int | None, removed: int | None) -> None:
        row = kinds[kind_of(path)]
        row["files"] += 1
        row["added"] += added or 0
        row["removed"] += removed or 0

    for path, added, removed in tracked_changes(root, base["commit"]):
        if added is None:
            binary.append(path)
        add(path, added, removed)
    untracked = 0
    for path in untracked_paths(root):
        how, lines = measure_untracked(root, path)
        if how == "skipped":
            skipped += 1
            continue
        untracked += 1
        if how == "binary":
            binary.append(path)
        elif how == "too_large":
            too_large.append(path)
        add(path, lines, 0)
    present = {}
    for kind in KINDS:
        row = kinds[kind]
        if row["files"]:
            present[kind] = {**row, "net": row["added"] - row["removed"]}
    total = {
        key: sum(row[key] for row in present.values()) for key in ("files", "added", "removed")
    }
    total["net"] = total["added"] - total["removed"]
    added_all = total["added"]
    share = (
        None
        if added_all == 0
        else round((added_all - present.get("code", {}).get("added", 0)) / added_all, 4)
    )
    return {
        "version": VERSION,
        "base": base,
        "kinds": present,
        "total": total,
        "non_code_share_of_added": share,
        "untracked_files": untracked,
        "binary": sorted(binary),
        "too_large": sorted(too_large),
        "skipped_untracked": skipped,
    }


def render_json(report: dict[str, Any]) -> str:
    return json.dumps(report, indent=2, sort_keys=True) + "\n"


def render_text(report: dict[str, Any]) -> str:
    base = report["base"]
    lines = [
        f"size against {textio.plain(base['ref'])} ({base['how']}), commit {base['commit'][:12]}",
        f"{'kind':<8}{'files':>7}{'+added':>10}{'-removed':>10}{'net':>10}",
    ]

    def row(name: str, values: dict[str, int]) -> str:
        return (
            f"{name:<8}{values['files']:>7}{values['added']:>10}{values['removed']:>10}"
            f"{values['net']:>+10}"
        )

    lines.extend(row(kind, report["kinds"][kind]) for kind in KINDS if kind in report["kinds"])
    lines.append(row("total", report["total"]))
    share = report["non_code_share_of_added"]
    lines.append(
        "non-code share of added lines: "
        + ("none (no line added)" if share is None else f"{share * 100:.1f}%")
    )
    if report["binary"]:
        lines.append(f"note: {len(report['binary'])} binary file(s) count as files, with no lines")
    if report["too_large"]:
        names = ", ".join(textio.plain(path) for path in report["too_large"])
        lines.append(
            f"note: {len(report['too_large'])} untracked file(s) over {UNTRACKED_BYTES} bytes "
            f"count as files, with no lines: {names}"
        )
    if report["skipped_untracked"]:
        lines.append(
            f"note: {report['skipped_untracked']} untracked entries are no file (a nested "
            "repository, for example) and are not counted"
        )
    return "\n".join(lines) + "\n"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="outcomebound size",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "Say how big a change is against a base, and what kind of lines it holds. It counts "
            "what `git diff-index --numstat` reports for the work tree against the base "
            "(committed and "
            "uncommitted tracked changes, with Git's rename detection; `diff-index` does the "
            "reading, so the index is not refreshed), plus each untracked file "
            "that Git does not ignore, counted as added lines. A binary file counts as a file "
            "with no lines. An untracked file over 2 MB counts as a file with no lines, and a "
            "note names it.\n\n"
            "Kinds, by path, the first match wins:\n"
            "  records  anything under .agents/ or .outcomebound/\n"
            "  tests    a folder named test, tests, __tests__, spec, specs (not docs/specs), "
            "fixtures or\n"
            "           testdata; or a file named test_*, *_test.*, *.test.*, *.spec.* or "
            "conftest.py\n"
            "  docs     *.md, *.rst, *.txt, *.adoc, or anything under a docs/ folder\n"
            "  config   CI files, *.json, *.yaml, *.yml, *.toml, *.ini, *.cfg, lock files\n"
            "  code     everything else\n\n"
            "The report has one line per kind present, a total, and the share of added lines "
            "that are not code. It runs no project command and writes nothing. It does not "
            "decide whether the change is too big or whether its lines are needed."
        ),
        epilog=(
            "The default base is the merge base of HEAD with the upstream of the current "
            "branch, else with origin/HEAD; if neither exists, size refuses and names --base. "
            "A branch whose upstream is its own pushed copy measures only what is not pushed. "
            "For stability work, name the release tag in production: --base v1.4.3. An "
            "explicit base is used as it is, not as a merge base. "
            "Exits: 0 a report; 1 Git failed or the base cannot be found; 2 a usage error."
        ),
    )
    parser.add_argument(
        "target",
        nargs="?",
        default=".",
        help="a folder; the whole Git work tree holding it is measured (default: .)",
    )
    parser.add_argument("--base", metavar="REF", help="the base commit, branch or tag")
    parser.add_argument("--json", action="store_true", help="print one JSON object, not text")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    options = _parser().parse_args(argv)
    target = Path(options.target)
    if not target.is_dir():
        sys.stderr.write(f"{TARGET_NOT_FOLDER}: {textio.quote(options.target)} is not a folder\n")
        return 2
    try:
        top = _git_ok(target, "rev-parse", "--show-toplevel").decode("utf-8", "replace").strip()
        root = Path(top)
        report = build_report(root, resolve_base(root, options.base))
    except SizeError as error:
        sys.stderr.write(f"{error}\n")
        return 1
    sys.stdout.write(render_json(report) if options.json else render_text(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
