"""The Codex CLI harness: `codex exec --json`, with identity read from its native session.

The `--json` stream of codex-cli 0.162.1 carries a thread id and no model, effort or working
directory. Each is read from the session record the CLI keeps under its home (the `sessions`
folder of `$CODEX_HOME`, else of the default Codex home): found by the stream's thread id,
checked, copied byte for byte, and compared with what the run asked for. Nothing is inferred
from the arguments, and a missing record or field makes the call an error.
"""

from __future__ import annotations

import sqlite3
import subprocess
import tempfile
from collections.abc import Callable
from contextlib import closing
from pathlib import Path
from typing import Any

from evals.codex_events import (
    command_transcript,
    item_types,
    parse_events,
    stream_models,
    tokens_used,
    unknown_types,
    warnings,
)
from evals.harnesses import CallResult, Request
from evals.native_commands import fill_directories
from evals.native_receipts import NativeCapture, copy_exact, find_session, thread_id
from evals.processes import bounded_command

NAME = "codex"
# These keep most of the operator's own codex setup out of every arm: without them a call loads
# `$CODEX_HOME/config.toml` (its personality, rules and writable roots) and reads and writes the
# operator's memories. Auth still comes from `CODEX_HOME`. The call keeps its session: the
# session record is where a run reads what codex ran. They do not keep out agent role files
# under `$CODEX_HOME/agents/`, which codex read in every recorded run (codex-cli 0.158.0 to
# 0.162.1); docs/evaluations.md states it as a limit.
ISOLATION = (
    "--ignore-user-config",
    "--ignore-rules",
    "-c",
    "features.memories=false",
    "-c",
    "memories.generate_memories=false",
    "-c",
    "memories.use_memories=false",
)
# The thread table of codex's state database keeps whether the thread could read memories.
STATE_DATABASE = "state_5.sqlite"
# What a fixture that needs a local listener adds: the `workspace-write` option of codex that lets
# a command bind a port. codex-cli 0.163.0 offers it as one switch for all network access, the
# loopback interface and the internet alike; the sandbox refuses a bind without it.
LISTENER_SETTING = "sandbox_workspace_write.network_access=true"
Run = Callable[..., Any]


