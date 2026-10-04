"""The quality floor: a project's own format, lint, type, secret and shell checks, blocking
only what is new.

What this module decides: the claims each stack is offered (`RECIPES`), what each tool's
output means (the parsers), when a finding is new (a baseline is a sorted multiset of
`path:code` lines, with no message, no position and no count), how `apply` fits a floor to a
project that already has findings (`fit`: each finding recorded, never a secret, and the
commit it was adopted at) and when a change loosens the floor (`loosening`). Every tool runs
from the project root through `validation._execute`, so it finds the project's own config:
nothing here renders, names or shadows a config file, so every rule a check applies is the
project's own. Tools come from PATH's absolute entries only, so a checkout cannot supply its
own; a claim's `prefix` (`uv run`, `docker compose run --rm app`) is found there too, and its
tool runs where the prefix puts it. No run has a time limit unless its claim sets
`timeout_seconds`.

What it does not decide: which rules hold. Those live in the project's `ruff.toml`,
`mypy.ini`, `pyproject.toml`, `setup.cfg`, `.gitleaks.toml` and `.shellcheckrc`, which the
loosening check watches and never writes. The check makes a loosening visible; it cannot
prevent one.
"""

from __future__ import annotations

import argparse
import datetime
import json
import math
import os
import re
import shutil
import sys
import tempfile
from collections import Counter
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from outcomebound_tools import fileplan, validation
from outcomebound_tools.gitenv import GIT_READ_CONFIGURATION, git_environment

FLOOR_PATH = ".outcomebound/floor.json"
BASELINE_DIR = ".outcomebound/floor"
FORMAT_VERSION = 1
PASS, FAIL, UNVERIFIED = "PASS", "FAIL", "UNVERIFIED"
GATE, BASELINE = "gate", "baseline"

# --- The shipped recipes: python and shell ------------------------------------------------
#
# `{file}` runs the argv once per tracked file matching `files`; `{range}` is `<base>..HEAD`
# under `check --base`, and without it `argv_without_base` runs instead; `{report}` is a
# scratch file the tool writes its report to.

_LEAKS = ["--redact", "--no-banner", "--report-format", "json", "--report-path", "{report}"]
RECIPES: dict[str, tuple[dict[str, Any], ...]] = {
    "python": (
        {
            "name": "python.format",
            "mode": GATE,
            "tool": "ruff",
            "min_version": "0.16.7",
            "argv": ["ruff", "format", "--check", "."],
            "parser": "ruff-format",
        },
        {
            "name": "python.lint",
            "mode": BASELINE,
            "tool": "ruff",
            "min_version": "0.16.7",
            "argv": ["ruff", "check", "--output-format", "json", "."],
            "parser": "ruff",
        },
        {
            "name": "python.types",
            "mode": BASELINE,
            "tool": "mypy",
            "min_version": "2.3.1",
            "argv": ["mypy", "--output", "json"],
            "parser": "mypy",
        },
        {
            "name": "python.secrets",
            "mode": GATE,
            "tool": "gitleaks",
            "min_version": "8.21.2",
            "argv": ["gitleaks", "git", "--log-opts={range}", *_LEAKS, "."],
            "argv_without_base": ["gitleaks", "dir", *_LEAKS, "."],
            "parser": "gitleaks",
        },
    ),
    "shell": (
        {
            "name": "shell.syntax",
            "mode": GATE,
            "tool": "bash",
            "argv": ["bash", "-n", "{file}"],
            "files": ["*.sh"],
            "parser": "bash-n",
        },
        {"name": "shell.injection", "mode": GATE, "files": ["*.sh"], "parser": "injection"},
        {
            "name": "shell.lint",
            "mode": BASELINE,
            "tool": "shellcheck",
            "min_version": "0.9.0",
            "argv": ["shellcheck", "-f", "json1", "{file}"],
            "files": ["*.sh"],
            "parser": "shellcheck",
        },
    ),
}
STACKS = (("python", ("pyproject.toml", "setup.cfg", "*.py")), ("shell", ("*.sh",)))

PARSER_NAMES = (
    "ruff-format",
    "ruff",
    "mypy",
    "gitleaks",
    "bash-n",
    "shellcheck",
    "injection",
    "exit",
)
PER_FILE_PARSERS = ("bash-n", "shellcheck", "exit")
CLAIM_FIELDS = frozenset(
    {
        "name",
        "mode",
        "tool",
        "min_version",
        "prefix",
        "argv",
        "argv_without_base",
        "files",
        "parser",
        "timeout_seconds",
    }
)
NAME = re.compile(r"[a-z][a-z0-9-]*(?:\.[a-z][a-z0-9-]*)*")
TOOL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+-]*")
DOTTED = re.compile(r"\d+(?:\.\d+)*")
VERSION_TEXT = re.compile(r"\d+(?:\.\d+)+")
COMMIT = re.compile(r"[0-9a-f]{40}(?:[0-9a-f]{24})?")
DAY = re.compile(r"\d{4}-\d{2}-\d{2}")


class FloorError(Exception):
    """The floor, or the Git repository under it, cannot be read; the message says which."""


class Unreadable(Exception):
    """A run that establishes nothing: a missing or old tool, or output no parser can read."""


class Missing(Unreadable):
    """The claim's tool is not on PATH, or is older than its min_version."""


@dataclass(frozen=True)
class Claim:
    """One check: the argv a project's own tool runs, the parser that reads it, its mode."""

    name: str
    mode: str
    parser: str
    tool: str | None = None
    argv: tuple[str, ...] = ()
    argv_without_base: tuple[str, ...] | None = None
    files: tuple[str, ...] = ()
    min_version: str | None = None
    prefix: tuple[str, ...] = ()
    timeout_seconds: float | None = None

    @property
    def baseline_path(self) -> str:
        return f"{BASELINE_DIR}/{self.name}.baseline"

    def document(self) -> dict[str, Any]:
        """The claim as `floor.json` holds it, with its empty fields left out."""

        values: dict[str, Any] = {
            "name": self.name,
            "mode": self.mode,
            "tool": self.tool,
            "min_version": self.min_version,
            "prefix": list(self.prefix),
            "argv": list(self.argv),
            "argv_without_base": None
            if self.argv_without_base is None
            else [*self.argv_without_base],
            "files": list(self.files),
            "parser": self.parser,
            "timeout_seconds": self.timeout_seconds,
        }
        return {key: value for key, value in values.items() if value not in (None, [])}


@dataclass(frozen=True)
class Adoption:
    """Where `apply` fitted the floor: the commit, the day, and how many findings it recorded
    into each claim's baseline. Without `--base`, a scan of a commit range reads only the
    commits after `commit`."""

    commit: str
    on: str
    recorded: tuple[tuple[str, int], ...] = ()

    def document(self) -> dict[str, Any]:
        values = {"commit": self.commit, "on": self.on, "recorded": dict(self.recorded)}
        return {key: value for key, value in values.items() if value}


@dataclass(frozen=True)
class Floor:
    claims: tuple[Claim, ...]
    adopted: Adoption | None = None

    def text(self) -> bytes:
        """`floor.json` as a person reads its diff: one field a line, an argv on one line."""

        def fields(values: dict[str, Any], indent: str) -> str:
            return ",\n".join(
                f"{indent}{json.dumps(k)}: {json.dumps(v)}" for k, v in values.items()
            )

        claims = ",\n".join(
            "    {\n" + fields(c.document(), "      ") + "\n    }" for c in self.claims
        )
        listed = f"[\n{claims}\n  ]" if claims else "[]"
        adopted = ""
        if self.adopted is not None:
            document = self.adopted.document()
            recorded = document.pop("recorded", {})
            lines = [fields(document, "    ")]
            if recorded:
                lines.append(f'    "recorded": {{\n{fields(recorded, "      ")}\n    }}')
            adopted = '  "adopted": {\n' + ",\n".join(lines) + "\n  },\n"
        return f'{{\n  "version": {FORMAT_VERSION},\n{adopted}  "claims": {listed}\n}}\n'.encode()


def _field(raw: dict[str, Any], key: str, where: str, pattern: re.Pattern[str]) -> str | None:
    value = raw.get(key)
    if value is not None and not (isinstance(value, str) and pattern.fullmatch(value)):
        raise FloorError(f"{where}: {key} {value!r} is not valid")
    return value


