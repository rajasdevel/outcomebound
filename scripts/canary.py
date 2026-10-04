#!/usr/bin/env python3
"""The release canary: this checkout's engine beside the installed release, read-only, on the
projects of a local list.

The list is the file that `OB_CANARY_LIST` names: one project path a line, `#` for a comment, a
relative path read from the list's folder. The list is private, so it stays outside this
repository, and nothing printed or recorded names a project's path: a project is named by its
number in the list.

For each project, the installed release (`outcomebound` on PATH, less this checkout's launcher)
and the candidate (this checkout) each run `adopt <p> --dry-run`, `adopt <p> --check` and
`instructions check <p> --json`. The candidate runs under each `--python`; by default the oldest
supported Python (3.10, from `uv python find 3.10` or `python3.10` on PATH) and the Python the
installed release runs under, since a Python version can change what the standard library
raises. Nothing is written into a project: `git status --porcelain` is read before and after.

The report names, per project and per run, a crash (a traceback, a signal, or an exit that is
not the command's documented verdict), an exception adopt reports (`adopt: [Errno N] ...`), a
refusal (another `adopt:` reason), a changed verdict or exit code, and the report lines added
or removed by kind: a `warning` or `UNVERIFIED` line by its first four words, each word that is
not a plain word shown as `<...>`, and any other line by its first word. The verdict is the last
line. A crash, an exception or a refusal of the candidate, a project tree that changed, or a
project that is not a Git work tree is FAIL; anything else is PASS, and the kinds added and
removed are printed for a person to judge.

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
# Each command: its label, its arguments around the project, and the exits it documents.
COMMANDS = (
    ("adopt --dry-run", ("adopt", "{p}", "--dry-run"), frozenset({0, 1})),
    ("adopt --check", ("adopt", "{p}", "--check"), frozenset(range(101))),
    ("instructions check", ("instructions", "check", "{p}", "--json"), frozenset({0, 1, 2})),
)
# A word a report line may show as it is; any other word (a path, a number, quoted text) is
# shown as `<...>`, so no project's path or name reaches the report.
PLAIN = re.compile(r"[A-Za-z][A-Za-z-]*[:,;]?")
GROUPED = frozenset({"warning", "UNVERIFIED"})
ERRNO = re.compile(r"\[Errno (\d+)\]")
# The last line of a traceback: an exception's name, which is shown; its message is not.
EXCEPTION = re.compile(r"((?:\w+\.)*\w*(?:Error|Exception|Interrupt|Exit|Warning))(?::|$)")


class Unverified(Exception):
    """A run that cannot start: no list, no installed release, no interpreter."""


@dataclass
class Outcome:
    """What one command printed, read without its paths."""

    exit: int
    crash: str | None = None
    exception: str | None = None
    refusals: int = 0
    verdict: str = ""
    kinds: Counter[str] = field(default_factory=Counter)

    def failed(self) -> str | None:
        if self.crash:
            return f"crash: {self.crash}"
        if self.exception:
            return f"exception: {self.exception}"
        if self.refusals:
            return f"refusal: {self.refusals} reason(s)"
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


def read(label: str, exit: int, out: str, err: str) -> Outcome:
    """One command's outcome, from its exit and what it printed."""

    documented = next(codes for name, _, codes in COMMANDS if name == label)
    outcome = Outcome(exit, crash=_crash(exit, out, err, documented))
    if outcome.crash:
        return outcome
    if label.startswith("adopt"):
        reasons = [line for line in err.splitlines() if line.startswith("adopt: ")]
        errnos = sorted({found.group(1) for line in reasons for found in ERRNO.finditer(line)})
        if errnos:
            outcome.exception = "OSError " + ", ".join(f"[Errno {n}]" for n in errnos)
        outcome.refusals = 0 if errnos else len(reasons)
        outcome.verdict = f"exit {exit}"
        outcome.kinds = Counter(kind for line in out.splitlines() if (kind := _kind(line)))
        return outcome
    try:
        report = json.loads(out)
        findings = list(report["findings"])
        outcome.verdict = str(report["result"])
    except (ValueError, KeyError, TypeError):
        outcome.verdict = f"exit {exit}, no JSON report"
        return outcome
    outcome.kinds = Counter(
        f"{_word(str(item.get('check')))} {_word(str(item.get('verdict')))}"
        for item in findings
        if isinstance(item, dict) and item.get("verdict") != "PASS"
    )
    return outcome


