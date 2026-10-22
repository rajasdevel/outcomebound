"""The Claude Code harness: `claude -p` with stream-JSON output, one fresh home per cell.

Each call runs with a new cell folder beside its kept session copy (`<fixture>.claude-home/`):
its own `HOME`, `CLAUDE_CONFIG_DIR` and `XDG_*` folders, so nothing of the operator's Claude Code
setup (user settings, user `CLAUDE.md` and rules, installed plugins, skills, agents, memory, MCP
servers) reaches the call. The folder is kept: it holds the session the CLI wrote, and session
history is never removed. Before the call, the folders above the workspace and the machine's
managed policy are checked for instruction files and loaders (`claude_stream.reach_rows`); a
call that would read one is refused before the model runs.

The call: `--permission-mode acceptEdits` with `--permission-prompts none`, so a file edit inside
the workspace (and a root the fixture adds) is allowed and anything that would ask a person is
denied; Bash runs in Claude Code's sandbox (`--settings`: enabled, no unsandboxed retry, start
refused where the sandbox cannot run, commands allowed inside it), which confines a command's
writes to the workspace and the temporary folders and its network to nothing, with a local port
only where the fixture asks. Settings come from the project and local sources only, MCP servers
from none (`--strict-mcp-config`), plugins from the `--plugin-dir` folders the arm names only.
Hook events are printed in the stream (`--include-hook-events`), so a hook that runs is seen.

Identity: the session id, working directory, permission mode and API key source come from the
stream's start event; the model and effort from the native session's assistant records, under
the cell's `config/projects/`, found by the session id and copied byte for byte. A missing or
differing item is a call error. What the call loaded (plugins, skills, MCP servers, hooks) is
checked from the start event and the hook events (`claude_stream.loading_check`); an item the arm
does not add is a call error, so the cell is void, and an item the event does not name is
UNVERIFIED in the record, never a pass.

Login: preflight runs `claude auth status --json` in a fresh cell (no model call) and observes a
subscription sign-in (`claude.ai`, or `oauth_token` from `CLAUDE_CODE_OAUTH_TOKEN`). Whether a
subscription login stored by the operator's own session is found from a fresh config folder is
UNVERIFIED; `CLAUDE_CODE_OAUTH_TOKEN` (`claude setup-token`) is the route that does not depend on
it, and is the only Claude variable a call inherits; the sandbox hides it from the model's
commands.

While the call runs, the stream is read about once a second for the input the session has used
(`claude_stream.StreamMeter`); a call that passes its cap is stopped, as one past its time is.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any, NamedTuple

from evals.claude_stream import (
    Expected,
    StreamMeter,
    agreed,
    directories,
    effort_of,
    event_types,
    failed,
    find_native,
    hook_events,
    isolation_verdict,
    loading_check,
    model_base,
    model_names,
    reach_rows,
    result_event,
    session_id,
    session_tokens,
    start_event,
    stream_transcript,
    workspace_instructions,
    workspace_skills,
)
from evals.codex_events import parse_events
from evals.harnesses import Budget, CallResult, Request
from evals.harnesses.codex import check_protected
from evals.native_receipts import NativeCapture, copy_exact, temporary_write_roots
from evals.watch import watched_command

NAME = "claude-code"
CLI = "claude"
# A Claude Code call has no grant like codex's `.agents/work`: a file edit anywhere in the
# workspace is allowed in both, so a `field` call is the same call, recorded as such.
SANDBOXES = ("eval", "field")
# The sign-ins `claude auth status` names that bill a subscription, not an API key.
SUBSCRIPTION = ("claude.ai", "oauth_token")
# The start event's `apiKeySource` of a call that bills no API key. UNVERIFIED until a real call:
# the SDK types name `oauth` among the sources, and the CLI prints `none` where it read no key.
NO_KEY = ("none", "oauth")
PERMISSION_MODE = "acceptEdits"
# What a cell inherits of the operator's environment: all but Claude Code's own variables (its
# `CLAUDE*` settings and those it reads without the prefix: MCP, Bash, thinking and timeout
# limits, feature switches, telemetry, a model or endpoint override), Ponytail's config and the
# XDG folders, less the one credential a subscription call may need. A session started from
# inside another Claude Code session would otherwise inherit its settings.
DROPPED = (
    "CLAUDE",
    "ANTHROPIC_",
    "PONYTAIL_",
    "XDG_",
    "MCP_",
    "DISABLE_",
    "ENABLE_",
    "BASH_",
    "MAX_",
    "OTEL_",
    "VERTEX_REGION_",
    "AWS_BEARER_TOKEN_BEDROCK",
    "AI_AGENT",
    "API_TIMEOUT_MS",
    "BAGGAGE",
    "USE_LOCAL_OAUTH",
    "USE_STAGING_OAUTH",
    "USE_BUILTIN_RIPGREP",
    "SLASH_COMMAND_TOOL_CHAR_BUDGET",
    "IS_DEMO",
    "IS_SANDBOX",
    "OLDPWD",
    "SSH_AUTH_SOCK",
)
KEPT = ("CLAUDE_CODE_OAUTH_TOKEN",)
# Set in every cell: no auto memory (codex runs with memories off too), no update mid-run.
CELL_SETTINGS = {"CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1", "DISABLE_AUTOUPDATER": "1"}
# The Git identity every cell's fresh home gives, alike for every arm: a fixture's own repository
# config, where its setup writes one, takes precedence over it.
GIT_IDENTITY = ("OutcomeBound eval", "eval@example.invalid")
SUFFIX = ".native.jsonl"
CELL = ".claude-home"
# The skills an OutcomeBound install can carry: an arm that does not carry one must not load it.
OB_EXTRA_SKILLS = ("adopt-outcomebound",)
Run = Callable[..., Any]
RunEnv = Callable[[list[str], dict[str, str]], tuple[int | None, str, str]]


class Cell(NamedTuple):
    """A call's own folders: its `HOME`, its Claude config folder and its four XDG folders."""

    root: Path

    def folders(self) -> dict[str, Path]:
        return {
            "HOME": self.root / "home",
            "CLAUDE_CONFIG_DIR": self.root / "config",
            "XDG_CONFIG_HOME": self.root / "xdg" / "config",
            "XDG_DATA_HOME": self.root / "xdg" / "data",
            "XDG_CACHE_HOME": self.root / "xdg" / "cache",
            "XDG_STATE_HOME": self.root / "xdg" / "state",
        }

    def make(self) -> tuple[Path, ...]:
        """Make the folders, the cell new: FileExistsError where it is already there."""

        self.root.mkdir(parents=True, exist_ok=False)
        for folder in self.folders().values():
            folder.mkdir(parents=True)
        return tuple(self.folders().values())

    @property
    def config(self) -> Path:
        return self.folders()["CLAUDE_CONFIG_DIR"]


