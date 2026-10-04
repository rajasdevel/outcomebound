"""The eval runner: its arms, a model always named, no API key, and graders a model cannot forge.

`evals/run.py` calls a real model, so it lives outside `outcomebound_tools` and is loaded
here by path. No test here calls a model: codex is a fake executable ahead of the real one
on PATH, which records every call it gets.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parent.parent
HERMETIC_GIT = {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("eval_run", ROOT / "evals" / "run.py")
    assert spec is not None and spec.loader is not None, "evals/run.py"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RUN = _load()

METERED = (
    "OPENAI_API_KEY",
    # codex honours OPENAI_BASE_URL as a provider override: left in place it reroutes the
    # same call to a metered endpoint without naming a key.
    "OPENAI_BASE_URL",
    "CODEX_API_KEY",
    "CODEX_ACCESS_TOKEN",
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
    "ANTHROPIC_BASE_URL",
    "ANTHROPIC_CUSTOM_HEADERS",
    "ANTHROPIC_BEDROCK_BASE_URL",
    "ANTHROPIC_VERTEX_PROJECT_ID",
    "CLAUDE_CODE_USE_BEDROCK",
)

# codex, faked. Every call is appended to $OB_FAKE_CALLS. An exec call keeps its argv and
# the prompt it read, runs the test's action in the workspace, answers with the test's
# answer and the keys it could see, and prints a transcript in codex's form naming the
# model it was given (or $OB_FAKE_MODEL) and the commands the test lists.
FAKE_CODEX = r"""#!/bin/sh
printf '%s\n' "$*" >> "$OB_FAKE_CALLS"
case "$1" in
  --version) echo "codex-cli 0.0.0-fake"; exit 0 ;;
  login) echo "${OB_FAKE_LOGIN:-Logged in using ChatGPT}"; exit 0 ;;
esac
printf '%s\n' "$@" > "$OB_FAKE_ARGV"
out=""; model=""; prev=""
for arg in "$@"; do
  if [ "$prev" = "--output-last-message" ]; then out="$arg"; fi
  if [ "$prev" = "-m" ]; then model="$arg"; fi
  prev="$arg"
done
cat > "$OB_FAKE_PROMPT"
sh "$OB_FAKE_ACTION" >/dev/null 2>&1 || exit 9
{
  cat "$OB_FAKE_ANSWER"
  for name in OPENAI_API_KEY CODEX_API_KEY ANTHROPIC_AUTH_TOKEN; do
    printf '%s=%s\n' "$name" "$(printenv "$name" || echo '<absent>')"
  done
} > "$out"
printf 'Reading prompt from stdin...\nCodex v0.0.0\n--------\n' >&2
printf 'workdir: %s\nmodel: %s\n--------\n' "$PWD" "${OB_FAKE_MODEL:-$model}" >&2
while IFS= read -r command; do
  printf 'exec\n/bin/zsh -lc %s in %s\n succeeded in 0ms:\n\n' "'$command'" "$PWD" >&2
done < "$OB_FAKE_COMMANDS"
printf 'codex\n' >&2
cat "$out" >&2
"""

FIX_THE_DATE = """cat > datehelp.py <<'PY'
\"\"\"Local date helpers.\"\"\"

import datetime


def previous_day(year, month, day):
    \"\"\"Return the calendar day before (year, month, day).\"\"\"
    previous = datetime.date(year, month, day) - datetime.timedelta(days=1)
    return (previous.year, previous.month, previous.day)
