#!/usr/bin/env python3
"""Measure whether the OutcomeBound kernel, and the skills an install carries, change what a
model does.

A run builds each fixture's disposable repository, hands a harness (today `codex exec`) one
arm's kernel and the fixture's task, and judges what the model left with the fixture's
deterministic post-checks, run through `outcomebound_tools.validation`. The post-checks are the
verdict. The model, effort and working directory a call counts for are the ones the harness's
own session record states, never the ones requested (evals/harnesses/__init__.py).

Four arms: `earlier`, an earlier wording of the operating-contract kernel, kept in
`evals/arms/earlier-kernel.md`; `current`,
what `outcomebound adopt --harness codex` installs from this checkout: the kernel rendered as
adopt renders it, at codex's skill path the whole folder of each skill that install carries
(the thirteen every install carries), and this
checkout's launcher first on the call's PATH; `unsized`, the current arm without the kernel's
sizing paragraph, which asks whether that paragraph earns its place; and `none`, no kernel,
skill or launcher, each fixture's note without its pointer to the core skill. The model is
always named and passed to codex, so codex's configured default never runs.

No run bills an API key from the environment: every credential and endpoint override a
CLI reads there is removed from each child, and preflight must observe a ChatGPT login. A
credential kept in codex's own files is invisible here.

Standard library only, and outside outcomebound_tools: this calls a real model.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, NamedTuple

# Direct script execution also needs the repository package path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evals.codex_events import command_transcript, observed_model, tokens_used
from evals.evidence import grading_digest, workspace_digest
from evals.harnesses import Request
from evals.harnesses.codex import CodexHarness
from evals.native_commands import fill_directories
from evals.native_receipts import parse_records
from evals.processes import bounded_command, partial_output

# The stream decoders the graders' tests read through this module.
__all__ = ["command_transcript", "observed_model"]

REPO = Path(__file__).resolve().parent.parent
FIXTURES = REPO / "evals" / "fixtures"
# A fixture's own file naming the fragments its install selects, one id a line.
FRAGMENTS_FILE = "fragments"
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
)
RAW = REPO / "evals" / "results" / "raw"
TEMPLATE = "templates/managed-block.agents.md.tmpl"
LAUNCHER = "scripts/outcomebound"
# The harness whose install the current arm mirrors, and the one `--harness` takes by default.
HARNESS = "codex"
HARNESSES = (HARNESS,)
# An earlier wording of the kernel, kept as a file so the arm runs in any checkout.
EARLIER = "earlier"
EARLIER_KERNEL = REPO / "evals" / "arms" / "earlier-kernel.md"
# The kernel-off arm: the task alone, in a fixture that carries no OutcomeBound text.
NONE = "none"
# The current arm less the kernel's sizing paragraph, the one that opens with this phrase.
UNSIZED = "unsized"
SIZING = "Satisfy all four completely"
# Where a fixture's skill copies live: the path its note names, and codex's skill path.
SKILL_ROOTS = (".outcomebound/skills/", ".agents/skills/")
ARMS = (EARLIER, "current", UNSIZED, NONE)
# The arms that stand for an install: their fixtures carry what adopt writes into AGENTS.md.
INSTALLED = ("current", UNSIZED)
# A fixture note's own pointer to the core skill, which an install replaces with its pointers.
NOTE_POINTER = re.compile(
    r"\s*Read `\.outcomebound/skills/using-outcomebound/SKILL\.md` before planning work here\."
)
REPETITIONS = (1, 2, 3)

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
# Where a post-check finds what stays outside the workspace: this checkout's evals/, holding
# graders and acceptance tests the model never has in its workspace.
EVAL_DIR_ENV = "OUTCOMEBOUND_EVAL_DIR"
ANSWER_ENV = "OUTCOMEBOUND_EVAL_ANSWER"
CLAIM_LINE = re.compile(r"^(PASS|FAIL|UNVERIFIED) (\S+) \[", re.MULTILINE)
OBSERVED = "observed: "


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
            command, capture_output=True, text=True, cwd=cwd, env=child_env(), timeout=60
        )
    except (OSError, subprocess.SubprocessError) as problem:
        return None, "", f"{command[0]}: {type(problem).__name__}: {problem}"
    return done.returncode, done.stdout, done.stderr


def kernel(arm: str) -> str:
    """The arm's operating-contract block, sentinels included, as the model receives it; the
    kernel-off arm's is empty."""

    if arm == NONE:
        return ""
    if arm == EARLIER:
        return EARLIER_KERNEL.read_text(encoding="utf-8").strip("\n")
    from outcomebound_tools import adopt

    try:
        text = adopt.kernel_block(REPO).strip("\n")
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