def cell_for(keep: Path) -> Cell:
    """The cell beside `keep`, the call's session copy: `<fixture>.claude-home/`."""

    name = keep.name.removesuffix(SUFFIX) if keep.name.endswith(SUFFIX) else keep.name
    return Cell(keep.with_name(name + CELL))


def ob_skills() -> tuple[str, ...]:
    """Every skill an OutcomeBound install of this checkout can carry."""

    from outcomebound_tools import fragments

    return (*fragments.SKILLS, *OB_EXTRA_SKILLS)


def settings(
    request: Request, write_roots: tuple[Path, ...] = (), unreadable: tuple[Path, ...] = ()
) -> dict[str, Any]:
    """The `--settings` of a call: no skill or plugin synced from claude.ai; Bash in the
    sandbox, allowed there and nowhere else, its writes confined to the workspace, the roots the
    fixture adds and the temporary folders, the runner's protected paths denied, the `unreadable`
    paths denied to its reads, no network host (the allow list is empty and strict), a local
    port only where the fixture asks, and the one credential a cell inherits hidden from the
    model's commands."""

    return {
        "syncClaudeAiSkills": False,
        "syncClaudeAiPlugins": False,
        "sandbox": {
            "enabled": True,
            "failIfUnavailable": True,
            "autoAllowBashIfSandboxed": True,
            "allowUnsandboxedCommands": False,
            "network": {
                "allowedDomains": [],
                "strictAllowlist": True,
                "allowLocalBinding": request.local_listener,
            },
            "filesystem": {
                "allowWrite": [str(root) for root in write_roots],
                "denyWrite": [str(path) for path in request.protected],
                "denyRead": [str(path) for path in unreadable],
            },
            "credentials": {"envVars": [{"name": name, "mode": "deny"} for name in KEPT]},
        },
    }


