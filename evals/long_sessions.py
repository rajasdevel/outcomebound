"""Long fixture sessions: strict input, scripted turns and retained native usage."""

from __future__ import annotations

import contextlib
import datetime
import json
import math
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any, NamedTuple

from evals import session_protocol as protocol
from evals.claude_stream import isolation_verdict
from evals.codex_events import COST_KEYS
from evals.harnesses import Budget, CallResult, Request
from evals.native_receipts import parse_records
from evals.processes import bounded_command
from evals.session_evidence import ActionLedger, contamination, isolation_residual
from evals.session_permissions import (
    isolation_rows,
    require_seals,
    sealed_roots,
    sealed_sources,
    source_access,
    stage_access,
    tree_state,
)
from evals.session_usage import CallUsage
from evals.watch import tree_manifest

SESSION_FILE = "session.json"
TURNS_ENV = "OB_TURNS"
ACTIONS_ENV = "OB_ACTIONS"


class SessionError(ValueError):
    """A session or next-turn document that the runner cannot use."""


def _object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise SessionError(f"duplicate key {key!r}")
        result[key] = value
    return result


def _json(raw: str | bytes) -> dict[str, Any]:
    try:
        value = json.loads(raw, object_pairs_hook=_object)
    except (ValueError, UnicodeDecodeError) as problem:
        raise SessionError(f"not readable JSON: {problem}") from None
    if not isinstance(value, dict):
        raise SessionError("not a JSON object")
    return value


class Session(NamedTuple):
    shape: str
    max_turns: int
    max_nudges: int
    session_timeout_seconds: float
    input_cap: int
    next_turn: tuple[str, ...]
    labels: tuple[str, ...]
    cut_after_calls: int | None = None
    resume_message: str = ""
    cut_check: tuple[str, ...] | None = None
    # The fixture's cap on clarification turns: its next_turn enforces it, the driver its type.
    max_clarifications: int | None = None


def _limits(document: dict[str, Any]) -> float:
    for key in ("max_turns", "max_nudges", "input_cap"):
        value = document[key]
        minimum = 0 if key == "max_nudges" else 1
        if type(value) is not int or value < minimum:
            raise SessionError(f"{key} is a whole number >= {minimum}")
    raw = document["session_timeout_seconds"]
    try:
        seconds = float(raw) if type(raw) in (int, float) else float("nan")
    except OverflowError:
        seconds = float("nan")
    if not math.isfinite(seconds) or seconds <= 0:
        raise SessionError("session_timeout_seconds is a finite positive number")
    return float(seconds)


def _command(value: Any, name: str) -> tuple[str, ...]:
    if (
        not isinstance(value, list)
        or not value
        or not all(isinstance(w, str) and w.strip() and "\0" not in w for w in value)
    ):
        raise SessionError(f"{name} is a nonempty list of nonempty strings without NUL")
    return tuple(value)


def _split(document: dict[str, Any]) -> tuple[int | None, str, tuple[str, ...] | None]:
    shape = document["shape"]
    cut, message = document.get("cut_after_calls"), document.get("resume_message", "")
    if not isinstance(message, str) or "\0" in message:
        raise SessionError("resume_message is a string without NUL")
    check = document.get("cut_check")
    if shape == "split":
        if cut is not None and (type(cut) is not int or cut <= 0):
            raise SessionError("split cut_after_calls is a positive whole number")
        check = _command(check, "cut_check")
        if not message.strip():
            raise SessionError("split resume_message is a nonempty string")
        if document["max_turns"] < 2:
            raise SessionError("split max_turns is at least 2")
    elif cut is not None or check is not None:
        raise SessionError("cut_after_calls and cut_check apply only to split")
    return cut, message, check


