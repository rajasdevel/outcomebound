#!/usr/bin/env python3
"""The release canary: this checkout's engine beside the installed release, on the
projects of a local list.

The list is the file that `OB_CANARY_LIST` names: one project path a line, `#` for a comment, a
relative path read from the list's folder. The list is private, so it stays outside this
repository, and nothing printed or recorded names a project's path: a project is named by its
number in the list.

For each project, the installed release (`outcomebound` on PATH, less this checkout's launcher)
and the candidate (this checkout) each run `adopt <p> --dry-run`, `adopt <p> --check` and
`instructions check <p> --json`, and, where the project holds them:

- `floor check <p> --base HEAD` where `.outcomebound/floor.json` exists. HEAD as the base makes
  the change range empty, so every claim runs over the tree, the secrets claim scans no commit,
  and no adoption commit is needed. Floor commands may use the network or write.
  A floor run has no time limit; its
  seconds are reported.
- `tickets check <p> --json --draft <files>` for each draft set the project names: each
  `tickets check --draft` command of the claims plan that `.outcomebound/tickets.json` names,
  its files read from the plan's cwd and kept only inside the project. The layer has no
  conventional folder for drafts, and the tree is never searched for them.
- `tickets check <p> --json --input issues.json` where a readable `issues.json`, the file the
  export command writes, is in the project root; else the line says UNVERIFIED and why. The
  canary calls no tracker.

Each command that does not run gets a line that says why. The candidate runs under each
`--python`; by default the oldest supported Python (3.10, from `uv python find 3.10` or
`python3.10` on PATH) and the Python the installed release runs under, since a Python version
can change what the standard library raises. Every run gets
`RUFF_CACHE_DIR` and `MYPY_CACHE_DIR` in a temporary folder, and `git status --porcelain
--untracked-files=all` and the ignored entries (a folder Git ignores named once) are read
before the runs and after each engine's run. These checks detect reported changes after execution;
they compare status and entry names, not file contents. They do not prevent writes or prove
unchanged contents, including files that are already dirty, untracked or ignored. Inspect custom
floor commands first. Where they may write, use an owned isolated checkout with the required
inputs and retain its identity; distinguish its results from original-checkout observations.
Cache redirection is not a sandbox for arbitrary commands. No gate is skipped.

The report names, per project and per run, a crash (a traceback, a signal, or an exit that is
not the command's documented verdict), an exception adopt reports (`adopt: [Errno N] ...`), a
refusal (another `adopt:` reason, a `floor:` reason, or a ticket verb's named code with no
report), a changed verdict or exit code, and the report lines added or removed by kind: an adopt
`warning` or `UNVERIFIED` line by its first four words, each word that is not a plain word shown
as `<...>`, and any other adopt line by its first word; an instruction finding by its check and
verdict; a floor claim by its name (a name the engine's recipes do not give shown as `<...>`)
and its result; a ticket message by its level and its code. The verdict is the last line. A
crash, an exception or a refusal of the candidate, a command of the candidate that printed no
valid report (`--json` with no JSON, a required field missing or of the wrong type, a result
that disagrees with its exit, or a floor exit that its claim lines do not explain), a difference
in the before/after Git status or ignored-entry list, or a project that is not a Git work tree
is FAIL; a valid report whose
result is UNVERIFIED is a verdict, compared as any other; anything else is PASS, and the kinds
added and removed are printed for a person to judge. Where the installed release failed and the
candidate did not, the line says `no baseline: installed engine failed`, and nothing of that
command is compared.

The verdict is recorded in the Git common directory, under `outcomebound-canary/`, keyed by the
tree of HEAD: `main` takes squash merges, so the release commit is a new commit with the tree of
the branch the canary ran on. No record is written while the checkout holds changes not
committed, since HEAD's tree is then not what ran. `--verify` reads PASS where a PASS record
exists for HEAD's tree, else FAIL; `make release-check` runs it first.

Exit 0: PASS; 1: FAIL; 2: UNVERIFIED (no list, no installed release, no interpreter) or usage.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

NAME = "canary"
LIST_ENV = "OB_CANARY_LIST"
ROOT = Path(__file__).resolve().parent.parent
RECORDS = "outcomebound-canary"
OLDEST = "3.10"
# What the launcher of a checkout runs: the engine of the checkout named first, isolated.
RUNPY = (
    "import runpy, sys\n"
    "sys.path.insert(0, sys.argv[1])\n"
    'sys.argv = ["outcomebound", *sys.argv[2:]]\n'
    'runpy.run_module("outcomebound_tools", run_name="__main__", alter_sys=True)\n'
)


@dataclass(frozen=True)
class Command:
    """One command both engines run on a project: its label in the report, its arguments
    around the project, the exits it documents, how its output is read, and whether its seconds
    are reported."""

    label: str
    arguments: tuple[str, ...]
    exits: frozenset[int]
    reader: str
    timed: bool = False


# The commands every project gets.
COMMANDS = (
    Command("adopt --dry-run", ("adopt", "{p}", "--dry-run"), frozenset({0, 1}), "adopt"),
    Command("adopt --check", ("adopt", "{p}", "--check"), frozenset(range(101)), "adopt"),
    Command(
        "instructions check",
        ("instructions", "check", "{p}", "--json"),
        frozenset({0, 1, 2}),
        "instructions",
    ),
)
FLOOR = ".outcomebound/floor.json"
TICKETS = ".outcomebound/tickets.json"
# The export `outcomebound tickets export` writes: `issues.json` in the checkout it runs in.
EXPORT = "issues.json"
# The exit `instructions check` and `tickets check` give for each result of their report.
RESULTS = {"PASS": 0, "FAIL": 1, "UNVERIFIED": 2}
VERDICTS = frozenset(RESULTS)
# A word a report line may show as it is; any other word (a path, a number, quoted text) is
# shown as `<...>`, so no project's path or name reaches the report.
PLAIN = re.compile(r"[A-Za-z][A-Za-z-]*[:,;]?")
# A ticket message's code, which the engine names, never the project.
CODE = re.compile(r"[A-Z][A-Z0-9_]*")
# A floor claim's line, and the claim names the engine's own recipes give; a project's own
# claim name is shown as `<...>`.
CLAIM = re.compile(r"(PASS|FAIL|UNVERIFIED) (\S+) \(")
RECIPE = re.compile(r"(?:python|shell|typescript)\.[a-z]+|secrets|loosening")
# A refusal's line on stderr: the floor's, and a ticket verb's named code.
REFUSAL = {"floor": re.compile(r"floor: "), "tickets": re.compile(r"[A-Z][A-Z_]+: ")}
GROUPED = frozenset({"warning", "UNVERIFIED"})
ERRNO = re.compile(r"\[Errno (\d+)\]")
# The last line of a traceback: an exception's name, which is shown; its message is not.
EXCEPTION = re.compile(r"((?:\w+\.)*\w*(?:Error|Exception|Interrupt|Exit|Warning))(?::|$)")
# The tools a floor claim runs that keep a cache in the tree they read, and the variable that
# moves each; the canary moves both out of every project.
CACHES = ("RUFF_CACHE_DIR", "MYPY_CACHE_DIR")


class Unverified(Exception):
    """A run that cannot start: no list, no installed release, no interpreter."""


@dataclass
class Outcome:
    """What one command printed, read without its paths."""

    exit: int
    crash: str | None = None
    exception: str | None = None
    refusals: int = 0
    unreported: str | None = None
    verdict: str = ""
    kinds: Counter[str] = field(default_factory=Counter)
    seconds: float = 0.0

    def failed(self) -> str | None:
        if self.crash:
            return f"crash: {self.crash}"
        if self.exception:
            return f"exception: {self.exception}"
        if self.refusals:
            return f"refusal: {self.refusals} reason(s)"
        if self.unreported:
            return f"no report: {self.unreported}"
        return None


def _word(token: str) -> str:
    return token if PLAIN.fullmatch(token) else "<...>"


def _kind(line: str) -> str | None:
    tokens = line.split()
    if not tokens:
        return None
    first = _word(tokens[0])
    if first in GROUPED:
        return " ".join([first, *(_word(token) for token in tokens[1:5])])
    return first


def _crash(exit: int, out: str, err: str, documented: frozenset[int]) -> str | None:
    if "Traceback (most recent call last)" in err + out:
        names = [found.group(1) for line in err.splitlines() if (found := EXCEPTION.match(line))]
        return f"traceback, {names[-1] if names else 'an exception'}"
    if exit < 0:
        return f"signal {-exit}"
    if exit not in documented:
        return f"exit {exit}, not a documented verdict"
    return None


def read(command: Command, exit: int, out: str, err: str) -> Outcome:
    """One command's outcome, from its exit and what it printed."""

    outcome = Outcome(exit, crash=_crash(exit, out, err, command.exits))
    if outcome.crash:
        return outcome
    if command.reader == "adopt":
        reasons = [line for line in err.splitlines() if line.startswith("adopt: ")]
        errnos = sorted({found.group(1) for line in reasons for found in ERRNO.finditer(line)})
        if errnos:
            outcome.exception = "OSError " + ", ".join(f"[Errno {n}]" for n in errnos)
        outcome.refusals = 0 if errnos else len(reasons)
        outcome.verdict = f"exit {exit}"
        outcome.kinds = Counter(kind for line in out.splitlines() if (kind := _kind(line)))
        return outcome
    if command.reader == "floor":
        kinds, problem = _floor(exit, out)
    elif command.reader == "tickets":
        kinds, problem = _tickets(exit, out)
    else:
        kinds, problem = _instructions(exit, out)
    if kinds is None:
        refusal = REFUSAL.get(command.reader)
        outcome.refusals = (
            sum(1 for line in err.splitlines() if refusal.match(line)) if refusal else 0
        )
        outcome.unreported = None if outcome.refusals else problem
        outcome.verdict = f"exit {exit}, no valid report"
        return outcome
    outcome.verdict = next(name for name, code in RESULTS.items() if code == exit)
    outcome.kinds = kinds
    return outcome