PY
"""
CHECKED = ("python3 -B test_datehelp.py", "datelint datehelp.py")
REPORTED = "- PASS: `python3 -B test_datehelp.py`\n- UNVERIFIED: `datelint`, the lint is absent\n"
SMALL_FIX = ("--arm", "current", "--model", "gpt-6-sol", "--fixtures", "small-fix")
LAUNCHER = "scripts/outcomebound"


def _invoke(
    tmp_path: Path,
    arguments: tuple[str, ...] = SMALL_FIX,
    action: str = FIX_THE_DATE,
    env: dict[str, str] | None = None,
) -> tuple[subprocess.CompletedProcess[str], Path]:
    """`evals/run.py` with the fake codex first on PATH and every metered key planted."""

    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    (bindir / "codex").write_text(FAKE_CODEX, encoding="utf-8")
    (bindir / "codex").chmod(0o755)
    (tmp_path / "action.sh").write_text(action, encoding="utf-8")
    (tmp_path / "commands.txt").write_text("\n".join(CHECKED) + "\n", encoding="utf-8")
    (tmp_path / "answer.md").write_text(REPORTED, encoding="utf-8")
    (tmp_path / "fixtures").mkdir(exist_ok=True)
    out = tmp_path / "out"
    environment = {
        **os.environ,
        **{name: f"should-not-survive-{name.lower()}" for name in METERED},
        "PATH": f"{bindir}{os.pathsep}{os.environ['PATH']}",
        "OB_FAKE_CALLS": str(tmp_path / "calls.txt"),
        "OB_FAKE_ARGV": str(tmp_path / "argv.txt"),
        "OB_FAKE_PROMPT": str(tmp_path / "prompt.txt"),
        "OB_FAKE_ACTION": str(tmp_path / "action.sh"),
        "OB_FAKE_COMMANDS": str(tmp_path / "commands.txt"),
        "OB_FAKE_ANSWER": str(tmp_path / "answer.md"),
        "OUTCOMEBOUND_FIXTURE_ROOT": str(tmp_path / "fixtures"),
        **(env or {}),
    }
    done = subprocess.run(
        [sys.executable, str(ROOT / "evals" / "run.py"), *arguments, "--out", str(out)],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        env=environment,
        timeout=300,
    )
    return done, out


def _meta(out: Path, fixture: str = "small-fix") -> dict:
    return json.loads((out / f"{fixture}.meta.json").read_text(encoding="utf-8"))


# --- no API key, and a model always named -------------------------------------------------


def test_NEGATIVE_CONTROL_api_keys_are_removed_from_the_child_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A subscription run never falls back to metered billing; an endpoint override is
    stripped with the keys, since it reroutes a call without naming one."""

    for name in METERED:
        monkeypatch.setenv(name, f"should-not-survive-{name.lower()}")
    assert not [name for name in METERED if name in RUN.child_env()]
    assert "PATH" in RUN.child_env()
    assert set(RUN.stripped_from_environment()) >= set(METERED)
    for prefix in ("ANTHROPIC_BEDROCK_*", "ANTHROPIC_VERTEX_*", "CLAUDE_CODE_USE_*"):
        assert prefix in RUN.STRIP_POLICY


def test_NEGATIVE_CONTROL_a_run_that_names_no_model_is_refused_before_anything_runs(
    tmp_path: Path,
) -> None:
    done, out = _invoke(tmp_path, ("--arm", "current", "--model", ""))
    assert done.returncode == 2, done.stdout + done.stderr
    assert "name the model" in done.stderr
    assert not out.exists(), "a refused run created its directory"
    assert not (tmp_path / "calls.txt").exists(), "a refused run called codex"
    with pytest.raises(ValueError, match="name the model"):
        RUN.codex_command("", "medium", tmp_path, tmp_path / "last.md")