def load_list(path: Path) -> list[Path]:
    """The projects a list names, in order; a relative path is read from the list's folder."""

    projects = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#"):
            named = Path(line).expanduser()
            projects.append(named if named.is_absolute() else path.parent / named)
    return projects


def _status(project: Path) -> bytes | None:
    done = subprocess.run(
        ["git", "-C", str(project), "status", "--porcelain", "-z"],
        capture_output=True,
        stdin=subprocess.DEVNULL,
        check=False,
    )
    return done.stdout if done.returncode == 0 else None


@dataclass
class Engine:
    """One side of the comparison: how to start it, and its label in the report."""

    label: str
    argv: list[str]
    env: dict[str, str]

    def run(self, project: Path) -> dict[str, Outcome]:
        outcomes = {}
        for label, arguments, _ in COMMANDS:
            argv = [*self.argv, *(a.replace("{p}", str(project)) for a in arguments)]
            done = subprocess.run(
                argv,
                cwd=project,
                env=self.env,
                capture_output=True,
                text=True,
                errors="replace",
                stdin=subprocess.DEVNULL,
                check=False,
            )
            outcomes[label] = read(label, done.returncode, done.stdout, done.stderr)
        return outcomes


@dataclass
class Result:
    """One project's lines, each with the candidates that print it, and what failed it."""

    number: int
    lines: dict[tuple[str, str], list[str]] = field(default_factory=dict)
    failures: Counter[str] = field(default_factory=Counter)
    added: set[str] = field(default_factory=set)
    removed: set[str] = field(default_factory=set)

    def add(self, text: str, command: str = "", under: str = "") -> None:
        self.lines.setdefault((command, text), []).extend([under] if under else [])

    def shown(self) -> list[str]:
        return [
            f"{command}, under {' and '.join(under)}: {text}" if command else text
            for (command, text), under in self.lines.items()
        ]


def _compare(result: Result, command: str, before: Outcome, after: Outcome, under: str) -> None:
    failed = after.failed()
    if failed:
        known = before.failed()
        installed = f" (installed: {known})" if known else ""
        result.add(f"{failed}{installed}", command, under)
        result.failures[failed.split(":")[0]] += 1
        return
    if before.failed():
        result.add(f"installed: {before.failed()}; candidate: none", command, under)
    if before.verdict != after.verdict:
        result.add(f"verdict {before.verdict} -> {after.verdict}", command, under)
    for kind in sorted(set(before.kinds) | set(after.kinds)):
        old, new = before.kinds[kind], after.kinds[kind]
        if old != new:
            result.add(f"{kind!r} {old} -> {new}", command, under)
        finding = command.startswith("instructions") or kind.split()[0] in GROUPED
        if finding and old == 0 and new:
            result.added.add(f"{command} {kind}")
        if finding and new == 0 and old:
            result.removed.add(f"{command} {kind}")


def canary(number: int, project: Path, installed: Engine, candidates: list[Engine]) -> Result:
    """One project: the installed release, then each candidate, then the tree once more."""

    result = Result(number)
    before = _status(project) if project.is_dir() else None
    if before is None:
        result.add("not a Git work tree that this user can read")
        result.failures["unreadable project"] += 1
        return result
    baseline = installed.run(project)
    for candidate in candidates:
        for command, outcome in candidate.run(project).items():
            _compare(result, command, baseline[command], outcome, candidate.label)
    if _status(project) != before:
        result.add("the project's tree changed during the run (git status differs)")
        result.failures["changed tree"] += 1
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
        print("\n".join(f"  {line}" for line in result.shown()) or "  no change")
    failures: Counter[str] = sum((r.failures for r in results), Counter())
    failed = sum(1 for r in results if r.failures)
    added = sum(len(r.added) for r in results)
    removed = sum(len(r.removed) for r in results)
    verdict = "FAIL" if failed else "PASS"
    counts = ", ".join(f"{kind}: {n}" for kind, n in sorted(failures.items())) or "no failure"
    summary = {
        "projects": len(results),
        "failed": failed,
        "failures": dict(failures),
        "finding kinds added": added,
        "finding kinds removed": removed,
    }
    line = (
        f"{verdict} {NAME}: {failed} of {len(results)} project(s) failed ({counts}); "
        f"warning or finding kinds: {added} added, {removed} removed, for a person to judge"
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
        description="Run this checkout's engine beside the installed release, read-only, on each "
        f"project of the local list that {LIST_ENV} names, and record the verdict for HEAD's "
        "tree. Exit 0: PASS; 1: FAIL; 2: UNVERIFIED (no list, no installed release or no "
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
