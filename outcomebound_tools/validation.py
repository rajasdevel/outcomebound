"""Execute an explicit changed-risk validation plan without overstating its result.

The runner answers one narrow question per claim: did the declared check succeed?
It does not infer that the implementation, release, runtime, or user outcome is
correct beyond that declaration. Plans are explicitly selected local JSON files;
the runner does not accept stdin projections. It keeps one result record per claim
beside the claim's log (`validation_record`), which `validation status` reads. A
plan is executable code: the caller must establish its provenance before running
it. ``shell=False`` prevents implicit shell interpretation, not arbitrary effects
from an executable named by the plan.

`_execute` is also the one subprocess seam the floor runs its tools through, so a
timeout ends a check and everything it started the same way wherever it runs. No
timeout is the default: a claim waits for its command unless the plan or the claim
sets `timeout_seconds`.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import math
import re
import shutil
import subprocess
import sys
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from typing import Any

from outcomebound_tools import home, programs, schemacheck, validation_record
from outcomebound_tools.paths import names_git

PASSED = "PASS"
FAIL = "FAIL"
UNVERIFIED = "UNVERIFIED"

EXECUTABLE_KINDS = frozenset({"static", "test", "build", "runtime"})
LOG_DIR_NAME = ".outcomebound-checks"
LOG_TAIL_LINES = 20

PLAN_KEYS = frozenset({"version", "cwd", "timeout_seconds", "claims"})
CLAIM_KEYS = frozenset(
    {
        "name",
        "risk",
        "kind",
        "required",
        "command",
        "required_paths",
        "timeout_seconds",
        "executes_tests",
        "produces",
        "paths",
        "environment",
    }
)
PRODUCES_KEYS = frozenset({"paths", "when_missing"})
TESTS_KEYS = frozenset({"no_tests_exit", "ran_output", "when_none"})

_PLAN_SCHEMA_PATH = home.ROOT / "schemas" / "validation-plan.schema.json"
_PLAN_SCHEMA: dict[str, Any] | None = None


class PlanError(ValueError):
    """The validation plan cannot be executed honestly."""


def _plan_schema() -> dict[str, Any]:
    global _PLAN_SCHEMA
    if _PLAN_SCHEMA is None:
        try:
            _PLAN_SCHEMA = json.loads(_PLAN_SCHEMA_PATH.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise PlanError(f"cannot read {_PLAN_SCHEMA_PATH}: {error}") from error
    return _PLAN_SCHEMA


@dataclass(frozen=True)
class CountContract:
    """What the project declares a run that executed no test looks like.

    Exactly one of `no_tests_exit` (the command's own exit code for "no tests collected",
    such as pytest's 5) or `ran_output` (a regex the output holds where at least one test
    ran). `when_none` is the verdict for such a run: UNVERIFIED (default) or FAIL.
    """

    no_tests_exit: int | None
    ran_output: re.Pattern[str] | None
    when_none: str


@dataclass(frozen=True)
class Produces:
    """Output a claim's command must leave: each path new or changed by this run.

    `when_missing` is the verdict for a command that exited 0 and left a path
    unchanged or absent: UNVERIFIED (default) or FAIL.
    """

    paths: tuple[str, ...]
    when_missing: str


@dataclass(frozen=True)
class Claim:
    name: str
    risk: str
    kind: str
    required: bool
    command: tuple[str, ...]
    required_paths: tuple[str, ...]
    timeout_seconds: float | None
    tests: CountContract | None = None
    produces: Produces | None = None
    paths: tuple[str, ...] = ()
    environment: tuple[str, ...] = ()


@dataclass(frozen=True)
class Plan:
    cwd: Path
    claims: tuple[Claim, ...]
    log_dir: Path
    digest: str = ""


@dataclass(frozen=True)
class Result:
    claim: Claim
    status: str
    detail: str
    log_path: Path | None = None
    waiver: str | None = None
    exit_code: int | None = None
    log_written: bool = False


def _nonempty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PlanError(f"{field} must be a non-empty string")
    if "\x00" in value:
        raise PlanError(f"{field} contains a NUL byte")
    return value.strip()


def _positive_number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PlanError(f"{field} must be a positive number")
    try:
        normalized = float(value)
    except (OverflowError, ValueError) as error:
        raise PlanError(f"{field} must be a positive number") from error
    if not math.isfinite(normalized) or normalized <= 0:
        raise PlanError(f"{field} must be a positive number")
    return normalized


def _string_list(value: Any, field: str, *, allow_empty: bool) -> tuple[str, ...]:
    if not isinstance(value, list) or (not allow_empty and not value):
        qualifier = "a list" if allow_empty else "a non-empty list"
        raise PlanError(f"{field} must be {qualifier} of strings")
    return tuple(_nonempty_string(item, f"{field} item") for item in value)


def _optional_seconds(value: Any, field: str) -> float | None:
    """A timeout where one is set; None, which waits for the command, where none is."""

    return None if value is None else _positive_number(value, field)


def _tests_contract(value: Any, field: str) -> CountContract:
    if not isinstance(value, dict):
        raise PlanError(f"{field} must be an object")
    unknown = sorted(set(value) - TESTS_KEYS)
    if unknown:
        raise PlanError(f"{field} has unknown field(s): {', '.join(unknown)}")
    if ("no_tests_exit" in value) == ("ran_output" in value):
        raise PlanError(f"{field} must name exactly one of no_tests_exit and ran_output")
    when_none = value.get("when_none", UNVERIFIED)
    if when_none not in (UNVERIFIED, FAIL):
        raise PlanError(f"{field}.when_none must be {UNVERIFIED} or {FAIL}")
    exit_code_value = value.get("no_tests_exit")
    if "no_tests_exit" in value and (
        isinstance(exit_code_value, bool) or not isinstance(exit_code_value, int)
    ):
        raise PlanError(f"{field}.no_tests_exit must be an integer")
    if exit_code_value == 0:
        raise PlanError(f"{field}.no_tests_exit cannot be 0: the claim could never pass")
    pattern = None
    if "ran_output" in value:
        text = _nonempty_string(value["ran_output"], f"{field}.ran_output")
        try:
            pattern = re.compile(text, re.MULTILINE)
        except re.error as error:
            raise PlanError(f"{field}.ran_output is not a regular expression: {error}") from error
    return CountContract(exit_code_value, pattern, when_none)


def _project_paths(value: Any, field: str, *, allow_root: bool) -> tuple[str, ...]:
    """Paths relative to the plan's directory: none absolute, none with '..', none in `.git`,
    and the project itself (`.`) only where `allow_root`."""

    paths = _string_list(value, field, allow_empty=allow_root)
    for raw in paths:
        parts = re.split(r"[\\/]", raw)
        if (
            Path(raw).is_absolute()
            or PureWindowsPath(raw).anchor
            or raw.startswith(("/", "\\"))
            or ".." in parts
        ):
            raise PlanError(
                f"{field} item must be relative, inside the project, without '..': {raw}"
            )
        if any(names_git(part) for part in parts) or (
            "." in parts and not (allow_root and raw == ".")
        ):
            raise PlanError(
                f"{field} item must name a file or folder under the project, "
                f"not the project itself or anything in .git: {raw}"
            )
    return paths


def _env_names(value: Any, field: str) -> tuple[str, ...]:
    names = _string_list(value, field, allow_empty=True)
    if any("=" in name for name in names):
        raise PlanError(f"{field} item must be a variable name, without '='")
    return names


def _produces(value: Any, field: str) -> Produces:
    if not isinstance(value, dict):
        raise PlanError(f"{field} must be an object")
    unknown = sorted(set(value) - PRODUCES_KEYS)
    if unknown:
        raise PlanError(f"{field} has unknown field(s): {', '.join(unknown)}")
    if "paths" not in value:
        raise PlanError(f"{field}.paths is required")
    paths = _project_paths(value["paths"], f"{field}.paths", allow_root=False)
    when_missing = value.get("when_missing", UNVERIFIED)
    if when_missing not in (UNVERIFIED, FAIL):
        raise PlanError(f"{field}.when_missing must be {UNVERIFIED} or {FAIL}")
    return Produces(paths, when_missing)


def _claim(item: dict[str, Any], prefix: str, name: str, default_timeout: float | None) -> Claim:
    """One claim after its name was read; every other field is checked here."""

    risk = _nonempty_string(item.get("risk"), f"{prefix}.risk")
    kind = _nonempty_string(item.get("kind"), f"{prefix}.kind").lower()
    if kind not in EXECUTABLE_KINDS:
        raise PlanError(f"{prefix}.kind must be one of: {', '.join(sorted(EXECUTABLE_KINDS))}")
    required = item.get("required", True)
    if not isinstance(required, bool):
        raise PlanError(f"{prefix}.required must be boolean")
    if "command" not in item:
        raise PlanError(f"{prefix}.command is required for {kind} claims")
    return Claim(
        name=name,
        risk=risk,
        kind=kind,
        required=required,
        command=_string_list(item["command"], f"{prefix}.command", allow_empty=False),
        required_paths=_string_list(
            item.get("required_paths", []), f"{prefix}.required_paths", allow_empty=True
        ),
        timeout_seconds=_optional_seconds(
            item.get("timeout_seconds", default_timeout), f"{prefix}.timeout_seconds"
        ),
        tests=(
            _tests_contract(item["executes_tests"], f"{prefix}.executes_tests")
            if "executes_tests" in item
            else None
        ),
        produces=(
            _produces(item["produces"], f"{prefix}.produces") if "produces" in item else None
        ),
        environment=_env_names(item.get("environment", []), f"{prefix}.environment"),
        paths=(
            _project_paths(item["paths"], f"{prefix}.paths", allow_root=True)
            if "paths" in item
            else ()
        ),
    )


def _claims(raw_claims: Any, default_timeout: float | None) -> tuple[Claim, ...]:
    """Read the claim collection, preserving its order and unique names."""

    if not isinstance(raw_claims, list) or not raw_claims:
        raise PlanError("claims must be a non-empty list")

    claims: list[Claim] = []
    names: set[str] = set()
    # 0-based to match the schema check's `$.claims[0]` paths: both reach the
    # same stderr, so two numbering schemes for one claim would misdirect a reader.
    for index, item in enumerate(raw_claims):
        prefix = f"claims[{index}]"
        if not isinstance(item, dict):
            raise PlanError(f"{prefix} must be an object")
        unknown = sorted(set(item) - CLAIM_KEYS)
        if unknown:
            raise PlanError(f"{prefix} has unknown field(s): {', '.join(unknown)}")
        name = _nonempty_string(item.get("name"), f"{prefix}.name")
        if name in names:
            raise PlanError(f"duplicate claim name: {name}")
        names.add(name)
        claims.append(_claim(item, prefix, name, default_timeout))

    if not any(claim.required for claim in claims):
        raise PlanError("at least one claim must be required")
    return tuple(claims)


def parse_plan(
    raw: Any,
    *,
    invocation_cwd: Path,
    cwd_override: str | None = None,
    log_dir: Path | None = None,
) -> Plan:
    """Validate and normalize a decoded plan object."""
    if not isinstance(raw, dict):
        raise PlanError("plan root must be a JSON object")
    problems = schemacheck.validate(raw, _plan_schema())
    if problems:
        raise PlanError("; ".join(problems))
    unknown = sorted(set(raw) - PLAN_KEYS)
    if unknown:
        raise PlanError(f"unknown plan field(s): {', '.join(unknown)}")
    if raw.get("version") != 1:
        raise PlanError("version must be 1")

    raw_cwd = cwd_override if cwd_override is not None else raw.get("cwd", ".")
    cwd = Path(_nonempty_string(raw_cwd, "cwd"))
    if not cwd.is_absolute():
        cwd = invocation_cwd / cwd
    cwd = cwd.resolve()
    if not cwd.is_dir():
        raise PlanError(f"cwd is not a directory: {cwd}")

    default_timeout = _optional_seconds(raw.get("timeout_seconds"), "timeout_seconds")
    claims = _claims(raw.get("claims"), default_timeout)
    resolved_log_dir = log_dir if log_dir is not None else cwd / LOG_DIR_NAME
    return Plan(cwd=cwd, claims=claims, log_dir=resolved_log_dir)


def load_plan(path: Path, *, cwd_override: str | None = None) -> Plan:
    """Load a directly named local JSON plan."""
    plan_path = path.resolve()
    if not plan_path.is_file():
        raise PlanError(f"plan is not a file: {path}")
    try:
        plan_bytes = plan_path.read_bytes()
        raw = json.loads(plan_bytes.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PlanError(f"cannot read plan: {error}") from error
    plan = parse_plan(
        raw,
        invocation_cwd=plan_path.parent,
        cwd_override=cwd_override,
        log_dir=plan_path.parent / LOG_DIR_NAME,
    )
    return dataclasses.replace(plan, digest=hashlib.sha256(plan_bytes).hexdigest())


def _resolve_required_path(cwd: Path, raw: str) -> Path:
    path = Path(raw)
    return path if path.is_absolute() else cwd / path


class _OutsideProject(OSError):
    """A produced path resolves, through a link, outside the plan's working directory."""