class CodexHarness:
    """`env` gives the environment of every child, less each metered credential; `run` starts a
    short command and gives its status, stdout and stderr; `timeout` bounds a call."""

    name = NAME

    def __init__(self, env: Callable[[], dict[str, str]], run: Run, timeout: float = 900) -> None:
        self._env, self._run, self._timeout = env, run, timeout

    def preflight(self) -> dict[str, Any]:
        """Observe a ChatGPT login before any call; a login codex does not name is not observed."""

        status, out, error = self._run(["codex", "login", "status"])
        output = (out + error).strip()
        line = next(
            (row.strip() for row in output.splitlines() if "Logged in using ChatGPT" in row), ""
        )
        return {
            "ok": status == 0 and bool(line),
            "auth": "subscription" if status == 0 and line else "not-observed",
            "auth_evidence": line,
            "preflight": output[:2000],
        }

    def version(self) -> str:
        status, text, _error = self._run(["codex", "--version"])
        return text.strip().splitlines()[0] if status == 0 and text.strip() else "unknown"

    def home(self) -> Path:
        """The codex home the call uses: `$CODEX_HOME` as the child sees it, else the default."""

        named = self._env().get("CODEX_HOME")
        return Path(named) if named else Path.home() / ".codex"

    def command(
        self,
        model: str,
        effort: str,
        cwd: Path,
        last_message: Path,
        write_roots: tuple[Path, ...] = (),
        local_listener: bool = False,
    ) -> list[str]:
        """The `codex exec` argv for one call: the model named, the operator's setup left out.

        The call may write the workspace and, where it is a Git repository, its `.git`, which
        `workspace-write` otherwise keeps read-only: a fixture would measure the sandbox, not
        the model, if a commit were impossible. Only `.agents/work` is added for task notes;
        the installed skills and the rest of `.agents` retain their default protection.

        `workspace-write` also refuses a command a port to listen on. Only where the fixture
        needs a local listener (`local_listener`) is `LISTENER_SETTING` added; every other call
        keeps the default.
        """

        if not model:
            raise ValueError("name the model: codex's configured default never runs")
        argv = [
            "codex",
            "exec",
            "--json",
            *ISOLATION,
            "-s",
            "workspace-write",
            "-m",
            model,
            "-c",
            f"model_reasoning_effort={effort}",
            "--skip-git-repo-check",
            "-C",
            str(cwd),
            "--output-last-message",
            str(last_message),
        ]
        if local_listener:
            argv += ["-c", LISTENER_SETTING]
        if (Path(cwd) / ".git").is_dir():
            argv += ["--add-dir", str(Path(cwd) / ".git")]
        argv += ["--add-dir", str(Path(cwd) / ".agents" / "work")]
        for root in write_roots:
            argv += ["--add-dir", str(root)]
        return argv

    def call(
        self,
        prompt: str,
        request: Request,
        cwd: Path,
        write_roots: tuple[Path, ...],
        path: str,
        keep: Path,
    ) -> CallResult:
        """One call. ValueError, before the model runs, where the sessions folder or `keep` is
        within the model's reach; otherwise the result, whose `error` names a mismatch. Where
        `request.local_listener` is set the sandbox lets a command bind a port, and the native
        session must show it."""

        sessions = self.home() / "sessions"
        NativeCapture(sessions, keep).check_roots((cwd, *write_roots))
        with tempfile.NamedTemporaryFile("r+", suffix=".md", delete=False) as handle:
            last_message = Path(handle.name)
        try:
            try:
                done = bounded_command(
                    self.command(
                        request.model,
                        request.effort,
                        cwd,
                        last_message,
                        write_roots,
                        request.local_listener,
                    ),
                    input=prompt,
                    env={**self._env(), "PATH": path},
                    cwd=str(cwd),
                    timeout=self._timeout,
                )
                stdout, stderr, code = _text(done.stdout), _text(done.stderr), done.returncode
            except subprocess.TimeoutExpired as problem:
                stdout, stderr, code = _text(problem.stdout), _text(problem.stderr), None
            answer = last_message.read_text(encoding="utf-8") if last_message.is_file() else ""
        finally:
            last_message.unlink(missing_ok=True)
        transcript = command_transcript(stdout, stderr)
        events = parse_events(stdout) or []
        observed, extras, checks, session = identify(stdout, sessions, keep, request, cwd)
        # The stream gives no working directory for a command; the native session does.
        transcript, filled = fill_directories(transcript, session)
        extras.update(filled)
        extras.update(
            harness=NAME,
            cli_warnings=warnings(events),
            item_types=item_types(events),
            unknown_item_types=unknown_types(events),
            tokens_used=tokens_used(transcript),
            identity_checks=checks,
            local_listener=request.local_listener,
        )
        failed = next((check[2] for check in checks if check[1] == "FAIL"), "")
        return CallResult(answer, transcript, code, observed, extras, failed, checks)

    def memory_mode(self, thread: str) -> str | None:
        """The thread's `memory_mode` in the state database, read-only, or None where there is
        no database, table, row or value to read."""

        database = self.home() / STATE_DATABASE
        if not database.is_file():
            return None
        try:
            uri = f"{database.resolve().as_uri()}?mode=ro"
            with closing(sqlite3.connect(uri, uri=True)) as connection:
                row = connection.execute(
                    "select memory_mode from threads where id = ?", (thread,)
                ).fetchone()
        except sqlite3.Error:
            return None
        return str(row[0]) if row and row[0] is not None else None


def _text(value: str | bytes | None) -> str:
    return value.decode("utf-8", "replace") if isinstance(value, bytes) else value or ""


def _agreed(records: list[dict[str, Any]], field: str) -> tuple[str | None, str]:
    """The one value every `turn_context` record gives for `field`, and the problem otherwise."""

    values = [
        record["payload"].get(field)
        for record in records
        if record.get("type") == "turn_context" and isinstance(record.get("payload"), dict)
    ]
    if not values:
        return None, "the native session has no turn_context"
    if any(not isinstance(value, str) or not value for value in values):
        return None, f"the native session gives no {field}"
    if len(set(values)) != 1:
        return None, f"the native session gives conflicting {field} values: {sorted(set(values))}"
    return values[0], ""


