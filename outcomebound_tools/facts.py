"""The project facts and the guidance pointers an install writes into AGENTS.md.

What this module decides: the lines of the `project-facts` block, each a label and the fact
verbatim (Done, Setup, CI test, Irreversible edges, Text for people, Precedence), a fact it cannot
observe left out and named UNVERIFIED; the `guidance-pointers` block, the project's own `local`
fragment inline and then one `- <condition>: read <path>` line per selected fragment and per
installed skill;
and how the test command a project's CI runs is read: lexically, from GitHub Actions `run:`
steps, each from its working directory, and GitLab CI `script:` entries, running nothing and
following no symlink, and leaving out, named, each command the reading cannot settle; and the
onboarding signals `--detect` prints, read the same way (generated paths, applied migration
folders, publishing workflows, runtime versions, environment names, CI secret names, lockfiles
and the project's own setup entry points), each a candidate a person confirms.

What it does not decide: which fragments, harnesses or Done commands are selected (the
adopter's, recorded by adopt), or whether any command works.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

from outcomebound_tools import discovery, identity, paths, textio
from outcomebound_tools.fragments import EDGE_SEPARATOR, Fragment

FACTS = "project-facts"
POINTERS = "guidance-pointers"
# A sentinel no reader compares, as the kernel's `v=` is not: an upgrade re-renders both blocks.
VERSION = "1.0.0"
LOCAL = "local"
FRAGMENT_DIR = ".outcomebound/fragments"
FLOOR = ".outcomebound/floor.json"
FLOOR_EDGE = "loosening the quality floor"
LABELS = ("Done", "Setup", "CI test", "Irreversible edges", "Text for people", "Precedence")
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
    # Internal proposal candidates only; observed CI facts retain commands from every shell.
    done: tuple[str, ...] = ()
    # Each test command with the job that runs it, one pair for each job; "" where none is named.
    jobs: tuple[tuple[str, str], ...] = ()
    # Each test command with its job and the step item that runs it ("" for a GitLab job).
    places: tuple[tuple[str, str, str], ...] = ()


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
    name: str | None = None
    job: str = ""
    step: str = ""


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


def _github_shell_settings(found: Sequence[Entry]) -> dict[tuple[str, ...], str | None]:
    """Explicit shell settings by scope, including defaults the lexical reader cannot settle."""

    settings: dict[tuple[str, ...], str | None] = {}
    for entry in found:
        if entry.path[-3:] == ("defaults", "run", "shell"):
            settings[entry.path[:-3]] = entry.value
        elif entry.path[-1] == "shell" and _in_step(entry.path):
            settings[entry.path[:-1]] = entry.value
        elif entry.value is None and entry.path[-1] == "defaults":
            settings[entry.path[:-1]] = None
        elif entry.value is None and entry.path[-2:] == ("defaults", "run"):
            settings[entry.path[:-2]] = None
    return settings


def _github_default_shell(runner: str | None) -> str | None:
    """A hosted runner's documented shell family; unknown or dynamic runners stay unsettled."""

    if runner is None:
        return None
    if re.fullmatch(r"windows-(?:latest|\d+)(?:-arm)?", runner):
        return "pwsh"
    if re.fullmatch(r"ubuntu-(?:latest|slim|\d+\.\d+)(?:-arm)?", runner) or re.fullmatch(
        r"macos-(?:latest|\d+)(?:-(?:large|xlarge|intel))?", runner
    ):
        return "bash"
    return None


def _github(found: Sequence[Entry]) -> list[Shell]:
    """Each `run:` step, from its own `working-directory:`, else its job's or the workflow's
    `defaults.run.working-directory:`."""

    directories: dict[tuple[str, ...], str | None] = {}
    for entry in found:
        if entry.path[-3:] == ("defaults", "run", "working-directory"):
            directories[entry.path[:-3]] = entry.value
        elif entry.path[-1] == "working-directory" and _in_step(entry.path):
            directories[entry.path[:-1]] = entry.value
    settings = _github_shell_settings(found)
    runners = {entry.path[:-1]: entry.value for entry in found if entry.path[-1] == "runs-on"}
    shells = []
    for entry in found:
        if entry.path[-1] != "run" or not _in_step(entry.path):
            continue
        step = entry.path[:-1]
        scopes = [scope for scope in (step, step[:2], ()) if scope in directories]
        name = next(
            (settings[scope] for scope in (step, step[:2], ()) if scope in settings),
            _github_default_shell(runners.get(step[:2])),
        )
        job = step[1] if len(step) > 1 and step[0] == "jobs" else ""
        item = step[3] if len(step) > 3 and step[0] == "jobs" and step[2] == "steps" else ""
        shells.append(
            Shell((entry.value,), directories[scopes[0]] if scopes else "", name, job, item)
        )
    return shells


