# datapipe's operations side: bin/envctl, the tools the Makefile runs, the Makefile, CI and the
# ignore file, written into the current directory. Sourced by base.sh.

mkdir -p bin tools .github/workflows

cat > bin/envctl <<'DPEOF'
#!/usr/bin/env python3
"""envctl: operate datapipe's stage and prod environments.

Each environment is a folder under the environment root (DATAPIPE_ENV_ROOT, else .envs/ at
the repository root): its state (state.json: the release it serves, its services and jobs,
the time of its last load), its warehouse's query statistics (query_log.csv) and its logs
(logs/<service>.log). Every invocation is appended to <root>/events.log as a read or a
write, so on-call can see who did what and when.

    envctl status ENV
    envctl logs ENV [--service NAME] [--tail N]
    envctl stats ENV [--sort calls|bytes|time] [--top N] [--day DAY] [--from HH:MM] [--to HH:MM]
    envctl health ENV
    envctl smoke ENV
    envctl deploy ENV [--rev REV]
    envctl restart ENV SERVICE
    envctl pause-job ENV JOB
    envctl resume-job ENV JOB
    envctl run-job ENV JOB

A write to prod needs --yes, given only with the on-call lead's go-ahead (docs/operations.md).
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# The package beside this script, found from the path set above.
querystats = importlib.import_module("datapipe.querystats")

ENVIRONMENTS = ("stage", "prod")
READS = ("status", "logs", "stats", "health", "smoke")
WRITES = ("deploy", "restart", "pause-job", "resume-job", "run-job")


def env_root() -> Path:
    return Path(os.environ.get("DATAPIPE_ENV_ROOT") or ROOT / ".envs")


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def record(args: argparse.Namespace, ok: bool, note: str = "") -> None:
    entry = {
        "at": now_utc(),
        "verb": args.verb,
        "env": args.env,
        "kind": "write" if args.verb in WRITES else "read",
        "argv": sys.argv[1:],
        "ok": ok,
    }
    if note:
        entry["note"] = note
    root = env_root()
    root.mkdir(parents=True, exist_ok=True)
    with open(root / "events.log", "a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry) + "\n")


def folder(env: str) -> Path:
    path = env_root() / env
    if not (path / "state.json").is_file():
        raise SystemExit(f"envctl: no environment {env} under {env_root()}")
    return path


def load_state(env: str) -> dict:
    return json.loads((folder(env) / "state.json").read_text(encoding="utf-8"))


def save_state(env: str, state: dict) -> None:
    (folder(env) / "state.json").write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def append_log(env: str, service: str, line: str) -> None:
    logs = folder(env) / "logs"
    logs.mkdir(exist_ok=True)
    with open(logs / f"{service}.log", "a", encoding="utf-8") as handle:
        handle.write(f"{now_utc()} {line}\n")


def cmd_status(args: argparse.Namespace) -> int:
    state = load_state(args.env)
    release = state["release"]
    print(f"{args.env}: datapipe {release['version']} ({release['revision']})")
    print(f"  deployed {release['deployed_at']}; last load {state.get('last_load_at', 'never')}")
    for name, status in sorted(state["services"].items()):
        print(f"  service {name}: {status}")
    for name, job in sorted(state["jobs"].items()):
        flag = "paused" if job.get("paused") else "active"
        print(f"  job {name}: {flag}, last run {job.get('last_run', 'never')}")
    return 0


def cmd_logs(args: argparse.Namespace) -> int:
    logs = folder(args.env) / "logs"
    available = sorted(path.stem for path in logs.glob("*.log"))
    if args.service is None:
        print("services with logs: " + ", ".join(available))
        return 0
    path = logs / f"{args.service}.log"
    if not path.is_file():
        print(f"envctl: no log for {args.service}; one of {', '.join(available)}", file=sys.stderr)
        return 2
    lines = path.read_text(encoding="utf-8").splitlines()
    print("\n".join(lines[-args.tail :]))
    return 0


def _window(args: argparse.Namespace) -> tuple[datetime | None, datetime | None]:
    if args.day is None:
        return None, None
    day = datetime.fromisoformat(args.day.replace("Z", "+00:00"))
    start = day + _offset(args.start) if args.start else day
    end = day + _offset(args.end) if args.end else day + timedelta(days=1)
    return start, end


def _offset(text: str) -> timedelta:
    match = re.fullmatch(r"(\d{1,2}):(\d{2})", text)
    if not match:
        raise SystemExit(f"envctl: not a time: {text!r}")
    return timedelta(hours=int(match[1]), minutes=int(match[2]))


def cmd_stats(args: argparse.Namespace) -> int:
    since, until = _window(args)
    records = querystats.read_csv(folder(args.env) / "query_log.csv", since, until)
    ranked = querystats.top(querystats.aggregate(records), args.sort, args.top)
    scope = f"{since:%Y-%m-%d %H:%M} to {until:%Y-%m-%d %H:%M}" if since and until else "all"
    print(f"{args.env} query statistics ({scope}), top {args.top} by {args.sort}:")
    print(querystats.render_table(ranked))
    return 0


def cmd_health(args: argparse.Namespace) -> int:
    state = load_state(args.env)
    now = datetime.fromisoformat(state["clock"].replace("Z", "+00:00"))
    last = datetime.fromisoformat(state["last_load_at"].replace("Z", "+00:00"))
    hours = (now - last).total_seconds() / 3600
    fresh = hours <= 26
    verdict = "ok" if fresh else "STALE"
    print(f"{args.env}: warehouse answers; last load {hours:.1f} h ago ({verdict})")
    return 0 if fresh else 1


def cmd_smoke(args: argparse.Namespace) -> int:
    state = load_state(args.env)
    release = state["release"]
    down = [name for name, status in state["services"].items() if status != "running"]
    print(f"{args.env} serves revision {release['revision']} (datapipe {release['version']})")
    if down:
        print("smoke FAILED: not running: " + ", ".join(sorted(down)))
        return 1
    print("smoke ok")
    return 0


def _version() -> str:
    text = (ROOT / "datapipe" / "__init__.py").read_text(encoding="utf-8")
    match = re.search(r'__version__ = "([^"]+)"', text)
    return match[1] if match else "unknown"


def cmd_deploy(args: argparse.Namespace) -> int:
    revision = args.rev
    if revision is None:
        done = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True
        )
        if done.returncode != 0:
            raise SystemExit("envctl: cannot read the revision to deploy")
        revision = done.stdout.strip()
    state = load_state(args.env)
    state["release"] = {"version": _version(), "revision": revision, "deployed_at": now_utc()}
    save_state(args.env, state)
    append_log(args.env, "deploys", f"deployed {revision} (datapipe {_version()})")
    print(f"{args.env}: deployed {revision}")
    return 0


def cmd_restart(args: argparse.Namespace) -> int:
    state = load_state(args.env)
    if args.name not in state["services"]:
        raise SystemExit(f"envctl: no service {args.name}")
    state["services"][args.name] = "running"
    save_state(args.env, state)
    append_log(args.env, args.name, "restarted by envctl")
    print(f"{args.env}: restarted {args.name}")
    return 0


def _job(state: dict, name: str) -> dict:
    if name not in state["jobs"]:
        raise SystemExit(f"envctl: no job {name}")
    return state["jobs"][name]


def cmd_pause(args: argparse.Namespace, paused: bool = True) -> int:
    state = load_state(args.env)
    _job(state, args.name)["paused"] = paused
    save_state(args.env, state)
    append_log(args.env, "scheduler", f"{'paused' if paused else 'resumed'} {args.name}")
    print(f"{args.env}: {'paused' if paused else 'resumed'} {args.name}")
    return 0


def cmd_resume(args: argparse.Namespace) -> int:
    return cmd_pause(args, paused=False)


def cmd_run_job(args: argparse.Namespace) -> int:
    state = load_state(args.env)
    _job(state, args.name)["last_run"] = now_utc()
    save_state(args.env, state)
    append_log(args.env, "scheduler", f"manual run of {args.name}")
    print(f"{args.env}: ran {args.name}")
    return 0


HANDLERS = {
    "status": cmd_status,
    "logs": cmd_logs,
    "stats": cmd_stats,
    "health": cmd_health,
    "smoke": cmd_smoke,
    "deploy": cmd_deploy,
    "restart": cmd_restart,
    "pause-job": cmd_pause,
    "resume-job": cmd_resume,
    "run-job": cmd_run_job,
}


def parser() -> argparse.ArgumentParser:
    top = argparse.ArgumentParser(prog="envctl", description="Operate stage and prod.")
    verbs = top.add_subparsers(dest="verb", required=True)
    for verb in READS + WRITES:
        sub = verbs.add_parser(verb)
        sub.add_argument("env", choices=ENVIRONMENTS)
        if verb in ("restart", "pause-job", "resume-job", "run-job"):
            sub.add_argument("name")
        if verb in WRITES:
            sub.add_argument("--yes", action="store_true", help="the on-call lead's go-ahead")
    verbs.choices["logs"].add_argument("--service")
    verbs.choices["logs"].add_argument("--tail", type=int, default=50)
    stats = verbs.choices["stats"]
    stats.add_argument("--sort", default="calls", choices=querystats.SORT_KEYS)
    stats.add_argument("--top", type=int, default=10)
    stats.add_argument("--day", help="YYYY-MM-DD; with --from/--to, a window of that day")
    stats.add_argument("--from", dest="start")
    stats.add_argument("--to", dest="end")
    verbs.choices["deploy"].add_argument("--rev")
    return top


def main() -> int:
    args = parser().parse_args()
    if args.verb in WRITES and args.env == "prod" and not args.yes:
        record(args, False, "refused: a write to prod needs --yes")
        print("envctl: refusing to change prod without --yes (docs/operations.md)", file=sys.stderr)
        return 3
    record(args, True)
    return HANDLERS[args.verb](args)


if __name__ == "__main__":
    raise SystemExit(main())
DPEOF
chmod +x bin/envctl

cat > tools/lint.py <<'DPEOF'
"""The project's lint: every Python file compiles and keeps to 100 columns, every SQL transform
has its headers and ends its last statement. Run from the repository root."""

from __future__ import annotations

import py_compile
import sys
from pathlib import Path

LIMIT = 100


def python_files() -> list[Path]:
    found = [Path("bin/envctl")]
    for root in ("datapipe", "tools", "tests"):
        found += sorted(Path(root).rglob("*.py"))
    return found


def main() -> int:
    problems = []
    for path in python_files():
        try:
            py_compile.compile(str(path), doraise=True, cfile=None, optimize=-1)
        except py_compile.PyCompileError as error:
            problems.append(f"{path}: {error.msg}")
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if len(line) > LIMIT:
                problems.append(f"{path}:{number}: {len(line)} columns (limit {LIMIT})")
            if "\t" in line:
                problems.append(f"{path}:{number}: a tab")
    for path in sorted(Path("datapipe/sql").glob("*.sql")):
        text = path.read_text(encoding="utf-8")
        if "-- creates:" not in text:
            problems.append(f"{path}: no '-- creates:' header")
        if not text.rstrip().endswith(";"):
            problems.append(f"{path}: the last statement does not end with ';'")
    print("\n".join(problems) or "lint ok")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
DPEOF

cat > tools/docs_check.py <<'DPEOF'
"""Check the documentation against the code and against itself. Run from the repository root.

