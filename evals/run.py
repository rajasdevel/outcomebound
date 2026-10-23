#!/usr/bin/env python3
"""Measure whether the OutcomeBound kernel, and the skills an install carries, change what a
model does.

A run builds each fixture's disposable repository, hands a harness (`codex exec` or `claude -p`)
one arm's kernel and the fixture's task, and judges what the model left with the fixture's
deterministic post-checks, run through `outcomebound_tools.validation`. The post-checks are the
verdict. The graders never enter the workspace: a fixture's setup writes them to a grading stage
outside it, the runner seals the stage and the grading files before the call and checks them
after it, and the post-checks run from a sealed copy kept with the run, which `--regrade` uses
too. The model, effort and working directory a call counts for are the ones the harness's own
session record states, never the ones requested (evals/harnesses/__init__.py).

Four arms: `earlier`, an earlier wording of the operating-contract kernel, kept in
`evals/arms/earlier-kernel.md`; `current`,
what `outcomebound adopt --harness codex` installs from this checkout: the kernel rendered as
adopt renders it, at codex's skill path the whole folder of each skill that install carries
(the fourteen every install carries), and this
checkout's launcher first on the call's PATH; `unsized`, the current arm without the kernel's
sizing paragraph, which asks whether that paragraph earns its place; and `none`, no kernel,
skill or launcher, each fixture's note without its pointer to the core skill. The `earlier`
arm can also be the install of a Git ref (`--earlier-ref`) or another guidance set's own files
(`--earlier-verbatim`), and `--arm-label` names it in the records. The model is
always named and passed to codex, so codex's configured default never runs.

On a fixture whose install adopt makes (an `install.json`), an element arm measures one part of
the install: `--drop` takes elements from the current arm, `--add` puts elements into the none
arm, and `--edits` changes the installed text; each is built from adopt's own install, with no
model call, and `--dump-arm` shows it.

No run bills an API key from the environment: every credential and endpoint override a
CLI reads there is removed from each child, and preflight must observe a subscription login (a
ChatGPT login for codex, a Claude subscription for Claude Code). A credential kept in codex's own
files is invisible here.

`--harness claude-code` runs each call with `claude -p` (evals/harnesses/claude_code.py): the
current arm is then what `outcomebound adopt --harness claude-code` installs (the skills at
`.claude/skills/`), each call gets a fresh home and config folder, and `--plugin-dir` adds a plugin
from a pinned clone under the evals home's `third-party/` folder.

A suite-v2 fixture (`v2-<id>`, run only when named) has a `suite.json`: its tier, the budget
its call is stopped at (input cap, timeout), the runner-owned stubs its call finds first on
PATH (`evals/stub_place.py`) and the workspace paths hashed about once a second while the call
runs (`evals/watch.py`). A call stopped at its budget is graded, and counts as a failure; only a
runner fault voids a run. `--rescore` scores copies of kept workspaces with a fixture's current
graders, beside the original verdicts, which it never changes.

Standard library only, and outside outcomebound_tools: this calls a real model.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path, PurePosixPath
from typing import Any, NamedTuple

# Direct script execution also needs the repository package path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evals import stub_place
from evals.claude_stream import above as claude_above
from evals.claude_stream import (
    expected_records,
    expected_start,
    leaked_records,
    leaked_start,
    loading_check,
    reach_rows,
    shown_env,
)
from evals.claude_stream import failed as failed_rows
from evals.codex_events import (
    COST_KEYS,
    command_transcript,
    observed_model,
    session_tokens,
    tokens_used,
    with_outputs,
)
from evals.evidence import (
    changed,
    grading_digest,
    grading_hashes,
    seal,
    sealed_changes,
    tree_digest,
    tree_hashes,
    workspace_digest,
)
from evals.harnesses import SERVICE_TIER, Budget, Request
from evals.harnesses.claude_code import ClaudeCodeHarness, cell_for, unreadable
from evals.harnesses.codex import CodexHarness, catalog
from evals.native_commands import fill_directories
from evals.native_receipts import parse_records
from evals.processes import bounded_command, partial_output
from evals.watch import Watcher

# The stream decoders the graders' tests read through this module.
__all__ = ["command_transcript", "observed_model"]

REPO = Path(__file__).resolve().parent.parent
FIXTURES = REPO / "evals" / "fixtures"
# A fixture's own file naming the fragments its install selects, one id a line.
FRAGMENTS_FILE = "fragments"
# A fixture's own `install.json` (the replica fixtures have one): the Done commands its install
# records, the fragments it selects and the sandbox of its call, `eval` (the task-note folder
# `.agents/work` granted) or `field` (as an adopter's call runs: `.agents` stays read-only).
INSTALL_FILE = "install.json"
INSTALL_KEYS = ("done", "fragments", "sandbox")
SANDBOXES = ("eval", "field")
# A fixture's own empty file (a comment may explain it) that marks it as needing a local listener:
# the run lets the model's commands bind a port, for this fixture only.
LISTENER_FILE = "local-listener"
# A fixture's own script printing its task for the built workspace, in place of a fixed
# prompt.md: what it prints can name the seed commit, which exists only once the build is done.
TASK_SCRIPT = "task.sh"
# The hand-off fixtures measure a hand-off package on a named implementer, not the kernel, so
# they run only when --fixtures names them.
NAMED_ONLY = (
    "handoff-",
    "lifecycle-",
    "adopt-",
    "clause-",
    "explain-mismatch",
    "review-close-after-check",
    "patch-validation",
    "property-oracles",
    "testing-no-work",
    "new-project-",
    "onboard-",
    "skill-",
    "business-requirements-",
    "field-",
    "scaffold-",
    "replica-",
    "v2-",
)
# A suite-v2 fixture's own `suite.json`. The runner reads its `tier`, its `budget`
# (`input_cap`, the input tokens with the cached among them that the call's session may pass,
# and `timeout_seconds`), its `stubs` (runner-owned stubs, by name, from `evals/stubs/`) and its
# `watch` paths (workspace-relative files hashed about once a second during the call); its other
# keys are for the self-test and the panel. No cap and CALL_TIMEOUT where the budget names none.
SUITE_FILE = "suite.json"
TIERS = ("XS", "S", "M", "L")
# What the checks of a run read, besides the workspace and the transcript: the call's budget
# record, the watch log, and the stubs' folder and digests (`evals/stub_place.py`). A variable
# that is absent was not recorded for the run.
BUDGET_ENV = "OB_EVAL_BUDGET"
WATCH_LOG_ENV = "OB_EVAL_WATCH_LOG"
# The fixtures whose runs compare an install with no guidance on work like an adopter's: nothing
# a call reads from its Codex home or above its workspace may name OutcomeBound or give it
# instructions, so that neither arm reads more of either than its fixture and its install. The
# operator's own skills and agent roles, which both arms read alike, are recorded, not refused.
CLEAN_HOME = ("replica-",)
RAW = REPO / "evals" / "results" / "raw"
TEMPLATE = "templates/managed-block.agents.md.tmpl"
LAUNCHER = "scripts/outcomebound"
# The harness whose install the current arm mirrors, and the one `--harness` takes by default.
HARNESS = "codex"
CLAUDE = "claude-code"
HARNESSES = (HARNESS, CLAUDE)
# The harness this run installs for: `--harness` sets it, and the current arm is what
# `outcomebound adopt --harness <it>` installs, at its skill path.
INSTALL_HARNESS = HARNESS
# Where a plugin an arm adds must come from: a pinned clone in the private evals home's
# `third-party/` folder, never a person's plugin cache.
THIRD_PARTY = "third-party"
# An earlier wording of the kernel, kept as a file so the arm runs in any checkout.
EARLIER = "earlier"
EARLIER_KERNEL = REPO / "evals" / "arms" / "earlier-kernel.md"
# `--earlier-ref REF` makes the earlier arm a full install of the engine at that Git ref (its
# kernel, its skills, its fragments), in place of the kernel wording kept in EARLIER_KERNEL.
EARLIER_REF = ""
_EARLIER_SOURCE: dict[str, Path] = {}
# `--earlier-verbatim DIR` makes the earlier arm another guidance set's own files: the AGENTS.md
# and the skills/ folders of DIR, a folder outside this checkout, installed as they are. The
# AGENTS.md heads the fixture's own AGENTS.md; nothing of OutcomeBound is added: no kernel, facts
# block, pointer or launcher.
EARLIER_VERBATIM = ""
_VERBATIM: dict[str, tuple[str, dict[str, bytes]]] = {}
# The files a fixture's setup wrote, by built workspace, as `as_installed` found them before any
# install: the fixture's own, such as a declared ticket store under `.outcomebound/`.
_FIXTURE_FILES: dict[Path, frozenset[str]] = {}
# The kernel-off arm: the task alone, in a fixture that carries no OutcomeBound text.
NONE = "none"
# The current arm less the kernel's sizing paragraph, the one that opens with this phrase.
UNSIZED = "unsized"
SIZING = "Satisfy all four completely"
# Where a fixture's skill copies live: the path its note names, Claude Code's skill path and
# codex's skill path (the last stays last: element checks name a pointer line under it).
SKILL_ROOTS = (".outcomebound/skills/", ".claude/skills/", ".agents/skills/")
# The facts-only arm: the fixture's own note, then what `outcomebound adopt --facts-only`
# installs for the harness: the project-facts block, the local fragment inline where the fixture
# selects it, and the skills where the harness lists skills itself; no kernel and no pointer.
FACTS_ONLY = "facts-only"
# The bare arm: no instruction file at all, the fixture's own note among them, and no
# OutcomeBound file. Its fixture is built as the none arm's, then loses every file named below.
BARE = "bare"
ARMS = (EARLIER, "current", UNSIZED, NONE, FACTS_ONLY, BARE)
# The arms whose fixture's setup runs as the none arm's: no core skill, no pointer to it.
NOTE_ONLY = (NONE, FACTS_ONLY, BARE)
# What the bare arm removes after the fixture's setup: each file of these names at any depth
# (codex reads the first two, Claude Code the others and AGENTS.md, from `.claude/` too), each
# `.claude/rules` folder at any depth, and at the workspace's root each skill root and the
# fragment folder. A nested Git repository, the subject of a fixture's task, keeps its own.
BARE_NAMES = ("AGENTS.md", "AGENTS.override.md", "CLAUDE.md", "CLAUDE.local.md")
BARE_FOLDER = ".claude/rules"
BARE_ROOTS = (*SKILL_ROOTS, ".outcomebound/fragments/")
# The arms that stand for an install: their fixtures carry what adopt writes into AGENTS.md.
INSTALLED = ("current", UNSIZED)
# A fixture note's own pointer to the core skill, which an install replaces with its pointers.
NOTE_POINTER = re.compile(
    r"\s*Read `\.outcomebound/skills/using-outcomebound/SKILL\.md` before planning work here\."
)
# A run is one repetition of its fixtures; a measurement takes three, a confirmation more.
REPETITIONS = tuple(range(1, 11))
MEASURED = 3
# The elements of an adopted install that `--drop` takes from the current arm and `--add` puts
# into the none arm: the three blocks adopt writes into AGENTS.md (the guidance-pointers block
# whole: its read-once line and every pointer line), each fragment and each skill (its file or
# folder and its pointer line), and this checkout's launcher first on the call's PATH.
KERNEL_ELEMENT, FACTS_ELEMENT, POINTERS_ELEMENT = "kernel", "facts", "pointers"
LAUNCHER_ELEMENT = "launcher"
ELEMENT = re.compile(r"kernel|facts|pointers|launcher|(?:fragment|skill):[a-z0-9][a-z0-9-]*")
# A pointer line of the guidance-pointers block, and the file it names.
POINTER_LINE = re.compile(r"^- .+: read (\S+)$")
# The elements that own a pointer line.
LINED = ("fragment:", "skill:")
# The note an install writes its blocks into, and the only installed file besides the skills and
# fragments that `--edits` may change.
NOTE = "AGENTS.md"

# Every variable a supported CLI reads for a credential, or for routing a call somewhere
# other than the subscription endpoint: an override bills a metered endpoint without ever
# naming a key. The model's own commands inherit this environment too.
STRIPPED_KEYS = (
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
    "ANTHROPIC_BASE_URL",
    "ANTHROPIC_CUSTOM_HEADERS",
    "CODEX_ACCESS_TOKEN",
    "CODEX_API_KEY",
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
)
STRIPPED_PREFIXES = ("ANTHROPIC_BEDROCK_", "ANTHROPIC_VERTEX_", "CLAUDE_CODE_USE_")
STRIP_POLICY = tuple(sorted(STRIPPED_KEYS + tuple(f"{p}*" for p in STRIPPED_PREFIXES)))

PREFLIGHT_EXIT = 3
CALL_TIMEOUT = 900
SETUP_TIMEOUT = 300
POST_CHECK_TIMEOUT = 600
# Fixture repositories are kept after a run, for the operator to inspect what the model did.
# With a root, each is `<root>/<run directory name>/<fixture>-r<repetition>`; the root is
# `--workspace-root`, else `$OUTCOMEBOUND_EVAL_ROOT`, else `$OUTCOMEBOUND_FIXTURE_ROOT`.
EVAL_ROOT_ENV = "OUTCOMEBOUND_EVAL_ROOT"
FIXTURE_ROOT_ENV = "OUTCOMEBOUND_FIXTURE_ROOT"
# A fixture is judged by Git comparisons, so an operator's global or system Git config
# (hooksPath, excludesFile, an alias) must not reach the child that builds or checks it.
HERMETIC_GIT = {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
# The `seed` tag lives in a workspace the model can write to, so the runner reads the seed
# once, before the model runs, and hands that commit to the checks.
SEED_SHA_ENV = "OUTCOMEBOUND_SEED_SHA"
TRANSCRIPT_ENV = "OUTCOMEBOUND_EVAL_TRANSCRIPT"
# Where a post-check finds what stays outside the workspace: the run's sealed copy of its
# graders (`<fixture>.graders/`, holding `checks/` and a copy of the grading files under
# `evals/`), and the `evals/` folder inside it.
GRADER_DIR_ENV = "OUTCOMEBOUND_GRADER_DIR"
EVAL_DIR_ENV = "OUTCOMEBOUND_EVAL_DIR"
# A temporary folder outside the workspace, where a fixture's setup writes its graders, and the
# end of the name of the sealed copy that the run keeps of them beside its other files.
STAGE_PREFIX = "ob-graders-"
SEALED_SUFFIX = ".graders"
ANSWER_ENV = "OUTCOMEBOUND_EVAL_ANSWER"
CLAIM_LINE = re.compile(r"^(PASS|FAIL|UNVERIFIED) (\S+) \[", re.MULTILINE)
OBSERVED = "observed: "
# The error a record from before the budget record kept for a call that ran past its time.
TIMED_OUT = re.compile(r" call timed out after ")


def fixture_names() -> list[str]:
    return sorted(path.name for path in FIXTURES.iterdir() if (path / "setup.sh").is_file())


def default_fixtures() -> list[str]:
    """The fixtures a run takes when --fixtures names none: all but the named-only ones."""

    return [name for name in fixture_names() if not name.startswith(NAMED_ONLY)]


def selected_fragments(name: str) -> tuple[str, ...]:
    """The fragments the fixture's install selects: its `fragments` file, one id a line, `#`
    starting a comment; none where it has no such file."""

    path = FIXTURES / name / FRAGMENTS_FILE
    if not path.is_file():
        return ()
    ids = (line.split("#", 1)[0].strip() for line in path.read_text("utf-8").splitlines())
    return tuple(item for item in ids if item)


class Install(NamedTuple):
    """What a fixture's install records: the Done commands, in run order, as `adopt --done`
    takes them; the fragments it selects; the sandbox of its call; and whether the `current`
    arm is installed by the engine's own adopt, as in the field (an install.json says so)."""

    done: tuple[str, ...] = ()
    fragments: tuple[str, ...] = ()
    sandbox: str = "eval"
    adopted: bool = False


class InstallError(ValueError):
    """A fixture's install.json that the runner refuses; the message names what is wrong."""


def _install_list(document: dict[str, Any], key: str) -> tuple[str, ...]:
    """The list of strings `key` names: each one line, not blank, with no surrounding space and
    no duplicate."""

    values = document[key]
    if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
        raise InstallError(f"{key} is a list of strings")
    for value in values:
        if not value.strip() or value != value.strip() or "\n" in value or "\r" in value:
            raise InstallError(f"{key}: {value!r} is not one line with no surrounding space")
    if len(set(values)) != len(values):
        raise InstallError(f"{key} names an item twice")
    return tuple(values)


def fixture_install(name: str) -> Install:
    """The fixture's install: its `install.json`, checked whole, or, where it has none, no Done
    command, the fragments its `fragments` file names and the `eval` sandbox. InstallError where
    the file is not exactly `{"done": [...], "fragments": [...], "sandbox": "eval"|"field"}`,
    where a Done command is one `adopt --done` refuses or a fragment one the engine does not ship,
    or where the fixture names its fragments in both files."""

    path = FIXTURES / name / INSTALL_FILE
    if not path.is_file():
        return Install((), selected_fragments(name), "eval")
    if (FIXTURES / name / FRAGMENTS_FILE).exists():
        raise InstallError(f"{FRAGMENTS_FILE} and {INSTALL_FILE} both name fragments; keep one")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as problem:
        raise InstallError(f"not readable JSON: {problem}") from None
    if not isinstance(document, dict) or sorted(document) != sorted(INSTALL_KEYS):
        keys = sorted(document) if isinstance(document, dict) else type(document).__name__
        raise InstallError(f"an object with exactly {', '.join(INSTALL_KEYS)}; found {keys}")
    done, chosen = _install_list(document, "done"), _install_list(document, "fragments")
    if document["sandbox"] not in SANDBOXES:
        raise InstallError(f"sandbox is {' or '.join(SANDBOXES)}, not {document['sandbox']!r}")
    from outcomebound_tools import adopt, fragments

    try:
        if list(done) != adopt._commands(done):
            raise InstallError("a Done command adopt would change")
        if chosen:
            fragments.select(fragments.load_all(REPO), chosen)
    except (adopt.AdoptError, fragments.FragmentError) as problem:
        raise InstallError(str(problem)) from None
    return Install(done, chosen, document["sandbox"], True)


class Suite(NamedTuple):
    """What a fixture's `suite.json` asks of the runner: its tier, the input cap (None: no cap)
    and the timeout of its call (None: CALL_TIMEOUT), the stubs its call finds first on PATH,
    the workspace paths watched during the call, and the file's SHA-256."""

    tier: str
    input_cap: int | None
    timeout: float | None
    stubs: tuple[str, ...]
    watch: tuple[str, ...]
    sha256: str


class SuiteError(ValueError):
    """A fixture's suite.json that the runner refuses; the message names what is wrong."""


def _suite_names(document: dict[str, Any], key: str) -> tuple[str, ...]:
    values = document.get(key, [])
    if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
        raise SuiteError(f"{key} is a list of strings")
    if len(set(values)) != len(values):
        raise SuiteError(f"{key} names an item twice")
    return tuple(values)


def _suite_budget(document: dict[str, Any]) -> tuple[int | None, float | None]:
    budget = document.get("budget", {})
    if not isinstance(budget, dict):
        raise SuiteError("budget is an object")
    cap, seconds = budget.get("input_cap"), budget.get("timeout_seconds")
    if cap is not None and (type(cap) is not int or cap <= 0):
        raise SuiteError(f"budget.input_cap is a positive whole number of tokens, not {cap!r}")
    if seconds is not None and (
        isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or seconds <= 0
    ):
        raise SuiteError(f"budget.timeout_seconds is a positive number, not {seconds!r}")
    return cap, float(seconds) if seconds is not None else None


def fixture_suite(name: str) -> Suite | None:
    """The fixture's `suite.json` as the runner reads it, or None where it has none. SuiteError
    where it is not a JSON object, its tier is not one of TIERS, its budget names a cap or a
    timeout that is not positive, it names a stub that `evals/stubs/` cannot give, or a watch
    path that is not workspace-relative."""

    path = FIXTURES / name / SUITE_FILE
    if not path.is_file():
        return None
    try:
        raw = path.read_bytes()
        document = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as problem:
        raise SuiteError(f"not readable JSON: {problem}") from None
    if not isinstance(document, dict):
        raise SuiteError("not a JSON object")
    if document.get("tier") not in TIERS:
        raise SuiteError(f"tier is one of {', '.join(TIERS)}, not {document.get('tier')!r}")
    cap, seconds = _suite_budget(document)
    stubs, watch = _suite_names(document, "stubs"), _suite_names(document, "watch")
    try:
        stub_place.check(stubs, stub_source())
    except stub_place.StubError as problem:
        raise SuiteError(f"stubs: {problem}") from None
    for item in watch:
        relative = PurePosixPath(item)
        if relative.is_absolute() or ".." in relative.parts or relative.as_posix() != item:
            raise SuiteError(f"watch: {item!r} is not a workspace-relative path")
    return Suite(document["tier"], cap, seconds, stubs, watch, hashlib.sha256(raw).hexdigest())


def stub_source() -> Path:
    """The folder the stubs are placed from: `stubs/` beside the fixtures' folder."""

    return evals_dir() / "stubs"


def needs_local_listener(name: str) -> bool:
    """Whether the fixture has a `local-listener` file: its task starts a service on a port."""

    return (FIXTURES / name / LISTENER_FILE).is_file()


def evals_dir() -> Path:
    """The `evals/` folder the fixtures and graders are read from."""

    return FIXTURES.parent


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _stripped(name: str) -> bool:
    return name in STRIPPED_KEYS or name.startswith(STRIPPED_PREFIXES)


def child_env() -> dict[str, str]:
    """The environment every child gets: this one, less each metered credential and override."""

    return {name: value for name, value in os.environ.items() if not _stripped(name)}


def fixture_setup_env() -> dict[str, str]:
    """Keep fixture Git isolated, but retain caller config for read-only source access."""

    caller = child_env()
    return {
        **caller,
        **HERMETIC_GIT,
        "OUTCOMEBOUND_SOURCE_GIT_CONFIG": json.dumps(
            {key: caller.get(key) for key in HERMETIC_GIT}
        ),
    }


def stripped_from_environment() -> list[str]:
    """The names this run actually removed: the policy acted, beside the policy declared."""

    return sorted(name for name in os.environ if _stripped(name))


def _run(command: list[str], cwd: Path | None = None) -> tuple[int | None, str, str]:
    """A command's exit status, stdout and stderr; one that cannot start has status None."""

    try:
        done = subprocess.run(
            command,
            capture_output=True,
            text=True,
            cwd=cwd,
            env=child_env(),
            timeout=60,
            encoding="utf-8",
        )
    except (OSError, subprocess.SubprocessError) as problem:
        return None, "", f"{command[0]}: {type(problem).__name__}: {problem}"
    return done.returncode, done.stdout, done.stderr