def _gitlab(found: Sequence[Entry]) -> list[Shell]:
    """Each job's `before_script:` and `script:` as one shell, its `after_script:` as another."""

    shells: dict[tuple[tuple[str, ...], bool], list[str | None]] = {}
    for entry in found:
        at = next((i for i, name in enumerate(entry.path) if name in SCRIPT_KEYS), None)
        if at is not None:
            key = (entry.path[:at], entry.path[at] == "after_script")
            shells.setdefault(key, []).append(entry.value)
    return [Shell(tuple(values), job=key[0][0] if key[0] else "") for key, values in shells.items()]


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
            found = entries(textio.decode(data))
        except UnicodeDecodeError:
            result.append(CiFile(path, data, unread=("not UTF-8 text",)))
            continue
        tests: list[str] = []
        unread: list[str] = []
        done: list[str] = []
        jobs: list[tuple[str, str]] = []
        places: list[tuple[str, str, str]] = []
        for shell in _github(found) if path.startswith(WORKFLOWS) else _gitlab(found):
            settled, left = _settle(shell)
            tests += settled
            unread += left
            jobs += [(command, shell.job) for command in settled]
            places += [(command, shell.job, shell.step) for command in settled]
            if shell.name in ("sh", "bash"):
                done += settled
        result.append(
            CiFile(
                path,
                data,
                tuple(dict.fromkeys(tests)),
                tuple(unread),
                tuple(dict.fromkeys(done)),
                tuple(dict.fromkeys(jobs)),
                tuple(dict.fromkeys(places)),
            )
        )
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


class Chosen(NamedTuple):
    """What the adopter chose for the facts block: the Done commands, in run order, the style
    for text a person reads, a key of `STYLES`, or none, and the Setup commands, in run order,
    which adopt records as the person's fact and never runs."""

    done: Sequence[str]
    style: Sequence[str] = ()
    setup: Sequence[str] = ()


def render(
    target: Path,
    selected: Sequence[Fragment],
    done: Sequence[str],
    files: Sequence[str],
    skills: Sequence[tuple[str, str]],
    style: Sequence[str] = (),
) -> Rendered:
    """The facts and pointers blocks for `target`, for a project that records no Setup:
    `render_chosen` with Done and the style for text a person reads."""

    return render_chosen(target, selected, Chosen(done, style), files, skills)


def render_chosen(
    target: Path,
    selected: Sequence[Fragment],
    chosen: Chosen,
    files: Sequence[str],
    skills: Sequence[tuple[str, str]],
) -> Rendered:
    """The facts and pointers blocks for `target`.

    `selected` holds the selected fragments in order, `local` among them when chosen; `chosen`
    the recorded Done and Setup commands in run order and the style for text a person reads;
    `files` the co-loaded instruction files, AGENTS.md first; `skills` a (condition, path) pair
    per installed skill.
    """

    done, style, setup = chosen
    lines: list[str] = []
    unverified: list[str] = []
    inputs = {f"{FRAGMENT_DIR}/{item.id}.md": item.digest for item in selected}
    if done:
        lines.append(f"- Done: {both([code(command) for command in done])}")
    else:
        unverified.append("Done: no command is recorded; adopt records one with --done")
    if setup:
        lines.append(f"- Setup: {both([code(command) for command in setup])}")
    else:
        unverified.append("Setup: no command is recorded; adopt records one with --setup")
    ci = read_ci(target)
    inputs.update(
        (item.path, sha256(textio.fold(item.data))) for item in ci if item.data is not None
    )
    line, left_out = _ci_fact(ci)
    lines.extend([line] if line else [])
    unverified.extend(left_out)
    edges = [edge for item in selected for edge in item.edges]
    try:
        floor = paths.read_bounded(target, FLOOR)
    except paths.PathError:
        floor = None
    if floor is not None:
        inputs[FLOOR] = sha256(textio.fold(floor))
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