def unreadable(request: Request, cwd: Path, keep: Path) -> tuple[Path, ...]:
    """What a call's commands must not read: the request's `unreadable` paths (the grading
    stage), the operator's user-level Claude folder, every other entry of the run's evidence
    folder (other fixtures' cells, sealed graders and records) but the call's own cell, session
    copy, stubs and watch log, and the other runs' folders beside it, unless that folder is the
    file system's root, the home folder or a temporary folder. Only what exists when the call
    starts; never the workspace or a folder that holds it."""

    found = [*request.unreadable]
    user = Path.home() / ".claude"
    found += [user] if user.exists() else []
    run = keep.parent
    own = {cell_for(keep).root.resolve(), keep.resolve(), *(p.resolve() for p in request.protected)}
    if run.is_dir():
        found += [entry for entry in run.iterdir() if entry.resolve() not in own]
    shared = {Path("/").resolve(), Path.home().resolve(), *temporary_write_roots()}
    if run.parent.is_dir() and run.parent.resolve() not in shared:
        found += [entry for entry in run.parent.iterdir() if entry.resolve() != run.resolve()]
    workspace = cwd.resolve()
    return tuple(p for p in found if not workspace.is_relative_to(p.resolve()))


def _run_env(command: list[str], env: dict[str, str]) -> tuple[int | None, str, str]:
    """A short command's exit status, stdout and stderr under `env`; None where it cannot run."""

    try:
        done = subprocess.run(
            command, capture_output=True, text=True, env=env, timeout=60, encoding="utf-8"
        )
    except (OSError, subprocess.SubprocessError) as problem:
        return None, "", f"{command[0]}: {type(problem).__name__}: {problem}"
    return done.returncode, done.stdout, done.stderr