def read_session(path: Path) -> Session | None:
    """Read session.json, refusing missing, extra or mistyped fields before setup runs."""

    if not path.exists():
        return None
    try:
        document = _json(path.read_bytes())
    except OSError as problem:
        raise SessionError(f"not readable: {problem}") from None
    required = set(Session._fields[:7])
    missing, unknown = required - document.keys(), document.keys() - set(Session._fields)
    if missing:
        raise SessionError("missing fields: " + ", ".join(sorted(missing)))
    if unknown:
        raise SessionError("unknown fields: " + ", ".join(sorted(unknown)))
    shape = document["shape"]
    if shape not in ("interactive", "unattended", "split"):
        raise SessionError("shape is interactive, unattended or split")
    seconds = _limits(document)
    command = _command(document["next_turn"], "next_turn")
    try:
        declared = protocol.labels(document["labels"])
    except protocol.ProtocolError as problem:
        raise SessionError(str(problem)) from None
    cut, message, check = _split(document)
    clarifications = document.get("max_clarifications")
    if clarifications is not None and (type(clarifications) is not int or clarifications < 0):
        raise SessionError("max_clarifications is a whole number >= 0")
    return Session(
        shape,
        document["max_turns"],
        document["max_nudges"],
        float(seconds),
        document["input_cap"],
        tuple(command),
        declared,
        cut,
        message,
        check,
        clarifications,
    )


def next_message(raw: str, declared: tuple[str, ...]) -> dict[str, Any]:
    try:
        return protocol.next_turn(_json(raw), declared)
    except protocol.ProtocolError as problem:
        raise SessionError(str(problem)) from None


