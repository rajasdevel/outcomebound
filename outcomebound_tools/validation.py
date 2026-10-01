"""Execute an explicit changed-risk validation plan without overstating its result.

The runner answers one narrow question per claim: did the declared check succeed?
It does not infer that the implementation, release, runtime, or user outcome is
correct beyond that declaration. Plans are explicitly selected local JSON files;
the runner does not accept stdin projections and writes no receipt or ledger. A
plan is executable code: the caller must establish its provenance before running
it. ``shell=False`` prevents implicit shell interpretation, not arbitrary effects
from an executable named by the plan.

`_execute` is also the one subprocess seam the floor runs its tools through, so a
timeout ends a check and everything it started the same way wherever it runs.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import math
import os
import re
import signal
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from outcomebound_tools import home, schemacheck

PASS = "PASS"
FAIL = "FAIL"
UNVERIFIED = "UNVERIFIED"

EXECUTABLE_KINDS = frozenset({"static", "test", "build", "runtime"})
LOG_DIR_NAME = ".outcomebound-checks"
LOG_TAIL_LINES = 20

PLAN_KEYS = frozenset({"version", "cwd", "timeout_seconds", "claims"})
CLAIM_KEYS = frozenset(
    {"name", "risk", "kind", "required", "command", "required_paths", "timeout_seconds"}
)
DEFAULT_TIMEOUT_SECONDS = 120.0

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
class Claim:
    name: str
    risk: str
    kind: str
    required: bool
    command: tuple[str, ...]
    required_paths: tuple[str, ...]
    timeout_seconds: float


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


def _claim(item: dict[str, Any], prefix: str, name: str, default_timeout: float) -> Claim:
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
        timeout_seconds=_positive_number(
            item.get("timeout_seconds", default_timeout), f"{prefix}.timeout_seconds"
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

    default_timeout = _positive_number(
        raw.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS), "timeout_seconds"
    )
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


def _terminate_group(process: subprocess.Popen[bytes]) -> None:
    """Kill the command *and everything it started*.

    A timed-out check that spawned children leaves them running, still holding
    the write end of the captured pipe: the parent then blocks reading a pipe
    nobody will close, and the descendants keep changing a worktree the caller
    expects to be left alone. Killing the session the child leads ends both. On a
    platform without process groups only the direct child is killed; the caller's
    UNVERIFIED already says descendants were not observed.
    """

    if hasattr(os, "killpg") and hasattr(os, "getpgid"):
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            return
        except OSError:
            pass
    with contextlib.suppress(OSError):
        process.kill()


def _execute(
    command: Sequence[str], cwd: Path, timeout: float, env: Mapping[str, str] | None = None
) -> tuple[int | None, bytes, bool]:
    """Run one argv, returning (exit status or None, output, timed_out).

    `env` replaces the inherited environment entirely; `None` inherits it. The
    caller composes it, because what belongs in it is the caller's knowledge,
    not this function's.
    """

    process = subprocess.Popen(
        command,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        shell=False,
        env=env,
        # POSIX: the child leads its own session, so a timeout can end every
        # descendant rather than orphaning them.
        start_new_session=os.name == "posix",
    )
    try:
        output, _ = process.communicate(timeout=timeout)
        return process.returncode, output or b"", False
    except subprocess.TimeoutExpired:
        _terminate_group(process)
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
    if status == 0:
        return Result(claim, PASS, "declared check exited 0", log_path)
    return Result(claim, FAIL, f"declared check exit {status}", log_path)


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
    return PASS


def exit_code(status: str) -> int:
    return {PASS: 0, FAIL: 1, UNVERIFIED: 2}[status]


def _main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="outcomebound validation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "Run each check a validation plan declares, report each PASS, FAIL or UNVERIFIED,\n"
            "and end with one VERDICT line: PASS only when every required check passed.\n\n"
            "A plan is a JSON document: a cwd, a timeout for each check, and claims, each\n"
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
    args = parser.parse_args(argv)

    try:
        plan = load_plan(Path(args.plan), cwd_override=args.cwd)
    except PlanError as error:
        sys.stderr.write(f"validation: UNVERIFIED — invalid plan: {error}\n")
        return 2

    results = run_plan(plan)
    for result in results:
        requirement = "required" if result.claim.required else "optional"
        sys.stdout.write(
            f"{result.status} {result.claim.name} [{result.claim.kind}, {requirement}] — "
            f"{result.detail}; addresses: {result.claim.risk}\n"
        )
        excerpt = "" if result.status == PASS else tail(result.log_path)
        if excerpt and result.log_path is not None:
            sys.stdout.write(f"  last {LOG_TAIL_LINES} lines of {result.log_path.name}:\n")
            for line in excerpt.splitlines():
                sys.stdout.write(f"  | {line}\n")
    status = verdict(results)
    suffix = "" if status != PASS else " (all required declared checks passed)"
    sys.stdout.write(f"VERDICT: {status}{suffix}\n")
    return exit_code(status)


if __name__ == "__main__":
    raise SystemExit(_main())
