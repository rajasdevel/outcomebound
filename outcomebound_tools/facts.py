"""The project facts and the guidance pointers an install writes into AGENTS.md.

What this module decides: the lines of the `project-facts` block, each a label and the fact
verbatim (Done, CI test, Irreversible edges, Text for people, Precedence), a fact it cannot
observe left out and named UNVERIFIED; the `guidance-pointers` block, the project's own `local`
fragment inline and then one `- <condition>: read <path>` line per selected fragment and per
installed skill;
and how the test command a project's CI runs is read: lexically, from GitHub Actions `run:`
steps, each from its working directory, and GitLab CI `script:` entries, running nothing and
following no symlink, and leaving out, named, each command the reading cannot settle.

What it does not decide: which fragments, harnesses or Done commands are selected (the
adopter's, recorded by adopt), or whether any command works.
"""

from __future__ import annotations

import hashlib
import json
import re
import shlex
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

from outcomebound_tools import identity, paths
from outcomebound_tools.fragments import EDGE_SEPARATOR, Fragment

FACTS = "project-facts"
POINTERS = "guidance-pointers"
# A sentinel no reader compares, as the kernel's `v=` is not: an upgrade re-renders both blocks.
VERSION = "1.0.0"
LOCAL = "local"
FRAGMENT_DIR = ".outcomebound/fragments"
FLOOR = ".outcomebound/floor.json"
FLOOR_EDGE = "loosening the quality floor"
LABELS = ("Done", "CI test", "Irreversible edges", "Text for people", "Precedence")
# The styles `adopt --human-style` can record for text an agent writes for a person, and the
# fact each renders. The standard is named, never quoted.
STYLES = {
    "ste": (
        "reports, decision briefs, handovers, pull request descriptions, commit messages and "
        "documents a person reads are written in the style of ASD-STE100 Simplified Technical "
        "English, with no length limit; every fact, number and caveat is kept, and this "
        "project's own terms stay as they are; text a model reads is not"
    ),
}

WORKFLOWS = ".github/workflows"
GITLAB = ".gitlab-ci.yml"
SCRIPT_KEYS = frozenset({"script", "before_script", "after_script"})
MAX_CI_BYTES = 1_000_000