# --- What the target's files show for onboarding ----------------------------------
#
# adopt's reading, as the CI test fact is: lexical, of files read whole under a size bound,
# running nothing and following no link. Each signal is a candidate a person confirms, never a
# finding; a file the reading cannot settle is named, not guessed at.

BOUNDS, CONTEXT, DISTINGUISH = "Bounds", "Context", "Distinguish"
MAX_SIGNAL_BYTES = MAX_CI_BYTES
GENERATED = "linguist-generated"
ATTRIBUTE_LINE = re.compile(r'^(?:"((?:[^"\\]|\\.)*)"|(\S+))\s*(.*)$')
# The commands and the actions that publish or deploy. A step that runs one is a candidate for
# the project's list of irreversible edges.
PUBLISHING_COMMANDS = (
    ("npm", "publish"),
    ("twine", "upload"),
    ("uv", "publish"),
    ("cargo", "publish"),
    ("gh", "release", "create"),
    ("docker", "push"),
    ("terraform", "apply"),
    ("kubectl", "apply"),
    ("helm", "upgrade"),
    ("fly", "deploy"),
    ("wrangler", "deploy"),
    ("firebase", "deploy"),
)
PUBLISHING_ACTIONS = frozenset(
    {
        "pypa/gh-action-pypi-publish",
        "js-devtools/npm-publish",
        "rubygems/release-gem",
        "softprops/action-gh-release",
        "ncipollo/release-action",
        "actions/deploy-pages",
        "peaceiris/actions-gh-pages",
        "helm/chart-releaser-action",
        "cloudflare/wrangler-action",
        "azure/webapps-deploy",
        "google-github-actions/deploy-cloudrun",
        "aws-actions/amazon-ecs-deploy-task-definition",
        "firebaseextended/action-hosting-deploy",
    }
)
SECRET = re.compile(
    r"\bsecrets\.([A-Za-z_][A-Za-z0-9_]*)|\bsecrets\[\s*['\"]([A-Za-z_]\w*)['\"]\s*\]"
)
ENVIRONMENT_FILES = (".env.example", ".env.sample")
ENVIRONMENT_NAME = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=")
RUNTIME_FILES = (
    ".python-version",
    ".nvmrc",
    ".node-version",
    ".tool-versions",
    "rust-toolchain",
    "rust-toolchain.toml",
)
# A lockfile and the command that installs from it; the person picks, and the engine proposes
# none of them.
LOCKFILE_INSTALLS = (
    ("package-lock.json", "npm ci"),
    ("pnpm-lock.yaml", "pnpm install --frozen-lockfile"),
    ("yarn.lock", "yarn install --frozen-lockfile (Yarn 1) or yarn install --immutable (Yarn 2+)"),
    ("bun.lock", "bun install --frozen-lockfile"),
    ("bun.lockb", "bun install --frozen-lockfile"),
    ("uv.lock", "uv sync --frozen"),
    ("poetry.lock", "poetry install"),
    ("Pipfile.lock", "pipenv sync"),
    ("Gemfile.lock", "bundle install"),
    ("Cargo.lock", "cargo fetch --locked"),
    ("go.sum", "go mod download"),
    ("composer.lock", "composer install"),
)
MANIFEST_LOCKS = (
    (
        "package.json",
        (
            *("package-lock.json", "npm-shrinkwrap.json", "pnpm-lock.yaml"),
            *("yarn.lock", "bun.lock", "bun.lockb"),
        ),
    ),
    ("pyproject.toml", ("uv.lock", "poetry.lock", "pdm.lock", "pylock.toml")),
    ("Pipfile", ("Pipfile.lock",)),
    ("Cargo.toml", ("Cargo.lock",)),
    ("go.mod", ("go.sum",)),
    ("composer.json", ("composer.lock",)),
    ("Gemfile", ("Gemfile.lock",)),
)
PACKAGE_MANAGERS = (
    ("pnpm-lock.yaml", "pnpm"),
    ("yarn.lock", "yarn"),
    ("bun.lock", "bun"),
    ("bun.lockb", "bun"),
)
MAKEFILES = ("GNUmakefile", "makefile", "Makefile")
SETUP_NAMES = ("setup", "bootstrap")
SETUP_EXECUTABLES = ("bin/setup", "script/setup", "script/bootstrap", "scripts/setup.sh")
MAKE_TARGET = re.compile(r"^(setup|bootstrap)[ \t]*:(?!=)", re.MULTILINE)