def earlier_source() -> Path:
    """The engine tree at EARLIER_REF, exported once from this checkout's Git objects."""

    if EARLIER_REF in _EARLIER_SOURCE:
        return _EARLIER_SOURCE[EARLIER_REF]
    target = Path(tempfile.mkdtemp(prefix="ob-earlier-source-"))
    archive = subprocess.run(
        [
            "git",
            "-C",
            str(REPO),
            "archive",
            EARLIER_REF,
            "VERSION",
            "templates",
            "skills",
            "fragments",
            "adapters",
        ],
        capture_output=True,
    )
    if archive.returncode != 0:
        raise SystemExit(
            f"run: --earlier-ref {EARLIER_REF}: {archive.stderr.decode(errors='replace').strip()}"
        )
    unpacked = subprocess.run(
        ["tar", "-x", "-C", str(target)], input=archive.stdout, capture_output=True
    )
    if unpacked.returncode != 0:
        raise SystemExit(f"run: --earlier-ref {EARLIER_REF}: the export did not unpack")
    _EARLIER_SOURCE[EARLIER_REF] = target
    return target


def ref_commit(ref: str) -> str:
    """The commit a Git ref of this checkout names now, for the run's record: a branch moves."""

    done = subprocess.run(
        ["git", "-C", str(REPO), "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if done.returncode != 0 or not done.stdout.strip():
        raise SystemExit(f"run: --earlier-ref {ref}: not a Git ref of this checkout")
    return done.stdout.strip()


def earlier_commit() -> str | None:
    """The commit that the earlier arm's ref names, or None where the arm names no ref."""

    return ref_commit(EARLIER_REF) if EARLIER_REF else None


def verbatim_guidance() -> tuple[str, dict[str, bytes]]:
    """The AGENTS.md text of the folder EARLIER_VERBATIM names, and every file under its skills/
    by its path inside skills/, bytes as they are. Each skill is a folder with a SKILL.md. The
    folder must lie outside this checkout: another project's files are never committed here."""

    if EARLIER_VERBATIM in _VERBATIM:
        return _VERBATIM[EARLIER_VERBATIM]
    root = Path(EARLIER_VERBATIM).resolve()
    refusal = ""
    if REPO in (root, *root.parents):
        refusal = "the folder is inside this checkout"
    elif not (root / "AGENTS.md").is_file() or not (root / "AGENTS.md").read_bytes().strip():
        refusal = "no non-empty AGENTS.md"
    skills: dict[str, bytes] = {}
    for path in sorted((root / "skills").rglob("*")) if not refusal else ():
        if path.is_symlink():
            refusal = f"{path.relative_to(root)} is a link"
        elif path.is_file():
            skills[path.relative_to(root / "skills").as_posix()] = path.read_bytes()
    names = {path.split("/")[0] for path in skills}
    lacking = sorted(name for name in names if f"{name}/SKILL.md" not in skills)
    if not refusal and (not names or lacking):
        refusal = "no skills/<name>/SKILL.md" + (f" for {', '.join(lacking)}" if lacking else "")
    if refusal:
        raise SystemExit(f"run: --earlier-verbatim {EARLIER_VERBATIM}: {refusal}")
    agents = (root / "AGENTS.md").read_bytes().decode("utf-8")
    _VERBATIM[EARLIER_VERBATIM] = (agents, skills)
    return _VERBATIM[EARLIER_VERBATIM]


def verbatim_install(arm: Arm | str) -> bool:
    """Whether the arm is the earlier arm as another guidance set's own files."""

    return (arm if isinstance(arm, str) else arm.name) == EARLIER and bool(EARLIER_VERBATIM)


def earlier_install(arm: Arm) -> bool:
    """Whether the arm is the earlier arm as an install of EARLIER_REF."""

    return arm.name == EARLIER and bool(EARLIER_REF)


def kernel(arm: str) -> str:
    """The arm's operating-contract block, sentinels included, as the model receives it; the
    kernel-off arm's is empty."""

    if arm in NOTE_ONLY or verbatim_install(arm):
        return ""
    if arm == EARLIER and not EARLIER_REF:
        return EARLIER_KERNEL.read_text(encoding="utf-8").strip("\n")
    from outcomebound_tools import adopt

    try:
        text = adopt.kernel_block(earlier_source() if arm == EARLIER else REPO).strip("\n")
    except adopt.AdoptError as error:
        raise SystemExit(f"run: the current arm cannot render its kernel: {error}") from None
    return without_sizing(text) if arm == UNSIZED else text


def without_sizing(text: str) -> str:
    """The kernel with its sizing paragraph removed and every other byte kept."""

    paragraphs = text.split("\n\n")
    kept = [paragraph for paragraph in paragraphs if not paragraph.startswith(SIZING)]
    if len(kept) != len(paragraphs) - 1:
        raise SystemExit(f"run: the kernel has no one paragraph opening {SIZING!r} to remove")
    return "\n\n".join(kept)


class Edit(NamedTuple):
    """One edit of a `--edits` file: in the installed file `path`, workspace-relative, the one
    occurrence of `old` becomes `new` (empty: the text is deleted)."""

    path: str
    old: str
    new: str


class EditsError(ValueError):
    """A `--edits` file, or one of its edits, that the runner refuses; the message says why."""


class Elements(NamedTuple):
    """What `--drop`, `--add` and `--edits` ask of an arm: the elements taken from the current
    install, the elements put into the none arm, the edits, and the SHA-256 of their file."""

    dropped: tuple[str, ...] = ()
    added: tuple[str, ...] = ()
    edits: tuple[Edit, ...] = ()
    edits_sha256: str = ""

    def named(self) -> bool:
        return bool(self.dropped or self.added or self.edits)


# What a run without --drop, --add or --edits asks: no element arm.
NO_ELEMENTS = Elements()


class Arm(NamedTuple):
    """What one arm hands the model: its kernel, ahead of the task; the files an install
    writes, by fixture-relative path; the launcher put first on the call's PATH; and, for an
    arm that stands for an install, the fragments selected and each skill's pointer, which
    `as_installed` writes into the fixture's AGENTS.md. An element arm (`element_arm`) also
    names the elements it drops from the current install or adds to the none arm, and its edits;
    its `name` is the arm it builds from, `current` or `none`.

    A named tuple, not a dataclass: the tests load this file by path, outside sys.modules.
    """

    name: str
    kernel: str
    files: dict[str, bytes]
    launcher: Path | None
    selected: tuple[str, ...] = ()
    skills: tuple[tuple[str, str], ...] = ()
    agents: str = ""
    done: tuple[str, ...] = ()
    adopted: bool = False
    dropped: tuple[str, ...] = ()
    added: tuple[str, ...] = ()
    edits: tuple[Edit, ...] = ()
    edits_sha256: str = ""

    def shaped(self) -> bool:
        """Whether the arm is an element arm: the current install less some elements, the none
        arm plus some, or either with edits."""

        return bool(self.dropped or self.added or self.edits)

    def keeps(self, element: str) -> bool:
        """Whether the arm holds `element`: the current arm all but what it drops, the none arm
        only what it adds."""

        return element in self.added if self.name == NONE else element not in self.dropped

    def record(self) -> dict[str, Any]:
        """The arm's contents as the run's metadata keeps them: digests, the launcher, the
        Done commands its facts block records, the elements it drops or adds, and for edits the
        digest of their file and of each edit's text."""

        edits = [
            {
                "path": edit.path,
                "old_sha256": sha256_text(edit.old),
                "new_sha256": sha256_text(edit.new),
            }
            for edit in self.edits
        ]
        return {
            "kernel_sha256": sha256_text(self.kernel),
            "arm_files": {
                path: hashlib.sha256(data).hexdigest() for path, data in sorted(self.files.items())
            },
            "arm_launcher": str(self.launcher) if self.launcher else None,
            **({"agents_sha256": sha256_text(self.agents)} if self.agents else {}),
            **({"arm_done": list(self.done)} if self.done else {}),
            **({"arm_adopted": True} if self.adopted else {}),
            "elements": {"dropped": list(self.dropped), "added": list(self.added)},
            **({"edits": {"sha256": self.edits_sha256, "items": edits}} if self.edits else {}),
        }


def carried_skills(root: Path) -> tuple[str, ...]:
    """The skills an install of the engine tree `root` carries: the engine's list, less any the
    tree lacks (a variant may drop one). A skill folder the list does not name is refused, never
    left out in silence: `--earlier-verbatim` installs a set of other skills."""

    present = {path.parent.name for path in (root / "skills").glob("*/SKILL.md")}
    from outcomebound_tools import fragments

    extra = sorted(present - set(fragments.SKILLS) - {"adopt-outcomebound"})
    if extra:
        raise SystemExit(
            f"run: the tree holds a skill that no install carries: {', '.join(extra)}; "
            "--earlier-verbatim installs another set of skills"
        )
    return tuple(skill for skill in fragments.SKILLS if skill in present)


def load_arm(
    name: str, selected: tuple[str, ...] = (), done: tuple[str, ...] = (), adopted: bool = False
) -> Arm:
    """The arm as it runs, for an install that selects the fragments `selected` and records the
    Done commands `done`; `adopted`, for `current` alone, installs it with the engine's own
    adopt after the build (`adopt_install`), its kernel in AGENTS.md and not in the prompt.
    `current` mirrors a codex install of this checkout: the whole folder of each skill that
    install carries, which is every install's ten, at the skill path the harness table gives
    codex, and this checkout's launcher. The earlier arm is its kernel alone and the kernel-off
    arm has nothing, whatever is selected or recorded."""

    text = kernel(name)
    if verbatim_install(name):
        from outcomebound_tools import adopt

        try:
            (route,) = adopt.routes(REPO, [INSTALL_HARNESS])
        except adopt.AdoptError as error:
            raise SystemExit(
                f"run: the skill path of {INSTALL_HARNESS} is unknown: {error}"
            ) from None
        files = {f"{route.skills}/{path}": data for path, data in verbatim_guidance()[1].items()}
        return Arm(name, text, files, None, agents=verbatim_guidance()[0])
    if name in (NONE, BARE) or (name == EARLIER and not EARLIER_REF):
        return Arm(name, text, {}, None)
    if name == FACTS_ONLY:
        return facts_only_arm(selected, done)
    from outcomebound_tools import adopt, facts, fragments

    root = earlier_source() if name == EARLIER else REPO
    try:
        (route,) = adopt.routes(root, [INSTALL_HARNESS])
        chosen = fragments.select(fragments.load_all(root), selected) if selected else []
        carried = carried_skills(root)
        files = {
            f"{route.skills}/{skill}/{relative}": data
            for skill in carried
            for relative, data in adopt.skill_files(root, skill).items()
        }
        files.update(
            {f"{facts.FRAGMENT_DIR}/{item.id}.md": adopt._fragment_bytes(item) for item in chosen}
        )
        pointers = tuple(
            (adopt.CONDITIONS[skill], f"{route.skills}/{skill}/SKILL.md") for skill in carried
        )
    except (adopt.AdoptError, fragments.FragmentError) as error:
        raise SystemExit(f"run: the current arm cannot read what adopt installs: {error}") from None
    return Arm(
        name,
        text,
        files,
        REPO / LAUNCHER,
        tuple(selected),
        pointers,
        done=tuple(done),
        adopted=adopted and name == "current",
    )


def facts_only_arm(selected: tuple[str, ...], done: tuple[str, ...]) -> Arm:
    """The facts-only arm, for an install that selects the fragments `selected` and records the
    Done commands `done`: always installed by this checkout's adopt with `--facts-only` after
    the build, on any fixture. Its files are what that install writes besides AGENTS.md and the
    ignore and manifest files: each skill the install carries, at the harness's skill path, where
    the harness lists skills itself, and nothing elsewhere; no fragment file. It keeps this
    checkout's launcher, as the current arm does, so the two differ in the installed text alone."""

    from outcomebound_tools import adopt

    try:
        (route,) = adopt.routes(REPO, [INSTALL_HARNESS])
        files = {
            f"{route.skills}/{skill}/{relative}": data
            for skill in (carried_skills(REPO) if route.native else ())
            for relative, data in adopt.skill_files(REPO, skill).items()
        }
    except adopt.AdoptError as error:
        raise SystemExit(
            f"run: the facts-only arm cannot read what adopt installs: {error}"
        ) from None
    return Arm(
        FACTS_ONLY, "", files, REPO / LAUNCHER, tuple(selected), done=tuple(done), adopted=True
    )


def fixture_arm(name: str, arm: Arm) -> Arm:
    """The adoption controller and the onboarding fixtures carry their subject skill; ordinary
    installs do not, nor the arms that build on the none arm's fixture."""

    if not name.startswith(("adopt-", "onboard-")) or arm.name in NOTE_ONLY:
        return arm
    from outcomebound_tools import adopt

    (route,) = adopt.routes(REPO, [INSTALL_HARNESS])
    root = f"{route.skills}/adopt-outcomebound"
    files = {
        **arm.files,
        **{
            f"{root}/{path}": data
            for path, data in adopt.skill_files(REPO, "adopt-outcomebound").items()
        },
    }
    return arm._replace(files=files)


# --- element arms ---------------------------------------------------------------------------


def element_of(path: str) -> str | None:
    """The element a workspace file belongs to: `skill:<name>` for a file under a skill copy's
    folder, `fragment:<id>` for an installed fragment; None for any other file."""

    from outcomebound_tools import facts

    for root in SKILL_ROOTS:
        if path.startswith(root) and "/" in path[len(root) :]:
            return f"skill:{path[len(root) :].split('/', 1)[0]}"
    folder, _, name = path.rpartition("/")
    if folder == facts.FRAGMENT_DIR and name.endswith(".md"):
        return f"fragment:{name[: -len('.md')]}"
    return None


def install_elements(arm: Arm) -> tuple[str, ...]:
    """Every element an adopted install of the arm's fragments holds, in the order of the
    pointers: the blocks, each fragment, each skill this checkout's install carries, the
    launcher."""

    return (
        KERNEL_ELEMENT,
        FACTS_ELEMENT,
        POINTERS_ELEMENT,
        *(f"fragment:{item}" for item in arm.selected),
        *(f"skill:{skill}" for skill in carried_skills(REPO)),
        LAUNCHER_ELEMENT,
    )


def read_edits(path: Path) -> tuple[tuple[Edit, ...], str]:
    """The edits a `--edits` file lists, in order, and the file's SHA-256. EditsError where the
    file is not a JSON list of `{"path", "old", "new"}` objects of strings, where an `old` is
    empty, or where a path is not workspace-relative."""

    try:
        raw = path.read_bytes()
        document = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as problem:
        raise EditsError(f"not readable JSON: {problem}") from None
    if not isinstance(document, list) or not document:
        raise EditsError('a list of {"path": ..., "old": ..., "new": ...} objects, not empty')
    edits = []
    for item in document:
        if not isinstance(item, dict) or sorted(item) != ["new", "old", "path"]:
            raise EditsError('each edit is exactly {"path": ..., "old": ..., "new": ...}')
        if not all(isinstance(value, str) for value in item.values()):
            raise EditsError("each edit's path, old and new are strings")
        relative = PurePosixPath(item["path"])
        if relative.is_absolute() or ".." in relative.parts or relative.as_posix() != item["path"]:
            raise EditsError(f"{item['path']!r} is not a workspace-relative path")
        if not item["old"]:
            raise EditsError(f"{item['path']}: old is empty; name the text the edit replaces")
        edits.append(Edit(item["path"], item["old"], item["new"]))
    return tuple(edits), hashlib.sha256(raw).hexdigest()


def edited(text: str, edit: Edit) -> str:
    """`text` with the edit applied; EditsError where its `old` does not occur exactly once."""

    count = text.count(edit.old)
    if count != 1:
        raise EditsError(
            f"{edit.path}: the text to replace occurs {count} times, not once: {edit.old[:80]!r}"
        )
    return text.replace(edit.old, edit.new, 1)


def element_arm(base: Arm, kind: str, elements: Elements) -> Arm:
    """The element arm built from `base`, the current arm of an adopted install: as `current`,
    the install less each dropped element; as `none`, only the added elements. Its files, kernel
    and launcher are what the build installs, the edits applied to the files they name (and an
    edit of AGENTS.md to the kernel, where its text occurs there once), so `record()` gives the
    digests of what is installed. EditsError where an edit's text does not occur once."""

    arm = base._replace(
        name=kind,
        dropped=elements.dropped,
        added=elements.added,
        edits=elements.edits,
        edits_sha256=elements.edits_sha256,
    )
    files = {path: data for path, data in base.files.items() if arm.keeps(element_of(path) or "")}
    skills = tuple(
        (condition, path)
        for condition, path in base.skills
        if arm.keeps(element_of(path) or "") and arm.keeps(POINTERS_ELEMENT)
    )
    kernel = base.kernel if arm.keeps(KERNEL_ELEMENT) else ""
    for edit in elements.edits:
        if edit.path in files:
            try:
                files[edit.path] = edited(files[edit.path].decode("utf-8"), edit).encode("utf-8")
            except UnicodeDecodeError:
                raise EditsError(f"{edit.path} is not UTF-8 text") from None
        elif edit.path == NOTE and kernel.count(edit.old) == 1:
            kernel = kernel.replace(edit.old, edit.new, 1)
    launcher = base.launcher if arm.keeps(LAUNCHER_ELEMENT) else None
    return arm._replace(kernel=kernel, files=files, launcher=launcher, skills=skills)


def element_refusal(install: Install, elements: Elements) -> str:
    """Why a fixture whose install is `install` cannot run the element arm, or an empty string:
    it has no install.json, a fragment its install does not select, a skill no install carries,
    or an edit of a file the install does not write."""

    if not install.adopted:
        return (
            f"an element arm is built from an adopted install, and the fixture has no "
            f"{INSTALL_FILE}"
        )
    for element in (*elements.dropped, *elements.added):
        kind, _, item = element.partition(":")
        if kind == "fragment" and item not in install.fragments:
            selected = ", ".join(install.fragments) or "none"
            return (
                f"{element}: its {INSTALL_FILE} selects no fragment {item} (it selects {selected})"
            )
        if kind == "skill" and item not in carried_skills(REPO):
            return f"{element}: the install carries no skill {item}"
    for edit in elements.edits:
        if edit.path != NOTE and element_of(edit.path) is None:
            return (
                f"--edits names {edit.path}; an edit changes {NOTE} or an installed skill or "
                "fragment file"
            )
    return ""


def element_label(kind: str, elements: Elements) -> str:
    """The default name of an element arm: `current-minus-<element>[-<element>...]` or
    `none-plus-<element>[...]`, each `:` written as `.`; the arm's own name otherwise."""

    named = elements.dropped if kind != NONE else elements.added
    if not named:
        return kind
    joined = "-".join(element.replace(":", ".") for element in named)
    return f"{kind}-{'plus' if kind == NONE else 'minus'}-{joined}"


def _pointer_element(line: str) -> str | None:
    """The element a pointer line points into, or None for any other line of the block."""

    found = POINTER_LINE.match(line)
    return element_of(found.group(1)) if found else None


def _line_kept(arm: Arm, line: str) -> bool:
    """Whether the element arm keeps one line of the guidance-pointers block. A pointer line
    belongs to its fragment or skill and to the block whole: the current arm keeps it while it
    keeps both, the none arm adds it with either. Any other line belongs to the block alone."""

    element = _pointer_element(line)
    if element is None:
        return arm.keeps(POINTERS_ELEMENT)
    owners = (arm.keeps(POINTERS_ELEMENT), arm.keeps(element))
    return any(owners) if arm.name == NONE else all(owners)


def shaped_note(text: str, arm: Arm) -> str:
    """AGENTS.md as the element arm has it, from the text adopt wrote: each block the arm does
    not keep cut as adopt cuts it, and the guidance-pointers block left with the lines the arm
    keeps. Where the none arm adds a pointer line without the block, the block keeps its markers,
    its read-once line and that line only."""

    from outcomebound_tools import adopt, facts

    for element, block in ((KERNEL_ELEMENT, adopt.KERNEL), (FACTS_ELEMENT, facts.FACTS)):
        if not arm.keeps(element):
            text = adopt.cut(text, block)
    found = adopt.block_text(text, facts.POINTERS)
    if found is None:
        return text
    lines = found.decode("utf-8").split("\n")
    kept = [line for line in lines[1:-1] if _line_kept(arm, line)]
    if not arm.keeps(POINTERS_ELEMENT):
        if not kept:
            return adopt.cut(text, facts.POINTERS)
        kept = [facts.ONCE, *kept]
    return text.replace(found.decode("utf-8"), "\n".join([lines[0], *kept, lines[-1]]), 1)


def _remove(workdir: Path, relative: str, data: bytes | None) -> None:
    """Put a file back as it was before the install (`data`), or remove it where it was not
    there, with each folder the removal leaves empty."""

    path = workdir / relative
    if data is not None:
        path.write_bytes(data)
        return
    path.unlink(missing_ok=True)
    for folder in path.parents:
        if folder == workdir or not folder.is_dir() or any(folder.iterdir()):
            break
        folder.rmdir()


def apply_edits(workdir: Path, edits: tuple[Edit, ...]) -> str:
    """Apply the edits to the built workspace's files, in order; why one could not be, or an
    empty string."""

    for edit in edits:
        path = workdir / edit.path
        if not path.is_file():
            return f"--edits: the install wrote no {edit.path}"
        try:
            path.write_bytes(edited(path.read_bytes().decode("utf-8"), edit).encode("utf-8"))
        except UnicodeDecodeError:
            return f"--edits: {edit.path} is not UTF-8 text"
        except EditsError as problem:
            return f"--edits: {problem}"
    return ""


def _shed_files(workdir: Path, arm: Arm, before: dict[str, bytes], written: list[str]) -> None:
    """Take from adopt's install the files the element arm does not hold: the current arm each
    dropped element's (a skill's copies at each skill root among them), the none arm every file
    adopt wrote (`written`) but an added element's, each put back as it was before the install
    (`before`). AGENTS.md is left to `shaped_note`."""

    if arm.name == NONE:
        for path in written:
            if path != NOTE and not arm.keeps(element_of(path) or ""):
                _remove(workdir, path, before.get(path))
        return
    for path in sorted(tree_hashes(workdir)):
        element = element_of(path)
        if element is not None and not arm.keeps(element):
            _remove(workdir, path, None)


def shape_install(workdir: Path, arm: Arm, before: dict[str, bytes], written: list[str]) -> str:
    """Make adopt's install in `workdir` the element arm's, before it joins the seed: its files
    as `_shed_files` leaves them, AGENTS.md as `shaped_note` gives it (removed where adopt wrote
    it and nothing is left), then the edits applied. Why it could not be made so, or an empty
    string; the kernel block left in AGENTS.md must be the arm's kernel, which its record
    digests."""

    from outcomebound_tools import adopt

    _shed_files(workdir, arm, before, written)
    note = workdir / NOTE
    if note.is_file():
        text = note.read_bytes().decode("utf-8")
        shaped = shaped_note(text, arm)
        if not shaped and NOTE not in before:
            _remove(workdir, NOTE, None)
        elif shaped != text:
            note.write_bytes(shaped.encode("utf-8"))
    unfit = apply_edits(workdir, arm.edits)
    if unfit:
        return unfit
    text = note.read_bytes().decode("utf-8") if note.is_file() else ""
    block = adopt.block_text(text, adopt.KERNEL)
    if (block.decode("utf-8") if block else "") != arm.kernel:
        return "the kernel block in AGENTS.md is not the arm's kernel"
    return ""


def element_problems(workdir: Path, arm: Arm) -> list[str]:
    """What the built workspace of an element arm holds that differs from its elements: a block,
    fragment file, skill folder or pointer line present that the arm does not keep, or absent
    that it keeps; for the none arm, a file adopt writes that no element owns."""

    from outcomebound_tools import adopt, facts

    note = workdir / NOTE
    text = note.read_text("utf-8") if note.is_file() else ""
    found = adopt.block_text(text, facts.POINTERS)
    lines = found.decode("utf-8").split("\n")[1:-1] if found else []
    pointed = {_pointer_element(line) for line in lines} - {None}
    problems = []

    def expect(what: str, wanted: bool, present: bool) -> None:
        if wanted != present:
            problems.append(f"{what} {'missing' if wanted else 'present'}")

    for element in install_elements(arm):
        kind, _, item = element.partition(":")
        if element in (KERNEL_ELEMENT, FACTS_ELEMENT):
            block = adopt.KERNEL if element == KERNEL_ELEMENT else facts.FACTS
            expect(
                f"the {block} block", arm.keeps(element), adopt.block_text(text, block) is not None
            )
        elif element == POINTERS_ELEMENT:
            lined = [item for item in install_elements(arm) if item.startswith(LINED)]
            wanted = arm.keeps(element) or (arm.name == NONE and any(map(arm.keeps, lined)))
            expect(f"the {facts.POINTERS} block", wanted, found is not None)
        elif kind == "fragment":
            fragment = f"{facts.FRAGMENT_DIR}/{item}.md"
            expect(f"{element}'s file", arm.keeps(element), (workdir / fragment).is_file())
            line = f"- x: read {fragment}"
            expect(f"{element}'s pointer line", _line_kept(arm, line), element in pointed)
        elif kind == "skill":
            present = any((workdir / root / item).exists() for root in SKILL_ROOTS)
            expect(f"{element}'s folder", arm.keeps(element), present)
            line = f"- x: read {SKILL_ROOTS[-1]}{item}/SKILL.md"
            expect(f"{element}'s pointer line", _line_kept(arm, line), element in pointed)
    if arm.name == NONE:
        for path in (adopt.WORKSPACE_IGNORE, adopt.LOCAL_IGNORE, adopt.MANIFEST):
            expect(path, False, (workdir / path).exists())
    return problems


def element_problem(workdir: Path, arm: Arm) -> str:
    """Why the built workspace of an element arm does not hold exactly its elements, or an empty
    string (for any other arm too)."""

    problems = element_problems(workdir, arm) if arm.shaped() else []
    return "the arm does not hold exactly its elements: " + "; ".join(problems) if problems else ""


def fixture_write_roots(name: str, workdir: Path) -> tuple[Path, ...]:
    """Only the upgrade case grants nested Git and exact managed skill directories."""

    if name != "adopt-upgrade":
        return ()
    from outcomebound_tools import adopt

    target = workdir / "target" / "project"
    return (target / ".git", *(target / ".agents" / "skills" / skill for skill in adopt.SKILLS))


def as_installed(workdir: Path, arm: Arm) -> str:
    """For an arm that stands for an install, give the built fixture what adopt writes into
    AGENTS.md, and fold it into the seed commit; why it could not, or an empty string.

    The fixture's note keeps its project text and loses its own pointer to the core skill;
    AGENTS.md gains the project facts, with the arm's Done commands as `adopt --done` records
    them, and the guidance pointers, each skill's with its condition, rendered by the engine as
    an install renders them. An arm that is another guidance
    set's own files writes that set's AGENTS.md above the note instead, and no facts or pointers.
    An element arm is installed by adopt as the current arm is, and then made its own
    (`shape_install`); the none arm plus elements keeps the note as the none arm's setup left it.
    """

    _FIXTURE_FILES[workdir] = frozenset(tree_hashes(workdir))
    installs = arm.name in INSTALLED or (arm.name == EARLIER and (EARLIER_REF or arm.agents))
    if not installs and not arm.adopted:
        return ""
    from outcomebound_tools import facts, fragments

    rewritten = []
    for note in ("AGENTS.md", "README.md") if arm.name != NONE else ():
        path = workdir / note
        if path.is_file():
            text = path.read_text(encoding="utf-8")
            path.write_text(NOTE_POINTER.sub("", text), "utf-8")
            rewritten += [note] if NOTE_POINTER.search(text) else []
    if arm.adopted:
        return adopt_install(workdir, arm, tuple(rewritten))
    agents = workdir / "AGENTS.md"
    if arm.agents:
        # Another guidance set's AGENTS.md, as it is, ahead of the fixture's own project note.
        note = agents.read_text(encoding="utf-8").strip("\n") if agents.is_file() else ""
        agents.write_text(arm.agents.rstrip("\n") + "\n" + (f"\n{note}\n" if note else ""), "utf-8")
    else:
        root = earlier_source() if arm.name == EARLIER else REPO
        chosen = fragments.select(fragments.load_all(root), arm.selected) if arm.selected else []
        rendered = facts.render(workdir, chosen, list(arm.done), ["AGENTS.md"], list(arm.skills))
        head = agents.read_text(encoding="utf-8").rstrip("\n") + "\n\n" if agents.is_file() else ""
        blocks = [rendered.facts, *([rendered.pointers] if rendered.pointers else [])]
        agents.write_text(head + "\n\n".join(block.strip("\n") for block in blocks) + "\n", "utf-8")
    env = {**child_env(), **HERMETIC_GIT}
    # Only the notes this function wrote join the seed: a fixture's uncommitted edits, such as
    # the work in progress beside a read-only review, stay uncommitted, as setup left them.
    notes = [note for note in ("AGENTS.md", "README.md") if (workdir / note).is_file()]
    for command in (
        ["git", "add", "--", *notes],
        ["git", "commit", "-q", "--amend", "--no-edit"],
        ["git", "tag", "-f", "seed"],
    ):
        done = subprocess.run(
            command, cwd=workdir, capture_output=True, text=True, env=env, encoding="utf-8"
        )
        if done.returncode != 0:
            return f"the install could not be folded into the seed: {done.stderr.strip()}"
    return ""


def adopt_install(workdir: Path, arm: Arm, rewritten: tuple[str, ...] = ()) -> str:
    """Install the arm into the built fixture as an adopter does: this checkout's launcher runs
    `outcomebound adopt --harness <INSTALL_HARNESS>` with the arm's fragments and Done commands,
    which writes the kernel, facts and pointers blocks into AGENTS.md, the skills, the fragments,
    `.agents/.gitignore` and `.outcomebound/`. What it wrote, less what its own ignore files
    keep out, and the notes `as_installed` rewrote (`rewritten`) are folded into the seed
    commit; the setup's other uncommitted edits stay so. An
    element arm's install is made its own (`shape_install`) before it is folded in, and may
    leave nothing to fold. Why it could not, or an empty string."""

    env = {**child_env(), **HERMETIC_GIT}
    argv = [str(REPO / LAUNCHER), "adopt", str(workdir), "--harness", INSTALL_HARNESS]
    argv += ["--facts-only"] if arm.name == FACTS_ONLY else []
    argv += ["--fragments", ",".join(arm.selected)] if arm.selected else []
    for line in arm.done:
        argv += ["--done", line]
    before = tree_hashes(workdir)
    saved = {
        path: (workdir / path).read_bytes()
        for path, digest in before.items()
        if arm.shaped() and not digest.startswith("link:")
    }
    done = bounded_command(argv, cwd=str(workdir), env=env, timeout=SETUP_TIMEOUT)
    if done.returncode != 0:
        return f"adopt exited {done.returncode}: {(done.stdout + done.stderr).strip()[-600:]}"
    after = tree_hashes(workdir)
    written = sorted(path for path in {*before, *after} if before.get(path) != after.get(path))
    if arm.shaped():
        unfit = shape_install(workdir, arm, saved, written)
        if unfit:
            return unfit
        after = tree_hashes(workdir)
        written = sorted(path for path in {*before, *after} if before.get(path) != after.get(path))
    ignored = subprocess.run(
        ["git", "check-ignore", "--stdin"],
        input="\n".join(written),
        cwd=workdir,
        capture_output=True,
        text=True,
        env=env,
        encoding="utf-8",
    ).stdout.splitlines()
    # A note whose pointer to the core skill `as_installed` took out joins the seed even where
    # the install leaves it as it was: an element arm may cut every block adopt wrote into it.
    kept = sorted({*(path for path in written if path not in ignored), *rewritten})
    if not kept:
        # An element arm may keep nothing adopt wrote: the none arm plus the launcher alone.
        return "" if arm.shaped() else "adopt wrote nothing into the fixture"
    for command in (
        ["git", "add", "-A", "--", *kept],
        ["git", "commit", "-q", "--amend", "--no-edit"],
        ["git", "tag", "-f", "seed"],
    ):
        folded = subprocess.run(
            command, cwd=workdir, capture_output=True, text=True, env=env, encoding="utf-8"
        )
        if folded.returncode != 0:
            return f"the install could not be folded into the seed: {folded.stderr.strip()}"
    return ""


def refresh_baseline_hashes(workdir: Path, stage: Path, removed: tuple[str, ...] = ()) -> None:
    """Re-record the notes `as_installed` rewrote in a fixture's `baseline-hashes`, which its
    setup wrote before the install; without it a check that compares the tree to that baseline
    counts the install as the model's edit. Only the lines of those notes change, and the lines
    of `baseline-hashes` and `baseline-files` that name a path the bare arm removed (`removed`)
    are dropped."""

    def gone(name: str) -> bool:
        return any(name == f"./{item}" or name.startswith(f"./{item}/") for item in removed)

    listed = stage / "checks" / "baseline-files"
    if removed and listed.is_file():
        kept = [line for line in listed.read_text(encoding="utf-8").splitlines() if not gone(line)]
        listed.write_text("".join(f"{line}\n" for line in kept), encoding="utf-8")
    path = stage / "checks" / "baseline-hashes"
    if not path.is_file():
        return
    lines = []
    for line in path.read_text(encoding="utf-8").splitlines():
        _digest, _, name = line.partition("  ")
        if gone(name):
            continue
        if name in ("./AGENTS.md", "./README.md") and (workdir / name).is_file():
            line = f"{hashlib.sha256((workdir / name).read_bytes()).hexdigest()}  {name}"
        lines.append(line)
    path.write_text("".join(f"{line}\n" for line in lines), encoding="utf-8")


def _nested_repository(workdir: Path, path: Path) -> bool:
    """Whether `path` lies inside a Git repository nested in `workdir`."""

    return any((parent / ".git").exists() for parent in path.parents if workdir in parent.parents)


def instruction_paths(workdir: Path) -> tuple[list[str], list[str]]:
    """What the bare arm removes from the built `workdir` (`BARE_NAMES`, `BARE_FOLDER`,
    `BARE_ROOTS`), and what it keeps because a nested Git repository holds it; each by
    workspace-relative path, a folder as one entry."""

    found = [root.rstrip("/") for root in BARE_ROOTS if (workdir / root).exists()]
    for folder, subfolders, names in os.walk(workdir):
        here = Path(folder)
        subfolders[:] = sorted(name for name in subfolders if name != ".git")
        for name in list(subfolders):
            relative = (here / name).relative_to(workdir).as_posix()
            if relative in found:
                subfolders.remove(name)
            elif relative == BARE_FOLDER or relative.endswith(f"/{BARE_FOLDER}"):
                found.append(relative)
                subfolders.remove(name)
        found += [
            (here / name).relative_to(workdir).as_posix() for name in names if name in BARE_NAMES
        ]
    removed = sorted(item for item in found if not _nested_repository(workdir, workdir / item))
    return removed, sorted(set(found) - set(removed))


def strip_instructions(workdir: Path, extra: dict[str, Any]) -> tuple[tuple[str, ...], str]:
    """For the bare arm: remove each instruction file and OutcomeBound folder from the built
    fixture (`instruction_paths`) and fold the removal into the seed commit, so a check that
    compares the tree with the seed does not count it as the model's change. `extra` records
    what was removed and what a nested repository kept. The paths removed, and why the removal
    could not be folded in, or an empty string."""

    removed, kept = instruction_paths(workdir)
    extra["instructions_removed"] = removed
    if kept:
        extra["instructions_kept"] = kept
    for item in removed:
        path = workdir / item
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink()
    if not removed:
        return (), ""
    env = {**child_env(), **HERMETIC_GIT}
    # Only the removed paths leave the index: a fixture's uncommitted edits stay as setup left
    # them, as under `as_installed`.
    for command in (
        ["git", "rm", "-r", "-q", "--cached", "--ignore-unmatch", "--", *removed],
        ["git", "commit", "-q", "--amend", "--no-edit", "--allow-empty"],
        ["git", "tag", "-f", "seed"],
    ):
        done = subprocess.run(
            command, cwd=workdir, capture_output=True, text=True, env=env, encoding="utf-8"
        )
        if done.returncode != 0:
            return tuple(
                removed
            ), f"the removal could not be folded into the seed: {done.stderr.strip()}"
    return tuple(removed), ""


def facts_only_problems(workdir: Path) -> list[str]:
    """What the built workspace of the facts-only arm holds that adopt's facts-only install does
    not: a kernel block, a pointer line, a fragment file, or no project-facts block."""

    from outcomebound_tools import adopt, facts

    note = workdir / NOTE
    text = note.read_text("utf-8") if note.is_file() else ""
    problems = []
    if adopt.block_text(text, facts.FACTS) is None:
        problems.append(f"the {facts.FACTS} block missing")
    if adopt.block_text(text, adopt.KERNEL) is not None:
        problems.append(f"the {adopt.KERNEL} block present")
    found = adopt.block_text(text, facts.POINTERS)
    lines = found.decode("utf-8").splitlines() if found else []
    problems += [f"pointer line present: {line}" for line in lines if POINTER_LINE.match(line)]
    fragments = sorted((workdir / facts.FRAGMENT_DIR).glob("*.md"))
    problems += [f"fragment file present: {path.relative_to(workdir)}" for path in fragments]
    return problems


def install(workdir: Path, files: dict[str, bytes]) -> None:
    """Write the arm's files into a fixture before its setup.sh runs, which commits everything
    its target holds in its first commit: the files are part of the seed, and of any baseline
    the setup records, so no post-check counts them as the model's change."""

    for relative, data in files.items():
        path = workdir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def installed(workdir: Path, files: dict[str, bytes]) -> str:
    """Why the built fixture does not hold the arm's files as committed, or an empty string."""

    if not files:
        return ""
    changed = [
        path
        for path, data in files.items()
        if not (workdir / path).is_file() or (workdir / path).read_bytes() != data
    ]
    if changed:
        return "the arm's files differ after setup: " + ", ".join(sorted(changed))
    status, _out, error = _run(["git", "ls-files", "--error-unmatch", "--", *files], cwd=workdir)
    return "" if status == 0 else f"setup did not commit the arm's files: {error.strip()}"


def without_launchers(path: str, root: str | None) -> str:
    """`path` with no `outcomebound`: each entry that holds one is replaced by a new folder, in
    `root`, of links to its other entries, so every other command resolves as it did."""

    kept = []
    for entry in path.split(os.pathsep):
        if not entry or not shutil.which("outcomebound", path=entry):
            kept.append(entry)
            continue
        mirror = Path(tempfile.mkdtemp(prefix="ob-path-", dir=root))
        for name in _entries(Path(entry)):
            if Path(name).stem != "outcomebound":
                (mirror / name).symlink_to(Path(entry) / name)
        kept.append(str(mirror))
    return os.pathsep.join(kept)


def call_path(arm: Arm, root: str | None) -> str:
    """The PATH codex and the model's commands get: the arm's launcher, alone in a directory
    of its own, ahead of this environment's PATH less every other `outcomebound`, so the arm's
    launcher is the only one a call reaches, and an arm with none reaches none."""

    path = without_launchers(child_env().get("PATH", os.defpath), root)
    if arm.launcher is None:
        return path
    directory = Path(tempfile.mkdtemp(prefix="ob-launcher-", dir=root))
    (directory / "outcomebound").symlink_to(arm.launcher)
    return f"{directory}{os.pathsep}{path}"


# --- what a call reaches besides its prompt -------------------------------------------------

# The instruction files codex reads from its home and from each folder on its project path.
INSTRUCTIONS = ("AGENTS.md", "AGENTS.override.md")
# codex's own bundled skills, which it writes into every home it runs with: the harness's, not
# the operator's, so both arms read them as every adopter's session does.
SYSTEM_SKILLS = ".system"
# Skill folders codex reads outside its home: the user's and the machine's.
OUTSIDE_SKILLS = (Path.home() / ".agents" / "skills", Path("/etc/codex/skills"))


def launchers(path: str) -> list[str]:
    """Each PATH entry that holds an executable `outcomebound`, with what it resolves to."""

    found = []
    for entry in path.split(os.pathsep):
        hit = shutil.which("outcomebound", path=entry) if entry else None
        if hit:
            found.append(f"{entry} -> {os.path.realpath(hit)}")
    return found


def _entries(folder: Path) -> list[str]:
    try:
        return sorted(item.name for item in folder.iterdir())
    except OSError:
        return []


def home_leaks(home: Path) -> list[str]:
    """What the Codex home `home`, and the skill folders codex reads outside it, give a call
    beyond its fixture and its install: an instruction file, the operator's skills, an agent
    role. codex's own bundled skills are not counted."""

    found = [f"{home / name}" for name in INSTRUCTIONS if (home / name).exists()]
    found += [f"{home / 'skills' / name}" for name in _entries(home / "skills")]
    found = [item for item in found if Path(item).name != SYSTEM_SKILLS]
    found += [f"{home / 'agents' / name}" for name in _entries(home / "agents")]
    found += [f"{folder / name}" for folder in OUTSIDE_SKILLS for name in _entries(folder)]
    return found


def _names_outcomebound(path: Path) -> bool:
    """Whether a file, or any file under a folder, holds the word OutcomeBound in any case."""

    files = [path] if path.is_file() else [item for item in path.rglob("*") if item.is_file()]
    return any(b"outcomebound" in _bytes(item).lower() for item in files)


def _bytes(path: Path) -> bytes:
    """A file's bytes; one that cannot be read reads as naming OutcomeBound, never as clean."""

    try:
        return path.read_bytes()
    except OSError:
        return b"outcomebound (unreadable)"


def _instructing(path: Path) -> bool:
    """Whether `path` is an instruction file with text in it."""

    return path.name in INSTRUCTIONS and path.is_file() and bool(path.read_bytes().strip())


def guiding_reach(home: Path, where: Path) -> list[str]:
    """What a call would read, from the Codex home `home` (its instruction files, the
    operator's skills and agent roles, the skill folders outside it) or from the instruction
    files at and above `where`, that names OutcomeBound or is an instruction file with text."""

    reached = [*home_leaks(home), *instructions_above(where)]
    return [item for item in reached if _instructing(Path(item)) or _names_outcomebound(Path(item))]


def unclean_reach(
    names: list[str], home: Path, where: Path | None, bare: bool = False
) -> list[str]:
    """For a run of a fixture that needs a clean reach (`CLEAN_HOME`), or of the bare arm
    (`bare`), whose measure is no instruction at all: `guiding_reach` of the Codex home `home`
    and of the folder its workspaces are made in, `where` (None: the system's temporary
    folder)."""

    if not bare and not any(name.startswith(CLEAN_HOME) for name in names):
        return []
    return guiding_reach(home, where or Path(tempfile.gettempdir()))


def instructions_above(folder: Path) -> list[str]:
    """Each instruction file in `folder` or a folder above it."""

    resolved = folder.resolve()
    return [
        str(place / name)
        for place in (resolved, *resolved.parents)
        for name in INSTRUCTIONS
        if (place / name).is_file()
    ]


def task_text(name: str, workdir: Path) -> str:
    """A fixture's task: its prompt.md, or what its task.sh prints for the built `workdir`.

    The script runs after the seed is final, with the build's environment; it may read the
    workspace and writes nothing there. A script that fails, or prints nothing, is a fixture
    error, never a task.
    """

    fixture = FIXTURES / name
    if not (fixture / TASK_SCRIPT).is_file():
        return (fixture / "prompt.md").read_text(encoding="utf-8")
    done = bounded_command(
        ["bash", str(fixture / TASK_SCRIPT), str(workdir)],
        env={**child_env(), **HERMETIC_GIT},
        timeout=SETUP_TIMEOUT,
    )
    if done.returncode != 0 or not done.stdout.strip():
        raise ValueError(f"{TASK_SCRIPT} exited {done.returncode}: {done.stderr.strip()[:600]}")
    return done.stdout


def build_prompt(kernel_text: str, task: str) -> str:
    """The kernel, then the fixture's task verbatim: nothing else reaches the model from here."""

    head = f"{kernel_text}\n\n" if kernel_text else ""
    return f"{head}Task:\n{task.strip()}\n"


Harness = CodexHarness | ClaudeCodeHarness


def make_harness(name: str = HARNESS, plugin_dirs: tuple[Path, ...] = ()) -> Harness:
    """The named harness, wired to this runner's environment, short-command runner and call
    timeout; a new one is a module under evals/harnesses and a line here. `plugin_dirs` are the
    plugin folders a Claude Code arm adds; codex takes none."""

    if name == CLAUDE:
        return ClaudeCodeHarness(child_env, _run, CALL_TIMEOUT, plugin_dirs)
    if name != HARNESS:
        raise ValueError(f"no harness {name}; there is {', '.join(HARNESSES)}")
    if plugin_dirs:
        raise ValueError(f"--plugin-dir adds a plugin to a {CLAUDE} call; {name} takes none")
    return CodexHarness(child_env, _run, CALL_TIMEOUT)


def set_harness(name: str) -> None:
    """Install for `name`: the current arm becomes what adopt installs for that harness."""

    global INSTALL_HARNESS
    INSTALL_HARNESS = name


def evals_home() -> Path:
    """The private evals home, as `evals/ponytail/driver.py` finds it: `OB_EVALS_HOME`, else
    `outcomebound-evals` beside the main checkout."""

    from evals.ponytail.driver import evals_home as found

    return found()


def plugin_dir_refusal(folder: str) -> str:
    """Why `folder` cannot be a plugin an arm adds, or an empty string: it must be an existing
    folder that resolves inside the evals home's `third-party/` folder (a pinned clone), so a
    plugin never comes from a person's plugin cache."""

    if not folder:
        return "--plugin-dir names no folder"
    path = Path(folder)
    if not path.is_absolute():
        return f"--plugin-dir {folder} is not an absolute path"
    allowed = (evals_home() / THIRD_PARTY).resolve()
    if not path.is_dir():
        return f"--plugin-dir {folder} is not a folder"
    if not path.resolve().is_relative_to(allowed) or path.resolve() == allowed:
        return f"--plugin-dir {folder} is not inside {allowed}: a plugin comes from a pinned clone"
    return ""


def plugin_records(folders: tuple[Path, ...]) -> list[dict[str, Any]]:
    """Each plugin folder with the commit its clone is at (None where Git names none)."""

    found = []
    for folder in folders:
        status, commit, _error = _run(["git", "-C", str(folder), "rev-parse", "HEAD"])
        found.append({"path": str(folder), "commit": commit.strip() if status == 0 else None})
    return found


def source() -> dict[str, Any]:
    """The checkout the kernel, the fixtures and the core skill were read from."""

    status, commit, _error = _run(["git", "-C", str(REPO), "rev-parse", "HEAD"])
    listed, changes, _error = _run(["git", "-C", str(REPO), "status", "--porcelain"])
    return {
        "commit": commit.strip() if status == 0 else "unknown",
        "dirty": bool(changes.strip()) if listed == 0 else None,
    }


def protected_snapshot(
    fixture: Path,
    workdir: Path,
    installed_files: tuple[str, ...] = (),
    without_skills: bool = False,
    dropped: tuple[str, ...] = (),
    removed: tuple[str, ...] = (),
) -> dict[str, str]:
    """Digests of the grading inputs the model could rewrite, taken while the build is trusted.

    `protected.paths` stays beside the fixture's definition, outside the workspace, and the
    digests stay in this process: the model can edit the files, never this baseline. The
    files the arm installed are protected beside them. An arm `without_skills`, the kernel-off
    arm or another guidance set's own files, protects no OutcomeBound skill copy it does not
    install: each the list names must be absent, since that arm has none; the skills it installs
    are protected. The same holds for the copies of each skill in `dropped`, which an element arm
    takes from the current install. A path the bare arm removed (`removed`, or under one) is not
    there to protect: it is left out.
    """

    snapshot = {}
    lines = (fixture / "protected.paths").read_text(encoding="utf-8").splitlines()
    for raw, listed in [*((line, True) for line in lines), *((p, False) for p in installed_files)]:
        name = raw.strip()
        if not name or name.startswith("#"):
            continue
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"protected path is not fixture-relative: {name}")
        if any(name == item or name.startswith(f"{item}/") for item in removed):
            continue
        skill = (element_of(name) or "").partition(":")[2]
        absent = without_skills or skill in dropped
        if absent and listed and name.startswith(SKILL_ROOTS) and name not in installed_files:
            if (workdir / relative).exists():
                raise ValueError(f"the arm carries no skill, yet the build holds {name}")
            continue
        if not (workdir / relative).is_file():
            raise ValueError(f"protected path does not exist: {name}")
        snapshot[name] = hashlib.sha256((workdir / relative).read_bytes()).hexdigest()
    if not snapshot:
        raise ValueError(f"{fixture.name}/protected.paths names no path")
    return snapshot


def check_protected(workdir: Path, snapshot: dict[str, str]) -> tuple[bool, str]:
    changed = [
        name
        for name, digest in snapshot.items()
        if not (workdir / name).is_file()
        or hashlib.sha256((workdir / name).read_bytes()).hexdigest() != digest
    ]
    if changed:
        return False, "FAIL protected-grading-inputs — changed or missing: " + ", ".join(changed)
    return True, "PASS protected-grading-inputs — graders, authority and exclusions match setup"


class Sealed(NamedTuple):
    """What grades a run, as it stood after the build and before the call: the stage, the SHA-256
    of each of its files and of each grading file of this checkout."""

    stage: Path
    stage_files: dict[str, str]
    grading_files: dict[str, str]


def seal_inputs(stage: Path, name: str) -> Sealed:
    """Record what grades `name` now: the stage and the grading files."""

    return Sealed(stage, tree_hashes(stage), grading_hashes(evals_dir(), name))


def check_graders(sealed: Sealed, name: str) -> tuple[bool, str]:
    """Whether the stage and the grading files are as they were sealed, and if not, the report
    that fails the run before any check executes."""

    now = grading_hashes(evals_dir(), name)
    moved = [
        *(f"stage/{item}" for item in changed(sealed.stage_files, tree_hashes(sealed.stage))),
        *(f"evals/{item}" for item in changed(sealed.grading_files, now)),
    ]
    if moved:
        return False, "FAIL protected-grading-inputs — changed or missing: " + ", ".join(moved)
    return True, ""


class SealMoved(Exception):
    """The sealed copy differs from what was sealed before the call; the message names what."""


def seal_graders(sealed: Sealed, name: str, destination: Path) -> str:
    """Copy what grades `name` into `destination` and return the copy's digest, once the copy is
    shown to hold what was sealed before the call. A difference, which a process the call left
    running could make, removes the copy and raises `SealMoved` with the report that fails the
    run."""

    plan = FIXTURES / name / "post.plan.json"
    digest = seal(sealed.stage, plan, evals_dir(), name, destination)
    moved = sealed_changes(destination, sealed.stage_files, sealed.grading_files, name)
    if moved:
        shutil.rmtree(destination, ignore_errors=True)
        raise SealMoved(
            "FAIL protected-grading-inputs — changed after the check, in the sealed copy: "
            + ", ".join(moved)
        )
    return digest


def seed_commit(workdir: Path) -> str | None:
    command = ["git", "rev-parse", "--verify", "refs/tags/seed^{commit}"]
    status, seed, _error = _run(command, cwd=workdir)
    return seed.strip() if status == 0 else None


class CallRecords(NamedTuple):
    """What the runner observed around a call, for its checks: the budget record (`stopped`,
    `input`, `uncached`, `output`, `seconds`), the watch log, the stubs' folder and their
    digests before and after the call. None where the run did not record it."""

    budget: dict[str, Any] | None = None
    watch_log: Path | None = None
    stubs: Path | None = None
    stub_digests: dict[str, dict[str, str]] | None = None


def records_env(records: CallRecords | None, folder: Path) -> dict[str, str]:
    """The variables that hand the checks what the runner recorded around the call; the budget
    and the stubs' digests are written as JSON files into `folder`, the run-owned grading
    folder. A record the run did not keep sets no variable."""

    if records is None:
        return {}
    env = {}
    if records.budget is not None:
        _write(folder / "budget.json", records.budget)
        env[BUDGET_ENV] = str(folder / "budget.json")
    if records.watch_log is not None:
        env[WATCH_LOG_ENV] = str(records.watch_log)
    if records.stubs is not None:
        env[stub_place.STUBS_ENV] = str(records.stubs)
    if records.stub_digests is not None:
        _write(folder / "stub-digests.json", records.stub_digests)
        env[stub_place.DIGESTS_ENV] = str(folder / "stub-digests.json")
    return env


class Judging(NamedTuple):
    """What judges a run: the sealed copy of its graders (None: see `post_check`) and what the
    runner recorded around its call. `post_check` takes it in place of the graders' path."""

    graders: Path | None
    records: CallRecords | None = None


def post_check(
    fixture: Path,
    workdir: Path,
    seed: str | None,
    transcript: str,
    answer: str,
    graders: Path | Judging | None = None,
) -> tuple[str, str, Path]:
    """The fixture's plan, run by validation from a run-owned directory beside the workspace.

    The plan and the graders are the run's sealed copy, `graders`, which the plan names through
    `OUTCOMEBOUND_GRADER_DIR` and its `evals/` folder through `OUTCOMEBOUND_EVAL_DIR`. A run
    from before the graders left the workspace has no sealed copy: its plan is the fixture's, its
    graders are the ones its kept workspace holds, and `evals/` is this checkout's.

    The plan is copied into the run-owned directory, so repetitions never share logs, and the
    transcript and the answer are written there before any check reads them, with what the
    runner recorded around the call (`records_env`), where `graders` is a `Judging` that holds
    it.
    """

    records = None
    if isinstance(graders, Judging):
        graders, records = graders

    grading = Path(tempfile.mkdtemp(prefix="ob-grading-", dir=str(workdir.parent)))
    plan = grading / "post.plan.json"
    plan.write_bytes(((graders or fixture) / "post.plan.json").read_bytes())
    (grading / "transcript.txt").write_text(transcript, encoding="utf-8")
    (grading / "answer.md").write_text(answer, encoding="utf-8")
    env = {
        **child_env(),
        **HERMETIC_GIT,
        "PYTHONPATH": str(REPO),
        "PYTHONDONTWRITEBYTECODE": "1",
        GRADER_DIR_ENV: str(graders or workdir),
        EVAL_DIR_ENV: str(graders / "evals" if graders else evals_dir()),
        TRANSCRIPT_ENV: str(grading / "transcript.txt"),
        ANSWER_ENV: str(grading / "answer.md"),
        **records_env(records, grading),
    }
    if seed:
        env[SEED_SHA_ENV] = seed
    done = bounded_command(
        [sys.executable, "-m", "outcomebound_tools.validation", str(plan), "--cwd", str(workdir)],
        cwd=str(REPO),
        env=env,
        timeout=POST_CHECK_TIMEOUT,
    )
    verdict = {0: "PASS", 1: "FAIL"}.get(done.returncode, "UNVERIFIED")
    return verdict, done.stdout + done.stderr, grading / ".outcomebound-checks"


def observations(log_dir: Path | None) -> list[str]:
    """Each `observed:` line a check printed: what it saw, never part of its verdict."""

    if log_dir is None or not log_dir.is_dir():
        return []
    return [
        line
        for log in sorted(log_dir.glob("*.log"))
        for line in log.read_text(encoding="utf-8", errors="replace").splitlines()
        if line.startswith(OBSERVED)
    ]


def new_workspace(workspace: Path | None) -> Path:
    """The empty directory a fixture is built in: `workspace`, which must not exist yet, or a
    new temporary one."""

    if workspace is None:
        return Path(tempfile.mkdtemp(prefix="ob-fixture-"))
    workspace.mkdir(parents=True, exist_ok=False)
    return workspace


def new_stage(avoid: tuple[Path, ...] = ()) -> Path:
    """The folder a fixture's setup writes its graders to: new, private (mode 0700), in the
    system's temporary folder, and not inside any folder of `avoid` (the workspace and the
    workspace root). ValueError where the temporary folder is inside one."""

    stage = Path(tempfile.mkdtemp(prefix=STAGE_PREFIX)).resolve()
    for folder in avoid:
        if folder.resolve() in (stage, *stage.parents):
            shutil.rmtree(stage, ignore_errors=True)
            raise ValueError(f"the grading stage {stage} would be inside {folder}")
    return stage


class Place(NamedTuple):
    """Where a run keeps its evidence: the new directory its workspace is built in (None for a
    temporary one), the file its harness copies the native session to (None for a file beside
    the workspace), the new folder that holds the sealed copy of its graders (None for one beside
    the workspace) and the workspace root, which the stage must stay outside; for a suite
    fixture, the new folder its stubs are placed in and the new file its watch log is written
    to (None for each: beside the workspace)."""

    workspace: Path | None = None
    keep: Path | None = None
    graders: Path | None = None
    root: Path | None = None
    stubs: Path | None = None
    watch: Path | None = None


def build_workspace(
    name: str, arm: Arm, workdir: Path, extra: dict[str, Any], stage: Path
) -> tuple[str | None, dict[str, str], str | None, str]:
    """Install the arm's files and build the fixture in `workdir`; its setup writes the graders
    to `stage`, never into `workdir`.

    Returns None, the protected digests, the seed commit and the prompt (the arm's kernel, then
    the fixture's task); or, where the build fails, the report of why with the error in `extra`.
    """

    fixture = FIXTURES / name
    if not arm.adopted:
        install(workdir, arm.files)
    try:
        built = bounded_command(
            ["bash", str(fixture / "setup.sh"), str(workdir), str(stage)],
            env={
                **fixture_setup_env(),
                "OB_EVAL_ARM": NONE if arm.name in NOTE_ONLY else arm.name,
                **({"OB_EVAL_SOURCE": str(earlier_source())} if earlier_install(arm) else {}),
                **({"OB_EVAL_VERBATIM": "1"} if verbatim_install(arm) else {}),
            },
            timeout=SETUP_TIMEOUT,
        )
    except (OSError, subprocess.SubprocessError) as problem:
        extra["error"] = f"fixture setup {type(problem).__name__}: {problem}"
        return partial_output(problem), {}, None, ""
    report = built.stdout + built.stderr
    if built.returncode != 0:
        extra["error"] = f"fixture setup exited {built.returncode}"
        return report, {}, None, ""
    unfit = (
        as_installed(workdir, arm) or installed(workdir, arm.files) or element_problem(workdir, arm)
    )
    removed: tuple[str, ...] = ()
    if not unfit and arm.name == BARE:
        removed, unfit = strip_instructions(workdir, extra)
    if not unfit and arm.name == FACTS_ONLY and facts_only_problems(workdir):
        unfit = "the facts-only install differs: " + "; ".join(facts_only_problems(workdir))
    if not unfit:
        refresh_baseline_hashes(workdir, stage, removed)
    if unfit:
        extra["error"] = unfit
        return report, {}, None, ""
    try:
        protected = protected_snapshot(
            fixture,
            workdir,
            tuple(arm.files),
            without_skills=arm.name in NOTE_ONLY or verbatim_install(arm),
            dropped=tuple(
                item.split(":", 1)[1] for item in arm.dropped if item.startswith("skill:")
            ),
            removed=removed,
        )
    except (OSError, ValueError) as problem:
        extra["error"] = f"protected fixture setup failed: {problem}"
        return report, {}, None, ""
    seed = seed_commit(workdir)
    (workdir / ".agents" / "work").mkdir(parents=True, exist_ok=True)
    try:
        # An adopted install keeps its kernel in AGENTS.md: the prompt is the task alone.
        prompt = build_prompt("" if arm.adopted else arm.kernel, task_text(name, workdir))
    except (OSError, ValueError, subprocess.SubprocessError) as problem:
        extra["error"] = f"the fixture's task could not be written: {problem}"
        return report + partial_output(problem), {}, None, ""
    return None, protected, seed, prompt


class Scene(NamedTuple):
    """Where one run happens: its workspace, its grading stage, where it keeps its evidence and
    the record that it builds."""

    workdir: Path
    stage: Path
    place: Place
    extra: dict[str, Any]


def run_fixture(
    name: str,
    request: Request,
    arm: Arm,
    path: str,
    harness: Harness | None = None,
    place: Place | None = None,
) -> tuple[str, str, int | None, dict[str, Any]]:
    """Build the fixture, let the model act in it through the harness, then judge what it left.

    The graders never enter the workspace: the fixture's setup writes them to a stage, a folder
    of its own outside the workspace, which exists for this call only.

    Returns the answer, the report (the harness's output, then the post-checks'), its exit
    status (None where no call finished) and what the run's record keeps, the prompt among
    it. A post-check FAIL is the measurement; only a fixture that cannot be built, or a call
    that fails, is an error.
    """

    harness = harness or make_harness()
    place = place or Place()
    workdir = new_workspace(place.workspace)
    extra: dict[str, Any] = {
        "verdict": "UNVERIFIED",
        "claims": {},
        "fixture_repo": str(workdir),
        "harness": harness.name,
    }
    try:
        stage = new_stage((workdir, *((place.root,) if place.root else ())))
    except ValueError as problem:
        extra["error"] = f"the grading stage could not be made: {problem}"
        return "", extra["error"], None, extra
    try:
        return _call_and_judge(
            name, request, arm, path, harness, Scene(workdir, stage, place, extra)
        )
    finally:
        shutil.rmtree(stage, ignore_errors=True)


class Instruments(NamedTuple):
    """What the runner sets around one call: the call's PATH (a suite fixture's stubs folder
    first), its budget, the stubs placed and their digests before the call, the watch log and
    its watcher, and the fixture's suite (None for a fixture without a suite.json)."""

    path: str
    budget: Budget
    stubs: Path | None = None
    before: tuple[tuple[str, str], ...] = ()
    watch_log: Path | None = None
    watcher: Watcher | None = None
    suite: Suite | None = None

    def protected(self) -> tuple[Path, ...]:
        """The runner-owned paths the call reads and must not write."""

        return tuple(path for path in (self.stubs, self.watch_log) if path is not None)


def instruments(suite: Suite | None, workdir: Path, place: Place, path: str) -> Instruments:
    """The instruments of one call: for a suite fixture, its stubs placed read-only in their
    own folder (Place.stubs, else beside the workspace) put first on `path`, a watcher of its
    watch paths that writes Place.watch (else a file beside the workspace), and its budget; for
    any other fixture, `path` and CALL_TIMEOUT. OSError or a StubError where a stub cannot be
    placed."""

    if suite is None:
        return Instruments(path, Budget(CALL_TIMEOUT))
    budget = Budget(suite.timeout or CALL_TIMEOUT, suite.input_cap)
    stubs, before = None, {}
    if suite.stubs:
        stubs = place.stubs or workdir.parent / f"{workdir.name}.stubs"
        before = stub_place.place(suite.stubs, stubs, stub_source())
        path = f"{stubs}{os.pathsep}{path}"
    placed = tuple(before.items())
    log = place.watch or workdir.parent / f"{workdir.name}.watch.jsonl"
    return Instruments(path, budget, stubs, placed, log, Watcher(workdir, suite.watch, log), suite)


def budget_record(extra: dict[str, Any], returncode: int | None, elapsed: float) -> dict[str, Any]:
    """The call's budget record: why it was stopped (`input_cap`, `timeout`, or None where it
    ended by itself), the input it used (the cached among it), the uncached input and the
    output, from its session's own counts (None where none were read), and its seconds. A
    harness that names no stop, and a call that did not finish without a runner fault, is a
    `timeout`."""

    if "stopped" in extra:
        stopped = extra["stopped"]
    else:
        stopped = "timeout" if returncode is None and not extra.get("error") else None
    tokens = extra.get("session_tokens") or {}
    used, cached = tokens.get("input_tokens"), tokens.get("cached_input_tokens")
    return {
        "stopped": stopped,
        "input": used,
        "uncached": used - cached if used is not None and cached is not None else None,
        "output": tokens.get("output_tokens"),
        "seconds": elapsed,
    }


def after_call(
    kit: Instruments, extra: dict[str, Any], returncode: int | None, elapsed: float
) -> CallRecords:
    """What the call left beside its workspace, recorded in `extra` and returned for the
    checks: the budget record, the stubs' digests after the call (the folder is then made
    writable again, its files left read-only), and the watch log, its count of changes and its
    digest."""

    budget = budget_record(extra, returncode, elapsed)
    digests = None
    if kit.stubs is not None:
        before = dict(kit.before)
        digests = stub_place.record(before, stub_place.digests(kit.stubs, tuple(before)))
        with contextlib.suppress(OSError):
            stub_place.release(kit.stubs)
    log = kit.watch_log
    extra.update(
        tier=kit.suite.tier if kit.suite else None,
        suite_sha256=kit.suite.sha256 if kit.suite else None,
        budget=budget,
        stubs={"dir": str(kit.stubs), "digests": digests} if kit.stubs is not None else None,
        watch_log=str(log) if log is not None else None,
        watch_changes=kit.watcher.changes if kit.watcher is not None else None,
        watch_sha256=_file_digest(log) if log is not None else None,
    )
    kept = log if log is not None and log.is_file() else None
    return CallRecords(budget, kept, kit.stubs, digests)


def _file_digest(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def stop_of(meta: dict[str, Any]) -> str | None:
    """Why the run's call was stopped by its budget or its time, or None. A record from before
    the budget record kept a timeout as its error, and it counts the same."""

    budget = meta.get("budget")
    if isinstance(budget, dict) and budget.get("stopped"):
        return str(budget["stopped"])
    return "timeout" if TIMED_OUT.search(str(meta.get("error") or "")) else None


def judge_stop(extra: dict[str, Any], stopped: str | None) -> None:
    """A call stopped at its budget or its time fails the run, whatever its checks found; the
    checks' own verdict is kept as `checks_verdict`, and its claims stand as they were graded."""

    if stopped:
        extra["checks_verdict"] = extra.get("verdict")
        extra["verdict"] = "FAIL"


def _call_and_judge(
    name: str, request: Request, arm: Arm, path: str, harness: Harness, scene: Scene
) -> tuple[str, str, int | None, dict[str, Any]]:
    workdir, stage, place, extra = scene
    keep = place.keep or workdir.parent / f"{workdir.name}.native.jsonl"
    try:
        suite = fixture_suite(name)
    except SuiteError as problem:
        extra["error"] = f"{SUITE_FILE}: {problem}"
        return "", extra["error"], None, extra
    failure, protected, seed, prompt = build_workspace(name, arm, workdir, extra, stage)
    if failure is not None:
        return "", failure, None, extra
    extra["prompt"] = prompt
    sealed = seal_inputs(stage, name)  # after the build and before the call; checked after it
    grading_files = grading_digest(evals_dir(), name)
    sandbox = fixture_install(name).sandbox
    try:
        kit = instruments(suite, workdir, place, path)
    except (OSError, ValueError) as problem:
        extra["error"] = f"the call's stubs could not be placed: {problem}"
        return "", extra["error"], None, extra

    started = time.monotonic()
    answer, transcript, returncode = "", "", None
    try:
        with kit.watcher or contextlib.nullcontext():
            result = harness.call(
                prompt,
                request._replace(
                    local_listener=needs_local_listener(name),
                    sandbox=sandbox,
                    budget=kit.budget,
                    protected=kit.protected(),
                    unreadable=(stage,),
                ),
                workdir,
                fixture_write_roots(name, workdir),
                kit.path,
                keep,
            )
        answer, transcript, returncode = result.answer, result.transcript, result.returncode
        extra.update(result.extras)
        extra["identity_error"] = result.error
        extra["observed"] = result.observed
        extra["model_observed"] = (result.observed or {}).get("model")
    except (OSError, ValueError, subprocess.SubprocessError) as problem:
        # The post-checks still run: a call that failed may have changed the repository.
        extra["error"] = f"{type(problem).__name__}: {problem}"
        transcript = partial_output(problem)
    elapsed = round(time.monotonic() - started, 1)
    records = after_call(kit, extra, returncode, elapsed)

    intact, report, graders = judged_inputs(name, scene, sealed, protected)
    left = Left(seed, transcript, answer, records)
    report = grade(name, workdir, left, (intact, report), extra, graders)
    judge_stop(extra, stop_of(extra))
    extra.update(
        protected_snapshot=protected,
        elapsed_seconds=elapsed,
        grading_files_sha256=grading_files,
        graders_copy=graders.name if graders else None,
        # Taken last, after the post-checks: it is what a later `--regrade` finds.
        workspace_sha256=workspace_digest(workdir, {**child_env(), **HERMETIC_GIT}),
    )
    return answer, report, returncode, extra


def judged_inputs(
    name: str, scene: Scene, sealed: Sealed, protected: dict[str, str]
) -> tuple[bool, str, Path | None]:
    """After the call: whether every grading input is as it was (the protected files of the
    workspace, the stage and the grading files), the report that says so, and, where all are,
    the sealed copy of the graders that the post-checks run from."""

    workdir, _stage, place, extra = scene
    intact, report = check_protected(workdir, protected)
    held, moved = check_graders(sealed, name)
    if intact and held:
        graders = place.graders or workdir.parent / f"{workdir.name}{SEALED_SUFFIX}"
        try:
            extra["graders_sha256"] = seal_graders(sealed, name, graders)
            return True, report, graders
        except SealMoved as problem:
            moved = str(problem)
        except OSError as problem:
            extra["error"] = f"the graders could not be sealed: {type(problem).__name__}: {problem}"
            moved = f"UNVERIFIED sealed-graders — {problem}"
    lines = [line for line in (report if not intact else "", moved) if line]
    return False, "\n".join(lines), None


class Left(NamedTuple):
    """What a run left to judge, besides its workspace: the seed commit read before the model
    ran, the transcript document, the final answer and what the runner recorded around the
    call."""

    seed: str | None
    transcript: str
    answer: str
    records: CallRecords | None = None


def grade(
    name: str,
    workdir: Path,
    left: Left,
    protected: tuple[bool, str],
    extra: dict[str, Any],
    graders: Path | None = None,
) -> str:
    """Judge what a run left: the post-checks, from the run's sealed copy of its graders, unless
    a grading input changed (`protected` is whether none did, and the protected check's report).
    Sets the verdict, the claims and what the checks observed in `extra`, and returns the
    report: the transcript, then the protected check and the post-checks' own output."""

    seed, transcript, answer, records = left
    intact, protected_report = protected
    verdict, output, log_dir = "FAIL", "VERDICT: FAIL\n", None
    if intact:
        try:
            verdict, output, log_dir = post_check(
                FIXTURES / name, workdir, seed, transcript, answer, Judging(graders, records)
            )
        except (OSError, subprocess.SubprocessError) as problem:
            extra["error"] = f"post-check {type(problem).__name__}: {problem}"
            verdict, output = "UNVERIFIED", partial_output(problem)
    extra.update(
        verdict=verdict,
        claims={claim: result for result, claim in CLAIM_LINE.findall(output)},
        protected_intact=intact,
        observations=observations(log_dir),
        seed_sha=seed,
        post_check_log_dir=str(log_dir) if log_dir else None,
    )
    return f"{transcript}\n\n--- post-checks ---\n{protected_report}\n{output}"


def call_error(returncode: int | None, answer: str, extra: dict[str, Any], model: str) -> str:
    """Why this run's call does not count, or an empty string where it does.

    The identity is the harness's: its `identity_error` names the item of the native session
    that is missing or differs from what the run asked for. A run with no observed model never
    counts, whatever it requested. A call stopped at its budget or its time counts, with its
    exit status and its answer as the stop left them: the run fails, and is not void."""

    name = extra.get("harness", HARNESS)
    if extra.get("error"):
        return str(extra["error"])
    if not stop_of(extra) and returncode != 0:
        return f"{name} exited {returncode}"
    if not stop_of(extra) and not answer.strip():
        return f"{name} produced no final message"
    if extra.get("identity_error"):
        return str(extra["identity_error"])
    seen = extra.get("model_observed")
    if not seen:
        return f"{name} did not report the model it ran"
    if seen != model:
        return f"{name} reported running {seen}, not {model}"
    return ""


def _write(path: Path, document: Any) -> None:
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def workspace_root(option: str) -> Path | None:
    """Where fixture workspaces are kept: `--workspace-root`, else the environment's named
    root, else None for a temporary directory each."""

    named = option or os.environ.get(EVAL_ROOT_ENV) or os.environ.get(FIXTURE_ROOT_ENV)
    return Path(named).resolve() if named else None


def workspace_path(root: Path, out: Path, name: str, repetition: int) -> Path:
    return root / out.name / f"{name}-r{repetition}"


def refuse_workspaces(root: Path, paths: list[Path]) -> str:
    """Why the workspaces cannot be made, or an empty string: the root, or a parent of one,
    holds a Git checkout (a fixture must not be read as part of one), or a path exists."""

    for folder in (root, *root.parents):
        if (folder / ".git").exists():
            return f"workspace root {root} is inside a Git checkout ({folder}); name another"
    taken = [str(path) for path in paths if path.exists()]
    return "workspace already exists: " + ", ".join(taken) if taken else ""


# What the bare arm records of each fixture: the instruction files and OutcomeBound folders it
# removed, and those a nested repository kept.
BARE_RECORDS = ("instructions_removed", "instructions_kept")


def bare_record(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """What STATUS.json keeps of the bare arm's removals, by fixture; nothing for another arm."""

    return {
        key: {row["fixture"]: row[key] for row in rows if key in row}
        for key in BARE_RECORDS
        if any(key in row for row in rows)
    }


def index_row(status: dict[str, Any], name: str, meta: dict[str, Any]) -> dict[str, Any]:
    """One run's line in INDEX.json: what ran and where its evidence is."""

    return {
        "fixture": name,
        "harness": meta.get("harness", status["harness"]),
        "arm": status["arm"],
        "model": status["model"],
        "effort": status["effort"],
        "verdict": meta["verdict"],
        "error": meta["error"],
        "thread_id": meta.get("thread_id"),
        "native_session": meta.get("native_session"),
        "workspace": meta.get("fixture_repo"),
        **{key: meta[key] for key in BARE_RECORDS if key in meta},
    }


def run_one(
    out: Path,
    status: dict[str, Any],
    name: str,
    arm: Arm,
    path: str,
    harness: Harness,
) -> tuple[bool, dict[str, Any]]:
    """One fixture under the run's arm, recorded in `out`; whether its call failed, and its
    INDEX row. The workspace is kept under the status's root, if it names one, and the
    harness's session record is copied to `<fixture>.native.jsonl`; a suite fixture's stubs are
    placed in `<fixture>.stubs/` and its watch log is `<fixture>.watch.jsonl`."""

    root = status.get("workspace_root")
    workspace = workspace_path(Path(root), out, name, status["repetition"]) if root else None

    answer, report, returncode, extra = run_fixture(
        name,
        Request(status["model"], status["effort"], service_tier=status.get("service_tier", "")),
        arm,
        path,
        harness,
        Place(
            workspace,
            out / f"{name}.native.jsonl",
            out / f"{name}{SEALED_SUFFIX}",
            Path(root) if root else None,
            out / f"{name}.stubs",
            out / f"{name}.watch.jsonl",
        ),
    )
    (out / f"{name}.prompt.md").write_text(extra.pop("prompt", ""), encoding="utf-8")
    error = call_error(returncode, answer, extra, status["model"])
    extra.pop("error", None)
    (out / f"{name}.answer.md").write_text(answer, encoding="utf-8")
    (out / f"{name}.transcript.txt").write_text(report, encoding="utf-8")
    record = {**status, **arm.record(), "fixture": name}
    meta = {**record, "returncode": returncode, "error": error, **extra}
    _write(out / f"{name}.meta.json", meta)
    claims = ", ".join(f"{claim} {verdict}" for claim, verdict in extra["claims"].items())
    tokens = extra.get("session_tokens")
    cost = f"; {_spent(tokens)}, {extra.get('elapsed_seconds')} seconds" if tokens else ""
    stopped = f"; stopped: {stop_of(meta)}" if stop_of(meta) else ""
    print(f"{name}: {extra['verdict']}" + (f" ({claims})" if claims else "") + cost + stopped)
    if error:
        sys.stderr.write(f"run: {name}: {error}\n")
    return bool(error), index_row(status, name, meta)


REGRADED = "regraded_from"
UNVERIFIED = "UNVERIFIED"
POST_CHECKS = "\n--- post-checks ---\n"


def _regrade_files(path: Path, name: str, meta: dict[str, Any], plan: dict[str, Any]) -> str:
    """Name the saved files of the run in `plan`, and why one is missing or differs from its
    recorded digest; an empty string where all is well."""

    for key, suffix in (
        ("answer", "answer.md"),
        ("prompt", "prompt.md"),
        ("saved", "transcript.txt"),
    ):
        plan[key] = path.with_name(f"{name}.{suffix}")
        if not plan[key].is_file():
            return f"{plan[key].name} is missing"
    plan["native"] = path.with_name(f"{name}.native.jsonl")
    if plan["native"].is_file():
        recorded = meta.get("native_sha256")
        if recorded and hashlib.sha256(plan["native"].read_bytes()).hexdigest() != recorded:
            return f"{plan['native'].name} differs from the digest the meta recorded"
    else:
        plan["native"] = None
    log = meta.get("watch_log")
    if log and _file_digest(Path(log)) != meta.get("watch_sha256"):
        return f"the watch log {log} is missing or differs from the digest the meta recorded"
    return ""


def kept_records(meta: dict[str, Any]) -> CallRecords:
    """What the runner recorded around a kept run's call, as its meta keeps it, for judging it
    again; none of it for a record from before it was kept."""

    stubs = _object(meta.get("stubs"))
    return CallRecords(
        _object(meta.get("budget")) or None,
        Path(meta["watch_log"]) if meta.get("watch_log") else None,
        Path(stubs["dir"]) if stubs.get("dir") else None,
        stubs.get("digests"),
    )


def _object(value: Any) -> dict[str, Any]:
    """`value` where a record keeps an object there, else an empty one."""

    return value if isinstance(value, dict) else {}


def native_records(raw: bytes) -> list[dict[str, Any]]:
    """The records of a kept session copy; for a call stopped while its tool wrote, the copy's
    complete lines (the harness recorded the unfinished one as `native_partial_tail`)."""

    try:
        return parse_records(raw)
    except ValueError:
        return parse_records(raw.rpartition(b"\n")[0])


def kept_transcript(plan: dict[str, Any], meta: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
    """A kept run's transcript, with its command directories set again from its native copy
    and, where it kept none, each command's output from its events; its answer, and what
    setting the directories recorded."""

    saved = plan["saved"].read_text(encoding="utf-8", errors="replace")
    transcript = saved.split(POST_CHECKS, 1)[0]
    answer = plan["answer"].read_text(encoding="utf-8")
    session = None
    if meta.get("harness", HARNESS) == HARNESS:
        # A transcript kept before `outputs` were written gains them from its own events.
        transcript = with_outputs(transcript)
        if plan["native"]:
            session = native_records(plan["native"].read_bytes())
    transcript, filled = fill_directories(transcript, session)
    return transcript, answer, filled


def _regrade_graders(path: Path, name: str, meta: dict[str, Any], plan: dict[str, Any]) -> str:
    """Find the graders that judge the run again, in `plan`, and why they cannot: the run's own
    sealed copy where it kept one, which must be as its digest says; otherwise this checkout's
    files, which must be as the run recorded them, where it recorded them."""

    sealed = meta.get("graders_sha256")
    if sealed:
        copy = path.with_name(f"{name}{SEALED_SUFFIX}")
        if not copy.is_dir():
            return f"{copy.name} is missing"
        if tree_digest(copy) != sealed:
            return f"{copy.name} differs from the digest the meta recorded (graders_sha256)"
        # The copy keeps the grading files' paths under `evals/`, so their digest reproduces; a
        # record that kept none is not complete.
        recorded = meta.get("grading_files_sha256")
        if recorded and grading_digest(copy / "evals", str(name)) != recorded:
            return f"{copy.name} holds grading files that differ from grading_files_sha256"
        plan["graders"] = copy
        plan["grading_files"] = "PASS" if recorded else UNVERIFIED
        return ""
    recorded = meta.get("grading_files_sha256")
    if recorded and recorded != grading_digest(evals_dir(), str(name)):
        return "this checkout's fixture files under evals/ differ from the ones the run used"
    plan["grading_files"] = "PASS" if recorded else UNVERIFIED
    return ""


def _regrade_plan(source: Path, path: Path, meta: dict[str, Any]) -> tuple[dict[str, Any], str]:
    """What one kept run needs to be judged again, and why it cannot be: the saved files, the
    sealed copy of its graders, the workspace and the digests, each compared where the source run
    recorded one.

    The returned dict holds the paths and the statements for the new meta; the string is the
    reason to refuse, or empty."""

    name = meta.get("fixture", "")
    plan: dict[str, Any] = {"meta": meta, "name": name, "graders": None}
    if not name:
        return plan, "the meta names no fixture"
    if not meta.get("graders_sha256") and not (FIXTURES / str(name) / "post.plan.json").is_file():
        return plan, f"this checkout has no fixture {name!r}"
    refused = _regrade_files(path, name, meta, plan)
    if refused:
        return plan, refused
    workdir = Path(str(meta.get("fixture_repo", "")))
    if not workdir.is_dir():
        return plan, f"the kept workspace {workdir} is missing"
    plan["workdir"] = workdir
    refused = _regrade_graders(path, name, meta, plan)
    if refused:
        return plan, refused
    before = workspace_digest(workdir, {**child_env(), **HERMETIC_GIT})
    recorded = meta.get("workspace_sha256")
    if recorded and recorded != before:
        return plan, "the kept workspace differs from the state the run left"
    plan["workspace_unchanged"] = "PASS" if recorded and before else UNVERIFIED
    return plan, ""


def _regrade_protected(workdir: Path, meta: dict[str, Any]) -> tuple[bool, str, str]:
    """The protected check as the source run recorded it: against its snapshot where it kept
    one; otherwise (a run from before snapshots were kept) its own result is carried."""

    snapshot = meta.get("protected_snapshot")
    if isinstance(snapshot, dict) and snapshot:
        intact, report = check_protected(workdir, snapshot)
        return intact, report, "PASS" if intact else "FAIL"
    intact = meta.get("protected_intact") is True
    report = (
        f"{UNVERIFIED} protected-grading-inputs - the source record keeps no snapshot; its own "
        f"result is carried: {'intact' if intact else 'changed'}"
    )
    return intact, report, UNVERIFIED


def regrade(source: Path, out: Path) -> int:
    """Judge the runs kept under `source` again, with no model call, into the new `out`.

    Each run's workspace, saved transcript, answer, seed and native session copy are read; the
    command records are rebuilt from the native session (`fill_directories`); the protected
    check and the post-checks run as in a normal run, from a new grading folder. The observed
    identity and the call's own record stay as the source run kept them. Exit 2, with nothing
    written, where any run cannot be judged again: a digest differs or a file is missing.
    """

    paths = sorted(source.glob("*.meta.json"))
    if not paths:
        print(f"no run records under {source}")
        return 1
    plans, refusals = [], []
    for path in paths:
        meta = json.loads(path.read_text(encoding="utf-8"))
        plan, why = _regrade_plan(source, path, meta)
        plans.append(plan)
        if why:
            refusals.append(f"regrade: refused {plan['name'] or path.name}: {why}")
    if refusals:
        sys.stderr.write("\n".join(refusals) + "\n")
        return 2
    try:
        out.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        raise SystemExit(f"regrade: {out} already exists; name a new --out") from None
    rows = []
    for plan in plans:
        rows.append(_regrade_one(source, out, plan))
        _write(out / "INDEX.json", rows)
    return 0


def _regrade_one(source: Path, out: Path, plan: dict[str, Any]) -> dict[str, Any]:
    meta, name, workdir = plan["meta"], plan["name"], plan["workdir"]
    transcript, answer, filled = kept_transcript(plan, meta)
    intact, protected_report, protected_check = _regrade_protected(workdir, meta)
    extra: dict[str, Any] = {}
    left = Left(meta.get("seed_sha"), transcript, answer, kept_records(meta))
    report = grade(name, workdir, left, (intact, protected_report), extra, plan["graders"])
    judge_stop(extra, stop_of(meta))
    problem = extra.pop("error", "")
    record = {
        **meta,
        **extra,
        **filled,
        REGRADED: str(source),
        "error": meta.get("error") or problem,
        "protected_check": protected_check,
        "grading_files_unchanged": plan["grading_files"],
        "workspace_unchanged": plan["workspace_unchanged"],
        "workspace_sha256": workspace_digest(workdir, {**child_env(), **HERMETIC_GIT}),
    }
    (out / f"{name}.prompt.md").write_text(plan["prompt"].read_text(encoding="utf-8"), "utf-8")
    (out / f"{name}.answer.md").write_text(answer, encoding="utf-8")
    (out / f"{name}.transcript.txt").write_text(report, encoding="utf-8")
    if plan["native"]:
        shutil.copyfile(plan["native"], out / f"{name}.native.jsonl")
    if plan["graders"]:
        shutil.copytree(plan["graders"], out / f"{name}{SEALED_SUFFIX}", symlinks=True)
    _write(out / f"{name}.meta.json", record)
    claims = ", ".join(f"{claim} {verdict}" for claim, verdict in extra["claims"].items())
    print(f"{name}: {extra['verdict']}" + (f" ({claims})" if claims else ""))
    return index_row({"harness": HARNESS, **record}, name, record)


# --- rescore: a fixture's current graders on copies of kept workspaces -----------------------

# The name a kept workspace is moved to while its copy is graded at its own path; a folder left
# under this name by an interrupted rescore is the original, to be moved back by hand.
ASIDE = ".rescore-original"


def rebuilt_arm(name: str, meta: dict[str, Any]) -> tuple[Arm | None, str]:
    """The arm a kept run ran under, built again from this checkout, and why it cannot be: a
    plain arm, or an element arm from the elements its meta names; an arm from another ref or
    guidance set, or one with edits, whose text the meta does not keep, is refused."""

    if meta.get("earlier_ref") or meta.get("earlier_verbatim"):
        return None, "its arm came from --earlier-ref or --earlier-verbatim"
    if meta.get("edits"):
        return None, "its arm had --edits, whose text the meta does not keep"
    kind = str(meta.get("arm_kind") or meta.get("arm"))
    if kind not in ARMS:
        return None, f"its arm {kind!r} is not one of {', '.join(ARMS)}"
    harness = str(meta.get("harness") or HARNESS)
    if harness not in HARNESSES:
        return None, f"its harness {harness!r} is not one of {', '.join(HARNESSES)}"
    set_harness(harness)
    try:
        chosen = fixture_install(name)
    except InstallError as problem:
        return None, f"{INSTALL_FILE}: {problem}"
    elements = _object(meta.get("elements"))
    named = Elements(tuple(elements.get("dropped") or ()), tuple(elements.get("added") or ()))
    if named.named():
        base = load_arm("current", chosen.fragments, chosen.done, True)
        return element_arm(base, kind, named), ""
    return fixture_arm(name, load_arm(kind, chosen.fragments, chosen.done, chosen.adopted)), ""


def install_differences(arm: Arm, meta: dict[str, Any]) -> list[str]:
    """What the install this checkout makes differs in from the kept run's: the kernel, and each
    file whose digest differs or that only one of them installs."""

    record = arm.record()
    found = ["kernel"] if record["kernel_sha256"] != meta.get("kernel_sha256") else []
    kept = _object(meta.get("arm_files"))
    files = record["arm_files"]
    found += sorted(path for path in {*kept, *files} if kept.get(path) != files.get(path))
    return found


def _rescore_plan(path: Path, meta: dict[str, Any]) -> tuple[dict[str, Any], str]:
    """What one kept run needs to be scored with the current graders, and why it cannot be: its
    saved files as `--regrade` reads them, its kept workspace as the run left it, no folder left
    by an interrupted rescore, and its arm built again."""

    name = str(meta.get("fixture") or "")
    plan: dict[str, Any] = {"meta": meta, "name": name, "path": path}
    if not name or not (FIXTURES / name / "post.plan.json").is_file():
        return plan, f"this checkout has no fixture {name!r}"
    refused = _regrade_files(path, name, meta, plan)
    if refused:
        return plan, refused
    workdir = Path(str(meta.get("fixture_repo", "")))
    if not workdir.is_dir():
        return plan, f"the kept workspace {workdir} is missing"
    if workdir.with_name(workdir.name + ASIDE).exists():
        return plan, f"{workdir.name}{ASIDE} is left from an interrupted rescore; move it back"
    plan["workdir"] = workdir
    before = workspace_digest(workdir, {**child_env(), **HERMETIC_GIT})
    recorded = meta.get("workspace_sha256")
    if recorded and recorded != before:
        return plan, "the kept workspace differs from the state the run left"
    plan["before"] = before
    plan["workspace_unchanged"] = "PASS" if recorded else UNVERIFIED
    plan["arm"], refused = rebuilt_arm(name, meta)
    return plan, refused


def rescore(directories: list[Path]) -> int:
    """Score the runs kept under each of `directories` with each fixture's current graders,
    with no model call, and write `<fixture>.rescore-<graders digest>.json` beside each meta.

    The current graders are what a build of the fixture from this checkout, under the run's own
    arm, writes to its grading stage, sealed with the current plan and grading files; their copy
    is kept as `<fixture>.rescore-<digest>.graders`. Each kept workspace is moved aside and a
    copy of it is graded at its own path (checks read the paths the transcript records), then
    removed, and the workspace moved back and compared with its digest. The meta, the transcript
    and the verdicts of the run are never changed. What a setup derives from its build matches
    the kept workspace only where the build is deterministic, as the suite-v2 seeds are: the file
    says whether the build's seed commit and install match the run's. Exit 2, with nothing
    written, where any run cannot be scored; 1 where a run's build or grading failed."""

    plans, refusals = [], []
    for directory in directories:
        paths = sorted(directory.glob("*.meta.json"))
        if not paths:
            refusals.append(f"rescore: no run records under {directory}")
        for path in paths:
            meta = json.loads(path.read_text(encoding="utf-8"))
            plan, why = _rescore_plan(path, meta)
            plans.append(plan)
            if why:
                refusals.append(f"rescore: refused {path}: {why}")
    if refusals:
        sys.stderr.write("\n".join(refusals) + "\n")
        return 2
    return 1 if [plan for plan in plans if not _rescore_one(plan)] else 0


def current_graders(name: str, arm: Arm, destination: Path) -> tuple[str | None, str]:
    """Build the fixture from this checkout under `arm` in a temporary workspace, and seal what
    its setup wrote to the stage, with the current plan and grading files, into the new folder
    `destination`. The digest of the sealed copy and the seed commit of the build; None and the
    reason where the build failed."""

    workdir, extra = new_workspace(None), dict[str, Any]()
    stage = new_stage((workdir,))
    try:
        failure, _protected, seed, _prompt = build_workspace(name, arm, workdir, extra, stage)
        if failure is not None:
            return None, str(extra.get("error", "the fixture could not be built"))
        digest = seal(stage, FIXTURES / name / "post.plan.json", evals_dir(), name, destination)
    finally:
        shutil.rmtree(stage, ignore_errors=True)
        shutil.rmtree(workdir, ignore_errors=True)
    return digest, seed or ""


def _remove_copy(folder: Path) -> None:
    """Remove the graded copy whole, a read-only entry among it."""

    def writable(function: Any, path: str, _error: Any) -> None:
        os.chmod(os.path.dirname(path), 0o700)
        with contextlib.suppress(OSError):
            os.chmod(path, 0o700)
        function(path)

    shutil.rmtree(folder, onerror=writable)


def graded_copy(plan: dict[str, Any], graders: Path) -> dict[str, Any]:
    """Grade a copy of the kept workspace at its own path: the original is moved aside, copied
    back, the copy graded and removed, and the original moved back. What `grade` records."""

    meta, name, workdir = plan["meta"], plan["name"], plan["workdir"]
    transcript, answer, _filled = kept_transcript(plan, meta)
    aside = workdir.with_name(workdir.name + ASIDE)
    extra: dict[str, Any] = {}
    os.rename(workdir, aside)
    try:
        shutil.copytree(aside, workdir, symlinks=True)
        intact, protected_report, extra["protected_check"] = _regrade_protected(workdir, meta)
        left = Left(meta.get("seed_sha"), transcript, answer, kept_records(meta))
        grade(name, workdir, left, (intact, protected_report), extra, graders)
    finally:
        if workdir.exists():
            _remove_copy(workdir)
        os.rename(aside, workdir)
    judge_stop(extra, stop_of(meta))
    return extra


def _rescore_one(plan: dict[str, Any]) -> bool:
    """Score one planned run and write its rescore file; whether it was scored."""

    meta, name, path, arm = plan["meta"], plan["name"], plan["path"], plan["arm"]
    building = path.with_name(f"{name}.rescore-{uuid.uuid4().hex}.building")
    digest, seed = current_graders(name, arm, building)
    if digest is None:
        sys.stderr.write(f"rescore: {path}: the current graders could not be built: {seed}\n")
        return False
    target = path.with_name(f"{name}.rescore-{digest}.json")
    graders = path.with_name(f"{name}.rescore-{digest}.graders")
    if target.exists():
        shutil.rmtree(building, ignore_errors=True)
        print(f"{name}: already rescored with graders {digest[:12]} ({target.name})")
        return True
    if graders.exists():
        shutil.rmtree(graders)
    building.rename(graders)
    extra = graded_copy(plan, graders)
    after = workspace_digest(plan["workdir"], {**child_env(), **HERMETIC_GIT})
    if after != plan["before"]:
        sys.stderr.write(f"rescore: {path}: the kept workspace changed while it was scored\n")
        return False
    _write(
        target,
        {
            "fixture": name,
            "meta": path.name,
            "run_id": meta.get("run_id"),
            "repetition": meta.get("repetition"),
            "arm": meta.get("arm"),
            "thread_id": meta.get("thread_id"),
            "date": datetime.date.today().isoformat(),
            "source": source(),
            "original": {
                "graders_sha256": meta.get("graders_sha256"),
                "grading_files_sha256": meta.get("grading_files_sha256"),
                "verdict": meta.get("verdict"),
                "claims": meta.get("claims"),
            },
            "rescore": {
                "graders_sha256": digest,
                "graders_copy": graders.name,
                "grading_files_sha256": grading_digest(evals_dir(), name),
                "verdict": extra["verdict"],
                "checks_verdict": extra.get("checks_verdict", extra["verdict"]),
                "claims": extra["claims"],
                "observations": extra["observations"],
                "protected_check": extra["protected_check"],
                "error": extra.get("error"),
            },
            "install_differences": install_differences(arm, meta),
            # Grading data a setup derives from its build (a commit, a digest) matches the kept
            # workspace only where the build is the same: a seed commit that differs says not.
            "seed_matches_run": seed == meta.get("seed_sha") if meta.get("seed_sha") else None,
            "workspace_unchanged": plan["workspace_unchanged"],
        },
    )
    claims = ", ".join(f"{claim} {verdict}" for claim, verdict in extra["claims"].items())
    print(
        f"{name}: rescore {extra['verdict']}"
        + (f" ({claims})" if claims else "")
        + f" with graders {digest[:12]}; the original {meta.get('verdict')} is kept"
    )
    return True


def _provenance(metas: list[dict[str, Any]]) -> list[str]:
    """What makes recorded runs incomparable, each on one line."""

    lines = []
    for name in sorted({meta["arm"] for meta in metas}):
        runs = [meta for meta in metas if meta["arm"] == name]
        kernels = {meta["kernel_sha256"] for meta in runs}
        if len(kernels) > 1:
            lines.append(f"UNVERIFIED: the {name} arm ran {len(kernels)} different kernels")
        # A fixture's install selects its own fragments, so file sets compare within a fixture.
        for fixture in sorted({str(meta.get("fixture", "")) for meta in runs}):
            files = {
                json.dumps(meta.get("arm_files", {}), sort_keys=True)
                for meta in runs
                if str(meta.get("fixture", "")) == fixture
            }
            if len(files) > 1:
                where = f" for {fixture}" if fixture else ""
                lines.append(
                    f"UNVERIFIED: the {name} arm installed {len(files)} different file sets{where}"
                )
    commits = sorted({str(meta.get("commit")) for meta in metas})
    if len(commits) > 1:
        lines.append("runs span commits: " + ", ".join(commit[:12] for commit in commits))
    if any(meta.get("dirty") is not False for meta in metas):
        lines.append("UNVERIFIED: a run came from a checkout with uncommitted changes")
    return lines


def _with_tokens(path: Path, meta: dict[str, Any]) -> dict[str, Any]:
    """The record, with its tokens read from the saved transcript where it kept none, and its
    session's cost and skill catalog from the native copy beside it where it kept none."""

    if "tokens_used" not in meta:
        saved = path.with_name(path.name.replace(".meta.json", ".transcript.txt"))
        text = saved.read_text(encoding="utf-8", errors="replace") if saved.is_file() else ""
        meta = {**meta, "tokens_used": tokens_used(text)}
    if "session_tokens" not in meta or "catalog" not in meta:
        native = path.with_name(path.name.replace(".meta.json", ".native.jsonl"))
        try:
            records = native_records(native.read_bytes()) if native.is_file() else None
        except (OSError, ValueError):
            records = None
        meta = {"session_tokens": session_tokens(records), "catalog": catalog(records), **meta}
    return meta


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    middle = len(ordered) // 2
    return ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) / 2


def _medians(runs: list[dict[str, Any]]) -> str:
    """The median tokens and seconds over the runs that recorded each, or an empty string."""

    parts = []
    for key, label in (("tokens_used", "tokens"), ("elapsed_seconds", "seconds")):
        values = [float(run[key]) for run in runs if run.get(key) is not None]
        if values:
            parts.append(f"{label} {_median(values):g}")
    return ", ".join(parts)


def _spent(tokens: dict[str, Any]) -> str:
    """Tokens as a line gives them: input, with the cached and the uncached among it, and
    output, with the reasoning among it."""

    cached = round(tokens["cached_input_tokens"])
    uncached = round(tokens["input_tokens"] - tokens["cached_input_tokens"])
    reasoning = (
        "reasoning counted in it"
        if tokens.get("reasoning_in_output")
        else f"reasoning {round(tokens['reasoning_output_tokens'])}"
    )
    return (
        f"input {round(tokens['input_tokens'])} (cached {cached}, uncached {uncached}), "
        f"output {round(tokens['output_tokens'])} ({reasoning}) tokens"
    )


def _catalog_text(found: dict[str, Any] | None) -> str:
    """A call's skill catalog as a line gives it, or `unrecorded`."""

    if not found:
        return UNRECORDED
    plugins = ", ".join(f"{name} {count}" for name, count in found["plugins"].items())
    return (
        f"{found['skills']} skills, plugin skills {plugins or 'none'}; "
        f"developer messages {found['developer_characters']} characters"
    )


def _catalog_shape(found: dict[str, Any] | None) -> str:
    """What two calls' catalogs are compared by: the count of skills and each plugin's count.
    The developer messages' size is not among it: it holds the workspace's path."""

    if not found:
        return UNRECORDED
    return json.dumps([found["skills"], found["plugins"]], sort_keys=True)


def _catalog_lines(group: list[dict[str, Any]]) -> list[str]:
    """The skill catalog each call of the group was given, one line where all were given the
    same; a group whose calls saw different catalogs is flagged. Nothing for a group whose
    records come from before a native session was read."""

    if not any(run.get("session_tokens") or run.get("catalog") for run in group):
        return []
    runs = sorted(group, key=lambda run: run["repetition"])
    shapes = {_catalog_shape(run.get("catalog")) for run in runs}
    if len(shapes) == 1:
        sizes = sorted(run["catalog"]["developer_characters"] for run in runs if run.get("catalog"))
        found = runs[0].get("catalog")
        if found and sizes[0] != sizes[-1]:
            size = f"{sizes[0]} to {sizes[-1]}"
            found = {**found, "developer_characters": size}
        return [f"  catalog: {_catalog_text(found)}"]
    lines = [f"  UNVERIFIED: these calls saw {len(shapes)} different skill catalogs"]
    lines += [
        f"  repetition {run['repetition']} catalog: {_catalog_text(run.get('catalog'))}"
        for run in runs
    ]
    return lines


def _catalog_comparison(metas: list[dict[str, Any]]) -> list[str]:
    """For each fixture that more than one arm ran, a line where the arms' calls were given
    different plugin skills: the arms' own skills differ by design, the plugins should not."""

    lines = []
    for fixture in sorted({str(meta.get("fixture")) for meta in metas}):
        runs = [meta for meta in metas if str(meta.get("fixture")) == fixture]
        arms = sorted({str(meta["arm"]) for meta in runs})
        seen = {
            arm: sorted(
                {
                    json.dumps(meta["catalog"]["plugins"], sort_keys=True)
                    if meta.get("catalog")
                    else UNRECORDED
                    for meta in runs
                    if meta["arm"] == arm
                }
            )
            for arm in arms
        }
        if len(arms) > 1 and len({item for items in seen.values() for item in items}) > 1:
            lines.append(
                f"UNVERIFIED: the arms on {fixture} were given different plugin skills: "
                + "; ".join(f"{arm} {' or '.join(items)}" for arm, items in seen.items())
            )
    return lines


def _cost_lines(group: list[dict[str, Any]], runs: list[dict[str, Any]]) -> list[str]:
    """What the group's calls spent: the median tokens and seconds of the runs counted; then,
    from each session's own token counts, the median over the runs counted, the sum over every
    call, failed ones among them, and each run's own beside its verdict, where any call kept
    them."""

    lines = [f"  median {_medians(runs)}"] if _medians(runs) else []
    spent = [run for run in group if run.get("session_tokens")]
    if not spent:
        return lines
    counted = [run for run in runs if run.get("session_tokens")]
    if counted:
        median: dict[str, Any] = {
            key: _median([float(run["session_tokens"][key]) for run in counted])
            for key in COST_KEYS
        }
        median["reasoning_in_output"] = _reasoning_in_output(counted)
        lines.append(f"  median cost {_spent(median)} over {len(counted)} counted run(s)")
    total: dict[str, Any] = {
        key: sum(run["session_tokens"][key] for run in spent) for key in COST_KEYS
    }
    total["reasoning_in_output"] = _reasoning_in_output(spent)
    seconds = sum(float(run["elapsed_seconds"]) for run in group if run.get("elapsed_seconds"))
    failed = sum(1 for run in spent if run["error"] and not stop_of(run))
    lines.append(
        f"  spent on {len(spent)} call(s), {failed} failed among them: {_spent(total)}; "
        f"{seconds:.1f} seconds over all {len(group)}"
    )
    for run in sorted(group, key=lambda run: run["repetition"]):
        verdict = "call failed, not counted" if run["error"] else run["verdict"]
        if stop_of(run):
            verdict = f"stopped ({stop_of(run)}), counted as FAIL"
        tokens = _spent(run["session_tokens"]) if run.get("session_tokens") else "tokens unrecorded"
        lines.append(
            f"  repetition {run['repetition']}: {verdict}; {tokens}; "
            f"{_recorded(run.get('elapsed_seconds'))} seconds"
        )
    return lines


UNRECORDED = "unrecorded"


def _reasoning_in_output(runs: list[dict[str, Any]]) -> bool:
    """Whether every run's tool counts reasoning inside its output, with no count of its own."""

    return all(run["session_tokens"].get("reasoning_in_output") for run in runs)


def _recorded(value: Any) -> str:
    """A recorded field as text; a field the record does not keep is its own value."""

    return UNRECORDED if value is None else str(value)


def _instrument(meta: dict[str, Any]) -> tuple[str, str, str, str, str]:
    """What the run was measured with: its kernel, the files its install wrote, the graders that
    judged it, the grading files they read, and an element arm's elements and edits (none for
    any other arm, whether its record names them or not). Records that differ in one are not one
    group."""

    files = meta.get("arm_files")
    elements = meta.get("elements") or {}
    shape = {key: value for key, value in elements.items() if value}
    if meta.get("edits"):
        shape["edits"] = meta["edits"].get("sha256")
    return (
        _recorded(meta.get("kernel_sha256")),
        UNRECORDED if files is None else json.dumps(files, sort_keys=True),
        _recorded(meta.get("graders_sha256")),
        _recorded(meta.get("grading_files_sha256")),
        json.dumps(shape, sort_keys=True) if shape else "none",
    )


def _attempt(meta: dict[str, Any]) -> tuple[str, ...] | None:
    """Which attempt a record measured: its native thread, else the run that made the call (a
    run names one fixture once per repetition). None where it keeps neither."""

    if meta.get("thread_id"):
        return ("thread", str(meta["thread_id"]))
    if meta.get("run_id"):
        return ("run", str(meta["run_id"]), str(meta.get("fixture")), str(meta.get("repetition")))
    return None


def _attempts(
    metas: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[int, list[dict[str, Any]]], dict[int, int]]:
    """The records that stand for one attempt each, the other measurements of each (a regrade of
    it) by the id of the record they belong to, and how many further copies of it were found.

    An original stands for its attempt; a regrade only where no original was kept beside it. The
    first record found stands where several of one kind are."""

    standing: dict[tuple[str, ...], dict[str, Any]] = {}
    for meta in metas:
        key = _attempt(meta)
        if key is not None:
            held = standing.get(key)
            if held is None or (held.get(REGRADED) and not meta.get(REGRADED)):
                standing[key] = meta
    counted: list[dict[str, Any]] = []
    alternates: dict[int, list[dict[str, Any]]] = {}
    copies: dict[int, int] = {}
    for meta in metas:
        key = _attempt(meta)
        stands = standing.get(key) if key is not None else None
        if stands is None or stands is meta:
            counted.append(meta)
        elif meta.get(REGRADED) and not stands.get(REGRADED):
            alternates.setdefault(id(stands), []).append(meta)
        else:
            copies[id(stands)] = copies.get(id(stands), 0) + 1
    return counted, alternates, copies


def _short(text: str) -> str:
    return text if text in (UNRECORDED, "none") else hashlib.sha256(text.encode()).hexdigest()[:12]


def _regrade_line(run: dict[str, Any], other: dict[str, Any]) -> str:
    claims = sorted(
        claim
        for claim in {*run["claims"], *other["claims"]}
        if run["claims"].get(claim) != other["claims"].get(claim)
    )
    differing = f"; claims that differ: {', '.join(claims)}" if claims else ""
    return (
        f"  repetition {run['repetition']} regrade (an alternate measurement of this attempt, "
        f"not counted): {other['verdict']}; the original {run['verdict']} is kept{differing}"
    )


def summarize(directories: list[Path]) -> int:
    """Print, per fixture and arm, how many runs PASS the verdict and each claim, and the
    median tokens and seconds of the runs counted.

    Records are grouped by fixture, harness, arm, model and effort and by the instrument that
    measured them (kernel, installed files and graders, a field not recorded being a value of
    its own), so runs of different instruments are never pooled. An attempt counts once, by its
    native thread or run: a regrade of it, and a further copy of its record, are printed and not
    counted. A run whose call failed measured the call, not the model, so it is named and not
    counted; a call stopped at its budget or its time (`stop_of`) measured the model, and counts
    as a FAIL. A run whose record keeps no token count has it read from the transcript saved
    beside it.
    """

    metas = [
        _with_tokens(path, json.loads(path.read_text(encoding="utf-8")))
        for directory in directories
        for path in sorted(directory.rglob("*.meta.json"))
    ]
    if not metas:
        print("no run records under " + ", ".join(str(item) for item in directories))
        return 1
    counted, alternates, copies = _attempts(metas)
    # The harness is part of the key: runs of different harnesses are never merged. A record
    # from before runs named a harness came from codex.
    groups: dict[tuple[str, ...], list[dict[str, Any]]] = {}
    for meta in counted:
        label = (meta["fixture"], meta.get("harness", HARNESS), meta["arm"], meta["model"])
        groups.setdefault((*label, meta["effort"], *_instrument(meta)), []).append(meta)
    labels = [group_key[:5] for group_key in groups]
    for group_key, group in sorted(groups.items()):
        _print_group(group_key, group, labels.count(group_key[:5]) > 1, alternates, copies)
    for line in [*_provenance(metas), *_catalog_comparison(counted)]:
        print(line)
    return 0


def _isolation_lines(group: list[dict[str, Any]]) -> list[str]:
    """Each Claude Code cell's isolation verdict (PASS, UNVERIFIED with the items no record
    names, or FAIL), one line a repetition; nothing for a run that records none."""

    lines = []
    for run in sorted(group, key=lambda run: run["repetition"]):
        if run.get("isolation_verdict"):
            items = run.get("isolation_unverified") or []
            named = f" ({', '.join(items)})" if items else ""
            lines.append(
                f"  repetition {run['repetition']} isolation: {run['isolation_verdict']}{named}"
            )
    return lines


def _print_group(
    key: tuple[str, ...],
    group: list[dict[str, Any]],
    split: bool,
    alternates: dict[int, list[dict[str, Any]]],
    copies: dict[int, int],
) -> None:
    """One group's counts and lines; its instrument where another group has the same label."""

    fixture, harness_name, arm, model, effort, *instrument = key
    counted = (run for run in group if not run["error"] or stop_of(run))
    runs = sorted(counted, key=lambda run: run["repetition"])
    passed = sum(1 for run in runs if run["verdict"] == "PASS" and not stop_of(run))
    failed = len(group) - len(runs)
    stopped = sum(1 for run in runs if stop_of(run))
    notes = [
        *([f"{failed} failed call(s) not counted"] if failed else []),
        *([f"{stopped} stopped at the budget or the timeout, counted as FAIL"] if stopped else []),
    ]
    tail = f" ({'; '.join(notes)})" if notes else ""
    print(f"{fixture} | {harness_name} | {arm} | {model} {effort}: PASS {passed}/{len(runs)}{tail}")
    if split:
        names = ("kernel", "files", "graders", "grading files", "elements")
        found = zip(names, instrument, strict=True)
        print("  instrument: " + ", ".join(f"{name} {_short(value)}" for name, value in found))
    for line in [*_cost_lines(group, runs), *_catalog_lines(group), *_isolation_lines(group)]:
        print(line)
    for claim in dict.fromkeys(claim for run in runs for claim in run["claims"]):
        count = sum(1 for run in runs if run["claims"].get(claim) == "PASS")
        print(f"  {claim}: PASS {count}/{len(runs)}")
    for run in runs:
        if not run["protected_intact"]:
            print(f"  repetition {run['repetition']}: a grading input was changed")
        for line in run["observations"]:
            print(f"  repetition {run['repetition']} {line}")
    for run in sorted(group, key=lambda run: run["repetition"]):
        for other in alternates.get(id(run), []):
            print(_regrade_line(run, other))
    extra = sum(copies.get(id(run), 0) for run in group)
    if extra:
        print(f"  {extra} further record(s) of an attempt already counted, not counted")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="evals/run.py",
        description=(
            "Hand a harness (default codex) each fixture's task behind one arm's kernel, in a "
            "disposable repository, and judge what the model left with the fixture's "
            "deterministic post-checks. See evals/README.md."
        ),
        epilog=(
            f"arms: {EARLIER} is an earlier wording of the kernel ({EARLIER_KERNEL.name}); "
            f"current is what `outcomebound adopt --harness {HARNESS}` installs from this "
            f"checkout: {TEMPLATE} rendered as adopt renders it, the whole folder of each "
            f"skill that install carries at {HARNESS}'s skill path (the fourteen every install "
            f"carries), and {LAUNCHER} "
            f"first on the call's PATH; {UNSIZED} is current without the kernel's sizing "
            f"paragraph; {NONE} is the task alone, with no kernel, skill or launcher; "
            f"{FACTS_ONLY} is the fixture's note and what `outcomebound adopt --facts-only` "
            "installs for the harness, with the launcher; "
            f"{BARE} is {NONE} with no instruction file at all, the fixture's own note among "
            "them. The model is always named and passed to codex with -m, so codex's configured "
            "default never runs. Each arm's measurement is "
            f"{len(default_fixtures())} fixtures x {MEASURED} repetitions: "
            f"{len(default_fixtures()) * MEASURED} runs; "
            "the handoff, lifecycle, adoption and suite-v2 (v2-) "
            "fixtures run only when --fixtures names them. "
            "On a fixture with an install.json, an element arm measures one part of the "
            f"install: --drop takes elements from current, --add puts elements into {NONE}, "
            "and --edits changes the installed text; elements are "
            f"{KERNEL_ELEMENT} (the operating-contract block), {FACTS_ELEMENT} (the "
            f"project-facts block), {POINTERS_ELEMENT} (the guidance-pointers block whole), "
            "fragment:<id> (its file and pointer line), skill:<name> (its folder and pointer "
            f"line) and {LAUNCHER_ELEMENT} (on the call's PATH). Each is built from adopt's own "
            "install with no model call; --dump-arm shows it, and STATUS.json and each meta "
            "record arm_kind, elements and the edits' digests."
        ),
    )
    parser.add_argument(
        "--arm",
        choices=ARMS,
        help=f"{EARLIER}: an earlier wording of the kernel; current: what adopt "
        f"installs for {HARNESS}, and the launcher on PATH; {UNSIZED}: current without the "
        f"kernel's sizing paragraph; {NONE}: no kernel, skill or launcher; {FACTS_ONLY}: the "
        f"facts-only install, and the launcher on PATH; {BARE}: {NONE} with no instruction file",
    )
    parser.add_argument(
        "--drop",
        action="append",
        metavar="ELEMENT",
        help="with --arm current: the install less ELEMENT (kernel, facts, pointers, "
        "fragment:<id>, skill:<name> or launcher); repeat for more; the default label is "
        "current-minus-<element>[-<element>...], each ':' written as '.'",
    )
    parser.add_argument(
        "--add",
        action="append",
        metavar="ELEMENT",
        help=f"with --arm {NONE}: the {NONE} arm plus exactly ELEMENT, from adopt's own install; "
        f"repeat for more; the default label is {NONE}-plus-<element>[-<element>...]",
    )
    parser.add_argument(
        "--edits",
        default="",
        metavar="FILE",
        help='apply FILE, a JSON list of {"path", "old", "new"}, to the installed files after the '
        "install (AGENTS.md, a skill's or a fragment's file); each old occurs exactly once in its "
        "file, else the run exits 2 before it starts; an empty new deletes the text; with --arm "
        f"current (and --drop) or --arm {NONE} with --add, under --arm-label",
    )
    parser.add_argument(
        "--earlier-ref",
        default="",
        metavar="REF",
        help="make the earlier arm a full install of the engine at this Git ref of the "
        "checkout (kernel, skills, fragments), in place of the kept earlier kernel wording",
    )
    parser.add_argument(
        "--earlier-verbatim",
        default="",
        metavar="DIR",
        help="make the earlier arm another guidance set's own files: the AGENTS.md of DIR, a "
        "folder outside this checkout, above the fixture's own note, and the skills/ folders of "
        "DIR at codex's skill path, all as they are, with no kernel, facts block, pointers or "
        "launcher",
    )
    parser.add_argument(
        "--arm-label",
        default="",
        metavar="NAME",
        help="name the arm NAME in STATUS.json, the metas, INDEX.json and the summary, in place "
        "of its kind or an element arm's default label (for a ref, or edits, that stand for a "
        "variant of the guidance)",
    )
    parser.add_argument(
        "--harness",
        choices=HARNESSES,
        default=HARNESS,
        help=f"the tool that runs the model (default: %(default)s); with {CLAUDE} the current arm "
        f"is what adopt installs for {CLAUDE}",
    )
    parser.add_argument(
        "--plugin-dir",
        action="append",
        metavar="DIR",
        help=f"with --harness {CLAUDE}: load the plugin in DIR for each call (repeat for more); "
        f"DIR is a pinned clone inside the evals home's {THIRD_PARTY}/ folder, never a plugin "
        "cache, and the record names its commit",
    )
    parser.add_argument(
        "--model",
        default="",
        metavar="MODEL",
        help="the model the harness runs, always named",
    )
    parser.add_argument(
        "--effort", default="medium", help="the harness's reasoning effort (default: medium)"
    )
    parser.add_argument(
        "--service-tier",
        default="",
        metavar="TIER",
        help="the serving tier a codex call asks for, as `-c service_tier=TIER`; `priority` is "
        "codex's fast mode. The native session must show it. Default: none, codex's own tier; "
        "claude-code has no tier and refuses one",
    )
    parser.add_argument(
        "--fixtures",
        default=",".join(default_fixtures()),
        help="comma-separated fixtures to run (default: %(default)s)",
    )
    parser.add_argument(
        "--repetition",
        type=int,
        choices=REPETITIONS,
        default=1,
        metavar=f"{REPETITIONS[0]}..{REPETITIONS[-1]}",
        help=f"which repetition this run is, {REPETITIONS[0]} to {REPETITIONS[-1]}; a "
        f"measurement takes {MEASURED} (default: 1)",
    )
    parser.add_argument(
        "--out", default="", help="a new directory for the run (default: evals/results/raw/<id>)"
    )
    parser.add_argument(
        "--workspace-root",
        metavar="DIR",
        default="",
        help="keep each workspace at DIR/<run directory name>/<fixture>-r<repetition>, outside "
        f"any Git checkout (default: ${EVAL_ROOT_ENV}, else ${FIXTURE_ROOT_ENV}, else a "
        "temporary directory each)",
    )
    parser.add_argument(
        "--probe",
        action="store_true",
        help="make one minimal call, with the requested model and effort, and print whether the "
        "harness meets the run contract; runs no fixture",
    )
    parser.add_argument(
        "--regrade",
        metavar="DIR",
        help="judge again, with no model call, the runs kept under DIR: rebuild each run's "
        "command records from its native session copy and run the protected check and the "
        "post-checks on its kept workspace, from the run's own sealed graders, into the new "
        "--out; refuses where the sealed graders or the workspace differ from what the run "
        "recorded",
    )
    parser.add_argument(
        "--rescore",
        action="append",
        metavar="RUN_DIR",
        help="score, with no model call, the runs kept under RUN_DIR (repeat for more) with each "
        "fixture's current graders, built from this checkout under the run's own arm: a copy of "
        "each kept workspace is graded at its own path, and <fixture>.rescore-<graders "
        "digest>.json is written beside the meta with both graders' digests and the new "
        "verdicts; the meta, the transcript and the original verdicts are never changed",
    )
    parser.add_argument(
        "--dump-arm",
        metavar="FIXTURE",
        help="build FIXTURE under --arm and print, with no model call, what its call would "
        "receive (argv, prompt, instruction files from the workspace up, the Codex home or the "
        f"{CLAUDE} cell's environment, the launchers on PATH, the install's files) and each "
        f"isolation rule as PASS or FAIL; with --harness {CLAUDE}, the loading check against a "
        "synthetic start event too; exit 1 where a rule fails",
    )
    parser.add_argument(
        "--summary",
        nargs="+",
        metavar="DIR",
        help="print the verdicts the runs under each DIR recorded, what their calls spent "
        "(uncached input among it) and the skill catalog each call was given, and run nothing",
    )
    return parser


def checked_fixtures(parser: argparse.ArgumentParser, args: argparse.Namespace) -> list[str]:
    """The fixtures a run may start on; options this runner refuses exit 2."""

    if not args.model:
        parser.error("name the model: --model MODEL")
    if args.probe:
        return []
    if args.arm is None:
        parser.error("name the arm: " + ", ".join(f"--arm {name}" for name in ARMS))
    names = [name.strip() for name in args.fixtures.split(",") if name.strip()]
    unknown = sorted(set(names) - set(fixture_names()))
    if unknown or not names:
        parser.error(f"no fixture {', '.join(unknown)}; there are {', '.join(fixture_names())}")
    refused = [problem for problem in map(suite_refusal, names) if problem]
    if refused:
        parser.error("; ".join(refused))
    return names


def suite_refusal(name: str) -> str:
    """What is wrong with the fixture's suite.json, or an empty string where the runner reads
    it (or it has none)."""

    try:
        fixture_suite(name)
    except SuiteError as problem:
        return f"{name}/{SUITE_FILE}: {problem}"
    return ""


def fixture_arms(
    parser: argparse.ArgumentParser, arm: str, names: list[str], elements: Elements = NO_ELEMENTS
) -> dict[str, Arm]:
    """The arm each fixture runs under, with its install's fragments and Done commands, and the
    elements and edits `elements` names; a fixture whose install.json the runner refuses, or
    that cannot run the element arm (`element_refusal`, an edit whose text does not occur once
    in an installed skill or fragment file), exits 2, before anything is built."""

    arms = {}
    for name in names:
        try:
            chosen = fixture_install(name)
        except InstallError as problem:
            parser.error(f"{name}/{INSTALL_FILE}: {problem}")
        if not elements.named():
            installed = load_arm(arm, chosen.fragments, chosen.done, chosen.adopted)
            arms[name] = fixture_arm(name, installed)
            continue
        refused = element_refusal(chosen, elements)
        if refused:
            parser.error(f"{name}: {refused}")
        base = load_arm("current", chosen.fragments, chosen.done, True)
        try:
            arms[name] = element_arm(base, arm, elements)
        except EditsError as problem:
            parser.error(f"{name}: --edits: {problem}")
        missing = [
            edit.path for edit in elements.edits if edit.path not in (NOTE, *arms[name].files)
        ]
        if missing:
            parser.error(f"{name}: --edits: the arm installs no {', '.join(missing)}")
    return arms


def element_options(parser: argparse.ArgumentParser, args: argparse.Namespace) -> Elements:
    """The elements and edits the options name, checked: `--drop` with `--arm current`, `--add`
    with `--arm none`, each a known element and named once, and `--edits` a readable file, for
    the current arm or the none arm plus elements, under `--arm-label`. A refusal exits 2."""

    dropped, added = tuple(args.drop or ()), tuple(args.add or ())
    if args.arm in (FACTS_ONLY, BARE) and (dropped or added or args.edits):
        parser.error(
            f"--arm {args.arm} takes no --drop, --add or --edits: it is measured as it is; "
            f"build an element arm from --arm current or --arm {NONE}"
        )
    if dropped and args.arm != "current":
        parser.error("--drop takes an element from the current install: use --arm current")
    if added and args.arm != NONE:
        parser.error(f"--add puts an element into the {NONE} arm: use --arm {NONE}")
    for element in (*dropped, *added):
        if not ELEMENT.fullmatch(element):
            parser.error(
                f"no element {element!r}; there are {KERNEL_ELEMENT}, {FACTS_ELEMENT}, "
                f"{POINTERS_ELEMENT}, fragment:<id>, skill:<name> and {LAUNCHER_ELEMENT}"
            )
    for named in (dropped, added):
        if len(set(named)) != len(named):
            parser.error("name each element once")
    return Elements(dropped, added, *edits_option(parser, args, added))


def edits_option(
    parser: argparse.ArgumentParser, args: argparse.Namespace, added: tuple[str, ...]
) -> tuple[tuple[Edit, ...], str]:
    """The edits `--edits` names and the digest of their file, or none; it changes the current
    arm or the none arm plus elements, under `--arm-label`. A refusal exits 2."""

    if not args.edits:
        return (), ""
    if args.arm not in ("current", NONE) or (args.arm == NONE and not added):
        parser.error(f"--edits changes an install: use --arm current, or --arm {NONE} with --add")
    if not args.arm_label:
        parser.error("--edits needs --arm-label: name the variant the edits make")
    try:
        return read_edits(Path(args.edits))
    except EditsError as problem:
        parser.error(f"--edits {args.edits}: {problem}")


def run_arm(kind: str, elements: Elements) -> Arm:
    """The arm a run's STATUS.json records, with no fixture's fragments: the named arm, or the
    element arm built from the current install."""

    if not elements.named():
        return load_arm(kind)
    return element_arm(load_arm("current", adopted=True), kind, elements)


def tried_edits(parser: argparse.ArgumentParser, arms: dict[str, Arm]) -> None:
    """Exit 2, before the run starts, where an edit of AGENTS.md does not apply: each fixture
    whose arm edits it is built once in a temporary folder, with no model call, and removed."""

    for name, arm in arms.items():
        if all(edit.path != NOTE for edit in arm.edits):
            continue
        workdir = new_workspace(None)
        stage = new_stage((workdir,))
        extra: dict[str, Any] = {}
        try:
            failure = build_workspace(name, arm, workdir, extra, stage)[0]
        finally:
            shutil.rmtree(stage, ignore_errors=True)
            shutil.rmtree(workdir, ignore_errors=True)
        if failure is not None:
            parser.error(f"{name}: {extra.get('error', 'the fixture could not be built')}")


PROBE_PROMPT = "Reply with the word ok. Do not run commands.\n"
# The second probe of a Claude Code call: commands whose results show what the call's sandbox
# and cell give a model's commands. The runner observes the write and the commit itself; the
# PATH, the stub and the token are read from the commands' recorded output.
SANDBOX_STUB = "ob-probe-stub"
SANDBOX_HEAD = (
    "This is a check of the environment, not a task. Run each command below with your shell "
    "tool, one call for each command, exactly as written, in this order, even where one fails. "
    "Change nothing else. Then reply with the word done.\n\n"
)
# Each command of the sandbox probe; `{stub}` and `{outside}` are filled in.
SANDBOX_COMMANDS = (
    "command -v {stub}",
    "printf '%s\\n' \"$PATH\" | cut -d: -f1",
    "touch {outside}",
    'if [ -n "${{CLAUDE_CODE_OAUTH_TOKEN:-}}" ]; then echo token-visible;'
    " else echo token-hidden; fi",
    "git init -q probe-repo && printf 'x\\n' > probe-repo/f && git -C probe-repo add f"
    " && git -C probe-repo commit -q -m probe && git -C probe-repo rev-parse HEAD",
)


def _probe_output(transcript: str, command: str) -> tuple[bool, str | None]:
    """Whether the call ran `command` (its whole recorded command), and the output recorded
    for it (None where none was)."""

    try:
        document = json.loads(transcript)
    except ValueError:
        return False, None
    commands, outputs = document.get("commands") or [], document.get("outputs") or []
    for index, record in enumerate(commands):
        if record[0].strip() == command.strip():
            found = outputs[index] if index < len(outputs) else None
            return True, found if isinstance(found, str) else None
    return False, None


def sandbox_rows(
    transcript: str, commands: list[str], work: Path, outside: Path, stubs: Path
) -> list[list[str]]:
    """What the sandbox probe's call shows, each `PASS`, `FAIL` or `UNVERIFIED` (the model did
    not run the command): the stub found first on PATH, the PATH's first entry as the model's
    commands see it (a login shell can put its own entries first), a write outside the
    workspace denied (the runner looks for the file), the subscription token hidden from the
    model's commands, and a Git commit made under the cell's fresh home (the runner reads it)."""

    stub, first, touch, token, commit = commands
    rows = []
    ran, out = _probe_output(transcript, stub)
    wanted = str(stubs / SANDBOX_STUB)
    rows.append(
        _probe_row(
            "sandbox-stub-on-path",
            ran,
            (out or "").strip() == wanted,
            f"{(out or '').strip()} (wanted {wanted})",
        )
    )
    ran, out = _probe_output(transcript, first)
    rows.append(
        _probe_row(
            "sandbox-path-first",
            ran,
            (out or "").strip() == str(stubs),
            f"first PATH entry {(out or '').strip()} (wanted {stubs})",
        )
    )
    ran, _out = _probe_output(transcript, touch)
    rows.append(
        _probe_row(
            "sandbox-write-outside-denied",
            ran,
            not outside.exists(),
            f"{outside} {'exists' if outside.exists() else 'absent'} after the call",
        )
    )
    ran, out = _probe_output(transcript, token)
    if "CLAUDE_CODE_OAUTH_TOKEN" not in child_env():
        rows.append(
            ["sandbox-token-hidden", "UNVERIFIED", "CLAUDE_CODE_OAUTH_TOKEN is not set here"]
        )
    else:
        rows.append(
            _probe_row(
                "sandbox-token-hidden",
                ran and "token-" in (out or ""),
                "token-hidden" in (out or ""),
                (out or "").strip() or "no output",
            )
        )
    ran, _out = _probe_output(transcript, commit)
    status, head, _error = _run(["git", "-C", str(work / "probe-repo"), "rev-parse", "HEAD"])
    rows.append(
        _probe_row(
            "sandbox-git-commit", ran, status == 0, head.strip() or "no commit in probe-repo"
        )
    )
    return rows


def _probe_row(item: str, ran: bool, ok: bool, detail: str) -> list[str]:
    if not ran:
        return [item, "UNVERIFIED", f"the model did not run the command; {detail}"]
    return [item, "PASS" if ok else "FAIL", detail]


def sandbox_probe(
    args: argparse.Namespace, out: Path, root: Path | None, tool: ClaudeCodeHarness
) -> list[list[str]]:
    """The second probe of a Claude Code call: one more model call, in a workspace of its own,
    with a runner-owned stub folder first on its PATH, that runs the commands of
    `SANDBOX_PROMPT`; its rows (`sandbox_rows`) and the call's own checks."""

    workspace = workspace_path(root, out, "probe-sandbox", args.repetition) if root else None
    work = new_workspace(workspace)
    stubs = out / "probe.stubs"
    stubs.mkdir()
    (stubs / SANDBOX_STUB).write_text("#!/bin/sh\necho probe stub\n", encoding="utf-8")
    (stubs / SANDBOX_STUB).chmod(0o555)
    stubs.chmod(0o555)
    outside = out / "probe-outside-write.txt"
    commands = [
        command.format(stub=SANDBOX_STUB, outside=shlex.quote(str(outside)))
        for command in SANDBOX_COMMANDS
    ]
    prompt = SANDBOX_HEAD + "".join(f"{n}. {c}\n" for n, c in enumerate(commands, start=1))
    path = f"{stubs}{os.pathsep}{child_env().get('PATH', os.defpath)}"
    try:
        result = tool.call(
            prompt,
            Request(args.model, args.effort, protected=(stubs,), service_tier=args.service_tier),
            work,
            (),
            path,
            out / "probe-sandbox.native.jsonl",
        )
    finally:
        stubs.chmod(0o755)
    _write(
        out / "probe-sandbox.json",
        {"workspace": str(work), "checks": result.checks, **result.extras},
    )
    return [
        *sandbox_rows(result.transcript, commands, work, outside, stubs),
        *([f"sandbox-call-{item}", verdict, detail] for item, verdict, detail in result.checks),
    ]


def probe(args: argparse.Namespace, out: Path, root: Path | None, tool: Harness) -> int:
    """One minimal call through the same code path as a counted one; each item of the run
    contract printed as PASS, FAIL or UNVERIFIED. For Claude Code, a second call runs the
    commands of the sandbox probe (`sandbox_probe`). Exit 3 without a login, 1 on any FAIL.
    One model call (two for Claude Code), no retry."""

    login = tool.preflight()
    if not login["ok"]:
        sys.stderr.write(
            f"probe: UNVERIFIED - preflight did not observe a subscription login for {tool.name}.\n"
        )
        return PREFLIGHT_EXIT
    workspace = workspace_path(root, out, "probe", args.repetition) if root else None
    message = refuse_workspaces(root, [workspace]) if root and workspace else ""
    if message:
        raise SystemExit(f"probe: {message}")
    out.mkdir(parents=True, exist_ok=False)
    work = new_workspace(workspace)
    (work / ".agents" / "work").mkdir(parents=True, exist_ok=True)
    result = tool.call(
        PROBE_PROMPT,
        Request(args.model, args.effort, service_tier=args.service_tier),
        work,
        (),
        child_env().get("PATH", os.defpath),
        out / "probe.native.jsonl",
    )
    rows = [
        [
            "call-exit",
            "PASS" if result.returncode == 0 else "FAIL",
            f"exit status {result.returncode}",
        ],
        [
            "final-message",
            "PASS" if result.answer.strip() else "FAIL",
            "a final message" if result.answer.strip() else "no final message",
        ],
        *result.checks,
        # A Claude Code call's reach and loading rows, UNVERIFIED where no record names an item.
        *(result.extras.get("isolation") or []),
    ]
    unknown = result.extras.get("unknown_item_types", [])
    rows.append(
        [
            "item-types",
            "FAIL" if unknown else "PASS",
            f"seen {result.extras.get('item_types', [])}; unknown {unknown}",
        ]
    )
    if isinstance(tool, ClaudeCodeHarness):
        rows += sandbox_probe(args, out, root, tool)
    key = result.extras.get("thread_id")
    memory = tool.memory_mode(key) if key and isinstance(tool, CodexHarness) else None
    for item, verdict, detail in rows:
        print(f"{verdict} {item} - {detail}")
    print(f"observed: memory_mode {memory if memory is not None else 'not readable'}")
    print(f"observed: cli_warnings {result.extras.get('cli_warnings', [])}")
    failed = any(row[1] == "FAIL" for row in rows)
    _write(
        out / "probe.json",
        {
            "harness": tool.name,
            "model": args.model,
            "effort": args.effort,
            **({"service_tier": args.service_tier} if args.service_tier else {}),
            "workspace": str(work),
            "observed": result.observed,
            "checks": rows,
            "memory_mode": memory,
            **result.extras,
        },
    )
    return 1 if failed else 0


def _section(title: str, body: list[str]) -> list[str]:
    return [f"--- {title} ---", *(body or ["(none)"])]


def _instruction_files(workdir: Path) -> list[str]:
    """Each instruction file on the path from the workspace up, with its size and, for the ones
    inside the workspace, its text."""

    lines = []
    for found in instructions_above(workdir):
        place = Path(found)
        inside = workdir.resolve() in (place.parent, *place.parent.parents)
        lines.append(
            f"{found} ({place.stat().st_size} bytes, {'in' if inside else 'above'} the workspace)"
        )
        if inside or place.stat().st_size:
            lines += [
                "  | " + line for line in place.read_text("utf-8", errors="replace").splitlines()
            ]
    return lines


def _engine_import(workdir: Path, path: str) -> str:
    """Where the call's `python3`, in the workspace, imports the engine from, or an empty
    string where it cannot."""

    python = shutil.which("python3", path=path)
    if not python:
        return ""
    done = bounded_command(
        [python, "-c", "import outcomebound_tools as e; print(e.__file__)"],
        cwd=str(workdir),
        env={**child_env(), "PATH": path},
        timeout=60,
    )
    return done.stdout.strip() if done.returncode == 0 else ""


def _elements_text(arm: Arm) -> str:
    """An element arm's elements, as the dump and the isolation rule name them."""

    named = f"dropped {list(arm.dropped)}" if arm.name != NONE else f"added {list(arm.added)}"
    edits = f"; {len(arm.edits)} edit(s), file {arm.edits_sha256[:12]}" if arm.edits else ""
    return f"{arm.name} arm, {named}{edits}"


def _element_lines(arm: Arm) -> list[str]:
    """An element arm's elements, each kept or not, and its edits, for the dump."""

    lines = [
        f"{'kept' if arm.keeps(element) else 'not held'}: {element}"
        for element in install_elements(arm)
    ]
    lines.insert(0, _elements_text(arm))
    lines += [
        f"edit {edit.path}: old {sha256_text(edit.old)[:12]}, new {sha256_text(edit.new)[:12]}"
        for edit in arm.edits
    ]
    return lines


def outside_elements(text: str, arm: Arm) -> str:
    """An instruction file's text less what the none arm's added elements put there: each added
    block, and an added pointer line with the read-once line and markers it keeps. What is left
    is the text a call reaches outside the arm's elements."""

    if arm.name != NONE or not arm.added:
        return text
    from outcomebound_tools import adopt, facts

    for element, block in (
        (KERNEL_ELEMENT, adopt.KERNEL),
        (FACTS_ELEMENT, facts.FACTS),
        (POINTERS_ELEMENT, facts.POINTERS),
    ):
        if arm.keeps(element):
            text = adopt.cut(text, block)
    found = adopt.block_text(text, facts.POINTERS)
    if found is None:
        return text
    lines = found.decode("utf-8").split("\n")
    left = [
        line
        for line in lines[1:-1]
        if line != facts.ONCE and not arm.keeps(_pointer_element(line) or "")
    ]
    if not left:
        return adopt.cut(text, facts.POINTERS)
    return text.replace(found.decode("utf-8"), "\n".join([lines[0], *left, lines[-1]]), 1)


def _setup_file(workdir: Path, path: str) -> bool:
    """Whether the fixture's setup wrote `path` (relative to `workdir`) and no element owns it:
    the fixture's own file, which no install adds, takes away or counts as carried."""

    return path in _FIXTURE_FILES.get(workdir, frozenset()) and element_of(path) is None


def _setup_only(workdir: Path, item: Path) -> bool:
    """Whether every file under `item` is one the fixture's setup wrote (`_setup_file`)."""

    names = (
        [item.relative_to(workdir).as_posix()]
        if item.is_file()
        else [(item / path).relative_to(workdir).as_posix() for path in tree_hashes(item)]
    )
    return all(_setup_file(workdir, name) for name in names)


def _carried_outside(workdir: Path, arm: Arm) -> list[str]:
    """What the none arm plus elements carries outside them: a file under `.outcomebound/`, or
    an OutcomeBound skill's folder at a skill root, that no added element owns and the fixture's
    setup did not write."""

    from outcomebound_tools import fragments

    found = [
        f".outcomebound/{path}"
        for path in tree_hashes(workdir / ".outcomebound")
        if not arm.keeps(element_of(f".outcomebound/{path}") or "")
        and not _setup_file(workdir, f".outcomebound/{path}")
    ]
    found += [
        f"{root}{skill}"
        for root in SKILL_ROOTS
        for skill in fragments.SKILLS
        if (workdir / root / skill).exists() and not arm.keeps(f"skill:{skill}")
    ]
    return found


def _reach(workdir: Path, home: Path | None) -> list[tuple[str, bool, str]]:
    """What the call reaches from outside its workspace: for codex (`home` its Codex home), the
    home and the folders above the workspace; for Claude Code (`home` None, each call's home is
    new), the folders above the workspace and the machine's managed policy."""

    if home is None:
        return [(item, verdict == "PASS", detail) for item, verdict, detail in reach_rows(workdir)]
    return [
        (
            "codex-home-neutral",
            not guiding_reach(home, workdir.parent),
            f"{guiding_reach(home, workdir.parent) or 'nothing names OutcomeBound or instructs'}; "
            f"reached alike by every arm: {home_leaks(home) or 'nothing'}",
        ),
        (
            "nothing-above-workspace",
            not instructions_above(workdir.parent),
            f"{instructions_above(workdir.parent) or 'no instruction file'}",
        ),
    ]


def isolation(
    arm: Arm, workdir: Path, prompt: str, path: str, home: Path | None
) -> list[list[str]]:
    """Each isolation rule of the call, as `[rule, PASS|FAIL, detail]`: the only `outcomebound`
    on its PATH is the arm's own; its Codex home (`home`; None for a Claude Code call, whose
    home is new) and the folders above its workspace give it no instructions or skills; an arm
    that carries no OutcomeBound text reaches none; and an element arm holds exactly its
    elements, the none arm plus elements reaching no OutcomeBound text, skill or launcher outside
    them."""

    own = [os.path.realpath(arm.launcher)] if arm.launcher else []
    reached = launchers(path)
    rows: list[tuple[str, bool, str]] = [
        (
            "launcher-on-path",
            [item.rsplit(" -> ", 1)[1] for item in reached] == own,
            f"{reached or 'no outcomebound'}; the arm's own: {own or 'none'}",
        ),
        *_reach(workdir, home),
    ]
    if arm.shaped():
        problems = element_problems(workdir, arm)
        rows.append(("elements", not problems, "; ".join(problems) or _elements_text(arm)))
    if arm.name == FACTS_ONLY:
        problems = facts_only_problems(workdir)
        rows.append(("facts-only-install", not problems, "; ".join(problems) or "as adopt wrote"))
    if arm.name == BARE:
        left, kept = instruction_paths(workdir)
        rows.append(
            (
                "no-instruction-file",
                not left,
                f"in the workspace: {left or 'none'}; a nested repository keeps: {kept or 'none'}",
            )
        )
    if arm.name in (NONE, BARE) or verbatim_install(arm):
        files = instructions_above(workdir) if home is not None else claude_above(workdir)
        texts = [
            prompt,
            *(outside_elements(Path(f).read_text("utf-8", "replace"), arm) for f in files),
        ]
        named = [text for text in texts if "outcomebound" in text.lower()]
        carried = (
            _carried_outside(workdir, arm)
            if arm.shaped()
            else [
                str(item.relative_to(workdir))
                for item in (
                    workdir / ".outcomebound",
                    *(workdir / root / "using-outcomebound" for root in SKILL_ROOTS),
                )
                if item.exists() and not _setup_only(workdir, item)
            ]
        )
        rows.append(
            (
                "no-outcomebound-text",
                not named and not carried,
                f"{len(named)} text(s) name OutcomeBound; carried: {carried or 'nothing'}",
            )
        )
        engine = _engine_import(workdir, path)
        rows.append(("no-engine-import", not engine, engine or "python3 cannot import the engine"))
    return [[rule, "PASS" if ok else "FAIL", detail] for rule, ok, detail in rows]


def dump_arm(parser: argparse.ArgumentParser, args: argparse.Namespace) -> int:
    """Build one fixture under one arm and print, with no model call, what its codex call would
    receive: argv, prompt, instruction files, Codex home, launchers on PATH and the install's
    files, then each isolation rule as PASS or FAIL. The workspace is kept. Exit 0 where every
    rule passes, 1 where one fails, 2 where the fixture cannot be built."""

    name = args.dump_arm
    if not args.model or args.arm is None:
        parser.error("--dump-arm needs --arm and --model")
    if name not in fixture_names():
        parser.error(f"no fixture {name}; there are {', '.join(fixture_names())}")
    set_earlier_ref(parser, args)
    elements = element_options(parser, args)
    plugins = harness_options(parser, args)
    arm = fixture_arms(parser, args.arm, [name], elements)[name]
    label = args.arm_label or element_label(args.arm, elements)
    root = workspace_root(args.workspace_root)
    workspace = root / f"dump-{uuid.uuid4().hex[:12]}" / f"{name}-{label}" if root else None
    refused = refuse_workspaces(root, [workspace]) if root and workspace else ""
    if refused:
        raise SystemExit(f"run: {refused}")
    tool = make_harness(args.harness, plugins)
    workdir = new_workspace(workspace)
    extra: dict[str, Any] = {}
    stage = new_stage((workdir, *((root,) if root else ())))
    try:
        failure, _protected, _seed, prompt = build_workspace(name, arm, workdir, extra, stage)
    finally:
        shutil.rmtree(stage, ignore_errors=True)
    if failure is not None:
        sys.stderr.write(f"run: {name} could not be built: {extra.get('error')}\n{failure}\n")
        return 2
    install = fixture_install(name)
    path = call_path(arm, str(root) if root else None)
    request = Request(
        args.model,
        args.effort,
        needs_local_listener(name),
        install.sandbox,
        service_tier=args.service_tier,
    )
    if isinstance(tool, ClaudeCodeHarness):
        lines, rows = claude_dump(tool, arm, workdir, prompt, DumpCall(name, request, path))
        print("\n".join([f"fixture {name}, arm {label}; workspace {workdir} (kept)", *lines]))
        return 1 if any(row[1] == "FAIL" for row in rows) else 0
    argv = tool.argv(
        request, workdir, Path("<last-message file>"), fixture_write_roots(name, workdir)
    )
    home = tool.home()
    rows = isolation(arm, workdir, prompt, path, home)
    fragments = [item for item in arm.selected if not arm.shaped() or arm.keeps(f"fragment:{item}")]
    lines = [
        f"fixture {name}, arm {label}; workspace {workdir} (kept)",
        *_section("argv (the prompt is its stdin)", [" ".join(shlex.quote(a) for a in argv)]),
        *_section("prompt", prompt.splitlines()),
        *_section("instruction files from the workspace up", _instruction_files(workdir)),
        *_section(
            f"codex home {home} ({'$CODEX_HOME' if child_env().get('CODEX_HOME') else 'default'})",
            [
                *(f"reaches the call: {item}" for item in home_leaks(home)),
                f"codex's own skills: {_entries(home / 'skills' / SYSTEM_SKILLS) or 'none'}",
                "plugin cache (the call ignores the config.toml that enables plugins and turns "
                "plugins off; a run's catalog record shows the skills a call was "
                f"given): {_entries(home / 'plugins' / 'cache') or 'none'}",
            ],
        ),
        *_section("PATH entries holding outcomebound", launchers(path)),
        *_section(
            f"install: {install.sandbox} sandbox, Done {list(arm.done) or 'none'}, "
            f"fragments {fragments or 'none'}",
            [f"{sha}  {file}" for file, sha in arm.record()["arm_files"].items()],
        ),
        *(_section("elements", _element_lines(arm)) if arm.shaped() else []),
        *_section("isolation", [" ".join(row) for row in rows]),
    ]
    print("\n".join(lines))
    return 1 if any(row[1] == "FAIL" for row in rows) else 0


class DumpCall(NamedTuple):
    """The call a dump shows: its fixture, its request and its PATH."""

    name: str
    request: Request
    path: str


def claude_dump(
    tool: ClaudeCodeHarness, arm: Arm, workdir: Path, prompt: str, call: DumpCall
) -> tuple[list[str], list[list[str]]]:
    """What a Claude Code call of the built `workdir` would receive, with no model call: the
    argv, the cell's environment (a credential's value shown as `<set>`), the prompt, the
    instruction files from the workspace up, the launchers on PATH and the install's files; the
    isolation rules; and the loading check run twice on a synthetic start event, once as the arm
    should load and once with a plugin and a hook it does not add, which must fail. The lines
    to print and every rule, a loading check that passes the leak among them as a FAIL."""

    name, request, path = call
    write_roots = fixture_write_roots(name, workdir)
    cell = cell_for(workdir.parent / f"{workdir.name}.native.jsonl")
    env = shown_env(tool.cell_env(cell, path))
    expected = tool.expected(workdir)
    session = str(uuid.uuid4())
    start = expected_start(workdir, request.model, expected, session)
    records = expected_records(expected, session)
    clean = loading_check([start], expected, records)
    leak = loading_check(leaked_start(start), expected, leaked_records(records))
    leaked = {"plugins", "skills", "hooks", "instruction-files"}
    caught = {row[0] for row in leak if row[1] == "FAIL"} >= leaked
    denied = unreadable(request, workdir, workdir.parent / f"{workdir.name}.native.jsonl")
    rows = isolation(arm, workdir, prompt, path, None)
    rows.append(
        [
            "loading-check-clean",
            "FAIL" if failed_rows(clean) else "PASS",
            "; ".join(failed_rows(clean)) or "the expected load passes",
        ]
    )
    rows.append(
        [
            "loading-check-leak",
            "PASS" if caught else "FAIL",
            "; ".join(failed_rows(leak)) or "a stray plugin, skill, hook and rules file passed",
        ]
    )
    inside = workdir.resolve()
    files = [
        f"{item} ({'in' if Path(item).resolve().is_relative_to(inside) else 'above'} the workspace)"
        for item in claude_above(workdir)
    ]
    lines = [
        *_section(
            "argv (the prompt is its stdin)",
            [shlex.join(tool.argv(request, workdir, write_roots, denied))],
        ),
        *_section(
            f"environment of the cell {cell.root} (made new at the call)",
            [f"{k}={v}" for k, v in env.items()],
        ),
        *_section("prompt", prompt.splitlines()),
        *_section("instruction and rules files from the workspace up", files),
        *_section("PATH entries holding outcomebound", launchers(path)),
        *_section(
            f"install: {fixture_install_safe(name)}; skills Claude Code loads from the "
            f"workspace: {list(expected.skills) or 'none'}",
            [f"{sha}  {file}" for file, sha in arm.record()["arm_files"].items()],
        ),
        *(_section("elements", _element_lines(arm)) if arm.shaped() else []),
        *_section(
            "synthetic start event (stands in for the CLI's own)",
            [json.dumps(start, sort_keys=True)],
        ),
        *_section("loading check, the expected load", [" ".join(row) for row in clean]),
        *_section(
            "synthetic native records (stand in for the CLI's own)",
            [json.dumps(record, sort_keys=True) for record in records],
        ),
        *_section(
            "loading check, with a stray plugin, skill, hook and rules file",
            [" ".join(row) for row in leak],
        ),
        *_section("isolation", [" ".join(row) for row in rows]),
    ]
    return lines, rows


def fixture_install_safe(name: str) -> str:
    """A fixture's install as one line, or why it cannot be read."""

    try:
        install = fixture_install(name)
    except InstallError as problem:
        return f"unreadable ({problem})"
    done, chosen = list(install.done) or "none", list(install.fragments) or "none"
    return f"{install.sandbox} sandbox, Done {done}, fragments {chosen}"


def no_login(out: Path, status: dict[str, Any], login: dict[str, Any]) -> int:
    """Record a run whose preflight observed no subscription login, say why, and give the
    preflight exit."""

    _write(out / "STATUS.json", status)
    hint = login.get("hint") or "Log in to codex interactively"
    sys.stderr.write(
        f"run: UNVERIFIED - preflight did not observe a subscription login for "
        f"{status['harness']}. {hint}; this runner never falls back to an API key.\n"
    )
    return PREFLIGHT_EXIT


def harness_options(parser: argparse.ArgumentParser, args: argparse.Namespace) -> tuple[Path, ...]:
    """Install for `--harness` (`set_harness`), refuse a `--service-tier` that is malformed or
    that claude-code cannot meet, and give the plugin folders `--plugin-dir`
    names, each checked (`plugin_dir_refusal`) and resolved; a plugin for a harness other than
    Claude Code, or a folder outside the evals home's third-party clones, exits 2."""

    set_harness(args.harness)
    if args.service_tier and not SERVICE_TIER.fullmatch(args.service_tier):
        parser.error(f"--service-tier {args.service_tier!r} is one lower-case word")
    if args.service_tier and args.harness == CLAUDE:
        parser.error(f"--service-tier: {CLAUDE} has no serving tier to request")
    named = tuple(args.plugin_dir or ())
    if named and args.harness != CLAUDE:
        parser.error(f"--plugin-dir adds a plugin to a {CLAUDE} call: use --harness {CLAUDE}")
    for folder in named:
        refused = plugin_dir_refusal(folder)
        if refused:
            parser.error(refused)
    if len(set(named)) != len(named):
        parser.error("name each --plugin-dir once")
    return tuple(Path(folder).resolve() for folder in named)


def harness_reach(
    parser: argparse.ArgumentParser,
    tool: Harness,
    names: list[str],
    where: Path | None,
    bare: bool = False,
) -> dict[str, Any]:
    """Refuse, before anything is built, a run whose calls would read what their arm does not
    give them from outside their workspaces (`refuse_unclean`, `refuse_claude_reach`); else
    what the record keeps of it: the Codex home and what it gives each call, or the Claude Code
    rows and the plugin folders with their commits."""

    if isinstance(tool, CodexHarness):
        refuse_unclean(parser, names, tool.home(), where, bare)
        # What the Codex home gives each call besides its fixture and install.
        return {"codex_home": str(tool.home()), "codex_home_reach": home_leaks(tool.home())}
    return {
        "claude_reach": refuse_claude_reach(parser, where),
        "plugin_dirs": plugin_records(tool.plugin_dirs),
    }


def refuse_claude_reach(parser: argparse.ArgumentParser, where: Path | None) -> list[list[str]]:
    """Exit 2, before anything is built, where a Claude Code call of a workspace made in `where`
    (None: the system's temporary folder) would read an instruction or rules file above it, or
    a managed policy that loads code or instructions; otherwise the rows, for the record."""

    rows = reach_rows((where or Path(tempfile.gettempdir())) / "workspace")
    problems = failed_rows(rows)
    if problems:
        parser.error(
            "a Claude Code call reads what is above its workspace, and these would reach it: "
            + "; ".join(problems)
            + "; name a --workspace-root outside your home folder (which holds your user-level "
            "Claude folder), with no CLAUDE.md, AGENTS.md or .claude/rules above it"
        )
    return rows


LABEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")


def set_earlier_ref(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    """Apply `--earlier-ref` and `--earlier-verbatim`: each changes the earlier arm only, and
    only one may name it. Each ref must be in this checkout."""

    global EARLIER_REF, EARLIER_VERBATIM
    for option in ("earlier_ref", "earlier_verbatim"):
        if getattr(args, option) and args.arm != EARLIER:
            parser.error(f"--{option.replace('_', '-')} changes the earlier arm: use --arm earlier")
    if args.earlier_ref and args.earlier_verbatim:
        parser.error("name the earlier arm once: --earlier-ref or --earlier-verbatim")
    if args.arm_label and not LABEL.fullmatch(args.arm_label):
        parser.error("--arm-label is letters, digits, '.', '_' and '-', from a letter or digit")
    EARLIER_REF = args.earlier_ref
    EARLIER_VERBATIM = args.earlier_verbatim
    if EARLIER_REF:
        ref_commit(EARLIER_REF)
    if EARLIER_VERBATIM:
        verbatim_guidance()


def _no_call(parser: argparse.ArgumentParser, args: argparse.Namespace) -> int:
    """`--rescore`, `--regrade` or `--dump-arm`: each runs no model."""

    if args.rescore:
        return rescore([Path(item).resolve() for item in args.rescore])
    if args.regrade:
        return regrade(Path(args.regrade).resolve(), Path(args.out or RAW / uuid.uuid4().hex))
    return dump_arm(parser, args)


def refuse_unclean(
    parser: argparse.ArgumentParser,
    names: list[str],
    home: Path,
    where: Path | None,
    bare: bool = False,
) -> None:
    """Exit 2, before anything is built, where a call of a fixture that needs a clean reach, or
    of the bare arm, would read OutcomeBound text or an instruction file with text from its Codex
    home or above its workspace (`unclean_reach`); otherwise print what the home gives every
    call alike."""

    reached = unclean_reach(names, home, where, bare)
    if reached:
        whose = f"a {BARE} arm's" if bare else f"a {'/'.join(CLEAN_HOME)} fixture's"
        parser.error(
            f"{whose} calls read nothing that names OutcomeBound or "
            f"instructs from the Codex home or above the workspace, and these would: "
            f"{', '.join(reached)}; empty or move them, or name another --workspace-root"
        )
    if any(name.startswith(CLEAN_HOME) for name in names) and home_leaks(home):
        print(f"codex home {home} gives every call alike: {', '.join(home_leaks(home))}")


def _main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.summary:
        return summarize([Path(item) for item in args.summary])
    # Absolute before any use: the grader commands run in the fixture repository, where a
    # relative path would resolve to another place.
    args.out = str(Path(args.out).resolve()) if args.out else ""
    args.workspace_root = str(Path(args.workspace_root).resolve()) if args.workspace_root else ""
    if args.rescore or args.regrade or args.dump_arm:
        return _no_call(parser, args)
    names = checked_fixtures(parser, args)
    set_earlier_ref(parser, args)
    plugins = harness_options(parser, args)
    elements = element_options(parser, args)
    run_id = uuid.uuid4().hex
    out = Path(args.out) if args.out else RAW / run_id
    root = workspace_root(args.workspace_root)
    tool = make_harness(args.harness, plugins)
    if args.probe:
        return probe(args, out, root, tool)
    reach = harness_reach(parser, tool, names, root / out.name if root else None, args.arm == BARE)
    # Each fixture's install, read before anything runs: an install.json the runner refuses, a
    # fragment the engine does not ship, an element the install does not hold or an edit that
    # does not apply stops the run here.
    arms = fixture_arms(parser, args.arm, names, elements)
    tried_edits(parser, arms)
    arm = run_arm(args.arm, elements)
    if root:
        wanted = [workspace_path(root, out, name, args.repetition) for name in names]
        refused = refuse_workspaces(root, wanted)
        if refused:
            raise SystemExit(f"run: {refused}")
        root.mkdir(parents=True, exist_ok=True)
    try:
        out.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        raise SystemExit(f"run: {out} already exists; name a new --out") from None
    status: dict[str, Any] = {
        "run_id": run_id,
        "date": datetime.date.today().isoformat(),
        "harness": tool.name,
        "arm": args.arm_label or element_label(args.arm, elements),
        "arm_kind": args.arm,
        "earlier_ref": EARLIER_REF or None,
        "earlier_verbatim": EARLIER_VERBATIM or None,
        "earlier_commit": earlier_commit(),
        "model": args.model,
        "effort": args.effort,
        **({"service_tier": args.service_tier} if args.service_tier else {}),
        "repetition": args.repetition,
        "workspace_root": str(root) if root else None,
        **arm.record(),
        **source(),
        "cli_version": tool.version(),
        "api_keys_stripped": list(STRIP_POLICY),
        "api_keys_removed_from_environment": stripped_from_environment(),
        **reach,
    }
    login = tool.preflight()
    status.update({key: login[key] for key in ("auth", "auth_evidence", "preflight")})
    if not login["ok"]:
        return no_login(out, {**status, "status": "UNVERIFIED", "fixtures": names}, login)
    path = call_path(arm, str(root) if root else None)
    found = shutil.which("outcomebound", path=path)
    status["outcomebound_on_path"] = os.path.realpath(found) if found else None
    _write(out / "STATUS.json", {**status, "status": "running", "fixtures": names})
    completed: list[str] = []
    rows: list[dict[str, Any]] = []
    failures = 0
    for name in names:
        failed, row = run_one(out, status, name, arms[name], path, tool)
        completed.append(name)
        rows.append(row)
        _write(out / "INDEX.json", rows)
        if failed:
            failures = 1
            break  # Inspect unsupported/failed call evidence before spending on another.
    state = "ran with failures" if failures else "ran"
    _write(
        out / "STATUS.json",
        {
            **status,
            "status": state,
            "fixtures": names,
            "completed_fixtures": completed,
            "failures": failures,
            **bare_record(rows),
        },
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(_main())
