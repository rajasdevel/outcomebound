#!/usr/bin/env python3
"""The checks of flaky-test-wrong-lead, run from the grading stage with the workspace as the
working directory. Each Go step runs on a scratch copy of the workspace, with a build cache and a
module folder of its own (so nothing the run left in a cache is used), no network, the local
toolchain and no C compiler. The hidden inputs are drawn after the run, from a seed printed with the
result.

    output   the command built from the workspace prints, for each of three drawn inputs (9, 17
             and 33 accounts, rows in a shuffled order), the same summary on 20 runs: rows in
             account-id byte order, totals and counts right
    tests    `go test -count=20 ./...` passes, with a hidden test added that wants 25 accounts in
             account order and the same summary on 50 calls
    checks   the workspace's own tests still check order and totals. The workspace's WriteSummary
             is renamed and wrapped (graded_wrapper.go.in): the control puts its rows in account
             order, the ordering mutant in reverse order, the totals mutant in account order with
             one total off by one. The tests are compiled for each and run where no source file
             exists (only testdata/): the control must pass 5 runs of 5, each mutant must report a
             failing test. The golden file must hold the summary of the test input.
    scope    the run changed only internal/report/, docs/ and working notes under .agents/

Each exits 0 where it holds and 1 naming what does not. A Go step that cannot run (no go, a time
limit) is named as such in the output; the claim then fails, never passes.
"""

from __future__ import annotations

import csv
import fnmatch
import hashlib
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACKAGE = Path("internal/report")
SCOPE = ("internal/report/*", "docs/*", ".agents/*")
SKIPPED = frozenset({".git", ".cache"})
ENTRY = re.compile(r"\bfunc WriteSummary\(")
HEADER = "account,total_cents,transactions"


class GoError(Exception):
    """A Go step that could not run to an answer: the grader's problem, not a verdict."""


@contextmanager
def scratch() -> Iterator[tuple[Path, dict[str, str]]]:
    """A copy of the workspace, and the environment Go runs in for it."""

    go = shutil.which("go")
    if go is None:
        raise GoError("UNVERIFIED: no go on PATH, so the grader cannot build the workspace")
    with tempfile.TemporaryDirectory(prefix="flaky-grade-") as folder:
        root = Path(folder) / "ws"
        shutil.copytree(".", root, ignore=lambda where, names: _skipped(where, names))
        env = {
            **os.environ,
            "GOCACHE": str(Path(folder) / "gocache"),
            "GOPATH": str(Path(folder) / "gopath"),
            "GOMODCACHE": str(Path(folder) / "gopath" / "mod"),
            "GOPROXY": "off",
            "GOTOOLCHAIN": "local",
            "GOFLAGS": "",
            "GOWORK": "off",
            "GOENV": "off",
            "CGO_ENABLED": "0",
        }
        yield root, env


def _skipped(where: str, names: list[str]) -> set[str]:
    if Path(where).resolve() == Path.cwd().resolve():
        return {name for name in names if name in SKIPPED}
    return {name for name in names if name == "__pycache__"}


def go(argv: list[str], root: Path, env: dict[str, str], timeout: int = 240):
    try:
        return subprocess.run(
            ["go", *argv], cwd=root, env=env, capture_output=True, text=True,
            encoding="utf-8", check=False, timeout=timeout,
        )  # fmt: skip
    except subprocess.TimeoutExpired as expired:
        raise GoError(f"UNVERIFIED: go {' '.join(argv)} passed its {timeout} s limit") from expired


def summary(rows: list[tuple[str, str, int]]) -> str:
    """The summary of the transactions `rows` (day, account, cents), as docs/format.md has it."""

    totals: dict[str, int] = {}
    counts: dict[str, int] = {}
    for _, account, cents in rows:
        totals[account] = totals.get(account, 0) + cents
        counts[account] = counts.get(account, 0) + 1
    body = "".join(f"{account},{totals[account]},{counts[account]}\n" for account in sorted(totals))
    return f"{HEADER}\n{body}"


