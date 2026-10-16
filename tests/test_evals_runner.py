"""The eval runner: its arms, a model always named, no API key, and graders a model cannot forge.

`evals/run.py` calls a real model, so it lives outside `outcomebound_tools` and is loaded
here by path. No test here calls a model: codex is a fake executable ahead of the real one
on PATH, which records every call it gets and writes the native session a codex-cli 0.162.1
call leaves under `$CODEX_HOME/sessions`.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from evals.harnesses import CallResult, Request
from tests.eval_helpers import HERMETIC_GIT, ROOT, RUN
from tests.portable import needs_posix_bash

# The fixture runner uses bash; this marker reports unavailable platforms explicitly.
pytestmark = needs_posix_bash

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
# answer and the keys it could see, prints a stream in the form of codex-cli 0.162.1 (a thread
# id and no model) with the commands the test lists, and leaves the native session record
# under $CODEX_HOME/sessions: the model and effort it was given, unless a test sets
# $OB_FAKE_MODEL or $OB_FAKE_EFFORT, and its working directory. $OB_FAKE_SESSION breaks the
# record in one way (none, twice, symlink, wrong-id, no-turn-context, split-model, no-version);
# $OB_FAKE_ITEMS names extra item types for the stream; $OB_FAKE_STREAM_MODEL makes the stream
# name a model, as an older CLI did. $OB_FAKE_NATIVE_COMMANDS makes the stream give each command
# as the shell-quoted argv of a `zsh -lc` call with no working directory, as 0.162.1 does, and
# the session record each command's `CommandExecution` item with its `cwd`: `exact`; `workdir`
# (the first command ran in a subfolder of the session's cwd); `count` (one item missing);
# `text` (the first item's script differs).
FAKE_CODEX = r"""#!/bin/sh
printf '%s\n' "$*" >> "$OB_FAKE_CALLS"
case "$1" in
  --version) echo "${OB_FAKE_VERSION:-codex-cli 0.162.1}"; exit 0 ;;
  login) echo "${OB_FAKE_LOGIN:-Logged in using ChatGPT}"; exit "${OB_FAKE_LOGIN_EXIT:-0}" ;;
esac
printf '%s\n' "$@" > "$OB_FAKE_ARGV"
out=""; prev=""
for arg in "$@"; do
  if [ "$prev" = "--output-last-message" ]; then out="$arg"; fi
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
python3 - <<'EVENTS'
import json,os,shlex
from pathlib import Path
argv=Path(os.environ["OB_FAKE_ARGV"]).read_text().splitlines()
model=os.environ.get("OB_FAKE_MODEL") or argv[argv.index("-m")+1]
effort=os.environ.get("OB_FAKE_EFFORT") or next(
    a.split("=",1)[1] for a in argv if a.startswith("model_reasoning_effort="))
cwd=os.environ.get("OB_FAKE_CWD") or os.getcwd()
key="0192f0aa-1111-7222-8333-444455556666"
mode=os.environ.get("OB_FAKE_SESSION","")
started={"type":"thread.started","thread_id":key}
if os.environ.get("OB_FAKE_STREAM_MODEL"):
    started["model"]=os.environ["OB_FAKE_STREAM_MODEL"]
print(json.dumps(started))
extras=[name for name in os.environ.get("OB_FAKE_ITEMS","").split(",") if name]
if "error" in extras:
    warning={"id":"item_0","type":"error","message":"Ignoring malformed agent role definition"}
    print(json.dumps({"type":"item.completed","item":warning}))
print(json.dumps({"type":"turn.started"}))
native=os.environ.get("OB_FAKE_NATIVE_COMMANDS","")
ran=[]
for number,command in enumerate(Path(os.environ["OB_FAKE_COMMANDS"]).read_text().splitlines()):
    argv_=["/bin/zsh","-lc",command]
    ran.append((argv_,os.getcwd()+"/sub" if native=="workdir" and number==0 else os.getcwd()))
    item={"id":str(number),"type":"command_execution","command":command,"cwd":os.getcwd()}
    if native:
        item={"id":str(number),"type":"command_execution","command":shlex.join(argv_)}
    print(json.dumps({"type":"item.started","item":item}))
    print(json.dumps({"type":"item.completed","item":{**item,"status":"completed","exit_code":0}}))
if "file_change" in extras:
    edit={"id":"item_8","type":"file_change","changes":[{"path":"a.py","kind":"update"}]}
    print(json.dumps({"type":"item.started","item":{**edit,"status":"in_progress"}}))
    print(json.dumps({"type":"item.completed","item":{**edit,"status":"completed"}}))
if "future_tool" in extras:
    print(json.dumps({"type":"item.completed","item":{"id":"item_9","type":"future_tool"}}))
print(json.dumps({"type":"turn.completed","usage":{"input_tokens":0,"output_tokens":0}}))
if mode != "none" and os.environ.get("CODEX_HOME"):
    home=Path(os.environ["CODEX_HOME"])
    day=home/"sessions"/"2026"/"10"/"14"
    day.mkdir(parents=True,exist_ok=True)
    meta={"id":"11111111-1111-4111-8111-111111111111" if mode=="wrong-id" else key,
          "cwd":cwd,"cli_version":"0.162.1","originator":"codex_exec","source":"exec"}
    if mode=="no-version":
        del meta["cli_version"]
    context={"cwd":cwd,"model":model,"effort":effort,"approval_policy":"never"}
    records=[{"type":"session_meta","payload":meta}]
    if mode!="no-turn-context":
        records.append({"type":"turn_context","payload":context})
    shown=ran[:-1] if native=="count" else ran
    if native=="text":
        shown=[([*shown[0][0][:2],shown[0][0][2]+" --changed"],shown[0][1]),*shown[1:]]
    for number,(a,where) in enumerate(shown if native else []):
        item={"type":"CommandExecution","id":f"exec-{number}","command":a,
              "cwd":"file://"+where,"status":"completed","exit_code":0}
        records.append({"type":"event_msg","payload":{"type":"item_completed","item":item}})
    if mode=="split-model":
        records.append({"type":"turn_context","payload":{**context,"model":"gpt-6-astra"}})
    text="".join(json.dumps(record)+"\n" for record in records)
    name=f"rollout-2026-10-14T00-00-00-{key}.jsonl"
    if mode=="symlink":
        (home/"elsewhere.jsonl").write_text(text)
        (day/name).symlink_to(home/"elsewhere.jsonl")
    else:
        (day/name).write_text(text)
    if mode=="twice":
        (day/f"rollout-2026-10-14T00-00-01-{key}.jsonl").write_text(text)