class ClaudeCodeHarness:
    """`env` gives the environment every child starts from (less each metered credential);
    `run` starts a short command under it; `timeout` bounds a call; `plugin_dirs` are the plugin
    folders the arm adds (`--plugin-dir`); `run_env` starts a short command under a given
    environment (the preflight's fresh cell)."""

    name = NAME

    def __init__(
        self,
        env: Callable[[], dict[str, str]],
        run: Run,
        timeout: float = 900,
        plugin_dirs: tuple[Path, ...] = (),
        run_env: RunEnv | None = None,
    ) -> None:
        self._env, self._run, self._timeout = env, run, timeout
        self.plugin_dirs = tuple(Path(folder).resolve() for folder in plugin_dirs)
        self._run_env = run_env or _run_env

    def preflight(self) -> dict[str, Any]:
        """Observe a subscription sign-in from a fresh cell, as a call has, with no model call.
        The cell is removed after, unless the CLI wrote a session there."""

        cell = Cell(Path(tempfile.mkdtemp(prefix="ob-claude-preflight-")) / "cell")
        cell.make()
        try:
            env = self.cell_env(cell, self._env().get("PATH", os.defpath))
            status, out, error = self._run_env([CLI, "auth", "status", "--json"], env)
        finally:
            if not (cell.config / "projects").exists():
                shutil.rmtree(cell.root.parent, ignore_errors=True)
        try:
            document = json.loads(out)
        except ValueError:
            document = None
        document = document if isinstance(document, dict) else {}
        method = document.get("authMethod")
        ok = (
            status == 0
            and document.get("loggedIn") is True
            and method in SUBSCRIPTION
            and not document.get("apiKeySource")
        )
        return {
            "ok": ok,
            "auth": "subscription" if ok else "not-observed",
            "auth_evidence": f"loggedIn {document.get('loggedIn')}, authMethod {method}",
            "preflight": (out + error).strip()[:2000],
            "hint": "sign in to Claude Code with a subscription, or set CLAUDE_CODE_OAUTH_TOKEN "
            "from `claude setup-token`; a call never falls back to an API key",
        }

    def version(self) -> str:
        status, text, _error = self._run([CLI, "--version"])
        return text.strip().splitlines()[0] if status == 0 and text.strip() else "unknown"

    def cell_env(self, cell: Cell, path: str) -> dict[str, str]:
        """The environment of a call in `cell`: the operator's, less every variable `DROPPED`
        names but the subscription token, with the cell's own folders, the call's PATH and the
        cell settings."""

        base = {
            key: value
            for key, value in self._env().items()
            if not key.startswith(DROPPED) or key in KEPT
        }
        folders = {key: str(folder) for key, folder in cell.folders().items()}
        return {**base, **folders, **CELL_SETTINGS, "PATH": path}

    def argv(
        self,
        request: Request,
        cwd: Path,
        write_roots: tuple[Path, ...] = (),
        denied: tuple[Path, ...] = (),
    ) -> list[str]:
        """The `claude -p` argv for `request` in `cwd`; the prompt is its stdin. ValueError for
        a call with no model or a sandbox this harness does not know."""

        if not request.model:
            raise ValueError("name the model: Claude Code's configured default never runs")
        if request.sandbox not in SANDBOXES:
            raise ValueError(f"no sandbox {request.sandbox!r}; there is {', '.join(SANDBOXES)}")
        argv = [
            CLI,
            "-p",
            "--output-format",
            "stream-json",
            "--verbose",
            "--include-hook-events",
            "--model",
            request.model,
            "--effort",
            request.effort,
            "--permission-mode",
            PERMISSION_MODE,
            "--permission-prompts",
            "none",
            "--setting-sources",
            "project,local",
            "--settings",
            json.dumps(settings(request, write_roots, denied), sort_keys=True),
            "--strict-mcp-config",
            "--no-chrome",
        ]
        for root in write_roots:
            argv += ["--add-dir", str(root)]
        for folder in self.plugin_dirs:
            argv += ["--plugin-dir", str(folder)]
        return argv

    def expected(self, cwd: Path) -> Expected:
        """What a call in `cwd` may load: the arm's plugins, the workspace's skills and
        instruction files, and no OutcomeBound skill the workspace does not hold."""

        own = workspace_skills(cwd)
        foreign = tuple(skill for skill in ob_skills() if skill not in own)
        return Expected(self.plugin_dirs, own, foreign, cwd, workspace_instructions(cwd))

    def call(
        self,
        prompt: str,
        request: Request,
        cwd: Path,
        write_roots: tuple[Path, ...],
        path: str,
        keep: Path,
    ) -> CallResult:
        """One call. ValueError, before the model runs, where the cell or `keep` is within the
        model's reach, a protected path is writable, the cell is not new, or the call would read
        an instruction file or loader its arm does not give it; otherwise the result, whose
        `error` names a mismatch of identity or of what loaded."""

        cell = cell_for(keep)
        NativeCapture(cell.root, keep).check_roots((cwd, *write_roots))
        check_protected(request.protected, (cwd, *write_roots))
        expected = self.expected(cwd)
        reach = reach_rows(cwd, cell.make())
        if failed(reach):
            shutil.rmtree(cell.root)  # made by this call, and holding no session yet
            raise ValueError(
                "the call would read what its arm does not give it: " + "; ".join(failed(reach))
            )
        identity = cell.folders()["HOME"] / ".gitconfig"
        identity.write_text(
            f"[user]\n\tname = {GIT_IDENTITY[0]}\n\temail = {GIT_IDENTITY[1]}\n", encoding="utf-8"
        )
        denied = unreadable(request, cwd, keep)
        budget = request.budget or Budget(self._timeout)
        meter = StreamMeter()

        def over_cap(printed: Callable[[], str]) -> str | None:
            if budget.input_cap is None:
                return None
            used = meter.input(printed())
            return "input_cap" if used is not None and used > budget.input_cap else None

        argv = self.argv(request, cwd, write_roots, denied)
        done = watched_command(
            argv,
            input=prompt,
            env=self.cell_env(cell, path),
            cwd=str(cwd),
            timeout=budget.seconds,
            poll=over_cap,
        )
        events = parse_events(done.stdout) or []
        observed, extras, checks, records = identify(
            events, cell.config, keep, request, cwd, stopped=bool(done.stopped)
        )
        transcript, decoded = stream_transcript(
            done.stdout, done.stderr, directories(records or [])
        )
        loading = loading_check(events, expected, records)
        void = failed(loading)
        verdict, items = isolation_verdict(loading)
        detail = "; ".join(void) or (
            f"unverified: {', '.join(items)}" if items else "nothing the arm lacks"
        )
        checks.append(["isolation", verdict, detail])
        tokens = session_tokens(events)
        result = result_event(events) or {}
        extras.update(
            harness=NAME,
            claude_home=str(cell.root),
            item_types=event_types(events),
            unknown_item_types=[f"tool.{name}" for name in decoded.unknown],
            tools=decoded.tools,
            skills_invoked=decoded.skills,
            files_recorded=len(decoded.files) if decoded.files is not None else None,
            session_tokens=tokens,
            tokens_used=tokens["input_tokens"] + tokens["output_tokens"] if tokens else None,
            catalog=None,
            identity_checks=checks,
            isolation=[*reach, *loading],
            isolation_verdict=verdict,
            isolation_unverified=items if verdict == "UNVERIFIED" else [],
            void="isolation" if void else None,
            git_identity=list(GIT_IDENTITY),
            start=_start_record(events),
            hooks=hook_events(events),
            permission_denials=len(result.get("permission_denials") or []),
            result_subtype=result.get("subtype"),
            num_turns=result.get("num_turns"),
            local_listener=request.local_listener,
            sandbox=request.sandbox,
            settings=settings(request, write_roots, denied),
            plugin_dirs=[str(folder) for folder in self.plugin_dirs],
            stopped=done.stopped,
            budget_requested={"seconds": budget.seconds, "input_cap": budget.input_cap},
            input_seen_at_stop=meter.last if done.stopped else None,
        )
        error = next((c[2] for c in checks if c[1] == "FAIL" and c[0] != "isolation"), "")
        if not error and void:
            error = "isolation: " + "; ".join(void)
        return CallResult(
            decoded.answer, transcript, done.returncode, observed, extras, error, checks
        )