def _file_state(path: Path) -> tuple[int, int, str]:
    stat = path.stat()
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return stat.st_mtime_ns, stat.st_size, digest


def _snapshot(cwd: Path, raw: str) -> object | None:
    """What a produced path holds now: None where absent, else its state.

    A file is its modification time, size and content digest; a directory is each
    file in it the same way. The path may not resolve outside `cwd`. Nothing is
    created, moved or deleted.
    """

    path = cwd / raw
    if not path.resolve().is_relative_to(cwd.resolve()):
        raise _OutsideProject(raw)
    if not path.exists():
        return None
    if path.is_dir():
        root = cwd.resolve()
        files = [entry for entry in sorted(path.rglob("*")) if entry.is_file()]
        if any(not entry.resolve().is_relative_to(root) for entry in files):
            raise _OutsideProject(raw)
        return {entry.relative_to(path).as_posix(): _file_state(entry) for entry in files}
    return _file_state(path)


PRODUCED_CAVEAT = (
    "a produced file proves only that the command wrote it, not that its content is right"
)


def _state_or_absent(cwd: Path, raw: str) -> object | None:
    """One path's state now; a path the runner cannot read reads as absent."""

    try:
        return _snapshot(cwd, raw)
    except OSError:
        return None


def _states(cwd: Path, paths: Sequence[str]) -> dict[str, object | None]:
    return {raw: _state_or_absent(cwd, raw) for raw in paths}