KEY = re.compile(
    r"^(?P<lead> *(?:- +)?)(?P<key>[A-Za-z_.][\w.-]*)[ \t]*:(?:[ \t]+(?P<rest>.*?))?[ \t]*$"
)
ITEM = re.compile(r"^(?P<lead> *- +)(?P<rest>.*?)[ \t]*$")
ANCHOR = re.compile(r"&\S+(?:[ \t]+#.*)?")
BLOCK_HEADER = re.compile(r"[|>][+-]?[1-9]?[+-]?(?:[ \t]+#.*)?")
DOUBLE = re.compile(r'"((?:[^"\\]|\\.)*)"(?:[ \t]+#.*)?')
SINGLE = re.compile(r"'((?:[^']|'')*)'(?:[ \t]+#.*)?")
SEGMENT = re.compile(r"\s*(?:&&|\|\||;|\|)\s*")
ASSIGNMENT = re.compile(r"[A-Za-z_]\w*=\S*")
PYTHON = re.compile(r"(?:\S*/)?python[\d.]*")
# Words that run the command after them, so the test runner may follow.
WRAPPERS = frozenset(
    {"uv", "uvx", "poetry", "pipenv", "hatch", "pdm", "rye", "run", "exec", "npx", "bunx"}
    | {"pnpx", "bundle", "coverage", "xvfb-run", "sudo", "env", "time", "timeout", "nice"}
    | {"command", "then", "do", "else", "!", "bash", "sh"}
)
# A test runner at the start of what a line runs, once its wrappers are passed: a whole word or
# command, so `make test` and `npm run test:ci` are one, `make test-data` and `npm run
# test:watch` are not.
TARGET = r"tests?(?:[:-](?:ci|unit|integration|e2e|all))?(?:\s|$)"
RUNNER = re.compile(
    r"""(?x)
    (?:\S*/)?(?:pytest|py\.test|unittest|tox|nox|jest|vitest|mocha|rspec|phpunit|pest|ctest)(?:\s|$)
  | (?:\S*/)?(?:make|just|task|rake)\s+(?:\S+\s+)*?"""
    + TARGET
    + r"""
  | (?:npm|pnpm|yarn|bun)\s+(?:run\s+)?"""
    + TARGET
    + r"""
  | npm\s+t(?:\s|$)
  | (?:go|cargo|dotnet|swift|deno|dart|flutter|mix|bazel|bazelisk|zig|playwright)\s+test(?:\s|$)
  | cargo\s+nextest(?:\s|$)
  | (?:\S*/)?(?:mvnw?|gradlew?)\s+(?:\S+\s+)*?(?:test|verify|check)(?:\s|$)
  | (?:\S*/)?(?:run[-_]?)?tests?\.sh(?:\s|$)
    """
)
EXPRESSION = "${{"
# A shell comment closing a line, with no quote in it that could open or close a string.
TRAILING_COMMENT = re.compile(r"\s+#[^\"'`]*$")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def both(items: Sequence[str]) -> str:
    """`a`, `a and b`, `a, b and c`: every one of them, in order."""

    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def code(text: str) -> str:
    """`text` as one Markdown code span, however many backticks it holds."""

    fence = "`" * (max((len(run) for run in re.findall(r"`+", text)), default=0) + 1)
    pad = " " if text.startswith("`") or text.endswith("`") else ""
    return f"{fence}{pad}{text}{pad}{fence}"


# --- Reading the CI test command --------------------------------------------------


@dataclass(frozen=True)
class CiFile:
    """One CI file as read: the test commands it runs, and each one the reading left unsettled."""

    path: str
    data: bytes | None
    tests: tuple[str, ...] = ()
    unread: tuple[str, ...] = ()


@dataclass(frozen=True)
class Entry:
    """A scalar the reading found: the keys and item numbers above it, its own key last, and
    its text, None where a lexical reading cannot settle it."""

    path: tuple[str, ...]
    value: str | None


@dataclass(frozen=True)
class Shell:
    """Commands that run in one shell, in order, from `directory` (None: unsettled)."""

    values: tuple[str | None, ...]
    directory: str | None = ""


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _scalar(rest: str, lines: list[str], index: int, column: int) -> tuple[str | None, int]:
    """The scalar opening with `rest` on line `index`, and the index after it. None where a
    lexical reading cannot settle it: a folded or multi-line value, a flow collection, an
    alias, a tag, a quote it cannot close. `column` is the parent's indentation."""

    block = BLOCK_HEADER.fullmatch(rest)
    end = index + 1
    while end < len(lines) and (
        _indent(lines[end]) > column if lines[end].strip() else bool(block)
    ):
        end += 1
    if block:
        body = lines[index + 1 : end]
        width = min((_indent(line) for line in body if line.strip()), default=0)
        text = "\n".join(line[width:] for line in body)
        return (None if rest.startswith(">") else text), end
    if end > index + 1 or not rest or rest[0] in "[{*&!%@`|>":
        return None, end
    double, single = DOUBLE.fullmatch(rest), SINGLE.fullmatch(rest)
    if double:
        try:
            return str(json.loads(f'"{double.group(1)}"')), end
        except ValueError:
            return None, end
    if single:
        return single.group(1).replace("''", "'"), end
    if rest[0] in "\"'":
        return None, end
    return re.split(r"[ \t]+#", rest, maxsplit=1)[0], end