START_KEYS = (
    "model",
    "cwd",
    "permissionMode",
    "apiKeySource",
    "claude_code_version",
    "tools",
    "plugins",
    "skills",
    "mcp_servers",
    "agents",
    "slash_commands",
    "output_style",
)


def _start_record(events: list[dict[str, Any]]) -> dict[str, Any] | None:
    """What the meta keeps of the start event: what the call was given."""

    start = start_event(events)
    return {key: start[key] for key in START_KEYS if key in start} if start else None


Records = list[dict[str, Any]]


def identify(
    events: list[dict[str, Any]],
    config: Path,
    keep: Path,
    request: Request,
    cwd: Path,
    stopped: bool = False,
) -> tuple[dict[str, str | None] | None, dict[str, Any], list[list[str]], Records | None]:
    """What the call's stream and native session say it ran, set against what was asked for.

    Returns the observed identity (None where no session was read), the meta entries for the
    session, one check per item, and the session's records. A call the harness `stopped` may
    have left its session's last line unfinished: its records are the complete lines, and
    `native_partial_tail` gives the bytes left over."""

    checks: list[list[str]] = []

    def check(item: str, ok: bool | None, good: str, bad: str) -> None:
        """One identity item: PASS, FAIL, or UNVERIFIED where `ok` is None (no record names
        it; recorded, never a call error)."""

        verdict = "UNVERIFIED" if ok is None else "PASS" if ok else "FAIL"
        checks.append([item, verdict, bad if ok is False or ok is None else good])

    extras: dict[str, Any] = {"thread_id": None, "native_session": None, "native_sha256": None}
    check("stream-readable", bool(events), "events read", "the CLI stream has no events")
    try:
        key = session_id(events)
    except ValueError as problem:
        check("session-id", False, "", str(problem))
        return None, extras, checks, None
    check("session-id", True, key, "")
    extras["thread_id"] = key
    try:
        source, raw, records, tail = find_native(config, key)
        if tail and not stopped:
            raise ValueError("its last line is unfinished, and the call was not stopped")
        extras["native_sha256"] = copy_exact(source, raw, keep)
    except (OSError, ValueError) as problem:
        check("native-session", False, "", f"no native session for {key}: {problem}")
        return None, extras, checks, None
    extras.update(native_session=str(source), native_copy=str(keep))
    if tail:
        extras["native_partial_tail"] = tail
    check("native-session", True, str(source), "")
    start = start_event(events) or {}
    _identity_checks(check, start, records, request, cwd, events)
    version = start.get("claude_code_version")
    extras["models_raw"] = sorted(
        {*model_names(events), *filter(None, [agreed(records, "model")[0]])}
    )
    observed = {
        "model": model_base(agreed(records, "model")[0]),
        "effort": effort_of(records)[0],
        "cwd": start.get("cwd") if isinstance(start.get("cwd"), str) else None,
        "cli_version": version if isinstance(version, str) and version else None,
    }
    return observed, extras, checks, records