def _json_report(exit: int, out: str) -> tuple[dict | None, str]:
    """A `--json` report whose result is PASS, FAIL or UNVERIFIED and agrees with its exit."""

    try:
        report = json.loads(out)
    except ValueError:
        return None, f"exit {exit}, no JSON report"
    if not isinstance(report, dict):
        return None, "the JSON report is not an object"
    result = report.get("result")
    if result not in VERDICTS:
        return None, "the report has no result PASS, FAIL or UNVERIFIED"
    if RESULTS[result] != exit:
        return None, f"the report's result {result} disagrees with exit {exit}"
    return report, ""


def _instructions(exit: int, out: str) -> tuple[Counter[str] | None, str]:
    """The kinds of an `instructions check --json` report: each finding that is not PASS."""

    report, problem = _json_report(exit, out)
    if report is None:
        return None, problem
    findings = report.get("findings")
    if not isinstance(findings, list):
        return None, "the report has no list of findings"
    for item in findings:
        if not (
            isinstance(item, dict)
            and isinstance(item.get("check"), str)
            and item.get("verdict") in VERDICTS
        ):
            return None, "a finding has no check or no verdict PASS, FAIL or UNVERIFIED"
    kinds = Counter(
        f"{_word(item['check'])} {_word(item['verdict'])}"
        for item in findings
        if item["verdict"] != "PASS"
    )
    return kinds, ""