def _refusal(claim: Claim, cwd: Path, raw: str) -> Result | None:
    try:
        _snapshot(cwd, raw)
    except _OutsideProject:
        return Result(claim, UNVERIFIED, f"produces path is outside the project: {raw}")
    except OSError as error:
        return Result(claim, UNVERIFIED, f"cannot read produces path {raw}: {error}")
    return None


def _before(claim: Claim, cwd: Path) -> dict[str, object | None] | Result:
    """The declared paths' states before the command, or the result that refuses to run it."""

    if claim.produces is None:
        return {}
    refusals = (_refusal(claim, cwd, raw) for raw in claim.produces.paths)
    refused = next((result for result in refusals if result is not None), None)
    return refused or _states(cwd, claim.produces.paths)


def _produced(
    produces: Produces, before: Mapping[str, object | None], cwd: Path, result: Result
) -> Result:
    """A claim that exited 0, held to the output it declares.

    A path counts as produced when it is absent before and present after, or its
    state changed. The stricter of this verdict and the claim's own wins; both
    facts stay in the detail.
    """

    after = _states(cwd, produces.paths)
    missing = [raw for raw in produces.paths if after[raw] is None or after[raw] == before[raw]]
    if not missing:
        detail = f"{result.detail}; produced: {', '.join(produces.paths)} ({PRODUCED_CAVEAT})"
        return dataclasses.replace(result, detail=detail)
    detail = (
        f"{result.detail}; declared output missing or unchanged by this run: {', '.join(missing)}"
    )
    rank = {PASSED: 0, UNVERIFIED: 1, FAIL: 2}
    status = max(result.status, produces.when_missing, key=rank.__getitem__)
    return dataclasses.replace(result, status=status, detail=detail)