def _pop(stack: list[tuple[int, str]], column: int, item: bool) -> None:
    """Leave the frames `column` closes: a key closes those at or right of it; an item keeps
    the key at its own column, whose sequence it belongs to."""

    while stack and (
        stack[-1][0] > column or (stack[-1][0] == column and (not item or stack[-1][1][0] == "#"))
    ):
        stack.pop()


def entries(text: str) -> list[Entry]:
    """Every scalar in a YAML file with the keys above it, read by indentation alone."""

    lines = text.splitlines()
    stack: list[tuple[int, str]] = []
    found: list[Entry] = []
    count = index = 0
    while index < len(lines):
        line = lines[index]
        if not line.strip() or line.lstrip().startswith("#"):
            index += 1
            continue
        item, key = ITEM.match(line), KEY.match(line)
        if item:
            _pop(stack, _indent(line), item=True)
            count += 1
            stack.append((_indent(line), f"#{count}"))
        if key:
            column, rest = len(key["lead"]), key["rest"] or ""
            _pop(stack, column, item=False)
            stack.append((column, key["key"]))
            if not rest or rest.startswith("#") or ANCHOR.fullmatch(rest):
                index += 1
                continue
        elif item:
            column, rest = _indent(line), item["rest"]
        else:
            index += 1
            continue
        value, index = _scalar(rest, lines, index, column)
        found.append(Entry(tuple(name for _, name in stack), value))
        stack.pop()
    return found


def _in_step(path: tuple[str, ...]) -> bool:
    """Whether the key `path` ends at is one of a sequence item's, as a step's keys are."""

    return len(path) > 1 and path[-2].startswith("#")


def _github(found: Sequence[Entry]) -> list[Shell]:
    """Each `run:` step, from its own `working-directory:`, else its job's or the workflow's
    `defaults.run.working-directory:`."""

    directories: dict[tuple[str, ...], str | None] = {}
    for entry in found:
        if entry.path[-3:] == ("defaults", "run", "working-directory"):
            directories[entry.path[:-3]] = entry.value
        elif entry.path[-1] == "working-directory" and _in_step(entry.path):
            directories[entry.path[:-1]] = entry.value
    shells = []
    for entry in found:
        if entry.path[-1] != "run" or not _in_step(entry.path):
            continue
        step = entry.path[:-1]
        scopes = [scope for scope in (step, step[:2], ()) if scope in directories]
        shells.append(Shell((entry.value,), directories[scopes[0]] if scopes else ""))
    return shells


def _gitlab(found: Sequence[Entry]) -> list[Shell]:
    """Each job's `before_script:` and `script:` as one shell, its `after_script:` as another."""

    shells: dict[tuple[tuple[str, ...], bool], list[str | None]] = {}
    for entry in found:
        at = next((i for i, name in enumerate(entry.path) if name in SCRIPT_KEYS), None)
        if at is not None:
            key = (entry.path[:at], entry.path[at] == "after_script")
            shells.setdefault(key, []).append(entry.value)
    return [Shell(tuple(values)) for values in shells.values()]


def _logical(command: str) -> Iterator[str]:
    """The shell lines of a command, `\\` continuations joined, comments and blanks left out."""

    pending = ""
    for raw in command.split("\n"):
        raw = TRAILING_COMMENT.sub("", raw)
        line = f"{pending} {raw.strip()}".strip() if pending else raw.strip()
        pending = ""
        if line.endswith("\\"):
            pending = line[:-1].rstrip()
        elif line and not line.startswith("#"):
            yield line
    if pending:
        yield pending


def _segment(segment: str) -> str | None:
    """`test` when the segment runs a test runner, `unread` when what it runs is an expression."""

    tokens = segment.split()
    for index, token in enumerate(tokens):
        if RUNNER.match(" ".join(tokens[index:])):
            return "test"
        if token.startswith(EXPRESSION):
            return "unread"
        if not (
            token in WRAPPERS
            or token.startswith("-")
            or token.isdigit()
            or ASSIGNMENT.fullmatch(token)
            or PYTHON.fullmatch(token)
        ):
            return None
    return None