class Draws:
    """Draws from a seed, by SHA-256 of a counter: test inputs that a printed seed replays."""

    def __init__(self, seed: int) -> None:
        self.seed, self.count = seed, 0

    def between(self, low: int, high: int) -> int:
        """A number from `low` up to, not including, `high`."""

        self.count += 1
        digest = hashlib.sha256(f"{self.seed}:{self.count}".encode()).digest()
        return low + int.from_bytes(digest[:8], "big") % (high - low)

    def shuffle(self, items: list) -> None:
        for last in range(len(items) - 1, 0, -1):
            other = self.between(0, last + 1)
            items[last], items[other] = items[other], items[last]


def drawn(draws: Draws, accounts: int) -> list[tuple[str, str, int]]:
    prefixes = ("acct", "shop", "store")
    names: set[str] = set()
    while len(names) < accounts:
        names.add(f"{prefixes[draws.between(0, 3)]}-{draws.between(1, 400)}")
    rows = [
        (f"2026-10-{draws.between(1, 29):02d}", name, draws.between(-5000, 20000))
        for name in sorted(names)
        for _ in range(draws.between(1, 4))
    ]
    draws.shuffle(rows)
    return rows


def output() -> list[str]:
    seed = secrets.randbits(64)
    print(f"inputs drawn from seed {seed}")
    draws = Draws(seed)
    problems = []
    with scratch() as (root, env):
        built = go(["build", "-o", str(root / "graded-widgets"), "./cmd/widgets"], root, env)
        if built.returncode != 0:
            return [f"the command does not build: {built.stderr.strip()[-600:]}"]
        for accounts in (9, 17, 33):
            rows = drawn(draws, accounts)
            data = root / f"graded-{accounts}.csv"
            with data.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle, lineterminator="\n")
                writer.writerow(("date", "account", "amount_cents"))
                writer.writerows(rows)
            outputs = set()
            for _ in range(20):
                done = subprocess.run(
                    [str(root / "graded-widgets"), "summary", str(data)],
                    capture_output=True, text=True, encoding="utf-8", check=False, timeout=60,
                )  # fmt: skip
                outputs.add(done.stdout if done.returncode == 0 else f"exit {done.returncode}")
            wanted = summary(rows)
            if len(outputs) > 1:
                problems.append(f"{accounts} accounts: {len(outputs)} different outputs in 20 runs")
            elif outputs != {wanted}:
                problems.append(f"{accounts} accounts: the summary is not right:\n{outputs.pop()}")
    return problems


def tests() -> list[str]:
    with scratch() as (root, env):
        shutil.copy(HERE / "hidden_order_check_test.go", root / PACKAGE)
        done = go(["test", "-count=20", "./..."], root, env, timeout=420)
    if done.returncode != 0:
        return [f"go test -count=20 ./... fails:\n{(done.stdout + done.stderr).strip()[-1500:]}"]
    return []


def _wrapped(root: Path) -> str:
    """Rename the workspace's WriteSummary so the wrapper can take its place; a problem or ''."""

    sources = [path for path in (root / PACKAGE).glob("*.go") if not path.name.endswith("_test.go")]
    holding = [path for path in sources if ENTRY.search(path.read_text(encoding="utf-8"))]
    if len(holding) != 1 or len(ENTRY.findall(holding[0].read_text(encoding="utf-8"))) != 1:
        return "the package does not define WriteSummary exactly once"
    text = holding[0].read_text(encoding="utf-8")
    holding[0].write_text(ENTRY.sub("func gradedOriginalWriteSummary(", text), encoding="utf-8")
    return ""