EVENTS

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


# The session folder and the results of a run must lie outside every folder the model may write,
# and the system's temporary folders are among them (the sandbox grants them), so a run's
# CODEX_HOME and output directory live under the checkout, not under pytest's tmp_path.
_TRUSTED: list[Path] = []


def _trusted() -> Path:
    base = ROOT / ".agents" / "work" / "eval-native-tests"
    base.mkdir(parents=True, exist_ok=True)
    folder = Path(tempfile.mkdtemp(prefix="run-", dir=base))
    _TRUSTED.append(folder)
    return folder


@pytest.fixture(autouse=True)
def _remove_trusted_folders():
    yield
    while _TRUSTED:
        shutil.rmtree(_TRUSTED.pop(), ignore_errors=True)


def _invoke(
    tmp_path: Path,
    arguments: tuple[str, ...] = SMALL_FIX,
    action: str = FIX_THE_DATE,
    env: dict[str, str] | None = None,
    output_dir: Path | None = None,
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
    trusted = _trusted()
    out = output_dir or trusted / "out"
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
        "CODEX_HOME": str(trusted / "home"),
        **(env or {}),
    }
    done = subprocess.run(
        [sys.executable, str(ROOT / "evals" / "run.py"), *arguments, "--out", str(out)],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        env=environment,
        timeout=300,
        encoding="utf-8",
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
        RUN.make_harness().command("", "medium", tmp_path, tmp_path / "last.md")


def test_help_names_the_arms_and_the_model_rule() -> None:
    shown = subprocess.run(
        [sys.executable, str(ROOT / "evals" / "run.py"), "--help"],
        capture_output=True,
        text=True,
        check=True,
        encoding="utf-8",
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
    assert current.files == _folders(skills, adopt.SKILLS)
    assert next(iter(current.files)) == f"{skills}/using-outcomebound/SKILL.md"
    assert (current.kernel, current.launcher) == (RUN.kernel("current"), ROOT / LAUNCHER)
    assert current.record()["arm_files"] == {
        path: hashlib.sha256(data).hexdigest() for path, data in current.files.items()
    }
    earlier = RUN.load_arm("earlier")
    assert (earlier.kernel, earlier.files, earlier.launcher) == (RUN.kernel("earlier"), {}, None)


def test_the_current_arm_carries_every_installs_skills_and_the_fixtures_fragments_only() -> None:
    """A fixture's `fragments` file selects fragments as adopt's `--fragments` does: the
    current arm carries every install's thirteen skills and each selected fragment's file, and
    the earlier and kernel-off arms carry nothing whatever is selected."""

    from outcomebound_tools import adopt, fragments

    table = json.loads((ROOT / "adapters" / "harnesses.json").read_text(encoding="utf-8"))
    skills = table["codex"]["skill_install_path"].rstrip("/")
    selected = RUN.load_arm("current", ("tickets",))
    fragment = ".outcomebound/fragments/tickets.md"
    assert set(selected.files) - {fragment} == set(_folders(skills, adopt.SKILLS))
    assert selected.files[fragment] == adopt._fragment_bytes(fragments.load_all(ROOT)["tickets"])
    assert f"{skills}/slice-tickets/references/github.md" in selected.files
    assert (selected.kernel, selected.launcher) == (RUN.kernel("current"), ROOT / LAUNCHER)
    for arm in (RUN.EARLIER, RUN.NONE):
        assert RUN.load_arm(arm, ("tickets",)).files == {}
    with pytest.raises(SystemExit, match="unknown fragment"):
        RUN.load_arm("current", ("no-such-fragment",))


def test_each_fixture_selects_the_fragment_it_names_and_the_others_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    selecting = {name for name in RUN.fixture_names() if RUN.selected_fragments(name)}
    tickets = {
        "slice-a-spec",
        "slice-gate-findings",
        "slice-parity-registry",
        "slice-shared-ledger",
    }
    runtime = {"runtime-check", "runtime-none"}
    deploy = {"deploy-authorized", "deploy-none", "deploy-wrong-version"}
    commands = {"field-commands-hazards"}
    assert selecting == tickets | runtime | deploy | commands
    for names, fragment in (
        (tickets, "tickets"),
        (runtime, "runtime"),
        (deploy, "deploy"),
        (commands, "commands"),
    ):
        for name in names:
            assert RUN.selected_fragments(name) == (fragment,)
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
        encoding="utf-8",
    ).stdout.split()
    assert sorted(tracked) == sorted(arm.files)


# No fixture's setup branches on the arm: the arms differ in the files installed (`current` and
# `unsized` install the same set, `earlier` and `none` none), in the protected list (`none` drops
# the skills) and in the note rewrite for installs. So every fixture runs under the install arm
# and under the kernel-off arm, and the other two arms on a few fixtures that cover each shape.
_ARM_SAMPLE = ("small-fix", "slice-a-spec", "decision")
_ARM_CASES = [
    pytest.param(fixture, arm, id=f"{arm}-{fixture}")
    for fixture in RUN.fixture_names()
    for arm in RUN.ARMS
    if arm in ("current", RUN.NONE) or fixture in _ARM_SAMPLE
]


@pytest.mark.parametrize(("fixture", "arm"), _ARM_CASES)
def test_every_fixture_reaches_the_model_in_every_arm(
    tmp_path: Path, fixture: str, arm: str
) -> None:
    """With the fake codex doing nothing, each fixture builds under the arms that differ in what
    they install, protects its graders and reaches the call, so no real run stops at setup."""

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
        encoding="utf-8",
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
        encoding="utf-8",
    ).stdout.split()
    assert sorted(tracked) == sorted(arm.files)
    status = json.loads((out / "STATUS.json").read_text(encoding="utf-8"))
    assert status["arm_files"] == RUN.load_arm("current").record()["arm_files"]