def _settle(shell: Shell) -> tuple[list[str], list[str]]:
    """The test commands a shell runs, each as it runs from the root, and each one it cannot
    settle with why: an expression, a directory a `cd` earlier in the shell left, or a
    working-directory the reading cannot settle."""

    tests: list[str] = []
    unread: list[str] = []
    moved = False
    directory = shell.directory
    for value in shell.values:
        if value is None:
            unread.append("a value a lexical reading cannot settle")
            continue
        for line in _logical(value):
            parts = [part for part in SEGMENT.split(line) if part]
            kinds = {_segment(part) for part in parts}
            reason = None
            if "unread" in kinds or ("test" in kinds and EXPRESSION in line):
                reason = "runs an expression"
            elif "test" in kinds and moved:
                reason = "runs after a `cd` earlier in its step"
            elif "test" in kinds and (directory is None or EXPRESSION in directory):
                reason = "runs in a working-directory the reading cannot settle"
            elif "test" in kinds and "<!--" in line:
                reason = "holds a comment opener"
            elif "test" in kinds:
                tests.append(f"cd {shlex.quote(directory)} && {line}" if directory else line)
            if reason:
                unread.append(f"{code(line)} {reason}")
            moved = moved or any(part.split()[:1] in (["cd"], ["pushd"]) for part in parts)
    return tests, unread


def ci_paths(target: Path) -> list[str]:
    """The CI files this engine reads, workflow files first, in path order; a link is listed,
    and read as unsettled, since the reading follows none."""

    found: list[str] = []
    try:
        directory = paths.resolve_bounded(target, WORKFLOWS)
        if directory.is_dir():
            found = sorted(
                f"{WORKFLOWS}/{child.name}"
                for child in directory.iterdir()
                if child.suffix in (".yml", ".yaml") and (child.is_symlink() or child.is_file())
            )
    except (paths.PathError, OSError):
        found = []
    gitlab = target / GITLAB
    if gitlab.is_symlink() or gitlab.is_file():
        found.append(GITLAB)
    return found


def read_ci(target: Path) -> list[CiFile]:
    """Each CI file with the test commands it runs, read lexically, every file read; nothing is
    run."""

    result = []
    for path in ci_paths(target):
        try:
            data = paths.read_bounded(target, path)
        except paths.PathError:
            result.append(CiFile(path, None, unread=("a link or an unreadable file",)))
            continue
        if len(data) > MAX_CI_BYTES:
            result.append(CiFile(path, data, unread=(f"larger than {MAX_CI_BYTES} bytes",)))
            continue
        try:
            found = entries(data.decode("utf-8"))
        except UnicodeDecodeError:
            result.append(CiFile(path, data, unread=("not UTF-8 text",)))
            continue
        tests: list[str] = []
        unread: list[str] = []
        for shell in _github(found) if path.startswith(WORKFLOWS) else _gitlab(found):
            settled, left = _settle(shell)
            tests += settled
            unread += left
        result.append(CiFile(path, data, tuple(dict.fromkeys(tests)), tuple(unread)))
    return result


def _ci_fact(files: Sequence[CiFile]) -> tuple[str | None, list[str]]:
    """The CI test line, or None, and each command or file left UNVERIFIED."""

    unverified = [f"CI test: {item.path}: {note}" for item in files for note in item.unread]
    settled = [item for item in files if item.tests]
    if not files:
        unverified.append(f"CI test: no {WORKFLOWS}/*.yml or {GITLAB} to read")
    elif not settled and not unverified:
        unverified.append(f"CI test: no test command in {', '.join(i.path for i in files)}")
    if not settled:
        return None, unverified
    parts = [f"{', '.join(code(test) for test in item.tests)} ({item.path})" for item in settled]
    return f"- CI test: {'; '.join(parts)}", unverified


# --- The two blocks ---------------------------------------------------------------