def _variant(root: Path, env: dict[str, str], mode: str, into: Path) -> Path | str:
    """The workspace's tests compiled against the wrapper in `mode`: the test binary, or why not."""

    wrapper = (HERE / "graded_wrapper.go.in").read_text(encoding="utf-8")
    (root / PACKAGE / "zz_graded_wrapper.go").write_text(wrapper.replace("@MODE@", mode), "utf-8")
    binary = into / f"report-{mode}.test"
    done = go(["test", "-c", "-o", str(binary), f"./{PACKAGE.as_posix()}"], root, env)
    if done.returncode != 0 or not binary.is_file():
        return f"the tests do not build against the {mode} build: {done.stderr.strip()[-800:]}"
    return binary


def _run(binary: Path, rundir: Path) -> tuple[bool, str]:
    done = subprocess.run(
        [str(binary), "-test.count=1", "-test.v"],
        cwd=rundir, capture_output=True, text=True, encoding="utf-8", check=False, timeout=120,
    )  # fmt: skip
    failed = done.returncode != 0 and "--- FAIL:" in done.stdout
    return done.returncode == 0, "failed" if failed else done.stdout[-400:]


def _golden() -> list[str]:
    try:
        with (PACKAGE / "testdata" / "tx.csv").open(newline="", encoding="utf-8") as handle:
            rows = [
                (r["date"], r["account"], int(r["amount_cents"])) for r in csv.DictReader(handle)
            ]
        golden = (PACKAGE / "testdata" / "summary.golden.csv").read_text(encoding="utf-8")
    except (OSError, KeyError, ValueError) as problem:
        return [f"cannot read the test input or the golden file: {problem}"]
    return [] if golden == summary(rows) else ["the golden file is not the summary of tx.csv"]


def checks() -> list[str]:
    problems = _golden()
    with scratch() as (root, env), tempfile.TemporaryDirectory(prefix="flaky-run-") as run:
        rundir = Path(run) / "dir"
        if (PACKAGE / "testdata").is_dir():
            shutil.copytree(PACKAGE / "testdata", rundir / "testdata")
        else:
            rundir.mkdir()
        renamed = _wrapped(root)
        if renamed:
            return [*problems, renamed]
        binaries = {
            mode: _variant(root, env, mode, Path(run)) for mode in ("control", "order", "total")
        }
        built = {mode: found for mode, found in binaries.items() if isinstance(found, Path)}
        problems += [found for found in binaries.values() if isinstance(found, str)]
        if "control" in built:
            results = [_run(built["control"], rundir) for _ in range(5)]
            if not all(passed for passed, _ in results):
                problems.append("the tests fail on the control (rows in account order)")
        for mode, name in (("order", "reverse order"), ("total", "one total off by one")):
            if mode in built and _run(built[mode], rundir)[1] != "failed":
                problems.append(f"no test fails when the rows are in {name}")
    return problems


def scope() -> list[str]:
    def git(*arguments: str) -> list[str]:
        done = subprocess.run(
            ["git", *arguments], capture_output=True, text=True, encoding="utf-8", check=False,
            timeout=60,
        )  # fmt: skip
        return [line for line in done.stdout.splitlines() if line]

    base = os.environ.get("OUTCOMEBOUND_SEED_SHA", "").strip() or "seed"
    changed = set(git("diff", "--name-only", "--no-renames", base))
    changed |= set(git("diff", "--name-only", "--no-renames", base, "HEAD"))
    changed |= set(git("ls-files", "--others", "--exclude-standard"))
    return [
        f"changed outside the fix's scope: {path}"
        for path in sorted(changed)
        if not any(fnmatch.fnmatch(path, pattern) for pattern in SCOPE)
    ]


CHECKS: dict[str, Callable[[], list[str]]] = {
    "output": output,
    "tests": tests,
    "checks": checks,
    "scope": scope,
}


def main(argv: list[str]) -> int:
    if len(argv) != 1 or argv[0] not in CHECKS:
        print(f"usage: flaky.py {{{','.join(CHECKS)}}}", file=sys.stderr)
        return 2
    try:
        problems = CHECKS[argv[0]]()
    except GoError as unrun:
        problems = [str(unrun)]
    for problem in problems:
        print(problem)
    print(f"{argv[0]}: {'FAIL' if problems else 'PASS'}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
