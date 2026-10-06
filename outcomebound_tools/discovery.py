"""Read-only project discovery.

The output is deliberately ephemeral: filesystem observations may become stale and
recommendations are not accepted profile choices.  This module reads only a small
allowlist of project metadata, never follows symlinks, and never executes a detected
command. In a Git work tree it does not enter what Git ignores, which one read-only
`git ls-files` names, and it never enters a nested repository: a folder holding its own
`.git`.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
import stat
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from outcomebound_tools import declared_tests, home, paths, programs, schemacheck
from outcomebound_tools.gitenv import GIT_READ_CONFIGURATION, git_environment

ROOT = home.ROOT

MAX_DEPTH = 4
MAX_ENTRIES = 10_000
MAX_RELEVANT_FILES = 512
MAX_PACKAGE_BYTES = 1_000_000
MAX_PACKAGE_SCRIPTS = 128

MARKERS = {
    "pyproject.toml": "python",
    "setup.py": "python",
    "setup.cfg": "python",
    "pytest.ini": "python",
    "tox.ini": "python",
    "requirements.txt": "python",
    "uv.lock": "python",
    "Pipfile": "python",
    "package.json": "node",
    "tsconfig.json": "node",
    "jsconfig.json": "node",
    "package-lock.json": "node",
    "pnpm-lock.yaml": "node",
    "yarn.lock": "node",
    "bun.lock": "node",
    "bun.lockb": "node",
    "go.mod": "go",
    "go.work": "go",
    "go.sum": "go",
    "composer.json": "php",
    "composer.lock": "php",
    "Cargo.toml": "rust",
    "Cargo.lock": "rust",
}

# Markers a filename alone cannot carry. A shell component is a
# directory holding scripts, and a schema component is a directory holding
# migrations, so both are observed from the directory listing the walk already
# has. Nothing here opens a file: the evidence is a path.
SHELL_SUFFIX = ".sh"
# How far below a component root a script may sit and still qualify that root.
SHELL_DEPTH = 2
# Shell scripts are counted in their own bounded population: they are read from
# every scanned directory, not only the ones a named marker matched, so sharing
# `MAX_RELEVANT_FILES` would let an unrelated file count exhaust them
# silently.
MAX_SHELL_SCRIPTS = 512
MIGRATION_DIRECTORIES = {"migrations": "sql", "alembic": "sql"}
NESTED_MIGRATION_DIRECTORIES = {("db", "migrate"): "sql"}
# `config.yaml` beside `models/` is a SQL model project's shape; neither half alone is one.
PAIRED_MARKERS = {("config.yaml", "models"): "sql"}

WORKFLOW_FILES = {
    "AGENTS.md": "project-guidance",
    "CONTRIBUTING.md": "project-workflow",
    "DEVELOPMENT.md": "project-workflow",
    "DEVELOPING.md": "project-workflow",
}

IGNORED_DIRECTORIES = {
    ".git",
    ".hg",
    ".svn",
    ".outcomebound",
    ".venv",
    "venv",
    "node_modules",
    "vendor",
    "dist",
    "build",
    "coverage",
    "__pycache__",
}

# Harness markers. A recognized directory is an OBSERVATION about the project,
# never a harness choice: `.agents/skills/` belongs to two harnesses, and bare
# `.agents/` belongs to none — it is where skills live, not evidence that any
# harness reads this repository. Whoever chooses the harness applies the
# unique/shared/multiple/no-marker rules to these candidates; nothing here does.
HARNESS_MARKER_CANDIDATES = {
    ".agents/skills/": ("amp", "codex"),
    ".claude/": ("claude-code",),
    ".codex/": ("codex",),
    ".cursor/": ("cursor",),
    ".gemini/": ("gemini",),
}

# A kind with no module contributes no guidance. `php`, `rust`, `shell` and `sql`
# are observed and named as markers, and select no module.
MODULE_FOR_KIND = {"python": "python", "node": "frontend", "go": "go"}
MODULE_ORDER = {"python": 0, "frontend": 1, "go": 2}
SENSITIVE_COMMAND = re.compile(r"(?i)(?:api[_-]?key|credential|password|secret|token)\s*=")

DISCOVERY_FORMAT_VERSION = 1

# The check-candidate allowlist. The names below are the only observed scripts
# this module OFFERS as a check; everything else stays an observation under
# `package_scripts`. The allowlist decides what is offered, never what a
# command does: a script called `test` can deploy, so every candidate carries
# the label below and none of them reaches `test-command` until the user
# confirms the command contents.
CANDIDATE_LABEL = "observed command; effects unverified"
CANDIDATE_SCRIPT_NAMES = ("check", "format:check", "lint", "test", "typecheck", "verify")
CANDIDATE_SCRIPT_PREFIXES = ("lint:", "test:")


def is_check_candidate(name) -> bool:
    """True when an observed script name is on the check-candidate allowlist."""

    return isinstance(name, str) and (
        name in CANDIDATE_SCRIPT_NAMES or name.startswith(CANDIDATE_SCRIPT_PREFIXES)
    )


def _candidates(commands) -> list[dict]:
    """Every offered command, labeled unverified and explicitly unconfirmed."""

    return [
        {"command": command, "label": CANDIDATE_LABEL, "confirmed": False} for command in commands
    ]


class DiscoveryError(ValueError):
    """The requested discovery boundary is invalid or unreadable."""


def git_read(target: Path, *arguments: str, data: bytes | None = None) -> bytes | None:
    """What one read-only git command printed in `target`, or None where it failed or Git
    cannot run. Git comes from PATH's absolute entries only (`programs.require`), so the target
    cannot supply its own, on Windows too, and nothing the target configures runs
    (`GIT_READ_CONFIGURATION`)."""

    inherited = dict(os.environ)
    inherited["PATH"] = os.pathsep.join(
        part for part in inherited.get("PATH", "").split(os.pathsep) if os.path.isabs(part)
    )
    try:
        completed = subprocess.run(
            [programs.require("git", inherited), *GIT_READ_CONFIGURATION, *arguments],
            cwd=target,
            env=git_environment(inherited),
            input=data,
            stdin=None if data is not None else subprocess.DEVNULL,
            capture_output=True,
            check=False,
        )
    except OSError:
        return None
    return completed.stdout if completed.returncode == 0 else None


def git_ignored(target: Path) -> tuple[frozenset[str], frozenset[str]] | None:
    """What Git ignores under `target`: the folders it ignores whole and the other files it
    ignores, target-relative; None where `target` is not in a Git work tree, lies in a folder
    its repository ignores, or Git cannot list it. One `git ls-files --directory` names an
    ignored folder once, so its contents are never listed."""

    inside = git_read(target, "rev-parse", "--is-inside-work-tree")
    if inside is None or inside.strip() != b"true":
        return None
    if git_read(target, "check-ignore", "-q", ".") is not None:
        return None
    raw = git_read(
        target, "ls-files", "-z", "--others", "--ignored", "--exclude-standard", "--directory"
    )
    if raw is None:
        return None
    items = [os.fsdecode(item) for item in raw.split(b"\0") if item]
    folders = frozenset(item.rstrip("/") for item in items if item.endswith("/"))
    return folders, frozenset(item for item in items if not item.endswith("/"))


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _relative(path: Path, target: Path) -> str:
    value = path.relative_to(target).as_posix()
    return value or "."


def _bounded_root(value) -> str:
    """The path grammar for a component root.

    A leading `~` and every control character (code point < 32, or DEL)
    are refused for the same reason `paths.admits` refuses
    them: `~/x` reads as a home-relative path to a shell or an operator,
    and a control byte in a reported root cannot be read back reliably
    from the ephemeral document. Absoluteness is `Path.is_absolute`.
    """

    text = os.fspath(value)
    if text == ".":
        return text
    # `Path.is_absolute` is discovery's own test and is deliberately NOT folded
    # into the shared predicate: on POSIX it agrees with the grammar's
    # leading-`/` rule and on Windows it does not, so folding them together
    # would change which roots are accepted.
    if Path(text).is_absolute() or not paths.admits(text):
        raise DiscoveryError(f"not a bounded component root: {text!r}")
    return text


def _is_regular(path: Path) -> bool:
    try:
        return stat.S_ISREG(path.lstat().st_mode)
    except OSError:
        return False


def _worktree_workflows(target: Path) -> tuple[list[dict], list[dict]]:
    """Observe the known repository-level workflow documents, without following links."""

    observed = []
    skipped = []
    for relative, kind in sorted(WORKFLOW_FILES.items()):
        path = target / relative
        if path.is_symlink():
            skipped.append({"path": relative, "reason": "symlink"})
        elif _is_regular(path):
            observed.append(
                {
                    "path": relative,
                    "kind": kind,
                    "evidence": "path presence only; content was not inspected",
                }
            )
    return observed, skipped


def _normal_roots(target: Path, roots) -> list[Path]:
    if roots is None:
        values = ["."]
    elif isinstance(roots, (str, os.PathLike)):
        values = [roots]
    else:
        values = list(roots)

    result = []
    seen = set()
    for value in values:
        relative = _bounded_root(value)
        candidate = target if relative == "." else target.joinpath(*relative.split("/"))
        cursor = target
        for part in () if relative == "." else relative.split("/"):
            cursor = cursor / part
            try:
                if stat.S_ISLNK(cursor.lstat().st_mode):
                    raise DiscoveryError(f"component root crosses a symlink: {relative}")
            except FileNotFoundError as error:
                raise DiscoveryError(f"component root does not exist: {relative}") from error
            except OSError as error:
                raise DiscoveryError(
                    f"cannot inspect component root {relative}: {error}"
                ) from error
        if not candidate.is_dir():
            raise DiscoveryError(f"component root is not a directory: {relative}")
        key = candidate.absolute()
        if key not in seen:
            seen.add(key)
            result.append(candidate)
    return result


LOCKFILES = (
    ("pnpm-lock.yaml", "pnpm"),
    ("yarn.lock", "yarn"),
    ("bun.lock", "bun"),
    ("bun.lockb", "bun"),
    ("package-lock.json", "npm"),
)


def _package_manager_evidence(marker_paths: set[str], root: str) -> list[tuple[str, str]]:
    """The lockfiles naming a package's manager: its own root's, else its workspace's.

    A workspace member usually has no lockfile of its own; the nearest enclosing
    directory up to `.` holding one answers for it.
    """

    prefix = "" if root == "." else root + "/"
    result = [
        (manager, f"{filename} indicates {manager}")
        for filename, manager in LOCKFILES
        if prefix + filename in marker_paths
    ]
    directory = PurePosixPath(root)
    while not result and root != "." and directory != PurePosixPath("."):
        directory = directory.parent
        above = "" if directory == PurePosixPath(".") else f"{directory.as_posix()}/"
        result = [
            (manager, f"{above}{filename} in an enclosing directory indicates {manager}")
            for filename, manager in LOCKFILES
            if above + filename in marker_paths
        ]
    return result


def _script_invocation(manager: str, name: str) -> str:
    if manager == "npm":
        return f"npm {name}" if name in ("test", "start", "stop", "restart") else f"npm run {name}"
    return f"{manager} {name}"


def _manager(document: dict, lock_evidence: list[tuple[str, str]]) -> dict:
    evidence = list(lock_evidence)
    declaration = document.get("packageManager")
    if declaration is not None:
        match = (
            re.fullmatch(r"(npm|pnpm|yarn|bun)@[^\s]+", declaration)
            if isinstance(declaration, str)
            else None
        )
        if match:
            name = match.group(1)
            evidence.append((name, f"package.json packageManager declares {name}"))
        else:
            evidence.append(("unknown", "package.json packageManager declaration is unusable"))
    candidates = sorted({name for name, _ in evidence})
    details = sorted({detail for _, detail in evidence})
    if len(candidates) == 1 and candidates[0] != "unknown":
        return {
            "status": "observed",
            "name": candidates[0],
            "evidence": details,
        }
    return {
        "status": "unresolved",
        "candidates": candidates,
        "evidence": details or ["no lockfile or packageManager declaration was observed"],
    }


def _read_package(path: Path, relative: str, lock_evidence: list[tuple[str, str]]) -> dict:
    try:
        size = path.lstat().st_size
        if size > MAX_PACKAGE_BYTES:
            return {
                "path": relative,
                "status": "bounded",
                "evidence": f"package.json exceeds the {MAX_PACKAGE_BYTES}-byte read limit",
                "scripts": [],
            }
        document = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {
            "path": relative,
            "status": "malformed",
            "evidence": "package.json is not valid JSON",
            "scripts": [],
        }
    except (OSError, UnicodeError):
        return {
            "path": relative,
            "status": "unreadable",
            "evidence": "package.json could not be read as UTF-8 project metadata",
            "scripts": [],
        }

    if not isinstance(document, dict):
        return {
            "path": relative,
            "status": "malformed",
            "evidence": "package.json top level is not an object",
            "scripts": [],
        }
    scripts = document.get("scripts", {})
    if not isinstance(scripts, dict):
        return {
            "path": relative,
            "status": "malformed",
            "evidence": "package.json scripts is not an object",
            "scripts": [],
        }
    if len(scripts) > MAX_PACKAGE_SCRIPTS:
        return {
            "path": relative,
            "status": "bounded",
            "evidence": f"package.json has more than {MAX_PACKAGE_SCRIPTS} scripts",
            "scripts": [],
        }

    manager = _manager(document, lock_evidence)
    observed = []
    for name, command in sorted(scripts.items()):
        if (
            not isinstance(name, str)
            or not name
            or len(name) > 128
            or any(character in name for character in "\r\n\0")
            or not isinstance(command, str)
            or len(command) > 4096
            or any(character in command for character in "\0")
        ):
            continue
        displayed = (
            "[redacted: sensitive-looking assignment]"
            if SENSITIVE_COMMAND.search(command)
            else command
        )
        invocation = (
            _script_invocation(manager["name"], name) if manager["status"] == "observed" else None
        )
        observed.append(
            {
                "name": name,
                "command": displayed,
                "invocation": invocation,
                "execution_status": "UNVERIFIED",
            }
        )
    return {
        "path": relative,
        "status": "parsed",
        "evidence": "scripts parsed as metadata; none were executed",
        "manager": manager,
        "scripts": observed,
    }


def _component_id(root: str) -> str:
    if root == ".":
        return "project"
    value = re.sub(r"[^a-z0-9]+", "-", root.lower()).strip("-")
    if not value or not value[0].isalpha():
        value = "component-" + value
    return value or "component"


def _test_options(
    target: Path | str | None, root: str, markers: list[dict], packages: list[dict]
) -> list[str]:
    """The runners this root declares, in order (`declared_tests.runner_options`)."""

    return declared_tests.runner_options(
        None if target is None else Path(target), root, markers, packages
    )


def _directory_markers(current: Path, target: Path, file_names, directory_names) -> list[dict]:
    """Markers a directory listing carries, for the kinds no filename names.

    Only `os.scandir` results the walk already produced and one `is_dir` test
    for the nested pair are read; no file is opened and nothing is executed.
    Shell is not decided here: it depends on which roots the other markers
    infer, which is only known once the whole walk is done (`_shell_markers`).
    """

    root = _relative(current, target)
    names = set(directory_names)
    rows = []
    rows.extend(
        {
            "kind": MIGRATION_DIRECTORIES[name],
            "path": _relative(current / name, target),
            "root": root,
        }
        for name in sorted(names & set(MIGRATION_DIRECTORIES))
    )
    for parts, kind in sorted(NESTED_MIGRATION_DIRECTORIES.items()):
        if parts[0] in names and (current.joinpath(*parts)).is_dir():
            rows.append(
                {"kind": kind, "path": _relative(current.joinpath(*parts), target), "root": root}
            )
    for (filename, directory), kind in sorted(PAIRED_MARKERS.items()):
        if filename in set(file_names) and directory in names:
            rows.append({"kind": kind, "path": _relative(current / filename, target), "root": root})
    return rows


def _nearest_root(path: str, roots) -> str:
    """The deepest candidate root that contains `path`; the target root contains everything.

    A script belongs to ONE component: the nearest one. `api/run.sh` beside
    `api/go.mod` is the `api` component's script, not also the target root's,
    and a component is not qualified by a script that another component owns.
    """

    deepest = "."
    for root in roots:
        if root == ".":
            continue
        if path.startswith(root + "/") and len(PurePosixPath(root).parts) > (
            0 if deepest == "." else len(PurePosixPath(deepest).parts)
        ):
            deepest = root
    return deepest


def _shell_markers(scripts, markers: list[dict]) -> list[dict]:
    """Shell roots: the target root, and every root another marker already infers.

    A shell component is a component the project already has, not any
    directory that happens to hold a script: `scripts/` beside a `pyproject.toml`
    is the same component as the package, and a script four segments below the
    target root with no component of its own qualifies nothing. Each script
    qualifies only its nearest candidate root, and only when it sits at most
    `SHELL_DEPTH` segments below it; the lexicographically first qualifying
    script is that root's marker evidence.
    """

    roots = {".", *(row["root"] for row in markers)}
    found: dict[str, str] = {}
    for path in sorted(scripts):
        root = _nearest_root(path, roots)
        prefix = "" if root == "." else root + "/"
        if 1 <= len(PurePosixPath(path[len(prefix) :]).parts) <= SHELL_DEPTH:
            found.setdefault(root, path)
    return [{"kind": "shell", "path": found[root], "root": root} for root in sorted(found)]


def _components(markers: list[dict], packages: list[dict], target=None) -> list[dict]:
    by_root: dict[str, dict] = {}
    for marker in markers:
        row = by_root.setdefault(
            marker["root"],
            {
                "id": _component_id(marker["root"]),
                "root": marker["root"],
                "modules": [],
                "evidence": [],
            },
        )
        module = MODULE_FOR_KIND.get(marker["kind"])
        if module is not None and module not in row["modules"]:
            row["modules"].append(module)
        row["evidence"].append(marker["path"])
    result = []
    for root, row in sorted(by_root.items()):
        row["modules"].sort(key=MODULE_ORDER.get)
        row["evidence"].sort()
        row["test_options"] = _test_options(target, root, markers, packages)
        row["check_candidates"] = _candidates(row["test_options"])
        result.append(row)
    return result


def discover(target, roots=None) -> dict:
    """Return dated filesystem observations without changing or executing the target.

    ``roots`` optionally bounds component-marker discovery to target-relative
    directories.  Worktree-level workflow references are still observed at the
    target root because they govern every component.
    """

    requested = Path(target).expanduser()
    try:
        if stat.S_ISLNK(requested.lstat().st_mode):
            raise DiscoveryError(f"target is a symlink: {requested}")
        if not requested.is_dir():
            raise DiscoveryError(f"target is not a directory: {requested}")
        target_path = requested.resolve(strict=True)
    except FileNotFoundError as error:
        raise DiscoveryError(f"target does not exist: {requested}") from error
    except OSError as error:
        raise DiscoveryError(f"cannot inspect target {requested}: {error}") from error

    scan_roots = _normal_roots(target_path, roots)
    ignored = git_ignored(target_path)
    ignored_folders, ignored_files = ignored or (frozenset(), frozenset())
    markers = []
    shell_scripts: list[str] = []
    shell_truncated = False
    workflow_refs = []
    skipped = []
    seen_relevant = set()
    entry_count = 0
    truncated = False
    depth_limited = False

    for scan_root in scan_roots:
        for current_text, directory_names, file_names in os.walk(
            scan_root, topdown=True, followlinks=False
        ):
            current = Path(current_text)
            relative_current = current.relative_to(scan_root)
            depth = len(relative_current.parts)
            entry_count += len(directory_names) + len(file_names)
            if entry_count > MAX_ENTRIES:
                truncated = True
                directory_names[:] = []
                break

            safe_directories = []
            for name in sorted(directory_names):
                path = current / name
                relative = _relative(path, target_path)
                try:
                    symlink = stat.S_ISLNK(path.lstat().st_mode)
                except OSError:
                    symlink = False
                if symlink:
                    skipped.append({"path": relative, "reason": "symlink"})
                elif relative in ignored_folders or os.path.lexists(path / ".git"):
                    continue
                elif name not in IGNORED_DIRECTORIES:
                    if depth < MAX_DEPTH:
                        safe_directories.append(name)
                    else:
                        depth_limited = True
            directory_names[:] = safe_directories

            if len(seen_relevant) < MAX_RELEVANT_FILES:
                for row in _directory_markers(current, target_path, file_names, safe_directories):
                    if row["path"] not in seen_relevant:
                        seen_relevant.add(row["path"])
                        markers.append(row)
            file_names[:] = [
                name
                for name in file_names
                if _relative(current / name, target_path) not in ignored_files
            ]
            for name in sorted(file_names):
                if not name.endswith(SHELL_SUFFIX) or not _is_regular(current / name):
                    continue
                if len(shell_scripts) >= MAX_SHELL_SCRIPTS:
                    shell_truncated = True
                    break
                shell_scripts.append(_relative(current / name, target_path))

            for name in sorted(file_names):
                path = current / name
                relative = _relative(path, target_path)
                marker_kind = MARKERS.get(name)
                if not marker_kind:
                    continue
                try:
                    mode = path.lstat().st_mode
                except OSError:
                    continue
                if stat.S_ISLNK(mode):
                    skipped.append({"path": relative, "reason": "symlink"})
                    continue
                if not stat.S_ISREG(mode) or relative in seen_relevant:
                    continue
                if len(seen_relevant) >= MAX_RELEVANT_FILES:
                    truncated = True
                    continue
                seen_relevant.add(relative)
                if marker_kind:
                    root = Path(relative).parent.as_posix()
                    markers.append(
                        {
                            "kind": marker_kind,
                            "path": relative,
                            "root": "." if root == "." else root,
                        }
                    )
        if truncated:
            break

    markers.extend(_shell_markers(shell_scripts, markers))
    workflow_refs, workflow_skipped = _worktree_workflows(target_path)
    skipped.extend(workflow_skipped)
    markers.sort(key=lambda row: (row["path"], row["kind"]))
    workflow_refs.sort(key=lambda row: row["path"])
    skipped = sorted({(row["path"], row["reason"]) for row in skipped})
    skipped_rows = [{"path": path, "reason": reason} for path, reason in skipped]
    marker_paths = {row["path"] for row in markers}
    packages = []
    for marker in markers:
        if Path(marker["path"]).name == "package.json":
            path = target_path.joinpath(*marker["path"].split("/"))
            lock_evidence = _package_manager_evidence(marker_paths, marker["root"])
            packages.append(_read_package(path, marker["path"], lock_evidence))
    packages.sort(key=lambda row: row["path"])

    unknown = [
        {
            "subject": "outcome",
            "reason": "a project outcome cannot be accepted from filesystem detection",
        },
        {
            "subject": "integration-mode",
            "reason": (
                "project files do not establish whether guidance-only or managed use is wanted"
            ),
        },
        {"subject": "harness", "reason": "the active harness is not established by project files"},
        {
            "subject": "required-checks",
            "reason": "path presence does not establish a policy check requirement",
        },
    ]
    for package in packages:
        if package["status"] != "parsed":
            unknown.append(
                {
                    "subject": f"package-scripts:{package['path']}",
                    "reason": package["evidence"],
                }
            )
        elif package["manager"]["status"] == "unresolved":
            unknown.append(
                {
                    "subject": f"package-manager:{package['path']}",
                    "reason": "; ".join(package["manager"]["evidence"]),
                }
            )
    if truncated or depth_limited:
        unknown.append(
            {
                "subject": "discovery-completeness",
                "reason": "the bounded entry, file, or depth limit was reached",
            }
        )

    try:
        project_state = "empty" if not any(target_path.iterdir()) else "populated"
    except OSError:
        project_state = "unknown"
    roots_report = [_relative(path, target_path) for path in scan_roots]
    limits = [
        f"component scan is limited to depth {MAX_DEPTH} and {MAX_ENTRIES} directory entries",
        "only allowlisted project metadata was read; workflow files were observed by path only",
        "symlinks were not followed and detected commands were not executed",
        "nested repositories were not entered",
        "what Git ignores was not entered"
        if ignored is not None
        else "Git listed no ignored paths here (not a Git work tree, an ignored folder, or Git "
        "could not run), so no .gitignore was applied",
    ]
    if shell_truncated:
        limits.append(
            f"shell-script collection stopped at the {MAX_SHELL_SCRIPTS}-file limit; a shell "
            "component root beyond it was not inferred"
        )
    return {
        "observed_at": _timestamp(),
        "target": str(target_path),
        "roots": roots_report,
        "observed": {
            "project_state": project_state,
            "markers": markers,
            "package_scripts": packages,
            "workflow_refs": workflow_refs,
            "harness_markers": harness_markers(target_path),
            # A harness root the project tracks and fills with skills of its
            # own, named before any native copy lands there.
            "project_skill_roots": project_skill_roots(target_path),
            # The integration-mode default asks one question about the target
            # — is this a Git working tree — so the answer is recorded as an
            # observation rather than re-derived from a path the document may
            # outlive.
            "git_target": (target_path / ".git").exists(),
            "skipped": skipped_rows,
        },
        "inferred": {"components": _components(markers, packages, target_path)},
        "unknown": unknown,
        "limits": limits,
    }


def project_skill_roots(target: Path | str) -> list[dict[str, object]]:
    """The harness skill roots the project already owns: `{path, tracked, skills}`."""

    from outcomebound_tools import adapters, harness_roots

    return [
        dict(item)
        for item in harness_roots.project_skill_roots(
            target, (adapters.native_skill_root(name) for name in adapters.harness_names())
        )
    ]


def harness_markers(target) -> list:
    """The recognized harness directories that actually exist, sorted and unique.

    Only an existing directory with no symlinked component qualifies: a file
    named `.claude`, a symlink into someone else's checkout, or a directory that
    is not on this list is not an observation about this project's harness. The
    array is sorted lexicographically and deduplicated, so two runs of the same
    target produce the same document.
    """

    root = Path(target)
    observed = set()
    for marker in HARNESS_MARKER_CANDIDATES:
        path = root
        for part in PurePosixPath(marker.rstrip("/")).parts:
            path = path / part
            if path.is_symlink() or not path.is_dir():
                path = None
                break
        if path is not None:
            observed.add(marker)
    return sorted(observed)


def validate_document(data, source_root=ROOT) -> dict:
    """Validate one ephemeral discovery document against its shipped schema."""

    if not isinstance(data, dict) or data.get("format_version") != DISCOVERY_FORMAT_VERSION:
        raise DiscoveryError(f"not a discovery document at format {DISCOVERY_FORMAT_VERSION}")
    schema_path = Path(source_root) / "schemas" / "discovery.schema.json"
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise DiscoveryError(f"cannot read {schema_path}: {error}") from error
    problems = schemacheck.validate(data, schema)
    if problems:
        raise DiscoveryError("; ".join(problems))
    return copy.deepcopy(data)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="outcomebound discovery",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "Print, as one JSON document, what a project's own files show: the markers,\n"
            "package scripts, harness files and workflows observed; the components inferred\n"
            "from them, each with its root, modules and candidate check commands; and what\n"
            "files cannot establish, such as the outcome or the harness in use. It reads a\n"
            "small allowlist of metadata files, follows no symlink and runs nothing it finds.\n"
            "Its schema is $(outcomebound home)/schemas/discovery.schema.json;\n"
            "adopt --detect reads it to propose the Done commands when CI names none."
        ),
    )
    parser.add_argument("target", help="project directory to inspect")
    parser.epilog = (
        "The emitted document is ephemeral: nothing is written into the target "
        "and observations go stale. Rerun rather than storing the output."
    )
    args = parser.parse_args(argv)
    try:
        observations = discover(args.target)
        payload = {
            "format_version": DISCOVERY_FORMAT_VERSION,
            # The document reports what was OBSERVED; nothing here executed a
            # command or loaded anything, so PASS is a statement about the scan
            # completing, never about the project or its checks.
            "result": "PASS",
            "observations": observations,
        }
    except (OSError, ValueError) as error:
        parser.error(str(error))
    json.dump(payload, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