def _log_path(log_dir: Path, name: str) -> Path:
    """The readable log name of one claim name. A name that sanitizing left as it was keeps its
    plain name; one it changed gains a short digest of the original, so `lint/typecheck` and
    `lint typecheck` do not share a log. `_log_paths` makes the names of one plan unique."""

    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-") or "claim"
    if safe != name:
        safe = f"{safe}-{hashlib.sha256(name.encode('utf-8')).hexdigest()[:8]}"
    return log_dir / f"{safe}.log"


def _log_paths(log_dir: Path, names: Sequence[str]) -> list[Path]:
    """One log per claim of a plan, in its order, no two alike once letter case is folded: a
    plain name can equal the name a sanitized one was given (`lint-typecheck-f9a13aac`), and a
    case-insensitive file system holds `lint` and `LINT` in one file. A later claim whose name
    is taken gains its place in the plan (`lint-2.log`), so each log holds its own output."""

    taken: set[str] = set()
    found = []
    for place, name in enumerate(names, 1):
        path = _log_path(log_dir, name)
        number = place
        while path.name.casefold() in taken:
            path = log_dir / f"{path.name.removesuffix('.log')}-{number}.log"
            number += 1
        taken.add(path.name.casefold())
        found.append(path)
    return found


def _execute(
    command: Sequence[str], cwd: Path, timeout: float | None, env: Mapping[str, str] | None = None
) -> tuple[int | None, bytes, bool]:
    """Run one argv, returning (exit status or None, output, timed_out); a `timeout` of None
    waits for the command however long it runs.

    `env` replaces the inherited environment entirely; `None` inherits it. The
    caller composes it, because what belongs in it is the caller's knowledge,
    not this function's.

    A bare program name is looked for in the absolute entries of that environment's
    PATH (`programs.resolve`), never in `cwd` or in a folder `cwd` supplies; one not
    found raises `FileNotFoundError`.

    A timed-out check that spawned children leaves them running, still holding the
    write end of the captured pipe: the parent then blocks reading a pipe nobody
    will close, and the descendants keep changing a worktree the caller expects to
    be left alone. So the child leads its own process group, and a timeout ends the
    whole tree (`programs.stop_tree`).
    """

    process = programs.start_tree(
        programs.resolve(command, env),
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        shell=False,
        env=env,
    )
    try:
        output, _ = process.communicate(timeout=timeout)
        return process.returncode, output or b"", False
    except subprocess.TimeoutExpired:
        programs.stop_tree(process)
        try:
            output, _ = process.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            output = b""
        return None, output or b"", True
    except BaseException:
        # An interruption (Ctrl-C) leaves the child's group running and writing otherwise.
        programs.stop_tree(process)
        raise
    finally:
        if process.stdout is not None:
            process.stdout.close()


