#!/usr/bin/env python3
"""The checks of flaky-test-wrong-lead, run from the grading stage with the workspace as the
working directory. Each Go step runs on a scratch copy of the workspace, with a build cache and a
module folder of its own (so nothing the run left in a cache is used), no network, the local
toolchain and no C compiler. The inputs are drawn after the run, from a seed printed with the
result.

    output   the command built from the workspace prints, for drawn inputs of 0, 1, 2, 3, 4, 9, 17
             and 33 accounts (rows in a shuffled order), the same summary on 20 runs: rows in
             account-id byte order, totals and counts right
    tests    the tests build, and `go test -count=20 ./...` passes with a hidden test added that
             wants 1 to 4 and 25 accounts in account order and the same summary on 50 calls
    checks   the workspace's own tests still check order and totals. The one package-level
             WriteSummary (a function, or a variable that holds one; found with Go's own parser,
             rename_entry.go) is renamed and wrapped (graded_wrapper.go.in): the control puts its
             rows in account order by the account field, one mutant in reverse order, the other
             in account order with one total off by one. The three test binaries are run, in an
             order drawn at random, from one path, with one environment and a fresh folder that
             holds only testdata/ (no source file): the control must pass 5 runs of 5, and each
             mutant must report a failing test. The golden file must hold the summary of tx.csv.
    scope    the run changed only internal/report/, docs/ and working notes under .agents/

Each exits 0 where it holds and 1 naming what does not. A check that cannot judge for a reason
that is not the run's prints `unjudged:` and exits 3: no go on PATH, a build step of the grader's
own past its time limit, a file the system cannot write, or a WriteSummary the wrapper cannot
take the place of. A command or a test of the run's that does not finish in time is a failure.
"""

from __future__ import annotations

import csv
import fnmatch
import hashlib
import os
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
HEADER = "account,total_cents,transactions"
SIZES = (0, 1, 2, 3, 4, 9, 17, 33)
MODES = {"control": 0, "order": 1, "total": 2}
UNJUDGED_EXIT = 3
BUILD_LIMIT, RUN_LIMIT = 300, 120


class Unjudged(Exception):
    """The check could not judge, for a reason that is not the run's."""


@contextmanager
def scratch() -> Iterator[tuple[Path, dict[str, str]]]:
    """A copy of the workspace, and the environment Go runs in for it."""

    if shutil.which("go") is None:
        raise Unjudged("no go on PATH, so the grader cannot build the workspace")
    with tempfile.TemporaryDirectory(prefix="flaky-grade-") as folder:
        root = Path(folder) / "ws"
        shutil.copytree(".", root, ignore=_skipped)
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