def _tickets(exit: int, out: str) -> tuple[Counter[str] | None, str]:
    """The kinds of a `tickets check --json` report: each message, by its level and its code."""

    report, problem = _json_report(exit, out)
    if report is None:
        return None, problem
    tickets = report.get("tickets")
    if not isinstance(tickets, list) or not all(isinstance(t, dict) for t in tickets):
        return None, "the report has no list of tickets"
    messages = [report.get("messages"), *(ticket.get("messages") for ticket in tickets)]
    if not all(isinstance(group, list) for group in messages):
        return None, "the report or a ticket has no list of messages"
    kinds: Counter[str] = Counter()
    for item in (item for group in messages for item in group):
        level = item.get("level") if isinstance(item, dict) else None
        code = item.get("code") if isinstance(item, dict) else None
        if not (isinstance(level, str) and isinstance(code, str)):
            return None, "a message has no level or no code"
        shown = [token if CODE.fullmatch(token) else "<...>" for token in (level, code)]
        kinds[" ".join(shown)] += 1
    return kinds, ""


def _floor(exit: int, out: str) -> tuple[Counter[str] | None, str]:
    """The kinds of a `floor check` report: each claim's line, by its name and its result.
    Exit 0 is every claim PASS, and exit 1 at least one claim that is not."""

    claims = [found.groups() for line in out.splitlines() if (found := CLAIM.match(line))]
    if exit == 2:
        return None, "exit 2, the floor could not run"
    if exit == 0 and any(status != "PASS" for status, _ in claims):
        return None, "exit 0, but a claim did not pass"
    if exit == 1 and all(status == "PASS" for status, _ in claims):
        return None, "exit 1, but no claim failed or read UNVERIFIED"
    kinds = Counter(
        f"{name if RECIPE.fullmatch(name) else '<...>'} {status}" for status, name in claims
    )
    return kinds, ""