class Arm(NamedTuple):
    """What one arm hands the model: its kernel, ahead of the task; the files an install
    writes, by fixture-relative path; the launcher put first on the call's PATH; and, for an
    arm that stands for an install, the fragments selected and each skill's pointer, which
    `as_installed` writes into the fixture's AGENTS.md.

    A named tuple, not a dataclass: the tests load this file by path, outside sys.modules.
    """

    name: str
    kernel: str
    files: dict[str, bytes]
    launcher: Path | None
    selected: tuple[str, ...] = ()
    skills: tuple[tuple[str, str], ...] = ()

    def record(self) -> dict[str, Any]:
        """The arm's contents as the run's metadata keeps them: digests and the launcher."""

        return {
            "kernel_sha256": sha256_text(self.kernel),
            "arm_files": {
                path: hashlib.sha256(data).hexdigest() for path, data in sorted(self.files.items())
            },
            "arm_launcher": str(self.launcher) if self.launcher else None,
        }


def load_arm(name: str, selected: tuple[str, ...] = ()) -> Arm:
    """The arm as it runs, for an install that selects the fragments `selected`. `current`
    mirrors a codex install of this checkout: the whole folder of each skill that install
    carries, which is every install's ten, at the skill path the harness table gives codex, and
    this checkout's launcher. The earlier arm is its kernel alone and the kernel-off arm has
    nothing, whatever is selected."""

    text = kernel(name)
    if name in (EARLIER, NONE):
        return Arm(name, text, {}, None)
    from outcomebound_tools import adopt, facts, fragments

    try:
        (route,) = adopt.routes(REPO, [HARNESS])
        chosen = fragments.select(fragments.load_all(REPO), selected) if selected else []
        carried = fragments.SKILLS
        files = {
            f"{route.skills}/{skill}/{relative}": data
            for skill in carried
            for relative, data in adopt.skill_files(REPO, skill).items()
        }
        files.update(
            {f"{facts.FRAGMENT_DIR}/{item.id}.md": adopt._fragment_bytes(item) for item in chosen}
        )
        pointers = tuple(
            (adopt.CONDITIONS[skill], f"{route.skills}/{skill}/SKILL.md") for skill in carried
        )
    except (adopt.AdoptError, fragments.FragmentError) as error:
        raise SystemExit(f"run: the current arm cannot read what adopt installs: {error}") from None
    return Arm(name, text, files, REPO / LAUNCHER, tuple(selected), pointers)