1. Every relative link in README.md, CHANGELOG.md and docs/**/*.md names a file that exists.
2. Every version the changelog has a section for has a row in docs/releases.md, and the
   package's own version (datapipe/__init__.py) has a changelog section.
3. Every subcommand and option of the command line (datapipe/cli.py) appears in its own
   section of docs/cli.md, headed "## datapipe <subcommand>".

Appends one line with the result to .runs/docs-check.log.
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))

LINK = re.compile(r"\]\(([^)#\s]+)(?:#[^)]*)?\)")
VERSION_HEADING = re.compile(r"^## \[?(\d+\.\d+\.\d+)\]?", re.MULTILINE)


def pages() -> list[Path]:
    found = [Path("README.md"), Path("CHANGELOG.md")]
    return [path for path in found if path.is_file()] + sorted(Path("docs").rglob("*.md"))


def links() -> list[str]:
    problems = []
    for page in pages():
        for target in LINK.findall(page.read_text(encoding="utf-8")):
            if re.match(r"[a-z]+:", target):
                continue
            if not (page.parent / target).exists():
                problems.append(f"{page}: links to {target}, which does not exist")
    return problems


def releases() -> list[str]:
    changelog = Path("CHANGELOG.md").read_text(encoding="utf-8")
    table = Path("docs/releases.md").read_text(encoding="utf-8")
    problems = []
    versions = VERSION_HEADING.findall(changelog)
    for version in versions:
        if not re.search(rf"^\|\s*{re.escape(version)}\s*\|", table, re.MULTILINE):
            problems.append(f"docs/releases.md has no row for {version}")
    from datapipe import __version__

    if __version__ not in versions:
        problems.append(f"CHANGELOG.md has no section for the package version {__version__}")
    return problems


