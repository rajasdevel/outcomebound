"""The harness seam: what `evals/run.py` needs from the tool that runs the model.

A harness is an object with a `name` and three methods. `run.py` calls only these, so a new
harness is one new module here and one entry in `evals/run.py`'s `harness()`; nothing in the
runner, the fixtures or the graders names a CLI.

    preflight() -> dict   {"ok": bool, "auth": str, "auth_evidence": str, "preflight": str};
                          observes, with no model call, that the call will use the access the
                          run intends. A login the tool does not name is not observed.
    version() -> str      the tool's own version line, or "unknown".
    call(prompt, request, cwd, write_roots, path, keep) -> CallResult
                          one model call, never retried. `request` names the model and effort
                          asked for, and whether the model's commands may bind a local port
                          (`local_listener`, false: the tool's default sandbox); `cwd` is the
                          workspace, `write_roots` the extra paths the model may write, `path`
                          the call's PATH, `keep` a new file the harness copies the tool's own
                          session record to. `request.budget` bounds the call's time and the
                          input its session may pass; a call the harness stops at either says
                          which in `extras["stopped"]`.

`evals/README.md`, "Adding a harness", states what a harness must meet.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, NamedTuple

# A serving tier is one lower-case word; it goes into the tool's argv as a config value.
SERVICE_TIER = re.compile(r"[a-z][a-z0-9_-]*")

# How a call ended early, as `extras["stopped"]` names it: its session passed the input cap, or
# the call ran past its time. None: the call ended by itself.
STOPS = ("input_cap", "timeout")


class Budget(NamedTuple):
    """What one call may spend before the harness stops it: `seconds` of wall time, and
    `input_cap`, the input tokens (cached input among them) its session may pass, None for no
    cap. The cap is best effort: the harness reads the tool's own session record about once a
    second, so the model turn in flight when the cap is passed completes before the stop."""

    seconds: float
    input_cap: int | None = None


class Request(NamedTuple):
    """What a run asks for; a call counts only where the tool's own record shows it. `model` and
    `effort` are the identity. `local_listener` lets the model's commands bind a local port,
    which the default sandbox of the tool refuses; the tool's record must show the same.
    `sandbox` is `eval`, where the model may also write `.agents/work` for task notes, or
    `field`, the tool's own default for that folder, as an adopter's session has it; the tool's
    record must show a `field` call without that grant. `budget` bounds the call (None: the
    harness's own timeout and no cap). `protected` names runner-owned paths outside the
    workspace that the model's commands read and never write (the stubs folder, the watch log):
    the harness refuses the call, before the model runs, where one lies inside a path the model
    may write. `unreadable` names runner-owned paths the model's commands should not read (the
    grading stage); a harness that can deny reads denies them, and one that cannot ignores
    them. `service_tier` is the serving tier the call asks for (Codex's `priority` is its fast
    mode); empty asks for none, and the tool's own default applies. The tool's record must show
    the tier that was asked for; a harness with no such tier refuses the request. `cell` is a new
    folder, outside every path the model may write, where a harness that gives each call a home
    of its own (Claude Code) makes it; None: beside `keep`. The runner names it with the
    workspace's opaque id, so no path the call sees names the fixture or the arm."""

    model: str
    effort: str
    local_listener: bool = False
    sandbox: str = "eval"
    budget: Budget | None = None
    protected: tuple[Path, ...] = ()
    unreadable: tuple[Path, ...] = ()
    service_tier: str = ""
    cell: Path | None = None


class CallResult(NamedTuple):
    """One call, as the runner records it.

    `answer` is the model's final message; `transcript` is a JSON document in the
    `outcomebound-command-events-v1` form that the graders read; `returncode` is the tool's
    exit status, None where the call did not finish; `observed` holds `model`, `effort`, `cwd`
    and `cli_version` as the tool's own session record states them, or None where none could be
    read; `extras` goes into the run's meta file (it names `harness`, `thread_id`,
    `native_session`, `native_sha256` and the like); `error` is why the identity does not match
    what was requested, or an empty string; `checks` lists each identity item as
    `[item, "PASS" or "FAIL", detail]`.
    """

    answer: str
    transcript: str
    returncode: int | None
    observed: dict[str, str | None] | None
    extras: dict[str, Any]
    error: str
    checks: list[list[str]]