def _finding(command: Command, kind: str) -> bool:
    """Whether a kind is a finding, counted when the candidate adds or removes it."""

    if command.reader == "adopt":
        return kind.split()[0] in GROUPED
    if command.reader == "floor":
        return not kind.endswith(" PASS")
    return True


def _drafts(root: Path) -> tuple[list[list[Path]], str]:
    """The draft sets the project names: each `tickets check --draft` command of the claims plan
    its tickets declaration names, its files read from the plan's cwd. None, and why, where the
    project names none; the tree is never searched for drafts."""

    try:
        declaration = json.loads((root / TICKETS).read_text(encoding="utf-8"))
        named = declaration["claims"]
        plan_path = (root / named).resolve()
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        claims = plan["claims"]
        cwd = (plan_path.parent / plan.get("cwd", ".")).resolve()
    except (OSError, ValueError, KeyError, TypeError):
        return [], "the tickets declaration or its claims plan cannot be read"
    sets: list[list[Path]] = []
    for claim in claims if isinstance(claims, list) else []:
        argv = claim.get("command") if isinstance(claim, dict) else None
        if not (isinstance(argv, list) and all(isinstance(a, str) for a in argv)):
            continue
        if "tickets" not in argv or "--draft" not in argv:
            continue
        after = argv[argv.index("--draft") + 1 :]
        tokens = after[: next((i for i, a in enumerate(after) if a.startswith("-")), len(after))]
        files: list[Path] = []
        for token in tokens:
            try:
                pattern = any(c in token for c in "*?[")
                found = sorted(cwd.glob(token)) if pattern else [cwd / token]
            except (ValueError, NotImplementedError):
                # An absolute pattern, which glob does not take; the plan's cwd reads none.
                continue
            files.extend(
                path.resolve()
                for path in found
                if path.is_file() and path.resolve().is_relative_to(root.resolve())
            )
        if files and files not in sets:
            sets.append(files)
    if not sets:
        return [], "the claims plan names no `tickets check --draft` files that exist"
    return sets, ""