class Signal(NamedTuple):
    """One onboarding signal: its kind, the file or folders that show it, the value read (empty
    where none), and the slot of the project's `local` fragment a proposed line goes to."""

    kind: str
    where: str
    value: str
    slot: str


class SetupCandidate(NamedTuple):
    """The project's own entry point for setup: the command to record, and what shows it."""

    command: str
    evidence: str


def read_small(target: Path, relative: str) -> tuple[str | None, str]:
    """(the file's text, why it was not read): no text and no reason where the path is absent;
    a reason where it is a link, unreadable, not UTF-8 text or over `MAX_SIGNAL_BYTES`."""

    if not os.path.lexists(target / relative):
        return None, ""
    try:
        if (target / relative).lstat().st_size > MAX_SIGNAL_BYTES:
            return None, f"larger than {MAX_SIGNAL_BYTES} bytes"
        data = paths.read_bounded(target, relative)
    except (paths.PathError, OSError):
        return None, "a link or an unreadable file"
    try:
        return textio.universal(textio.decode(data)), ""
    except UnicodeDecodeError:
        return None, "not UTF-8 text"


def generated_patterns(text: str) -> list[str]:
    """The `.gitattributes` patterns that set `linguist-generated`, in file order, once each."""

    found: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        match = None if not line or line.startswith(("#", "[attr]")) else ATTRIBUTE_LINE.match(line)
        if match is None:
            continue
        marked = False
        for attribute in match.group(3).split():
            if attribute in (GENERATED, f"{GENERATED}=true"):
                marked = True
            elif attribute in (f"-{GENERATED}", f"!{GENERATED}", f"{GENERATED}=false"):
                marked = False
        if marked:
            found.append(match.group(1) if match.group(1) is not None else match.group(2))
    return list(dict.fromkeys(found))


def migration_folders(tracked: Iterable[str]) -> list[str]:
    """The tracked folders named `migrations` or `alembic`, or `db/migrate`, the names
    discovery reads, each once, sorted: a folder of many files is one signal."""

    nested = {names[-1]: names[:-1] for names in discovery.NESTED_MIGRATION_DIRECTORIES}
    found: set[str] = set()
    for path in tracked:
        parts = path.split("/")[:-1]
        for index, part in enumerate(parts):
            if part in discovery.MIGRATION_DIRECTORIES or (
                part in nested
                and tuple(parts[max(index - len(nested[part]), 0) : index]) == nested[part]
            ):
                found.add("/".join(parts[: index + 1]))
    return sorted(found)


def environment_names(text: str) -> list[str]:
    """The variable names an example environment file sets, in file order, once each; never a
    value."""

    names = (
        ENVIRONMENT_NAME.match(line)
        for line in text.splitlines()
        if not line.lstrip().startswith("#")
    )
    return list(dict.fromkeys(match.group(1) for match in names if match is not None))


def runtime_value(name: str, text: str) -> str:
    """The version a runtime file names: its non-comment lines joined, a `channel` for a Rust
    toolchain file; empty where it names none."""

    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line and not line.startswith("#")]
    channel = re.search(r"(?m)^\s*channel\s*=\s*[\"']([^\"']+)[\"']", text)
    if name.startswith("rust-toolchain") and channel:
        return channel.group(1)
    if name.endswith(".toml"):
        return ""
    return "; ".join(lines) if name == ".tool-versions" else ", ".join(lines)


def requires_python(text: str) -> str:
    """The `requires-python` value in the `[project]` table of a pyproject.toml; empty if none."""

    inside = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("["):
            inside = re.fullmatch(r"\[project\]\s*(?:#.*)?", stripped) is not None
        elif inside:
            found = re.match(r"""requires-python\s*=\s*(["'])(.*?)\1""", stripped)
            if found:
                return found.group(2)
    return ""