Records = list[dict[str, Any]]


def _network_access(records: list[dict[str, Any]]) -> tuple[bool | None, str]:
    """Whether the sandbox policy of the session allows network access, as every `turn_context`
    record gives it, and the problem where the records give none or disagree."""

    values = []
    for record in records:
        if record.get("type") != "turn_context" or not isinstance(record.get("payload"), dict):
            continue
        policy = record["payload"].get("sandbox_policy")
        values.append(policy.get("network_access") if isinstance(policy, dict) else None)
    if not values or any(not isinstance(value, bool) for value in values):
        return None, "the native session gives no sandbox network_access"
    if len(set(values)) != 1:
        return None, f"the native session gives conflicting network_access values: {values}"
    return values[0], ""


def identify(
    stdout: str, sessions: Path, keep: Path, request: Request, cwd: Path
) -> tuple[dict[str, str | None] | None, dict[str, Any], list[list[str]], Records | None]:
    """What the call's native session says it ran, set against what was asked for.

    Returns the observed identity (None where no session was read), the meta entries for the
    session, one check per item, and the session's records (None where none were read). A check
    that fails carries, as its detail, the text of the call error. The sandbox must allow
    network access exactly where the fixture asked for a local listener."""

    model, effort, local_listener = request
    events = parse_events(stdout) or []
    checks: list[list[str]] = []

    def check(item: str, ok: bool, good: str, bad: str) -> bool:
        checks.append([item, "PASS" if ok else "FAIL", good if ok else bad])
        return ok

    extras: dict[str, Any] = {"thread_id": None, "native_session": None, "native_sha256": None}
    if not check("stream-readable", bool(events), "events read", "the CLI stream has no events"):
        return None, extras, checks, None
    try:
        key = thread_id(stdout)
    except ValueError as problem:
        check("thread-id", False, "", f"the stream has no usable thread id: {problem}")
        return None, extras, checks, None
    check("thread-id", True, key, "")
    extras["thread_id"] = key
    try:
        source, raw, records = find_session(sessions, key)
        extras["native_sha256"] = copy_exact(source, raw, keep)
    except (OSError, ValueError) as problem:
        check("native-session", False, "", f"no native session for {key}: {problem}")
        return None, extras, checks, None
    extras.update(native_session=str(source), native_copy=str(keep))
    check("native-session", True, str(source), "")

    payload = records[0].get("payload", {})
    version = payload.get("cli_version")
    seen_model, model_problem = _agreed(records, "model")
    seen_effort, effort_problem = _agreed(records, "effort")
    seen_cwd, cwd_problem = _agreed(records, "cwd")
    observed = {
        "model": seen_model,
        "effort": seen_effort,
        "cwd": seen_cwd,
        "cli_version": version if isinstance(version, str) and version else None,
    }
    check(
        "cli-version",
        observed["cli_version"] is not None,
        str(observed["cli_version"]),
        "the native session names no cli_version",
    )
    check(
        "native-model",
        seen_model == model,
        f"{seen_model} == requested",
        model_problem or f"the native session reports model {seen_model}, not {model}",
    )
    check(
        "native-effort",
        seen_effort == effort,
        f"{seen_effort} == requested",
        effort_problem or f"the native session reports effort {seen_effort}, not {effort}",
    )
    wanted = Path(cwd).resolve()
    same = (
        seen_cwd is not None and Path(seen_cwd).is_absolute() and Path(seen_cwd).resolve() == wanted
    )
    check(
        "native-cwd",
        same,
        f"{seen_cwd} == workspace",
        cwd_problem or f"the native session reports working directory {seen_cwd}, not {wanted}",
    )
    network, network_problem = _network_access(records)
    extras["sandbox_network_access"] = network
    check(
        "native-sandbox-network",
        network is local_listener,
        f"network_access {network} == requested",
        network_problem
        or f"the native session reports network_access {network}, not {local_listener}",
    )
    named = stream_models(events)
    if named:
        check(
            "stream-model",
            named == {model},
            f"{model} == requested",
            f"the stream reports model {sorted(named)}, not {model}",
        )
    return observed, extras, checks, records