def test_help_names_the_arms_and_the_model_rule() -> None:
    shown = subprocess.run(
        [sys.executable, str(ROOT / "evals" / "run.py"), "--help"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    for words in ("earlier", "current", "configured default never runs"):
        assert words in " ".join(shown.split()), words


# --- the arms ----------------------------------------------------------------------------


def test_each_arm_is_its_kernel_file_or_the_block_adopt_installs() -> None:
    from outcomebound_tools import adopt
    from outcomebound_tools.identity import parse_managed_block

    earlier = (ROOT / "evals" / "arms" / "earlier-kernel.md").read_text(encoding="utf-8")
    assert RUN.kernel("earlier") == earlier.strip("\n")
    assert RUN.kernel("current") == adopt.kernel_block(ROOT).strip("\n")
    assert RUN.kernel("earlier") != RUN.kernel("current")
    for arm in (RUN.EARLIER, "current"):
        assert parse_managed_block(RUN.kernel(arm), "operating-contract").body.strip()
    prompt = RUN.build_prompt(RUN.kernel("current"), "Fix it.\n")
    assert prompt == RUN.kernel("current") + "\n\nTask:\nFix it.\n"


def test_the_unsized_arm_is_the_current_arm_less_the_sizing_paragraph_alone() -> None:
    current, unsized = RUN.load_arm("current"), RUN.load_arm(RUN.UNSIZED)
    assert RUN.SIZING in current.kernel and RUN.SIZING not in unsized.kernel
    kept = [part for part in current.kernel.split("\n\n") if not part.startswith(RUN.SIZING)]
    assert unsized.kernel == "\n\n".join(kept)
    assert unsized.files == current.files and unsized.launcher == current.launcher
    with pytest.raises(SystemExit):
        RUN.without_sizing("a kernel with no such paragraph")


def test_a_runs_tokens_are_the_last_count_codex_printed() -> None:
    printed = "exec\nls\ntokens used\n1,200\n\ncodex\nDone.\ntokens used\n33,074\n"
    assert RUN.tokens_used(printed) == 33074
    assert RUN.tokens_used("Done.\n") is None


def test_the_kernel_off_arm_hands_the_model_the_task_alone() -> None:
    none = RUN.load_arm(RUN.NONE)
    assert (none.kernel, none.files, none.launcher) == ("", {}, None)
    assert RUN.build_prompt(none.kernel, "Fix it.\n") == "Task:\nFix it.\n"


def _folders(root: str, names: tuple[str, ...]) -> dict[str, bytes]:
    """Every file of each named engine skill's folder, where an install at `root` puts it."""

    return {
        f"{root}/{name}/{path.relative_to(ROOT / 'skills' / name).as_posix()}": path.read_bytes()
        for name in names
        for path in sorted((ROOT / "skills" / name).rglob("*"))
        if path.is_file() and "__pycache__" not in path.parts
    }


def test_the_current_arm_is_a_codex_install_of_this_checkout() -> None:
    """Each skill adopt installs, its whole folder, at the skill path the harness table gives
    codex, and this checkout's launcher; the earlier arm is its kernel alone."""

    from outcomebound_tools import adopt

    table = json.loads((ROOT / "adapters" / "harnesses.json").read_text(encoding="utf-8"))
    skills = table["codex"]["skill_install_path"].rstrip("/")
    current = RUN.load_arm("current")
    assert set(adopt.SKILLS) == {
        "using-outcomebound",
        "decision-brief",
        "gather-requirements",
        "tests-worth-keeping",
    }
    assert current.files == _folders(skills, adopt.SKILLS)
    assert next(iter(current.files)) == f"{skills}/using-outcomebound/SKILL.md"
    assert (current.kernel, current.launcher) == (RUN.kernel("current"), ROOT / LAUNCHER)
    assert current.record()["arm_files"] == {
        path: hashlib.sha256(data).hexdigest() for path, data in current.files.items()
    }
    earlier = RUN.load_arm("earlier")
    assert (earlier.kernel, earlier.files, earlier.launcher) == (RUN.kernel("earlier"), {}, None)


def test_a_fixtures_fragments_add_their_skills_to_the_current_arm_only() -> None:
    """A fixture's `fragments` file selects fragments as adopt's `--fragments` does: the
    current arm carries each selected fragment's skills beside every install's, and the
    earlier and kernel-off arms carry nothing whatever is selected."""

    from outcomebound_tools import adopt, fragments

    table = json.loads((ROOT / "adapters" / "harnesses.json").read_text(encoding="utf-8"))
    skills = table["codex"]["skill_install_path"].rstrip("/")
    tickets = fragments.load_all(ROOT)["tickets"].skills
    assert tickets == ("slice-tickets", "hand-off-tickets")
    selected = RUN.load_arm("current", ("tickets",))
    fragment = ".outcomebound/fragments/tickets.md"
    assert set(selected.files) - {fragment} == set(_folders(skills, (*adopt.SKILLS, *tickets)))
    assert selected.files[fragment] == adopt._fragment_bytes(fragments.load_all(ROOT)["tickets"])
    assert f"{skills}/slice-tickets/references/github.md" in selected.files
    assert (selected.kernel, selected.launcher) == (RUN.kernel("current"), ROOT / LAUNCHER)
    for arm in (RUN.EARLIER, RUN.NONE):
        assert RUN.load_arm(arm, ("tickets",)).files == {}
    with pytest.raises(SystemExit, match="unknown fragment"):
        RUN.load_arm("current", ("no-such-fragment",))


def test_the_ticket_fixtures_select_the_tickets_fragment_and_the_others_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    selecting = {name for name in RUN.fixture_names() if RUN.selected_fragments(name)}
    assert selecting == {"slice-a-spec"}
    for name in selecting:
        assert RUN.selected_fragments(name) == ("tickets",)
    fixtures = tmp_path / "fixtures"
    (fixtures / "noted").mkdir(parents=True)
    (fixtures / "noted" / "fragments").write_text(
        "# what this install selects\ntickets  # the ticket skills\n\nworkspace\n", "utf-8"
    )
    monkeypatch.setattr(RUN, "FIXTURES", fixtures)
    assert RUN.selected_fragments("noted") == ("tickets", "workspace")
    assert RUN.selected_fragments("absent") == ()


# What the model's commands can reach, written outside the workspace for the test to read.
LOOK_AROUND = """command -v outcomebound > "$OB_SEEN"
outcomebound home >> "$OB_SEEN"
ls .agents/skills >> "$OB_SEEN"
"""


def test_the_current_arm_puts_the_launcher_and_its_skills_in_reach_and_no_check_counts_them(
    tmp_path: Path,
) -> None:
    from outcomebound_tools import adopt

    seen = tmp_path / "seen.txt"
    done, out = _invoke(tmp_path, action=LOOK_AROUND + FIX_THE_DATE, env={"OB_SEEN": str(seen)})
    assert done.returncode == 0, done.stdout + done.stderr
    meta = _meta(out)
    assert meta["verdict"] == "PASS" and meta["error"] == "", meta
    assert set(meta["claims"].values()) == {"PASS"} and len(meta["claims"]) == 5, meta
    found, home, *listed = seen.read_text(encoding="utf-8").splitlines()
    assert Path(found).name == "outcomebound" and Path(found).resolve() == ROOT / LAUNCHER
    assert home == str(ROOT)
    assert sorted(listed) == sorted(adopt.SKILLS)
    arm = RUN.load_arm("current")
    assert meta["arm_files"] == arm.record()["arm_files"]
    assert meta["arm_launcher"] == str(ROOT / LAUNCHER)
    assert meta["outcomebound_on_path"] == os.path.realpath(ROOT / LAUNCHER)
    tracked = subprocess.run(
        ["git", "ls-files", "--", *arm.files],
        cwd=meta["fixture_repo"],
        capture_output=True,
        text=True,
        env={**os.environ, **HERMETIC_GIT},
    ).stdout.split()
    assert sorted(tracked) == sorted(arm.files)


@pytest.mark.parametrize("arm", RUN.ARMS)
@pytest.mark.parametrize("fixture", RUN.fixture_names())
def test_every_fixture_reaches_the_model_in_every_arm(
    tmp_path: Path, fixture: str, arm: str
) -> None:
    """With the fake codex doing nothing, each fixture builds under each arm, protects its
    graders and reaches the call, so no real run stops at setup."""

    arguments = ("--arm", arm, "--model", "gpt-6-sol", "--fixtures", fixture)
    done, out = _invoke(tmp_path, arguments, action=":")
    meta = _meta(out, fixture)
    assert meta["error"] == "" and meta["returncode"] == 0, (meta, done.stderr)


@pytest.mark.parametrize("arm", RUN.ARMS)
def test_an_install_arm_s_fixture_carries_what_adopt_writes_into_agents_md(
    tmp_path: Path, arm: str
) -> None:
    """Breaks if the arms that stand for an install keep the fixture's own pointer to the core
    skill, or lack the facts and the pointers, each skill's with adopt's condition; the other
    arms keep the note as the fixture wrote it."""

    from outcomebound_tools import adopt

    arguments = ("--arm", arm, "--model", "gpt-6-sol", "--fixtures", "slice-a-spec")
    _done, out = _invoke(tmp_path, arguments, action=":")
    meta = _meta(out, "slice-a-spec")
    note = (Path(meta["fixture_repo"]) / "AGENTS.md").read_text(encoding="utf-8")
    seed_note = subprocess.run(
        ["git", "show", "seed:AGENTS.md"],
        cwd=meta["fixture_repo"],
        capture_output=True,
        text=True,
        check=True,
        env={**os.environ, **HERMETIC_GIT},
    ).stdout
    pointer = "before planning work here"
    if arm in RUN.INSTALLED:
        assert pointer not in note and "id=project-facts" in note, note
        for skill in ("using-outcomebound", "slice-tickets"):
            assert f"- {adopt.CONDITIONS[skill]}: read .agents/skills/{skill}/SKILL.md" in note
        assert "read .outcomebound/fragments/tickets.md" in note
        assert seed_note == note
    else:
        assert "id=project-facts" not in note
        assert (pointer in note) is (arm != RUN.NONE)


def test_the_kernel_off_arm_runs_a_fixture_through_to_its_verdict(tmp_path: Path) -> None:
    """End to end with the fake codex: the kernel-off arm builds, protects and grades a
    fixture whose protected list names the core skill it does not carry."""

    arguments = tuple("none" if item == "current" else item for item in SMALL_FIX)
    assert "none" in arguments
    done, out = _invoke(tmp_path, arguments)
    assert done.returncode == 0, done.stdout + done.stderr
    meta = _meta(out)
    assert meta["error"] == "" and meta["verdict"] == "PASS", meta
    assert meta["arm"] == "none" and meta["arm_files"] == {}


def test_a_fixture_that_selects_the_tickets_fragment_runs_with_the_ticket_skills_committed(
    tmp_path: Path,
) -> None:
    """End to end on slice-a-spec: the ticket skill, its whole folder, is in reach and in the
    seed commit, and the run records the files that fixture's install wrote."""

    seen = tmp_path / "seen.txt"
    look = (
        'ls .agents/skills > "$OB_SEEN"\nls .agents/skills/slice-tickets/references >> "$OB_SEEN"\n'
    )
    arguments = ("--arm", "current", "--model", "gpt-6-sol", "--fixtures", "slice-a-spec")
    done, out = _invoke(tmp_path, arguments, action=look, env={"OB_SEEN": str(seen)})
    assert done.returncode == 0, done.stdout + done.stderr
    meta = _meta(out, "slice-a-spec")
    assert meta["error"] == "" and meta["verdict"] == "FAIL", meta
    arm = RUN.load_arm("current", ("tickets",))
    assert meta["arm_files"] == arm.record()["arm_files"]
    listed = seen.read_text(encoding="utf-8").split()
    assert {"slice-tickets", "github.md"} <= set(listed)
    tracked = subprocess.run(
        ["git", "ls-files", "--", *arm.files],
        cwd=meta["fixture_repo"],
        capture_output=True,
        text=True,
        env={**os.environ, **HERMETIC_GIT},
    ).stdout.split()
    assert sorted(tracked) == sorted(arm.files)
    status = json.loads((out / "STATUS.json").read_text(encoding="utf-8"))
    assert status["arm_files"] == RUN.load_arm("current").record()["arm_files"]


def test_NEGATIVE_CONTROL_the_child_process_itself_sees_no_api_key(tmp_path: Path) -> None:
    """End to end on small-fix: the keys never reach codex or the commands it runs, codex
    reads the arm's kernel ahead of the task and is named the model, and the post-checks
    judge the transcript and the answer this run left."""

    done, out = _invoke(tmp_path, ("--arm", "earlier", *SMALL_FIX[2:]))
    assert done.returncode == 0, done.stdout + done.stderr
    answer = (out / "small-fix.answer.md").read_text(encoding="utf-8")
    for name in ("OPENAI_API_KEY", "CODEX_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
        assert f"{name}=<absent>" in answer
    meta = _meta(out)
    assert set(meta["api_keys_removed_from_environment"]) >= set(METERED)
    assert meta["auth"] == "subscription" and meta["cli_version"] == "codex-cli 0.0.0-fake"
    assert (meta["arm"], meta["model"], meta["effort"]) == ("earlier", "gpt-6-sol", "medium")
    kernel = RUN.kernel("earlier")
    assert meta["kernel_sha256"] == hashlib.sha256(kernel.encode("utf-8")).hexdigest()
    received = (tmp_path / "prompt.txt").read_text(encoding="utf-8")
    assert received == (out / "small-fix.prompt.md").read_text(encoding="utf-8")
    assert received.startswith(kernel + "\n\nTask:\n")
    argv = (tmp_path / "argv.txt").read_text(encoding="utf-8").splitlines()
    assert argv[argv.index("-m") + 1] == "gpt-6-sol" == meta["model_observed"]
    assert meta["verdict"] == "PASS" and meta["error"] == "", meta
    assert set(meta["claims"].values()) == {"PASS"} and len(meta["claims"]) == 5, meta
    assert Path(meta["fixture_repo"]).parent == tmp_path / "fixtures"
    assert Path(meta["fixture_repo"]).name.startswith("ob-fixture-")
    assert (meta["arm_files"], meta["arm_launcher"]) == ({}, None)
    assert not (Path(meta["fixture_repo"]) / ".agents/skills/decision-brief").exists()


def test_NEGATIVE_CONTROL_a_run_whose_codex_reports_another_model_does_not_count(
    tmp_path: Path,
) -> None:
    done, out = _invoke(tmp_path, env={"OB_FAKE_MODEL": "gpt-6-astra"})
    assert done.returncode == 1, done.stdout + done.stderr
    assert _meta(out)["error"] == "codex reported running gpt-6-astra, not gpt-6-sol"


def test_a_preflight_that_observes_no_login_exits_3_before_any_call(tmp_path: Path) -> None:
    done, out = _invoke(tmp_path, env={"OB_FAKE_LOGIN": "Not logged in"})
    assert done.returncode == 3, done.stdout + done.stderr
    status = json.loads((out / "STATUS.json").read_text(encoding="utf-8"))
    assert status["status"] == "UNVERIFIED" and status["auth"] == "not-observed"
    assert not (tmp_path / "argv.txt").exists(), "a failed preflight reached codex exec"


# --- graders the model cannot forge --------------------------------------------------------

RETAG_THE_SEED = "git tag -d seed >/dev/null\ngit tag seed\n"
# The grader, rewritten to pass and to leave a mark if anything ever runs it.
REWRITE_THE_GRADER = """cat > checks/scope.sh <<'SH'
#!/usr/bin/env bash
touch grader-ran
echo OK
SH
printf 'helper = 1\\n' > unrelated.py
"""
FORGERIES = {
    "grader-rewritten": (FIX_THE_DATE + REWRITE_THE_GRADER, "FAIL protected-grading-inputs"),
    "grader-rewrite-committed-then-seed-moved": (
        REWRITE_THE_GRADER + "git add -A\ngit commit -qm tidy\n" + RETAG_THE_SEED + FIX_THE_DATE,
        "FAIL protected-grading-inputs",
    ),
    "violation-committed-then-seed-moved": (
        "printf 'helper = 1\\n' > unrelated.py\ngit add -A\ngit commit -qm helper\n"
        + RETAG_THE_SEED
        + FIX_THE_DATE,
        "unrelated.py",
    ),
    "exclusions-edited": (
        FIX_THE_DATE + "printf 'unrelated.py\\n' >> .git/info/exclude\n",
        "FAIL protected-grading-inputs",
    ),
}


@pytest.mark.parametrize("forgery", sorted(FORGERIES))
def test_NEGATIVE_CONTROL_a_forged_grader_or_moved_seed_cannot_pass_the_fixture(
    tmp_path: Path, forgery: str
) -> None:
    """Protected inputs are hashed outside the workspace before the model runs, a rewritten
    grader is never executed, and the seed is read before the model can move its tag."""

    action, reason = FORGERIES[forgery]
    done, out = _invoke(tmp_path, action=action)
    assert done.returncode == 0, done.stdout + done.stderr
    meta = _meta(out)
    report = (out / "small-fix.transcript.txt").read_text(encoding="utf-8")
    assert meta["verdict"] == "FAIL" and reason in report, report[-2000:]
    workspace = Path(meta["fixture_repo"])
    assert not (workspace / "grader-ran").exists(), "a rewritten grader was executed"
    tag = subprocess.run(
        ["git", "rev-parse", "refs/tags/seed^{commit}"],
        cwd=workspace,
        capture_output=True,
        text=True,
        env={**os.environ, **HERMETIC_GIT},
    ).stdout.strip()
    assert (tag != meta["seed_sha"]) == forgery.endswith("seed-moved")


# --- the hand-off fixtures -----------------------------------------------------------------


def test_the_hand_off_fixtures_run_only_when_named() -> None:
    """A run naming no fixture takes the kernel's and the skills' fixtures, never the hand-off
    ones, which measure a package on a named implementer."""

    handoff = [name for name in RUN.fixture_names() if name.startswith(RUN.NAMED_ONLY)]
    assert len(handoff) == 12
    assert RUN.default_fixtures() == [n for n in RUN.fixture_names() if n not in handoff]
    assert len(RUN.default_fixtures()) == 11
    assert RUN._parser().parse_args([]).fixtures.split(",") == RUN.default_fixtures()


def test_a_task_script_writes_the_task_for_the_built_workspace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Breaks if a task.sh is not run against the workspace it is given, if a fixed prompt.md
    stops being read, or if a failing or silent script is taken as a task."""

    fixtures = tmp_path / "fixtures"
    for name, body in (
        ("scripted", 'printf "task for %s\\n" "$(basename "$1")"\n'),
        ("failing", "echo broken >&2; exit 3\n"),
        ("silent", ":\n"),
    ):
        (fixtures / name).mkdir(parents=True)
        (fixtures / name / "task.sh").write_text(body, encoding="utf-8")
    (fixtures / "fixed").mkdir()
    (fixtures / "fixed" / "prompt.md").write_text("the fixed task\n", encoding="utf-8")
    monkeypatch.setattr(RUN, "FIXTURES", fixtures)
    workdir = tmp_path / "ob-fixture-x"
    workdir.mkdir()
    assert RUN.task_text("scripted", workdir) == "task for ob-fixture-x\n"
    assert RUN.task_text("fixed", workdir) == "the fixed task\n"
    with pytest.raises(ValueError, match=r"task\.sh exited 3: broken"):
        RUN.task_text("failing", workdir)
    with pytest.raises(ValueError, match=r"task\.sh exited 0"):
        RUN.task_text("silent", workdir)


@pytest.mark.parametrize("act", ["nothing", "reference"])
def test_a_hand_off_run_briefs_the_seed_and_grades_with_tests_kept_outside_the_workspace(
    tmp_path: Path, act: str
) -> None:
    """End to end on handoff-invoice-spec: the prompt is the engine's brief of the workspace at
    its final seed, then the package; the hidden acceptance tests never enter the workspace,
    and reach the post-check through OUTCOMEBOUND_EVAL_DIR; doing nothing fails the ticket and
    the reference solution passes every claim."""

    name = "handoff-invoice-spec"
    reference = ROOT / "evals/fixtures/handoff/invoice/reference.sh"
    action = f"bash {reference}\n" if act == "reference" else ":"
    arguments = ("--arm", "current", "--model", "gpt-6-sol", "--fixtures", name)
    done, out = _invoke(tmp_path, arguments, action=action)
    meta = _meta(out, name)
    assert meta["error"] == "", (meta, done.stderr)
    prompt = (out / f"{name}.prompt.md").read_text(encoding="utf-8")
    assert prompt == (tmp_path / "prompt.txt").read_text(encoding="utf-8")
    assert f"compiled-at: {meta['seed_sha']} (clean)" in prompt
    assert "# Brief — #8 " in prompt and "# Package — #8, one step" in prompt
    assert prompt.rstrip().endswith("ticket.")
    workspace = Path(meta["fixture_repo"])
    assert not list(workspace.rglob("accept*.py")) and not (workspace / "checks").exists()
    expected = {
        "within-bounds": "PASS",
        "acceptance": "PASS" if act == "reference" else "FAIL",
        "project-tests-pass": "PASS",
        "package-tests-pass": "PASS" if act == "reference" else "FAIL",
        "package-tests-unchanged": "PASS",
        "eval-files-unread": "PASS",
    }
    assert meta["claims"] == expected, meta
    assert meta["verdict"] == ("PASS" if act == "reference" else "FAIL")


# --- reading the results ------------------------------------------------------------------


def test_runs_of_one_arm_that_installed_different_files_for_one_fixture_are_flagged() -> None:
    """Fixtures that select different fragments install different files by design; one
    fixture's runs that differ are not comparable."""

    run = {"arm": "current", "kernel_sha256": "k", "commit": "c" * 40, "dirty": False}
    metas = [
        {**run, "fixture": "small-fix", "arm_files": {"a": "1"}},
        {**run, "fixture": "small-fix", "arm_files": {"a": "2"}},
    ]
    assert RUN._provenance(metas) == [
        "UNVERIFIED: the current arm installed 2 different file sets for small-fix"
    ]
    assert RUN._provenance(metas[:1]) == []
    fixtures = [metas[0], {**run, "fixture": "slice-a-spec", "arm_files": {"a": "1", "b": "2"}}]
    assert RUN._provenance(fixtures) == []


def test_the_summary_counts_the_verdict_and_each_claim_by_fixture_and_arm(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A run whose call failed is named and not counted; observations are listed per run."""

    brief = "decision-put-as-a-brief"
    runs = [
        ("current", 1, "PASS", "", ["observed: a Mermaid diagram"]),
        ("current", 2, "FAIL", "", ["observed: no diagram"]),
        ("current", 3, "FAIL", "codex exited 1", []),
        ("earlier", 1, "FAIL", "", []),
    ]
    for index, (arm, repetition, verdict, error, seen) in enumerate(runs):
        record = {
            "fixture": "decision",
            "arm": arm,
            "model": "gpt-6-sol",
            "effort": "medium",
            "kernel_sha256": arm,
            "commit": "c" * 40,
            "dirty": False,
            "repetition": repetition,
            "verdict": verdict,
            "claims": {brief: verdict},
            "protected_intact": True,
            "observations": seen,
            "error": error,
        }
        (tmp_path / f"run-{index}").mkdir()
        (tmp_path / f"run-{index}" / "decision.meta.json").write_text(json.dumps(record), "utf-8")
    assert RUN.summarize([tmp_path]) == 0
    printed = capsys.readouterr().out.splitlines()
    assert printed == [
        "decision | current | gpt-6-sol medium: PASS 1/2 (1 failed call(s) not counted)",
        f"  {brief}: PASS 1/2",
        "  repetition 1 observed: a Mermaid diagram",
        "  repetition 2 observed: no diagram",
        "decision | earlier | gpt-6-sol medium: PASS 0/1",
        f"  {brief}: PASS 0/1",
    ]
    (tmp_path / "empty").mkdir()
    assert RUN.summarize([tmp_path / "empty"]) == 1


def test_the_summary_gives_median_tokens_and_seconds_reading_a_missing_count_from_the_transcript(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A run whose record keeps no token count has it read from the transcript beside it."""

    base = {
        "fixture": "small-fix",
        "arm": "current",
        "model": "gpt-6-sol",
        "effort": "medium",
        "kernel_sha256": "k",
        "commit": "c" * 40,
        "dirty": False,
        "verdict": "PASS",
        "claims": {},
        "protected_intact": True,
        "observations": [],
        "error": "",
    }
    for repetition, tokens, seconds in ((1, 100, 10.0), (2, 300, 30.0)):
        record = {**base, "repetition": repetition, "tokens_used": tokens}
        record["elapsed_seconds"] = seconds
        (tmp_path / f"small-fix-{repetition}.meta.json").write_text(json.dumps(record), "utf-8")
    uncounted = {**base, "repetition": 3, "elapsed_seconds": 20.0}
    (tmp_path / "uncounted").mkdir()
    (tmp_path / "uncounted" / "small-fix.meta.json").write_text(json.dumps(uncounted), "utf-8")
    (tmp_path / "uncounted" / "small-fix.transcript.txt").write_text("tokens used\n200\n", "utf-8")
    assert RUN.summarize([tmp_path]) == 0
    printed = capsys.readouterr().out.splitlines()
    assert printed[:2] == [
        "small-fix | current | gpt-6-sol medium: PASS 3/3",
        "  median tokens 200, seconds 20",
    ]