def fixture_arm(name: str, arm: Arm) -> Arm:
    """The adoption controller and the onboarding fixtures carry their subject skill; ordinary
    installs do not."""

    if not name.startswith(("adopt-", "onboard-")) or arm.name == NONE:
        return arm
    from outcomebound_tools import adopt

    root = ".agents/skills/adopt-outcomebound"
    files = {
        **arm.files,
        **{
            f"{root}/{path}": data
            for path, data in adopt.skill_files(REPO, "adopt-outcomebound").items()
        },
    }
    return arm._replace(files=files)


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
    AGENTS.md gains the project facts and the guidance pointers, each skill's with its
    condition, rendered by the engine as an install renders them.
    """

    if arm.name not in INSTALLED:
        return ""
    from outcomebound_tools import facts, fragments

    for note in ("AGENTS.md", "README.md"):
        path = workdir / note
        if path.is_file():
            path.write_text(NOTE_POINTER.sub("", path.read_text(encoding="utf-8")), "utf-8")
    chosen = fragments.select(fragments.load_all(REPO), arm.selected) if arm.selected else []
    rendered = facts.render(workdir, chosen, [], ["AGENTS.md"], list(arm.skills))
    agents = workdir / "AGENTS.md"
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
        done = subprocess.run(command, cwd=workdir, capture_output=True, text=True, env=env)
        if done.returncode != 0:
            return f"the install could not be folded into the seed: {done.stderr.strip()}"
    return ""


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


def call_path(arm: Arm, root: str | None) -> str:
    """The PATH codex and the model's commands get: the arm's launcher, alone in a directory
    of its own, ahead of this environment's PATH."""

    path = child_env().get("PATH", os.defpath)
    if arm.launcher is None:
        return path
    directory = Path(tempfile.mkdtemp(prefix="ob-launcher-", dir=root))
    (directory / "outcomebound").symlink_to(arm.launcher)
    return f"{directory}{os.pathsep}{path}"


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


def make_harness(name: str = HARNESS) -> CodexHarness:
    """The named harness, wired to this runner's environment, short-command runner and call
    timeout. Only `codex` exists; a new one is a module under evals/harnesses and a line here."""

    if name != "codex":
        raise ValueError(f"no harness {name}; there is {', '.join(HARNESSES)}")
    return CodexHarness(child_env, _run, CALL_TIMEOUT)


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
) -> dict[str, str]:
    """Digests of the grading inputs the model could rewrite, taken while the build is trusted.

    `protected.paths` stays beside the fixture's definition, outside the workspace, and the
    digests stay in this process: the model can edit the files, never this baseline. The
    files the arm installed are protected beside them. An arm `without_skills`, the kernel-off
    arm, protects no skill copy: each the list names must be absent, since that arm has none.
    """

    snapshot = {}
    lines = (fixture / "protected.paths").read_text(encoding="utf-8").splitlines()
    for raw in [*lines, *installed_files]:
        name = raw.strip()
        if not name or name.startswith("#"):
            continue
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"protected path is not fixture-relative: {name}")
        if without_skills and name.startswith(SKILL_ROOTS):
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


def seed_commit(workdir: Path) -> str | None:
    command = ["git", "rev-parse", "--verify", "refs/tags/seed^{commit}"]
    status, seed, _error = _run(command, cwd=workdir)
    return seed.strip() if status == 0 else None