def _words(raw: dict[str, Any], key: str, where: str) -> tuple[str, ...] | None:
    value = raw.get(key)
    if value is None:
        return None
    if not isinstance(value, list) or not value or not all(isinstance(v, str) and v for v in value):
        raise FloorError(f"{where}: {key} is not a list of non-empty strings")
    return tuple(value)


def _seconds(raw: dict[str, Any], where: str) -> float | None:
    value = raw.get("timeout_seconds")
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 < value < math.inf:
        raise FloorError(f"{where}: timeout_seconds {value!r} is not a positive number")
    return value


def _ranged(argv: Sequence[str]) -> bool:
    return any("{range}" in part for part in argv)


def _incoherent(claim: Claim) -> str | None:
    """Why a claim cannot run as written, or None."""

    if claim.parser == "injection":
        engine_only = not (claim.tool or claim.argv or claim.argv_without_base or claim.prefix)
        if claim.files and engine_only:
            return None
        return "the injection scan runs in the engine: give it files, and no tool, prefix or argv"
    if claim.tool is None or not claim.argv:
        return "give it a tool and an argv"
    if any(argv[0] != claim.tool for argv in (claim.argv, claim.argv_without_base) if argv):
        return f"each argv starts with its tool, {claim.tool}; a command before it is its prefix"
    if claim.prefix and not TOOL.fullmatch(claim.prefix[0]):
        return f"a prefix starts with a command PATH finds, not {claim.prefix[0]!r}"
    each = "{file}" in claim.argv
    if each != bool(claim.files) or (each and claim.parser not in PER_FILE_PARSERS):
        return "{file} in argv, files and a per-file parser (bash-n, shellcheck, exit) go together"
    if claim.parser in ("bash-n", "shellcheck") and not each:
        return f"{claim.parser} reads one script a run: put {{file}} in its argv"
    if claim.parser == "exit" and claim.mode != GATE:
        return "an exit status has nothing to baseline: its mode is gate"
    if claim.argv_without_base and not _ranged(claim.argv):
        return "argv_without_base stands in for an argv that scans {range}"
    return None


def parse_claim(raw: object) -> Claim:
    if not isinstance(raw, dict):
        raise FloorError("a claim is not a JSON object")
    name = raw.get("name")
    if not isinstance(name, str) or not NAME.fullmatch(name):
        raise FloorError(f"claim name {name!r} is not lowercase words joined by dots")
    where = f"claim {name}"
    unknown = sorted(set(raw) - CLAIM_FIELDS)
    if unknown:
        raise FloorError(f"{where}: unknown field {', '.join(unknown)}")
    if raw.get("mode") not in (GATE, BASELINE) or raw.get("parser") not in PARSER_NAMES:
        raise FloorError(f"{where}: mode is gate or baseline; parser is one of {PARSER_NAMES}")
    claim = Claim(
        name,
        raw["mode"],
        raw["parser"],
        tool=_field(raw, "tool", where, TOOL),
        argv=_words(raw, "argv", where) or (),
        argv_without_base=_words(raw, "argv_without_base", where),
        files=_words(raw, "files", where) or (),
        min_version=_field(raw, "min_version", where, DOTTED),
        prefix=_words(raw, "prefix", where) or (),
        timeout_seconds=_seconds(raw, where),
    )
    problem = _incoherent(claim)
    if problem is not None:
        raise FloorError(f"{where}: {problem}")
    return claim


def _day(value: object) -> bool:
    try:
        return (
            isinstance(value, str)
            and bool(DAY.fullmatch(value))
            and bool(datetime.date.fromisoformat(value))
        )
    except ValueError:
        return False


def parse_adoption(raw: object) -> Adoption:
    recorded = raw.get("recorded", {}) if isinstance(raw, dict) else None
    if not (
        isinstance(raw, dict)
        and {"commit", "on"} <= set(raw) <= {"commit", "on", "recorded"}
        and isinstance(raw["commit"], str)
        and COMMIT.fullmatch(raw["commit"])
        and _day(raw["on"])
        and isinstance(recorded, dict)
        and all(
            NAME.fullmatch(name) and isinstance(n, int) and not isinstance(n, bool) and n > 0
            for name, n in recorded.items()
        )
    ):
        raise FloorError(
            'adopted is {"commit": "<full commit id>", "on": "YYYY-MM-DD"}, with an optional'
            ' "recorded": {"<claim>": <findings>}'
        )
    return Adoption(raw["commit"], raw["on"], tuple(sorted(recorded.items())))


def parse_floor(value: object) -> Floor:
    if not (
        isinstance(value, dict)
        and {"version", "claims"} <= set(value) <= {"version", "adopted", "claims"}
        and value["version"] == FORMAT_VERSION
        and isinstance(value["claims"], list)
    ):
        raise FloorError(
            f'a floor is {{"version": {FORMAT_VERSION}, "claims": [...]}}, with an optional'
            ' "adopted"'
        )
    claims = tuple(parse_claim(item) for item in value["claims"])
    names = [claim.name for claim in claims]
    twice = sorted({name for name in names if names.count(name) > 1})
    if twice:
        raise FloorError(f"claim {', '.join(twice)} is declared twice")
    adopted = parse_adoption(value["adopted"]) if "adopted" in value else None
    return Floor(claims, adopted)


def load_floor(root: Path) -> Floor:
    data = fileplan.current(root, FLOOR_PATH)
    if data is None:
        raise FloorError(f"{FLOOR_PATH} is absent; `outcomebound floor propose` prints one")
    try:
        value = json.loads(data)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise FloorError(f"{FLOOR_PATH} is not JSON: {error}") from error
    return parse_floor(value)


# --- Git, read-only ------------------------------------------------------------------------


def _git(root: Path, *arguments: str) -> bytes:
    """What one read-only git command printed in `root`; a failure raises `FloorError`."""

    inherited = {
        key: value
        for key, value in os.environ.items()
        if key not in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE")
    }
    environment = git_environment({**inherited, "GIT_OPTIONAL_LOCKS": "0"})
    try:
        status, output, _ = validation._execute(
            ["git", *GIT_READ_CONFIGURATION, *arguments], root, None, environment
        )
    except OSError as error:
        raise FloorError(f"git could not run: {error}") from error
    if status != 0:
        detail = output.decode("utf-8", "replace").strip() or f"exit {status}"
        raise FloorError(f"git {' '.join(arguments[:2])} failed: {detail}")
    return output


def _tracked(root: Path, patterns: Sequence[str]) -> list[str]:
    """The paths Git tracks under `root` that match `patterns`, or all of them."""

    listed = _git(root, "ls-files", "-z", "--", *patterns).decode("utf-8", "surrogateescape")
    return sorted(path for path in listed.split("\0") if path)


def _scripts(root: Path, patterns: Sequence[str]) -> list[str]:
    """The tracked regular files matching `patterns`; a symlink is not followed."""

    return [
        path
        for path in _tracked(root, patterns)
        if (root / path).is_file() and not (root / path).is_symlink()
    ]