def _write_log(log_path: Path | None, output: bytes) -> bool:
    """Whether the output reached its log; a log that cannot be written never changes a verdict."""

    if log_path is None:
        return False
    try:
        log_path.write_bytes(output)
    except OSError:
        return False
    return True


def run_claim(
    claim: Claim, cwd: Path, log_dir: Path | None, log_path: Path | None = None
) -> Result:
    """Run one claim, judged by its exit status alone.

    With a ``log_dir`` the command's output is written to one sanitized name
    inside it, ``log_path`` where the plan gave the claim one, rewritten in place;
    ``log_dir=None`` runs the command and writes nothing at all.
    """

    missing = [raw for raw in claim.required_paths if not _resolve_required_path(cwd, raw).exists()]
    if missing:
        return Result(claim, UNVERIFIED, f"required path missing: {', '.join(missing)}")
    before = _before(claim, cwd)
    if isinstance(before, Result):
        return before
    log_path = None if log_dir is None else log_path or _log_path(log_dir, claim.name)
    if log_path is not None:
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            return Result(claim, UNVERIFIED, f"could not create check log directory: {error}")
    try:
        status, output, timed_out = _execute(claim.command, cwd, claim.timeout_seconds)
    except FileNotFoundError:
        return Result(claim, UNVERIFIED, f"executable not found: {claim.command[0]}")
    except OSError as error:
        return Result(claim, UNVERIFIED, f"could not execute check: {error}")
    log_written = _write_log(log_path, output)
    if timed_out:
        detail = f"timeout after {claim.timeout_seconds:g} seconds"
        return Result(claim, UNVERIFIED, detail, log_path, log_written=log_written)
    result = _judge(claim, status, output, log_path)
    if claim.produces is not None and status == 0:
        result = _produced(claim.produces, before, cwd, result)
    return dataclasses.replace(result, exit_code=status, log_written=log_written)