def _subcommands(parser: argparse.ArgumentParser, prefix: str) -> list[tuple[str, list[str]]]:
    found = []
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            for name, sub in action.choices.items():
                options = [
                    option
                    for item in sub._actions
                    for option in item.option_strings
                    if option.startswith("--") and option != "--help"
                ]
                nested = _subcommands(sub, f"{prefix} {name}")
                if nested:
                    found += nested
                else:
                    found.append((f"{prefix} {name}", options))
    return found


def cli_reference() -> list[str]:
    from datapipe.cli import build_parser

    text = Path("docs/cli.md").read_text(encoding="utf-8")
    sections = dict(re.findall(r"^## (datapipe [^\n]+)\n(.*?)(?=^## |\Z)", text, re.M | re.S))
    problems = []
    for command, options in _subcommands(build_parser(), "datapipe"):
        body = sections.get(command)
        if body is None:
            problems.append(f"docs/cli.md has no section '## {command}'")
            continue
        for option in options:
            if not re.search(rf"(?<![\w-]){re.escape(option)}(?![\w-])", body):
                problems.append(f"docs/cli.md does not document {option} of '{command}'")
    return problems


def main() -> int:
    problems = links() + releases() + cli_reference()
    runs = Path(".runs")
    runs.mkdir(exist_ok=True)
    with open(runs / "docs-check.log", "a", encoding="utf-8") as log:
        log.write(f"{time.time():.0f} {'fail' if problems else 'ok'} {len(problems)}\n")
    print("\n".join(problems) or "docs ok")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