def plan(root: Path) -> tuple[list[Command], list[str]]:
    """The commands both engines run on one project, and a line for each one not run, with
    why."""

    commands, skipped = list(COMMANDS), []
    if (root / FLOOR).is_file():
        commands.append(
            Command(
                "floor check",
                ("floor", "check", "{p}", "--base", "HEAD"),
                frozenset({0, 1, 2}),
                "floor",
                timed=True,
            )
        )
    else:
        skipped.append(f"floor check: not run, the project has no {FLOOR}")
    if not (root / TICKETS).is_file():
        skipped.append(f"tickets check: not run, the project has no {TICKETS}")
        return commands, skipped
    sets, why = _drafts(root)
    for number, files in enumerate(sets, start=1):
        commands.append(
            Command(
                f"tickets check --draft (set {number}, {len(files)} file(s))",
                ("tickets", "check", "{p}", "--json", "--draft", *map(str, files)),
                frozenset({0, 1, 2}),
                "tickets",
            )
        )
    if why:
        skipped.append(f"tickets check --draft: not run, {why}")
    if (root / EXPORT).is_file() and os.access(root / EXPORT, os.R_OK):
        commands.append(
            Command(
                "tickets check --input",
                ("tickets", "check", "{p}", "--json", "--input", str(root / EXPORT)),
                frozenset({0, 1, 2}),
                "tickets",
            )
        )
    else:
        skipped.append(
            f"tickets check --input: UNVERIFIED, no readable {EXPORT} in the project root, "
            "and the canary calls no tracker"
        )
    return commands, skipped


def load_list(path: Path) -> list[Path]:
    """The projects a list names, in order; a relative path is read from the list's folder."""

    projects = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#"):
            named = Path(line).expanduser()
            projects.append(named if named.is_absolute() else path.parent / named)
    return projects


def _git_bytes(project: Path, *arguments: str) -> bytes | None:
    done = subprocess.run(
        ["git", "-C", str(project), *arguments],
        capture_output=True,
        stdin=subprocess.DEVNULL,
        check=False,
    )
    return done.stdout if done.returncode == 0 else None


def _status(project: Path) -> tuple[bytes, bytes] | None:
    """What a run must leave as it was: `git status`, each untracked file named one by one, and
    the ignored entries, a folder Git ignores named once, so a cache folder a tool makes and
    ignores itself (ruff's) is seen too."""

    status = _git_bytes(project, "status", "--porcelain", "-z", "--untracked-files=all")
    ignored = _git_bytes(
        project, "ls-files", "-z", "--others", "--ignored", "--exclude-standard", "--directory"
    )
    return None if status is None or ignored is None else (status, ignored)


@dataclass
class Engine:
    """One side of the comparison: how to start it, and its label in the report."""

    label: str
    argv: list[str]
    env: dict[str, str]

    def run(self, project: Path, commands: list[Command]) -> dict[str, Outcome]:
        outcomes = {}
        # The floor's tools write their caches here, never into the project.
        with tempfile.TemporaryDirectory(prefix="outcomebound-canary-") as scratch:
            env = {**self.env, **{name: str(Path(scratch) / name) for name in CACHES}}
            for command in commands:
                argv = [*self.argv, *(a.replace("{p}", str(project)) for a in command.arguments)]
                started = time.monotonic()
                done = subprocess.run(
                    argv,
                    cwd=project,
                    env=env,
                    capture_output=True,
                    text=True,
                    errors="replace",
                    stdin=subprocess.DEVNULL,
                    check=False,
                )
                outcome = read(command, done.returncode, done.stdout, done.stderr)
                outcome.seconds = time.monotonic() - started
                outcomes[command.label] = outcome
        return outcomes