def _none_ran(
    claim: Claim, contract: CountContract, observed: str, log_path: Path | None
) -> Result:
    """The command's own word, and the project's declared contract that it ran no test."""

    consequence = (
        "so behavior is unverified"
        if contract.when_none == UNVERIFIED
        else "which the plan declares a failure"
    )
    detail = f"{observed}; the declared contract says no test executed, {consequence}"
    return Result(claim, contract.when_none, detail, log_path)


def _judge(claim: Claim, status: int | None, output: bytes, log_path: Path | None) -> Result:
    """A finished command's result: its exit status, and a declared contract that it ran a test."""

    contract = claim.tests
    if contract is not None and status is not None and status == contract.no_tests_exit:
        return _none_ran(claim, contract, f"declared check exit {status}", log_path)
    if status != 0:
        return Result(claim, FAIL, f"declared check exit {status}", log_path)
    if (
        contract is not None
        and contract.ran_output is not None
        and not contract.ran_output.search(output.decode("utf-8", errors="replace"))
    ):
        return _none_ran(claim, contract, "declared check exited 0", log_path)
    return Result(claim, PASSED, "declared check exited 0", log_path)


def tail(log_path: Path | None, lines: int = LOG_TAIL_LINES) -> str:
    if log_path is None or not log_path.is_file():
        return ""
    try:
        text = log_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return "\n".join(text.splitlines()[-lines:])


def claim_digest(claim: Claim, cwd: Path) -> str:
    """What decides how a claim's command runs and is judged: a result stands only for it."""

    tests, produces = claim.tests, claim.produces
    fields = {
        "command": claim.command,
        "cwd": str(cwd),
        "paths": claim.paths,
        "required_paths": claim.required_paths,
        "timeout_seconds": claim.timeout_seconds,
        "environment": claim.environment,
        "tests": None
        if tests is None
        else [
            tests.no_tests_exit,
            None if tests.ran_output is None else tests.ran_output.pattern,
            tests.when_none,
        ],
        "produces": None if produces is None else [produces.paths, produces.when_missing],
    }
    return hashlib.sha256(json.dumps(fields, sort_keys=True).encode("utf-8")).hexdigest()


def _kept(plan: Plan, claim: Claim, log: Path, started: str, snapshot: Any, result: Result) -> str:
    """Write this attempt's log copy and record beside the claim's latest log, never over an
    earlier attempt; the reason it was not kept, else an empty string."""

    attempt = validation_record.attempt_id()
    attempt_log, attempt_record = validation_record.attempt_paths(log, attempt)
    log_written = result.log_written
    if result.log_path is not None and result.log_written:
        try:
            shutil.copyfile(result.log_path, attempt_log)
        except OSError:
            log_written = False
    observed = {
        "claim": claim.name,
        "argv": list(claim.command),
        "cwd": str(plan.cwd),
        "paths": list(claim.paths),
        "environment": validation_record.environment(claim.environment),
        "exit_code": result.exit_code,
        "verdict": result.status,
        "detail": result.detail,
        "log": attempt_log.name if log_written else None,
        "log_written": log_written,
        "started": started,
        "ended": validation_record.now(),
        "plan_digest": plan.digest,
        "claim_digest": claim_digest(claim, plan.cwd),
    }
    record = validation_record.build(observed, snapshot)
    return validation_record.write(attempt_record, record) or ""