def post_check(
    fixture: Path, workdir: Path, seed: str | None, transcript: str, answer: str
) -> tuple[str, str, Path]:
    """The fixture's plan, run by validation from a run-owned directory beside the workspace.

    The plan is copied there, so repetitions never share logs, and the transcript and the
    answer are written there before any check reads them.
    """

    grading = Path(tempfile.mkdtemp(prefix="ob-grading-", dir=str(workdir.parent)))
    plan = grading / "post.plan.json"
    plan.write_bytes((fixture / "post.plan.json").read_bytes())
    (grading / "transcript.txt").write_text(transcript, encoding="utf-8")
    (grading / "answer.md").write_text(answer, encoding="utf-8")
    env = {
        **child_env(),
        **HERMETIC_GIT,
        "PYTHONPATH": str(REPO),
        EVAL_DIR_ENV: str(REPO / "evals"),
        TRANSCRIPT_ENV: str(grading / "transcript.txt"),
        ANSWER_ENV: str(grading / "answer.md"),
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


class Place(NamedTuple):
    """Where a run keeps its evidence: the new directory its workspace is built in (None for a
    temporary one) and the file its harness copies the native session to (None for a file
    beside the workspace)."""

    workspace: Path | None = None
    keep: Path | None = None


def build_workspace(
    name: str, arm: Arm, workdir: Path, extra: dict[str, Any]
) -> tuple[str | None, dict[str, str], str | None, str]:
    """Install the arm's files and build the fixture in `workdir`.

    Returns None, the protected digests, the seed commit and the prompt (the arm's kernel, then
    the fixture's task); or, where the build fails, the report of why with the error in `extra`.
    """

    fixture = FIXTURES / name
    install(workdir, arm.files)
    try:
        built = bounded_command(
            ["bash", str(fixture / "setup.sh"), str(workdir)],
            env={**fixture_setup_env(), "OB_EVAL_ARM": arm.name},
            timeout=SETUP_TIMEOUT,
        )
    except (OSError, subprocess.SubprocessError) as problem:
        extra["error"] = f"fixture setup {type(problem).__name__}: {problem}"
        return partial_output(problem), {}, None, ""
    report = built.stdout + built.stderr
    if built.returncode != 0:
        extra["error"] = f"fixture setup exited {built.returncode}"
        return report, {}, None, ""
    unfit = as_installed(workdir, arm) or installed(workdir, arm.files)
    if unfit:
        extra["error"] = unfit
        return report, {}, None, ""
    try:
        protected = protected_snapshot(
            fixture, workdir, tuple(arm.files), without_skills=arm.name == NONE
        )
    except (OSError, ValueError) as problem:
        extra["error"] = f"protected fixture setup failed: {problem}"
        return report, {}, None, ""
    seed = seed_commit(workdir)
    (workdir / ".agents" / "work").mkdir(parents=True, exist_ok=True)
    try:
        prompt = build_prompt(arm.kernel, task_text(name, workdir))
    except (OSError, ValueError, subprocess.SubprocessError) as problem:
        extra["error"] = f"the fixture's task could not be written: {problem}"
        return report + partial_output(problem), {}, None, ""
    return None, protected, seed, prompt


def run_fixture(
    name: str,
    request: Request,
    arm: Arm,
    path: str,
    harness: CodexHarness | None = None,
    place: Place | None = None,
) -> tuple[str, str, int | None, dict[str, Any]]:
    """Build the fixture, let the model act in it through the harness, then judge what it left.

    Returns the answer, the report (the harness's output, then the post-checks'), its exit
    status (None where no call finished) and what the run's record keeps, the prompt among
    it. A post-check FAIL is the measurement; only a fixture that cannot be built, or a call
    that fails, is an error.
    """

    harness = harness or make_harness()
    place = place or Place()
    workdir = new_workspace(place.workspace)
    keep = place.keep or workdir.parent / f"{workdir.name}.native.jsonl"
    extra: dict[str, Any] = {
        "verdict": "UNVERIFIED",
        "claims": {},
        "fixture_repo": str(workdir),
        "harness": harness.name,
    }
    failure, protected, seed, prompt = build_workspace(name, arm, workdir, extra)
    if failure is not None:
        return "", failure, None, extra
    extra["prompt"] = prompt

    started = time.monotonic()
    answer, transcript, returncode = "", "", None
    try:
        result = harness.call(
            prompt, request, workdir, fixture_write_roots(name, workdir), path, keep
        )
        answer, transcript, returncode = result.answer, result.transcript, result.returncode
        extra.update(result.extras)
        extra["identity_error"] = result.error
        extra["observed"] = result.observed
        extra["model_observed"] = (result.observed or {}).get("model")
        if returncode is None:
            extra["error"] = f"{harness.name} call timed out after {CALL_TIMEOUT} seconds"
    except (OSError, ValueError, subprocess.SubprocessError) as problem:
        # The post-checks still run: a call that timed out may have changed the repository.
        extra["error"] = f"{type(problem).__name__}: {problem}"
        transcript = partial_output(problem)
    elapsed = round(time.monotonic() - started, 1)

    intact, protected_report = check_protected(workdir, protected)
    report = grade(name, workdir, Left(seed, transcript, answer), (intact, protected_report), extra)
    extra.update(
        protected_snapshot=protected,
        elapsed_seconds=elapsed,
        grading_files_sha256=grading_digest(REPO / "evals", name),
        # Taken last, after the post-checks: it is what a later `--regrade` finds.
        workspace_sha256=workspace_digest(workdir, {**child_env(), **HERMETIC_GIT}),
    )
    return answer, report, returncode, extra


class Left(NamedTuple):
    """What a run left to judge, besides its workspace: the seed commit read before the model
    ran, the transcript document and the final answer."""

    seed: str | None
    transcript: str
    answer: str


def grade(
    name: str,
    workdir: Path,
    left: Left,
    protected: tuple[bool, str],
    extra: dict[str, Any],
) -> str:
    """Judge what a run left: the post-checks, unless a grading input changed (`protected` is
    whether none did, and the protected check's report). Sets the verdict, the claims and what
    the checks observed in `extra`, and returns the report: the transcript, then the protected
    check and the post-checks' own output."""

    seed, transcript, answer = left
    intact, protected_report = protected
    verdict, output, log_dir = "FAIL", "VERDICT: FAIL\n", None
    if intact:
        try:
            verdict, output, log_dir = post_check(
                FIXTURES / name, workdir, seed, transcript, answer
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
    counts, whatever it requested."""

    name = extra.get("harness", HARNESS)
    if extra.get("error"):
        return str(extra["error"])
    if returncode != 0:
        return f"{name} exited {returncode}"
    if not answer.strip():
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
    }


def run_one(
    out: Path,
    status: dict[str, Any],
    name: str,
    arm: Arm,
    path: str,
    harness: CodexHarness,
) -> tuple[bool, dict[str, Any]]:
    """One fixture under the run's arm, recorded in `out`; whether its call failed, and its
    INDEX row. The workspace is kept under the status's root, if it names one, and the
    harness's session record is copied to `<fixture>.native.jsonl`."""

    root = status.get("workspace_root")
    workspace = workspace_path(Path(root), out, name, status["repetition"]) if root else None

    answer, report, returncode, extra = run_fixture(
        name,
        Request(status["model"], status["effort"]),
        arm,
        path,
        harness,
        Place(workspace, out / f"{name}.native.jsonl"),
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
    print(f"{name}: {extra['verdict']}" + (f" ({claims})" if claims else ""))
    if error:
        sys.stderr.write(f"run: {name}: {error}\n")
    return bool(error), index_row(status, name, meta)


REGRADED = "regraded_from"
UNVERIFIED = "UNVERIFIED"
POST_CHECKS = "\n--- post-checks ---\n"


def _regrade_plan(source: Path, path: Path, meta: dict[str, Any]) -> tuple[dict[str, Any], str]:
    """What one kept run needs to be judged again, and why it cannot be: the saved files, the
    workspace and the two digests, each compared where the source run recorded one.

    The returned dict holds the paths and the two statements for the new meta; the string is
    the reason to refuse, or empty."""

    name = meta.get("fixture", "")
    fixture = FIXTURES / str(name)
    plan: dict[str, Any] = {"meta": meta, "name": name}
    if not name or not (fixture / "post.plan.json").is_file():
        return plan, f"this checkout has no fixture {name!r}"
    for key, suffix in (
        ("answer", "answer.md"),
        ("prompt", "prompt.md"),
        ("saved", "transcript.txt"),
    ):
        plan[key] = path.with_name(f"{name}.{suffix}")
        if not plan[key].is_file():
            return plan, f"{plan[key].name} is missing"
    plan["native"] = path.with_name(f"{name}.native.jsonl")
    if plan["native"].is_file():
        recorded = meta.get("native_sha256")
        if recorded and hashlib.sha256(plan["native"].read_bytes()).hexdigest() != recorded:
            return plan, f"{plan['native'].name} differs from the digest the meta recorded"
    else:
        plan["native"] = None
    workdir = Path(str(meta.get("fixture_repo", "")))
    if not workdir.is_dir():
        return plan, f"the kept workspace {workdir} is missing"
    plan["workdir"] = workdir
    now = grading_digest(REPO / "evals", str(name))
    recorded = meta.get("grading_files_sha256")
    if recorded and recorded != now:
        return plan, "this checkout's fixture files under evals/ differ from the ones the run used"
    plan["grading_files"] = "PASS" if recorded else UNVERIFIED
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
    saved = plan["saved"].read_text(encoding="utf-8", errors="replace")
    transcript = saved.split(POST_CHECKS, 1)[0]
    answer = plan["answer"].read_text(encoding="utf-8")
    session = None
    if plan["native"] and meta.get("harness", HARNESS) == HARNESS:
        session = parse_records(plan["native"].read_bytes())
    transcript, filled = fill_directories(transcript, session)
    intact, protected_report, protected_check = _regrade_protected(workdir, meta)
    extra: dict[str, Any] = {}
    left = Left(meta.get("seed_sha"), transcript, answer)
    report = grade(name, workdir, left, (intact, protected_report), extra)
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
    _write(out / f"{name}.meta.json", record)
    claims = ", ".join(f"{claim} {verdict}" for claim, verdict in extra["claims"].items())
    print(f"{name}: {extra['verdict']}" + (f" ({claims})" if claims else ""))
    return index_row({"harness": HARNESS, **record}, name, record)


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
    """The record, with its tokens read from the saved transcript where it kept none."""

    if "tokens_used" not in meta:
        saved = path.with_name(path.name.replace(".meta.json", ".transcript.txt"))
        text = saved.read_text(encoding="utf-8", errors="replace") if saved.is_file() else ""
        meta = {**meta, "tokens_used": tokens_used(text)}
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


def summarize(directories: list[Path]) -> int:
    """Print, per fixture and arm, how many runs PASS the verdict and each claim, and the
    median tokens and seconds of the runs counted.

    A run whose call failed measured the call, not the model, so it is named and not counted.
    A run whose record keeps no token count has it read from the transcript saved beside it.
    """

    metas = [
        _with_tokens(path, json.loads(path.read_text(encoding="utf-8")))
        for directory in directories
        for path in sorted(directory.rglob("*.meta.json"))
    ]
    if not metas:
        print("no run records under " + ", ".join(str(item) for item in directories))
        return 1
    # The harness is part of the key: runs of different harnesses are never merged. A record
    # from before runs named a harness came from codex.
    groups: dict[tuple[str, str, str, str, str], list[dict[str, Any]]] = {}
    for meta in metas:
        key = (meta["fixture"], meta.get("harness", HARNESS), meta["arm"], meta["model"])
        groups.setdefault((*key, meta["effort"]), []).append(meta)
    for (fixture, harness_name, arm, model, effort), group in sorted(groups.items()):
        runs = sorted((run for run in group if not run["error"]), key=lambda run: run["repetition"])
        passed = sum(1 for run in runs if run["verdict"] == "PASS")
        failed = len(group) - len(runs)
        tail = f" ({failed} failed call(s) not counted)" if failed else ""
        label = f"{fixture} | {harness_name} | {arm} | {model} {effort}"
        print(f"{label}: PASS {passed}/{len(runs)}{tail}")
        spent = _medians(runs)
        if spent:
            print(f"  median {spent}")
        for claim in dict.fromkeys(claim for run in runs for claim in run["claims"]):
            count = sum(1 for run in runs if run["claims"].get(claim) == "PASS")
            print(f"  {claim}: PASS {count}/{len(runs)}")
        for run in runs:
            if not run["protected_intact"]:
                print(f"  repetition {run['repetition']}: a grading input was changed")
            for line in run["observations"]:
                print(f"  repetition {run['repetition']} {line}")
    for line in _provenance(metas):
        print(line)
    return 0


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
            f"skill that install carries at {HARNESS}'s skill path (the thirteen every install "
            f"carries), and {LAUNCHER} "
            f"first on the call's PATH; {UNSIZED} is current without the kernel's sizing "
            f"paragraph; {NONE} is the task alone, with no kernel, skill or launcher. "
            "The model is always named and passed to codex with -m, so codex's configured "
            "default never runs. Each arm's measurement is "
            f"{len(default_fixtures())} fixtures x 3 repetitions: "
            f"{len(default_fixtures()) * len(REPETITIONS)} runs; "
            "the handoff, lifecycle and adoption "
            "fixtures run only when --fixtures names them."
        ),
    )
    parser.add_argument(
        "--arm",
        choices=ARMS,
        help=f"{EARLIER}: an earlier wording of the kernel; current: what adopt "
        f"installs for {HARNESS}, and the launcher on PATH; {UNSIZED}: current without the "
        f"kernel's sizing paragraph; {NONE}: no kernel, skill or launcher",
    )
    parser.add_argument(
        "--harness",
        choices=HARNESSES,
        default=HARNESS,
        help="the tool that runs the model (default: %(default)s)",
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
        "--fixtures",
        default=",".join(default_fixtures()),
        help="comma-separated fixtures to run (default: %(default)s)",
    )
    parser.add_argument(
        "--repetition",
        type=int,
        choices=REPETITIONS,
        default=1,
        help="which of the three repetitions this run is (default: 1)",
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
        "post-checks on its kept workspace, into the new --out; refuses where the fixture's "
        "files under evals/ or the workspace differ from what the run recorded",
    )
    parser.add_argument(
        "--summary",
        nargs="+",
        metavar="DIR",
        help="print the verdicts the runs under each DIR recorded, and run nothing",
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
    return names


PROBE_PROMPT = "Reply with the word ok. Do not run commands.\n"


def probe(args: argparse.Namespace, out: Path, root: Path | None) -> int:
    """One minimal call through the same code path as a counted one; each item of the run
    contract printed as PASS or FAIL. Exit 3 without a login, 1 on any FAIL. One model call,
    no retry."""

    tool = make_harness(args.harness)
    login = tool.preflight()
    if not login["ok"]:
        sys.stderr.write("probe: UNVERIFIED - preflight did not observe a ChatGPT login.\n")
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
        Request(args.model, args.effort),
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
    ]
    unknown = result.extras.get("unknown_item_types", [])
    rows.append(
        [
            "item-types",
            "FAIL" if unknown else "PASS",
            f"seen {result.extras.get('item_types', [])}; unknown {unknown}",
        ]
    )
    key = result.extras.get("thread_id")
    memory = tool.memory_mode(key) if key else None
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
            "workspace": str(work),
            "observed": result.observed,
            "checks": rows,
            "memory_mode": memory,
            **result.extras,
        },
    )
    return 1 if failed else 0