@dataclass
class Result:
    """One project's lines, each with the candidates that print it, and what failed it."""

    number: int
    lines: dict[tuple[str, str], list[str]] = field(default_factory=dict)
    failures: Counter[str] = field(default_factory=Counter)
    added: set[str] = field(default_factory=set)
    removed: set[str] = field(default_factory=set)
    not_run: int = 0
    changes: int = 0

    def add(self, text: str, command: str = "", under: str = "", change: bool = True) -> None:
        self.changes += change
        self.lines.setdefault((command, text), []).extend([under] if under else [])

    def shown(self) -> list[str]:
        return [
            f"{command}, under {' and '.join(under)}: {text}" if command else text
            for (command, text), under in self.lines.items()
        ]


def _compare(result: Result, command: Command, before: Outcome, after: Outcome, under: str) -> None:
    label = command.label
    if command.timed:
        shown = f"{after.verdict or 'no verdict'}, {after.seconds:.1f} s (installed: "
        shown += f"{before.verdict or 'no verdict'}, {before.seconds:.1f} s)"
        result.add(shown, label, under, change=False)
    failed = after.failed()
    if failed:
        known = before.failed()
        installed = f" (installed: {known})" if known else ""
        result.add(f"{failed}{installed}", label, under)
        result.failures[failed.split(":")[0]] += 1
        return
    if before.failed():
        result.add(
            f"no baseline: installed engine failed ({before.failed()}); the candidate's "
            f"verdict {after.verdict} was not compared",
            label,
            under,
        )
        return
    if before.verdict != after.verdict:
        result.add(f"verdict {before.verdict} -> {after.verdict}", label, under)
    for kind in sorted(set(before.kinds) | set(after.kinds)):
        old, new = before.kinds[kind], after.kinds[kind]
        if old != new:
            result.add(f"{kind!r} {old} -> {new}", label, under)
        if _finding(command, kind) and old == 0 and new:
            result.added.add(f"{label} {kind}")
        if _finding(command, kind) and new == 0 and old:
            result.removed.add(f"{label} {kind}")


def _changed(result: Result, project: Path, before: tuple[bytes, bytes], during: str) -> bool:
    """Whether the project's tree changed since `before`; a FAIL line where it did."""

    after = _status(project)
    if after == before:
        return False
    what = "git status" if after is None or after[0] != before[0] else "the ignored entries"
    result.add(f"the project's tree changed during {during} ({what} changed)")
    result.failures["changed tree"] += 1
    return True


def canary(number: int, project: Path, installed: Engine, candidates: list[Engine]) -> Result:
    """One project: the installed release, then each candidate, the tree read after each."""

    result = Result(number)
    before = _status(project) if project.is_dir() else None
    if before is None:
        result.add("not a Git work tree that this user can read")
        result.failures["unreadable project"] += 1
        return result
    commands, skipped = plan(project)
    result.add("ran: " + ", ".join(command.label for command in commands), change=False)
    for line in skipped:
        result.add(line, change=False)
    result.not_run = len(skipped)
    baseline = installed.run(project, commands)
    if _changed(result, project, before, "the installed release's run"):
        return result
    for candidate in candidates:
        outcomes = candidate.run(project, commands)
        for command in commands:
            _compare(
                result, command, baseline[command.label], outcomes[command.label], candidate.label
            )
        if _changed(result, project, before, f"the run under {candidate.label}"):
            return result
    return result


def _git(root: Path, *arguments: str) -> str | None:
    done = subprocess.run(
        ["git", "-C", str(root), *arguments], capture_output=True, text=True, check=False
    )
    return done.stdout.strip() if done.returncode == 0 else None


def tree(root: Path) -> str | None:
    """HEAD's tree, which a squash merge of HEAD keeps."""

    return _git(root, "rev-parse", "HEAD^{tree}")


def records(root: Path) -> Path | None:
    common = _git(root, "rev-parse", "--path-format=absolute", "--git-common-dir")
    return Path(common) / RECORDS if common else None