def _runtime_version(name: str, text: str) -> str:
    """The version `name` names: a runtime file's, the `requires-python` of a pyproject.toml or
    the `go` line of a go.mod; empty where it names none."""

    if name == "pyproject.toml":
        found = requires_python(text)
        return f"requires-python {found}" if found else ""
    if name == "go.mod":
        line = re.search(r"(?m)^go\s+([\w.]+)", text)
        return f"go {line.group(1)}" if line else ""
    return runtime_value(name, text)


def runtime_signals(target: Path) -> tuple[list[Signal], list[tuple[str, str]]]:
    """The runtime-version signals of the target's root, and the files it could not read."""

    signals: list[Signal] = []
    unread: list[tuple[str, str]] = []
    for name in (*RUNTIME_FILES, "pyproject.toml", "go.mod"):
        text, why = read_small(target, name)
        if text is None:
            unread.extend([(name, why)] if why else [])
            continue
        value = _runtime_version(name, text)
        if value:
            signals.append(Signal("runtime-version", name, value, CONTEXT))
    return signals, unread


def _publishing(part: str) -> str | None:
    """The publishing command a shell segment runs, once its wrappers are passed."""

    tokens = part.split()
    for index, token in enumerate(tokens):
        for words in PUBLISHING_COMMANDS:
            if tuple(tokens[index : index + len(words)]) == words:
                return " ".join(words)
        wrapper = (
            token in WRAPPERS
            or token.startswith("-")
            or token.isdigit()
            or ASSIGNMENT.fullmatch(token)
            or PYTHON.fullmatch(token)
        )
        if not wrapper:
            return None
    return None


def _workflows(files: Sequence[CiFile]) -> Iterator[tuple[CiFile, list[Entry]]]:
    """Each GitHub workflow file read, with its scalars; a file not read, or not text, is
    passed over, as `read_ci` names it."""

    for item in files:
        if item.data is None or not item.path.startswith(WORKFLOWS):
            continue
        try:
            yield item, entries(textio.decode(item.data))
        except UnicodeDecodeError:
            continue


def _job(entry: Entry) -> str:
    """The job a scalar sits in; empty for one outside every job."""

    return entry.path[1] if len(entry.path) > 1 and entry.path[0] == "jobs" else ""


def _secrets(found: Sequence[Entry]) -> dict[str, list[str]]:
    """Each secret name a workflow's scalars name, never a value, `GITHUB_TOKEN` left out, with
    the jobs that name it ("" for the workflow outside every job)."""

    names: dict[str, list[str]] = {}
    for entry in found:
        for match in SECRET.finditer(entry.value or ""):
            name = match.group(1) or match.group(2)
            if name != "GITHUB_TOKEN":
                names.setdefault(name, []).append(_job(entry))
    return {name: list(dict.fromkeys(jobs)) for name, jobs in names.items()}


def _publishing_acts(found: Sequence[Entry]) -> list[str]:
    """Each step of a workflow that runs a publishing command or uses a publishing action, as
    `job <job> runs <command>` or `job <job> uses <action>`, once each."""

    acts: list[str] = []
    for entry in found:
        if not _in_step(entry.path) or entry.value is None:
            continue
        where = f"job {_job(entry)}" if _job(entry) else "the workflow"
        if entry.path[-1] == "run":
            parts = (part for line in _logical(entry.value) for part in _parts(line))
            acts += [f"{where} runs {command}" for part in parts if (command := _publishing(part))]
        elif entry.path[-1] == "uses" and _action(entry.value) in PUBLISHING_ACTIONS:
            acts.append(f"{where} uses {entry.value.split('@')[0]}")
    return list(dict.fromkeys(acts))


def workflow_signals(files: Sequence[CiFile]) -> list[Signal]:
    """The publishing-workflow and ci-secrets signals of the GitHub workflow files read: the
    workflow, the job and the command or action; the secret names, never a value, with the jobs
    that name them."""

    signals: list[Signal] = []
    for item, found in _workflows(files):
        signals += [
            Signal("publishing-workflow", item.path, act, f"{BOUNDS} (edges:)")
            for act in _publishing_acts(found)
        ]
        secrets = _secrets(found)
        if secrets:
            listed = "; ".join(
                f"{name} in {', '.join(f'job {job}' if job else 'the workflow' for job in jobs)}"
                for name, jobs in sorted(secrets.items())
            )
            signals.append(Signal("ci-secrets", item.path, listed, DISTINGUISH))
    return signals


