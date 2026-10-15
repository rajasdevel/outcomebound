"""The finish check: at a harness's turn end, the project's recorded Done commands are checked, and
no turn end waits for them.

`outcomebound finish-check --constant-time --harness <row> --done <digest> --timeout <seconds>` is
the stop entry adopt writes into a row's settings document (`docs/specs/finish-check/design.md`,
"Constant-time stop"); the rows are those whose harness table entry carries `finish_hook`,
`claude-code` and `codex`. The Done commands run only while their digest is the entry's, and only
on a working tree they have not already been checked on, in the run: on a row whose `wake` field
names a key (claude-code's `asyncRewake`) the entry runs in the background and is the run, which
exits 2 with the report on stderr only on a failure that holds and otherwise prints nothing; on
any other row (codex) the stop reads, decides and prints its JSON in constant time and starts the
run detached, and a later stop delivers what it found. A failure holds unless it is a known
failure (`measure`), was seen on the tree the turn began with by another session's run or already
held in this session, or its signature was held once in the session; each other outcome goes to
the person once for each session, tree and kind: at a codex stop, or through the claude-code
turn-start entry (`--mark`). `--status` prints the last run and the records and writes nothing.
The run keeps its record, the checked-tree records, the lock and, in the Git common directory,
the held list; it writes nothing outside the Git directory. A usage error exits 1, never 2, which
a row reads as holding the finish.

What it does not decide: whether the harness fires the hook or runs an async entry (its install
report reads `UNVERIFIED` until a person sees it), or what the Done commands are. It compares a
known command's exit code and the failure ids its output names; where neither the record nor the
output names any, a new failure inside a command that fails with the same exit code is not told
apart from the known one.
"""

from __future__ import annotations

import argparse
import contextlib
import fnmatch
import hashlib
import io
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import IO, Any, NoReturn

from outcomebound_tools import adapters, paths, programs
from outcomebound_tools.gitenv import GIT_READ_CONFIGURATION, git_environment

ID = "finish-check"
# What every entry's command starts with, looked for before a settings document is parsed.
MARKER = f"outcomebound {ID}".encode()
MANIFEST = ".outcomebound/manifest.json"
FACTS = "project-facts"
# The seconds adopt writes in the row's `timeout` field and passes to the verb where the person
# names none: the documented default of both rows, a setting and not a ceiling (research
# harnesses/claude-code.md:267, harnesses/codex.md:143). `adopt --finish-timeout` changes it.
DEFAULT_TIMEOUT = 600
# The verb stops its commands this many seconds before the entry's timeout, so it remembers and
# reports the stop itself rather than being cut off by the harness; a timeout must exceed it.
MARGIN_SECONDS = 30
REPORT_CHARACTERS = 4000
# The seconds of the margin, after the commands' deadline, in which the tree is read again and
# its verdict remembered; the rest of the margin is the report's. A verdict is remembered only
# where both finish within them, a command stopped at the deadline included.
REMEMBER_SECONDS = 15
# The longest backtick run output keeps as written; a longer one is written as its count.
LONGEST_RUN = 15
BACKTICKS = re.compile(f"`{{{LONGEST_RUN + 1},}}")
# Where the last tree the Done commands were checked on is kept with its verdict, in the Git
# directory.
STATE = "outcomebound-finish-check"
# Where the Done commands that failed when adopt last measured them are kept, in the Git common
# directory, so that every worktree of the repository reads the one record.
KNOWN = "outcomebound-finish-check-known"
# The tree a turn began with, kept beside the checked-tree record, and the entry that writes it.
MARK = f"{STATE}-mark"
# What the person was told, as (session, tree, kind) triples, so that each notice is told once.
TOLD = f"{STATE}-told"
# The constant-time stop's own files: the record of the run in flight or last ended, and the lock
# that keeps one run for each Git directory, both in the Git directory; the note that a run could
# not start because the run before it would not stop; and, in the Git common directory, the
# signatures each session has held, so that a failure goes to the model once in a session.
RUN = f"{STATE}-run"
RUN_LOCK = f"{RUN}.lock"
STUCK = f"{STATE}-stuck"
HELD = f"{STATE}-held"
# The seconds the codex stop entry gives the harness, and the part of them the stop spends
# reading the tree; the run reads it again with its own budget.
STOP_TIMEOUT = 30
STOP_READ_SECONDS = 20
# The seconds a claude-code wake entry's `timeout` adds to the run's limit, so that the run always
# ends itself first and the harness's end is a backstop; and the age past its limit at which a run
# record with no end reads as a run that died.
WAKE_MARGIN = 60
# The seconds a run waits for the lock once it has asked the run on another tree to stop: the
# margin the time limit gives a command's stop.
SUPERSEDE_SECONDS = 30
# How often a run asks for the lock while it waits.
LOCK_POLL = 0.05
# The kinds of a checked-tree record: a check of a tree the commands left as they found it, or
# the results of a run whose tree changed before it ended, which never reads as checked and
# serves only as the baseline of a turn that began on that tree. No record before the
# constant-time stop names a kind, and an absent kind reads as a check; the word "checked" is the
# decision brief's mark key, which no other engine module names.
CHECKED, CHANGED = "check", "changed"
# Why a tree changed under a run: no session moved it (Done, or something outside the session,
# writes into the tree), or a run on a later tree superseded it.
OUTSIDE, SUPERSEDED = "outside", "superseded"
# How a run's holding failure stands: new, with no record of the tree the turn began with to tell,
# found again after the session recorded it and never delivered it, or already held once in the
# session.
NEW, NOBASE, AGAIN, HELD_BEFORE = "new", "nobase", "again", "held-before"
# How a run ended, besides its verdict: the turn changed nothing, the tree had a record, it
# followed the run on its tree.
UNCHANGED, RECORDED, FOLLOWED = "unchanged", "recorded", "followed"
# The kinds of notice the `told` file keys, beside the verdicts.
RUNNING, DEAD, STUCK_KIND, ERROR, SLOW, DIGEST_KIND, KNOWN_KIND, PAUSED_KIND, UNHELD = (
    "running",
    "dead",
    "stuck",
    "error",
    "slow",
    "digest",
    "known",
    "paused",
    "unheld",
)
# The note a run ends with where a failure held but the held list could not be written, so the
# hold went to the person and not to the model; and why the person is told it.
UNHELD_NOTE = "not held: the list of failures this session was held for could not be written"
# The note a run that ran no Done ends with where it delivered the tree's failure to the model.
DELIVERED_NOTE = "its failure was held for the agent"
UNHELD_WHY = (
    "the list of failures this session was held for could not be written, so a hold could not "
    "be kept to once"
)
# What starts the engine again for the detached run, isolated as the launcher starts it.
LAUNCH = (
    "import runpy, sys; sys.path.insert(0, sys.argv[1]); "
    "sys.argv = ['outcomebound', *sys.argv[2:]]; "
    "runpy.run_module('outcomebound_tools', run_name='__main__', alter_sys=True)"
)
ENGINE_ROOT = Path(__file__).resolve().parent.parent
# The lines of a failure without failure ids that its signature reads.
SIGNATURE_LINES = 20
HEX_RUN = re.compile(r"[0-9A-Fa-f]{8,}")
DIGIT_RUN = re.compile(r"[0-9]+")
# The seconds the entry gives the verb: 30 is the documented default of `UserPromptSubmit` on
# claude-code (research harnesses/claude-code.md §7.3), written out so that both rows carry it;
# the tree is read within the first 20 of them.
MARK_TIMEOUT = 30
MARK_SECONDS = 20
EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
STDIN_LIMIT = 16 * 1024 * 1024
TAIL_BYTES = 64 * 1024
COMMAND_SHOWN = 200
# Why each row without a finish hook has none yet, by row; any other is `OTHER`.
UNAVAILABLE = {
    "gemini": "a hook exists, but it is not built here yet",
    "cursor": "a follow-up message, not a hold, and CLI support undocumented",
    "amp": "plugin or extension only",
    "pi": "plugin or extension only",
    "generic": "no hook",
}
OTHER = "no finish hook is recorded for it"
# A report that a row's harness may not run the entry, which the install report names.
CAUTION = {"codex": "an open report, openai/codex#17532, says project hooks may not fire"}
# What a row's harness does with an entry adopt has changed, which the install report names: its
# documentation says it skips a new or changed hook until a person trusts it again (research
# harnesses/codex.md §7.1). claude-code reviews no changed entry.
REVIEW_AGAIN = {
    "codex": "Codex skips a new or changed hook until it is trusted, and trust is kept against "
    "the hook's hash, so each person trusts the changed entry again in /hooks"
}
PASS, FAIL, UNVERIFIED = "PASS", "FAIL", "UNVERIFIED"
ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)?")
CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")
DIGEST = re.compile(r"[0-9a-f]{64}")

Verdict = dict[str, str]


# --- What adopt writes -----------------------------------------------------------


def hook_of(row: object) -> dict[str, Any] | None:
    """The row's `finish_hook`, or None where the row has none."""

    hook = row.get("finish_hook") if isinstance(row, dict) else None
    return hook if isinstance(hook, dict) else None


def unavailable(name: str) -> str:
    """Why `name` has no finish check yet, in one clause."""

    return UNAVAILABLE.get(name, OTHER)


def done_digest(done: Sequence[str], skip: Mapping[str, Sequence[str]] | None = None) -> str:
    """The sha256 of the Done list as canonical JSON, and of the skip where one is declared: the
    entry runs only while it matches, so a skip that changes is a hook that changes."""

    value: object = list(done)
    if skip:
        value = {"done": list(done), "skip": {key: list(skip[key]) for key in sorted(skip)}}
    text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# --- The changes a Done command is not run for (`adopt --done-skip`) -----------------

# Paths a skip that covers every path matches: each kind of name at each depth.
_EVERY_PATH = ("a", "a.b", ".a", "a/b", "a/b/c.d", "a/.b/c", "a/b/c/d/e.f")


def glob_refusal(glob: str) -> str | None:
    """Why `glob` is not a skip glob, or None. A glob is `/`-separated and matched from the
    target's root: `*` and `?` stay inside one segment, a `**` segment matches zero or more."""

    if not glob or glob.startswith("/") or "\\" in glob or "[" in glob:
        return f"{glob!r} is empty, absolute, or holds a backslash or a bracket"
    segments = glob.split("/")
    if any(part in ("", ".", "..") for part in segments):
        return f"{glob!r} holds an empty, `.` or `..` segment"
    if any("**" in part and part != "**" for part in segments):
        return f"{glob!r} holds `**` inside a segment; `**` is a segment of its own"
    return None


def _segments_match(globs: Sequence[str], parts: Sequence[str]) -> bool:
    if not globs:
        return not parts
    if globs[0] == "**":
        return any(_segments_match(globs[1:], parts[index:]) for index in range(len(parts) + 1))
    return (
        bool(parts)
        and fnmatch.fnmatchcase(parts[0], globs[0])
        and _segments_match(globs[1:], parts[1:])
    )


def glob_matches(glob: str, path: str) -> bool:
    """Whether the target-relative `path` matches the skip glob `glob`, case-sensitively."""

    return _segments_match(glob.split("/"), path.split("/"))


def skip_refusal(done: Sequence[str], skip: Mapping[str, Sequence[str]]) -> str | None:
    """Why `skip` cannot go with `done`, or None: each key a Done command, each glob well formed,
    no command's globs together covering every path, and one command always run."""

    for command, globs in skip.items():
        if command not in done:
            return f"--done-skip names {command!r}, which is not a recorded Done command"
        if not globs:
            return f"--done-skip names no glob for {command!r}"
        for glob in globs:
            why = glob_refusal(glob)
            if why is not None:
                return f"--done-skip for {command!r}: {why}"
        if all(any(glob_matches(glob, path) for glob in globs) for path in _EVERY_PATH):
            return f"--done-skip for {command!r} covers every path, so it would never run"
    if all(command in skip for command in done):
        return (
            "--done-skip leaves no Done command that always runs; record the check that those "
            "changes do need (for example the project's documentation check) as a Done command"
        )
    return None