def _main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.summary:
        return summarize([Path(item) for item in args.summary])
    if args.regrade:
        return regrade(Path(args.regrade), Path(args.out) if args.out else RAW / uuid.uuid4().hex)
    names = checked_fixtures(parser, args)
    run_id = uuid.uuid4().hex
    out = Path(args.out) if args.out else RAW / run_id
    root = workspace_root(args.workspace_root)
    tool = make_harness(args.harness)
    if args.probe:
        return probe(args, out, root)
    arm = load_arm(args.arm)
    # Each fixture's install, read before anything runs: a fragment it names that the engine
    # does not ship stops the run here.
    arms = {name: fixture_arm(name, load_arm(args.arm, selected_fragments(name))) for name in names}
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
        "arm": args.arm,
        "model": args.model,
        "effort": args.effort,
        "repetition": args.repetition,
        "workspace_root": str(root) if root else None,
        **arm.record(),
        **source(),
        "cli_version": tool.version(),
        "api_keys_stripped": list(STRIP_POLICY),
        "api_keys_removed_from_environment": stripped_from_environment(),
    }
    login = tool.preflight()
    status.update({key: login[key] for key in ("auth", "auth_evidence", "preflight")})
    if not login["ok"]:
        _write(out / "STATUS.json", {**status, "status": "UNVERIFIED", "fixtures": names})
        sys.stderr.write(
            "run: UNVERIFIED - preflight did not observe a ChatGPT login. Log in to codex "
            "interactively; this runner never falls back to an API key.\n"
        )
        return PREFLIGHT_EXIT
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
        },
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(_main())