def test_the_earlier_ref_makes_the_earlier_arm_a_full_install_of_that_ref(tmp_path: Path) -> None:
    """`--earlier-ref REF` replaces the kept kernel wording with an install of the engine at REF:
    its kernel, its ten skills (in the arm files and in the fixture's note path) and the pointers,
    while the launcher stays this checkout's. Checked on HEAD, which every clone has."""

    def at_head(path: str) -> bytes:
        return subprocess.run(
            ["git", "-C", str(ROOT), "show", f"HEAD:{path}"], capture_output=True, check=True
        ).stdout

    done, out = _invoke(tmp_path, ("--arm", "earlier", "--earlier-ref", "HEAD", *SMALL_FIX[2:]))
    assert done.returncode == 0, done.stdout + done.stderr
    meta = _meta(out)
    status = json.loads((out / "STATUS.json").read_text(encoding="utf-8"))
    assert (status["arm"], status["earlier_ref"]) == ("earlier", "HEAD")
    assert meta["arm_files"] and meta["arm_launcher"] == str(ROOT / LAUNCHER)
    repo = Path(meta["fixture_repo"])
    skill = at_head("skills/using-outcomebound/SKILL.md")
    for root in (".agents/skills", ".outcomebound/skills"):
        assert (repo / root / "using-outcomebound" / "SKILL.md").read_bytes() == skill
    assert (repo / ".agents/skills/decision-brief/SKILL.md").is_file()
    prompt = (out / "small-fix.prompt.md").read_text(encoding="utf-8")
    assert "Task:" in prompt and "id=operating-contract" in prompt
    assert hashlib.sha256(RUN.kernel("current").encode()).hexdigest() == meta["kernel_sha256"]


def test_the_earlier_ref_is_refused_for_another_arm_and_for_an_unknown_ref(tmp_path: Path) -> None:
    done, _ = _invoke(tmp_path, ("--earlier-ref", "HEAD", *SMALL_FIX))
    assert done.returncode == 2 and "--earlier-ref changes the earlier arm" in done.stderr
    done, _ = _invoke(
        tmp_path, ("--arm", "earlier", "--earlier-ref", "no-such-ref", *SMALL_FIX[2:])
    )
    assert done.returncode != 0 and "--earlier-ref no-such-ref" in done.stderr


def _commit_of(changes: dict[str, bytes | None], base: str | None = None) -> str:
    """A commit made of `base`'s tree (an empty tree without it) with `changes` applied, a path
    mapped to None removed, in this checkout's object store and on no branch: a ref for the
    runner to read that moves no branch of the checkout and is collected with the other
    unreferenced objects."""

    index = Path(tempfile.mkdtemp(prefix="ob-index-")) / "index"
    env = {**os.environ, **HERMETIC_GIT, "GIT_INDEX_FILE": str(index)}

    def git(*arguments: str, data: bytes | None = None) -> str:
        done = subprocess.run(
            ["git", "-C", str(ROOT), *arguments], input=data, capture_output=True, env=env
        )
        assert done.returncode == 0, done.stderr.decode()
        return done.stdout.decode().strip()

    try:
        if base:
            git("read-tree", base)
        for path, data in changes.items():
            if data is None:
                git("update-index", "--force-remove", path)
                continue
            blob = git("hash-object", "-w", "--stdin", data=data)
            git("update-index", "--add", "--cacheinfo", f"100644,{blob},{path}")
        tree = git("write-tree")
        return git(
            "-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit-tree", tree,
            "-m", "a guidance set",
        )  # fmt: skip
    finally:
        shutil.rmtree(index.parent, ignore_errors=True)


def _guidance_set(folder: Path, files: dict[str, bytes]) -> Path:
    for path, data in files.items():
        (folder / path).parent.mkdir(parents=True, exist_ok=True)
        (folder / path).write_bytes(data)
    return folder