def build(argv: list[str], cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    """A Go build step of the grader's: past its limit, the check cannot judge."""

    try:
        return subprocess.run(
            ["go", *argv], cwd=cwd, env=env, capture_output=True, text=True,
            encoding="utf-8", check=False, timeout=BUILD_LIMIT,
        )  # fmt: skip
    except subprocess.TimeoutExpired as expired:
        raise Unjudged(
            f"go {' '.join(argv)} passed the grader's {BUILD_LIMIT} s limit"
        ) from expired


def execute(
    argv: list[str], cwd: Path, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str] | None:
    """A command of the run's (its binary, its tests): None where it does not finish in time."""

    try:
        return subprocess.run(
            argv, cwd=cwd, env=env, capture_output=True, text=True, encoding="utf-8",
            check=False, timeout=RUN_LIMIT,
        )  # fmt: skip
    except subprocess.TimeoutExpired:
        return None


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


def _write_input(path: Path, rows: list[tuple[str, str, int]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(("date", "account", "amount_cents"))
        writer.writerows(rows)


def output() -> list[str]:
    seed = secrets.randbits(64)
    print(f"inputs drawn from seed {seed}")
    draws, problems = Draws(seed), []
    with scratch() as (root, env):
        built = build(["build", "-o", str(root / "graded-widgets"), "./cmd/widgets"], root, env)
        if built.returncode != 0:
            return [f"the command does not build: {built.stderr.strip()[-600:]}"]
        for accounts in SIZES:
            rows = drawn(draws, accounts)
            data = root / f"graded-{accounts}.csv"
            _write_input(data, rows)
            outputs = set()
            for _ in range(20):
                done = execute([str(root / "graded-widgets"), "summary", str(data)], root)
                if done is None:
                    outputs.add(f"did not finish in {RUN_LIMIT} s")
                else:
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
        compiled = build(["test", "-count=1", "-run", "^$", "./..."], root, env)
        if compiled.returncode != 0:
            return [
                f"the tests do not build:\n{(compiled.stdout + compiled.stderr).strip()[-1500:]}"
            ]
        done = execute(["go", "test", "-count=20", "./..."], root, env)
    if done is None:
        return [f"go test -count=20 ./... did not finish in {RUN_LIMIT} s"]
    if done.returncode != 0:
        return [f"go test -count=20 ./... fails:\n{(done.stdout + done.stderr).strip()[-1500:]}"]
    return []


def _rename(root: Path, env: dict[str, str]) -> None:
    """Rename the workspace's one package-level WriteSummary so the wrapper can take its place."""

    found = build(["run", str(HERE / "rename_entry.go"), str(root / PACKAGE)], HERE, env)
    if found.returncode != 0:
        raise Unjudged(f"the wrapper cannot take WriteSummary's place: {found.stderr.strip()}")
    path, offset = found.stdout.strip().rsplit("\t", 1)
    source = Path(path).read_bytes()
    start = int(offset)
    if source[start : start + len(b"WriteSummary")] != b"WriteSummary":
        raise Unjudged(f"rename_entry pointed at no WriteSummary in {path}")
    renamed = (
        source[:start] + b"gradedOriginalWriteSummary" + source[start + len(b"WriteSummary") :]
    )
    Path(path).write_bytes(renamed)


def _variants(root: Path, env: dict[str, str], into: Path) -> dict[str, Path]:
    """The workspace's tests compiled against the wrapper in each mode, under random names."""

    wrapper = (HERE / "graded_wrapper.go.in").read_text(encoding="utf-8")
    binaries = {}
    for mode, number in MODES.items():
        (root / PACKAGE / "zz_graded_wrapper.go").write_text(
            wrapper.replace("@MODE@", str(number)), encoding="utf-8"
        )
        binary = into / secrets.token_hex(8) / "report.test"
        binary.parent.mkdir(parents=True)
        done = build(
            ["test", "-c", "-trimpath", "-vet=off", "-o", str(binary), f"./{PACKAGE.as_posix()}"],
            root,
            env,
        )
        if done.returncode != 0 or not binary.is_file():
            raise Unjudged(f"the wrapped tests do not build: {done.stderr.strip()[-800:]}")
        binaries[mode] = binary
    return binaries


def _run_variant(binary: Path, place: Path, testdata: Path | None) -> str:
    """Run one build from `place`/report.test in a fresh run folder: passed, failed or other."""

    for item in place.iterdir():
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()
    shutil.copy2(binary, place / "report.test")
    run = place / "run"
    run.mkdir()
    if testdata is not None:
        shutil.copytree(testdata, run / "testdata")
    done = execute([str(place / "report.test"), "-test.count=1", "-test.v"], run)
    if done is None:
        return "did not finish"
    if done.returncode == 0:
        return "passed"
    return "failed" if "--- FAIL:" in done.stdout else f"exit {done.returncode}"


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
    with scratch() as (root, env), tempfile.TemporaryDirectory(prefix="flaky-run-") as folder:
        unwrapped = Path(folder) / "unwrapped.test"
        plain = build(
            ["test", "-c", "-vet=off", "-o", str(unwrapped), f"./{PACKAGE.as_posix()}"], root, env
        )
        if plain.returncode != 0:
            return [*problems, f"the workspace's tests do not build: {plain.stderr.strip()[-800:]}"]
        _rename(root, env)
        binaries = _variants(root, env, Path(folder) / "builds")
        place = Path(folder) / secrets.token_hex(8)
        place.mkdir()
        testdata = root / PACKAGE / "testdata"
        order = ["control"] * 5 + ["order", "total"]
        secrets.SystemRandom().shuffle(order)
        results: dict[str, list[str]] = {mode: [] for mode in MODES}
        for mode in order:
            results[mode].append(
                _run_variant(binaries[mode], place, testdata if testdata.is_dir() else None)
            )
    if results["control"] != ["passed"] * 5:
        problems.append(
            f"the tests do not pass on the control (rows in account order): {results['control']}"
        )
    for mode, name in (("order", "reverse account order"), ("total", "one total off by one")):
        if results[mode] != ["failed"]:
            problems.append(f"no test fails when the rows are in {name}: {results[mode][0]}")
    return problems


def scope() -> list[str]:
    def git(*arguments: str) -> list[str]:
        done = subprocess.run(
            ["git", "--no-replace-objects", *arguments], capture_output=True, text=True,
            encoding="utf-8", check=False, timeout=60,
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
    except (Unjudged, OSError) as unrun:
        print(f"unjudged: {unrun}")
        return UNJUDGED_EXIT
    for problem in problems:
        print(problem)
    print(f"{argv[0]}: {'FAIL' if problems else 'PASS'}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