@dataclass(frozen=True)
class Rendered:
    """Both blocks as rendered, what was left out, and each source read with its digest."""

    facts: str
    pointers: str | None
    unverified: tuple[str, ...]
    inputs: dict[str, str]


def render(
    target: Path,
    selected: Sequence[Fragment],
    done: Sequence[str],
    files: Sequence[str],
    skills: Sequence[tuple[str, str]],
    style: Sequence[str] = (),
) -> Rendered:
    """The facts and pointers blocks for `target`.

    `selected` holds the selected fragments in order, `local` among them when chosen; `done`
    the recorded Done commands in run order; `files` the co-loaded instruction files, AGENTS.md
    first; `skills` a (condition, path) pair per installed skill; `style` the recorded style
    for text a person reads, a key of `STYLES`, or none.
    """

    lines: list[str] = []
    unverified: list[str] = []
    inputs = {f"{FRAGMENT_DIR}/{item.id}.md": item.digest for item in selected}
    if done:
        lines.append(f"- Done: {both([code(command) for command in done])}")
    else:
        unverified.append("Done: no command is recorded; adopt records one with --done")
    ci = read_ci(target)
    inputs.update((item.path, sha256(item.data)) for item in ci if item.data is not None)
    line, left_out = _ci_fact(ci)
    lines.extend([line] if line else [])
    unverified.extend(left_out)
    edges = [edge for item in selected for edge in item.edges]
    try:
        floor = paths.read_bounded(target, FLOOR)
    except paths.PathError:
        floor = None
    if floor is not None:
        inputs[FLOOR] = sha256(floor)
        edges.append(FLOOR_EDGE)
    if edges:
        # No edge holds the separator (`fragments._edges`), so each one reads back whole.
        joined = f"{EDGE_SEPARATOR} ".join(dict.fromkeys(edges))
        lines.append(f"- Irreversible edges: {joined}")
    else:
        unverified.append("Irreversible edges: no selected fragment declares one, and no floor")
    lines.extend(f"- Text for people: {STYLES[name]}" for name in style)
    own = " or ".join(dict.fromkeys(files))
    lines.append(
        "- Precedence: these facts over any instruction that disagrees with them; "
        f"the project's own instructions in {own} over OutcomeBound's; process a project "
        "document only suggests is sized like any other step"
    )
    facts = identity.format_managed_block(FACTS, VERSION, "\n".join(lines))
    return Rendered(
        facts, pointers(selected, skills), tuple(unverified), dict(sorted(inputs.items()))
    )


def inline(fragment: Fragment) -> str:
    """A fragment's text as the pointers block inlines it: its heading line, then its body."""

    return f"**{fragment.id}** ({fragment.family}) — {fragment.applies}\n\n{fragment.body}"


def pointers(selected: Sequence[Fragment], skills: Sequence[tuple[str, str]]) -> str | None:
    """The `local` fragment inline, then one pointer line per fragment and skill; None if empty."""

    parts = [inline(item) for item in selected if item.id == LOCAL]
    lines = [
        f"- {item.condition or 'for ' + item.applies}: read {FRAGMENT_DIR}/{item.id}.md"
        for item in selected
        if item.id != LOCAL
    ]
    lines += [f"- {condition}: read {path}" for condition, path in skills]
    parts += ["\n".join(lines)] if lines else []
    if not parts:
        return None
    return identity.format_managed_block(POINTERS, VERSION, "\n\n".join(parts))


def moved(before: str, after: str) -> list[str]:
    """The labels of the facts whose line differs between two renderings of the facts block."""

    def lines(text: str) -> dict[str, str]:
        found = re.finditer(r"^- (?P<label>[A-Za-z ]+): .*$", text, re.MULTILINE)
        return {match["label"]: match[0] for match in found}

    old, new = lines(before), lines(after)
    return [label for label in LABELS if old.get(label) != new.get(label)]