def _identity_checks(
    check: Callable[[str, bool | None, str, str], None],
    start: dict[str, Any],
    records: Records,
    request: Request,
    cwd: Path,
    events: list[dict[str, Any]],
) -> None:
    """The identity items: the CLI version, the model and effort of the native session, the
    working directory, permission mode and API key source of the start event, and the models
    the stream names. A model is compared without a context-window suffix (`[1m]`); an effort
    no assistant record names is UNVERIFIED, one that differs is a FAIL."""

    version = start.get("claude_code_version")
    check(
        "cli-version",
        isinstance(version, str) and bool(version),
        str(version),
        "the start event names no claude_code_version",
    )
    wanted = model_base(request.model)
    model, problem = agreed(records, "model")
    check(
        "native-model",
        model is not None and model_base(model) == wanted,
        f"{model} == requested",
        problem or f"the native session reports model {model}, not {request.model}",
    )
    effort, problem = effort_of(records)
    check(
        "native-effort",
        None if problem == "unrecorded" else effort == request.effort,
        f"{effort} == requested",
        "no assistant record names an effort"
        if problem == "unrecorded"
        else problem or f"the native session reports effort {effort}, not {request.effort}",
    )
    seen = start.get("cwd")
    same = (
        isinstance(seen, str)
        and Path(seen).is_absolute()
        and Path(seen).resolve() == Path(cwd).resolve()
    )
    check(
        "start-cwd",
        same,
        f"{seen} == workspace",
        f"the start event reports working directory {seen}, not {Path(cwd).resolve()}",
    )
    mode = start.get("permissionMode")
    check(
        "permission-mode",
        mode == PERMISSION_MODE,
        f"{mode} == requested",
        f"the start event reports permission mode {mode}, not {PERMISSION_MODE}",
    )
    source = start.get("apiKeySource")
    check(
        "api-key-source",
        source in NO_KEY,
        f"{source}: no API key",
        f"the start event reports API key source {source!r}; a call bills no API key",
    )
    named = model_names(events)
    check(
        "stream-model",
        {model_base(name) for name in named} == {wanted},
        f"{request.model} == requested",
        f"the stream reports model {sorted(named)}, not {request.model}",
    )