def _commit(root: Path, ref: str) -> str:
    if ref.startswith("-"):
        raise FloorError(f"{ref!r} starts with '-', so it is not a ref")
    try:
        found = _git(root, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
    except FloorError as error:
        raise FloorError(f"{ref} does not name a commit here") from error
    return found.decode("ascii", "replace").strip()


# --- Tools: found on PATH, at or above min_version -----------------------------------------


def _executable(tool: str) -> str | None:
    entries = [part for part in os.environ.get("PATH", "").split(os.pathsep) if os.path.isabs(part)]
    return shutil.which(tool, path=os.pathsep.join(entries)) if entries else None


def _numbers(text: str) -> tuple[int, ...]:
    return tuple(int(part) for part in text.split("."))


def _older(found: tuple[int, ...], least: tuple[int, ...]) -> bool:
    width = max(len(found), len(least))
    return found + (0,) * (width - len(found)) < least + (0,) * (width - len(least))


def _command(claim: Claim, executable: str, argv: Sequence[str]) -> list[str]:
    """What runs: the tool found on PATH in place of `argv[0]`, or, with a prefix, the prefix's
    command found on PATH, then the rest of the prefix and the whole argv, so the tool is the
    one where the prefix runs it."""

    if claim.prefix:
        return [executable, *claim.prefix[1:], *argv]
    return [executable, *argv[1:]]


def _version(claim: Claim, executable: str, root: Path) -> tuple[int, ...] | None:
    tool = claim.tool or ""
    asked = _command(claim, executable, [tool, "version" if tool == "gitleaks" else "--version"])
    try:
        status, output, _ = validation._execute(asked, root, claim.timeout_seconds, None)
    except OSError:
        return None
    found = VERSION_TEXT.search(output.decode("utf-8", "replace"))
    return None if status != 0 or found is None else _numbers(found.group(0))


def _ready(claim: Claim, root: Path) -> str:
    """The command the claim starts with (its prefix's, or else its tool) as an absolute path,
    or `Missing` when it is not on PATH, or the tool, through its prefix, is old or silent."""

    tool = claim.tool or ""
    first = claim.prefix[0] if claim.prefix else tool
    executable = _executable(first)
    if executable is None:
        raise Missing(f"{first} is not on PATH")
    if claim.min_version is not None:
        found = _version(claim, executable, root)
        through = f" through {' '.join(claim.prefix)}" if claim.prefix else ""
        if found is None:
            raise Missing(f"{tool} did not report a version{through}")
        if _older(found, _numbers(claim.min_version)):
            shown = ".".join(str(part) for part in found)
            raise Missing(f"{tool}{through} is {shown}, older than {claim.min_version}")
    return executable


def _run(claim: Claim, argv: Sequence[str], cwd: Path) -> tuple[int, str]:
    """Run `argv`, waiting for it unless the claim sets `timeout_seconds`."""

    tool = claim.tool or Path(argv[0]).name
    seconds = claim.timeout_seconds
    try:
        status, output, timed_out = validation._execute(list(argv), cwd, seconds, None)
    except OSError as error:
        raise Unreadable(f"{tool} could not run: {error}") from error
    if timed_out or status is None:
        raise Unreadable(f"{tool} did not finish in its timeout_seconds, {seconds}")
    return status, output.decode("utf-8", "replace")


# --- Findings and the parsers -----------------------------------------------------------------


@dataclass(frozen=True)
class Finding:
    path: str
    code: str
    message: str
    where: str = ""

    @property
    def key(self) -> str:
        """The finding as a baseline line holds it: its path and its rule's code. No message,
        which a tool rewords between releases and which quotes the project's own names; no
        line, no column, no count."""

        return f"{self.path}:{self.code}"

    def shown(self) -> str:
        place = ":".join(part for part in (self.path, self.where) if part)
        return f"{place}: {self.code} {self.message}" if place else f"{self.code} {self.message}"


# A baseline line: the path, then the first `:code` that ends the line or opens a message. An
# earlier floor wrote `path:code:message`; it reads as `path:code`.
KEY = re.compile(r"(?P<path>.*?):(?P<code>[A-Za-z][A-Za-z0-9_-]*)(?::.*)?")
SPACE = re.compile(r"\s+")
REFORMAT = re.compile(r"^(?:Would reformat: |\s*--> )(?P<path>.+?)(?::\d+:\d+)?$", re.MULTILINE)
REFORMAT_COUNT = re.compile(r"^(\d+) files? would be reformatted", re.MULTILINE)
FORMAT_ERROR = re.compile(
    r"^(?P<error>(?:error|invalid-syntax)\b[^\n]*)(?:\n\s*--> (?P<at>[^\n]+))?", re.MULTILINE
)
BASH_ERROR = re.compile(r"^.*?: line (?P<line>\d+): (?P<message>.+)$", re.MULTILINE)
MISSING_TARGET = "Missing target module, package, files, or command"
COMMENT = re.compile(r"^\s*#")
# The injection scan: text a shell script executes as code.
INJECTION = (
    ("eval", re.compile(r"(?:^|[;&|(]|\bthen\b|\bdo\b)\s*eval\b"), "`eval` executes text as code"),
    (
        "pipe-to-shell",
        re.compile(r"\b(?:curl|wget|fetch)\b[^|#]*\|\s*(?:sudo\s+)?(?:ba|z|k|da)?sh\b"),
        "a download is piped straight into a shell",
    ),
    (
        "source-process-substitution",
        re.compile(r"(?:^|\s)(?:\.|source)\s+<\("),
        "a process substitution is sourced, executing its output",
    ),
)


def _message(text: str) -> str:
    """A tool's message on one line."""

    return SPACE.sub(" ", text).strip()


def _relative(path: str, root: Path) -> str:
    """A tool's path as the project names it: relative to the root, with `/`."""

    candidate = Path(path)
    if candidate.is_absolute():
        try:
            return Path(os.path.realpath(candidate)).relative_to(root).as_posix()
        except ValueError:
            return candidate.as_posix()
    return candidate.as_posix()


def _first(text: str) -> str:
    return next((line.strip()[:200] for line in text.splitlines() if line.strip()), "no output")


def _json_after_prefix(text: str, opener: str) -> object:
    """The JSON value on the first line opening with `opener`; what came before is a warning."""

    offset = 0
    for line in text.splitlines(keepends=True):
        stripped = line.lstrip()
        if stripped.startswith(opener):
            try:
                return json.JSONDecoder().raw_decode(text, offset + len(line) - len(stripped))[0]
            except json.JSONDecodeError:
                return None
        offset += len(line)
    return None


def parse_ruff_format(status: int, text: str, root: Path) -> list[Finding]:
    """`ruff format --check`: exit 1 names each file it would rewrite, in either print style."""

    if status == 0:
        return []
    if status != 1:
        found = FORMAT_ERROR.search(text)
        reason = _first(text) if found is None else found["error"].strip()
        at = f"{found['at'].strip()}: " if found and found["at"] else ""
        raise Unreadable(f"ruff format exited {status}: {at}{reason}")
    paths = sorted({_relative(found["path"], root) for found in REFORMAT.finditer(text)})
    message = "the formatter would rewrite this file"
    if not paths:
        count = REFORMAT_COUNT.search(text)
        return [Finding(".", "unformatted", f"{count[1] if count else 'some'} unnamed files")]
    return [Finding(path, "unformatted", message) for path in paths]


def parse_ruff(status: int, text: str, root: Path) -> list[Finding]:
    """`ruff check --output-format json`: one finding per diagnostic."""

    report = _json_after_prefix(text, "[") if status in (0, 1) else None
    if not isinstance(report, list):
        raise Unreadable(f"ruff exited {status} without a JSON list: {_first(text)}")
    findings = []
    for item in report:
        if not isinstance(item, dict):
            raise Unreadable("a ruff diagnostic is not a JSON object")
        place = item.get("location")
        row, column = (
            (place.get("row"), place.get("column")) if isinstance(place, dict) else ("", "")
        )
        findings.append(
            Finding(
                _relative(str(item.get("filename") or ""), root),
                str(item.get("code") or "syntax"),
                _message(str(item.get("message") or "")),
                f"{row}:{column}",
            )
        )
    if status == 1 and not findings:
        raise Unreadable("ruff exited 1 and reported no diagnostic")
    return findings


def parse_mypy(status: int, text: str, root: Path) -> list[Finding]:
    """`mypy --output json`: a JSON object per line; a note is not a finding."""

    findings = []
    for line in text.splitlines():
        if not line.lstrip().startswith("{"):
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as error:
            raise Unreadable(f"a mypy record is not JSON: {error}") from error
        if isinstance(item, dict) and item.get("severity") == "error":
            findings.append(
                Finding(
                    _relative(str(item.get("file") or ""), root),
                    str(item.get("code") or "error"),
                    _message(str(item.get("message") or "")),
                    f"{item.get('line', '')}:{item.get('column', '')}",
                )
            )
    if status == 2:
        stop = findings[0].shown() if findings else _first(text)
        raise Unreadable(f"mypy stopped at a blocking error: {stop}")
    if status not in (0, 1) or (status == 1 and not findings):
        raise Unreadable(f"mypy exited {status} and reported no error: {_first(text)}")
    return findings


def parse_gitleaks(
    status: int, report: str, root: Path, tracked: frozenset[str] | None
) -> list[Finding]:
    """gitleaks' JSON report as `path:line` and the rule: never the secret, never its match.

    Its output is never quoted either, so a failure names only the exit status.
    """

    try:
        entries = json.loads(report) if status in (0, 1) else None
    except json.JSONDecodeError:
        entries = None
    if not isinstance(entries, list) or (status == 1 and not entries):
        raise Unreadable(f"gitleaks exited {status} without a readable report")
    findings = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise Unreadable("a gitleaks finding is not a JSON object")
        path = _relative(str(entry.get("File") or ""), root)
        if tracked is not None and path not in tracked:
            continue
        commit = str(entry.get("Commit") or "")[:12]
        where = f"{entry.get('StartLine', '')}" + (f" in {commit}" if commit else "")
        rule = str(entry.get("RuleID") or "secret")
        findings.append(Finding(path, rule, "a secret may be committed here", where))
    return findings


def parse_shellcheck(status: int, text: str, path: str) -> list[Finding]:
    """`shellcheck -f json1` over one script: a finding per comment, its code as `SC<n>`."""

    report = _json_after_prefix(text, "{") if status in (0, 1) else None
    comments = report.get("comments") if isinstance(report, dict) else None
    if not isinstance(comments, list) or (status == 1 and not comments):
        raise Unreadable(f"shellcheck exited {status} on {path} without a report: {_first(text)}")
    findings = []
    for item in comments:
        if not isinstance(item, dict):
            raise Unreadable("a shellcheck comment is not a JSON object")
        code, message = item.get("code"), _message(str(item.get("message") or ""))
        where = f"{item.get('line', '')}:{item.get('column', '')}"
        findings.append(Finding(path, f"SC{code}", message, where))
    return findings


def parse_per_file(parser: str, status: int, text: str, path: str) -> list[Finding]:
    """One run over one script: shellcheck's report, `bash -n`'s own message, or an exit
    status."""

    if parser == "shellcheck":
        return parse_shellcheck(status, text, path)
    if status == 0:
        return []
    if parser == "exit":
        return [Finding(path, "exit", f"exited {status}")]
    found = BASH_ERROR.search(text)
    if found is None:
        raise Unreadable(f"bash -n exited {status} on {path}: {_first(text)}")
    return [Finding(path, "syntax", _message(found["message"]), found["line"])]


def parse_exit(status: int, text: str, root: Path) -> list[Finding]:
    return [] if status == 0 else [Finding("", "exit", f"exited {status}: {_first(text)}")]


def scan_injection(root: Path, paths: Sequence[str]) -> list[Finding]:
    findings: list[Finding] = []
    for path in paths:
        text = (root / path).read_bytes().decode("utf-8", "replace")
        for number, line in enumerate(text.splitlines(), start=1):
            if not COMMENT.match(line):
                findings.extend(
                    Finding(path, rule, message, str(number))
                    for rule, pattern, message in INJECTION
                    if pattern.search(line)
                )
    return findings


WHOLE_RUN_PARSERS: dict[str, Callable[[int, str, Path], list[Finding]]] = {
    "ruff-format": parse_ruff_format,
    "ruff": parse_ruff,
    "mypy": parse_mypy,
    "exit": parse_exit,
}


# --- Running and judging a claim ----------------------------------------------------------


@dataclass(frozen=True)
class Context:
    root: Path
    base: str | None = None
    base_commit: str | None = None
    base_problem: str | None = None
    adopted: Adoption | None = None


@dataclass(frozen=True)
class Outcome:
    name: str
    status: str
    summary: str
    details: tuple[str, ...] = ()

    def lines(self) -> list[str]:
        return [f"{self.status} {self.name} ({self.summary})", *(f"  {d}" for d in self.details)]


def _argv(claim: Claim, executable: str, context: Context, report: str) -> list[str]:
    """The argv to run: `{range}` is `<base>..HEAD`, or without a base the commits since the
    adoption record's, or without either `argv_without_base` runs instead."""

    argv, start = claim.argv, context.base_commit
    if _ranged(argv) and context.base is None and context.adopted is not None:
        try:
            start = _commit(context.root, context.adopted.commit)
            _git(context.root, "merge-base", "--is-ancestor", start, "HEAD")
        except FloorError as error:
            shown = context.adopted.commit[:12]
            raise Unreadable(
                f"the adoption commit {shown} is not in HEAD's history here; fetch it, or pass"
                " --base"
            ) from error
    elif _ranged(argv) and context.base is None:
        if claim.argv_without_base is None:
            raise Unreadable("it scans a commit range, so it runs only with --base")
        argv = claim.argv_without_base
    elif _ranged(argv) and start is None:
        raise Unreadable(context.base_problem or "no base commit")
    elif _ranged(argv) and start is not None:
        start = _since(context.root, start, context.adopted)
    span = f"{start}..HEAD"
    parts = [part.replace("{range}", span).replace("{report}", report) for part in argv]
    return _command(claim, executable, parts)


GITLEAKS_FILES = (".gitleaks.toml", ".gitleaksignore")


def _mirror(root: Path, paths: Iterable[str], into: Path) -> None:
    """The tracked regular files `paths` under `into`, at the same relative paths, linked where
    the file system allows and copied where it does not; and gitleaks' own config and
    allowlist from the root, tracked or not, since gitleaks reads them from where it runs."""

    for path in {*paths, *(name for name in GITLEAKS_FILES if (root / name).is_file())}:
        source = root / path
        if not source.is_file() or source.is_symlink():
            continue
        target = into / path
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.link(source, target)
        except OSError:
            shutil.copyfile(source, target)


def _secrets(claim: Claim, executable: str, context: Context) -> list[Finding]:
    """gitleaks over `<base>..HEAD`, or without a base over the commits since adoption, or
    without either over the tracked files alone: gitleaks scans a directory whole, ignored
    folders included, so it runs in a scratch copy that holds only the files Git tracks."""

    working_tree = context.base is None and context.adopted is None and _ranged(claim.argv)
    tracked = frozenset(_tracked(context.root, ())) if working_tree else None
    with tempfile.TemporaryDirectory(prefix="outcomebound-floor-") as scratch:
        report = Path(scratch) / "report.json"
        where = context.root
        if tracked is not None:
            where = Path(os.path.realpath(scratch)) / "tracked"
            where.mkdir()
            _mirror(context.root, tracked, where)
        status, _ = _run(claim, _argv(claim, executable, context, str(report)), where)
        text = report.read_text(encoding="utf-8", errors="replace") if report.is_file() else ""
        return parse_gitleaks(status, text, where, tracked)


def findings_for(claim: Claim, context: Context) -> tuple[list[Finding], int | None]:
    """What one claim found, and how many tracked files it read when it reads files."""

    root = context.root
    scripts = _scripts(root, claim.files) if claim.files else []
    if claim.files and not scripts:
        # Nothing the claim reads is left, so nothing it holds can be new.
        return [], 0
    if claim.parser == "injection":
        return scan_injection(root, scripts), len(scripts)
    executable = _ready(claim, root)
    if scripts:
        found = []
        for path in scripts:
            parts = [part.replace("{file}", path) for part in claim.argv]
            argv = _command(claim, executable, parts)
            found.extend(parse_per_file(claim.parser, *_run(claim, argv, root), path))
        return found, len(scripts)
    if claim.parser == "gitleaks":
        return _secrets(claim, executable, context), None
    argv = _argv(claim, executable, context, "")
    status, text = _run(claim, argv, root)
    if claim.parser == "mypy" and status == 2 and MISSING_TARGET in text:
        # The project's config names no files, so its own `mypy` would stop here: `.` it is.
        status, text = _run(claim, [*argv, "."], root)
    return WHOLE_RUN_PARSERS[claim.parser](status, text, root), None


def _key(line: str) -> str:
    """A baseline line as `path:code`; `path:code:message`, as an earlier floor wrote it,
    reads the same."""

    found = KEY.fullmatch(line.strip())
    return line.strip() if found is None else f"{found['path']}:{found['code']}"


def _lines(text: str | None) -> Counter[str]:
    """A baseline's text as the multiset of its keys; a blank line holds nothing."""

    return Counter(_key(line) for line in (text or "").splitlines() if line.strip())


def read_baseline(root: Path, claim: Claim) -> Counter[str]:
    data = fileplan.current(root, claim.baseline_path)
    return _lines(None if data is None else data.decode("utf-8", "replace"))


def baseline_text(keys: Iterable[str]) -> bytes:
    return "".join(f"{key}\n" for key in sorted(keys)).encode("utf-8")


def _plural(count: int, word: str) -> str:
    return f"{count} {word}{'' if count == 1 else 's'}"


def judge(
    claim: Claim, findings: Sequence[Finding], baseline: Counter[str], files: int | None
) -> Outcome:
    """A gate fails on any finding; a baseline on a key found more often than it holds it."""

    read = "" if files is None else f" in {_plural(files, 'file')}"
    if claim.mode == GATE:
        shown = tuple(finding.shown() for finding in findings)
        summary = f"{_plural(len(findings), 'finding')}{read}"
        return Outcome(claim.name, FAIL if findings else PASS, summary, shown)
    found = Counter(finding.key for finding in findings)
    new, stale = found - baseline, baseline - found
    summary = f"{sum(new.values())} new, {sum((found & baseline).values())} baselined{read}"
    if stale:
        summary += f", {sum(stale.values())} stale"
    grouped: dict[str, list[Finding]] = {}
    for finding in findings:
        grouped.setdefault(finding.key, []).append(finding)
    added: list[str] = []
    for key, n in sorted(new.items()):
        # A key's findings are alike to the baseline, so each is listed: any may be the new one.
        added.append(f"+{n} {key}" + (f" (of {found[key]} found)" if found[key] > n else ""))
        added.extend(f"  {' '.join(filter(None, (f.where, f.message)))}" for f in grouped[key])
    return Outcome(claim.name, FAIL if new else PASS, summary, tuple(added))


def evaluate(claim: Claim, context: Context) -> Outcome:
    try:
        findings, files = findings_for(claim, context)
    except (Unreadable, FloorError) as problem:
        return Outcome(claim.name, UNVERIFIED, str(problem))
    held = read_baseline(context.root, claim) if claim.mode == BASELINE else Counter[str]()
    return judge(claim, findings, held, files)


# --- The loosening check ------------------------------------------------------------------

WHOLE_CONFIGS = frozenset(
    {
        "ruff.toml",
        ".ruff.toml",
        "mypy.ini",
        ".mypy.ini",
        ".gitleaks.toml",
        ".gitleaksignore",
        ".shellcheckrc",
        "shellcheckrc",
    }
)
HEADER = re.compile(r"^\s*\[\[?\s*(?P<name>[^\[\]]+?)\s*\]\]?\s*(?:[#;].*)?$")
# A suppression comment for a tool the floor runs, or shellcheck's. Each pattern is spelled
# so that its own source line does not match it.
DIRECTIVE = re.compile(
    r"#\s*(?:ruff:\s*)?no[q]a\b(?:\s*:\s*[a-z]+[0-9]+(?:[\s,]+[a-z]+[0-9]+)*)?"
    r"|#\s*type:\s*ignore\b(?:\[[^\]]*\])?"
    r"|#\s*mypy:[^\n#]*"
    r"|#\s*shellcheck\s+disable\s*=\s*[\w,-]+"
    r"|\bgitleaks:allo[w]\b",
    re.IGNORECASE,
)
# Files no linter or type checker reads. A suppression comment quoted in one changes no finding,
# except gitleaks', since gitleaks scans every file.
DOCUMENT_SUFFIXES = frozenset({".md", ".markdown", ".rst", ".txt", ".adoc"})
GITLEAKS_ONLY = re.compile(r"\bgitleaks:allo[w]\b", re.IGNORECASE)
TRAILER = re.compile(
    r"^Floor-Loosening:[ \t]*(?P<what>[^\n]*?[^;\s])[ \t]*;[ \t]*ruled[ \t]+(?P<ruling>\S+)[ \t]*$",
    re.MULTILINE,
)


def _tool_table(name: str) -> bool:
    return [part.strip("\"' ") for part in name.split(".")][:2] in (
        ["tool", "ruff"],
        ["tool", "mypy"],
    )


def _mypy_section(name: str) -> bool:
    return name == "mypy" or name.startswith("mypy-")


SECTIONED: dict[str, tuple[str, Callable[[str], bool]]] = {
    "pyproject.toml": ("[tool.ruff] or [tool.mypy]", _tool_table),
    "setup.cfg": ("[mypy]", _mypy_section),
}


def _section_lines(text: str | None, wanted: Callable[[str], bool]) -> list[str]:
    """The non-blank lines inside the sections `wanted` accepts, each stripped."""

    kept: list[str] = []
    inside = False
    for line in (text or "").splitlines():
        header = HEADER.match(line)
        if header is not None:
            inside = wanted(header["name"])
        if inside and line.strip():
            kept.append(line.strip())
    return kept


def _blob(root: Path, sha: str | None) -> str | None:
    return None if sha is None else _git(root, "cat-file", "blob", sha).decode("utf-8", "replace")


def _floor_at(root: Path, sha: str | None) -> Floor | None:
    """The floor.json blob `sha`, an empty floor for none, None when unreadable."""

    if sha is None:
        return Floor(())
    try:
        return parse_floor(json.loads(_blob(root, sha) or ""))
    except (FloorError, ValueError):
        return None


def _kept(before: Claim, after: Claim | None) -> bool:
    """`after` is `before`, or `before` with its mode moved from baseline to gate. Its
    `timeout_seconds` may differ: a claim that times out reads UNVERIFIED, which fails too."""

    if after is None:
        return False
    after = replace(after, timeout_seconds=before.timeout_seconds)
    return after == before or (before.mode == BASELINE and after == replace(before, mode=GATE))


def _floor_change(
    before: Floor | None, after: Floor | None, emptied: Callable[[Claim], bool]
) -> str | None:
    """A claim floor.json drops or changes, or an adoption record it changes or removes,
    loosens the floor; a claim it adds, a baseline claim it makes a gate, an adoption record
    where there was none, and a claim it drops whose files are all gone (`emptied`) do not."""

    if before is None or after is None:
        return f"{FLOOR_PATH} changed"
    now = {claim.name: claim for claim in after.claims}
    altered = sorted(
        c.name
        for c in before.claims
        if not _kept(c, now.get(c.name)) and not (c.name not in now and emptied(c))
    )
    if before.adopted is not None and after.adopted != before.adopted:
        altered.append("its adoption record")
    return f"{FLOOR_PATH} drops or changes {', '.join(altered)}" if altered else None


def _matches_none(root: Path, head: str, patterns: Sequence[str]) -> bool:
    """Whether `head` tracks no file matching `patterns`."""

    empty = _git(root, "hash-object", "-t", "tree", os.devnull).decode("ascii").strip()
    listed = _git(root, "diff", "--name-only", "-z", "--relative", empty, head, "--", *patterns)
    return not listed.strip(b"\0")


def _renames(root: Path, fork: str, head: str) -> dict[str, str]:
    """Each path Git reports renamed between `fork` and `head`: the new path to the old."""

    raw = _git(root, "diff", "--name-status", "-z", "-M", "--relative", fork, head, "--")
    fields = raw.decode("utf-8", "surrogateescape").split("\0")
    renamed: dict[str, str] = {}
    index = 0
    while index < len(fields) and fields[index]:
        status = fields[index]
        if status[0] in "RC":
            if status[0] == "R":
                renamed[fields[index + 2]] = fields[index + 1]
            index += 3
        else:
            index += 2
    return renamed


def _carried(gained: Counter[str], lost: Counter[str], renamed: dict[str, str]) -> Counter[str]:
    """The gained baseline lines left once each nets against a lost line of the same code at
    the path Git reports renamed to its own: a moved finding, not a new one."""

    left, lost = Counter(gained), Counter(lost)
    for line, count in gained.items():
        found = KEY.fullmatch(line)
        old = renamed.get(found["path"]) if found else None
        if found is None or old is None:
            continue
        twin = f"{old}:{found['code']}"
        moved = min(count, lost[twin])
        left[line] -= moved
        lost[twin] -= moved
    return +left


@dataclass(frozen=True)
class Span:
    """One loosening range: its root, its ends, and what Git reports renamed inside it."""

    root: Path
    fork: str
    head: str
    renamed: dict[str, str]


def _policy_change(
    span: Span, path: str, old: str | None, new: str | None, added: frozenset[str]
) -> str | None:
    """What loosens the floor in one changed file; `added` names the claims the range adds,
    whose first baseline records where they start rather than loosening them."""

    root, name = span.root, path.rsplit("/", 1)[-1]
    if path == FLOOR_PATH:
        return _floor_change(
            _floor_at(root, old),
            _floor_at(root, new),
            lambda claim: bool(claim.files) and _matches_none(root, span.head, claim.files),
        )
    if name in WHOLE_CONFIGS:
        return f"{path} changed"
    if path.startswith(f"{BASELINE_DIR}/") and path.endswith(".baseline"):
        if old is None and name.removesuffix(".baseline") in added:
            return None
        before, after = (_lines(_blob(root, sha)) for sha in (old, new))
        gained = sum(_carried(after - before, before - after, span.renamed).values())
        return f"{path} gained {_plural(gained, 'line')}" if gained else None
    if name not in SECTIONED:
        return None
    label, wanted = SECTIONED[name]
    before_lines, after_lines = (_section_lines(_blob(root, sha), wanted) for sha in (old, new))
    return f"{path} changed its {label} settings" if before_lines != after_lines else None


def _policy_changes(root: Path, fork: str, head: str) -> list[str]:
    raw = _git(
        root, "diff", "--raw", "-z", "--no-abbrev", "--no-renames", "--relative", fork, head, "--"
    )
    fields = raw.split(b"\0")
    entries: list[tuple[str, str | None, str | None]] = []
    for meta, named in zip(fields[0::2], fields[1::2], strict=False):
        parts = meta.decode("ascii", "replace").split()
        if len(parts) < 5:
            continue
        old, new = (None if set(sha) == {"0"} else sha for sha in parts[2:4])
        entries.append((named.decode("utf-8", "surrogateescape"), old, new))
    added: frozenset[str] = frozenset()
    for path, old, new in entries:
        if path == FLOOR_PATH:
            before, after = _floor_at(root, old), _floor_at(root, new)
            if before is not None and after is not None:
                added = frozenset(c.name for c in after.claims) - {c.name for c in before.claims}
    baselines = any(path.startswith(f"{BASELINE_DIR}/") for path, _, _ in entries)
    span = Span(root, fork, head, _renames(root, fork, head) if baselines else {})
    changes = (_policy_change(span, path, old, new, added) for path, old, new in entries)
    return [change for change in changes if change is not None]


def _directive_counts(patch: str) -> dict[str, Counter[str]]:
    """Each file's suppression comments the patch adds, net of those it removes."""

    net: dict[str, Counter[str]] = {}
    path, hunk = "", False
    for line in patch.splitlines():
        if line.startswith("diff --git "):
            hunk = False
        elif not hunk:
            if line.startswith(("--- a/", "+++ b/")):
                path = line[6:]
            hunk = line.startswith("@@")
        elif line.startswith(("+", "-")):
            pattern = GITLEAKS_ONLY if Path(path).suffix.lower() in DOCUMENT_SUFFIXES else DIRECTIVE
            found = Counter(" ".join(match.split()).lower() for match in pattern.findall(line))
            counts = net.setdefault(path, Counter())
            if line.startswith("+"):
                counts.update(found)
            else:
                counts.subtract(found)
    return {name: +counts for name, counts in net.items() if +counts}


def _added_directives(root: Path, fork: str, head: str) -> list[str]:
    patch = _git(
        root,
        "-c",
        "core.quotePath=false",
        "diff",
        "--no-color",
        "--no-ext-diff",
        "--no-textconv",
        "--relative",
        "--src-prefix=a/",
        "--dst-prefix=b/",
        "-M",
        "--unified=0",
        fork,
        head,
        "--",
    ).decode("utf-8", "replace")
    return [
        f"{path} adds {directive}" + (f" (x{count})" if count > 1 else "")
        for path, counts in sorted(_directive_counts(patch).items())
        if not path.startswith(f"{BASELINE_DIR}/")
        for directive, count in sorted(counts.items())
    ]


def _rulings(root: Path, base_commit: str) -> list[str]:
    log = _git(
        root,
        "-c",
        "log.showSignature=false",
        "log",
        "--no-color",
        "--format=%H%x1f%B%x1e",
        f"{base_commit}..HEAD",
    ).decode("utf-8", "replace")
    rulings: list[str] = []
    for record in log.split("\x1e"):
        commit, _, message = record.strip().partition("\x1f")
        rulings.extend(
            f"{commit[:12]} Floor-Loosening: {found['what']}; ruled {found['ruling']}"
            for found in TRAILER.finditer(message)
        )
    return rulings


def _is_ancestor(root: Path, older: str, newer: str) -> bool:
    try:
        _git(root, "merge-base", "--is-ancestor", older, newer)
    except FloorError:
        return False
    return True


def _adopted_after(root: Path, fork: str, adopted: Adoption | None) -> str | None:
    """The adoption commit, where the floor was adopted after `fork`: `fork` holds no
    floor.json, and the adoption commit descends from `fork` and is in HEAD's history. The
    commits before it come from before the floor existed. Where `fork` holds a floor, the range
    starts at `fork`, so an adoption record added or moved later hides nothing before it."""

    if adopted is None:
        return None
    try:
        commit = _commit(root, adopted.commit)
        held = _git(root, "ls-tree", "-z", "--name-only", fork, "--", FLOOR_PATH)
    except FloorError:
        return None
    if held.strip(b"\0") or commit == fork:
        return None
    if _is_ancestor(root, fork, commit) and _is_ancestor(root, commit, "HEAD"):
        return commit
    return None


def _since(root: Path, base_commit: str, adopted: Adoption | None) -> str:
    """Where a scan of `<base>..HEAD` starts: the adoption commit when the floor was adopted
    after the merge base, or else `base_commit`."""

    try:
        fork = _git(root, "merge-base", base_commit, "HEAD").decode("ascii").strip()
    except FloorError:
        return base_commit
    return _adopted_after(root, fork, adopted) or base_commit


def loosening(context: Context) -> Outcome:
    """FAIL on a loosening between the merge base with `--base` and HEAD, unless a commit in
    that same range carries a `Floor-Loosening: <what>; ruled <id>` line. Where the floor was
    adopted after the merge base, the range starts at the adoption commit instead."""

    name = "loosening"
    if context.base_commit is None:
        return Outcome(name, UNVERIFIED, context.base_problem or "no base commit")
    try:
        head = _commit(context.root, "HEAD")
        fork = _git(context.root, "merge-base", context.base_commit, head).decode().strip()
        adopted = _adopted_after(context.root, fork, context.adopted)
        start = adopted or fork
        changes = _policy_changes(context.root, start, head)
        changes += _added_directives(context.root, start, head)
        rulings = _rulings(context.root, start) if changes else []
    except FloorError as problem:
        return Outcome(name, UNVERIFIED, str(problem))
    span = f"{context.base}..HEAD"
    if adopted is not None:
        span = f"{adopted[:12]}..HEAD, the commits since the floor's adoption"
    if not changes:
        return Outcome(name, PASS, f"none in {span}")
    if rulings:
        return Outcome(name, PASS, f"{len(changes)} in {span}, ruled", (*changes, *rulings))
    summary = f"{len(changes)} in {span}; no commit carries Floor-Loosening: <what>; ruled <id>"
    return Outcome(name, FAIL, summary, tuple(changes))


# --- The verbs ----------------------------------------------------------------------------


def _context(root: Path, base: str | None, adopted: Adoption | None) -> Context:
    if base is None:
        return Context(root, adopted=adopted)
    try:
        return Context(root, base, _commit(root, base), adopted=adopted)
    except FloorError as problem:
        return Context(root, base, None, str(problem), adopted)


def _write(root: Path, changes: dict[str, bytes | None], accept: bool) -> int:
    """Write or delete through `fileplan.write`; without `accept`, only say what would change."""

    expected = {path: fileplan.current(root, path) for path in changes}
    changes = {path: data for path, data in changes.items() if data != expected[path]}
    if accept and changes:
        fileplan.write(root, changes, {path: expected[path] for path in changes})
    for path, data in changes.items():
        done, undone = ("removed", "remove") if data is None else ("wrote", "write")
        print(f"{done} {path}" if accept else f"would {undone} {path}")
    if changes and not accept:
        print("nothing written: pass --accept")
    return 0


def propose(root: Path) -> int:
    stacks = [stack for stack, patterns in STACKS if _tracked(root, patterns)]
    if not stacks:
        print("floor: Git tracks no python or shell file here; nothing to propose", file=sys.stderr)
        return 1
    floor = parse_floor(
        {"version": FORMAT_VERSION, "claims": [c for s in stacks for c in RECIPES[s]]}
    )
    sys.stdout.write(floor.text().decode("utf-8"))
    return 0


def _fingerprint(finding: Finding) -> str:
    """gitleaks' fingerprint without a commit, `path:rule:line`: as a line of
    `.gitleaksignore` it allowlists that line in a directory scan and in every commit."""

    return f"{finding.path}:{finding.code}:{finding.where.split(' ', 1)[0]}"


def fit(
    root: Path, proposed: Floor, source: Path, strict: bool
) -> tuple[list[Claim], dict[str, bytes | None], dict[str, int]]:
    """Run each claim once and fit it to the findings the project holds today: the claims to
    write, their baselines, and how many findings each baseline recorded.

    A claim whose parser can hold a baseline records its findings and becomes a baseline
    claim; an `exit` claim stays a gate; a secret is listed for a person, never recorded; a
    claim whose tool is missing or old stays as proposed, `UNVERIFIED` until provisioned; a
    claim whose tool runs but cannot read the project is left out, with why. `strict` fits
    nothing: every claim stays as proposed, and each says what it would fail on now."""

    context = Context(root)
    claims: list[Claim] = []
    changes: dict[str, bytes | None] = {}
    recorded: dict[str, int] = {}
    for claim in proposed.claims:
        try:
            findings, _ = findings_for(claim, context)
        except (Unreadable, FloorError) as problem:
            if strict or isinstance(problem, Missing):
                claims.append(claim)
                print(f"{claim.name}: {UNVERIFIED} ({problem})")
                if not strict:
                    print("  kept as proposed: provision its tool (`outcomebound floor provision`")
                    print(f"  says how), then apply {source} again to record its findings")
            else:
                print(
                    f"{claim.name}: left out ({problem}); once that is fixed, apply {source} again"
                )
            continue
        held = read_baseline(root, claim)
        keys = [finding.key for finding in findings]
        against = held if claim.mode == BASELINE or not strict else Counter[str]()
        new = sum((Counter(keys) - against).values())
        fails = f"fails now on {_plural(new, 'finding')}" if new else "passes"
        if claim.parser == "gitleaks" and findings:
            claims.append(claim)
            what = fails if strict else _plural(new, "finding")
            print(f"{claim.name}: {what} in the files Git tracks, never recorded")
            print("  rotate each secret, or allowlist it: add its line below to .gitleaksignore,")
            print("  a change check --base reads as a loosening")
            print("\n".join(f"  {_fingerprint(finding)}" for finding in findings))
        elif strict or not findings:
            claims.append(claim)
            print(f"{claim.name}: {fails}")
        elif claim.parser == "exit":
            claims.append(claim)
            print(f"{claim.name}: fails now ({findings[0].message}); it stays a gate")
        elif held:
            claims.append(replace(claim, mode=BASELINE))
            kept = _plural(sum(held.values()), "line")
            print(f"{claim.name}: {fails}; its baseline of {kept} is kept")
        else:
            claims.append(replace(claim, mode=BASELINE))
            recorded[claim.name] = len(keys)
            changes[claim.baseline_path] = baseline_text(keys)
            print(f"{claim.name}: {_plural(len(keys), 'finding')} recorded; mode baseline")
    return claims, changes, recorded


def _installed(root: Path) -> Floor | None:
    try:
        return load_floor(root) if fileplan.current(root, FLOOR_PATH) is not None else None
    except FloorError:
        return None


def apply(root: Path, source: Path, accept: bool, strict: bool) -> int:
    try:
        proposed = parse_floor(json.loads(source.read_text(encoding="utf-8")))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise FloorError(f"cannot read {source}: {error}") from error
    claims, changes, recorded = fit(root, proposed, source, strict)
    installed = _installed(root)
    adopted = proposed.adopted or (installed.adopted if installed else None)
    if adopted is None and not strict:
        try:
            head = _commit(root, "HEAD")
            adopted = Adoption(head, datetime.date.today().isoformat(), tuple(recorded.items()))
        except FloorError:
            print("no commit yet, so no adoption record: every finding counts as new")
    if adopted is not None:
        shown = f"adopted at {adopted.commit[:12]} on {adopted.on}"
        print(f"{shown}: without --base, check scans only later commits for secrets")
    changes[FLOOR_PATH] = Floor(tuple(claims), adopted).text()
    for claim in claims:
        if claim.mode == BASELINE and fileplan.current(root, claim.baseline_path) is None:
            changes.setdefault(claim.baseline_path, b"")
    status = _write(root, changes, accept)
    if accept and installed is not None:
        print("check --base reads a claim this changes or drops as a loosening: its commit")
        print("carries the line Floor-Loosening: <what>; ruled <decision id>")
    return status


def _noted(outcome: Outcome, claim: Claim, context: Context) -> Outcome:
    """The outcome, with what the adoption record says of its claim."""

    adopted = context.adopted
    if adopted is None or outcome.status == UNVERIFIED:
        return outcome
    count = dict(adopted.recorded).get(claim.name)
    if count is not None:
        note = f"; {_plural(count, 'finding')} recorded at adoption on {adopted.on}"
    elif context.base is None and _ranged(claim.argv):
        note = f" in the commits since adoption on {adopted.on}"
    else:
        return outcome
    return replace(outcome, summary=outcome.summary + note)


def check(root: Path, base: str | None, only: str | None) -> int:
    floor = load_floor(root)
    claims = [claim for claim in floor.claims if only is None or claim.name == only]
    if not claims and only is not None:
        raise FloorError(f"no claim is named {only}")
    context = _context(root, base, floor.adopted)
    status = 0
    for claim in claims:
        status = max(status, _show(_noted(evaluate(claim, context), claim, context)))
    if base is not None:
        status = max(status, _show(loosening(context)))
    return status


def _show(outcome: Outcome) -> int:
    """Print one outcome as soon as it is known; 1 unless it passed."""

    print("\n".join(outcome.lines()), flush=True)
    return 0 if outcome.status == PASS else 1


def record(root: Path, accept: bool) -> int:
    """`baseline`: the current findings, into each empty or absent baseline only."""

    context, status = Context(root), 0
    changes: dict[str, bytes | None] = {}
    for claim in (claim for claim in load_floor(root).claims if claim.mode == BASELINE):
        held = sum(read_baseline(root, claim).values())
        if held:
            print(f"KEPT {claim.name} ({_plural(held, 'line')}; delete it to record it again)")
            continue
        try:
            findings, _ = findings_for(claim, context)
        except (Unreadable, FloorError) as problem:
            print(f"{UNVERIFIED} {claim.name} ({problem})")
            status = 1
            continue
        print(f"{claim.name}: {_plural(len(findings), 'finding')} to record")
        changes[claim.baseline_path] = baseline_text(finding.key for finding in findings)
    return max(status, _write(root, changes, accept))


def ratchet(root: Path) -> int:
    """Delete each baseline line no finding matches; a tightening, so it asks nothing."""

    context, status = Context(root), 0
    changes: dict[str, bytes | None] = {}
    for claim in (claim for claim in load_floor(root).claims if claim.mode == BASELINE):
        held = read_baseline(root, claim)
        if not held:
            continue
        try:
            findings, _ = findings_for(claim, context)
        except (Unreadable, FloorError) as problem:
            print(f"{UNVERIFIED} {claim.name} ({problem}; its baseline is kept)")
            status = 1
            continue
        kept = held & Counter(finding.key for finding in findings)
        removed = sum(held.values()) - sum(kept.values())
        print(f"{claim.name}: {_plural(removed, 'line')} removed, {sum(kept.values())} kept")
        if removed:
            changes[claim.baseline_path] = baseline_text(kept.elements())
    return max(status, _write(root, changes, accept=True))


PIP_TOOLS = ("ruff", "mypy")
GITLEAKS_INSTALL = (
    "go install -ldflags=-X=github.com/zricethezav/gitleaks/v8/cmd.Version={version} "
    "github.com/zricethezav/gitleaks/v8@v{version}"
)
SHELLCHECK_INSTALL = (
    "the system's packages (apt-get install shellcheck, brew install shellcheck) or a release"
    " from https://github.com/koalaman/shellcheck/releases"
)


def _newest(first: str | None, second: str | None) -> str | None:
    known = [version for version in (first, second) if version is not None]
    return max(known, key=_numbers) if known else None


def provision(root: Path, accept: bool) -> int:
    wanted: dict[str, str | None] = {}
    for claim in load_floor(root).claims:
        if claim.tool is not None and claim.prefix:
            where = " ".join(claim.prefix)
            print(f"{claim.tool} runs through {where}: install it there, and {claim.prefix[0]}")
            print("  where PATH finds it")
        elif claim.tool is not None:
            wanted[claim.tool] = _newest(wanted.get(claim.tool), claim.min_version)
    for tool, version in sorted(wanted.items()):
        if tool == "gitleaks":
            command = (
                GITLEAKS_INSTALL.format(version=version)
                if version
                else ("go install github.com/zricethezav/gitleaks/v8@latest")
            )
            print(f"gitleaks is never downloaded here; install it with: {command}")
        elif tool == "shellcheck":
            least = f" {version} or later" if version else ""
            print(f"shellcheck is never downloaded here; install{least} from {SHELLCHECK_INSTALL}")
        elif tool not in PIP_TOOLS:
            print(f"{tool} is not provisioned here; install it with the system's packages")
    packages = [f"{t}=={v}" if v else t for t, v in sorted(wanted.items()) if t in PIP_TOOLS]
    return _pip_install(root, packages, accept) if packages else 0


def _pip_install(root: Path, packages: list[str], accept: bool) -> int:
    """pip-install `packages` into the python3 PATH names. The floor finds its tools on PATH, so
    they go into the project's environment, not the one running this engine, which an installed
    tool keeps to itself."""

    python = _executable("python3")
    if python is None:
        wanted = " ".join(packages)
        print(f"no python3 on PATH to install into; install {wanted} where PATH finds them")
        return 1 if accept else 0
    # `-I` keeps the target, which is the working directory, off `sys.path`: a `pip/` package
    # committed there would otherwise run in place of pip.
    argv = [python, "-I", "-m", "pip", "install", *packages]
    print(f"{'runs' if accept else 'would run'}: {' '.join(argv)}")
    if not accept:
        print("nothing installed: pass --accept")
        return 0
    status, output, _ = validation._execute(argv, root, None, None)
    if status != 0:
        text = output.decode("utf-8", "replace").strip()
        if "externally-managed-environment" in text:
            print(f"{python} is the system's Python, which pip will not install into: activate")
            print("the project's virtual environment and run provision again")
        else:
            print(text[-2000:])
        print(f"pip exited {status}")
        return 1
    return 0


def remove(root: Path, accept: bool) -> int:
    found = [FLOOR_PATH] if fileplan.current(root, FLOOR_PATH) is not None else []
    directory = fileplan.destination(root, BASELINE_DIR)
    if directory.is_dir():
        found += sorted(f"{BASELINE_DIR}/{p.name}" for p in directory.glob("*.baseline"))
    if not found:
        print("no floor here; nothing to remove")
        return 0
    return _write(root, dict.fromkeys(found), accept)


# --- The command line -----------------------------------------------------------------------

DESCRIPTION = """\
Run a project's own ruff, mypy, gitleaks, bash and shellcheck from its root; fail on what
is new.

verbs:
  propose TARGET              print a floor.json for the stacks Git tracks; writes nothing
  apply TARGET --floor FILE   write FILE to .outcomebound/floor.json, fitted to the findings
                              the project has today (apply --help; --strict fits nothing)
  check TARGET                run the claims (check --help: --base, --claim)
  baseline TARGET             record the current findings into each empty baseline
  ratchet TARGET              delete the baseline lines no finding matches
  provision TARGET            pip-install ruff and mypy at their min_version into the
                              python3 on PATH; print gitleaks' and shellcheck's install
                              commands, never downloading either
  remove TARGET               delete .outcomebound/floor.json and the baselines

apply, baseline, provision and remove change nothing without --accept. A gate claim fails
on any finding, a baseline claim on a finding its .outcomebound/floor/<claim>.baseline
does not hold. No tool or Git read has a time limit unless its claim sets
timeout_seconds. Exit 0: every claim passed; 1: a claim failed or could not be verified;
2: the floor could not run."""
APPLY_DESCRIPTION = """\
Write FILE to .outcomebound/floor.json, fitted to what the project holds today: each claim
runs once. A claim with findings records them in its baseline and becomes a baseline claim;
an exit-status claim stays a gate, and its failure is named. A claim whose tool is missing
or too old stays as FILE has it and reads UNVERIFIED: provision the tool, then apply FILE
again to record its findings. A claim whose tool runs but cannot read this project (a
blocking error) is left out, with why. Secrets are never recorded: they are listed once, to
rotate or to allowlist by fingerprint in .gitleaksignore. floor.json records "adopted": the
commit and day, and how many findings each baseline recorded that day; without --base,
check then scans for secrets only in the commits after it.

--strict fits nothing: every claim stays as FILE has it, with empty baselines, and apply
says what each would fail on now. It adds no adoption record, and keeps one already there.
Either way, a project may later set any claim's mode to gate, which check --base reads as no
loosening.

Fitting a floor already committed is read by check --base as the loosening it is (a
baseline that gains lines, a claim moved from gate to baseline); a first floor, or a claim
floor.json adds, is not."""

CHECK_DESCRIPTION = """\
Run every claim, or --claim NAME alone, and print one line per claim.

A claim whose files match no tracked file passes: 0 findings in 0 files.

With --base REF, gitleaks scans the commits REF..HEAD (without it, the commits since the
floor's adoption record or, where there is none, the files Git tracks in the working tree,
never an ignored one), and a loosening since the merge base with REF fails: an added
baseline line; a claim floor.json drops or changes, a move from gate to baseline included;
an adoption record it changes or removes; a change to ruff.toml, .ruff.toml, mypy.ini,
.mypy.ini, .gitleaks.toml, .gitleaksignore, .shellcheckrc, shellcheckrc or the [tool.ruff],
[tool.mypy] and [mypy] settings; an added noqa, type ignore, mypy, shellcheck-disable or
gitleaks-allow comment (in a document, only gitleaks-allow).
None of these loosens: a claim floor.json adds, with its first baseline; a claim's move
from baseline to gate; a claim's timeout_seconds; a claim it drops whose files are all
gone; an adoption record where there was none; a baseline line that moves with its file,
where Git reports the file renamed.
Where the floor was adopted after the merge base (the merge base holds no floor.json), both
ranges start at the adoption commit instead, so commits from before the floor never fail.
A commit in the range whose message has the line
'Floor-Loosening: <what>; ruled <decision id>' lets it pass, the id being whatever names
the decision in the project: an issue or pull request (#123), a decision record, a link.

A project's own check is one more claim: {"name": "project.imports", "mode": "gate",
"tool": "lint-imports", "argv": ["lint-imports"], "parser": "exit"} fails when it exits
non-zero. A claim may run its tool through a prefix, "prefix": ["uv", "run"] or
["docker", "compose", "run", "--rm", "app"]: the prefix's first word comes from PATH, and its
min_version is asked through the same prefix. "timeout_seconds": 1800 stops a claim's run
after that long, and it reads UNVERIFIED; without it, the floor waits for the tool."""
VERBS = {
    "propose": "Print a floor.json for the stacks Git tracks (python, shell); write nothing.",
    "apply": APPLY_DESCRIPTION,
    "check": CHECK_DESCRIPTION,
    "baseline": "Record the current findings into each empty or absent baseline.",
    "ratchet": "Delete the baseline lines no finding matches.",
    "provision": (
        "pip-install ruff and mypy at their min_version into the python3 on PATH, where the floor\n"
        "finds its tools.\n"
        "Print the commands that install gitleaks and shellcheck, and never download either."
    ),
    "remove": "Delete .outcomebound/floor.json and the baselines.",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="outcomebound floor",
        usage="outcomebound floor <verb> TARGET [option ...]",
        description=DESCRIPTION,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    verbs = parser.add_subparsers(
        dest="verb", required=True, help=argparse.SUPPRESS, prog="outcomebound floor"
    )
    for name, description in VERBS.items():
        verb = verbs.add_parser(
            name, description=description, formatter_class=argparse.RawDescriptionHelpFormatter
        )
        verb.add_argument("target", type=Path, help="the project root")
        if name == "apply":
            verb.add_argument("--floor", type=Path, required=True, metavar="FILE")
            verb.add_argument(
                "--strict",
                action="store_true",
                help="fit nothing; add no adoption record, keeping one already there",
            )
        if name == "check":
            verb.add_argument("--base", metavar="REF", help="the tip this change replaces")
            verb.add_argument("--claim", metavar="NAME", help="run this claim alone")
        if name in ("apply", "baseline", "provision", "remove"):
            verb.add_argument("--accept", action="store_true", help="change; without it, preview")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    root = arguments.target.resolve()
    try:
        if not root.is_dir():
            raise FloorError(f"{arguments.target} is not a directory")
        if arguments.verb == "propose":
            return propose(root)
        if arguments.verb == "apply":
            return apply(root, arguments.floor, arguments.accept, arguments.strict)
        if arguments.verb == "check":
            return check(root, arguments.base, arguments.claim)
        if arguments.verb == "baseline":
            return record(root, arguments.accept)
        if arguments.verb == "ratchet":
            return ratchet(root)
        if arguments.verb == "provision":
            return provision(root, arguments.accept)
        return remove(root, arguments.accept)
    except (FloorError, fileplan.WriteError) as problem:
        print(f"floor: {problem}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
