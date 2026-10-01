#!/usr/bin/env python3
"""Measure whether the OutcomeBound kernel, and the skills an install carries, change what a
model does.

A run builds each fixture's disposable repository, hands `codex exec` one arm's kernel and
the fixture's task, and judges what the model left with the fixture's deterministic
post-checks, run through `outcomebound_tools.validation`. The post-checks are the verdict.

Four arms: `earlier`, an earlier wording of the operating-contract kernel, kept in
`evals/arms/earlier-kernel.md`; `current`,
what `outcomebound adopt --harness codex` installs from this checkout: the kernel rendered as
adopt renders it, at codex's skill path the whole folder of each skill that install carries
(every install's, and those of the fragments a fixture's `fragments` file selects), and this
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

REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:  # the current arm is rendered by the engine's own adopt
    sys.path.insert(0, str(REPO))
FIXTURES = REPO / "evals" / "fixtures"
# A fixture's own file naming the fragments its install selects, one id a line.
FRAGMENTS_FILE = "fragments"
RAW = REPO / "evals" / "results" / "raw"
TEMPLATE = "templates/managed-block.agents.md.tmpl"
LAUNCHER = "scripts/outcomebound"
# The harness whose install the current arm mirrors: codex runs every call.
HARNESS = "codex"
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
FIXTURE_ROOT_ENV = "OUTCOMEBOUND_FIXTURE_ROOT"
# A fixture is judged by Git comparisons, so an operator's global or system Git config
# (hooksPath, excludesFile, an alias) must not reach the child that builds or checks it.
HERMETIC_GIT = {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
# The `seed` tag lives in a workspace the model can write to, so the runner reads the seed
# once, before the model runs, and hands that commit to the checks.
SEED_SHA_ENV = "OUTCOMEBOUND_SEED_SHA"
TRANSCRIPT_ENV = "OUTCOMEBOUND_EVAL_TRANSCRIPT"
ANSWER_ENV = "OUTCOMEBOUND_EVAL_ANSWER"
# These keep most of the operator's own codex setup out of every arm: without them a call loads
# `$CODEX_HOME/config.toml` (its personality, rules and writable roots), reads and writes the
# operator's memories, and keeps the session. Auth still comes from `CODEX_HOME`. They do not keep
# out agent role files under `$CODEX_HOME/agents/`, which codex read in every recorded run
# (codex-cli 0.158.0 and 0.159.0); docs/research/practices/evaluations.md states it as a limit.
CODEX_ISOLATION = (
    "--ephemeral",
    "--ignore-user-config",
    "--ignore-rules",
    "-c",
    "features.memories=false",
)
CLAIM_LINE = re.compile(r"^(PASS|FAIL|UNVERIFIED) (\S+) \[", re.MULTILINE)
MODEL_LINE = re.compile(r"^model: (\S+)$", re.MULTILINE)
# codex ends its output with this line and the call's token count on the line after it.
TOKENS_LINE = re.compile(r"^tokens used\s*\n\s*([\d,]+)\s*$", re.MULTILINE)
OBSERVED = "observed: "


def fixture_names() -> list[str]:
    return sorted(path.name for path in FIXTURES.iterdir() if (path / "setup.sh").is_file())


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
    carries, the ones every install carries and those the selected fragments name, at the
    skill path the harness table gives codex, and this checkout's launcher. The earlier arm
    is its kernel alone and the kernel-off arm has nothing, whatever is selected."""

    text = kernel(name)
    if name in (EARLIER, NONE):
        return Arm(name, text, {}, None)
    from outcomebound_tools import adopt, facts, fragments

    try:
        (route,) = adopt.routes(REPO, [HARNESS])
        chosen = fragments.select(fragments.load_all(REPO), selected) if selected else []
        carried = fragments.carried(chosen)
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
    for command in (
        ["git", "add", "-A"],
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


def build_prompt(kernel_text: str, task: str) -> str:
    """The kernel, then the fixture's task verbatim: nothing else reaches the model from here."""

    head = f"{kernel_text}\n\n" if kernel_text else ""
    return f"{head}Task:\n{task.strip()}\n"


def preflight() -> dict[str, Any]:
    """Observe a ChatGPT login before any call; a login codex does not name is not observed."""

    _status, out, error = _run(["codex", "login", "status"])
    output = (out + error).strip()
    line = next(
        (row.strip() for row in output.splitlines() if "Logged in using ChatGPT" in row), ""
    )
    return {
        "ok": bool(line),
        "auth": "subscription" if line else "not-observed",
        "auth_evidence": line,
        "preflight": output[:2000],
    }


def cli_version() -> str:
    status, text, _error = _run(["codex", "--version"])
    return text.strip().splitlines()[0] if status == 0 and text.strip() else "unknown"


def source() -> dict[str, Any]:
    """The checkout the kernel, the fixtures and the core skill were read from."""

    status, commit, _error = _run(["git", "-C", str(REPO), "rev-parse", "HEAD"])
    listed, changes, _error = _run(["git", "-C", str(REPO), "status", "--porcelain"])
    return {
        "commit": commit.strip() if status == 0 else "unknown",
        "dirty": bool(changes.strip()) if listed == 0 else None,
    }


def codex_command(model: str, effort: str, cwd: Path, last_message: Path) -> list[str]:
    """The `codex exec` argv for one call: the model named, the operator's setup left out.

    The call may write the workspace and, where it is a Git repository, its `.git`, which
    `workspace-write` otherwise keeps read-only: a fixture would measure the sandbox, not
    the model, if a commit were impossible.
    """

    if not model:
        raise ValueError("name the model: codex's configured default never runs")
    command = [
        "codex",
        "exec",
        *CODEX_ISOLATION,
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
    if (Path(cwd) / ".git").is_dir():
        command += ["--add-dir", str(Path(cwd) / ".git")]
    return command


def call_codex(prompt: str, model: str, effort: str, cwd: Path, path: str) -> tuple[str, str, int]:
    """The model's final message, everything codex printed, and codex's exit status; `path`
    is the call's PATH."""

    with tempfile.NamedTemporaryFile("r+", suffix=".md", delete=False) as handle:
        last_message = Path(handle.name)
    try:
        done = subprocess.run(
            codex_command(model, effort, cwd, last_message),
            input=prompt,
            capture_output=True,
            text=True,
            env={**child_env(), "PATH": path},
            cwd=str(cwd),
            timeout=CALL_TIMEOUT,
        )
        answer = last_message.read_text(encoding="utf-8") if last_message.is_file() else ""
    finally:
        last_message.unlink(missing_ok=True)
    return answer, done.stdout + done.stderr, done.returncode


def tokens_used(transcript: str) -> int | None:
    """The token count codex printed last, or None where it printed none."""

    found = TOKENS_LINE.findall(transcript)
    return int(found[-1].replace(",", "")) if found else None


def observed_model(transcript: str) -> str | None:
    """The model codex's own header names, after its `workdir:` line, or None."""

    _before, found, after = transcript.partition("\nworkdir: ")
    named = MODEL_LINE.search(after) if found else None
    return named.group(1) if named else None


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
        TRANSCRIPT_ENV: str(grading / "transcript.txt"),
        ANSWER_ENV: str(grading / "answer.md"),
    }
    if seed:
        env[SEED_SHA_ENV] = seed
    done = subprocess.run(
        [sys.executable, "-m", "outcomebound_tools.validation", str(plan), "--cwd", str(workdir)],
        capture_output=True,
        text=True,
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


def run_fixture(
    name: str, prompt: str, model: str, effort: str, arm: Arm, path: str
) -> tuple[str, str, int | None, dict[str, Any]]:
    """Install the arm's files, build the fixture, let the model act in it, then judge what
    it left.

    Returns the answer, the report (codex's output, then the post-checks'), codex's exit
    status (None where no call finished) and what the run's record keeps. A post-check FAIL
    is the measurement; only a fixture that cannot be built, or a call that fails, is an error.
    """

    fixture = FIXTURES / name
    workdir = Path(
        tempfile.mkdtemp(prefix="ob-fixture-", dir=os.environ.get(FIXTURE_ROOT_ENV) or None)
    )
    extra: dict[str, Any] = {"verdict": "UNVERIFIED", "claims": {}, "fixture_repo": str(workdir)}
    install(workdir, arm.files)
    built = subprocess.run(
        ["bash", str(fixture / "setup.sh"), str(workdir)],
        capture_output=True,
        text=True,
        env={**child_env(), **HERMETIC_GIT, "OB_EVAL_ARM": arm.name},
        timeout=SETUP_TIMEOUT,
    )
    if built.returncode != 0:
        extra["error"] = f"fixture setup exited {built.returncode}"
        return "", built.stdout + built.stderr, None, extra
    unfit = as_installed(workdir, arm) or installed(workdir, arm.files)
    if unfit:
        extra["error"] = unfit
        return "", built.stdout + built.stderr, None, extra
    try:
        protected = protected_snapshot(
            fixture, workdir, tuple(arm.files), without_skills=arm.name == NONE
        )
    except (OSError, ValueError) as problem:
        extra["error"] = f"protected fixture setup failed: {problem}"
        return "", built.stdout + built.stderr, None, extra
    seed = seed_commit(workdir)

    started = time.monotonic()
    answer, transcript, returncode = "", "", None
    try:
        answer, transcript, returncode = call_codex(prompt, model, effort, workdir, path)
    except (OSError, subprocess.SubprocessError) as problem:
        # The post-checks still run: a call that timed out may have changed the repository.
        extra["error"] = f"{type(problem).__name__}: {problem}"
    elapsed = round(time.monotonic() - started, 1)

    intact, protected_report = check_protected(workdir, protected)
    verdict, output, log_dir = "FAIL", "VERDICT: FAIL\n", None
    if intact:
        verdict, output, log_dir = post_check(fixture, workdir, seed, transcript, answer)
    extra.update(
        verdict=verdict,
        claims={claim: result for result, claim in CLAIM_LINE.findall(output)},
        protected_intact=intact,
        observations=observations(log_dir),
        model_observed=observed_model(transcript),
        seed_sha=seed,
        elapsed_seconds=elapsed,
        tokens_used=tokens_used(transcript),
        post_check_log_dir=str(log_dir) if log_dir else None,
    )
    report = f"{transcript}\n\n--- post-checks ---\n{protected_report}\n{output}"
    return answer, report, returncode, extra


def call_error(returncode: int | None, answer: str, extra: dict[str, Any], model: str) -> str:
    """Why this run's call does not count, or an empty string where it does."""

    if extra.get("error"):
        return str(extra["error"])
    if returncode != 0:
        return f"codex exited {returncode}"
    if not answer.strip():
        return "codex produced no final message"
    seen = extra.get("model_observed")
    if seen and seen != model:
        return f"codex reported running {seen}, not {model}"
    return ""


def _write(path: Path, document: dict[str, Any]) -> None:
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def run_one(out: Path, status: dict[str, Any], name: str, arm: Arm, path: str) -> bool:
    """One fixture under the run's arm, recorded in `out`; True where its call failed."""

    task = (FIXTURES / name / "prompt.md").read_text(encoding="utf-8")
    prompt = build_prompt(arm.kernel, task)
    (out / f"{name}.prompt.md").write_text(prompt, encoding="utf-8")
    answer, report, returncode, extra = run_fixture(
        name, prompt, status["model"], status["effort"], arm, path
    )
    error = call_error(returncode, answer, extra, status["model"])
    extra.pop("error", None)
    (out / f"{name}.answer.md").write_text(answer, encoding="utf-8")
    (out / f"{name}.transcript.txt").write_text(report, encoding="utf-8")
    record = {**status, **arm.record(), "fixture": name}
    _write(
        out / f"{name}.meta.json",
        {**record, "returncode": returncode, "error": error, **extra},
    )
    claims = ", ".join(f"{claim} {verdict}" for claim, verdict in extra["claims"].items())
    print(f"{name}: {extra['verdict']}" + (f" ({claims})" if claims else ""))
    if error:
        sys.stderr.write(f"run: {name}: {error}\n")
    return bool(error)


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
    groups: dict[tuple[str, str, str, str], list[dict[str, Any]]] = {}
    for meta in metas:
        key = (meta["fixture"], meta["arm"], meta["model"], meta["effort"])
        groups.setdefault(key, []).append(meta)
    for (fixture, arm, model, effort), group in sorted(groups.items()):
        runs = sorted((run for run in group if not run["error"]), key=lambda run: run["repetition"])
        passed = sum(1 for run in runs if run["verdict"] == "PASS")
        failed = len(group) - len(runs)
        tail = f" ({failed} failed call(s) not counted)" if failed else ""
        print(f"{fixture} | {arm} | {model} {effort}: PASS {passed}/{len(runs)}{tail}")
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
            "Hand codex each fixture's task behind one arm's kernel, in a disposable "
            "repository, and judge what the model left with the fixture's deterministic "
            "post-checks. See evals/README.md."
        ),
        epilog=(
            f"arms: {EARLIER} is an earlier wording of the kernel ({EARLIER_KERNEL.name}); "
            f"current is what `outcomebound adopt --harness {HARNESS}` installs from this "
            f"checkout: {TEMPLATE} rendered as adopt renders it, the whole folder of each "
            f"skill that install carries at {HARNESS}'s skill path (every install's, and those "
            f"of the fragments a fixture's `{FRAGMENTS_FILE}` file selects), and {LAUNCHER} "
            f"first on the call's PATH; {UNSIZED} is current without the kernel's sizing "
            f"paragraph; {NONE} is the task alone, with no kernel, skill or launcher. "
            "The model is always named and passed to codex with -m, so codex's configured "
            "default never runs. Each arm's measurement is "
            f"{len(fixture_names())} fixtures x 3 repetitions: "
            f"{len(fixture_names()) * len(REPETITIONS)} runs."
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
        "--model",
        default="",
        metavar="MODEL",
        help="the model codex runs, always named",
    )
    parser.add_argument(
        "--effort", default="medium", help="codex's model_reasoning_effort (default: medium)"
    )
    parser.add_argument(
        "--fixtures",
        default=",".join(fixture_names()),
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
    if args.arm is None:
        parser.error("name the arm: " + ", ".join(f"--arm {name}" for name in ARMS))
    names = [name.strip() for name in args.fixtures.split(",") if name.strip()]
    unknown = sorted(set(names) - set(fixture_names()))
    if unknown or not names:
        parser.error(f"no fixture {', '.join(unknown)}; there are {', '.join(fixture_names())}")
    return names


def _main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.summary:
        return summarize([Path(item) for item in args.summary])
    names = checked_fixtures(parser, args)
    arm = load_arm(args.arm)
    # Each fixture's install, read before anything runs: a fragment it names that the engine
    # does not ship stops the run here.
    arms = {name: load_arm(args.arm, selected_fragments(name)) for name in names}
    run_id = uuid.uuid4().hex
    out = Path(args.out) if args.out else RAW / run_id
    try:
        out.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        raise SystemExit(f"run: {out} already exists; name a new --out") from None
    status: dict[str, Any] = {
        "run_id": run_id,
        "date": datetime.date.today().isoformat(),
        "arm": args.arm,
        "model": args.model,
        "effort": args.effort,
        "repetition": args.repetition,
        **arm.record(),
        **source(),
        "cli_version": cli_version(),
        "api_keys_stripped": list(STRIP_POLICY),
        "api_keys_removed_from_environment": stripped_from_environment(),
    }
    login = preflight()
    status.update({key: login[key] for key in ("auth", "auth_evidence", "preflight")})
    if not login["ok"]:
        _write(out / "STATUS.json", {**status, "status": "UNVERIFIED", "fixtures": names})
        sys.stderr.write(
            "run: UNVERIFIED - preflight did not observe a ChatGPT login. Log in to codex "
            "interactively; this runner never falls back to an API key.\n"
        )
        return PREFLIGHT_EXIT
    path = call_path(arm, os.environ.get(FIXTURE_ROOT_ENV) or None)
    found = shutil.which("outcomebound", path=path)
    status["outcomebound_on_path"] = os.path.realpath(found) if found else None
    _write(out / "STATUS.json", {**status, "status": "running", "fixtures": names})
    failures = sum(run_one(out, status, name, arms[name], path) for name in names)
    state = "ran with failures" if failures else "ran"
    _write(
        out / "STATUS.json", {**status, "status": state, "fixtures": names, "failures": failures}
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(_main())