def _parts(line: str) -> list[str]:
    return [part for part in SEGMENT.split(line) if part]


def _action(uses: str) -> str:
    """`owner/repo` of a `uses:` value, in lower case: the action without its path and version."""

    return "/".join(uses.split("@")[0].lower().split("/")[:2])


def secrets_reaching(files: Sequence[CiFile]) -> dict[tuple[str, str, str], list[str]]:
    """The secret names a GitHub workflow passes to a step's command, by (file, job, step item):
    those in the workflow's `env`, the job's `env`, or the step itself. A name used elsewhere,
    such as in another step, reaches no other step's command, so it is not counted for it."""

    found: dict[tuple[str, str, str], list[str]] = {}
    for item, scalars in _workflows(files):
        everywhere = [
            name for entry in scalars if entry.path[:1] == ("env",) for name in _named(entry)
        ]
        for _command, job, step in item.places:
            names = list(everywhere)
            for entry in scalars:
                head = entry.path
                if head[:3] == ("jobs", job, "env") or (
                    step and head[:4] == ("jobs", job, "steps", step)
                ):
                    names += _named(entry)
            if names:
                found[(item.path, job, step)] = sorted(set(names))
    return found


def _named(entry: Entry) -> list[str]:
    """The secret names one scalar holds, `GITHUB_TOKEN` left out."""

    return [
        name
        for match in SECRET.finditer(entry.value or "")
        if (name := match.group(1) or match.group(2)) != "GITHUB_TOKEN"
    ]


def lockfile_candidates(target: Path) -> list[tuple[str, str]]:
    """(lockfile, the command that installs from it) for each lockfile at the target's root."""

    return [(name, command) for name, command in LOCKFILE_INSTALLS if _file(target, name)]


def manifests_without_lock(target: Path) -> list[str]:
    """Each manifest at the target's root that has no lockfile of its kind beside it."""

    return [
        manifest
        for manifest, locks in MANIFEST_LOCKS
        if _file(target, manifest) and not any(_file(target, lock) for lock in locks)
    ]


def _file(target: Path, relative: str) -> bool:
    """Whether `relative` is a regular file inside the target, reached by no link."""

    try:
        return paths.resolve_bounded(target, relative).is_file() and not paths.redirects(
            target / relative
        )
    except (paths.PathError, OSError):
        return False


def setup_candidates(target: Path) -> list[SetupCandidate]:
    """The project's own entry points for setup, in the order proposed: a Make target, a
    `package.json` script, an executable script. Nothing is run; the first is what `--detect`
    proposes, and the rest are named."""

    found: list[SetupCandidate] = []
    try:
        names = {entry.name for entry in target.iterdir()}
    except OSError:
        names = set()
    # GNU make reads the first of these that exists; a file system that ignores case lists the
    # name as it is spelled.
    for makefile in (name for name in MAKEFILES if name in names):
        text, _ = read_small(target, makefile)
        if text is not None:
            targets = {match.group(1) for match in MAKE_TARGET.finditer(text)}
            found += [
                SetupCandidate(f"make {name}", f"{makefile} target {name}")
                for name in SETUP_NAMES
                if name in targets
            ]
            break
    found += _package_setup(target)
    for relative in SETUP_EXECUTABLES:
        if _file(target, relative) and os.access(target / relative, os.X_OK):
            found.append(SetupCandidate(f"./{relative}", f"executable {relative}"))
    return found


def _package_setup(target: Path) -> list[SetupCandidate]:
    """The `setup` and `bootstrap` scripts of the root `package.json`, run by the package
    manager its lockfile names, else npm."""

    text, _ = read_small(target, "package.json")
    try:
        scripts = json.loads(text or "{}").get("scripts", {})
    except (ValueError, AttributeError):
        return []
    if not isinstance(scripts, dict):
        return []
    manager = next(
        (name for lock, name in PACKAGE_MANAGERS if _file(target, lock)),
        "npm",
    )
    return [
        SetupCandidate(f"{manager} run {name}", f"package.json script {name}")
        for name in SETUP_NAMES
        if isinstance(scripts.get(name), str)
    ]