def run_plan(
    plan: Plan, only: Collection[str] | None = None, *, keep: bool = False
) -> tuple[Result, ...]:
    """Run the plan's claims, or those named in `only`, in plan order. With `keep`, each claim
    leaves a record beside its log, whose state of Git is read when the claim starts."""

    logs = _log_paths(plan.log_dir, [claim.name for claim in plan.claims])
    results = []
    for claim, log in zip(plan.claims, logs, strict=True):
        if only is not None and claim.name not in only:
            continue
        started = validation_record.now()
        snapshot = validation_record.capture(plan.cwd, plan.log_dir) if keep else None
        result = run_claim(claim, plan.cwd, plan.log_dir, log)
        if keep:
            problem = _kept(plan, claim, log, started, snapshot, result)
            if problem:
                sys.stderr.write(f"validation: result of {claim.name} not kept: {problem}\n")
        results.append(result)
    return tuple(results)


def verdict(results: tuple[Result, ...]) -> str:
    """FAIL when a required claim failed, else UNVERIFIED when one was not verified."""

    required = [result for result in results if result.claim.required]
    if any(result.status == FAIL for result in required):
        return FAIL
    if any(result.status == UNVERIFIED for result in required):
        return UNVERIFIED
    return PASSED


def exit_code(status: str) -> int:
    return {PASSED: 0, FAIL: 1, UNVERIFIED: 2}[status]


def _waivers(items: Sequence[str], plan: Plan) -> dict[str, str]:
    names = {claim.name for claim in plan.claims}
    waivers: dict[str, str] = {}
    for item in items:
        name, separator, reason = item.partition("=")
        name = name.strip()
        if not separator or not reason.strip():
            raise PlanError(f"--waive wants NAME=REASON, got: {item}")
        if name not in names:
            raise PlanError(f"--waive names no claim: {name}")
        if name in waivers:
            raise PlanError(f"--waive names {name} twice")
        if any(not char.isprintable() for char in reason):
            raise PlanError(f"--waive reason for {name} holds a line break or a control character")
        waivers[name] = reason.strip()
    return waivers


def _selected(names: Sequence[str], plan: Plan) -> frozenset[str] | None:
    known = {claim.name for claim in plan.claims}
    unknown = sorted(set(names) - known)
    if unknown:
        raise PlanError(f"--claim names no claim: {', '.join(unknown)}")
    return frozenset(names) if names else None


def _status(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="outcomebound validation status",
        description=(
            "Read the result a validation plan's claims last kept and say, for each, whether a\n"
            "path it declares has changed since: CURRENT (none has), CHANGED (some has, named) or\n"
            "UNVERIFIED (no result, no declared paths, a changed claim, or no Git to compare).\n"
            "It runs nothing, writes nothing and never turns a result into PASS: you judge.\n"
            "CURRENT does not show that the declared paths hold everything the command reads.\n\n"
            "Exit 0 once the plan loads, 2 for an invalid plan."
        ),
    )
    parser.add_argument("plan", help="the validation-plan JSON file")
    parser.add_argument("--cwd", help="the plan cwd override the run used")
    args = parser.parse_args(argv)
    try:
        plan = load_plan(Path(args.plan), cwd_override=args.cwd)
    except PlanError as error:
        sys.stderr.write(f"validation: UNVERIFIED — invalid plan: {error}\n")
        return 2
    logs = _log_paths(plan.log_dir, [claim.name for claim in plan.claims])
    lines: list[tuple[str, str]] = []
    for claim, log in zip(plan.claims, logs, strict=True):
        record = validation_record.latest(log, claim.name)
        state, text = validation_record.assess(
            record,
            expected={
                "claim_digest": claim_digest(claim, plan.cwd),
                "plan_digest": plan.digest,
                "environment": validation_record.environment(claim.environment),
            },
            cwd=plan.cwd,
            paths=claim.paths,
            skip=plan.log_dir,
        )
        lines.append((state, f"{state} {claim.name} — {text}\n"))
    counts = ", ".join(
        f"{sum(1 for st, _ in lines if st == name)} {name}"
        for name in (validation_record.CURRENT, validation_record.CHANGED, UNVERIFIED)
    )
    sys.stdout.write(f"status: {counts} of {len(lines)} claims (no verdict; you judge)\n")
    sys.stdout.writelines(line for _, line in lines)
    return 0


