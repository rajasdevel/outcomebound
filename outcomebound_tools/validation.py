"""Execute an explicit changed-risk validation plan without overstating its result.

The runner answers one narrow question per claim: did the declared check succeed?
It does not infer that the implementation, release, runtime, or user outcome is
correct beyond that declaration. Plans are explicitly selected local JSON files;
the runner does not accept stdin projections and writes no receipt or ledger. A
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
import contextlib
import dataclasses
import json
import math
import re
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from outcomebound_tools import home, programs, schemacheck

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
    }
)
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
class Claim:
    name: str
    risk: str
    kind: str
    required: bool
    command: tuple[str, ...]
    required_paths: tuple[str, ...]
    timeout_seconds: float | None
    tests: CountContract | None = None


@dataclass(frozen=True)
class Plan:
    cwd: Path
    claims: tuple[Claim, ...]
    log_dir: Path


@dataclass(frozen=True)
class Result:
    claim: Claim
    status: str
    detail: str
    log_path: Path | None = None
    waiver: str | None = None


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
    )


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
    raw_claims = raw.get("claims")
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
    resolved_log_dir = log_dir if log_dir is not None else cwd / LOG_DIR_NAME
    return Plan(cwd=cwd, claims=tuple(claims), log_dir=resolved_log_dir)


def load_plan(path: Path, *, cwd_override: str | None = None) -> Plan:
    """Load a directly named local JSON plan."""
    plan_path = path.resolve()
    if not plan_path.is_file():
        raise PlanError(f"plan is not a file: {path}")
    try:
        raw = json.loads(plan_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PlanError(f"cannot read plan: {error}") from error
    return parse_plan(
        raw,
        invocation_cwd=plan_path.parent,
        cwd_override=cwd_override,
        log_dir=plan_path.parent / LOG_DIR_NAME,
    )


def _resolve_required_path(cwd: Path, raw: str) -> Path:
    path = Path(raw)
    return path if path.is_absolute() else cwd / path


def _log_path(log_dir: Path, name: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-") or "claim"
    return log_dir / f"{safe}.log"


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

    process = subprocess.Popen(
        programs.resolve(command, env),
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        shell=False,
        env=env,
        **programs.new_group(),
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
    finally:
        if process.stdout is not None:
            process.stdout.close()


def run_claim(claim: Claim, cwd: Path, log_dir: Path | None) -> Result:
    """Run one claim, judged by its exit status alone.

    With a ``log_dir`` the command's output is written to one sanitized name
    inside it, rewritten in place; ``log_dir=None`` runs the command and writes
    nothing at all.
    """

    missing = [raw for raw in claim.required_paths if not _resolve_required_path(cwd, raw).exists()]
    if missing:
        return Result(claim, UNVERIFIED, f"required path missing: {', '.join(missing)}")
    log_path = None if log_dir is None else _log_path(log_dir, claim.name)
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
    if log_path is not None:
        with contextlib.suppress(OSError):
            log_path.write_bytes(output)
    if timed_out:
        detail = f"timeout after {claim.timeout_seconds:g} seconds"
        return Result(claim, UNVERIFIED, detail, log_path)
    return _judge(claim, status, output, log_path)


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


def run_plan(plan: Plan) -> tuple[Result, ...]:
    return tuple(run_claim(claim, plan.cwd, plan.log_dir) for claim in plan.claims)


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
        if not separator or not reason.strip():
            raise PlanError(f"--waive wants NAME=REASON, got: {item}")
        if name not in names:
            raise PlanError(f"--waive names no claim: {name}")
        if any(ord(char) < 32 or ord(char) == 127 for char in reason):
            raise PlanError(f"--waive reason for {name} holds a line break or a control character")
        waivers[name] = reason.strip()
    return waivers


def _main(argv: Sequence[str] | None = None) -> int:
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
            "Exit 0 PASS, 1 FAIL, 2 UNVERIFIED or an invalid plan."
        ),
    )
    parser.add_argument("plan", help="the validation-plan JSON file to run")
    parser.add_argument(
        "--cwd", help="override the plan cwd; relative paths use the plan directory"
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
        waivers = _waivers(args.waive, plan)
    except PlanError as error:
        sys.stderr.write(f"validation: UNVERIFIED — invalid plan: {error}\n")
        return 2

    results = tuple(
        dataclasses.replace(result, waiver=waivers.get(result.claim.name))
        for result in run_plan(plan)
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
    sys.stdout.write(f"VERDICT: {status}{suffix}\n")
    return exit_code(status)


if __name__ == "__main__":
    raise SystemExit(_main())