def _write(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


@contextlib.contextmanager
def sealed_stage(stage: Path, extras: dict[str, Any], sources: Path | None = None):
    def reading():
        return source_access(sources, extras) if sources is not None else contextlib.nullcontext()

    mode = stage.stat().st_mode & 0o7777
    with reading():
        stage.chmod(mode or 0o700)
        before = tree_state(stage)
        stage.chmod(0)
    held = False
    try:
        yield
    finally:
        try:
            held = stage.stat().st_mode & 0o7777 == 0
            if not held:
                extras.update(
                    void="contaminated", error="the run changed grading-stage permissions"
                )
        finally:
            with reading():
                stage.chmod(mode or 0o700)
                held = held and tree_state(stage) == before
                stage.chmod(0 if sources is not None else mode)
            extras.setdefault("isolation", []).append(
                ["grading-stage-seal", "PASS" if held else "FAIL", "stage modes and content"]
            )
            if not held:
                extras.update(
                    void="contaminated",
                    error="the run changed grading-stage permissions or content",
                )


class NativeUsage:
    """Append-only source copies; each native session and call position is charged once."""

    def __init__(self, harness: str) -> None:
        self.harness = harness
        self.files: dict[str, dict[str, Any]] = {}
        self.raw: dict[str, bytes] = {}
        self.meter = CallUsage(harness)

    def add(self, extras: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        before, old_calls = self.total(), len(self.meter.calls)
        copies = extras.get("native_sessions") or [
            {
                "path": extras.get("native_session"),
                "copy": extras.get("native_copy"),
                "sha256": extras.get("native_sha256"),
            }
        ]
        for item in copies:
            source, copy = item["path"], item["copy"]
            if not source or not copy:
                raise SessionError("the turn has no retained native session")
            raw = Path(copy).read_bytes()
            if not raw.startswith(self.raw.get(source, b"")):
                raise SessionError("the native session replaced earlier turn records")
            self.meter.add(
                parse_records(raw[: raw.rfind(b"\n") + 1]),
                item.get("session_id", extras.get("thread_id") or source),
            )
            self.files[source], self.raw[source] = item, raw
        if not self.meter.calls:
            raise SessionError("the native session has no per-call token counts")
        after = self.total()
        keys = (
            (*COST_KEYS, "cache_creation_input_tokens")
            if self.harness == "claude-code"
            else COST_KEYS
        )
        return len(self.meter.calls) - old_calls, {
            k: after.get(k, 0) - before.get(k, 0) for k in keys
        }

    def total(self) -> dict[str, Any]:
        return self.meter.total()


def _transcript(turns: list[dict[str, Any]], documents: list[dict[str, Any]]) -> str:
    result: dict[str, Any] = {"format": "outcomebound-command-events-v1"}
    for key in ("commands", "outputs", "events", "files"):
        result[key] = (
            [row for doc in documents for row in doc.get(key, [])]
            if all(isinstance(doc.get(key), list) for doc in documents)
            else None
        )
    for key in ("stdout", "stderr"):
        result[key] = "\n".join(
            f"--- turn {i}: {turn['label']} ---\n{doc.get(key, '')}"
            for i, (turn, doc) in enumerate(zip(turns, documents, strict=True), 1)
        )
    result["children"] = [child for doc in documents for child in doc.get("children", [])]
    result["unknown_tools"] = sorted(
        {tool for doc in documents for tool in doc.get("unknown_tools", [])}
    )
    result["turns"] = turns
    return json.dumps(result)


class Driving(NamedTuple):
    workspace: Path
    roots: tuple[Path, ...]
    path: str
    keep: Path
    stage: Path
    env: dict[str, str]
    forbidden: tuple[Path, ...] = ()
    results_root: Path | None = None
    sources: Path | None = None


class Driver:
    """One long run; the surrounding runner owns setup, watching, sealing and grading."""

    def __init__(
        self, session: Session, prompt: str, request: Request, harness: Any, place: Driving
    ) -> None:
        self.session, self.request, self.harness, self.place = session, request, harness, place
        self.stem = place.keep.name.removesuffix(".native.jsonl")
        self.turns_file = self.file(".turns.json")
        self.actions_file = self.file(".actions.json")
        self.actions = ActionLedger()
        self.turns: list[dict[str, Any]] = []
        self.documents: list[dict[str, Any]] = []
        self.usage = NativeUsage(harness.name)
        self.started = time.monotonic()
        self.active = 0.0
        self.nudges, self.resumed = 0, ""
        self.first_calls, self.split_done = 0, False
        self.next_cut_poll = 0.0
        self.cut_polls = 0
        self.pending = {
            "label": "opener",
            "message": prompt,
            "required": True,
            "clarification": False,
            "wait_seconds": 0,
        }
        self.extras: dict[str, Any] = {}
        self.reconciliations: list[dict[str, Any]] = []
        self.initial_native: dict[str, Any] = {}
        self.checks: list[list[str]] = []
        self.last: CallResult | None = None
        self.checkpoint: tuple[list[str], tuple[int, ...]] | None = None
        self.roots_sealed = False
        self.base = request.budget or Budget(session.session_timeout_seconds)
        self.cell = request.cell or self.file(".claude-home")
        self.write_records()

    def file(self, suffix: str) -> Path:
        return self.place.keep.with_name(self.stem + suffix)

    def write_records(self) -> None:
        turns = {"version": protocol.VERSION, "turns": self.turns}
        actions = {
            "version": protocol.VERSION,
            "actions": [
                {**action, "turn": turn["turn"]}
                for turn in self.turns
                for action in turn["actions"]
            ],
        }
        protocol.turns(turns)
        protocol.actions(actions)
        _write(self.turns_file, turns)
        _write(self.actions_file, actions)

    @contextlib.contextmanager
    def sealed_call(self):
        stage = self.place.stage
        with contextlib.ExitStack() as opened:
            if self.session.cut_check and not self.split_done:
                with self.source_read():
                    command = self.command(self.session.cut_check, self.place.env)
                    descriptors = []
                    for i, word in enumerate(command):
                        if Path(word).is_file() and Path(word).resolve().is_relative_to(
                            stage.resolve()
                        ):
                            handle = opened.enter_context(Path(word).open("rb"))
                            descriptors.append(handle.fileno())
                            command[i] = f"/dev/fd/{handle.fileno()}"
                self.checkpoint = command, tuple(descriptors)
            try:
                with (
                    sealed_stage(stage, self.extras, self.place.sources),
                    sealed_sources(self.place.sources, self.extras)
                    if self.place.sources is not None
                    else contextlib.nullcontext(),
                ):
                    require_seals(
                        (stage, *self.request.unreadable, *self.place.forbidden),
                        (stage, *((self.place.sources,) if self.place.sources is not None else ())),
                        self.extras,
                    )
                    yield
            finally:
                self.checkpoint = None
                if self.roots_sealed:
                    held = all(
                        path.stat().st_mode & 0o7777 == 0o311 for path in self.sealed_paths()
                    )
                    self.extras.setdefault("isolation", []).append(
                        ["run-root-seal", "PASS" if held else "FAIL", "root modes after call"]
                    )
                    if not held:
                        self.extras.update(
                            void="contaminated", error="the run changed root permissions"
                        )

    def sealed_paths(self) -> tuple[Path, ...]:
        return (
            self.place.workspace.parent,
            self.place.keep.parent,
            self.place.results_root or self.place.keep.parent,
        )

    def seconds_left(self) -> float:
        return self.session.session_timeout_seconds - (
            time.monotonic() - self.started - self.extras.get("seal_wait_seconds", 0.0)
        )

    def budget(self) -> Budget | None:
        left = self.seconds_left()
        remaining = self.session.input_cap - self.usage.total()["input_tokens"]
        if left <= 0 or remaining <= 0:
            self.extras["stopped"] = "timeout" if left <= 0 else "input_cap"
            return None
        cap = min(self.base.input_cap, remaining) if self.base.input_cap is not None else remaining
        return Budget(min(self.base.seconds, left), cap)

    def record_extras(self, extras: dict[str, Any]) -> None:
        if self.harness.name == "claude-code":
            self.reconciliations += [
                {"turn": len(self.turns) + 1, **row}
                for row in extras.get("usage_reconciliation", [])
            ]
        rows = self.extras.get("isolation", []) + extras.get("isolation", [])
        accumulated = {
            key: list(dict.fromkeys(self.extras.get(key, []) + extras.get(key, [])))
            for key in ("cli_warnings", "unknown_item_types", "item_types", "unknown_tools")
        }
        held = {key: self.extras[key] for key in ("void", "error") if self.extras.get(key)}
        self.extras.update(extras, **accumulated, **held)
        if accumulated["unknown_tools"]:
            self.extras["decoder_verdict"] = "UNVERIFIED"
        if rows:
            verdict, items = isolation_verdict(rows)
            self.extras.update(
                isolation=rows,
                isolation_verdict=verdict,
                isolation_unverified=items if verdict == "UNVERIFIED" else [],
            )

    def call(self, budget: Budget) -> CallResult:
        turn = len(self.turns) + 1
        keep = self.place.keep if turn == 1 else self.file(f".turn-{turn}.native.jsonl")
        start_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
        cut = self.session.cut_after_calls
        with self.sealed_call():
            began = time.monotonic()
            result = self.harness.call(
                self.pending["message"],
                self.request._replace(
                    budget=budget,
                    resume=self.resumed,
                    reuse_cell=turn > 1,
                    cell=self.cell,
                    cut_check=self.cut_check
                    if self.session.shape == "split" and not self.split_done
                    else None,
                    cut_after_calls=cut - self.first_calls
                    if cut is not None and not self.split_done
                    else None,
                ),
                self.place.workspace,
                self.place.roots,
                self.place.path,
                keep,
            )
            self.active += time.monotonic() - began
        end_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self.last = result
        self.checks += result.checks
        if not self.turns:
            self.initial_native = {
                key: result.extras.get(key)
                for key in ("native_session", "native_copy", "native_sha256")
            }
        self.record_extras(result.extras)
        if result.extras.get("stopped") == "split":
            self.record_cut()
        forbidden = [
            str(p)
            for p in (
                self.place.stage,
                self.place.workspace.parent,
                self.place.keep.parent,
                self.place.results_root or self.place.keep.parent,
                *self.request.unreadable,
                *self.place.forbidden,
            )
        ] + ["person.json"]
        forbidden += [Path(w).name for w in self.session.next_turn if "/" in w]
        hits = contamination(
            result.extras.get("native_sessions", []),
            self.harness.name,
            forbidden,
            self.place.workspace,
        )
        if hits:
            evidence = self.file(f".turn-{turn}.contamination.json")
            _write(evidence, hits)
            self.extras["contamination_file"] = str(evidence)
        scan_actions = ActionLedger().add(
            result.extras.get("native_sessions", []), self.harness.name, self.place.workspace
        )
        residual = isolation_residual(
            hits,
            scan_actions,
            self.place.workspace,
        )
        self.extras["isolation_residual"] = list(
            {
                json.dumps(row, sort_keys=True): row
                for row in [*self.extras.get("isolation_residual", []), *residual]
            }.values()
        )
        answer = self.file(f".turn-{turn}.answer.md")
        transcript = self.file(f".turn-{turn}.transcript.txt")
        answer.write_text(result.answer, encoding="utf-8")
        transcript.write_text(
            f"--- turn {turn}: {self.pending['label']} ---\n{result.transcript}\n", encoding="utf-8"
        )
        calls = 0
        tokens: dict[str, Any] = {}
        try:
            calls, tokens = self.usage.add(result.extras)
        except (OSError, ValueError) as problem:
            self.extras.update(
                error=f"native session: {problem}", void=self.extras.get("void") or "runner"
            )
        if not self.split_done:
            self.first_calls += calls
        document = json.loads(result.transcript)
        actions = self.actions.add(
            result.extras.get("native_sessions", []),
            self.harness.name,
            self.place.workspace,
            result.extras.get("thread_id", ""),
        )
        self.documents.append(document)
        self.turns.append(
            {
                **self.pending,
                "turn": turn,
                "answer": result.answer,
                "answer_path": str(answer.resolve()),
                "actions": actions,
                "transcript": str(transcript),
                "started_at": start_utc,
                "ended_at": end_utc,
                "calls": calls,
                "session_id": self.extras.get("thread_id") or "",
                "session_tokens": tokens,
            }
        )
        self.write_records()
        return result

    def command(self, words: tuple[str, ...], env: dict[str, str]) -> list[str]:
        command = [re.sub(r"\$\{(\w+)\}", lambda m: env[m[1]], word) for word in words]
        if not any(
            Path(word).is_file() and Path(word).resolve().is_relative_to(self.place.stage.resolve())
            for word in command
        ):
            raise SessionError("the session program must be in the grading stage")
        return command

    def cut_check(self, *, final: bool = False) -> str | None:
        if not final and time.monotonic() < self.next_cut_poll:
            return None
        self.next_cut_poll = time.monotonic() + 5
        self.cut_polls += 1
        env = {**self.place.env, "OB_WORKSPACE": str(self.place.workspace)}
        command = self.checkpoint[0] if self.checkpoint else None
        kwargs: dict[str, Any] = {"pass_fds": self.checkpoint[1]} if self.checkpoint else {}
        for descriptor in self.checkpoint[1] if self.checkpoint else ():
            # `/dev/fd/N` shares this descriptor's offset: an earlier poll left it at the end,
            # and an empty script exits 0, which would read as the checkpoint.
            os.lseek(descriptor, 0, os.SEEK_SET)
        with self.source_read() if final else contextlib.nullcontext():
            command = command or self.command(self.session.cut_check or (), env)
            done = bounded_command(
                command,
                cwd=str(self.place.keep.parent if self.checkpoint else self.place.stage),
                env=env,
                timeout=min(30, max(self.seconds_left(), 0.001)),
                **kwargs,
            )
        _write(
            self.file(f".cut-check-{self.cut_polls}.json"),
            {"returncode": done.returncode, "stdout": done.stdout, "stderr": done.stderr},
        )
        if done.returncode not in (0, 1):
            raise SessionError(f"cut_check exited {done.returncode}")
        return "split" if done.returncode == 0 else None

    def record_cut(self, boundary: str = "cut") -> None:
        state = {
            "files": tree_manifest(self.place.workspace),
            "processes_stopped": boundary == "cut",
        }
        for name, args in (
            ("git_log", ["log", "--format=fuller"]),
            ("git_status", ["status", "--porcelain=v1", "--untracked-files=all"]),
        ):
            done = bounded_command(
                ["git", "--no-pager", *args],
                cwd=str(self.place.workspace),
                env=self.place.env,
                timeout=30,
            )
            if done.returncode:
                raise SessionError(f"cut snapshot {name}: {done.stderr}")
            state[name] = done.stdout
        target = self.file(".cut-state.json")
        _write(target, state)
        self.extras["cut_state"] = str(target)
        self.extras["split_boundary"] = boundary

    @contextlib.contextmanager
    def source_read(self):
        if self.place.sources is None:
            yield
        else:
            with source_access(self.place.sources, self.extras), stage_access(self.place.stage):
                yield

    def next_turn(self) -> dict[str, Any] | None:
        turn = len(self.turns)
        env = {
            **self.place.env,
            "OB_WORKSPACE": str(self.place.workspace),
            "OB_LAST_ANSWER": self.turns[-1].get("answer_path", ""),
            "OB_TURN": str(turn),
            "OB_HISTORY": str(self.turns_file),
            TURNS_ENV: str(self.turns_file),
            ACTIONS_ENV: str(self.actions_file),
            "OB_NUDGES": str(self.nudges),
        }
        stdout, stderr = "", ""
        try:
            self.write_records()
            with self.source_read():
                command = self.command(self.session.next_turn, env)
                done = bounded_command(
                    command,
                    cwd=str(self.place.stage),
                    env=env,
                    timeout=min(600, max(self.seconds_left(), 0.001)),
                )
            stdout, stderr = done.stdout, done.stderr
            if done.returncode:
                raise SessionError(f"exited {done.returncode}")
            following = next_message(stdout, self.session.labels)
            if self.seconds_left() <= 0:
                self.extras["stopped"] = "timeout"
                return None
            return following
        except (OSError, ValueError, KeyError, subprocess.SubprocessError) as problem:
            if isinstance(problem, subprocess.TimeoutExpired):
                output, error = problem.output, problem.stderr
                stdout = (
                    output.decode("utf-8", "replace") if isinstance(output, bytes) else output or ""
                )
                stderr = (
                    error.decode("utf-8", "replace") if isinstance(error, bytes) else error or ""
                )
            if isinstance(problem, subprocess.TimeoutExpired) and self.seconds_left() <= 0:
                self.extras["stopped"] = "timeout"
            else:
                self.extras.update(error=f"next_turn: {problem}", void="runner")
            return None
        finally:
            self.file(f".next-{turn}.stdout.txt").write_text(stdout, encoding="utf-8")
            self.file(f".next-{turn}.stderr.txt").write_text(stderr, encoding="utf-8")

    def split_boundary(self, result: CallResult) -> str | None:
        if self.split_done or self.session.shape != "split":
            return None
        stopped = result.extras.get("stopped")
        if stopped == "split":
            return "cut"
        if stopped is None and self.cut_check(final=True) == "split":
            self.record_cut("natural")
            return "natural"
        return None

    def following(self, result: CallResult) -> bool:
        self.resumed = self.extras.get("thread_id") or ""
        if not self.resumed:
            raise SessionError("the turn has no session id to resume")
        self.extras["stopped"] = None
        boundary = self.split_boundary(result)
        if boundary:
            self.extras.update(split_boundary=boundary, split_reached=True)
            self.split_done = True
            self.pending = {
                "label": "resume",
                "message": self.session.resume_message,
                "required": True,
                "clarification": False,
                "wait_seconds": 0,
            }
            self.resumed = ""
        else:
            following = self.next_turn()
            if following is None:
                return False
            if following.get("end"):
                self.extras["session_end_reason"] = following["reason"]
                self.extras["session_end"] = following
                if following["protocol_defect"]:
                    self.extras.update(
                        void="protocol_defect", error="next_turn ended as protocol_defect"
                    )
                elif self.session.shape == "split" and not self.split_done:
                    # Graded as is: recovery is not measured, and the missing work fails the run.
                    self.extras["split_reached"] = False
                return False
            wait = following.get("wait_seconds", 0)
            if wait and os.environ.get("OB_EVAL_SKIP_WAITS") == "1":
                # For the runner's own tests only; the record shows the run is no measurement.
                self.extras["waits_skipped"] = True
            elif wait:
                left = max(self.seconds_left(), 0)
                time.sleep(min(wait, left))
                if self.seconds_left() <= 0:
                    self.extras["stopped"] = "timeout"
                    return False
            self.pending = following
        return self.admit_turn()

    def admit_turn(self) -> bool:
        if len(self.turns) >= self.session.max_turns:
            self.extras["stopped"] = "max_turns"
            return False
        if self.pending["label"] == "nudge":
            if self.nudges >= self.session.max_nudges:
                self.extras["stopped"] = "max_nudges"
                return False
            self.nudges += 1
        return True

    def run(self) -> CallResult:
        seal_complete = False
        try:
            if self.place.sources is not None:
                with self.source_read():
                    pass
            with sealed_roots(self.sealed_paths(), self.place.stage, self.extras):
                self.roots_sealed = True
                self.drive()
            seal_complete = True
        except (OSError, ValueError, subprocess.SubprocessError) as problem:
            self.extras.update(error=f"session: {problem}", void="runner")
        self.record_extras(
            {
                "isolation": [
                    [
                        "session-seal",
                        "FAIL"
                        if self.extras.get("void") == "contaminated"
                        else "PASS"
                        if seal_complete
                        else "UNVERIFIED",
                        "root modes and grading stage",
                    ],
                    *isolation_rows(self.harness.name),
                ]
            }
        )
        self.extras.update(
            turns_file=str(self.turns_file),
            actions_file=str(self.actions_file),
            turns=self.turns,
            nudges=self.nudges,
            session_tokens=self.usage.total() if self.usage.files else None,
            turn_tokens=[t["session_tokens"] for t in self.turns],
            native_sessions=list(self.usage.files.values()),
            active_seconds=round(self.active, 3),
            seal_wait_seconds=round(self.extras.get("seal_wait_seconds", 0.0), 3),
            identity_checks=self.checks,
            usage_reconciliation=self.reconciliations + self.usage.meter.reconciliation(),
            **self.initial_native,
        )
        last = self.last or CallResult("", "", None, None, {}, "", [])
        return last._replace(
            transcript=_transcript(self.turns, self.documents),
            extras=self.extras,
            checks=self.checks,
        )

    def drive(self) -> None:
        while budget := self.budget():
            result = self.call(budget)
            stopped = result.extras.get("stopped")
            if (
                self.extras.get("error")
                or result.error
                or (stopped is None and (result.returncode != 0 or not result.answer.strip()))
            ):
                break
            if stopped == "cut_after_calls" or (
                not self.split_done
                and self.session.cut_after_calls is not None
                and self.first_calls >= self.session.cut_after_calls
                and stopped != "split"
            ):
                # A budget stop, graded as is: recovery is not measured.
                self.extras.update(stopped="cut_after_calls", split_reached=False)
                break
            if stopped in ("timeout", "input_cap"):
                break
            if self.usage.total()["input_tokens"] > self.session.input_cap:
                self.extras["stopped"] = "input_cap"
                break
            if not self.following(result):
                break