def _main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments[:1] == ["status"]:
        return _status(arguments[1:])
    parser = argparse.ArgumentParser(
        prog="outcomebound validation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "Run each check a validation plan declares, report each PASS, FAIL or UNVERIFIED,\n"
            "and end with one VERDICT line: PASS only when every required check passed.\n\n"
            "A plan is a JSON document: a cwd, an optional timeout for each check (none by\n"
            "default: a check waits for its command), and claims, each\n"
            "with a name, the risk it addresses, its kind, its command as an argv (never a\n"
            "shell string), whether it is required, and the paths it needs. Its schema is\n"
            "$(outcomebound home)/schemas/validation-plan.schema.json, and\n"
            "$(outcomebound home)/templates/validation/plan.example.json is an example.\n"
            "A plan runs its commands, so run only one you trust.\n\n"
            "Each claim that runs leaves a record (command, exit, verdict, log, times, the commit\n"
            "and the changed paths when it started) beside its log. `outcomebound validation\n"
            "status PLAN` reads them. A plan named `status` is given as ./status.\n\n"
            "Exit 0 PASS, 1 FAIL, 2 UNVERIFIED or an invalid plan."
        ),
    )
    parser.add_argument("plan", help="the validation-plan JSON file to run")
    parser.add_argument(
        "--cwd", help="override the plan cwd; relative paths use the plan directory"
    )
    parser.add_argument(
        "--claim",
        action="append",
        default=[],
        metavar="NAME",
        help="run only the named claim; repeat for more. The VERDICT line reads those claims only",
    )
    parser.add_argument(
        "--waive",
        action="append",
        default=[],
        metavar="NAME=REASON",
        help=(
            "record, beside a claim's observed result, that a person told you to go on "
            "without it; the result and the verdict stay as observed"
        ),
    )
    args = parser.parse_args(argv)

    try:
        plan = load_plan(Path(args.plan), cwd_override=args.cwd)
        only = _selected(args.claim, plan)
        waivers = _waivers(args.waive, plan)
        unrun = sorted(set(waivers) - set(only or waivers))
        if unrun:
            raise PlanError(f"--waive names a claim --claim did not select: {', '.join(unrun)}")
    except PlanError as error:
        sys.stderr.write(f"validation: UNVERIFIED — invalid plan: {error}\n")
        return 2

    results = tuple(
        dataclasses.replace(result, waiver=waivers.get(result.claim.name))
        for result in run_plan(plan, only, keep=True)
    )
    for result in results:
        requirement = "required" if result.claim.required else "optional"
        sys.stdout.write(
            f"{result.status} {result.claim.name} [{result.claim.kind}, {requirement}] — "
            f"{result.detail}; addresses: {result.claim.risk}\n"
        )
        if result.waiver is not None:
            sys.stdout.write(
                f"  waived by instruction: {result.waiver}; the observed {result.status} stands\n"
            )
        excerpt = "" if result.status == PASSED else tail(result.log_path)
        if excerpt and result.log_path is not None:
            sys.stdout.write(f"  last {LOG_TAIL_LINES} lines of {result.log_path.name}:\n")
            for line in excerpt.splitlines():
                sys.stdout.write(f"  | {line}\n")
    status = verdict(results)
    suffix = "" if status != PASSED else " (all required declared checks passed)"
    if only is not None:
        if not any(result.claim.required for result in results):
            status, suffix = UNVERIFIED, " (no required claim was selected)"
        else:
            suffix = (
                f" ({len(results)} of {len(plan.claims)} claims, selected by --claim; "
                "not the plan's verdict)"
            )
    sys.stdout.write(f"VERDICT: {status}{suffix}\n")
    return exit_code(status)


if __name__ == "__main__":
    raise SystemExit(_main())