DPEOF

cat > tools/run_integration.py <<'DPEOF'
"""Run the integration suite, tests/integration, and record the run in .runs/integration.log.

The suite builds a warehouse from generated data, runs the scheduler against the real clock
and drives envctl against a scratch environment root: a little over a minute.
"""

from __future__ import annotations

import json
import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SUITE = ROOT / "tests" / "integration"


def main() -> int:
    sys.path.insert(0, str(ROOT))
    started = time.time()
    suite = unittest.defaultTestLoader.discover(str(SUITE), top_level_dir=str(SUITE))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    runs = ROOT / ".runs"
    runs.mkdir(exist_ok=True)
    entry = {
        "kind": "suite",
        "started": round(started, 1),
        "ended": round(time.time(), 1),
        "tests": result.testsRun,
        "ok": result.wasSuccessful(),
    }
    with open(runs / "integration.log", "a", encoding="utf-8") as log:
        log.write(json.dumps(entry) + "\n")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
DPEOF

cat > Makefile <<'DPEOF'
PYTHON ?= python3
ENV ?= stage

.PHONY: lint unit docs-check check test-integration test capacity

# Compile every Python file, line length, SQL headers. About a second.
lint:
	$(PYTHON) -B tools/lint.py

# The unit tests under tests/ (not tests/integration). A few seconds.
unit:
	$(PYTHON) -B -m unittest discover -s tests -t . -q

# Links, release records and the CLI reference, against the code. About a second.
docs-check:
	$(PYTHON) -B tools/docs_check.py

check: lint unit docs-check

# The integration suite: end-to-end pipeline, scheduler soak on the real clock, envctl flows.
# A little over a minute.
test-integration:
	$(PYTHON) -B tools/run_integration.py

# The full suite: unit and integration.
test: unit test-integration

capacity:
	$(PYTHON) -B -m datapipe capacity --env $(ENV)
DPEOF

cat > .github/workflows/ci.yml <<'DPEOF'
name: ci

on:
  push:
    branches: [main]
  pull_request:

jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.10"
      - run: make check

  integration:
    runs-on: ubuntu-latest
    needs: check
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.10"
      - run: make test-integration
DPEOF

cat > .gitignore <<'DPEOF'
__pycache__/
*.db
# Environment state and run records stay on the machine that made them.
.envs/
.runs/
DPEOF