def recorded_skip(target: Path) -> dict[str, list[str]]:
    """The skip the manifest's facts record holds, or none where it is absent or not well formed:
    a skip that fails `skip_refusal` skips nothing, so a hand edit never loosens the check."""

    try:
        document = json.loads((target / MANIFEST).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    artifacts = document.get("artifacts") if isinstance(document, dict) else None
    for record in artifacts if isinstance(artifacts, list) else []:
        if isinstance(record, dict) and record.get("kind") == "block" and record.get("id") == FACTS:
            return skip_of(record.get("done", []), record.get(SKIP_KEY))
    return {}


def skip_of(done: object, value: object) -> dict[str, list[str]]:
    """`value` as a skip for `done`, where it is a well-formed one; else none."""

    if not (isinstance(done, list) and all(isinstance(item, str) for item in done)):
        return {}
    if not isinstance(value, dict) or not all(
        isinstance(key, str)
        and isinstance(globs, list)
        and all(isinstance(glob, str) for glob in globs)
        for key, globs in value.items()
    ):
        return {}
    skip = {key: list(globs) for key, globs in value.items()}
    return skip if skip and skip_refusal(done, skip) is None else {}


def changed_paths(target: Path, base: str, deadline: float | None = None) -> list[str] | None:
    """Each path, relative to the target, that differs from the commit `base` (a deletion and
    each side of a move included) or is untracked and not ignored; None where Git cannot say in
    time, or where a path outside the target changed."""

    prefix = _git(target, "rev-parse", "--show-prefix", deadline=deadline)
    diff = _git(
        target,
        "diff",
        "--name-only",
        "-z",
        "--no-renames",
        "--no-ext-diff",
        base,
        deadline=deadline,
    )
    untracked = _git(
        target, "ls-files", "-z", "--others", "--exclude-standard", "--full-name", deadline=deadline
    )
    if prefix is None or diff is None or untracked is None:
        return None
    lead = os.fsdecode(prefix.strip())
    found: list[str] = []
    for name in (diff + b"\0" + untracked).split(b"\0"):
        path = os.fsdecode(name)
        if not path:
            continue
        if not path.startswith(lead):
            return None
        found.append(path[len(lead) :])
    return found


def skipped_for(
    target: Path,
    done: Sequence[str],
    skip: Mapping[str, Sequence[str]],
    base: str,
    deadline: float | None = None,
) -> tuple[str, ...]:
    """The Done commands this change need not run: each whose skip globs match every changed
    path. None is skipped where nothing changed, where the paths cannot be read in time, where a
    path outside the target changed, or where every command would be."""

    if not skip:
        return ()
    changed = changed_paths(target, base, deadline)
    if not changed:
        return ()
    skipped = tuple(
        command
        for command in done
        if all(any(glob_matches(glob, path) for glob in skip.get(command, ())) for path in changed)
    )
    return () if len(skipped) >= len(done) else skipped


def command(harness: str, digest: str, timeout: int = DEFAULT_TIMEOUT) -> str:
    """The stop entry's command. `--constant-time` changes nothing in this engine: an engine from
    before the constant-time stop refuses it with a usage error rather than run Done under an
    entry it was not written for."""

    return (
        f"outcomebound {ID} --constant-time --harness {harness} --done {digest} --timeout {timeout}"
    )


def mark_command(harness: str, digest: str) -> str:
    return f"outcomebound {ID} --mark --harness {harness} --done {digest}"


def mark_entry(harness: str, digest: str) -> dict[str, Any]:
    """The group adopt adds under the row's turn-start event: it records the tree the turn
    begins with and prints nothing, which a harness would add to the model's context."""

    line = mark_command(harness, digest)
    return {"hooks": [{"type": "command", "command": line, "timeout": MARK_TIMEOUT}]}


_TABLE_WAKE = object()


def wake_of(harness: str) -> dict[str, Any] | None:
    """The row's `wake` field in this engine's harness table: how a run's failure reaches the
    model without a stop waiting for it, or None where a later stop delivers it."""

    try:
        hook = hook_of(adapters.table().get(harness))
    except adapters.AdapterError:
        return None
    wake = hook.get("wake") if hook is not None else None
    return wake if isinstance(wake, dict) else None


def entry(
    harness: str, digest: str, timeout: int = DEFAULT_TIMEOUT, wake: object = _TABLE_WAKE
) -> dict[str, Any]:
    """The group adopt adds under the row's event, in the order it is written. `timeout` is the
    run's limit, which the verb is told. On a row whose delivery is a wake (claude-code's
    `asyncRewake`) the entry runs in the background and is the run itself, and its own
    `timeout` is the limit plus `WAKE_MARGIN`, so that the run ends itself first; on any other
    row (codex) the entry is the stop, which returns within `STOP_TIMEOUT` seconds and starts the
    run detached. `wake` is the row's field where the caller holds its own table."""

    line = command(harness, digest, timeout)
    found = wake_of(harness) if wake is _TABLE_WAKE else wake
    if isinstance(found, dict) and isinstance(found.get("key"), str):
        hook = {"type": "command", "command": line, found["key"]: True}
        return {"hooks": [{**hook, "timeout": timeout + WAKE_MARGIN}]}
    return {"hooks": [{"type": "command", "command": line, "timeout": STOP_TIMEOUT}]}


def limit_of(group: object) -> int | None:
    """The run's limit an entry's command names (`--timeout`), or None where it names none that
    the verb admits: the entry's own `timeout` is the harness's, not the run's."""

    hooks = group.get("hooks") if isinstance(group, dict) else None
    first = hooks[0] if isinstance(hooks, list) and hooks and isinstance(hooks[0], dict) else {}
    words = str(first.get("command", "")).split()
    if "--timeout" not in words or words.index("--timeout") + 1 >= len(words):
        return None
    text = words[words.index("--timeout") + 1]
    value = int(text) if text.isdigit() else None
    return value if admits_timeout(value) else None


def admits_timeout(value: object) -> bool:
    """Whether `value` is a timeout the verb can work within: whole seconds past the margin."""

    return type(value) is int and value > MARGIN_SECONDS


def canonical(value: object) -> bytes:
    """The bytes an entry's record digests: sorted keys, no whitespace."""

    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def marked(value: object, mark: bool = False) -> bool:
    """Whether a group runs this verb, as the turn-start mark where `mark`, else at the stop:
    what makes an entry adopt's where its digest is not."""

    hooks = value.get("hooks") if isinstance(value, dict) else None
    return isinstance(hooks, list) and any(
        isinstance(hook, dict)
        and isinstance(hook.get("command"), str)
        and hook["command"].split()[:2] == ["outcomebound", ID]
        and ("--mark" in hook["command"].split()) == mark
        for hook in hooks
    )


# --- The hook's input and the target ---------------------------------------------


def read_input(stream: IO[bytes] | None) -> dict[str, Any] | None:
    """The hook's JSON input, or None where it cannot be read as an object."""

    try:
        if stream is None or stream.isatty():
            return None
        document = json.loads(stream.read(STDIN_LIMIT).decode("utf-8"))
    except (OSError, ValueError):
        return None
    return document if isinstance(document, dict) else None


# A folder the way Git Bash and Cygwin write it, `/c/work/app` or `/cygdrive/c/work/app`.
_MSYS_DRIVE = re.compile(r"^/(?:cygdrive/)?([A-Za-z])(?:/(.*))?$")


def native_path(given: str, windows: bool | None = None) -> str:
    """`given` as the folder this platform reads: on Windows, a drive written the way Git Bash
    writes it (`/c/work/app`) is `C:/work/app`, which Python would otherwise read as a folder
    `c` on the current drive; elsewhere, and for any other form, `given` as it is."""

    found = _MSYS_DRIVE.match(given)
    if found is None or not (os.name == "nt" if windows is None else windows):
        return given
    return f"{found.group(1).upper()}:/{found.group(2) or ''}"


def find_target(payload: Mapping[str, Any] | None, cwd: Path) -> tuple[Path, bool]:
    """(the target, whether it holds the manifest): the nearest directory holding the manifest
    upward from the input's `cwd`, where the agent works, else from the process's `cwd`; not
    found, the directory searched from. One rule for both rows: a root variable stays where the
    session started when the agent moves into a worktree."""

    given = payload.get("cwd") if payload is not None else None
    start = cwd / native_path(given) if isinstance(given, str) and given else cwd
    for directory in (start, *start.parents):
        if (directory / MANIFEST).is_file():
            return directory, True
    return start, False


SKIP_KEY = "done_skip"


def recorded_done(target: Path) -> list[str] | None:
    """The Done commands the manifest's facts record holds, or None where it cannot be read."""

    try:
        document = json.loads((target / MANIFEST).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    artifacts = document.get("artifacts") if isinstance(document, dict) else None
    for record in artifacts if isinstance(artifacts, list) else []:
        if isinstance(record, dict) and record.get("kind") == "block" and record.get("id") == FACTS:
            done = record.get("done", [])
            if isinstance(done, list) and all(isinstance(item, str) for item in done):
                return list(done)
    return None


# --- The working tree the Done commands were last checked on ----------------------


def _git(target: Path, *arguments: str, deadline: float | None = None) -> bytes | None:
    """One read-only Git command's output, or None; it takes no optional lock, and runs no
    longer than 60 seconds or past `deadline`, a `time.monotonic()` reading."""

    seconds = 60.0 if deadline is None else min(60.0, deadline - time.monotonic())
    if seconds <= 0:
        return None
    try:
        done = subprocess.run(
            [programs.require("git"), *GIT_READ_CONFIGURATION, "-C", str(target), *arguments],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            check=False,
            timeout=seconds,
            env=git_environment({**os.environ, "GIT_OPTIONAL_LOCKS": "0"}),
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return done.stdout if done.returncode == 0 else None


def _content(path: Path) -> bytes:
    """What an untracked path holds, for the tree digest: a link's text, or a file's digest and
    whether it may be executed, since a script that loses its execute bit no longer runs."""

    try:
        if path.is_symlink():
            return b"link " + os.fsencode(os.readlink(path))
        if not path.is_file():
            return b"not a file"
        digest = hashlib.sha256(b"x" if os.access(path, os.X_OK) else b"-")
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
        return digest.digest()
    except OSError:
        return b"unreadable"


def tree_digest(target: Path, digest: str, deadline: float | None = None) -> str | None:
    """A digest of the working tree for this Done digest and this target: the tracked diff
    against HEAD and each untracked file Git does not ignore; None where Git cannot say, or
    where `deadline` passes first. The target is part of it, so two targets in one repository
    never share a pass."""

    head = _git(target, "rev-parse", "--verify", "-q", "HEAD^{tree}", deadline=deadline)
    base = head.strip().decode() if head else EMPTY_TREE
    diff = _git(
        target,
        *("diff", "--binary", "--no-color", "--no-ext-diff", "--no-textconv", base),
        deadline=deadline,
    )
    untracked = _git(target, "ls-files", "-z", "--others", "--exclude-standard", deadline=deadline)
    if diff is None or untracked is None:
        return None
    where = os.fsencode(str(target.resolve()))
    total = hashlib.sha256(f"{digest}\0{base}\0".encode() + where + b"\0")
    total.update(hashlib.sha256(diff).digest())
    for name in sorted(item for item in untracked.split(b"\0") if item):
        if deadline is not None and time.monotonic() > deadline:
            return None
        total.update(name + b"\0" + _content(target / os.fsdecode(name)))
    return total.hexdigest()


# The Git directory of each target this process has asked Git for: one hook process reads many
# files there, and asks Git once.
_GIT_DIRS: dict[str, Path] = {}


def _state(target: Path, deadline: float | None = None, name: str = STATE) -> Path | None:
    """The file `name` in the target's Git directory, or None where Git cannot say in time."""

    found = _GIT_DIRS.get(str(target))
    if found is None:
        directory = _git(target, "rev-parse", "--absolute-git-dir", deadline=deadline)
        if not directory:
            return None
        found = _GIT_DIRS.setdefault(str(target), Path(os.fsdecode(directory.strip())))
    return found / name if name else found


@dataclass(frozen=True)
class Pending:
    """A failure a session's run recorded and no hold delivered: its signature, its command and
    when it was first found. A later run of the session that finds it again holds it."""

    signature: str
    command: str
    first: str

    def document(self) -> dict[str, str]:
        return {"signature": self.signature, "command": self.command, "first": self.first}

    @classmethod
    def of(cls, item: object) -> Pending | None:
        if not isinstance(item, dict):
            return None
        signature, command, first = (item.get(key) for key in ("signature", "command", "first"))
        if not (isinstance(signature, str) and isinstance(command, str) and isinstance(first, str)):
            return None
        return cls(signature, command, first)


@dataclass(frozen=True)
class Checked:
    """A working tree the Done commands ran on, the timeout they ran under, the verdict, and the
    results, which an unchanged tree repeats. `kind` is `CHECKED` where the commands left the
    tree as they found it, `CHANGED` where it changed before the run ended (`cause` says why
    where it is known): such a record is never a check, and serves only as the baseline of a
    turn that began on its tree. The rest is what a later stop delivers from it: the session
    whose run wrote it, when, the signature of the failure that holds and how it stands, the
    failures the session recorded and never delivered, the time of the mark the run compared
    with, and whether its input had the guard set or the session paused."""

    tree: str
    timeout: int
    verdict: str
    results: tuple[Result, ...] = ()
    kind: str = CHECKED
    session: str | None = None
    time: str = ""
    seconds: float = 0.0
    cause: str = ""
    holding: str = ""
    hold: str = ""
    first: str = ""
    pending: tuple[Pending, ...] = ()
    marked: str = ""
    guarded: bool = False
    paused: bool = False
    skipped: tuple[str, ...] = ()

    def document(self) -> dict[str, Any]:
        return {
            "tree": self.tree,
            "timeout": self.timeout,
            "verdict": self.verdict,
            "results": [result.document() for result in self.results],
            "kind": self.kind,
            "session": self.session,
            "time": self.time,
            "seconds": self.seconds,
            "cause": self.cause,
            "holding": self.holding,
            "hold": self.hold,
            "first": self.first,
            "pending": [item.document() for item in self.pending],
            "marked": self.marked,
            "guarded": self.guarded,
            "paused": self.paused,
            "skipped": list(self.skipped),
        }

    def text(self) -> str:
        return json.dumps(self.document(), ensure_ascii=False) + "\n"

    def repeats(self, tree: str | None, timeout: int) -> bool:
        """Whether a turn end on `tree` under `timeout` repeats this verdict without running: a
        check of the same tree, not one the hook's environment could not run, and for a verdict
        other than a pass the same timeout, since a longer one may let a command finish."""

        return (
            self.kind == CHECKED
            and self.cause != ENVIRONMENT
            and tree == self.tree
            and (self.verdict == PASS or timeout == self.timeout)
        )


def _checked(document: object) -> Checked | None:
    """One record as `Checked.document` wrote it, or None; a record an engine before the
    constant-time stop wrote has none of the fields after `results`."""

    if not isinstance(document, dict):
        return None
    try:
        tree, timeout = document["tree"], document["timeout"]
        verdict, items = document["verdict"], list(document["results"])
    except (KeyError, TypeError):
        return None
    results = tuple(result for result in map(Result.of, items) if result is not None)
    if not (isinstance(tree, str) and DIGEST.fullmatch(tree) and admits_timeout(timeout)):
        return None
    if verdict not in (PASS, FAIL, UNVERIFIED) or len(results) != len(items):
        return None
    kind = document.get("kind", CHECKED)
    if kind not in (CHECKED, CHANGED):
        return None
    if kind == CHECKED and verdict != PASS and verdict not in {r.verdict for r in results}:
        return None
    texts = ("time", "cause", "holding", "hold", "first", "marked")
    found = {key: document.get(key, "") for key in texts}
    session, seconds = document.get("session"), document.get("seconds", 0.0)
    flags = {key: document.get(key, False) for key in ("guarded", "paused")}
    listed = document.get("pending", [])
    pending = [Pending.of(item) for item in listed] if isinstance(listed, list) else [None]
    skipped = document.get("skipped", [])
    if not (isinstance(skipped, list) and all(isinstance(item, str) for item in skipped)):
        return None
    if not (
        all(isinstance(value, str) for value in found.values())
        and (session is None or isinstance(session, str))
        and isinstance(seconds, (int, float))
        and not isinstance(seconds, bool)
        and all(isinstance(value, bool) for value in flags.values())
        and all(item is not None for item in pending)
    ):
        return None
    return Checked(
        tree,
        int(timeout),
        str(verdict),
        results,
        kind,
        session,
        seconds=float(seconds),
        pending=tuple(item for item in pending if item is not None),
        skipped=tuple(skipped),
        **found,
        **flags,
    )


def parse_records(text: str) -> list[Checked] | None:
    """The records `remember` wrote, newest first, or None where the file cannot be read as
    them; a file holding one record, or only a tree digest, as 1.0.0 wrote it (a pass under the
    default timeout), is a list of one."""

    text = text.strip()
    if DIGEST.fullmatch(text):
        return [Checked(text, DEFAULT_TIMEOUT, PASS)]
    try:
        document = json.loads(text)
    except ValueError:
        return None
    items = document.get("records") if isinstance(document, dict) else None
    if not isinstance(items, list):
        one = _checked(document)
        return [one] if one is not None else None
    parsed = [_checked(item) for item in items]
    kept = [record for record in parsed if record is not None]
    return kept if kept and len(kept) == len(parsed) else None


def parse_checked(text: str) -> Checked | None:
    """The newest record `remember` wrote, or None where it cannot be read as one."""

    records = parse_records(text)
    return records[0] if records else None


def _records_of(target: Path, deadline: float | None = None) -> list[Checked]:
    state = _state(target, deadline)
    try:
        return (parse_records(state.read_text(encoding="utf-8")) or []) if state else []
    except (OSError, ValueError):
        return []


def last_checked(target: Path, deadline: float | None = None) -> Checked | None:
    """The newest record: the tree a run last ended on."""

    records = _records_of(target, deadline)
    return records[0] if records else None


def checked_for(target: Path, tree: str | None, deadline: float | None = None) -> Checked | None:
    """The record of `tree`, of any age the file keeps, or None."""

    if tree is None:
        return None
    return next((r for r in _records_of(target, deadline) if r.tree == tree), None)


def remember(
    target: Path, checked: Checked, deadline: float | None = None, keep: str | None = None
) -> None:
    """Keep `checked` as the newest record, and beside it the record of the tree `keep` names,
    where it differs: the tree the run's turn began on, which the turn's retry still compares
    with. Every other record goes. A Git directory that cannot take it, or one `deadline`
    passes before it is found, is left."""

    state = _state(target, deadline)
    if state is None:
        return
    kept = [checked]
    if keep is not None and keep != checked.tree:
        kept += [record for record in _records_of(target, deadline) if record.tree == keep][:1]
    document = {"records": [record.document() for record in kept]}
    write_whole(state, json.dumps(document, ensure_ascii=False) + "\n")


@dataclass(frozen=True)
class Mark:
    """The commit and the working tree a turn began with, the session that wrote them and when,
    and when the turn ended, where it has: a stamped mark stays until the next prompt writes the
    next turn's over it."""

    head: str
    tree: str
    session: str
    written: datetime
    ended: datetime | None = None

    def clock(self) -> str:
        """The time of day it was written, as the person's clock reads it."""

        return self.written.astimezone().strftime("%H:%M:%S")

    def document(self) -> dict[str, Any]:
        found = {
            "head": self.head,
            "tree": self.tree,
            "session": self.session,
            "time": self.written.isoformat(),
        }
        return found | ({"ended": self.ended.isoformat()} if self.ended else {})

    def same(self, other: Mark | None) -> bool:
        """Whether `other` is this turn's mark, stamped or not."""

        return other is not None and (self.head, self.tree, self.session, self.written) == (
            other.head,
            other.tree,
            other.session,
            other.written,
        )


def clock_of(text: str) -> str:
    """The time of day a UTC-offset time names, as the person's clock reads it, or the text."""

    when = stamp(text)
    return when.astimezone().strftime("%H:%M:%S") if when is not None else text


def now_text() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_whole(path: Path, text: str) -> bool:
    """Write `text` as the whole of `path`: to a file beside it, renamed over it, so that a
    reader sees the old file or the new one and never a part. Whether it was written. Windows
    refuses a rename over a file another process holds open for a moment; the rename is tried
    again then."""

    stage = path.with_name(f"{path.name}.{os.getpid()}.{threading.get_ident()}")
    try:
        stage.write_text(text, encoding="utf-8")
    except OSError:
        stage.unlink(missing_ok=True)
        return False
    for _ in range(4):
        if _renamed(stage, path):
            return True
        time.sleep(0.05)
    if _renamed(stage, path):
        return True
    stage.unlink(missing_ok=True)
    return False


def _renamed(stage: Path, path: Path) -> bool:
    try:
        os.replace(stage, path)
    except OSError:
        return False
    return True


def stamp(text: object) -> datetime | None:
    """A UTC-offset time as a transcript or a mark writes it, or None."""

    if not isinstance(text, str):
        return None
    try:
        when = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return when if when.tzinfo is not None else None


def read_mark(target: Path, deadline: float | None = None) -> Mark | None:
    """The mark the turn's first prompt wrote, or None: none written (an older install, a
    harness without the event), or unreadable."""

    path = _state(target, deadline, MARK)
    if path is None:
        return None
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
        head, tree = document["head"], document["tree"]
        session, written = document["session"], stamp(document["time"])
        ended = stamp(document["ended"]) if "ended" in document else None
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None
    if not (isinstance(head, str) and HEAD.fullmatch(head) and isinstance(tree, str)):
        return None
    if not (isinstance(session, str) and session and written is not None):
        return None
    if "ended" in document and ended is None:
        return None
    return Mark(head, tree, session, written, ended) if DIGEST.fullmatch(tree) else None


def prompt_input(row: Any, payload: dict[str, Any] | None) -> str | None:
    """The session id of a turn-start hook's input, or None where `payload` is not that input:
    the event the row documents named, and a session id. A mark written on any other input,
    such as the agent running the verb itself, is refused."""

    hook = hook_of(row)
    if payload is None or hook is None or payload.get("hook_event_name") != hook["mark_event"]:
        return None
    session = payload.get("session_id")
    return session if isinstance(session, str) and session else None


def begin_turn(
    digest: str,
    payload: dict[str, Any] | None,
    cwd: Path,
    session: str,
    deadline: float | None = None,
) -> tuple[Path, str | None] | None:
    """Keep the target's HEAD and tree as the turn's start, in the Git directory, with the
    session and the time, over a mark the last turn's end stamped. Where the HEAD or tree cannot
    be read in time, the mark of the turn before goes, so that no turn is compared with a tree
    it did not begin with. (the target, the tree it read, None where it kept the turn's mark and
    read none) where there is a target; errors are the caller's to swallow, and nothing is
    printed. `deadline` is the entry's, `MARK_SECONDS` from now by default."""

    deadline = time.monotonic() + MARK_SECONDS if deadline is None else deadline
    target, found = find_target(payload, cwd)
    path = _state(target, deadline, MARK) if found else None
    if path is None:
        return None
    live = read_mark(target, deadline)
    if live is not None and live.session == session and live.ended is None:
        # A prompt inside the turn (a queued message, or the prompt a codex hold creates): the
        # turn's first mark stays, since this tree holds the turn's edits.
        return target, None
    head, tree = _head(target, deadline), tree_digest(target, digest, deadline)
    if head is None or tree is None:
        path.unlink(missing_ok=True)
        return target, None
    mark = Mark(head, tree, session, datetime.now(timezone.utc))
    write_whole(path, json.dumps(mark.document()) + "\n")
    return target, tree


def stamp_mark(target: Path, mark: Mark, deadline: float | None = None) -> None:
    """Stamp `mark` ended, where it is still the mark on file and not stamped: the turn it
    began has ended. A mark the next prompt wrote meanwhile is left as it is."""

    path = _state(target, deadline, MARK)
    now = read_mark(target, deadline)
    if path is None or now is None or not mark.same(now) or now.ended is not None:
        return
    stamped = replace(now, ended=datetime.now(timezone.utc))
    write_whole(path, json.dumps(stamped.document()) + "\n")


# Text the harness writes into a `user` line of its own accord: a slash command's echo and
# output, an interrupt, and a task notification; none is a person's prompt.
HARNESS_TEXT = ("<command-name>", "<local-command-", "[Request interrupted", "<task-notification")


def _person_wrote(line: dict[str, Any]) -> bool:
    """Whether a claude-code `user` line is what the harness writes for a person's prompt: not
    a tool result, meta, side-chain, compaction summary or system-origin line, and no text the
    harness writes itself. Only the line's keys and the opening of its text are read."""

    message = line.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if line.get("isMeta") or line.get("isCompactSummary") or line.get("promptSource") == "system":
        return False
    if "toolUseResult" in line or "sourceToolAssistantUUID" in line:
        return False
    origin = line.get("origin")
    if isinstance(origin, dict) and origin.get("kind") != "human":
        return False
    blocks = content if isinstance(content, list) else [{"type": "text", "text": content}]
    if any(isinstance(block, dict) and block.get("type") == "tool_result" for block in blocks):
        return False
    texts = [b.get("text") for b in blocks if isinstance(b, dict) and b.get("type") == "text"]
    return not any(isinstance(text, str) and text.startswith(HARNESS_TEXT) for text in texts)


def _kind(harness: str, line: object) -> str | None:
    """What a transcript line is for the order check: `prompt` where it begins a turn, `work`
    where the model or a tool has acted since. Only the shape of a line is read, never its
    text. claude-code: a `user` line a person's prompt writes (`_person_wrote`); an `assistant`
    line. codex: an `event_msg` `task_started`; any `response_item` but a user or developer
    message."""

    if not isinstance(line, dict) or line.get("isSidechain") is True:
        return None
    kind, inner = line.get("type"), line.get("payload")
    if harness == "claude-code":
        if kind == "assistant":
            return "work"
        return "prompt" if kind == "user" and _person_wrote(line) else None
    if not isinstance(inner, dict):
        return None
    if kind == "event_msg":
        return "prompt" if inner.get("type") == "task_started" else None
    if kind == "response_item":
        user = inner.get("type") == "message" and inner.get("role") in ("user", "developer")
        return None if user else "work"
    return None


def first_work(harness: str, path: Path, deadline: float) -> datetime | None:
    """When the model or a tool first acted after the last prompt of the transcript at `path`;
    None where it cannot be read or parsed, names no such prompt or no such work, or `deadline`
    passes first."""

    began = False
    found: datetime | None = None
    try:
        with path.open("rb") as handle:
            for number, raw in enumerate(handle):
                if number % 256 == 0 and time.monotonic() > deadline:
                    return None
                if not raw.strip():
                    continue
                line = json.loads(raw)
                kind = _kind(harness, line)
                if kind == "prompt":
                    began, found = True, None
                elif kind == "work" and began and found is None:
                    found = stamp(line.get("timestamp"))
                    if found is None:
                        return None
    except (OSError, ValueError):
        return None
    return found


def trusted(harness: str, mark: Mark, payload: dict[str, Any] | None, deadline: float) -> bool:
    """Whether the stop may use `mark`: it was written for this session, and, where the input
    names the session's transcript, before the model or a tool first acted in this turn. A
    transcript that cannot be read or parsed makes it no mark. A row whose stop input names no
    transcript gets the session check alone."""

    if payload is None or payload.get("session_id") != mark.session:
        return False
    name = payload.get("transcript_path")
    if name is None or name == "":
        return True
    if not isinstance(name, str):
        return False
    first = first_work(harness, Path(name), deadline)
    return first is not None and mark.written < first


# --- The failures that were there before the change -------------------------------

# How each runner names a failing test or target in its own summary lines, one pattern per
# runner, matched against each line of a command's kept output, terminal escapes stripped. A
# command whose output matches none yields no failure ids, and its exit code alone decides.
FAILURE_IDS: tuple[tuple[str, re.Pattern[str]], ...] = (
    # A pytest node id runs to pytest's " - " before the message, or to the end of the line, so
    # a parametrize id with a space in it stays whole.
    ("pytest", re.compile(r"^(?:FAILED|ERROR) (.+?)(?: - .*)?$")),
    # The whole rest of a unittest line, so a subtest's "(i=1)" stays part of the id.
    ("unittest", re.compile(r"^(?:FAIL|ERROR): (.+)$")),
    ("go", re.compile(r"^\s*--- FAIL: (\S+)")),
    ("cargo", re.compile(r"^test (\S+) \.\.\. FAILED$")),
    # The marks jest and vitest print before a failing test: ✕, the multiplication sign, ✗.
    ("jest", re.compile(r"^\s*[\u2715\u00d7\u2717] (.+?)(?: \(?\d+(?:\.\d+)? ?m?s\)?)?$")),
    ("make", re.compile(r"^g?make(?:\[\d+\])?: \*\*\* \[(.+?)\] Error \d+$")),
)
HEAD = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})?")


def failure_ids(output: bytes) -> frozenset[str]:
    """The failing tests or targets a command's output names in a runner's summary lines, each
    as `<runner> <id>`; none where no line matches."""

    found: set[str] = set()
    for line in clean(output).split("\n"):
        for runner, pattern in FAILURE_IDS:
            match = pattern.match(line)
            if match:
                found.add(f"{runner} {match.group(1)}")
    return frozenset(found)


# Who named a failure's ids, in the words of a note: adopt when it measured Done, or the tree a
# turn began with.
BY_ADOPT = "adopt measured"
BY_TURN = "the tree at the start of this turn held"


@dataclass(frozen=True)
class Failure:
    """A Done command's failure when adopt measured Done, or on the tree a turn began with: its
    exit code, and the failure ids its output named, None where it named none."""

    code: int
    ids: frozenset[str] | None = None

    def tolerates(self, result: Result, by: str = BY_ADOPT) -> tuple[bool, str]:
        """(whether `result` is this failure again, why): the same exit code, and where either
        side names failure ids, ids that are all among the recorded ones; `by` says who named
        them."""

        if result.verdict != FAIL or result.code != self.code:
            return False, ""
        if not result.ids_complete:
            return False, (
                f"not known: the scan for failure ids stopped at {MAX_IDS} ids or the time limit "
                "before its output ended, so a new id after that point would not be seen"
            )
        now = result_ids(result)
        if self.ids is None and not now:
            return True, "known by its exit code only, since its output names no failure ids"
        if self.ids is None:
            return False, f"not known: its output now names failure ids, and {by} none"
        if not now:
            return False, f"not known: its output names none of the failure ids {by}"
        new = sorted(now - self.ids)
        if new:
            shown = ", ".join(shorten(item, 80) for item in new[:5])
            more = f" and {len(new) - 5} more" if len(new) > 5 else ""
            return False, f"not known: new failure ids {shown}{more}"
        return True, "known by its failure ids"


@dataclass(frozen=True)
class Known:
    """The Done commands that failed when adopt last measured them on commit `head` (empty on a
    branch with no commit), each with its `Failure`, for one Done digest and one target, named by
    its place in the work tree (`git rev-parse --show-prefix`); with the day and the seconds
    that measurement took."""

    done: str
    prefix: str
    head: str
    measured: str
    seconds: float
    failing: dict[str, Failure]
    # Whether the measurement ran as a hook runs Done (`hook_environment`); a record an engine
    # before that wrote, with the PATH of the agent that ran adopt, holds no such mark.
    as_hook: bool = False

    def document(self) -> dict[str, Any]:
        failing = {
            line: {"code": item.code, "ids": None if item.ids is None else sorted(item.ids)}
            for line, item in self.failing.items()
        }
        return {
            "done": self.done,
            "prefix": self.prefix,
            "head": self.head,
            "measured": self.measured,
            "seconds": self.seconds,
            "failing": failing,
            "as_hook": self.as_hook,
        }

    def key(self) -> tuple[str, str, str]:
        return self.done, self.prefix, self.head


def _failure(item: object) -> Failure | None:
    """A recorded failure: `{code, ids}`, or a bare exit code, read as naming no ids."""

    if type(item) is int:
        return Failure(item)
    if not isinstance(item, dict) or type(item.get("code")) is not int:
        return None
    ids = item.get("ids")
    if ids is None:
        return Failure(item["code"])
    if not isinstance(ids, list) or not all(isinstance(one, str) for one in ids):
        return None
    return Failure(item["code"], frozenset(ids))


def _known(document: object) -> Known | None:
    if not isinstance(document, dict):
        return None
    done, prefix, head = document.get("done"), document.get("prefix"), document.get("head")
    measured, seconds, failing = (document.get(k) for k in ("measured", "seconds", "failing"))
    if not (
        isinstance(done, str)
        and DIGEST.fullmatch(done)
        and isinstance(prefix, str)
        and isinstance(head, str)
        and HEAD.fullmatch(head)
        and isinstance(measured, str)
        and isinstance(seconds, (int, float))
        and not isinstance(seconds, bool)
        and isinstance(failing, dict)
    ):
        return None
    items = {line: _failure(item) for line, item in failing.items()}
    kept = {line: item for line, item in items.items() if item is not None}
    if len(kept) != len(items):
        return None
    return Known(
        done, prefix, head, measured, float(seconds), kept, document.get("as_hook") is True
    )


def parse_known(text: str) -> list[Known] | None:
    """The records `keep_known` wrote, or None where the file cannot be read as them."""

    try:
        document = json.loads(text)
    except ValueError:
        return None
    records = document.get("records") if isinstance(document, dict) else None
    if not isinstance(records, list):
        return None
    parsed = [_known(item) for item in records]
    kept = [record for record in parsed if record is not None]
    return kept if len(kept) == len(parsed) else None


def _known_path(target: Path, deadline: float | None = None) -> tuple[Path, str] | None:
    """(the records' path in the Git common directory, the target's prefix), or None."""

    common = _git(target, "rev-parse", "--git-common-dir", deadline=deadline)
    prefix = _git(target, "rev-parse", "--show-prefix", deadline=deadline)
    if not common or prefix is None:
        return None
    # Git can return a path relative to the command's cwd, including in a subdirectory.
    # Resolve it here instead of requiring Git's newer --path-format option.
    try:
        folder = (target / os.fsdecode(common.strip())).resolve(strict=True)
        if not folder.is_dir():
            return None
    except (OSError, ValueError):
        return None
    return folder / KNOWN, os.fsdecode(prefix.strip())


def _head(target: Path, deadline: float | None = None) -> str | None:
    """The target's HEAD commit; empty on a branch with no commit; None where Git cannot say."""

    if _git(target, "rev-parse", "--absolute-git-dir", deadline=deadline) is None:
        return None
    head = _git(target, "rev-parse", "--verify", "-q", "HEAD^{commit}", deadline=deadline)
    return head.strip().decode() if head else ""


def _records(path: Path) -> list[Known]:
    try:
        return parse_known(path.read_text(encoding="utf-8")) or []
    except (OSError, ValueError):
        return []


def known_record(target: Path, digest: str, deadline: float | None = None) -> Known | None:
    """The newest record for this Done digest and this target whose commit is in the history of
    the target's HEAD, or None: none kept, unreadable, or measured on a commit this checkout does
    not descend from, where a failure it names may be new here."""

    found = _known_path(target, deadline)
    if found is None:
        return None
    path, prefix = found
    candidates = [r for r in _records(path) if r.done == digest and r.prefix == prefix]
    if not candidates:
        return None
    head = _head(target, deadline)
    for record in reversed(candidates):
        if head is None:
            return None
        if not record.head or not head:
            if record.head == head:
                return record
            continue
        merge = ("merge-base", "--is-ancestor", record.head, "HEAD")
        if _git(target, *merge, deadline=deadline) is not None:
            return record
    return None


def keep_known(target: Path, record: Known, deadline: float | None = None) -> bool:
    """Keep `record` beside the others, its prefix the target's; whether it was kept. It replaces
    the record for its Done digest, target and commit, and the target's records for another Done
    list or for a commit its own descends from, which it supersedes."""

    found = _known_path(target, deadline)
    if found is None:
        return False
    path, prefix = found
    record = replace(record, prefix=prefix)

    def superseded(other: Known) -> bool:
        if other.prefix != prefix:
            return False
        if other.done != record.done or other.head == record.head:
            return True
        if not other.head or not record.head:
            return False
        merge = ("merge-base", "--is-ancestor", other.head, record.head)
        return _git(target, *merge, deadline=deadline) is not None

    records = [other for other in _records(path) if not superseded(other)] + [record]
    text = json.dumps({"records": [r.document() for r in records]}, ensure_ascii=False) + "\n"
    stage = path.with_name(f"{KNOWN}.{os.getpid()}")
    try:
        stage.write_text(text, encoding="utf-8")
        os.replace(stage, path)
    except OSError:
        stage.unlink(missing_ok=True)
        return False
    return True


# --- Running the Done commands ---------------------------------------------------


# Why a command reads UNVERIFIED: it met the time limit, it could not run where the hook runs, or
# it failed once and ended another way on a second run in the same environment (a possible flake).
TIME, ENVIRONMENT, FLAKE = "time", "environment", "flake"
# A tool the command names that this PATH does not hold, as the last line of output says it when a
# runner between the hook and the tool turns the shell's 127 into its own exit code: make's
# `make: pytest: No such file or directory`, a script's `run.sh: line 3: pytest: command not
# found` or `run.sh: 3: pytest: not found`, a shell's `sh: pytest: command not found` or, for
# busybox, `sh: pytest: not found`, and a Python launcher's `python3: No module named pytest`.
# A test's own message (`FileNotFoundError: [Errno 2] No such file or directory: 'x'`,
# `ModuleNotFoundError: No module named 'x'`) has no such form. make's own
# `make: *** [test] Error 1` lines after it are passed over.
_MISSING = re.compile(
    r"^(?:make(?:\[\d+\])?: (?P<made>[^\s:]+): No such file or directory"
    r"|process_begin: CreateProcess\(NULL, (?P<winmade>[^\s,]+),?(?: .*)?\) failed\."
    r"|\S+: (?:line )?\d+: (?P<scripted>.+?): "
    r"(?:(?:command )?not found|No such file or directory|Permission denied)"
    r"|(?:\S*/)?(?:ba|da|z|a)?sh: (?P<shelled>.+?): "
    r"(?:(?:command )?not found|No such file or directory|Permission denied)"
    r"|(?P<launcher>(?:\S*[/\\])?python[\d.]*(?:\.exe)?): No module named (?P<module>[\w.]+))$"
)
# GNU make on Windows says it in two lines: `process_begin: CreateProcess(NULL, <tool> ...)
# failed.` and `make (e=2): <sentence>`. `e=2` is ERROR_FILE_NOT_FOUND in every language; the
# sentence is localized, so only `e=2` is read (observed on a hosted Windows runner, 2026-10-06).
_MAKE_E2 = re.compile(r"^make(?:\[\d+\])? \(e=2\):")
# make's own lines after the tool's: its error line, and a nested make's directory lines.
_MAKE_ERROR = re.compile(r"^make(?:\[\d+\])?: (?:\*\*\* |(?:Leaving|Entering) directory )")


def _not_found(output: bytes) -> tuple[re.Match[str] | None, list[str]]:
    """The runner's not-found line the output ends in, make's own lines after it aside, and the
    lines before it; None where the output does not end in one."""

    lines = [line.strip() for line in clean(output).splitlines() if line.strip()]
    while lines and _MAKE_ERROR.match(lines[-1]):
        lines.pop()
    if len(lines) >= 2 and _MAKE_E2.match(lines[-1]):
        found = _MISSING.match(lines[-2])
        if found is not None and found["winmade"]:
            return found, lines[:-2]
        return None, lines[:-1]
    found = _MISSING.match(lines[-1]) if lines else None
    if found is not None and found["winmade"]:
        return None, lines[:-1]
    return found, lines[:-1]


def _tool_named(found: re.Match[str]) -> str:
    return (
        found["made"]
        or found["winmade"]
        or found["scripted"]
        or found["shelled"]
        or found["launcher"]
        or ""
    )


def _quiet_before(found: re.Match[str], before: Sequence[str]) -> bool:
    """Whether the lines before a not-found line are only make's directory lines and the echo of a
    command that starts with the missing tool."""

    tool = _tool_named(found)
    for line in before:
        echoed = line.split(" ", 1)[0] in (tool, Path(tool).name)
        if not (echoed or _MAKE_ERROR.match(line)):
            return False
    return True


def _missing_line(output: bytes) -> re.Match[str] | None:
    """The runner's not-found line, where it is the command's only word: the last line, make's
    own lines after it aside, with nothing before it but make's directory lines and the echo of a
    command that starts with the missing tool. Output before it means something else ran, and a
    missing last tool does not show that it passed."""

    found, before = _not_found(output)
    return found if found is not None and _quiet_before(found, before) else None


def ran_before_missing(output: bytes) -> bool:
    """Whether the output ends in a not-found line that other output precedes: something else
    ran, so a missing last tool, even at exit 126 or 127, is not the command's only word."""

    found, before = _not_found(output)
    return found is not None and not _quiet_before(found, before)


def missing_tool(output: bytes) -> str | None:
    """The tool a failing command's last line of output says this PATH does not hold, as the
    command line names it (`pytest`, or `python -m pytest`), or None."""

    found = _missing_line(output)
    if found is None:
        return None
    if found["module"]:
        return f"python -m {found['module']}"
    return _tool_named(found)


# Exit code of the probe that finds a module missing; any other non-zero exit says nothing.
_NO_MODULE = 3


def confirmed_absent(
    target: Path,
    output: bytes,
    environment: Mapping[str, str] | None = None,
    *,
    deadline: float | None = None,
) -> bool:
    """Whether the tool the last line names is in fact absent where the command ran, and not only
    said to be: a name `programs.find` does not find on that PATH, or a module the named Python
    launcher cannot find. A command can print the line itself; then the tool is there, and the
    failure stands."""

    found = _missing_line(output)
    if found is None:
        return False
    # Done runs from the target's root, so an empty or relative entry names a folder of it.
    source = environment if environment is not None else os.environ
    entries = programs.environment_value(source, "PATH")
    if entries is None:
        # A shell can supply its own default PATH. Absence on an unknown child
        # PATH is not established; an absolute Python launcher can still probe.
        if not found["module"] or not _folder_in(found["launcher"]):
            return False
        entries = ""
    path = os.pathsep.join(str((target / entry).resolve()) for entry in entries.split(os.pathsep))
    # What the shell could find: on Windows a script with no extension, which Git's shell runs.
    where = {"PATH": path}
    # What a Windows lookup reads besides PATH: the extensions to try, and the system folder.
    carried = ("PATHEXT", "SYSTEMROOT")
    where |= {key: value for key, value in source.items() if key.upper() in carried}
    if not found["module"]:
        tool = _tool_named(found)
        if _folder_in(tool):
            # A name with a folder is looked up as it stands, from the target's root.
            path_tool = target / tool
            denied = found.group(0).endswith("Permission denied")
            return not path_tool.is_file() or (denied and not os.access(path_tool, os.X_OK))
        return programs.find(tool, where, extensionless=True) is None
    launcher = found["launcher"]
    program = launcher if _folder_in(launcher) else programs.find(launcher, where)
    if program is None or not Path(program).exists():
        # A launcher that is not there would have failed before it could print the line, so
        # the line is the command's own text, not a launcher's word.
        return False
    probe = (
        "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec(sys.argv[1]) else 3)"
    )
    top = found["module"].split(".")[0]
    seconds = 30.0 if deadline is None else min(30.0, deadline - time.monotonic())
    if seconds <= 0:
        return False
    try:
        done = subprocess.run(
            [program, "-c", probe, top],
            cwd=target,
            env=environment,
            capture_output=True,
            timeout=seconds,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return done.returncode == _NO_MODULE


# A runner's word that something else in the same command failed: pytest's and similar runners'
# `3 failed`, and make's `Target 'all' not remade because of errors.` after `make -k`.
_MAKE_TARGET = re.compile(r"^g?(make(?:\[\d+\])?): \*\*\* \[.+?\] Error \d+$", re.M)
_OTHER_FAILURE = re.compile(r"\b[1-9]\d* (?:failed|errors?)\b|not remade because of errors")


def other_failure(output: bytes) -> bool:
    """Whether a command's output shows a failure besides a missing tool: failure ids a runner's
    summary names, a count of failed tests, or make's word that a target was not remade."""

    # make's own `*** [target] Error n` lines follow the missing tool itself, so they are not
    # another failure; a second target that failed under `make -k` says "not remade".
    text = clean(output)
    tests = {one for one in failure_ids(output) if not one.startswith("make ")}
    # Two failed targets of one make (`make -k a b`); a nested make's chain puts its lines at
    # different levels (`make[1]: *** [test]`, then `make: *** [all]`).
    levels = [found.group(1) for found in _MAKE_TARGET.finditer(text)]
    return bool(tests) or bool(_OTHER_FAILURE.search(text)) or len(levels) != len(set(levels))


def _folder_in(name: str) -> bool:
    """Whether a program's name holds a folder: `/` anywhere, and `\\` on Windows."""

    return "/" in name or (os.name == "nt" and "\\" in name)


def project_owned(target: Path, tool: str) -> bool:
    """Whether a tool `missing_tool` names is the project's own, so that its absence is the
    work's and not the hook's environment's: a path inside the target, relative or absolute, which
    no PATH resolves (a script the change removed or renamed); a bare name that an executable file
    in the target's HEAD commit carries, which a recipe puts on PATH itself; or a `python -m`
    module whose top package or module is in the target's tree or its HEAD commit, a namespace
    package's folder included."""

    root = target.resolve()
    if _folder_in(tool) and not tool.startswith("python -m "):
        path = Path(tool)
        # On Windows `/opt/x` has a root and no drive: it is not relative, and it names a place
        # of the current drive, not a place inside the target.
        if not (path.is_absolute() or path.root):
            return True
        resolved = path.resolve(strict=False)
        return resolved == root or root in resolved.parents
    listed = _git(target, "ls-tree", "-r", "HEAD")
    entries = [
        line.split("\t", 1) for line in (listed or b"").decode("utf-8", "replace").splitlines()
    ]
    tracked = [(entry[0].split(" ", 1)[0], entry[1]) for entry in entries if len(entry) == 2]
    if not tool.startswith("python -m "):
        return any(mode == "100755" and path.rsplit("/", 1)[-1] == tool for mode, path in tracked)
    top = tool.removeprefix("python -m ").split(".")[0]
    for folder in (target, target / "src"):
        if (folder / top).is_dir() or (folder / f"{top}.py").is_file():
            return True
    # The module's own place: the target's root or `src/`, where a launcher run from the root
    # imports it; a folder of that name deeper in the tree is another thing.
    places = [f"{base}{top}" for base in ("", "src/")]
    return any(
        path in (f"{place}.py" for place in places)
        or any(path.startswith(f"{place}/") for place in places)
        for _, path in tracked
    )


@dataclass(frozen=True)
class Result:
    command: str
    verdict: str
    seconds: float
    why: str = ""
    output: bytes = b""
    cause: str = ""
    # The exit code of a command that ran to its end; whether a FAIL is a known failure; and,
    # for a command with a known failure recorded, why it is known or not.
    code: int | None = None
    known: bool = False
    note: str = ""
    # For a known failure: the commit adopt measured it on.
    commit: str = ""
    # Whether a known failure is one the working tree a turn began with already had.
    before: bool = False
    # The failure ids the command's whole output named, not only its kept tail; and whether the
    # scan read that output to its end, not stopping at `MAX_IDS` or the time limit.
    ids: frozenset[str] = frozenset()
    ids_complete: bool = True

    def line(self) -> str:
        shown = shorten(self.command)
        if self.verdict == PASS:
            return f"PASS {shown} ({self.seconds:.0f} s)"
        if self.known and self.before:
            return (
                f"FAIL {shown}: {self.why}, as on the working tree this turn began with "
                f"({self.note}; known before this turn, not held)"
            )
        if self.known:
            on = f" on commit {self.commit[:12]}" if self.commit else ""
            return (
                f"FAIL {shown}: {self.why}, as when adopt measured Done{on} ({self.note}; not held)"
            )
        if self.note:
            return f"{self.verdict} {shown}: {self.why} ({self.note})"
        return f"{self.verdict} {shown}: {self.why}"

    def document(self) -> dict[str, Any]:
        return {
            "command": self.command,
            "verdict": self.verdict,
            "seconds": self.seconds,
            "why": self.why,
            "output": self.output.decode("utf-8", "replace"),
            "cause": self.cause,
            "code": self.code,
            "known": self.known,
            "note": self.note,
            "commit": self.commit,
            "before": self.before,
            "ids": sorted(self.ids),
            "ids_complete": self.ids_complete,
        }

    @classmethod
    def of(cls, item: object) -> Result | None:
        """The result `document` wrote, or None where `item` is not one; one written before
        `code`, `known` and `note` were kept has none of them."""

        if not isinstance(item, dict):
            return None
        command, verdict, why = item.get("command"), item.get("verdict"), item.get("why")
        output, cause, seconds = item.get("output"), item.get("cause"), item.get("seconds")
        code, known, note = item.get("code"), item.get("known", False), item.get("note", "")
        commit, before = item.get("commit", ""), item.get("before", False)
        listed, complete = item.get("ids", []), item.get("ids_complete", True)
        if not (
            isinstance(command, str)
            and verdict in (PASS, FAIL, UNVERIFIED)
            and isinstance(why, str)
            and isinstance(output, str)
            and isinstance(cause, str)
            and isinstance(seconds, (int, float))
            and not isinstance(seconds, bool)
            and (code is None or type(code) is int)
            and isinstance(known, bool)
            and isinstance(note, str)
            and isinstance(commit, str)
            and isinstance(before, bool)
            and isinstance(listed, list)
            and all(isinstance(one, str) for one in listed)
            and isinstance(complete, bool)
        ):
            return None
        data = output.encode("utf-8")
        return cls(
            command,
            str(verdict),
            float(seconds),
            why,
            data,
            cause,
            code,
            known,
            note,
            commit,
            before,
            frozenset(listed),
            complete,
        )


def result_ids(result: Result) -> frozenset[str]:
    """The failure ids of a result: those found in the command's whole output, and those in the
    tail it kept."""

    return result.ids | failure_ids(result.output)


def shorten(text: str, limit: int = COMMAND_SHOWN) -> str:
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _stop(process: subprocess.Popen[bytes]) -> str:
    """Kill the command's whole process group, on Windows its process tree, so nothing it
    started outlives the limit. Returns the path that ended the tree (`programs.stop_tree`)."""

    way = programs.stop_tree(process)
    process.wait()
    return way


# How a report names the path that stopped a command's tree on Windows, where there are three
# and a stop that leaves a process running needs to say which one it was.
STOPPED_BY = {
    "job": "its job",
    "taskkill": "taskkill",
    "kill": "a kill of the command alone",
}


def _tail(sink: IO[bytes]) -> bytes:
    size = sink.seek(0, os.SEEK_END)
    sink.seek(max(0, size - TAIL_BYTES))
    return sink.read()


MAX_IDS = 2000
LINE_BYTES = 64 * 1024


def _ids_in(sink: IO[bytes], deadline: float | None) -> tuple[frozenset[str], bool]:
    """The failure ids named anywhere in a command's output, read line by line so that memory
    holds the ids and not the text, and whether the scan reached the output's end: it stops at
    `MAX_IDS` ids, or at `deadline`, and then says so."""

    found: set[str] = set()
    sink.seek(0)
    while len(found) < MAX_IDS and (deadline is None or time.monotonic() < deadline):
        line = sink.readline(LINE_BYTES)
        if not line:
            return frozenset(found), True
        found |= failure_ids(line)
    return frozenset(found), sink.read(1) == b""


# The signals that stop a Done run from outside: Ctrl-C, and SIGTERM where adopt maps it.
STOPPING = (signal.SIGINT, signal.SIGTERM)
Handlers = dict[int, Any]


def _hold(held: list[int]) -> Handlers:
    """Record, rather than act on, each stopping signal that arrives from now on, and return the
    handlers to put back. Python acts on a signal between any two steps, so one that arrives after
    the command has started and before `subprocess.Popen` returns would leave no process to stop.
    A signal this process ignores stays ignored, so the command inherits it as before; outside the
    main thread nothing can be held, and nothing is."""

    if threading.current_thread() is not threading.main_thread():
        return {}
    previous: Handlers = {}
    for number in STOPPING:
        handler = signal.getsignal(number)
        if handler is None or handler == signal.SIG_IGN:
            continue
        previous[number] = signal.signal(number, lambda got, frame: held.append(got))
    return previous


def _release(previous: Handlers, held: Sequence[int]) -> None:
    """Put the handlers back, then act on each signal held as its handler would have."""

    for number, handler in previous.items():
        signal.signal(number, handler)
    for number in dict.fromkeys(held):
        handler = previous[number]
        if callable(handler):
            handler(number, None)
        elif handler == signal.SIG_DFL:
            _die(number)


def _die(number: int, windows: bool | None = None) -> NoReturn:
    """End this process as its signal's default action would. Windows has no such action to
    send: `os.kill` there ends the process at once with the signal's number as its exit code,
    never running a `finally`, so a Ctrl-C is the exception Python raises for it and any other
    signal exits with the shell's 128 plus its number."""

    if not (os.name == "nt" if windows is None else windows):
        os.kill(os.getpid(), number)
    if number == signal.SIGINT:
        raise KeyboardInterrupt
    raise SystemExit(128 + number)


def run_one(
    target: Path, line: str, seconds: float | None, environment: Mapping[str, str] | None = None
) -> Result:
    """Run one Done command from the target's root in its own process group, for at most
    `seconds`, None for as long as it takes; its output, both streams, kept for the report. The
    line runs under a POSIX shell: `/bin/sh`, on Windows the `sh.exe` of Git for Windows; where
    there is none the command reads `UNVERIFIED`, unheld. A stopping signal that arrives while
    the command starts is acted on once it has started, so its group is stopped too."""

    started = time.monotonic()
    shell = programs.posix_shell(environment)
    if shell is None:
        why = "could not start: no POSIX shell; install Git for Windows, or put its sh.exe on PATH"
        return Result(line, UNVERIFIED, 0.0, why, cause=ENVIRONMENT)
    environment = programs.shell_environment(shell, environment)
    with tempfile.TemporaryFile() as sink:
        held: list[int] = []
        previous = _hold(held)
        try:
            process = programs.start_tree(
                [shell, "-c", line],
                cwd=target,
                stdin=subprocess.DEVNULL,
                stdout=sink,
                stderr=subprocess.STDOUT,
                env=environment,
            )
        except OSError as error:
            _release(previous, held)
            why = f"could not start: {error.strerror or error}"
            return Result(line, UNVERIFIED, 0.0, why, cause=ENVIRONMENT)
        except BaseException:
            _release(previous, ())
            raise
        try:
            _release(previous, held)
            code = process.wait(timeout=None if seconds is None else max(seconds, 0.0))
        except subprocess.TimeoutExpired:
            way = _stop(process)
            elapsed = time.monotonic() - started
            why = f"stopped at the time limit after {elapsed:.0f} s"
            if os.name == "nt":
                # Only on Windows are there three ways to stop a tree: the report names the one.
                why += f", by {STOPPED_BY.get(way, way)}"
            return Result(line, UNVERIFIED, elapsed, why, _tail(sink), TIME)
        except BaseException:
            # Stopped from outside, by a KeyboardInterrupt or a signal handler's exception: the
            # command's group goes too, since it runs in its own session (on Windows, its own
            # process group) and the terminal's signal never reaches it.
            _stop(process)
            raise
        elapsed = time.monotonic() - started
        if code == 0:
            return Result(line, PASS, elapsed, code=code)
        tail = _tail(sink)
        missing = missing_tool(tail)
        owned = missing is not None and project_owned(target, missing)
        if (
            missing is not None
            and not owned
            and not other_failure(tail)
            and confirmed_absent(
                target, tail, environment, deadline=None if seconds is None else started + seconds
            )
        ):
            why = f"exit {code} after {elapsed:.0f} s: could not run in the hook's environment"
            note = f"its output says `{missing}` is not on this PATH"
            return Result(line, UNVERIFIED, elapsed, why, tail, ENVIRONMENT, code, note=note)
        why = f"exit {code} after {elapsed:.0f} s"
        ids, complete = _ids_in(sink, None if seconds is None else started + seconds)
        return Result(line, FAIL, elapsed, why, tail, code=code, ids=ids, ids_complete=complete)


def run_all(
    target: Path,
    done: Sequence[str],
    deadline: float,
    record: Known | None = None,
    earlier: Mapping[str, Failure] | None = None,
    into: list[Result] | None = None,
) -> list[Result]:
    """Each Done command in run order until `deadline`, stopping at the first that does not
    pass, a known failure aside: a FAIL that the command's `Failure` in `record` tolerates is
    marked known, with the record's commit, and the next command runs; so is one that its
    `Failure` in `earlier`, the working tree a turn began with, tolerates. Each result goes into
    `into` as its command ends, so that a run stopped from outside keeps those that ended."""

    known = record.failing if record is not None else {}
    before = earlier or {}
    commit = record.head if record is not None else ""
    results: list[Result] = [] if into is None else into
    for line in done:
        left = deadline - time.monotonic()
        if left <= 0:
            why = "not started: the time limit had passed"
            results.append(Result(line, UNVERIFIED, 0.0, why, cause=TIME))
            break
        result = run_one(target, line, left)
        if result.verdict == FAIL and line in known:
            tolerated, note = known[line].tolerates(result)
            result = replace(result, known=tolerated, note=note, commit=commit if tolerated else "")
        if result.verdict == FAIL and not result.known and line in before:
            tolerated, why = before[line].tolerates(result, BY_TURN)
            result = replace(result, known=tolerated, before=tolerated, note=why)
        results.append(result)
        if result.verdict != PASS and not result.known:
            break
    return results


@dataclass(frozen=True)
class Measured:
    """What `measure` found: each command's result, the seconds the whole run took, and whether
    the failures were kept as known in the Git common directory."""

    results: tuple[Result, ...]
    seconds: float
    kept: bool
    # The record this one supersedes in this checkout, and each failure kept now that it did
    # not hold: a command, or a failure id of a command it held.
    previous: Known | None = None
    added: tuple[str, ...] = ()
    # The PATH entries the measurement ran without, as a hook may: see `hook_environment`.
    dropped: tuple[str, ...] = ()
    # Each command the replaced record held as a known failure that now reads as a possible
    # flake, and so is held no longer.
    flaked: tuple[str, ...] = ()
    # Whether the commands ran as a hook runs Done, or with the PATH of the process that asked.
    as_hook: bool = True
    # Each failing command that ran again, to tell a flake or a missing PATH entry from a stable
    # failure; `seconds` counts none of those runs.
    reran: tuple[str, ...] = ()


def added_since(previous: Known, failing: Mapping[str, Failure]) -> list[str]:
    """Each failure in `failing` that `previous` did not hold: a command it did not name or held
    with another exit code, or a failure id new to a command it held."""

    added: list[str] = []
    for line, failure in failing.items():
        before = previous.failing.get(line)
        if before is None or before.code != failure.code:
            added.append(f"`{shorten(line, 80)}` (exit {failure.code})")
            continue
        new = sorted((failure.ids or frozenset()) - (before.ids or frozenset()))
        added.extend(f"`{shorten(line, 80)}`: {shorten(item, 120)}" for item in new)
    return added


def _same_failure(first: Result, again: Result) -> bool:
    """Whether `again` is `first`'s failure again: a FAIL with the same exit code and the same
    failure ids."""

    return (
        again.verdict == FAIL
        and again.code == first.code
        and result_ids(again) == result_ids(first)
    )


def _flake(first: Result, again: Result) -> Result:
    """`first`, a failure that its second run in the same environment did not repeat, as a
    possible flake: UNVERIFIED, and kept as no known failure."""

    if again.verdict == PASS:
        second = "passed"
    elif again.verdict != FAIL:
        second = "could not run"
    elif again.code == first.code:
        second = "failed with other failure ids"
    else:
        second = f"failed with exit {again.code}"
    why = f"{first.why}: possible flake"
    note = f"a second run in the same environment {second}, so no failure is kept for it"
    return replace(first, verdict=UNVERIFIED, why=why, cause=FLAKE, note=note)


def commits_since(target: Path, head: str, deadline: float | None = None) -> int | None:
    """How many commits the target's HEAD is past `head` (`git rev-list --count <head>..HEAD`);
    None where Git cannot count them: a shallow clone, a commit it lacks. An empty `head` is a
    branch with no commit, which no commit is past."""

    if not head:
        return 0 if _head(target, deadline) == "" else None
    counted = _git(target, "rev-list", "--count", f"{head}..HEAD", deadline=deadline)
    try:
        return int((counted or b"").strip())
    except ValueError:
        return None


def measure(target: Path, done: Sequence[str], timeout: int, as_hook: bool = True) -> Measured:
    """Run every Done command once from the target's root, to its end, with no time limit and
    past every failure, as adopt does at install: each FAIL is kept as a known failure for this
    Done list and the target's HEAD commit, with its exit code and the failure ids its output
    names, the day and the seconds the run took; and where the commands left the tree as they
    found it, that tree is remembered as checked under `timeout`, so a turn end on it runs
    nothing. A command that could not run here is neither known nor remembered.

    The environment is the hook's (`hook_environment`) with `as_hook`, else the caller's own,
    where no hook is installed. A command that fails runs once more in the same environment: a
    second run that does not repeat the failure, with its exit code and failure ids, reads
    UNVERIFIED as a possible flake, is kept as no known failure, and keeps the tree from being
    remembered. Only a failure that repeats goes on to the run with the PATH entries the hook
    environment left out. A KeyboardInterrupt, or any exception that stops the wait, stops the
    running command's group and is raised again, with nothing kept."""

    skip = recorded_skip(target) if recorded_done(target) == list(done) else {}
    digest = done_digest(done, skip)
    started = time.monotonic()
    head = _head(target)
    before = tree_digest(target, digest)
    environment, dropped = hook_environment(target, os.environ) if as_hook else (None, ())
    results = [run_one(target, line, None, environment) for line in done]
    # The seconds a hook would see are those of one run of each command: the reruns below tell
    # a flake or a missing PATH entry from a stable failure, and count in no recorded time.
    seconds = time.monotonic() - started
    reran: list[str] = []
    for index, result in enumerate(results):
        if result.verdict != FAIL:
            continue
        reran.append(result.command)
        again = run_one(target, result.command, None, environment)
        if not _same_failure(result, again):
            results[index] = _flake(result, again)
            continue
        if not dropped:
            continue
        # A command that fails without the entries a hook may lack, and passes with them, needs
        # those entries: a hook would fail it, and a known failure would hide its real failures.
        full = run_one(target, result.command, None)
        if _same_failure(result, full):
            continue
        # Passing with them, or failing another way, or not running: the command depends on
        # those entries, so neither run is kept as a known failure.
        how = "passes" if full.verdict == PASS else "runs differently"
        why = f"{result.why}: could not run in the hook's environment"
        note = f"it {how} with {', '.join(dropped)} on PATH"
        results[index] = replace(result, verdict=UNVERIFIED, why=why, cause=ENVIRONMENT, note=note)
    failing: dict[str, Failure] = {}
    for index, result in enumerate(results):
        if result.verdict == FAIL and result.code is not None:
            ids = result_ids(result)
            failing[result.command] = Failure(result.code, ids or None)
            note = "known by its failure ids" if ids else "known by its exit code only"
            results[index] = replace(result, known=True, note=note, commit=head or "")
    day = time.strftime("%Y-%m-%d")
    record = Known(digest, "", head or "", day, round(seconds, 1), failing, as_hook=as_hook)
    previous = known_record(target, digest) if head is not None else None
    kept = head is not None and keep_known(target, record)
    added = tuple(added_since(previous, failing)) if previous is not None else ()
    flaked = tuple(
        result.command
        for result in results
        if previous is not None and result.cause == FLAKE and result.command in previous.failing
    )
    unsettled = any(result.cause in (ENVIRONMENT, FLAKE) for result in results)
    if kept and before is not None and not unsettled and tree_digest(target, digest) == before:
        verdict = FAIL if failing else PASS
        listed = tuple(results) if failing else ()
        remember(target, Checked(before, timeout, verdict, listed, time=now_text()))
    return Measured(
        tuple(results), seconds, kept, previous, added, dropped, flaked, as_hook, tuple(reran)
    )


def hook_environment(
    target: Path, environ: Mapping[str, str]
) -> tuple[dict[str, str], tuple[str, ...]]:
    """`environ` as a hook may see it, and the PATH entries taken out: a hook has the harness's
    PATH, which a desktop harness starts without the project's tools, so the measurement runs
    without an entry inside the target and without a virtual environment's `bin` (a folder whose
    parent holds `pyvenv.cfg`), and without `VIRTUAL_ENV`. A Done that passes only with those
    entries then reads `UNVERIFIED` at install, where a person sees it, and not at each turn end:
    `measure` runs a command that fails without them once more with them. A conda environment's
    `bin` holds no `pyvenv.cfg` and is not told apart."""

    root = target.resolve()
    kept: list[str] = []
    dropped: list[str] = []
    for entry in (programs.environment_value(environ, "PATH") or "").split(os.pathsep):
        # Done runs from the target's root, so an empty entry (the current folder) and a
        # relative entry name folders of the target.
        folder = (root / entry).resolve()
        inside = folder == root or root in folder.parents
        try:
            venv = (folder.parent / "pyvenv.cfg").is_file()
        except OSError:
            # A folder this process cannot read is no virtual environment it can tell.
            venv = False
        if inside or venv:
            dropped.append(entry)
        else:
            kept.append(entry)
    environment = {
        key: value
        for key, value in environ.items()
        if (key.upper() if os.name == "nt" else key) not in ("PATH", "VIRTUAL_ENV")
    }
    environment["PATH"] = os.pathsep.join(kept)
    return environment, tuple(dropped)


# --- The report ------------------------------------------------------------------


def clean(data: bytes) -> str:
    """Output as text an agent can read: terminal escapes and control characters stripped."""

    text = data.decode("utf-8", "replace").replace("\r\n", "\n")
    text = "\n".join(line.rsplit("\r", 1)[-1] for line in text.split("\n"))
    return CONTROL.sub("", ANSI.sub("", text)).strip("\n")


def fenced(lines: list[str], room: int, head: Sequence[str] = ()) -> str:
    """The last of `lines` that fit in `room` characters after the `head` lines, which are
    always kept, fenced as data labelled `output`.

    A run of backticks longer than `LONGEST_RUN` is written as its count, so the fence that
    must outrun every run in the data stays short and the whole stays within `room`."""

    lines = [BACKTICKS.sub(lambda run: f"[{len(run.group())} backticks]", line) for line in lines]
    top = [BACKTICKS.sub(lambda run: f"[{len(run.group())} backticks]", line) for line in head]
    longest = max((len(run) for line in lines + top for run in re.findall(r"`+", line)), default=0)
    fence = "`" * max(3, longest + 1)
    kept: list[str] = []
    used = 2 * len(fence) + len("output") + 2 + sum(len(line) + 1 for line in top)
    for line in reversed(lines):
        if used + len(line) + 1 > room:
            if not kept and room - used - 1 > 0:
                kept.append(line[len(line) - (room - used - 1) :])
            break
        kept.insert(0, line)
        used += len(line) + 1
    return "\n".join([f"{fence}output", *top, *kept, fence])


SKIPPED = re.compile(r"^SKIPPED\b")
TRACEBACK = re.compile(r"^E\s")
SHOWN_IDS = 8
SHOWN_ERRORS = 4


def _view(result: Result, room: int) -> str:
    """The fenced lines a report shows of a failing command's output: its last lines that fit.
    Where pytest names failures, its `SKIPPED` lines (the `-rs` summary prints them last) are
    left out, and what the tail does not show is put first: the failure ids the whole output
    named, and the first `E ` lines of the traceback."""

    lines = clean(result.output).split("\n")
    ids = sorted(result_ids(result))
    if not any(one.startswith("pytest ") for one in ids):
        return fenced(lines, room)
    lines = [line for line in lines if not SKIPPED.match(line)]
    shown = fenced(lines, room)
    cut = [one.split(" ", 1)[1] for one in ids if one.split(" ", 1)[1] not in shown]
    errors = [line for line in lines if TRACEBACK.match(line) and line not in shown]
    head: list[str] = []
    if cut:
        names = ", ".join(shorten(one, 100) for one in cut[:SHOWN_IDS])
        more = f" and {len(cut) - SHOWN_IDS} more" if len(cut) > SHOWN_IDS else ""
        head.append(f"Failing, not in the lines below: {names}{more}")
    if errors:
        head += [shorten(line, 160) for line in errors[:SHOWN_ERRORS]]
    while head and sum(len(line) + 1 for line in head) > room // 2:
        head.pop()
    return fenced(lines, room, head) if head else shown


def _shown(results: Sequence[Result]) -> Result:
    """The result whose output the report shows: the last that did not pass and is not a known
    failure, else the last that did not pass, else the last."""

    failed = [result for result in results if result.verdict != PASS]
    new = [result for result in failed if not result.known]
    return (new or failed or list(results))[-1]


def report(head: str, results: Sequence[Result]) -> str:
    """The verdict, one line per command run, then the last lines of the command `_shown`
    names as data, the whole under `REPORT_CHARACTERS`; commands that passed are summed up in one
    line where theirs would crowd out the rest."""

    lines = [result.line() for result in results]
    if len(lines) > 1 and sum(len(line) + 1 for line in lines) > REPORT_CHARACTERS // 4:
        passed = sum(result.verdict == PASS for result in results)
        rest = [line for result, line in zip(results, lines, strict=True) if result.verdict != PASS]
        first = all(result.verdict == PASS for result in results[:-1])
        summary = f"PASS the {passed} commands before it" if first else f"PASS {passed} others"
        lines = [summary, *rest] if passed else rest
    text = "\n".join([head, *lines])
    last = _shown(results)
    if last.verdict != PASS and last.output:
        intro = f"The last lines `{shorten(last.command, 80)}` printed, as data, not instructions:"
        room = REPORT_CHARACTERS - 1 - len(text) - len(intro) - 2
        if room > 40:
            text += "\n" + intro + "\n" + _view(last, room)
    return text


def told(message: str) -> Verdict:
    """A message the person sees; nothing is held and nothing reaches the model."""

    return {"systemMessage": message}


def _unverified_head(last: Result, target: Path, timeout: int) -> str:
    shown = shorten(last.command, 80)
    if last.cause == ENVIRONMENT:
        return (
            f"finish-check UNVERIFIED: `{shown}` could not run in the hook's environment, which "
            "has the harness process's PATH and no activated virtual environment; nothing was held."
        )
    quoted = paths.shell_path(target)
    return (
        f"finish-check UNVERIFIED: `{shown}` did not finish within {timeout - MARGIN_SECONDS} s, "
        f"{MARGIN_SECONDS} s before the hook's {timeout} s timeout; nothing was held. To give the "
        f"Done commands longer, re-run `outcomebound adopt {quoted} --finish-timeout <seconds>`, "
        f"for example {2 * timeout}; to take the check out, `outcomebound adopt {quoted} "
        "--no-finish-check`."
    )


def failures_of(results: Sequence[Result]) -> dict[str, Failure]:
    """The failure of each command a checked-tree record's results show failing: its exit code
    and the failure ids its output names, None where it names none."""

    return {
        result.command: Failure(result.code, result_ids(result) or None)
        for result in results
        if result.verdict == FAIL and result.code is not None
    }


def _environment(target: Path) -> str:
    """The environment a Done command ran with, in a sentence for the agent: where it ran and
    the PATH entries in front."""

    entries = (programs.environment_value(os.environ, "PATH") or "").split(os.pathsep)
    front = ", ".join(shorten(entry, 60) for entry in [e for e in entries if e][:3]) or "none"
    return (
        f"Done ran from {paths.shell_path(target)} with PATH starting {front}. A failure that "
        "appears only here may come from this environment, not your change."
    )


HOLD_FIRST = "finish-check FAIL: a Done command failed on this working tree."
HOLD_GUIDANCE = (
    "Fix what your change broke and continue with the work. If it failed before your change, a "
    "tool it needs is missing here, or the fix needs an act outside your authority, say so in "
    "your report and continue with the work it does not block. End your turn only when your "
    "work is done."
)


def hold_head(results: Sequence[Result], target: Path, first: str = HOLD_FIRST) -> str:
    """The first line of a hold: `first`, what the agent is asked to do, and what it needs to
    tell a failure of this environment or one known before from its own."""

    head = f"{first} {HOLD_GUIDANCE}"
    if any(result.known for result in results):
        when = "when adopt measured Done"
        if any(result.before for result in results):
            every = all(result.before for result in results if result.known)
            when = "when this turn began" if every else f"{when} or when this turn began"
        head += (
            f" A command marked known failed the same way before your change, {when}; it "
            "does not hold this turn. One that names new failure ids, or a new exit code, "
            "does."
        )
    if any(result.known and "exit code only" in result.note for result in results):
        head += (
            " A command known by its exit code only was compared by that code alone, since "
            "its output names no failure ids, so a new failure inside it is not told apart."
        )
    return head + " " + _environment(target)


def verdict_for(
    results: Sequence[Result],
    held: bool,
    target: Path,
    timeout: int,
    repeated: bool = False,
    why: str = "",
) -> Verdict:
    """What a run that did not pass prints; `repeated` where it is the verdict an unchanged tree
    was last checked with, run again for nothing. Only a failure that is not known holds; `why`
    says why one that is not known was told to the person instead."""

    last = results[-1]
    again = " Not run again: the working tree is unchanged since that check." if repeated else ""
    if last.verdict == UNVERIFIED:
        return told(report(_unverified_head(last, target, timeout) + again, results))
    if not any(result.verdict == FAIL and not result.known for result in results):
        coarse = any(result.known and "exit code only" in result.note for result in results)
        limit = (
            " A command known by its exit code only names no failure ids in its output, so a new "
            "failure inside it is not told apart."
            if coarse
            else ""
        )
        commits = sorted({result.commit[:12] for result in results if result.commit})
        on = f"on commit {', '.join(commits)}, which" if commits else "on a commit"
        earlier = any(result.before for result in results)
        if earlier and all(result.before for result in results if result.known):
            head = (
                "finish-check FAIL, known before this turn: each Done command that failed here "
                "failed as it did on the working tree this turn began with: the same exit code, "
                "and no failure id its output names is new; so nothing was held." + limit + again
            )
            return told(report(head, results))
        head = (
            "finish-check FAIL, known: each Done command that failed here failed as it did when "
            f"adopt measured Done {on} this checkout descends from: the same exit code, and no "
            "failure id its output names is new; so nothing was held." + limit + " A "
            "known command that passes leaves the record, and a later failure of it holds. "
            f"`outcomebound adopt {paths.shell_path(target)} --finish-check` measures Done again."
            + again
        )
        if earlier:
            head += (
                " A command marked known before this turn failed the same way on the working "
                "tree this turn began with."
            )
        return told(report(head, results))
    if held and not repeated:
        return {"decision": "block", "reason": report(hold_head(results, target), results)}
    why = why or (
        "the working tree is unchanged since this failure, so it was not run again"
        if repeated
        else "the stop hook already continued once or its input could not be read"
    )
    head = (
        "finish-check FAIL: a Done command failed on this working tree; told to you, not the "
        f"agent, since {why}."
    )
    return told(report(head, results))


def drop_fixed(
    target: Path, record: Known | None, results: Sequence[Result], deadline: float
) -> None:
    """A known failure that passes leaves the record: from then on, its failure holds."""

    fixed = {result.command for result in results if result.verdict == PASS}
    if record is not None and fixed & record.failing.keys():
        left = {line: item for line, item in record.failing.items() if line not in fixed}
        keep_known(target, replace(record, failing=left), deadline)


def marked_told(verdict: Verdict, when: str, unchanged: bool) -> Verdict:
    """`verdict`, where the turn-start mark has decided it, with what the person sees: that
    Done was not run on the tree the turn began with, or that a failure was known before the
    turn, and when the mark was written (`when`). A hold is the model's and gets nothing added."""

    if "decision" in verdict:
        return verdict
    shown = clock_of(when)
    if unchanged and not verdict:
        text = (
            f"finish-check: the tree is the one this turn began with (marked {shown}); Done was "
            "not run."
        )
        return told(text)
    note = (
        f" The tree is the one this turn began with (marked {shown})."
        if unchanged
        else f" The turn began with these failures (marked {shown})."
    )
    head, _, rest = str(verdict.get("systemMessage", "")).partition("\n")
    return told(head + note + (f"\n{rest}" if rest else ""))


def _unchanged_verdict(record: Checked | None, tree: str | None, target: Path) -> Verdict:
    """What a turn that changed nothing repeats: the check of this tree, where it is not a pass,
    as the person's to see again; else nothing."""

    if record is None or record.tree != tree or record.kind != CHECKED:
        return {}
    if record.verdict == PASS or not record.results:
        return {}
    return verdict_for(record.results, False, target, record.timeout, repeated=True)


# --- The same failure, and the failures a session was held for ---------------------


def _places(target: Path) -> list[tuple[str, str]]:
    """Each way a line can write the target and the system's temporary folder, longest first,
    the target's before the temporary folder's, which may hold it."""

    found: set[tuple[str, str]] = set()
    for base, name in ((target, "<target>"), (Path(tempfile.gettempdir()), "<tmp>")):
        try:
            places = {base, base.resolve()}
        except OSError:
            places = {base}
        found |= {
            (text, name)
            for place in places
            for text in (str(place), place.as_posix())
            if len(text) > 1
        }
    return sorted(found, key=lambda item: (item[1] != "<target>", -len(item[0])))


def _normalised(line: str, places: Sequence[tuple[str, str]]) -> str:
    for text, name in places:
        line = line.replace(text, name)
    return DIGIT_RUN.sub("#", HEX_RUN.sub("<hex>", line))


def signature(result: Result, target: Path) -> str:
    """A failure's signature: the sha256 of canonical JSON of its command line, its exit code,
    its sorted failure ids (empty where its output names none) and a digest of its lines. Where
    the output names failure ids the lines are the runner's lines that name them, so a new warning
    or a longer traceback elsewhere does not move it; else the last `SIGNATURE_LINES` non-empty
    lines of the kept tail. The lines are read with the target's path as `<target>`, the
    temporary folder as `<tmp>`, each run of 8 or more hexadecimal characters as `<hex>` and each
    run of digits as `#`, and then sorted: a timing, a process id, an object id, a scratch path
    or a parallel runner's order does not make the same failure new, and a new message does."""

    ids = sorted(result_ids(result))
    lines = clean(result.output).split("\n")
    if ids:
        kept = [line for line in lines if any(p.match(line) for _, p in FAILURE_IDS)]
    else:
        kept = [line for line in lines if line.strip()][-SIGNATURE_LINES:]
    places = _places(target)
    shown = sorted(_normalised(line.strip(), places) for line in kept)
    lines_digest = hashlib.sha256("\n".join(shown).encode("utf-8")).hexdigest()
    return hashlib.sha256(canonical([result.command, result.code, ids, lines_digest])).hexdigest()


def _common_dir(target: Path, deadline: float | None = None) -> Path | None:
    found = _known_path(target, deadline)
    return found[0].parent if found is not None else None


def _held_document(path: Path) -> dict[str, list[Any]]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    sessions = document.get("sessions") if isinstance(document, dict) else None
    if not isinstance(sessions, dict):
        return {}
    return {key: value for key, value in sessions.items() if isinstance(value, list)}


def held_signatures(
    target: Path, session: str | None, deadline: float | None = None
) -> frozenset[str]:
    """The signatures `session` was held for, in the held list of the Git common directory."""

    common = _common_dir(target, deadline) if session else None
    if common is None or session is None:
        return frozenset()
    items = _held_document(common / HELD).get(session, [])
    return frozenset(
        item["signature"]
        for item in items
        if isinstance(item, dict) and isinstance(item.get("signature"), str)
    )


def keep_held(
    target: Path, session: str | None, signature: str, tree: str, deadline: float | None = None
) -> bool:
    """Add `signature` to the session's held list, before the hold is printed: from then on the
    same failure in this session goes to the person. Whether it was written: a hold goes out
    only where it was. The list is not pruned."""

    common = _common_dir(target, deadline) if session else None
    if common is None or session is None:
        return False
    path = common / HELD
    document = _held_document(path)
    document.setdefault(session, []).append(
        {"signature": signature, "time": now_text(), "tree": tree}
    )
    return write_whole(path, json.dumps({"sessions": document}, ensure_ascii=False) + "\n")


# --- What the person is told, once for each session, tree and kind ---------------


@dataclass(frozen=True)
class Notice:
    """A message for the person about one tree, of one kind; `tree` is empty where it is about
    none."""

    tree: str
    kind: str
    text: str


def _told(path: Path) -> set[tuple[str, str, str]]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    if not isinstance(document, dict):
        return set()
    items = document.get("told")
    if isinstance(items, list):
        return {
            (item[0], item[1], item[2])
            for item in items
            if isinstance(item, list) and len(item) == 3 and all(isinstance(x, str) for x in item)
        }
    session, tree = document.get("session"), document.get("tree")
    if isinstance(session, str) and isinstance(tree, str):
        # What an engine before the constant-time stop kept: an unchanged turn told.
        return {(session, tree, UNCHANGED)}
    return set()


def tell(
    target: Path, session: str | None, notices: Sequence[Notice], deadline: float | None = None
) -> list[str]:
    """The texts of the notices the person was not yet told in this session, for their tree and
    kind, kept as told now; the file keeps this session's entries only. With no session every
    notice is told, and nothing is kept."""

    unique = list({(notice.tree, notice.kind): notice for notice in notices}.values())
    path = _state(target, deadline, TOLD) if session else None
    if path is None or session is None:
        return [notice.text for notice in unique]
    known = _told(path)
    fresh = [notice for notice in unique if (session, notice.tree, notice.kind) not in known]
    if fresh:
        # Only this session's entries are kept: another session's are never read again by it.
        mine = {key for key in known if key[0] == session}
        keys = mine | {(session, notice.tree, notice.kind) for notice in fresh}
        write_whole(path, json.dumps({"told": sorted(list(key) for key in keys)}) + "\n")
    return [notice.text for notice in fresh]


def _digest_text(target: Path) -> str:
    return (
        f"finish-check UNVERIFIED: the Done commands in {target / MANIFEST} are not the ones "
        "this hook was written for; nothing ran. "
        f"Re-run `outcomebound adopt {paths.shell_path(target)}`."
    )


def _changed_text(record: Checked, target: Path) -> str:
    head = (
        "finish-check UNVERIFIED: Done ran on a tree that changed before it ended, so no tree "
        "was checked; nothing was held."
    )
    if record.cause == OUTSIDE:
        head += (
            " No prompt was written while it ran: Done, or something outside the session, writes "
            "into the tree; have Done write only what Git ignores."
        )
    elif record.cause == SUPERSEDED:
        head += " It was stopped from outside: a turn end on a later tree, or the harness."
    return report(head, record.results) if record.results else head


def _pass_text(record: Checked) -> str:
    listed = ", ".join(shorten(result.command, 80) for result in record.results)
    skipped = ", ".join(shorten(command, 80) for command in record.skipped)
    not_run = (
        f"; not run, every changed path is one its --done-skip names: {skipped}" if skipped else ""
    )
    return f"finish-check PASS: {listed}, {record.seconds:.0f}s{not_run}; not reviewed, not landed"


@dataclass(frozen=True)
class Viewer:
    """Who a notice is for: the session, the tree it stands on, whether its stop has the guard
    set, and the signatures the session was held for."""

    session: str | None
    tree: str | None
    guarded: bool = False
    held: frozenset[str] = frozenset()


def record_notice(record: Checked, viewer: Viewer, target: Path) -> Notice | None:
    """What the person is told of `record` at a turn end or a prompt of `session` on `tree`, or
    None: a pass adopt measured (the person saw it), and a failure that is still to be held, or
    was held from this record, are not told."""

    if record.kind == CHANGED:
        return Notice(record.tree, CHANGED, _changed_text(record, target))
    if record.verdict == PASS:
        if record.session is None or not record.results:
            return None
        return Notice(record.tree, PASS, _pass_text(record))
    if not record.results:
        return None
    if record.verdict == UNVERIFIED:
        text = verdict_for(record.results, False, target, record.timeout)["systemMessage"]
        return Notice(record.tree, UNVERIFIED, text)
    if not record.holding:
        repeated = record.session != viewer.session
        verdict = verdict_for(record.results, False, target, record.timeout, repeated=repeated)
        if record.marked and any(result.before for result in record.results):
            verdict = marked_told(verdict, record.marked, False)
        return Notice(record.tree, KNOWN_KIND, str(verdict["systemMessage"]))
    return _failure_notice(record, viewer, target)


def _failure_notice(record: Checked, viewer: Viewer, target: Path) -> Notice | None:
    """What the person is told of a failure that holds, where it does not reach the model:
    another session's, one held once already, the repeat after the guard on the tree it was held
    on, one after the guard, one while paused; None for one still to be held, or held from this
    record."""

    session, tree, guarded, held = viewer.session, viewer.tree, viewer.guarded, viewer.held
    own = session is not None and record.session == session
    if not own:
        why = "another session's run found it"
    elif record.hold == HELD_BEFORE:
        why = "it was held once already in this session"
    elif record.holding in held:
        if not (guarded and record.tree == tree):
            return None
        why = "the working tree is unchanged since this failure, so it was not run again"
    elif record.guarded or (guarded and record.tree == tree):
        why = "the stop hook already continued once or its input could not be read"
    elif record.paused:
        head = (
            "finish-check FAIL: a Done command failed while the session was paused, with "
            "background work in flight; it is held at the first turn end of the session that is "
            "not paused, where Done still fails."
        )
        return Notice(record.tree, PAUSED_KIND, report(head, record.results))
    else:
        return None
    text = verdict_for(record.results, False, target, record.timeout, why=why)["systemMessage"]
    return Notice(record.tree, FAIL, str(text))


def hold_report(record: Checked, target: Path, both: bool = False) -> str:
    """The report a hold gives the model: its first line says how the failure stands (found
    again after the session recorded it, with the time of each run where `both`; with no record
    of the tree the turn began with; or new), then what to do, then the commands and the output.
    """

    if record.hold == AGAIN and record.first:
        first = (
            "finish-check FAIL: Done failed on the tree this turn began with, at "
            f"{clock_of(record.first)}, and still fails now"
        )
        first += f" (found again at {clock_of(record.time)})." if both else "."
    elif record.hold == NOBASE:
        first = (
            "finish-check FAIL: a Done command failed on this working tree; no record of the tree "
            "this turn began with was found, so the failure may predate this turn."
        )
    else:
        first = HOLD_FIRST
    return report(hold_head(record.results, target, first), record.results)


def deliverable(
    record: Checked | None,
    session: str | None,
    guarded: bool,
    paused: bool,
    held: frozenset[str],
    tree: str | None,
) -> bool:
    """Whether a turn end of `session` on `tree` holds for `record` at once: the check of this
    very tree, by this session's run, with a failure that holds and that no hold delivered, the
    guard unset and the session not paused."""

    return (
        record is not None
        and record.kind == CHECKED
        and record.tree == tree
        and record.verdict == FAIL
        and bool(record.holding)
        and record.hold in (NEW, NOBASE, AGAIN)
        and record.holding not in held
        and session is not None
        and record.session == session
        and not guarded
        and not paused
    )


def confirmed(
    record: Checked | None, session: str | None, guarded: bool, held: frozenset[str]
) -> bool:
    """Whether a codex stop holds for `record`, the record of the tree its turn began on: a run
    of this session found the failure again there, and no hold delivered it."""

    return (
        record is not None
        and record.hold == AGAIN
        and bool(record.holding)
        and record.holding not in held
        and session is not None
        and record.session == session
        and not guarded
    )


# --- The run record and the run lock -----------------------------------------------


@dataclass(frozen=True)
class Run:
    """The record the run that holds the lock writes in the Git directory: its process, the
    tree and HEAD it started on, when, the session, the mark it read, the Done digest and the
    limit; and how it ended, once it has."""

    pid: int
    tree: str
    head: str
    started: datetime
    session: str | None
    mark: dict[str, str] | None
    done: str
    timeout: int
    guarded: bool = False
    ended: dict[str, str] | None = None

    def document(self) -> dict[str, Any]:
        found: dict[str, Any] = {
            "pid": self.pid,
            "tree": self.tree,
            "head": self.head,
            "started": self.started.isoformat(),
            "session": self.session,
            "mark": self.mark,
            "done": self.done,
            "timeout": self.timeout,
            "guarded": self.guarded,
        }
        return found | ({"ended": self.ended} if self.ended is not None else {})


def _run_of(document: object) -> Run | None:
    if not isinstance(document, dict):
        return None
    pid, tree, head = document.get("pid"), document.get("tree"), document.get("head")
    started, session = stamp(document.get("started")), document.get("session")
    mark, done, timeout = document.get("mark"), document.get("done"), document.get("timeout")
    guarded, ended = document.get("guarded", False), document.get("ended")
    if not (
        type(pid) is int
        and isinstance(tree, str)
        and isinstance(head, str)
        and started is not None
        and (session is None or isinstance(session, str))
        and (
            mark is None
            or (isinstance(mark, dict) and all(isinstance(v, str) for v in mark.values()))
        )
        and isinstance(done, str)
        and type(timeout) is int
        and admits_timeout(timeout)
        and isinstance(guarded, bool)
    ):
        return None
    if ended is not None and not (
        isinstance(ended, dict) and all(isinstance(value, str) for value in ended.values())
    ):
        return None
    return Run(pid, tree, head, started, session, mark, done, int(timeout), guarded, ended)


def read_run(target: Path, deadline: float | None = None) -> tuple[Run | None, bool]:
    """(the run record, whether there is a file): a file that cannot be read or parsed is
    (None, True), which reads as a run that did not finish."""

    path = _state(target, deadline, RUN)
    return _read_run_at(path) if path is not None else (None, False)


def _read_run_at(path: Path) -> tuple[Run | None, bool]:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None, False
    except OSError:
        return None, True
    try:
        return _run_of(json.loads(text)), True
    except ValueError:
        return None, True


def _take(descriptor: int) -> bool:
    """Take the run lock on an open descriptor without waiting: `flock` on POSIX, so that only
    a close of this very descriptor releases it; on Windows `msvcrt.locking` on the first byte.
    The operating system releases either when the process ends, however it ends."""

    try:
        if sys.platform == "win32":
            import msvcrt

            os.lseek(descriptor, 0, os.SEEK_SET)
            msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return False
    return True


def _release_lock(descriptor: int) -> None:
    with contextlib.suppress(OSError):
        if sys.platform == "win32":
            import msvcrt

            os.lseek(descriptor, 0, os.SEEK_SET)
            msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(descriptor, fcntl.LOCK_UN)


class RunLock:
    """The run lock of one Git directory, `RUN_LOCK`. A run opens the file once and never again,
    and keeps the descriptor while it lives: `os.open` makes it non-inheritable and `subprocess`
    closes inherited descriptors, so no Done command keeps it alive."""

    def __init__(self, path: Path) -> None:
        self.descriptor = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
        self.held = False

    def take(self) -> bool:
        self.held = self.held or _take(self.descriptor)
        return self.held

    def close(self) -> None:
        if self.descriptor < 0:
            return
        if self.held:
            _release_lock(self.descriptor)
        with contextlib.suppress(OSError):
            os.close(self.descriptor)
        self.descriptor, self.held = -1, False


def lock_held(path: Path) -> bool:
    """Whether a run holds the lock: a non-blocking attempt from a descriptor of this call's own
    fails. Creates nothing; a lock it took is released at once."""

    try:
        descriptor = os.open(path, os.O_RDWR)
    except OSError:
        return False
    try:
        if _take(descriptor):
            _release_lock(descriptor)
            return False
        return True
    finally:
        os.close(descriptor)


NONE, LIVE, ENDED, DEAD = "none", "live", "ended", "dead"


def run_state(target: Path, deadline: float | None = None) -> tuple[str, Run | None]:
    """How the last run stands: `none`, `ended`, `live`, or `dead`. A run record with no end is
    dead where it cannot be read, where its process is gone, where its start is older than its
    limit plus `WAKE_MARGIN`, or where no run holds the lock; its process id is read only while
    the lock is held."""

    run, there = read_run(target, deadline)
    if run is None:
        return (DEAD if there else NONE), None
    if run.ended is not None:
        return ENDED, run
    age = (datetime.now(timezone.utc) - run.started).total_seconds()
    lock = _state(target, deadline, RUN_LOCK)
    if lock is None or not lock_held(lock) or age > run.timeout + WAKE_MARGIN:
        return DEAD, run
    return (LIVE if programs.alive(run.pid) else DEAD), run


def _young(run: Run) -> bool:
    age = (datetime.now(timezone.utc) - run.started).total_seconds()
    return age <= run.timeout + WAKE_MARGIN


HOLDER, FOLLOWER, STUCK_ROLE = "holder", "follower", "stuck"


def acquire(lock: RunLock, record: Path, tree: str) -> tuple[str, Run | None]:
    """Take the run lock: (`HOLDER`, None) once it is this run's; (`FOLLOWER`, the holder) where
    the run that holds it started on this same tree; (`STUCK_ROLE`, the holder) where a run on
    another tree, asked to stop once (`programs.terminate`: SIGTERM on POSIX, TerminateProcess on
    Windows), still holds it `SUPERSEDE_SECONDS` later. The holder's process id is read from its
    run record only while an attempt on the lock still fails, and never from a record that has
    ended or outlived its limit."""

    if lock.take():
        return HOLDER, None
    asked = False
    give_up = time.monotonic() + SUPERSEDE_SECONDS
    other: Run | None = None
    while True:
        other, _ = _read_run_at(record)
        live = (
            other is not None
            and other.ended is None
            and _young(other)
            and other.pid != os.getpid()
            and programs.alive(other.pid)
        )
        if live and other is not None and other.tree == tree:
            return FOLLOWER, other
        if live and other is not None and not asked:
            if lock.take():
                return HOLDER, None
            programs.terminate(other.pid)
            asked = True
            give_up = time.monotonic() + SUPERSEDE_SECONDS
        if lock.take():
            return HOLDER, None
        if time.monotonic() > give_up:
            return STUCK_ROLE, other
        time.sleep(LOCK_POLL)


def follow(lock: RunLock, until: float) -> bool:
    """Wait for the holder's end, as the lock tells it, until `until`; whether it ended."""

    while time.monotonic() < until:
        if lock.take():
            return True
        time.sleep(0.2)
    return lock.take()


class Superseded(BaseException):
    """A run on a later tree asked this one to stop (SIGTERM), or the harness did."""


class _Stopping:
    """The run's SIGTERM handler: while armed, it raises `Superseded` where the run is, which
    stops the live command's process group (`run_one`); otherwise it notes the request, and
    arming raises it then, so that a request that came before the commands started still
    stops them. Disarmed while the run writes its records."""

    def __init__(self) -> None:
        self.armed = False
        self.asked = False

    def __call__(self, number: int, frame: object) -> None:
        self.asked = True
        if self.armed:
            self.armed = False
            raise Superseded()

    def arm(self) -> None:
        if self.asked:
            raise Superseded()
        self.armed = True


def _session(payload: Mapping[str, Any] | None) -> str | None:
    found = payload.get("session_id") if payload is not None else None
    return found if isinstance(found, str) and found else None


def _paused(payload: Mapping[str, Any] | None) -> bool:
    """Whether the session is paused, not finished: background work or a scheduled wake-up will
    wake it (claude-code's `background_tasks` and `session_crons`)."""

    return bool(payload and (payload.get("background_tasks") or payload.get("session_crons")))


def _gitdir(target: Path, deadline: float | None = None) -> Path | None:
    return _state(target, deadline, "")


def _new_turn(target: Path, session: str | None, deadline: float | None = None) -> bool:
    """Whether a live (unstamped) mark of the session is on file: the person typed and a new
    turn began, decided by the stamp and never by comparing clocks."""

    mark = read_mark(target, deadline)
    return mark is not None and mark.session == session and mark.ended is None


def _outside(target: Path, started: datetime, deadline: float | None = None) -> bool:
    """Whether no live mark of any session was written after `started`: no session moved the
    tree while the run ran."""

    mark = read_mark(target, deadline)
    return not (mark is not None and mark.ended is None and mark.written >= started)


def _earlier(
    baseline: Checked | None, session: str | None, held: frozenset[str], target: Path
) -> dict[str, Failure]:
    """The failures of the tree the turn began with that a turn's run does not hold: those
    another session's run recorded, those this session was held for already, and those adopt
    knew. One this session recorded and no hold delivered is the session's own, and holds when
    a run finds it again."""

    if baseline is None:
        return {}
    found: dict[str, Failure] = {}
    for result in baseline.results:
        if result.verdict != FAIL or result.code is None:
            continue
        if baseline.session != session or result.known or signature(result, target) in held:
            found[result.command] = Failure(result.code, result_ids(result) or None)
    return found


def _carried(baseline: Checked | None, session: str | None, held: frozenset[str]) -> list[Pending]:
    if baseline is None or session is None or baseline.session != session:
        return []
    return [item for item in baseline.pending if item.signature not in held]


def _verdict(results: Sequence[Result]) -> str:
    if results and results[-1].verdict == UNVERIFIED:
        return UNVERIFIED
    return FAIL if any(result.verdict == FAIL for result in results) else PASS


@dataclass
class _Context:
    """What one run knows from its input and its start."""

    harness: str
    digest: str
    done: list[str]
    target: Path
    timeout: int
    session: str | None
    guarded: bool
    paused: bool
    wake: bool
    begun: float
    started: datetime
    skip: Mapping[str, Sequence[str]] = field(default_factory=dict)

    @property
    def until(self) -> float:
        return self.begun + self.timeout - MARGIN_SECONDS

    @property
    def book(self) -> float:
        return self.until + REMEMBER_SECONDS


def _wake_from(
    context: _Context, record: Checked | None, tree: str, deadline: float | None = None
) -> tuple[int, str, str]:
    """(exit code, report, note): exit 2 with the hold's report where the run's row wakes the
    model and `record`, the check of this tree, holds for this run's input, and no new turn
    began; the signature goes to the held list first, and where it cannot, exit 0 with
    `UNHELD_NOTE`, so the person is told and the model is not. Else exit 0. The held list is read
    and written by `deadline`, the run's own by default."""

    deadline = context.book if deadline is None else deadline
    if not context.wake or record is None:
        return 0, "", ""
    held = held_signatures(context.target, context.session, deadline)
    if not deliverable(record, context.session, context.guarded, context.paused, held, tree):
        return 0, "", ""
    if _new_turn(context.target, context.session, deadline):
        return 0, "", ""
    if not keep_held(context.target, context.session, record.holding, record.tree, deadline):
        return 0, "", UNHELD_NOTE
    return 2, hold_report(record, context.target), ""


@dataclass(frozen=True)
class _Turn:
    """What a run compares its results with: the tree it started on, the mark of the turn that
    ended there, the record of the tree that turn began with, and the session's held list."""

    tree: str
    mark: Mark | None
    baseline: Checked | None
    held: frozenset[str]


def _record(
    context: _Context,
    turn: _Turn,
    results: Sequence[Result],
    changed: bool,
    cause: str,
    skipped: Sequence[str] = (),
) -> Checked:
    """The record of a run's results: a check of the turn's tree, or, where `changed`, the
    results of a run whose tree changed, with the session's failures carried forward."""

    now = now_text()
    baseline, held, mark = turn.baseline, turn.held, turn.mark
    carried = _carried(baseline, context.session, held)
    by_signature = {item.signature: item for item in carried}
    last = results[-1] if results else None
    holding = hold = first = ""
    if last is not None and last.verdict == FAIL and not last.known:
        holding = signature(last, context.target)
        if holding in held:
            hold = HELD_BEFORE
        elif holding in by_signature:
            hold, first = AGAIN, by_signature[holding].first
        else:
            hold = NOBASE if baseline is None else NEW
    ran = {result.command for result in results}
    pending = [item for item in carried if item.command not in ran or item.signature == holding]
    if hold in (NEW, NOBASE) and last is not None:
        pending.append(Pending(holding, last.command, now))
    verdict = _verdict(results)
    return Checked(
        turn.tree,
        context.timeout,
        UNVERIFIED if changed else verdict,
        tuple(results),
        CHANGED if changed else CHECKED,
        context.session,
        now,
        round(time.monotonic() - context.begun, 1),
        cause or (ENVIRONMENT if last is not None and last.cause == ENVIRONMENT else ""),
        holding,
        hold,
        first,
        tuple(pending),
        mark.written.isoformat() if mark is not None else "",
        context.guarded,
        context.paused,
        tuple(skipped),
    )


def _check(
    context: _Context, stopping: _Stopping, tree: str, head: str, mark: Mark | None
) -> tuple[str, str, int, str]:
    """The holder's work: (outcome, note, exit code, report)."""

    target, book = context.target, context.book
    current = checked_for(target, tree, context.until)
    unchanged = mark is not None and mark.tree == tree and mark.head == head
    if unchanged or (current is not None and current.repeats(tree, context.timeout)):
        code, text, note = _wake_from(context, current, tree)
        note = DELIVERED_NOTE if code == 2 else note
        return (UNCHANGED if unchanged else RECORDED), note, code, text
    held = held_signatures(target, context.session, context.until)
    baseline = checked_for(target, mark.tree, context.until) if mark is not None else None
    turn = _Turn(tree, mark, baseline, held)
    known = known_record(target, context.digest, context.until)
    earlier = _earlier(baseline, context.session, held, target)
    results: list[Result] = []
    keep = mark.tree if mark is not None else None
    # A trusted mark's HEAD is where the turn began, so a turn that commits is read whole.
    base = mark.head if mark is not None and mark.head else "HEAD"
    skipped = skipped_for(target, context.done, context.skip, base, context.until)
    running = [line for line in context.done if line not in skipped]
    try:
        stopping.arm()
        run_all(target, running, context.until, known, earlier, into=results)
        after = tree_digest(target, context.digest, book)
    except Superseded:
        stopping.armed = False
        if results:
            record = _record(context, turn, results, True, SUPERSEDED, skipped)
            remember(target, record, book, keep)
        return SUPERSEDED, "", 0, ""
    stopping.armed = False
    verdict = _verdict(results).lower()
    if after is None:
        drop_fixed(target, known, results, book)
        return verdict, "not remembered: the tree could not be read again in time", 0, ""
    changed = after != tree
    cause = OUTSIDE if changed and _outside(target, context.started, book) else ""
    record = _record(context, turn, results, changed, cause, skipped)
    remember(target, record, book, keep)
    drop_fixed(target, known, results, book)
    if changed:
        return CHANGED, cause, 0, ""
    code, text, note = _wake_from(context, record, tree)
    return verdict, note, code, text


def _stuck(target: Path, context: _Context, tree: str, other: Run | None) -> None:
    path = _state(target, context.book, STUCK)
    if path is None:
        return
    note = {
        "time": now_text(),
        "session": context.session,
        "tree": tree,
        "pid": other.pid if other is not None else 0,
    }
    write_whole(path, json.dumps(note) + "\n")


_READ = object()


@dataclass(frozen=True)
class Entry:
    """What an entry's command names: the row, the row's finish hook, the Done digest and the
    run's limit."""

    harness: str
    hook: Mapping[str, Any]
    digest: str
    timeout: int


def run(
    entry: Entry, payload: dict[str, Any] | None, cwd: Path, *, wake: bool, given: object = _READ
) -> tuple[int, str]:
    """The run: (exit code, report). It runs Done for a turn end and records what it found;
    where `wake`, the row's delivery (claude-code), it is the entry's own process and exits 2
    with the report only on a failure that holds. Without `wake` (codex's detached `--run`) it
    only records; a later stop delivers. `given` is the mark the codex stop read and trusted;
    otherwise the run reads the mark of its session written before its start, trusts it by the
    stop's rules, and stamps it ended."""

    harness, hook, digest, timeout = entry.harness, entry.hook, entry.digest, entry.timeout
    context_start = time.monotonic(), datetime.now(timezone.utc)
    target, found = find_target(payload, cwd)
    done = recorded_done(target) if found else None
    skip = recorded_skip(target) if found else {}
    if not done or done_digest(done, skip) != digest:
        return 0, ""
    context = _Context(
        harness,
        digest,
        done,
        target,
        timeout,
        _session(payload),
        payload is None or payload.get(hook["guard"]) is not False,
        _paused(payload),
        wake,
        *context_start,
        skip,
    )
    gitdir = _gitdir(target, context.until)
    if gitdir is None:
        return 0, ""
    if given is _READ:
        raw = read_mark(target, context.until)
        own = raw if raw is not None and raw.session == context.session else None
        own = own if own is not None and own.written < context.started else None
        if own is not None:
            stamp_mark(target, own, context.until)
        mark = own if own is not None and trusted(harness, own, payload, context.until) else None
    else:
        mark = given if isinstance(given, Mark) else None
    tree = tree_digest(target, digest, context.until)
    head = _head(target, context.until)
    if tree is None or head is None:
        return 0, ""
    try:
        lock = RunLock(gitdir / RUN_LOCK)
    except OSError as error:
        _unlocked(context, gitdir, tree, head, error)
        return 0, ""
    try:
        role, other = acquire(lock, gitdir / RUN, tree)
        if role == STUCK_ROLE:
            _stuck(target, context, tree, other)
            return 0, ""
        if role == FOLLOWER:
            if not follow(lock, context.begun + timeout):
                return 0, ""
            # The follower's own budget may have passed while it waited: the held list is read
            # and written with time of its own, so the holder's hold is seen and not sent twice.
            later = max(context.book, time.monotonic() + REMEMBER_SECONDS)
            record = checked_for(target, tree, later)
            code, text, _ = _wake_from(context, record, tree, later)
            return code, text
        return _as_holder(context, gitdir, tree, head, mark)
    finally:
        lock.close()


def _unlocked(context: _Context, gitdir: Path, tree: str, head: str, error: OSError) -> None:
    """The record of a run that could not open the run lock: ended at once with the error, so the
    person is told and the check is never silent."""

    outcome = f"error: the run lock {RUN_LOCK} cannot be opened: {type(error).__name__}: {error}"
    record = Run(
        os.getpid(),
        tree,
        head,
        context.started,
        context.session,
        None,
        context.digest,
        context.timeout,
        context.guarded,
        {"time": now_text(), "outcome": outcome},
    )
    write_whole(gitdir / RUN, json.dumps(record.document()) + "\n")


def _as_holder(
    context: _Context, gitdir: Path, tree: str, head: str, mark: Mark | None
) -> tuple[int, str]:
    """The run that holds the lock: its record written before any command starts, and its end
    written on every exit it controls, before the lock goes."""

    (gitdir / STUCK).unlink(missing_ok=True)
    shown = {"tree": mark.tree, "time": mark.written.isoformat()} if mark is not None else None
    record = Run(
        os.getpid(),
        tree,
        head,
        context.started,
        context.session,
        shown,
        context.digest,
        context.timeout,
        context.guarded,
    )
    path = gitdir / RUN
    write_whole(path, json.dumps(record.document()) + "\n")
    stopping = _Stopping()
    main = threading.current_thread() is threading.main_thread()
    previous = signal.signal(signal.SIGTERM, stopping) if main else None
    outcome, note, code, text = "error", "", 0, ""
    try:
        outcome, note, code, text = _check(context, stopping, tree, head, mark)
    except Superseded:
        outcome = SUPERSEDED
    except Exception as error:
        outcome = f"error: {type(error).__name__}: {error}"
        code, text = 0, ""
    finally:
        stopping.armed = False
        ended = {"time": now_text(), "outcome": outcome}
        ended |= {"note": note} if note else {}
        write_whole(path, json.dumps(replace(record, ended=ended).document()) + "\n")
        if main and previous is not None:
            signal.signal(signal.SIGTERM, previous)
    return code, text


# --- The codex stop: decide in constant time, start the run, deliver later ---------


def _run_argv(
    entry: Entry, payload: Mapping[str, Any] | None, target: Path, mark: Mark | None
) -> list[str]:
    """The command that starts the detached run: this engine, isolated as the launcher runs it,
    told the stop's input and the mark the stop trusted."""

    # No transcript path: `ps` shows the command line to every account, and the run reads the
    # transcript only where it reads the mark itself, which it never does with `--input`.
    keys = ("session_id", "stop_hook_active", "hook_event_name")
    given: dict[str, Any] = {k: payload[k] for k in keys if payload is not None and k in payload}
    given["cwd"] = str(target)
    given["finish_check_mark"] = mark.document() if mark is not None else None
    return [
        sys.executable,
        "-I",
        "-X",
        "utf8",
        "-c",
        LAUNCH,
        str(ENGINE_ROOT),
        ID,
        "--run",
        "--constant-time",
        "--harness",
        entry.harness,
        "--done",
        entry.digest,
        "--timeout",
        str(entry.timeout),
        "--input",
        json.dumps(given),
    ]


def _given_mark(document: object) -> Mark | None:
    if not isinstance(document, dict):
        return None
    head, tree, session = document.get("head"), document.get("tree"), document.get("session")
    written = stamp(document.get("time"))
    if not (
        isinstance(head, str)
        and HEAD.fullmatch(head)
        and isinstance(tree, str)
        and DIGEST.fullmatch(tree)
        and isinstance(session, str)
        and session
        and written is not None
    ):
        return None
    return Mark(head, tree, session, written)


def _run_notices(
    target: Path, viewer: Viewer, deadline: float | None, from_run: bool
) -> list[Notice]:
    """What the person may be told about the last run: still running on this tree, did not
    finish, ended with an error; and, at a claude-code prompt (`from_run`), that the turn the run
    ended changed nothing, which a codex stop says itself."""

    state, last = run_state(target, deadline)
    if state == DEAD:
        if last is None:
            text = (
                "finish-check UNVERIFIED: the last run did not finish: its record cannot be "
                "read; nothing was held, and no tree was checked."
            )
            return [Notice("", DEAD, text)]
        text = (
            f"finish-check UNVERIFIED: the run that started at {clock_of(last.started.isoformat())}"
            " did not finish: its process is gone, or it outlived its time limit; nothing was "
            "held, and no tree was checked."
        )
        return [Notice(last.tree, DEAD, text)]
    if last is None:
        return []
    when = clock_of(last.started.isoformat())
    if state == LIVE:
        text = f"finish-check: Done is still running on this tree since {when}."
        return [Notice(last.tree, RUNNING, text)] if last.tree == viewer.tree else []
    outcome = (last.ended or {}).get("outcome", "")
    if outcome.startswith("error"):
        text = (
            f"finish-check UNVERIFIED: the run that started at {when} ended without a verdict "
            f"({outcome}); nothing was held."
        )
        return [Notice(last.tree, ERROR, text)]
    if (last.ended or {}).get("note") == UNHELD_NOTE and last.session == viewer.session:
        record = checked_for(target, last.tree, deadline)
        return [_unheld_notice(record, target)] if record is not None and record.results else []
    if from_run and outcome == UNCHANGED and last.session == viewer.session and last.mark:
        if (last.ended or {}).get("note") == DELIVERED_NOTE:
            # The run delivered this failure to the model; the person is not told it was not.
            return []
        record = checked_for(target, last.tree, deadline)
        verdict = _unchanged_verdict(record, last.tree, target)
        text = str(marked_told(verdict, last.mark.get("time", ""), True)["systemMessage"])
        return [Notice(last.tree, UNCHANGED, text)]
    return []


def _stuck_notice(target: Path, deadline: float | None) -> list[Notice]:
    """That the last run could not start, since the run before it would not stop."""

    path = _state(target, deadline, STUCK)
    try:
        note = json.loads(path.read_text(encoding="utf-8")) if path is not None else None
    except (OSError, ValueError):
        return []
    if not (isinstance(note, dict) and isinstance(note.get("time"), str)):
        return []
    text = (
        f"finish-check UNVERIFIED: Done did not start at {clock_of(note['time'])}: the run on "
        f"another tree (process {note.get('pid')}) did not stop within {SUPERSEDE_SECONDS} s of "
        "being asked; nothing was held, and the next turn end tries again."
    )
    return [Notice(str(note.get("tree", "")), STUCK_KIND, text)]


def _shown_records(target: Path, tree: str | None, deadline: float | None) -> list[Checked]:
    """The record of `tree` and the newest record, once each."""

    found: dict[str, Checked] = {}
    for record in (checked_for(target, tree, deadline), last_checked(target, deadline)):
        if record is not None:
            found.setdefault(record.tree, record)
    return list(found.values())


def notices(
    target: Path, viewer: Viewer, deadline: float | None, *, from_run: bool
) -> list[Notice]:
    """What the person may be told at a codex stop or a claude-code prompt (`from_run`): about
    the last run, a run that could not start, and each record's verdict."""

    found = _run_notices(target, viewer, deadline, from_run) + _stuck_notice(target, deadline)
    for record in _shown_records(target, viewer.tree, deadline):
        notice = record_notice(record, viewer, target)
        if notice is not None:
            found.append(notice)
    return found


def _unheld_notice(record: Checked, target: Path) -> Notice:
    """The person's notice of a failure that held where the held list could not be written."""

    verdict = verdict_for(record.results, False, target, record.timeout, why=UNHELD_WHY)
    return Notice(record.tree, UNHELD, str(verdict["systemMessage"]))


def _slow_stop(
    target: Path, viewer: Viewer, own: Mark | None, argv: list[str]
) -> tuple[Verdict, list[str] | None]:
    """A codex stop whose tree read passed its budget: it tells the person once and starts the
    run, which reads the tree with its own."""

    text = (
        f"finish-check UNVERIFIED: the working tree could not be read within {STOP_READ_SECONDS} "
        "s at this stop; the check runs in the background with its own time, and its verdict "
        "comes at a later stop."
    )
    texts = tell(target, viewer.session, [Notice("", SLOW, text)])
    if own is not None:
        stamp_mark(target, own)
    return (told("\n\n".join(texts)) if texts else {}), argv


def _stop_hold(
    target: Path, viewer: Viewer, current: Checked | None, mark: Mark | None, unchanged: bool
) -> Checked | None:
    """The record a codex stop holds for: the check of this tree, at once, where it holds for
    this session; else the record of the tree the turn began on, where a later run of the session
    found its failure again."""

    session, guarded, held = viewer.session, viewer.guarded, viewer.held
    if deliverable(current, session, guarded, False, held, viewer.tree):
        return current
    if mark is None or unchanged:
        return None
    base = checked_for(target, mark.tree)
    return base if confirmed(base, session, guarded, held) else None


def stop(
    entry: Entry, payload: dict[str, Any] | None, cwd: Path
) -> tuple[Verdict, list[str] | None]:
    """The codex stop: (what it prints, the command that starts the run or None). It reads,
    decides and returns within `STOP_TIMEOUT`, its tree read within `STOP_READ_SECONDS`, and
    runs nothing. It holds where a record of this session holds (`_stop_hold`). Otherwise it
    tells the person what they were not yet told, and stamps the turn's mark. It starts the run
    where the tree has no check, the turn changed something, and no run is on it; a tree it could
    not read in time gets the run all the same."""

    deadline = time.monotonic() + STOP_READ_SECONDS
    session = _session(payload)
    guarded = payload is None or payload.get(entry.hook["guard"]) is not False
    target, found = find_target(payload, cwd)
    if not found:
        return told(
            f"finish-check UNVERIFIED: no {MANIFEST} found from {target}; nothing ran."
        ), None
    done = recorded_done(target)
    if not done or done_digest(done, recorded_skip(target)) != entry.digest:
        return told(_digest_text(target)), None
    tree = tree_digest(target, entry.digest, deadline)
    raw = read_mark(target, deadline)
    own = raw if raw is not None and raw.session == session else None
    mark = own if own is not None and trusted(entry.harness, own, payload, deadline) else None
    viewer = Viewer(session, tree, guarded, held_signatures(target, session, deadline))
    if tree is None:
        return _slow_stop(target, viewer, own, _run_argv(entry, payload, target, mark))
    current = checked_for(target, tree, deadline)
    unchanged = mark is not None and mark.tree == tree and mark.head == _head(target, deadline)
    hold = _stop_hold(target, viewer, current, mark, unchanged)
    state, last = run_state(target, deadline)
    running = state == LIVE and last is not None and last.tree == tree
    repeating = current is not None and current.repeats(tree, entry.timeout)
    starts = not unchanged and not repeating and not running
    argv = _run_argv(entry, payload, target, mark) if starts else None
    unheld: list[Notice] = []
    if hold is not None:
        if keep_held(target, session, hold.holding, hold.tree):
            return {"decision": "block", "reason": hold_report(hold, target, both=True)}, argv
        unheld = [_unheld_notice(hold, target)]
    found_notices = unheld + notices(target, viewer, deadline, from_run=False)
    if unchanged and mark is not None:
        verdict = _unchanged_verdict(current, tree, target)
        text = str(marked_told(verdict, mark.written.isoformat(), True)["systemMessage"])
        found_notices = [n for n in found_notices if n.tree != tree or n.kind == RUNNING]
        found_notices.insert(0, Notice(tree, UNCHANGED, text))
    texts = tell(target, session, found_notices)
    if own is not None:
        stamp_mark(target, own)
    return (told("\n\n".join(texts)) if texts else {}), argv


# --- What a person reads ------------------------------------------------------------


def turn_notices(
    target: Path, session: str, tree: str | None, digest: str, deadline: float | None = None
) -> list[str]:
    """The claude-code turn-start entry's message: each notice not yet told to this session,
    since an async stop entry can show the person nothing but its wake. `deadline` is the
    entry's, `MARK_SECONDS` from now by default."""

    deadline = time.monotonic() + MARK_SECONDS if deadline is None else deadline
    done = recorded_done(target)
    if not done or done_digest(done, recorded_skip(target)) != digest:
        return tell(target, session, [Notice("", DIGEST_KIND, _digest_text(target))], deadline)
    viewer = Viewer(session, tree, False, held_signatures(target, session, deadline))
    return tell(target, session, notices(target, viewer, deadline, from_run=True), deadline)


OUTCOMES = {
    "pass": "PASS",
    "fail": "FAIL",
    "unverified": "UNVERIFIED",
    CHANGED: "UNVERIFIED: the tree changed while it ran",
    SUPERSEDED: "stopped from outside before it ended",
    UNCHANGED: "the turn changed nothing; Done was not run",
    RECORDED: "the tree was already checked; Done was not run",
}


def _where(tree: str, current: str | None) -> str:
    return "this tree" if tree == current else "another tree"


def _run_line(state: str, last: Run | None, tree: str | None) -> str:
    """How the last run stands, in one line for the person."""

    if last is None:
        return "run: none recorded" if state == NONE else "run: its record cannot be read"
    about = (
        f"started {clock_of(last.started.isoformat())} on {_where(last.tree, tree)}, process "
        f"{last.pid}, session {last.session}"
    )
    if last.mark:
        about += f", compared with the mark written at {clock_of(last.mark.get('time', ''))}"
    if state == LIVE:
        return f"run: running; {about}"
    if state == DEAD or last.ended is None:
        return f"run: did not finish; {about}"
    outcome = last.ended.get("outcome", "")
    note = f", {last.ended['note']}" if last.ended.get("note") else ""
    ended = clock_of(last.ended.get("time", ""))
    return f"run: ended {ended}: {OUTCOMES.get(outcome, outcome)}{note}; {about}"


def _record_text(record: Checked, viewer: Viewer, target: Path) -> str:
    """A record's verdict for the person: what they would be told, else its report."""

    notice = record_notice(record, viewer, target)
    if notice is not None:
        return notice.text
    if record.holding:
        return hold_report(record, target)
    if record.verdict == PASS:
        return _pass_text(record) if record.results else ""
    return str(verdict_for(record.results, False, target, record.timeout)["systemMessage"])


def status(folder: Path) -> str:
    """What `--status` prints, read-only: the last run (running since, ended and how, or did not
    finish), each notice it leaves, and the record of the current tree and the newest record,
    each with its verdict and its report."""

    target, found = find_target(None, folder)
    if not found:
        return f"finish-check UNVERIFIED: no {MANIFEST} found from {target}; nothing ran.\n"
    done = recorded_done(target) or []
    tree = tree_digest(target, done_digest(done, recorded_skip(target))) if done else None
    state, last = run_state(target)
    session = last.session if last is not None else None
    guarded = last.guarded if last is not None else False
    viewer = Viewer(session, tree, guarded, held_signatures(target, session))
    lines = [f"finish-check status of {paths.shell_path(target)}", _run_line(state, last, tree)]
    told_kinds = (DEAD, RUNNING, ERROR, STUCK_KIND, UNCHANGED, UNHELD)
    shown = notices(target, viewer, None, from_run=True)
    lines += [notice.text for notice in shown if notice.kind in told_kinds]
    records = _shown_records(target, tree, None)
    for record in records:
        by = f"session {record.session}" if record.session else "adopt's measurement"
        when = clock_of(record.time) if record.time else "an earlier engine"
        where = _where(record.tree, tree)
        lines.append(f"record: {record.kind} {record.verdict} for {where}, at {when}, by {by}")
        lines.append(_record_text(record, viewer, target))
    if not records:
        lines.append("record: none for this tree")
    return "\n".join(line for line in lines if line) + "\n"


# --- Command line ----------------------------------------------------------------

DESCRIPTION = """\
Run at a harness's stop hook, from the entry `outcomebound adopt --finish-check` writes. It reads
the hook's JSON input on stdin, finds the target (the nearest directory holding
.outcomebound/manifest.json upward from the input's cwd, else from its own), and checks the
manifest's Done commands, only while their digest is --done. No turn end waits for Done. On a row
whose harness table entry has a wake (claude-code, asyncRewake) the entry runs in the background
and is the run: it runs Done from the target's root, in order, stopping at the first that does
not pass and 30 seconds before --timeout, and exits 2 with the report on stderr only on a failure
that holds; on every other end it exits 0 and prints nothing. On any other row (codex) the stop
reads, decides and prints its JSON within 30 seconds, then starts the run detached; a later stop
delivers what the run found: a failure as decision block, everything else to the person as
systemMessage.

A tree already checked runs nothing. A known failure (adopt measured it) holds nothing. A failure
goes to the model at most once for each signature in a session, only from a run of that session,
and never where the tree the turn began with had it and another session recorded it or this
session was held for it. A pass, a failure told and not held, a run that did not finish and each
UNVERIFIED go to the person once for each session, tree and kind: on codex at the stop, on
claude-code through the turn-start entry.

With --mark it runs at a turn's first prompt instead: it keeps the target's HEAD and working tree
in the Git directory and exits 0 whatever goes wrong; on claude-code it prints the person's
untold notices as systemMessage, and nothing else. With --status [FOLDER] it prints the last run
and the record of the current tree, writes nothing and exits 0."""
EPILOG = """\
exit: 0 whenever it ran (its verdict as JSON on stdout at a codex stop); 2 only where a claude-code
run holds a failure, its report on stderr; 1 on a usage error, never 2."""


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        self.print_usage(sys.stderr)
        self.exit(1, f"{self.prog}: {message}\n")


def _parser() -> argparse.ArgumentParser:
    parser = _Parser(
        prog=f"outcomebound {ID}",
        description=DESCRIPTION,
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--harness", required=True, help="the harness-table row whose hook runs this"
    )
    parser.add_argument(
        "--done", required=True, metavar="DIGEST", help="the digest of the Done list it runs"
    )
    parser.add_argument(
        "--mark",
        action="store_true",
        help="at a turn's first prompt: keep the commit and tree the turn begins with, print "
        "only the person's notices (claude-code) and exit 0 whatever goes wrong",
    )
    parser.add_argument(
        "--constant-time",
        action="store_true",
        help="the entry of the constant-time stop; an engine from before it refuses the entry",
    )
    parser.add_argument("--run", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--input", default="", help=argparse.SUPPRESS)
    parser.add_argument(
        "--timeout",
        type=_seconds,
        default=DEFAULT_TIMEOUT,
        metavar="SECONDS",
        help=f"the run's limit, which the commands stop {MARGIN_SECONDS} seconds before; "
        f"default {DEFAULT_TIMEOUT}, the value entries written without it carry",
    )
    return parser


def _seconds(text: str) -> int:
    try:
        value = int(text)
    except ValueError:
        value = 0
    if not admits_timeout(value):
        raise argparse.ArgumentTypeError(f"whole seconds above {MARGIN_SECONDS}, not {text!r}")
    return value


def _begin(words: Sequence[str]) -> int:
    """The `--mark` mode: what a prompt must never fail on, so every error ends as exit 0 with
    nothing printed and nothing written. On a row whose delivery is a wake it prints the
    person's untold notices as one `systemMessage`, and nothing else."""

    with contextlib.suppress(Exception, SystemExit):
        with contextlib.redirect_stderr(io.StringIO()):
            args = _parser().parse_args(words)
        row = adapters.table().get(args.harness)
        payload = read_input(getattr(sys.stdin, "buffer", None))
        session = prompt_input(row, payload) if DIGEST.fullmatch(args.done) else None
        if session is None:
            return 0
        # One budget for the whole entry, within the harness's timeout for it.
        deadline = time.monotonic() + MARK_SECONDS
        began = begin_turn(args.done, payload, Path.cwd(), session, deadline)
        hook = hook_of(row)
        if began is None or hook is None or not isinstance(hook.get("wake"), dict):
            return 0
        target, tree = began
        if tree is None:
            tree = tree_digest(target, args.done, deadline)
        texts = turn_notices(target, session, tree, args.done, deadline)
        if texts:
            sys.stdout.write(json.dumps({"systemMessage": "\n\n".join(texts)}) + "\n")
            sys.stdout.flush()
    return 0


def _status(words: Sequence[str]) -> int:
    rest = [word for word in words if word != "--status"]
    if len(rest) > 1 or (rest and rest[0].startswith("-")):
        sys.stderr.write(f"usage: outcomebound {ID} --status [FOLDER]\n")
        return 1
    folder = Path(native_path(rest[0])) if rest else Path.cwd()
    try:
        sys.stdout.write(status(folder))
    except Exception as error:
        sys.stdout.write(
            f"finish-check status: could not be read: {type(error).__name__}: {error}\n"
        )
    sys.stdout.flush()
    return 0


def _close_stdout() -> None:
    """Close standard output, so that the harness reads the stop's JSON to its end before the
    run starts: the stream, and the descriptor under it, which is pointed at the null device."""

    with contextlib.suppress(Exception):
        stream = sys.stdout
        try:
            number: int | None = stream.fileno()
        except (OSError, ValueError, io.UnsupportedOperation):
            number = None
        stream.flush()
        stream.close()
        if number is not None:
            devnull = os.open(os.devnull, os.O_WRONLY)
            os.dup2(devnull, number)
            os.close(devnull)


def _detached(entry: Entry, given: str) -> int:
    """The `--run` mode a codex stop starts: the run, with the stop's input and the mark the stop
    trusted in `given`. Nobody reads what it prints, so it prints nothing and exits 0."""

    try:
        payload = json.loads(given)
    except ValueError:
        payload = None
    payload = payload if isinstance(payload, dict) else None
    mark = _given_mark(payload.pop("finish_check_mark", None)) if payload else None
    with contextlib.suppress(Exception):
        run(entry, payload, Path.cwd(), wake=False, given=mark)
    return 0


def _woken(entry: Entry, payload: dict[str, Any] | None) -> int:
    """The entry on a row whose delivery is a wake: the run, which exits 2 with the report on
    standard error only on a failure that holds, and otherwise prints nothing on either
    stream, since an async hook's output reaches the model on its next turn."""

    try:
        code, text = run(entry, payload, Path.cwd(), wake=True)
    except Exception:
        return 0
    if code == 2:
        sys.stderr.write(text + "\n")
        sys.stderr.flush()
    return code


def main(argv: Sequence[str] | None = None) -> int:
    words = list(sys.argv[1:] if argv is None else argv)
    if "--mark" in words:
        return _begin(words)
    if "--status" in words:
        return _status(words)
    parser = _parser()
    args = parser.parse_args(words)
    try:
        hook = hook_of(adapters.table().get(args.harness))
    except adapters.AdapterError as error:
        parser.error(str(error))
    if hook is None:
        parser.error(f"{args.harness}: not available yet: {unavailable(args.harness)}")
    if not DIGEST.fullmatch(args.done):
        parser.error("--done takes the 64-character digest adopt wrote")
    entry = Entry(args.harness, hook, args.done, args.timeout)
    if args.run:
        return _detached(entry, args.input)
    payload = read_input(getattr(sys.stdin, "buffer", None))
    if isinstance(hook.get("wake"), dict):
        return _woken(entry, payload)
    try:
        verdict, start = stop(entry, payload, Path.cwd())
    except Exception:
        # A stop must never fail the turn end: nothing for the model, nothing started.
        verdict, start = {}, None
    sys.stdout.write(json.dumps(verdict) + "\n")
    sys.stdout.flush()
    _close_stdout()
    if start is not None:
        target, _ = find_target(payload, Path.cwd())
        with contextlib.suppress(OSError):
            programs.start_detached(start, cwd=target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
