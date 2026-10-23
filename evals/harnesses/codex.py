"""The Codex CLI harness: `codex exec --json`, with identity read from its native session.

The `--json` stream of codex-cli 0.162.1 carries a thread id and no model, effort or working
directory. Each is read from the session record the CLI keeps under its home (the `sessions`
folder of `$CODEX_HOME`, else of the default Codex home): found by the stream's thread id,
checked, copied byte for byte, and compared with what the run asked for. Nothing is inferred
from the arguments, and a missing record or field makes the call an error.

While the call runs, the same record is read as it grows, about once a second, for the input
the session has used so far (`SessionMeter`): a call whose input passes its budget's cap is
stopped, as one that runs past its time is.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
from collections.abc import Callable
from contextlib import closing
from pathlib import Path
from typing import Any

from evals.codex_events import (
    command_transcript,
    item_types,
    parse_events,
    session_tokens,
    stream_models,
    tokens_used,
    unknown_types,
    warnings,
)
from evals.harnesses import SERVICE_TIER, Budget, CallResult, Request
from evals.native_commands import fill_directories
from evals.native_receipts import (
    NativeCapture,
    copy_exact,
    find_session,
    parse_records,
    temporary_write_roots,
    thread_id,
)
from evals.watch import watched_command

NAME = "codex"
# These keep most of the operator's own codex setup out of every arm: without them a call loads
# `$CODEX_HOME/config.toml` (its personality, rules and writable roots) and reads and writes the
# operator's memories. Auth still comes from `CODEX_HOME`. The call keeps its session: the
# session record is where a run reads what codex ran. They do not keep out agent role files
# under `$CODEX_HOME/agents/`, which codex read in every recorded run (codex-cli 0.158.0 to
# 0.162.1); docs/evaluations.md states it as a limit.
#
# With the user config ignored, the account's plugins still reached the skill catalog: with the
# remote plugin sync on, they joined it in some calls and not in others (the sync runs
# asynchronously); with the sync off, codex read them from its plugin cache in every call. Both
# change the prompt's size and what the model reads. `features.plugins=false` keeps every plugin
# out and leaves the workspace's own skills and codex's system skills (codex-cli 0.163.0,
# observed with `codex debug prompt-input`, which calls no model); each run's `catalog` record
# shows which skills its call was given.
ISOLATION = (
    "--ignore-user-config",
    "--ignore-rules",
    "-c",
    "features.memories=false",
    "-c",
    "memories.generate_memories=false",
    "-c",
    "memories.use_memories=false",
    "-c",
    "features.plugins=false",
)
# The heading of the skill list in codex's developer message; each entry under it is one line,
# `- <name>: <description> (file: <path>)`, a plugin's skill named `<plugin>:<skill>`.
SKILL_LIST = "### Available skills"
# The thread table of codex's state database keeps whether the thread could read memories.
STATE_DATABASE = "state_5.sqlite"
# What a fixture that needs a local listener adds: the `workspace-write` option of codex that lets
# a command bind a port. codex-cli 0.163.0 offers it as one switch for all network access, the
# loopback interface and the internet alike; the sandbox refuses a bind without it.
LISTENER_SETTING = "sandbox_workspace_write.network_access=true"
# The sandbox of an adopter's own session (`Request.sandbox`): no grant for `.agents/work`, which
# codex keeps read-only inside the workspace, so a working file there is refused as in the field.
FIELD = "field"
SANDBOXES = ("eval", FIELD)
NOTES = Path(".agents") / "work"
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
        """The `codex exec` argv for one call in the `eval` sandbox: the model named, the
        operator's setup left out.

        The call may write the workspace and, where it is a Git repository, its `.git`, which
        `workspace-write` otherwise keeps read-only: a fixture would measure the sandbox, not
        the model, if a commit were impossible. Only `.agents/work` is added for task notes;
        the installed skills and the rest of `.agents` retain their default protection. `argv`
        gives a `field` call, which adds no `.agents/work`.

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
        argv += ["--add-dir", str(Path(cwd) / NOTES)]
        for root in write_roots:
            argv += ["--add-dir", str(root)]
        return argv

    def argv(
        self, request: Request, cwd: Path, last_message: Path, write_roots: tuple[Path, ...] = ()
    ) -> list[str]:
        """The `codex exec` argv for `request`: `command`, with `-c service_tier=<tier>` where a
        tier is asked for, and in a `field` sandbox without the grant of `.agents/work`, which an
        adopter's call does not have: codex keeps `.agents` read-only, and where the model keeps a
        record is measured. ValueError for a sandbox or tier this harness does not know."""

        if request.sandbox not in SANDBOXES:
            raise ValueError(f"no sandbox {request.sandbox!r}; there is {', '.join(SANDBOXES)}")
        argv = self.command(
            request.model, request.effort, cwd, last_message, write_roots, request.local_listener
        )
        if request.service_tier:
            if not SERVICE_TIER.fullmatch(request.service_tier):
                raise ValueError(f"service tier {request.service_tier!r} is one lower-case word")
            # `-c service_tier=<tier>`, next to the effort: the operator's own config is
            # ignored, so codex's fast mode (`priority`) is asked for here.
            at = argv.index(f"model_reasoning_effort={request.effort}") + 1
            argv[at:at] = ["-c", f"service_tier={request.service_tier}"]
        if request.sandbox == FIELD:
            grant = argv.index(str(Path(cwd) / NOTES))
            del argv[grant - 1 : grant + 1]
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
        check_protected(request.protected, (cwd, *write_roots))
        budget = request.budget or Budget(self._timeout)
        meter = SessionMeter(sessions)

        def over_cap(printed: Callable[[], str]) -> str | None:
            if budget.input_cap is None:
                return None
            used = meter.input(printed())
            return "input_cap" if used is not None and used > budget.input_cap else None

        with tempfile.NamedTemporaryFile(
            "r+", suffix=".md", delete=False, encoding="utf-8"
        ) as handle:
            last_message = Path(handle.name)
        try:
            done = watched_command(
                self.argv(request, cwd, last_message, write_roots),
                input=prompt,
                env={**self._env(), "PATH": path},
                cwd=str(cwd),
                timeout=budget.seconds,
                poll=over_cap,
            )
            stdout, stderr, code = done.stdout, done.stderr, done.returncode
            answer = last_message.read_text(encoding="utf-8") if last_message.is_file() else ""
        finally:
            last_message.unlink(missing_ok=True)
        transcript = command_transcript(stdout, stderr)
        events = parse_events(stdout) or []
        observed, extras, checks, session = identify(
            stdout, sessions, keep, request, cwd, stopped=bool(done.stopped)
        )
        # The stream gives no working directory for a command; the native session does.
        transcript, filled = fill_directories(transcript, session)
        extras.update(filled)
        extras.update(
            harness=NAME,
            cli_warnings=warnings(events),
            item_types=item_types(events),
            unknown_item_types=unknown_types(events),
            tokens_used=tokens_used(transcript),
            session_tokens=session_tokens(session, events),
            catalog=catalog(session),
            identity_checks=checks,
            local_listener=request.local_listener,
            sandbox=request.sandbox,
            stopped=done.stopped,
            budget_requested={"seconds": budget.seconds, "input_cap": budget.input_cap},
            input_seen_at_stop=meter.last if done.stopped else None,
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


def check_protected(protected: tuple[Path, ...], roots: tuple[Path, ...]) -> None:
    """ValueError, before the model runs, where a runner-owned path the call must only read
    lies inside a path the model may write: the workspace, an added root, or a temporary folder
    the sandbox grants."""

    writable = [root.resolve() for root in (*roots, *temporary_write_roots())]
    for path in protected:
        if any(path.resolve().is_relative_to(root) for root in writable):
            raise ValueError(f"{path} is inside a path the model may write")


def _first_thread(printed: str) -> str | None:
    """The thread id of the stream's first line, once that line is complete and is a
    `thread.started` event; None before that."""

    first, newline, _rest = printed.partition("\n")
    if not newline:
        return None
    try:
        event = json.loads(first)
    except ValueError:
        return None
    if not isinstance(event, dict) or event.get("type") != "thread.started":
        return None
    key = event.get("thread_id")
    return key if isinstance(key, str) and key else None


class SessionMeter:
    """The input a running call has used, read from its native session as the file grows.

    The session is found once, by the stream's first `thread.started` id, as the one file
    `*-<id>.jsonl` under `sessions`; each read takes only the bytes written since the last one
    and the complete lines among them. The input is the running total (`input_tokens`, cached
    input among it) of the last `token_count` event; None until one is read. This bounds spend
    only: identity and cost are read from the copied session after the call."""

    def __init__(self, sessions: Path) -> None:
        self._sessions = sessions
        self._file: Path | None = None
        self._offset = 0
        self._tail = b""
        self.last: int | None = None

    def input(self, printed: str) -> int | None:
        if self._file is None:
            key = _first_thread(printed)
            if key is None or not self._sessions.is_dir():
                return None
            matches = list(self._sessions.rglob(f"*-{key}.jsonl"))
            if len(matches) != 1:
                return None
            self._file = matches[0]
        try:
            with self._file.open("rb") as handle:
                handle.seek(self._offset)
                data = handle.read()
        except OSError:
            return self.last
        self._offset += len(data)
        *lines, self._tail = (self._tail + data).split(b"\n")
        for line in lines:
            total = _running_input(line)
            if total is not None:
                self.last = total
        return self.last


def _running_input(line: bytes) -> int | None:
    """The `input_tokens` of a `token_count` event's running total, or None for any other
    line."""

    try:
        record = json.loads(line)
    except ValueError:
        return None
    payload = record.get("payload") if isinstance(record, dict) else None
    if not isinstance(payload, dict) or payload.get("type") != "token_count":
        return None
    info = payload.get("info")
    total = info.get("total_token_usage") if isinstance(info, dict) else None
    value = total.get("input_tokens") if isinstance(total, dict) else None
    return value if type(value) is int else None


def catalog(records: list[dict[str, Any]] | None) -> dict[str, Any] | None:
    """What codex put ahead of a call's first user message, from its native session: the
    characters of the developer messages, the entries of the skill list they hold, and each
    plugin whose skills are among them, with its count. None where the session holds no
    developer message before a user message."""

    texts: list[str] = []
    for record in records or []:
        if not isinstance(record, dict) or record.get("type") != "response_item":
            continue
        payload = record.get("payload")
        if not isinstance(payload, dict):
            continue
        if payload.get("type") != "message" or payload.get("role") not in ("developer", "user"):
            continue
        if payload["role"] == "user":
            break
        parts = payload.get("content")
        texts += [
            part["text"]
            for part in (parts if isinstance(parts, list) else [])
            if isinstance(part, dict) and isinstance(part.get("text"), str)
        ]
    else:
        return None
    if not texts:
        return None
    names = [name for text in texts for name in _skill_names(text)]
    plugins: dict[str, int] = {}
    for name in names:
        if ":" in name:
            plugin = name.split(":", 1)[0]
            plugins[plugin] = plugins.get(plugin, 0) + 1
    return {
        "developer_characters": sum(len(text) for text in texts),
        "skills": len(names),
        "plugins": dict(sorted(plugins.items())),
    }


def _skill_names(text: str) -> list[str]:
    """The name of each entry of the skill list in `text`: the lines that open `- ` under its
    heading, up to the next heading or tag."""

    if SKILL_LIST not in text:
        return []
    names = []
    for line in text.split(SKILL_LIST, 1)[1].splitlines()[1:]:
        if line.startswith(("#", "<")):
            break
        if line.startswith("- "):
            names.append(line[2:].split(": ", 1)[0].strip())
    return names


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


def _service_tier(records: Records) -> tuple[str | None, str]:
    """The one serving tier every `thread_settings_applied` event of the session gives, and the
    problem otherwise (no event, or no tier in one, or two tiers)."""

    values: list[Any] = []
    for record in records:
        payload = record.get("payload")
        if record.get("type") != "event_msg" or not isinstance(payload, dict):
            continue
        if payload.get("type") != "thread_settings_applied":
            continue
        settings = payload.get("thread_settings")
        values.append(settings.get("service_tier") if isinstance(settings, dict) else None)
    if not values:
        return None, "the native session has no thread_settings_applied event"
    if any(not isinstance(value, str) or not value for value in values):
        return None, "the native session gives no service_tier"
    if len(set(values)) != 1:
        return (
            None,
            f"the native session gives conflicting service_tier values: {sorted(set(values))}",
        )
    return values[0], ""


def _session(
    sessions: Path, key: str, stopped: bool, extras: dict[str, Any]
) -> tuple[Path, bytes, Records]:
    """`find_session`; for a call the harness stopped, whose tool was ended while it wrote, the
    same file read again with the unfinished last line left out of the records (the copy keeps
    every byte). ValueError as `find_session` gives it, for any other problem."""

    try:
        return find_session(sessions, key)
    except ValueError:
        if not stopped:
            raise
        matches = list(sessions.rglob(f"*-{key}.jsonl"))
        source = matches[0] if len(matches) == 1 else None
        if source is None or source.is_symlink():
            raise
        raw = source.read_bytes()
        complete, _newline, tail = raw.rpartition(b"\n")
        if not tail or not source.resolve().is_relative_to(sessions.resolve()):
            raise
        records = parse_records(complete)
        first = records[0] if records and isinstance(records[0], dict) else {}
        payload = first.get("payload")
        if not isinstance(payload, dict) or first.get("type") != "session_meta":
            raise
        if payload.get("id") != key:
            raise
        extras["native_partial_tail"] = len(tail)
        return source, raw, records


def _notes_unwritable(records: Records, cwd: Path) -> tuple[bool, str]:
    """Whether every `turn_context` record gives the sandbox's writable roots and none of them
    is the workspace's `.agents/work` or a folder inside it, and the problem otherwise."""

    notes = (Path(cwd) / NOTES).resolve()
    # A grant of `.agents/work`, of a folder inside it, or of `.agents` itself reaches the notes.
    reaching = (notes, notes.parent)
    seen = 0
    for record in records:
        if record.get("type") != "turn_context" or not isinstance(record.get("payload"), dict):
            continue
        policy = record["payload"].get("sandbox_policy")
        roots = policy.get("writable_roots") if isinstance(policy, dict) else None
        if not isinstance(roots, list) or not all(isinstance(root, str) for root in roots):
            return False, "the native session gives no sandbox writable_roots"
        seen += 1
        granted = [
            root
            for root in roots
            if Path(root).resolve() in reaching or notes in Path(root).resolve().parents
        ]
        if granted:
            return False, f"the native session grants {granted[0]} in a field sandbox"
    if not seen:
        return False, "the native session has no turn_context"
    return True, ""


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
    stdout: str, sessions: Path, keep: Path, request: Request, cwd: Path, stopped: bool = False
) -> tuple[dict[str, str | None] | None, dict[str, Any], list[list[str]], Records | None]:
    """What the call's native session says it ran, set against what was asked for.

    Returns the observed identity (None where no session was read), the meta entries for the
    session, one check per item, and the session's records (None where none were read). A check
    that fails carries, as its detail, the text of the call error. The sandbox must allow
    network access exactly where the fixture asked for a local listener. A call the harness
    `stopped` may have left its session's last line unfinished: its records are the complete
    lines, and `native_partial_tail` gives the bytes left over."""

    model, effort, local_listener, sandbox = request[:4]
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
        source, raw, records = _session(sessions, key, stopped, extras)
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
    if request.service_tier:
        seen_tier, tier_problem = _service_tier(records)
        extras["native_service_tier"] = seen_tier
        check(
            "native-service-tier",
            seen_tier == request.service_tier,
            f"{seen_tier} == requested",
            tier_problem
            or f"the native session reports service tier {seen_tier}, not {request.service_tier}",
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
    if sandbox == FIELD:
        unwritable, notes_problem = _notes_unwritable(records, cwd)
        check(
            "native-field-sandbox", unwritable, f"{NOTES} not writable == requested", notes_problem
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