def test_the_earlier_verbatim_arm_installs_another_guidance_sets_own_files(tmp_path: Path) -> None:
    """`--earlier-verbatim DIR`: the set's AGENTS.md heads the fixture's own note, and every file
    of its skills/ is at codex's skill path, byte for byte; none of OutcomeBound's reaches the
    fixture (no kernel in the prompt, core skill, facts block, pointer or launcher);
    `--arm-label` names the arm in the status, the meta, INDEX.json and the summary."""

    agents = b"Be lazy about the solution.\r\nNever lazy about the change.\n"
    skill = b"---\nname: lazy\ndescription: Use always.\n---\nCut first.\n"
    note = b"A note beside the skill.\n\xff\n"
    folder = _guidance_set(
        tmp_path / "set",
        {
            "AGENTS.md": agents,
            "skills/lazy/SKILL.md": skill,
            "skills/lazy/notes/more.md": note,
            "skills/other/SKILL.md": b"Another.\n",
        },
    )
    arguments = (
        *("--arm", "earlier", "--earlier-verbatim", str(folder), "--arm-label", "V4-set"),
        *SMALL_FIX[2:],
    )
    done, out = _invoke(tmp_path, arguments)
    assert done.returncode == 0, done.stdout + done.stderr
    meta = _meta(out)
    assert (meta["arm"], meta["arm_kind"], meta["earlier_verbatim"]) == (
        "V4-set",
        "earlier",
        str(folder),
    )
    assert meta["earlier_ref"] is None and meta["earlier_commit"] is None
    assert meta["arm_launcher"] is None
    assert meta["agents_sha256"] == hashlib.sha256(agents.decode().encode()).hexdigest()
    assert set(meta["arm_files"]) == {
        ".agents/skills/lazy/SKILL.md",
        ".agents/skills/lazy/notes/more.md",
        ".agents/skills/other/SKILL.md",
    }
    prompt = (out / "small-fix.prompt.md").read_text(encoding="utf-8")
    assert prompt.startswith("Task:\n") and "lazy" not in prompt
    repo = Path(meta["fixture_repo"])
    assert (repo / ".agents/skills/lazy/SKILL.md").read_bytes() == skill
    assert (repo / ".agents/skills/lazy/notes/more.md").read_bytes() == note
    assert not (repo / ".agents/skills/using-outcomebound").exists()
    assert not (repo / ".outcomebound").exists()
    raw = (repo / "AGENTS.md").read_bytes()
    assert raw.startswith(agents), "the set's AGENTS.md heads the file, byte for byte"
    assert len(raw) > len(agents) + 20, "the project note stays below it"
    text = raw.decode()
    assert "outcomebound:begin" not in text and "using-outcomebound" not in text
    tracked = subprocess.run(
        ["git", "ls-files", "--", ".agents/skills", "AGENTS.md"],
        cwd=repo,
        capture_output=True,
        text=True,
        env={**os.environ, **HERMETIC_GIT},
        encoding="utf-8",
    ).stdout.split()
    assert sorted(tracked) == sorted([*meta["arm_files"], "AGENTS.md"])
    for name in ("STATUS.json", "INDEX.json"):
        assert '"arm": "V4-set"' in (out / name).read_text(encoding="utf-8"), name
    summary = subprocess.run(
        [sys.executable, str(ROOT / "evals" / "run.py"), "--summary", str(out)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    ).stdout
    assert "small-fix | codex | V4-set | gpt-6-sol medium: PASS 1/1" in summary


def test_the_earlier_verbatim_arm_is_refused_unless_the_set_is_whole(tmp_path: Path) -> None:
    rules, skill = b"Rules.\n", b"One.\n"
    whole = _guidance_set(tmp_path / "whole", {"AGENTS.md": rules, "skills/one/SKILL.md": skill})
    cases = {
        "another arm": (("--arm", "current", "--earlier-verbatim", str(whole)), "earlier arm"),
        "two sources": (
            ("--arm", "earlier", "--earlier-verbatim", str(whole), "--earlier-ref", "HEAD"),
            "name the earlier arm once",
        ),
        "no folder": (("--arm", "earlier", "--earlier-verbatim", str(tmp_path / "none")), "AGENTS"),
        "inside the checkout": (
            ("--arm", "earlier", "--earlier-verbatim", str(ROOT / "evals")),
            "inside this checkout",
        ),
        "no AGENTS.md": (
            (
                *("--arm", "earlier", "--earlier-verbatim"),
                str(_guidance_set(tmp_path / "a", {"skills/a/SKILL.md": skill})),
            ),
            "no non-empty AGENTS.md",
        ),
        "no skills": (
            (
                *("--arm", "earlier", "--earlier-verbatim"),
                str(_guidance_set(tmp_path / "b", {"AGENTS.md": rules})),
            ),
            "no skills/<name>/SKILL.md",
        ),
        "a skill with no SKILL.md": (
            (
                *("--arm", "earlier", "--earlier-verbatim"),
                str(_guidance_set(tmp_path / "c", {"AGENTS.md": rules, "skills/a/n.md": b"N.\n"})),
            ),
            "for a",
        ),
        "a bad label": (
            ("--arm", "earlier", "--arm-label", "a b", "--earlier-ref", "HEAD"),
            "--arm-label",
        ),
    }
    for name, (arguments, message) in cases.items():
        done, out = _invoke(tmp_path, (*arguments, *SMALL_FIX[2:]))
        assert done.returncode != 0 and message in done.stderr, (name, done.stderr)
        assert not out.exists(), f"{name}: a refused run created its directory"
    assert not (tmp_path / "calls.txt").exists(), "a refused run called codex"


def test_the_earlier_ref_carries_an_arbitrary_ref_with_its_own_kernel_and_skills(
    tmp_path: Path,
) -> None:
    """A ref that is no tag and no branch: its kernel text reaches the prompt, a skill it drops
    is not installed (and not pointed at), and a skill folder the engine's list does not name is
    refused in place of being left out. `--arm-label` and the commit are recorded."""

    template = subprocess.run(
        ["git", "-C", str(ROOT), "show", "HEAD:templates/managed-block.agents.md.tmpl"],
        capture_output=True,
        check=True,
    ).stdout
    changed = template.replace(
        b"neither underengineer nor overengineer", b"a variant's own words", 1
    )
    assert changed != template
    # The whole folder of a skill goes, as a variant would drop it.
    tree = subprocess.run(
        ["git", "-C", str(ROOT), "ls-tree", "-r", "--name-only", "HEAD", "skills/sync-tracker"],
        capture_output=True,
        text=True,
        check=True,
        encoding="utf-8",
    ).stdout.split()
    commit = _commit_of(
        {"templates/managed-block.agents.md.tmpl": changed, **dict.fromkeys(tree)}, base="HEAD"
    )
    arguments = (
        *("--arm", "earlier", "--earlier-ref", commit, "--arm-label", "V1-edited"),
        *SMALL_FIX[2:],
    )
    done, out = _invoke(tmp_path, arguments)
    assert done.returncode == 0, done.stdout + done.stderr
    meta = _meta(out)
    assert (meta["arm"], meta["earlier_ref"], meta["earlier_commit"]) == (
        "V1-edited",
        commit,
        commit,
    )
    prompt = (out / "small-fix.prompt.md").read_text(encoding="utf-8")
    assert "a variant's own words" in prompt
    assert not [path for path in meta["arm_files"] if "/sync-tracker/" in path]
    assert any("/diagnose/SKILL.md" in path for path in meta["arm_files"])
    notes = (Path(meta["fixture_repo"]) / "AGENTS.md").read_text(encoding="utf-8")
    assert "diagnose/SKILL.md" in notes and "sync-tracker" not in notes
    stray = _commit_of({"skills/stray/SKILL.md": b"Not in the list.\n"}, base="HEAD")
    done, _ = _invoke(tmp_path, ("--arm", "earlier", "--earlier-ref", stray, *SMALL_FIX[2:]))
    assert done.returncode != 0 and "no install carries: stray" in done.stderr


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
    assert meta["auth"] == "subscription" and meta["cli_version"] == "codex-cli 0.162.1"
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
    assert Path(meta["fixture_repo"]) == tmp_path / "fixtures" / out.name / "small-fix-r1"
    assert (meta["arm_files"], meta["arm_launcher"]) == ({}, None)
    assert not (Path(meta["fixture_repo"]) / ".agents/skills/decision-brief").exists()


def test_NEGATIVE_CONTROL_a_run_whose_codex_reports_another_model_does_not_count(
    tmp_path: Path,
) -> None:
    done, out = _invoke(tmp_path, env={"OB_FAKE_MODEL": "gpt-6-astra"})
    assert done.returncode == 1, done.stdout + done.stderr
    error = "the native session reports model gpt-6-astra, not gpt-6-sol"
    assert _meta(out)["error"] == error


def test_a_preflight_that_observes_no_login_exits_3_before_any_call(tmp_path: Path) -> None:
    done, out = _invoke(tmp_path, env={"OB_FAKE_LOGIN": "Not logged in"})
    assert done.returncode == 3, done.stdout + done.stderr
    status = json.loads((out / "STATUS.json").read_text(encoding="utf-8"))
    assert status["status"] == "UNVERIFIED" and status["auth"] == "not-observed"
    assert not (tmp_path / "argv.txt").exists(), "a failed preflight reached codex exec"


# --- graders the model cannot forge --------------------------------------------------------

RETAG_THE_SEED = "git tag -d seed >/dev/null\ngit tag seed\n"
# A grader written into the workspace, to pass and to leave a mark if anything ever runs it. The
# workspace holds no `checks/` of its own, so the file is one more path out of scope: the
# fixture's scope claim must fail it, and nothing runs it.
REWRITE_THE_GRADER = """mkdir -p checks
cat > checks/scope.sh <<'SH'
#!/usr/bin/env bash
touch grader-ran
echo OK
SH
printf 'helper = 1\\n' > unrelated.py
"""
# The grader in the stage, rewritten during the call. The test gives the run a TMPDIR of its own,
# so the one stage it makes is the one that this finds.
REWRITE_THE_STAGE = """for f in "$TMPDIR"/ob-graders-*/checks/scope.sh; do
  printf '#!/bin/sh\\ntouch grader-ran\\n' > "$f"
done
"""
OUT_OF_SCOPE = 'not allowed: "checks/scope.sh"'
FORGERIES = {
    "grader-written-into-the-workspace": (FIX_THE_DATE + REWRITE_THE_GRADER, OUT_OF_SCOPE),
    "grader-written-committed-then-seed-moved": (
        REWRITE_THE_GRADER + "git add -A\ngit commit -qm tidy\n" + RETAG_THE_SEED + FIX_THE_DATE,
        OUT_OF_SCOPE,
    ),
    "stage-rewritten-during-the-call": (
        FIX_THE_DATE + REWRITE_THE_STAGE,
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
    (tmp_path / "tmp").mkdir()
    done, out = _invoke(tmp_path, action=action, env={"TMPDIR": str(tmp_path / "tmp")})
    assert done.returncode == 0, done.stdout + done.stderr
    meta = _meta(out)
    report = (out / "small-fix.transcript.txt").read_text(encoding="utf-8")
    assert meta["verdict"] == "FAIL" and reason in report, report[-2000:]
    if forgery.startswith("stage"):
        assert meta["claims"] == {} and meta["protected_intact"] is False, meta
    elif forgery.startswith("grader"):
        assert meta["claims"]["only-the-allowed-file-changed"] == "FAIL", meta
    workspace = Path(meta["fixture_repo"])
    assert not (workspace / "grader-ran").exists(), "a rewritten grader was executed"
    tag = subprocess.run(
        ["git", "rev-parse", "refs/tags/seed^{commit}"],
        cwd=workspace,
        capture_output=True,
        text=True,
        env={**os.environ, **HERMETIC_GIT},
        encoding="utf-8",
    ).stdout.strip()
    assert (tag != meta["seed_sha"]) == forgery.endswith("seed-moved")


# --- the hand-off fixtures -----------------------------------------------------------------


def test_specialized_fixtures_run_only_when_named() -> None:
    """New research cases must not increase the default model-call budget."""

    named = [name for name in RUN.fixture_names() if name.startswith(RUN.NAMED_ONLY)]
    assert {"patch-validation", "property-oracles", "testing-no-work"} <= set(named)
    assert {"onboard-plain", "onboard-signals"} <= set(named)
    assert {"lifecycle-stream", "lifecycle-switch"} <= set(named)
    assert {"skill-land-change", "skill-run-acceptance", "skill-sync-tracker"} <= set(named)
    assert {
        "field-commands-hazards",
        "field-docs-only-done",
        "field-docs-only-person",
        "field-goal-person-items",
        "field-order-class",
        "field-parallel-report",
        "field-prompt-and-spec",
        "field-report-gap",
        "field-review-verdict",
        "scaffold-client",
        "scaffold-prototype",
        "scaffold-switch",
    } <= set(named)
    new_project = {
        "new-project-ai",
        "new-project-idea",
        "new-project-skeleton",
        "new-project-small",
        "new-project-spike",
        "new-project-weak",
    }
    assert new_project <= set(named)
    assert RUN.default_fixtures() == [n for n in RUN.fixture_names() if n not in named]
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
        "decision | codex | current | gpt-6-sol medium: PASS 1/2 (1 failed call(s) not counted)",
        f"  {brief}: PASS 1/2",
        "  repetition 1 observed: a Mermaid diagram",
        "  repetition 2 observed: no diagram",
        "decision | codex | earlier | gpt-6-sol medium: PASS 0/1",
        f"  {brief}: PASS 0/1",
    ]
    (tmp_path / "empty").mkdir()
    assert RUN.summarize([tmp_path / "empty"]) == 1


SUMMARY_RUN = {
    "fixture": "synthetic",
    "harness": "codex",
    "arm": "current",
    "model": "named",
    "effort": "medium",
    "error": "",
    "repetition": 1,
    "verdict": "PASS",
    "claims": {"guard": "PASS"},
    "protected_intact": True,
    "observations": [],
    "kernel_sha256": "a",
    "arm_files": {},
    "commit": "a" * 40,
    "dirty": False,
    "tokens_used": 0,
    "grading_files_sha256": "g1",
    "graders_sha256": "s1",
    "thread_id": "one",
}


def _summary(tmp_path: Path, capsys: pytest.CaptureFixture[str], *records: dict) -> list[str]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    for index, record in enumerate(records):
        (tmp_path / f"{index}.meta.json").write_text(json.dumps(record), "utf-8")
    assert RUN.summarize([tmp_path]) == 0
    return capsys.readouterr().out.splitlines()


@pytest.mark.parametrize(
    "changed",
    [
        {"kernel_sha256": "b"},
        {"arm_files": {"a": "1"}},
        {"graders_sha256": "s2"},
        {"grading_files_sha256": "g2"},
        {"graders_sha256": None},
    ],
)
def test_the_summary_never_pools_runs_of_different_instruments(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], changed: dict
) -> None:
    """Different kernels, installed files or graders are different measurements, so each is its
    own group; a field a record does not keep is its own value, equal to no recorded one."""

    other = {**SUMMARY_RUN, **changed, "thread_id": "two"}
    if changed.get("graders_sha256", 1) is None:
        del other["graders_sha256"]
    printed = _summary(tmp_path, capsys, SUMMARY_RUN, other)
    headers = [line for line in printed if line.startswith("synthetic |")]
    assert headers == ["synthetic | codex | current | named medium: PASS 1/1"] * 2, printed
    assert sum(line.startswith("  instrument:") for line in printed) == 2, printed
    assert not any("2/2" in line for line in printed), printed


def test_the_summary_keeps_runs_of_one_instrument_in_one_group_even_without_digests(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bare = {k: v for k, v in SUMMARY_RUN.items() if k not in ("graders_sha256", "arm_files")}
    printed = _summary(tmp_path, capsys, bare, {**bare, "thread_id": "two"})
    assert printed[0] == "synthetic | codex | current | named medium: PASS 2/2", printed
    assert not any(line.startswith("  instrument:") for line in printed), printed


def test_a_regrade_is_an_alternate_measurement_of_its_attempt_and_not_another_attempt(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    original = {**SUMMARY_RUN, "verdict": "FAIL", "claims": {"guard": "FAIL"}}
    regrade = {**SUMMARY_RUN, "regraded_from": "/kept/run"}
    printed = _summary(tmp_path, capsys, original, regrade)
    assert printed[0] == "synthetic | codex | current | named medium: PASS 0/1", printed
    assert "  guard: PASS 0/1" in printed, printed
    assert any(
        "repetition 1" in line and "regrade" in line and "PASS" in line and "FAIL" in line
        for line in printed
    ), printed
    reverse = _summary(tmp_path / "reverse", capsys, regrade, original)
    assert reverse[0] == "synthetic | codex | current | named medium: PASS 0/1", reverse


def test_a_regrade_whose_graders_differ_still_belongs_to_its_original_attempt(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    regrade = {**SUMMARY_RUN, "graders_sha256": "s2", "regraded_from": "/kept/run"}
    printed = _summary(tmp_path, capsys, SUMMARY_RUN, regrade)
    assert [line for line in printed if line.startswith("synthetic |")] == [
        "synthetic | codex | current | named medium: PASS 1/1"
    ], printed


def test_a_regrade_with_no_original_beside_it_is_the_one_measurement_of_its_attempt(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    printed = _summary(tmp_path, capsys, {**SUMMARY_RUN, "regraded_from": "/kept/run"})
    assert printed[0] == "synthetic | codex | current | named medium: PASS 1/1", printed


def test_the_summary_counts_an_attempt_once_by_run_identity_where_no_thread_was_kept(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bare = {**SUMMARY_RUN, "thread_id": None, "run_id": "r1"}
    printed = _summary(
        tmp_path,
        capsys,
        bare,
        {**bare, "verdict": "FAIL", "regraded_from": "/kept/run"},
        {**bare, "run_id": "r2", "repetition": 2},
    )
    assert printed[0] == "synthetic | codex | current | named medium: PASS 2/2", printed


def test_two_copies_of_one_original_attempt_count_once(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    printed = _summary(tmp_path, capsys, SUMMARY_RUN, SUMMARY_RUN)
    assert printed[0] == "synthetic | codex | current | named medium: PASS 1/1", printed
    assert any("not counted" in line for line in printed), printed


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
        "small-fix | codex | current | gpt-6-sol medium: PASS 3/3",
        "  median tokens 200, seconds 20",
    ]


@needs_posix_bash
@pytest.mark.parametrize("arm", ["current", "none"])
def test_an_install_leaves_a_fixtures_uncommitted_edits_uncommitted(
    tmp_path: Path, arm: str
) -> None:
    """dirty-review's setup leaves someone else's edits uncommitted and records `git status` as
    its baseline; folding the install into the seed must commit only the notes it wrote, or the
    current arm starts from a clean tree and its worktree check fails whatever the model does."""

    loaded = RUN.load_arm(arm, RUN.selected_fragments("dirty-review"))
    workdir = tmp_path / "w"
    workdir.mkdir()
    RUN.install(workdir, loaded.files)
    env = {**RUN.child_env(), **RUN.HERMETIC_GIT, "OB_EVAL_ARM": arm}
    fixture = RUN.FIXTURES / "dirty-review"
    stage = tmp_path / "stage"
    stage.mkdir()
    subprocess.run(
        ["bash", str(fixture / "setup.sh"), str(workdir), str(stage)],
        check=True,
        env=env,
        capture_output=True,
        timeout=120,
    )
    assert RUN.as_installed(workdir, loaded) == ""
    status = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=workdir,
        capture_output=True,
        text=True,
        env=env,
        check=True,
        encoding="utf-8",
    ).stdout
    assert status == (stage / "checks" / "baseline-status").read_text(encoding="utf-8")
    assert not (workdir / "checks").exists()


def test_missing_observed_model_does_not_count_as_requested_model():
    assert RUN.call_error(0, "Finished", {"model_observed": None}, "requested")
    assert RUN.call_error(0, "Finished", {"model_observed": "requested"}, "requested") == ""


@pytest.mark.parametrize("new_session", [False, True])
def test_bounded_command_keeps_partial_output_and_stops_descendant(
    tmp_path, new_session, monkeypatch
):
    from tests.processes import running

    if Path("/proc/self/stat").is_file():
        monkeypatch.setenv("PATH", str(tmp_path / "no-external-tools"))
    child_pid = tmp_path / "child.pid"
    code = (
        "import subprocess, sys, time; "
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'], "
        f"start_new_session={new_session}); "
        f"open({str(child_pid)!r}, 'w').write(str(child.pid)); "
        "print('partial evidence', flush=True); time.sleep(60)"
    )
    with pytest.raises(subprocess.TimeoutExpired) as caught:
        RUN.bounded_command([sys.executable, "-c", code], timeout=5)
    assert "partial evidence" in caught.value.output
    import time

    pid = int(child_pid.read_text(encoding="utf-8"))
    # A killed process ends only when it leaves the kernel; on a loaded runner a process in an
    # uninterruptible disk wait takes longer, so the bound is wide and the state is reported.
    deadline = time.monotonic() + 60
    while running(pid) and time.monotonic() < deadline:
        time.sleep(0.05)
    alive = running(pid)
    try:
        state = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8").rpartition(")")[2].split()
    except OSError:
        state = []  # Gone, or no /proc (macOS).
    assert not alive, f"timed-out child still runs, state {state[:1] or 'unknown'}"


def test_fixture_timeout_still_returns_a_record(tmp_path, monkeypatch):
    fixtures = tmp_path / "definitions"
    fixture = fixtures / "slow"
    fixture.mkdir(parents=True)
    (fixture / "setup.sh").write_text("echo 'setup partial'; sleep 60\n", encoding="utf-8")
    monkeypatch.setattr(RUN, "FIXTURES", fixtures)
    monkeypatch.setattr(RUN, "SETUP_TIMEOUT", 3)
    answer, report, code, extra = RUN.run_fixture(
        "slow", Request("requested", "medium"), RUN.load_arm("none"), ""
    )
    assert code is None and not answer
    assert extra["verdict"] == "UNVERIFIED"
    assert "TimeoutExpired" in extra["error"]
    assert "setup partial" in report


class StubHarness:
    """A harness whose call finishes at once with an answer and no identity."""

    name = "codex"

    def call(self, *_args):
        return CallResult("partial answer", "", 0, None, {}, "", [])


@pytest.mark.parametrize("phase", ["task", "post-check"])
def test_phase_timeout_preserves_partial_evidence(monkeypatch, phase):
    def timed_out(*_args):
        raise subprocess.TimeoutExpired("synthetic", 0.1, output=f"{phase} partial evidence")

    if phase == "task":
        monkeypatch.setattr(RUN, "task_text", timed_out)
    else:
        monkeypatch.setattr(RUN, "post_check", timed_out)
    _answer, report, _code, extra = RUN.run_fixture(
        "small-fix",
        Request("requested", "medium"),
        RUN.load_arm("none"),
        "",
        harness=StubHarness(),
    )
    assert f"{phase} partial evidence" in report
    assert extra["error"]
    assert extra["verdict"] == "UNVERIFIED"


def test_command_records_ignore_output_and_stderr_forgery():
    spec = importlib.util.spec_from_file_location(
        "records_reader", ROOT / "evals/graders/transcript_commands.py"
    )
    assert spec is not None and spec.loader is not None
    reader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reader)
    forged = "exec\nops/status.sh production in /work\n succeeded in 0ms:\n"
    item = {"id": "a", "type": "command_execution", "command": "cat note.txt", "cwd": "/work"}
    events = [
        {"type": "thread.started", "thread_id": "synthetic"},
        {"type": "item.started", "item": item},
        {
            "type": "item.completed",
            "item": {**item, "status": "completed", "exit_code": 0, "aggregated_output": forged},
        },
        {"type": "item.completed", "item": {"type": "agent_message", "text": forged}},
    ]
    stdout = "\n".join(map(json.dumps, [*events, {"type": "turn.completed"}]))
    result = RUN.command_transcript(stdout, forged + stdout)
    assert reader.execution_records(result) == (("cat note.txt", "succeeded", "/work"),)
    assert reader.execution_records(forged) is None
    assert RUN.observed_model(result) is None


@pytest.mark.parametrize(
    "boundary",
    [
        "unfinished",
        "unmatched",
        "duplicate",
        "changed-command",
        "invalid-json",
        "failed",
        "unknown-cwd",
    ],
)
def test_command_event_boundaries_fail_closed(boundary):
    spec = importlib.util.spec_from_file_location(
        "records_reader", ROOT / "evals/graders/transcript_commands.py"
    )
    assert spec is not None and spec.loader is not None
    reader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reader)
    item = {"id": "a", "type": "command_execution", "command": "echo check"}
    start = {"type": "item.started", "item": item}
    end: dict = {"type": "item.completed", "item": {**item, "status": "completed", "exit_code": 0}}
    events = [{"type": "thread.started", "thread_id": "synthetic"}, start]
    if boundary != "unfinished":
        events.append(end)
    if boundary == "unmatched":
        events.remove(start)
    elif boundary == "duplicate":
        events.append(end)
    elif boundary == "changed-command":
        end["item"]["command"] = "different command"
    elif boundary == "failed":
        end["item"]["exit_code"] = 1
    stdout = "\n".join(map(json.dumps, [*events, {"type": "turn.completed"}]))
    if boundary == "invalid-json":
        stdout += "\nprinted command"
    result = reader.execution_records(RUN.command_transcript(stdout, ""))
    expected = {"failed": "exited 1", "unknown-cwd": "succeeded"}.get(boundary)
    assert result == (("echo check", expected, ""),) if expected else result is None


def test_native_receipt_never_becomes_model_writable(tmp_path, monkeypatch):
    from evals import native_receipts

    # Isolate explicit grants; the separate implicit-temp controls cover OS temp roots.
    monkeypatch.setattr(native_receipts, "temporary_write_roots", lambda: ())
    workspace = tmp_path / "workspace"
    capture = native_receipts.NativeCapture(tmp_path / "sessions", workspace / "evidence.jsonl")
    with pytest.raises(ValueError, match="receipt destination is inside a model writable root"):
        capture.check_roots((workspace,))
    assert not capture.destination.exists()


def test_failed_login_output_does_not_authorize_a_model_call(tmp_path):
    done, out = _invoke(tmp_path, env={"OB_FAKE_LOGIN_EXIT": "1"})
    assert done.returncode == RUN.PREFLIGHT_EXIT
    assert not (out / "small-fix.meta.json").exists()
    assert not any(
        line.startswith("exec ")
        for line in (tmp_path / "calls.txt").read_text(encoding="utf-8").splitlines()
    )


def test_native_receipt_source_cannot_overlap_model_writable_roots(tmp_path, monkeypatch):
    from evals import native_receipts

    monkeypatch.setattr(native_receipts, "temporary_write_roots", lambda: ())
    workspace = tmp_path / "workspace"
    capture = native_receipts.NativeCapture(workspace / "sessions", tmp_path / "copy.jsonl")
    with pytest.raises(ValueError, match="sessions directory overlaps"):
        capture.check_roots((workspace,))


@pytest.mark.parametrize("kind", ["mcp_tool_call", "custom_tool_call", "future_tool", None])
def test_unknown_cli_tool_items_do_not_prove_no_commands(kind):
    events = [
        {"type": "thread.started", "thread_id": "synthetic", "model": "named"},
        {"type": "item.completed", "item": {"type": kind}},
        {"type": "turn.completed"},
    ]
    transcript = RUN.command_transcript("\n".join(map(json.dumps, events)), "")
    assert json.loads(transcript)["commands"] is None
    assert RUN.observed_model(transcript) is None


def test_conflicting_actual_model_events_do_not_qualify_identity():
    events = [
        {"type": "thread.started", "thread_id": "synthetic", "model": "first"},
        {"type": "turn.started", "model": "different"},
        {"type": "turn.completed"},
    ]
    transcript = RUN.command_transcript("\n".join(map(json.dumps, events)), "")
    assert RUN.observed_model(transcript) is None


def test_unknown_top_level_execution_form_is_not_an_empty_command_record():
    events = [
        {"type": "thread.started", "thread_id": "synthetic", "model": "named"},
        {"type": "custom_tool_call", "name": "exec", "input": "uninterpreted code"},
        {"type": "turn.completed"},
    ]
    transcript = RUN.command_transcript("\n".join(map(json.dumps, events)), "")
    assert json.loads(transcript)["commands"] is None
    assert RUN.call_error(0, "done", {"model_observed": RUN.observed_model(transcript)}, "named")


# --- command directories from the native session, and judging kept runs again --------------


def _saved(out: Path, fixture: str = "small-fix") -> dict:
    """The command-events document at the head of a run's saved transcript."""

    text = (out / f"{fixture}.transcript.txt").read_text(encoding="utf-8")
    return json.loads(text.split("\n--- post-checks ---\n", 1)[0])


def _directories(out: Path) -> list[str]:
    return [row[2] for row in _saved(out)["commands"]]


@pytest.mark.parametrize("mode", ["exact", "workdir"])
def test_a_command_takes_its_directory_from_the_native_session_even_where_it_is_not_the_cwd(
    tmp_path: Path, mode: str
) -> None:
    """The 0.162.1 stream gives no directory; the native session gives each command's own."""

    done, out = _invoke(tmp_path, env={"OB_FAKE_NATIVE_COMMANDS": mode})
    assert done.returncode == 0, done.stdout + done.stderr
    meta = _meta(out)
    workspace = Path(meta["fixture_repo"]).resolve()
    assert meta["command_cwd_source"] == "native" and meta["command_native_disagreements"] == []
    assert _directories(out) == [
        str(workspace / "sub") if mode == "workdir" else str(workspace),
        str(workspace),
    ]


@pytest.mark.parametrize(
    ("mode", "reason"),
    [
        ("count", "none: the stream has 2 commands, the native session 1"),
        ("text", "none: the native commands do not match the stream's by text"),
    ],
)
def test_NEGATIVE_CONTROL_a_native_session_that_does_not_match_the_stream_fills_nothing(
    tmp_path: Path, mode: str, reason: str
) -> None:
    done, out = _invoke(tmp_path, env={"OB_FAKE_NATIVE_COMMANDS": mode})
    assert done.returncode == 0, done.stdout + done.stderr
    assert _meta(out)["command_cwd_source"] == reason
    assert _directories(out) == ["", ""], "a directory was filled without an exact match"


def _regrade(source: Path, target: Path, capsys: pytest.CaptureFixture[str]) -> tuple[int, str]:
    code = RUN._main(["--regrade", str(source), "--out", str(target)])
    return code, capsys.readouterr().err


def test_a_kept_run_is_judged_again_with_no_model_call_and_keeps_its_observed_identity(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    done, out = _invoke(tmp_path, env={"OB_FAKE_NATIVE_COMMANDS": "exact"})
    assert done.returncode == 0, done.stdout + done.stderr
    original = _meta(out)
    calls = (tmp_path / "calls.txt").read_text(encoding="utf-8")
    new = out.parent / "regraded"
    assert _regrade(out, new, capsys)[0] == 0
    assert (tmp_path / "calls.txt").read_text(encoding="utf-8") == calls, "a call was made"
    meta = _meta(new)
    assert meta["regraded_from"] == str(out)
    assert (meta["verdict"], meta["claims"]) == (original["verdict"], original["claims"])
    assert meta["observed"] == original["observed"] and meta["thread_id"] == original["thread_id"]
    assert meta["workspace_unchanged"] == "PASS" == meta["grading_files_unchanged"]
    assert meta["protected_check"] == "PASS" and meta["command_cwd_source"] == "native"
    assert meta["post_check_log_dir"] != original["post_check_log_dir"]
    assert _directories(new) == _directories(out) != ["", ""]
    assert (new / "small-fix.native.jsonl").read_bytes() == (
        out / "small-fix.native.jsonl"
    ).read_bytes()
    rows = json.loads((new / "INDEX.json").read_text(encoding="utf-8"))
    assert [(row["fixture"], row["harness"], row["verdict"]) for row in rows] == [
        ("small-fix", "codex", original["verdict"])
    ]
    assert RUN.summarize([new]) == 0


def test_a_run_from_before_digests_were_kept_is_judged_again_and_says_what_is_unverified(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The pass this was built for kept no digest, no protected snapshot and no directories."""

    done, out = _invoke(tmp_path, env={"OB_FAKE_NATIVE_COMMANDS": "workdir"})
    assert done.returncode == 0, done.stdout + done.stderr
    path = out / "small-fix.meta.json"
    old = _meta(out)
    for key in ("workspace_sha256", "grading_files_sha256", "protected_snapshot"):
        del old[key]
    path.write_text(json.dumps(old), encoding="utf-8")
    document = _saved(out)
    for row in document["commands"]:
        row[2] = ""
    saved = out / "small-fix.transcript.txt"
    after = saved.read_text(encoding="utf-8").split("\n--- post-checks ---\n", 1)[1]
    saved.write_text(json.dumps(document) + "\n--- post-checks ---\n" + after, encoding="utf-8")
    new = out.parent / "regraded"
    assert _regrade(out, new, capsys)[0] == 0
    meta = _meta(new)
    assert meta["workspace_unchanged"] == "UNVERIFIED" == meta["grading_files_unchanged"]
    assert meta["protected_check"] == "UNVERIFIED" and meta["verdict"] == "PASS"
    assert meta["command_cwd_source"] == "native" and "" not in _directories(new)
    assert meta["workspace_sha256"], "a digest is kept from here on"


@pytest.mark.parametrize(
    "what", ["workspace", "grading-files", "sealed-graders", "native-copy", "no-workspace"]
)
def test_NEGATIVE_CONTROL_a_run_whose_evidence_changed_is_refused_and_nothing_is_written(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], what: str
) -> None:
    done, out = _invoke(tmp_path, env={"OB_FAKE_NATIVE_COMMANDS": "exact"})
    assert done.returncode == 0, done.stdout + done.stderr
    meta = _meta(out)
    workspace = Path(meta["fixture_repo"])
    if what == "workspace":
        (workspace / "added-later.txt").write_text("x", encoding="utf-8")
    elif what == "grading-files":
        # A run with no sealed copy is judged with this checkout's files, which must be its own.
        del meta["graders_sha256"]
        meta["grading_files_sha256"] = "0" * 64
        (out / "small-fix.meta.json").write_text(json.dumps(meta), encoding="utf-8")
    elif what == "sealed-graders":
        (out / "small-fix.graders" / "post.plan.json").write_text("{}\n", encoding="utf-8")
    elif what == "native-copy":
        (out / "small-fix.native.jsonl").write_bytes(b'{"type":"x"}\n')
    else:
        shutil.rmtree(workspace)
    new = out.parent / "regraded"
    code, error = _regrade(out, new, capsys)
    assert code == 2 and "refused small-fix" in error, error
    assert not new.exists()