def write_record(root: Path, folder: Path | None, verdict: str, summary: dict) -> str:
    """Record the verdict for HEAD's tree; what the report says of it."""

    key = tree(root)
    if key is None or folder is None:
        return "record: none written, this checkout is not a Git work tree"
    if _git(root, "status", "--porcelain"):
        return "record: none written, the checkout holds changes not committed"
    folder.mkdir(parents=True, exist_ok=True)
    when = datetime.now(timezone.utc).isoformat(timespec="seconds")
    record = {"tree": key, "verdict": verdict, "recorded": when, **summary}
    (folder / f"{key}.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return f"record: {verdict} for tree {key[:12]}"


def verify(root: Path, folder: Path | None) -> int:
    """PASS where a PASS record exists for HEAD's tree."""

    key = tree(root)
    path = folder / f"{key}.json" if key and folder else None
    try:
        verdict = json.loads(path.read_text(encoding="utf-8"))["verdict"] if path else None
    except (OSError, ValueError, KeyError, TypeError):
        verdict = None
    if verdict == "PASS":
        print(f"PASS {NAME}: a PASS record for tree {key[:12] if key else ''}")
        return 0
    found = f"a {verdict} record" if verdict else "no record"
    print(
        f"FAIL {NAME}: {found} for this tree ({key[:12] if key else 'no HEAD'}); run "
        f"`make canary` with {LIST_ENV} set, on this commit, with no change left uncommitted"
    )
    return 1


def _version(python: str) -> str:
    done = subprocess.run(
        [python, "-I", "-c", "import sys; print('%d.%d.%d' % sys.version_info[:3])"],
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        check=False,
    )
    return done.stdout.strip() if done.returncode == 0 and done.stdout.strip() else "unknown"


def _installed_path() -> str:
    """`outcomebound` on PATH, less any PATH entry that holds this checkout's launcher."""

    own = (ROOT / "scripts").resolve()
    entries = os.environ.get("PATH", "").split(os.pathsep)
    kept = [entry for entry in entries if entry and Path(entry).resolve() != own]
    found = shutil.which("outcomebound", path=os.pathsep.join(kept))
    if not found:
        raise Unverified("no installed outcomebound on PATH")
    return found


def _installed_python(command: str) -> str:
    """The interpreter the installed launcher runs: the one beside it, or for a checkout's
    launcher, python3 on PATH."""

    here = Path(command).resolve().parent
    for name in ("python", "python3"):
        if os.access(here / name, os.X_OK):
            return str(here / name)
    if (here.parent / "outcomebound_tools").is_dir() and shutil.which("python3"):
        return str(shutil.which("python3"))
    raise Unverified("the installed outcomebound's interpreter was not found beside it")


def _oldest() -> str:
    if shutil.which("uv"):
        done = subprocess.run(
            ["uv", "python", "find", OLDEST], capture_output=True, text=True, check=False
        )
        if done.returncode == 0 and done.stdout.strip():
            return done.stdout.strip()
    found = shutil.which(f"python{OLDEST}")
    if not found:
        raise Unverified(f"no Python {OLDEST} (uv python find {OLDEST}, or python{OLDEST})")
    return found


def engines(installed: str, pythons: list[str]) -> tuple[Engine, list[Engine]]:
    env = {k: v for k, v in os.environ.items() if k != "OUTCOMEBOUND_HOME"}
    own = (ROOT / "scripts").resolve()
    path = [e for e in env.get("PATH", "").split(os.pathsep) if e and Path(e).resolve() != own]
    env["PATH"] = os.pathsep.join(path)
    chosen = pythons or [_oldest(), _installed_python(installed)]
    unique = list(dict.fromkeys(str(Path(p).resolve()) for p in chosen))
    candidate_env = {**env, "OUTCOMEBOUND_HOME": str(ROOT)}
    candidates = [
        Engine(f"python {_version(p)}", [p, "-I", "-c", RUNPY, str(ROOT)], candidate_env)
        for p in unique
    ]
    return Engine("installed", [installed], env), candidates


def _release(installed: Engine) -> str:
    done = subprocess.run(
        [*installed.argv, "home"], capture_output=True, text=True, env=installed.env, check=False
    )
    try:
        return (Path(done.stdout.strip()) / "VERSION").read_text(encoding="utf-8").strip()
    except OSError:
        return "unknown"


def report(results: list[Result], header: str) -> tuple[str, dict, str]:
    """Print each project's lines; the verdict, the record's summary and the verdict's line."""

    print(header)
    for result in results:
        print(f"project {result.number}: " + ("FAIL" if result.failures else "PASS"))
        for line in result.shown():
            print(f"  {line}")
        if not result.changes:
            print("  no change")
    failures: Counter[str] = sum((r.failures for r in results), Counter())
    failed = sum(1 for r in results if r.failures)
    added = sum(len(r.added) for r in results)
    removed = sum(len(r.removed) for r in results)
    not_run = sum(r.not_run for r in results)
    verdict = "FAIL" if failed else "PASS"
    counts = ", ".join(f"{kind}: {n}" for kind, n in sorted(failures.items())) or "no failure"
    summary = {
        "projects": len(results),
        "failed": failed,
        "failures": dict(failures),
        "finding kinds added": added,
        "finding kinds removed": removed,
        "commands not run": not_run,
    }
    line = (
        f"{verdict} {NAME}: {failed} of {len(results)} project(s) failed ({counts}); "
        f"warning or finding kinds: {added} added, {removed} removed, for a person to judge; "
        f"{not_run} command(s) not run, each named with why"
    )
    return verdict, summary, line


def run(args: argparse.Namespace) -> int:
    named = os.environ.get(LIST_ENV, "").strip()
    if not named:
        raise Unverified(f"no project list ({LIST_ENV})")
    try:
        projects = load_list(Path(named).expanduser())
    except OSError as error:
        raise Unverified(
            f"the project list in {LIST_ENV} cannot be read ({error.strerror})"
        ) from None
    if not projects:
        raise Unverified(f"the project list in {LIST_ENV} names no project")
    installed, candidates = engines(args.installed or _installed_path(), args.python)
    header = (
        f"{NAME}: candidate {(ROOT / 'VERSION').read_text(encoding='utf-8').strip()} under "
        + ", ".join(c.label for c in candidates)
        + f", beside installed {_release(installed)}, on {len(projects)} project(s)"
    )
    with ThreadPoolExecutor(max_workers=min(len(projects), os.cpu_count() or 1)) as pool:
        results = list(
            pool.map(
                lambda item: canary(item[0], item[1], installed, candidates),
                enumerate(projects, start=1),
            )
        )
    verdict, summary, line = report(results, header)
    folder = Path(args.records) if args.records else records(ROOT)
    print(write_record(ROOT, folder, verdict, summary))
    print(line)
    return 0 if verdict == "PASS" else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run this checkout's engine beside the installed release on each "
        f"project of the local list that {LIST_ENV} names, and record the verdict for HEAD's "
        "tree. Inspect custom floor commands; use owned isolated checkouts where they may write. "
        "Exit 0: PASS; 1: FAIL; 2: UNVERIFIED (no list, no installed release or no "
        "interpreter)."
    )
    parser.add_argument(
        "--verify", action="store_true", help="read the record for HEAD's tree; run nothing"
    )
    parser.add_argument(
        "--installed", help="the installed release's command (default: outcomebound on PATH)"
    )
    parser.add_argument(
        "--python",
        action="append",
        default=[],
        help=f"an interpreter for the candidate, repeatable (default: Python {OLDEST} and the "
        "installed release's)",
    )
    parser.add_argument(
        "--records", help=f"the record folder (default: {RECORDS}/ in the Git common directory)"
    )
    args = parser.parse_args(argv)
    if args.verify:
        return verify(ROOT, Path(args.records) if args.records else records(ROOT))
    try:
        return run(args)
    except Unverified as error:
        print(f"UNVERIFIED {NAME}: {error}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
