"""`outcomebound review council`: the plan runs nothing, the accepted run starts each reviewer
read-only against a snapshot with the data quoted, a reviewer that fails is reported while the rest
go on, a reviewer's own `Reviewed:` and `Disposition:` lines are dropped, every citation is looked
up at the reviewed revision, and the file that results is one `review check` and `review since`
read. The reviewers are stand-in `codex` and `claude` programs on PATH: no test starts a real one,
and a test that would find a real one fails first."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from outcomebound_tools import programs, review_check, review_council
from tests.fake_tools import shell_tool
from tests.portable import WINDOWS, needs_symlinks

ROOT = Path(__file__).resolve().parent.parent
IDENTITY = ("-c", "user.name=T", "-c", "user.email=t@example.test", "-c", "commit.gpgsign=false")

CODEX = """#!/bin/sh
log="$FAKE_LOG"
printf '%s\\n' "$@" > "$log/codex.argv"
printf 'CODEX_HOME=%s\\n' "${CODEX_HOME-(unset)}" > "$log/codex.env"
cat > "$log/codex.stdin"
pwd > "$log/codex.cwd"
cp src/app.py "$log/codex.snapshot"
ls -A > "$log/codex.ls"; ls -A .claude 2>&1 > "$log/codex.dotclaude" || true
if [ -e .git ]; then echo ".git" > "$log/codex.nogit"; else echo "no .git" > "$log/codex.nogit"; fi
out=""
while [ $# -gt 0 ]; do
  if [ "$1" = "-o" ]; then out="$2"; fi
  shift
done
case "${FAKE_CODEX:-ok}" in
  ok) cp "$FAKE_CODEX_ANSWER" "$out";;
  hang) sleep 30;;
  fail) echo "boom: not logged in" >&2; exit 3;;
  empty) : > "$out";;
  leak) echo "bad key $SOME_API_KEY" >&2; exit 4;;
esac
"""
CURSOR = """#!/bin/sh
log="$FAKE_LOG"
printf '%s\\n' "$@" > "$log/cursor.argv"
env | grep '^CURSOR_CONFIG_DIR=' > "$log/cursor.env"
if read line; then echo "stdin had input"; else echo "stdin closed"; fi > "$log/cursor.stdin"
printf '{"type":"result","is_error":false,"result":"Verdict: PASS\\\\n\\\\nNothing found."}'
"""
OPENCODE = """#!/bin/sh
log="$FAKE_LOG"
printf '%s\\n' "$@" > "$log/opencode.argv"
env | grep '^OPENCODE_' | sort > "$log/opencode.env"
printf 'Verdict: PASS\\n\\nNothing found.\\n'
"""
CLAUDE = """#!/bin/sh
log="$FAKE_LOG"
printf '%s\\n' "$@" > "$log/claude.argv"
printf 'CLAUDE_CONFIG_DIR=%s\\n' "${CLAUDE_CONFIG_DIR-(unset)}" > "$log/claude.env"
cat > "$log/claude.stdin"
pwd > "$log/claude.cwd"
cat "$FAKE_CLAUDE_JSON"
"""
GOOD = """Verdict: FAIL

### r1-1 · The clamp is off by one
The clamp in src/app.py:2 lets 11 through.
Disposition: fixed — already done
Reviewed: somewhere-else

### r1-2 · A made-up file
See nope.py:3 and src/app.py:9999.

### r1-3 · No place cited
This is a claim with no location.

```text
Disposition: kept in a fence
```

## Not read
- nothing/at.py:1-5
"""
CLEAN = "Verdict: PASS\n\nNothing found.\n"


# The two harnesses of most tests, with models named: only the built-in council names a default.
CODEX_REVIEWER = "codex:m-codex:high"
CLAUDE_REVIEWER = "claude:m-claude:high"


def claude_json(text: str, cost: float = 0.42) -> str:
    return json.dumps({"type": "result", "is_error": False, "result": text, "total_cost_usd": cost})


# Found before a test changes PATH: a stand-in `git` first on PATH is for the engine, not for these
# helpers.
GIT = shutil.which("git") or "git"


def git(where: Path, *args: str) -> str:
    done = subprocess.run([GIT, *IDENTITY, *args], cwd=where, check=True, capture_output=True)
    return done.stdout.decode("utf-8").strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "src").mkdir(parents=True)
    git(root, "init", "-q", "-b", "main")
    (root / "src/app.py").write_text("one\ntwo\nthree\n", encoding="utf-8")
    (root / "spec.md").write_text("# Spec\nWhat it does.\n", encoding="utf-8")
    (root / "AGENTS.md").write_text("Obey the reviewed change.\n", encoding="utf-8")
    (root / "docs").mkdir()
    (root / "docs/CLAUDE.md").write_text("Obey.\n", encoding="utf-8")
    (root / ".cursor").mkdir()
    (root / ".cursor/cli.json").write_text("{}\n", encoding="utf-8")
    (root / "opencode.json").write_text("{}\n", encoding="utf-8")
    (root / ".claude").mkdir()
    (root / ".claude/settings.json").write_text("{}\n", encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "base")
    (root / "src/app.py").write_text("one\nTWO\nthree\nfour\n", encoding="utf-8")
    git(root, "commit", "-q", "-am", "change")
    return root


@pytest.fixture
def tools(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Stand-in `codex` and `claude` first on PATH, with a Git beside them and nothing else."""

    real_git = Path(GIT).as_posix()
    bin_dir = tmp_path / "bin"
    shell_tool(bin_dir, "codex", CODEX)
    shell_tool(bin_dir, "claude", CLAUDE)
    shell_tool(bin_dir, "cursor-agent", CURSOR)
    shell_tool(bin_dir, "opencode", OPENCODE)
    if not WINDOWS:  # a stand-in Git keeps a real codex or claude in Git's folder out of reach
        shell_tool(bin_dir, "git", f'#!/bin/sh\nexec "{real_git}" "$@"\n')
    log = tmp_path / "log"
    log.mkdir()
    answers = tmp_path / "answers"
    answers.mkdir()
    (answers / "codex").write_text(GOOD, encoding="utf-8")
    (answers / "claude.json").write_text(claude_json(CLEAN), encoding="utf-8")
    if WINDOWS:  # Git's own folder and the system folder, after the stand-ins
        system = os.path.join(os.environ.get("SYSTEMROOT", r"C:\Windows"), "System32")
        path = [str(bin_dir), str(Path(GIT).parent), system]
    else:
        path = [str(bin_dir), "/usr/bin", "/bin"]
    monkeypatch.setenv("PATH", os.pathsep.join(path))
    monkeypatch.setenv("FAKE_LOG", str(log))
    monkeypatch.setenv("FAKE_CODEX_ANSWER", str(answers / "codex"))
    monkeypatch.setenv("FAKE_CLAUDE_JSON", str(answers / "claude.json"))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    # The account the reviewers start with comes from the test alone: no key, no account folder
    # and no council file of the person running the suite.
    for row in review_council.load_table()["harnesses"].values():
        account = row.get("account", {})
        routes = account.get("routes", {})
        for name in [
            account.get("home", ""),
            *account.get("presence", []),
            *routes.get("shown", []),
            *routes.get("refused", []),
        ]:
            monkeypatch.delenv(name, raising=False)
        for name in account.get("values", []):
            monkeypatch.delenv(name, raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    (tmp_path / "home").mkdir(exist_ok=True)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    for name in ("codex", "claude", "cursor-agent", "opencode"):
        assert Path(programs.find(name) or "").parent == bin_dir, f"a real {name} would run"
    return tmp_path


def council(
    capsys: pytest.CaptureFixture[str], repo: Path, *args: str, pair: bool = True
) -> tuple[int, str, str]:
    """Run the verb; with `pair`, and no reviewer named, the two harnesses at their defaults."""

    if pair and "--reviewer" not in args:
        args = (*args, "--reviewer", CODEX_REVIEWER, "--reviewer", CLAUDE_REVIEWER)
    if "--accept" in args and "--plan-id" not in args:
        # The person saw the plan first: take its id, as `--accept` requires.
        review_council.main(
            ["--root", str(repo), *("--plan" if a == "--accept" else a for a in args)]
        )
        shown = re.search(r"plan id: ([0-9a-f]{12})", capsys.readouterr().out)
        if shown:
            args = (*args, "--plan-id", shown.group(1))
    code = review_council.main(["--root", str(repo), *args])
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_plan_names_each_reviewer_its_argv_and_safeguards_and_runs_nothing(
    tools: Path, repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code, out, _ = council(capsys, repo, "--plan", "--base", "HEAD~1", "--budget-usd", "3")
    assert code == 0
    assert "COUNCIL PLAN (nothing has run)" in out
    assert "spends the person's credits" in out
    assert "reviewers from: --reviewer on the command line" in out
    assert f"reviewer r1: {CODEX_REVIEWER}" in out and f"reviewer r2: {CLAUDE_REVIEWER}" in out
    assert "-s read-only" in out and "--ignore-user-config" in out
    assert "--ephemeral" not in out, "the session is kept, so a usage tool counts its tokens"
    assert "--restricted" in out and "--tools Read,Grep,Glob" in out
    assert "--permission-mode dontAsk" in out and "--max-budget-usd 3" in out
    assert "timeout: 1800 s" in out
    assert "UNVERIFIED" in out
    # It started no program and made no folder.
    assert list((tools / "log").iterdir()) == []
    assert not (repo / ".agents").exists()


def test_the_budget_flag_is_in_the_argv_only_when_given(
    tools: Path, repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _, out, _ = council(capsys, repo, "--plan", "--base", "HEAD~1")
    assert "--max-budget-usd" not in out


def test_a_reviewer_is_harness_model_effort_with_defaults_for_a_missing_part() -> None:
    table = review_council.load_table()
    assert review_council.parse_reviewer("codex:m-9:low", 3, table).label == "codex:m-9:low"
    # The built-in council names one reviewer; a bare harness takes its model and effort.
    assert table["default_council"] == ["codex:gpt-6-astra:high"]
    assert review_council.parse_reviewer("codex", 1, table).label == "codex:gpt-6-astra:high"
    assert review_council.parse_reviewer("codex::max", 1, table).label == "codex:gpt-6-astra:max"
    with pytest.raises(review_council.CouncilError, match="no default"):
        review_council.parse_reviewer("claude", 1, table)
    # A model with no effort leaves the tool's own effort.
    assert review_council.parse_reviewer("claude:m-1", 1, table).label == "claude:m-1"
    for bad in ("", "gemini:x", "codex:--dangerously-bypass", "codex:m:e:x", "codex:a b"):
        with pytest.raises(review_council.CouncilError):
            review_council.parse_reviewer(bad, 1, table)


def test_accept_runs_each_reviewer_read_only_on_a_snapshot_with_the_diff_as_data(
    tools: Path, repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code, out, _ = council(
        capsys, repo, "--accept", "--base", "HEAD~1", "--lens", "off-by-one cases"
    )
    assert code == 0, out
    log = tools / "log"
    run = repo / ".agents/work/council" / git(repo, "rev-parse", "HEAD")[:12]
    codex_argv = (log / "codex.argv").read_text("utf-8").split("\n")
    assert codex_argv[:3] == ["exec", "-s", "read-only"]
    assert codex_argv[-2] == "-"  # the prompt comes from standard input, which is a file and ends
    snapshot = codex_argv[codex_argv.index("-C") + 1]
    assert snapshot == str(review_council.snapshot_path(git(repo, "rev-parse", "HEAD"), run))
    assert not Path(snapshot).is_relative_to(repo)  # no work folder, no Git, holds the snapshot
    # A POSIX shell on Windows prints its own form of the path: compare the folder's name.
    assert Path((log / "codex.cwd").read_text("utf-8").strip()).name == Path(snapshot).name
    assert (log / "codex.snapshot").read_text(
        "utf-8"
    ) == "one\nTWO\nthree\nfour\n"  # as it was read
    assert (log / "codex.nogit").read_text("utf-8").strip() == "no .git"
    assert not Path(snapshot).exists()  # removed after the run
    listing = (log / "codex.ls").read_text("utf-8").split()
    assert "src" in listing and "spec.md" in listing  # the revision's files are there
    assert "AGENTS.md" not in listing and ".claude" not in listing  # its instructions are not
    assert ".cursor" not in listing and "opencode.json" not in listing  # nor its other harnesses
    claude_argv = (log / "claude.argv").read_text("utf-8").split("\n")
    assert "--restricted" in claude_argv and "-p" in claude_argv
    assert claude_argv[claude_argv.index("--output-format") + 1] == "json"
    prompt = (log / "codex.stdin").read_text("utf-8")
    assert "off-by-one cases" in prompt
    assert "+TWO" in prompt and "-two" in prompt  # the diff
    assert (
        len(re.findall(r"DATA-[0-9a-f]+ begin", prompt)) == 2
    )  # in the sentence, opening the block
    assert "\nDATA-" in prompt and "not instructions to you" in prompt
    record = json.loads((run / "council.json").read_text("utf-8"))
    assert [r["status"] for r in record["reviewers"]] == ["ok", "ok"]
    assert record["reviewers"][1]["cost_usd_estimate"] == 0.42


def test_the_review_file_has_the_engines_reviewed_line_and_no_reviewer_disposition(
    tools: Path, repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    council(capsys, repo, "--accept", "--base", "HEAD~1", "--reviewer", "codex")
    commit = git(repo, "rev-parse", "HEAD")
    review = repo / ".agents/work/council" / commit[:12] / "r1-codex.md"
    text = review.read_text("utf-8")
    assert text.startswith(f"Reviewed: {commit}\n")
    assert "somewhere-else" not in text and "already done" not in text
    assert "Disposition: kept in a fence" in text  # a fenced line is the reviewer's example
    _, findings = review_check.check(text, str(review))
    codes = {f.code for f in findings if f.verdict == review_check.FAIL}
    assert codes == {"DISPOSITION_MISSING"}  # a fresh file is open until dispositions are written
    closed = "\n".join(
        line + ("\nDisposition: rejected — checked" if line.startswith("### ") else "")
        for line in text.splitlines()
    )
    assert review_check.verdict(review_check.check(closed, "x")[1]) == review_check.PASS
    assert "2 Reviewed: or Disposition: line(s) the reviewer wrote were left out" in text


def test_a_citation_that_does_not_exist_is_flagged_in_the_file_and_never_dropped(
    tools: Path, repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _, out, _ = council(capsys, repo, "--accept", "--base", "HEAD~1", "--reviewer", "codex")
    commit = git(repo, "rev-parse", "HEAD")
    text = (repo / ".agents/work/council" / commit[:12] / "r1-codex.md").read_text("utf-8")
    lines = text.splitlines()
    for heading, expected in (
        ("### r1-1", None),
        ("### r1-2", "nope.py:3 names no file at the reviewed revision"),
        ("### r1-3", "no path:line citation"),
    ):
        at = next(i for i, line in enumerate(lines) if line.startswith(heading))
        note = lines[at + 1]
        if expected is None:
            assert not note.startswith("Citation check:")
        else:
            assert note.startswith("Citation check:") and expected in note
    assert "src/app.py:9999 is past the end of src/app.py (4 lines)" in text
    assert "nope.py:3" in text and "The clamp in src/app.py:2" in text  # every word stays
    assert "nothing/at.py:1-5 names no file" not in text  # the list of what was not read
    assert "3 citation problem(s) of 3 citation(s)" in out


def test_the_existing_citation_of_a_named_file_checks_against_the_text_given(
    tools: Path, repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (repo / "spec.md").write_text(
        "# Spec\nOne\nTwo\nThree\nFour\n", encoding="utf-8"
    )  # uncommitted
    answer = "Verdict: UNVERIFIED\n\n### r1-1 · Gap\nspec.md:5 says four.\n"
    (tools / "answers/codex").write_text(answer, encoding="utf-8")
    code, out, _ = council(capsys, repo, "--accept", "--file", "spec.md", "--reviewer", "codex")
    assert code == 0, out
    prompt = (tools / "log/codex.stdin").read_text("utf-8")
    assert "    5| Four" in prompt  # line numbers added to a named file
    review = next((repo / ".agents/work/council").glob("*/r1-codex.md")).read_text("utf-8")
    assert "Citation check" not in review  # line 5 exists in the file as given, not at the commit


def test_a_failed_a_timed_out_and_an_unreadable_reviewer_are_reported_and_the_rest_go_on(
    tools: Path,
    repo: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Only the hanging reviewer gets the short limit: a reviewer that fails at once must not be
    # timed out by a loaded machine's start-up time.
    cases = {
        "fail": ("FAILED", "exit 3: boom: not logged in", "60"),
        "empty": ("FAILED", "its answer file is empty", "60"),
        "hang": ("TIMEOUT", "killed after 1 s", "1"),
    }
    for number, (mode, (status, detail, limit)) in enumerate(cases.items()):
        monkeypatch.setenv("FAKE_CODEX", mode)
        out_dir = tools / f"run{number}"
        code, out, _ = council(
            capsys, repo, "--accept", "--base", "HEAD~1", "--timeout", limit, "--out", str(out_dir)
        )
        assert code == 1
        assert f"r1 {CODEX_REVIEWER}: {status} after" in out and detail in out
        assert "r2 claude" in out and ": ok in" in out  # the other reviewer finished
        assert (out_dir / "r2-claude.md").is_file()
        assert not (out_dir / "r1-codex.md").exists()  # no file that would read as a clean review
    (tools / "answers/codex").write_text("Verdict: FAIL\n\nIt is broken.\n", encoding="utf-8")
    monkeypatch.setenv("FAKE_CODEX", "ok")
    code, out, _ = council(
        capsys, repo, "--accept", "--base", "HEAD~1", "--out", str(tools / "run8")
    )
    assert code == 1 and "UNREADABLE" in out and "names no finding" in out
    assert not (tools / "run8/r1-codex.md").exists()
    (tools / "answers/codex").write_text("I cannot help with that.\n", encoding="utf-8")
    monkeypatch.setenv("FAKE_CODEX", "ok")
    code, out, _ = council(
        capsys, repo, "--accept", "--base", "HEAD~1", "--out", str(tools / "run9")
    )
    assert code == 1 and "UNREADABLE" in out
    assert (tools / "run9/r1-codex.raw.txt").is_file()
    assert not (tools / "run9/r1-codex.md").exists()


def test_a_missing_program_is_a_reported_failure(
    tools: Path,
    repo: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for stand_in in (tools / "bin").glob("claude*"):
        stand_in.unlink()
    assert programs.find("claude") is None
    code, out, _ = council(capsys, repo, "--accept", "--base", "HEAD~1")
    assert code == 1
    assert f"r2 {CLAUDE_REVIEWER}: FAILED" in out and "not on PATH" in out
    assert "r1 codex" in out and ": ok in" in out


def test_an_existing_run_folder_is_refused_and_nothing_starts(
    tools: Path, repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tools / "taken").mkdir()
    code, _, err = council(
        capsys, repo, "--accept", "--base", "HEAD~1", "--out", str(tools / "taken")
    )
    assert code == 1 and "COUNCIL_REFUSED" in err and "exists" in err
    assert list((tools / "log").iterdir()) == []


def test_a_range_a_base_or_a_file_must_be_named_and_a_bad_ref_is_refused(
    tools: Path, repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    for args, word in (
        ((), "name what to review"),
        (("--range", "HEAD~1..HEAD", "--base", "HEAD~1"), "not both"),
        (("--range", "nowhere..HEAD"), "does not resolve"),
        (("--range", "HEAD~1"), "two refs"),
        (("--base=-x",), "does not resolve"),
        (("--file", "../escape.md"), "no file inside"),
        (("--file", "missing.md"), "no file inside"),
    ):
        code, _, err = council(capsys, repo, "--plan", *args)
        assert code == 1 and word in err, (args, err)


def test_the_range_diff_is_quoted_as_data(
    tools: Path, repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    council(capsys, repo, "--accept", "--range", "HEAD~1..HEAD", "--reviewer", "codex")
    prompt = (tools / "log/codex.stdin").read_text("utf-8")
    assert "diff --git a/src/app.py b/src/app.py" in prompt
    opening = re.findall(r"DATA-[0-9a-f]+ begin", prompt)
    assert len(opening) == 2 and opening[0] == opening[1]
    assert prompt.index("diff --git") > prompt.rindex(opening[0])  # the diff sits after the opening


def _with_limits(monkeypatch: pytest.MonkeyPatch, **limits: tuple[int, str]) -> None:
    """The real table, with each named harness's input limit set to `(limit, unit)`."""

    table = review_council.load_table()
    for name, (limit, unit) in limits.items():
        row = table["harnesses"][name]
        row["max_prompt"] = [{**row["max_prompt"][0], "limit": limit, "unit": unit}]
    monkeypatch.setattr(review_council, "load_table", lambda *_args, **_kw: table)


def _accented_change(repo: Path) -> None:
    """Commit a change whose text is two UTF-8 bytes for each character."""

    (repo / "src/app.py").write_text("\u00e9" * 4000 + "\n", encoding="utf-8")
    git(repo, "commit", "-q", "-am", "accented")


def test_a_plan_over_a_reviewers_input_limit_is_refused_before_the_yes_and_nothing_runs(
    tools: Path,
    repo: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _accented_change(repo)
    _, plan, _ = council(capsys, repo, "--plan", "--base", "HEAD~1")
    sizes = re.search(r"prompt: (\d+) characters, (\d+) UTF-8 bytes", plan)
    assert sizes, plan
    characters, octets = int(sizes.group(1)), int(sizes.group(2))
    assert octets > characters + 4000  # the unit decides whether a limit holds this prompt
    # Codex counts characters and holds it at exactly its limit; Claude counts bytes and does not.
    _with_limits(monkeypatch, codex=(characters, "characters"), claude=(characters, "bytes"))
    code, out, err = council(capsys, repo, "--plan", "--base", "HEAD~1")
    assert code == 1 and out == ""  # no plan to show the person, so no yes to ask for
    assert "COUNCIL_REFUSED" in err and "over a reviewer's input limit" in err
    assert f"reviewer r2 {CLAUDE_REVIEWER}: {octets} bytes, over the limit of" in err
    assert f"limit of {characters} bytes of the prompt" in err and "read 2026-" in err
    assert "reviewer r1" not in err
    # A run with any plan id is refused the same way, before any reviewer starts.
    code, _, err = council(capsys, repo, "--accept", "--base", "HEAD~1", "--plan-id", "0" * 12)
    assert code == 1 and "over a reviewer's input limit" in err
    assert list((tools / "log").iterdir()) == []
    assert not (repo / ".agents").exists()


def test_a_prompt_at_its_reviewers_limit_is_planned_and_run_as_measured(
    tools: Path,
    repo: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _accented_change(repo)
    _, plan, _ = council(capsys, repo, "--plan", "--base", "HEAD~1", "--reviewer", CODEX_REVIEWER)
    assert "limit of 1048576 characters of the prompt (codex-cli" in plan  # the table's own
    sizes = re.search(r"prompt: (\d+) characters", plan)
    assert sizes, plan
    characters = int(sizes.group(1))
    _with_limits(monkeypatch, codex=(characters, "characters"))
    code, out, _ = council(
        capsys, repo, "--accept", "--base", "HEAD~1", "--reviewer", CODEX_REVIEWER
    )
    assert code == 0, out
    # The run sent the prompt the preflight measured: the same size, so the limit held it.
    # Bytes, decoded: a text read folds the CRLF that a Windows checkout's diff can hold.
    assert len((tools / "log/codex.stdin").read_bytes().decode("utf-8")) == characters


@pytest.mark.parametrize("unit", ["characters", "bytes"])
def test_the_run_measures_each_prompt_again_and_starts_no_reviewer_over_its_limit(
    tools: Path, repo: Path, unit: str
) -> None:
    table = review_council.load_table()
    request = review_council.gather(repo, range_spec=None, base="HEAD~1", files=[], lens="x")
    reviewer = review_council.parse_reviewer(CODEX_REVIEWER, 1, table)
    out = tools / "run"
    out.mkdir()
    [job] = review_council.plan_jobs(request, [reviewer], table, out=out, timeout=None, budget=None)
    prompt = "\u00e9" * 10  # 10 characters, 20 bytes
    job.stdin.write_bytes(prompt.encode("utf-8"))
    size_now = review_council.measure(prompt, unit)
    job.cwd.mkdir(parents=True)
    try:
        for limit, starts in ((size_now - 1, False), (size_now, True)):
            job.spec = {
                **job.spec,
                "max_prompt": [
                    {**table["harnesses"]["codex"]["max_prompt"][0], "limit": limit, "unit": unit}
                ],
            }
            outcome = review_council.run_job(job)
            assert (tools / "log/codex.argv").exists() == starts, (limit, outcome)
            if not starts:
                assert outcome.status == "failed" and "not started" in outcome.detail
                assert f"{size_now} {unit}, over the limit of {limit} {unit}" in outcome.detail
    finally:
        shutil.rmtree(job.cwd, ignore_errors=True)


def test_each_platform_takes_its_own_argument_limit(
    tools: Path,
    repo: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec = review_council.load_table()["harnesses"]["opencode"]
    for platform, program, limit, scope in (
        ("linux", "/usr/bin/opencode", 131071, "prompt"),
        ("darwin", "/usr/local/bin/opencode", 1048576, "arguments and environment"),
        ("win32", r"C:\tools\opencode.cmd", 8191, "command line"),
        ("win32", r"C:\tools\opencode.exe", 32767, "command line"),
    ):
        monkeypatch.setattr(review_council, "PLATFORM", platform)
        row = review_council.input_limit(spec, program)
        assert row and (row["limit"], row["measure"]) == (limit, scope), platform
    monkeypatch.setattr(review_council, "PLATFORM", "freebsd14")
    assert review_council.input_limit(spec, "/usr/local/bin/opencode") is None
    _, plan, _ = council(capsys, repo, "--plan", "--base", "HEAD~1", "--reviewer", "opencode:p/m")
    assert "no input limit recorded for this harness on freebsd14 (UNVERIFIED)" in plan
    # A 40000-character prompt as one argument: within Linux's limit, over the Windows command line.
    (repo / "src/app.py").write_text("x" * 40000 + "\n", encoding="utf-8")
    git(repo, "commit", "-q", "-am", "long")
    monkeypatch.setattr(review_council, "PLATFORM", "linux")
    code, plan, _ = council(
        capsys, repo, "--plan", "--base", "HEAD~1", "--reviewer", "opencode:p/m"
    )
    assert code == 0 and "of the prompt (Linux execve(2)" in plan
    monkeypatch.setattr(review_council, "PLATFORM", "win32")
    code, out, err = council(
        capsys, repo, "--plan", "--base", "HEAD~1", "--reviewer", "opencode:p/m"
    )
    assert code == 1 and out == "" and "utf-16 of the command line (Windows" in err
    assert list((tools / "log").iterdir()) == []


@pytest.mark.skipif(
    WINDOWS, reason="a .cmd stand-in cannot carry the newlines of a multi-line argument"
)
def test_an_argument_prompt_is_delivered_as_measured_with_its_crlf_line_ends(
    tools: Path,
    repo: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (repo / "src/app.py").write_bytes(b"one\r\ntwo\r\n" * 50)
    git(repo, "commit", "-q", "-am", "crlf")
    monkeypatch.setattr(review_council, "PLATFORM", "linux")  # the row that counts the prompt
    reviewer = ("--reviewer", "opencode:p/m")
    _, plan, _ = council(capsys, repo, "--plan", "--base", "HEAD~1", *reviewer)
    sizes = re.search(r"UTF-8 bytes; (\d+) bytes against the limit", plan)
    assert sizes, plan
    octets = int(sizes.group(1))
    table = review_council.load_table()
    row = table["harnesses"]["opencode"]
    row["max_prompt"] = [{**row["max_prompt"][0], "limit": octets}]  # exactly at the limit
    monkeypatch.setattr(review_council, "load_table", lambda *_args, **_kw: table)
    code, out, _ = council(capsys, repo, "--accept", "--base", "HEAD~1", *reviewer)
    assert code == 0, out
    argv = (tools / "log/opencode.argv").read_bytes()
    sent = argv[argv.index(b"You are an independent reviewer") : -1]  # the last argument
    assert b"two\r\n" in sent and len(sent) == octets  # the CRLF kept, the size measured


def test_the_table_holds_a_source_and_a_read_day_for_every_flag_and_no_dangerous_flag() -> None:
    table = review_council.load_table()
    known = {"model", "effort", "snapshot", "answer", "budget", "prompt", "configdir", "api_key"}
    for entry in table["default_council"]:  # each default names a harness of the table
        assert entry.split(":")[0] in table["harnesses"] and entry.count(":") == 2, entry
    for entry in table["default_council"]:  # a harness whose read-only mode is unconfirmed
        assert table["harnesses"][entry.split(":")[0]].get("read_only_confirmed", True), entry
    for name, row in table["harnesses"].items():
        assert row["timeout_seconds"] > 0 and row["binary"], name
        assert row["max_prompt"], name  # every harness says how large a prompt it takes
        for limit in row["max_prompt"]:
            assert limit["unit"] in {"characters", "bytes", "utf-16"}, name
            assert limit["measure"] in {"prompt", "command line", "arguments and environment"}
            assert limit["limit"] is None or limit["limit"] > 0, name
            assert limit["version"] and limit["source"] and limit["read"], name
        words = [word for entry in row["argv"] for word in entry["args"]]
        words += [entry["value"] for entry in row.get("env", [])]
        assert not any(
            bad in word for word in words for bad in ("bypass", "dangerous", "yolo", "skip-perm")
        ), name
        for entry in [*row["argv"], *row.get("env", [])]:
            assert entry["source"] and entry["read"] and entry["why"], (name, entry)
            assert entry["run"] in {"tested", "UNVERIFIED"}, (name, entry)
            if entry["run"] == "tested":  # a claim of a run names what the run showed and when
                assert entry["observed"] and entry["observed_on"], (name, entry)
            assert isinstance(entry["listed_in_help"], bool)
            for word in [*entry.get("args", []), entry.get("value", "")]:
                for placeholder in review_council._PLACEHOLDER.findall(word):
                    assert placeholder in known, (name, word)
    assert ["-s", "read-only"] in [e["args"] for e in table["harnesses"]["codex"]["argv"]]
    claude = [e["args"] for e in table["harnesses"]["claude"]["argv"]]
    assert ["--permission-mode", "dontAsk"] in claude and ["--restricted"] in claude


def test_a_disposition_inside_a_longer_fence_is_kept_as_review_check_reads_it() -> None:
    body = (
        "````text\nDisposition: fixed — x\n```\nDisposition: still fenced\n````\nDisposition: out\n"
    )
    kept, dropped = review_council._strip(body)
    assert dropped == 1
    assert "Disposition: fixed — x" in kept and "Disposition: still fenced" in kept
    assert "Disposition: out" not in kept


def test_the_run_prints_each_verdict_and_finding_count(
    tools: Path, repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _, out, _ = council(capsys, repo, "--accept", "--base", "HEAD~1")
    assert "verdict FAIL, 3 finding(s)" in out and "verdict PASS, 0 finding(s)" in out


def test_a_path_with_no_readable_blob_is_flagged_and_the_run_goes_on(
    tools: Path,
    repo: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real = review_council.size._git_ok

    def refuse_blobs(root: Path, *args: str) -> bytes:
        if args[0] == "cat-file":
            raise review_council.size.SizeError("no blob")
        return real(root, *args)

    monkeypatch.setattr(review_council.size, "_git_ok", refuse_blobs)
    code, out, _ = council(capsys, repo, "--accept", "--base", "HEAD~1", "--reviewer", "codex")
    assert code == 0, out
    review = next((repo / ".agents/work/council").glob("*/r1-codex.md")).read_text("utf-8")
    assert "src/app.py:2 names an entry of the revision that is no file" in review
    assert next((repo / ".agents/work/council").glob("*/council.json")).is_file()


def test_claude_uses_bare_where_an_api_key_is_set_and_restricted_where_none_is(
    tools: Path,
    repo: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, plain, _ = council(capsys, repo, "--plan", "--base", "HEAD~1")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "not-a-real-key")
    _, keyed, _ = council(capsys, repo, "--plan", "--base", "HEAD~1")

    def argvs(text: str) -> list[str]:
        return [line for line in text.splitlines() if line.strip().startswith("argv: claude")]

    assert argvs(plain) and argvs(keyed)
    assert all("--restricted --safe-mode" in a and "--bare" not in a for a in argvs(plain))
    assert all("--bare" in a and "--restricted" not in a for a in argvs(keyed))
    assert "bills the API key" in keyed and "no ANTHROPIC_API_KEY is set" in plain
    assert "not-a-real-key" not in keyed + plain  # the key is never printed
    for argv_line in argvs(keyed):
        assert "--tools Read,Grep,Glob" in argv_line and "--permission-mode dontAsk" in argv_line


def test_a_harness_with_no_default_needs_a_model_named(
    capsys: pytest.CaptureFixture[str],
) -> None:
    table = {"harnesses": {"other": {}}, "default_council": []}
    with pytest.raises(review_council.CouncilError, match="no default"):
        review_council.parse_reviewer("other", 1, table)
    assert review_council.parse_reviewer("other:m:e", 1, table).label == "other:m:e"


NAMED = ("--reviewer", "cursor:some-model[effort=high]", "--reviewer", "opencode:p/m#high")


def test_the_plan_says_read_only_is_unconfirmed_for_cursor_and_opencode(
    tools: Path, repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _, plan, _ = council(capsys, repo, "--plan", "--base", "HEAD~1", *NAMED)
    assert plan.count("READ-ONLY NOT CONFIRMED BY DOCUMENTATION") == 2
    assert "reviewer r1: cursor:some-model[effort=high]" in plan
    assert "<the prompt>" in plan and "standard input: closed" in plan
    assert "OPENCODE_PERMISSION=" in plan and "CURSOR_CONFIG_DIR=" in plan


@pytest.mark.skipif(
    WINDOWS, reason="a .cmd stand-in cannot carry the newlines of a multi-line argument"
)
def test_cursor_and_opencode_take_the_prompt_as_the_last_argument(
    tools: Path, repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    named = NAMED
    code, out, _ = council(capsys, repo, "--accept", "--base", "HEAD~1", *named)
    assert code == 0, out
    log = tools / "log"
    cursor = (log / "cursor.argv").read_text("utf-8").split("\n")
    assert cursor[:3] == ["-p", "--mode", "ask"] and "--force" not in cursor
    assert cursor[cursor.index("--model") + 1] == "some-model[effort=high]"
    assert "independent reviewer" in "\n".join(cursor[cursor.index("--model") + 2 :])  # last
    assert (log / "cursor.stdin").read_text("utf-8").strip() == "stdin closed"
    assert (log / "cursor.env").read_text("utf-8").strip().startswith("CURSOR_CONFIG_DIR=")
    opencode = (log / "opencode.argv").read_text("utf-8").split("\n")
    assert opencode[:2] == ["run", "--standalone"] and "--auto" not in opencode
    assert "independent reviewer" in "\n".join(opencode[opencode.index("--model") + 2 :])
    env = (log / "opencode.env").read_text("utf-8")
    assert 'OPENCODE_PERMISSION={"*":"deny"' in env and "OPENCODE_DISABLE_CLAUDE_CODE=1" in env
    for name in ("r1-cursor.md", "r2-opencode.md"):
        review = next((repo / ".agents/work/council").glob(f"*/{name}"))
        assert review.read_text("utf-8").startswith("Reviewed: ")


def test_a_harness_with_its_effort_in_the_model_id_refuses_an_effort_part() -> None:
    table = review_council.load_table()
    for bad in ("cursor", "cursor:m:high", "opencode:p/m:high", "opencode"):
        with pytest.raises(review_council.CouncilError):
            review_council.parse_reviewer(bad, 1, table)
    with pytest.raises(review_council.CouncilError) as refused:
        review_council.parse_reviewer("cursor:m:high", 1, table)
    assert str(refused.value) == (
        'the harness cursor takes no effort part in "cursor:m:high": its effort is part of its '
        "model id (for example cursor:MODEL)"
    )
    assert review_council.parse_reviewer("cursor:m[effort=high]", 1, table).effort == ""


def test_accept_refuses_a_run_that_differs_from_the_plan_the_person_approved(
    tools: Path,
    repo: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, plan, _ = council(capsys, repo, "--plan", "--base", "HEAD~1")
    identity = re.search(r"plan id: ([0-9a-f]{12})", plan)
    assert identity and f"--plan-id {identity.group(1)}" in plan
    # The login changed after the plan: the key sets --bare, which the plan did not show.
    monkeypatch.setenv("ANTHROPIC_API_KEY", "not-a-real-key")
    code, _, err = council(
        capsys, repo, "--accept", "--base", "HEAD~1", "--plan-id", identity.group(1)
    )
    assert code == 1 and "differs from the plan" in err and "ANTHROPIC_API_KEY" in err
    assert list((tools / "log").iterdir()) == []  # nothing started
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    code, out, _ = council(
        capsys, repo, "--accept", "--base", "HEAD~1", "--plan-id", identity.group(1)
    )
    assert code == 0, out


def test_accept_refuses_without_a_plan_id(
    tools: Path, repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = review_council.main(
        ["--root", str(repo), "--accept", "--base", "HEAD~1", "--reviewer", CODEX_REVIEWER]
    )
    err = capsys.readouterr().err
    assert code == 1 and "--plan-id" in err and "--plan" in err
    assert list((tools / "log").iterdir()) == []  # nothing started


def test_a_credential_a_reviewer_echoes_in_an_error_is_not_printed(
    tools: Path,
    repo: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FAKE_CODEX", "leak")
    monkeypatch.setenv("SOME_API_KEY", "secret-value-1234")
    code, out, err = council(capsys, repo, "--accept", "--base", "HEAD~1", "--reviewer", "codex")
    assert code == 1 and "FAILED" in out
    assert "secret-value-1234" not in out + err and "[redacted]" in out


def _write_config(place: Path, **data: object) -> None:
    place.parent.mkdir(parents=True, exist_ok=True)
    place.write_text(json.dumps({"version": 1, **data}), encoding="utf-8")


@pytest.fixture
def person(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A home folder of the person with nothing in it."""

    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    return home


def test_with_no_file_and_no_reviewer_the_plan_has_the_one_built_in_reviewer(
    tools: Path, repo: Path, person: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _, out, _ = council(capsys, repo, "--plan", "--base", "HEAD~1", pair=False)
    assert "reviewers from: the built-in default council" in out
    assert "reviewer r1: codex:gpt-6-astra:high" in out and "reviewer r2" not in out


def test_the_projects_council_file_comes_before_the_persons_and_the_command_line_wins(
    tools: Path, repo: Path, person: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_config(person / ".outcomebound/council.json", reviewers=["codex:person-model:low"])
    _, out, _ = council(capsys, repo, "--plan", "--base", "HEAD~1", pair=False)
    assert "reviewers from: the council file" in out and str(person) in out
    assert "reviewer r1: codex:person-model:low" in out
    _write_config(
        repo / ".outcomebound/council.json",
        reviewers=["codex:project-a:high", "claude:project-b:high"],
        lens="the file's lens",
        timeout_seconds=77,
        budget_usd="2.5",
    )
    _, out, _ = council(capsys, repo, "--plan", "--base", "HEAD~1", pair=False)
    assert str(repo.resolve()) in out or ".outcomebound" in out
    assert (
        "reviewer r1: codex:project-a:high" in out and "reviewer r2: claude:project-b:high" in out
    )
    assert "person-model" not in out  # the person's file is not merged in
    assert "the file's lens" in out and "timeout: 77 s" in out and "--max-budget-usd 2.5" in out
    _, out, _ = council(
        capsys,
        repo,
        "--plan",
        "--base",
        "HEAD~1",
        "--reviewer",
        "codex:cli-model:high",
        "--lens",
        "the command's lens",
        "--timeout",
        "9",
        "--budget-usd",
        "1",
    )
    assert "reviewers from: --reviewer on the command line" in out
    assert "cli-model" in out and "project-a" not in out
    assert "the command's lens" in out and "timeout: 9 s" in out
    assert "--max-budget-usd" not in out  # Codex has no cap flag, so the cap reaches no argv


def test_a_council_file_that_is_not_valid_is_refused_with_its_reason(
    tools: Path, repo: Path, person: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    place = repo / ".outcomebound/council.json"
    for data, word in (
        ({"reviewers": []}, "reviewers"),
        ({"reviewers": ["codex"], "extra": 1}, "extra"),
        ({"reviewers": ["codex"], "budget_usd": "lots"}, "budget_usd"),
        ({"reviewers": ["gemini:x"]}, "not in the table"),
    ):
        _write_config(place, **data)
        code, _, err = council(capsys, repo, "--plan", "--base", "HEAD~1", pair=False)
        assert code == 1 and "COUNCIL_REFUSED" in err and word in err, (data, err)
    place.write_text("{not json", encoding="utf-8")
    code, _, err = council(capsys, repo, "--plan", "--base", "HEAD~1", pair=False)
    assert code == 1 and "cannot be read" in err


def test_a_reviewer_with_no_effort_and_no_default_has_no_effort_flag(
    tools: Path, repo: Path, person: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _, out, _ = council(
        capsys, repo, "--plan", "--base", "HEAD~1", "--reviewer", "claude:m-1", pair=False
    )
    (line,) = (line for line in out.splitlines() if line.strip().startswith("argv:"))
    assert "--model m-1" in line and "--effort" not in line
    # Codex has a default effort in the table, so a model alone takes it.
    _, out, _ = council(
        capsys, repo, "--plan", "--base", "HEAD~1", "--reviewer", "codex:m-2", pair=False
    )
    assert "-m m-2 -c model_reasoning_effort=high" in out


def test_an_empty_lens_on_the_command_line_overrides_the_files_lens(
    tools: Path, repo: Path, person: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_config(repo / ".outcomebound/council.json", reviewers=[CODEX_REVIEWER], lens="from file")
    _, out, _ = council(capsys, repo, "--plan", "--base", "HEAD~1", pair=False)
    assert "lens: from file" in out and "lens from: the council file" in out
    _, out, _ = council(capsys, repo, "--plan", "--base", "HEAD~1", "--lens", "", pair=False)
    assert "from file" not in out and "lens from: --lens on the command line" in out


def test_the_plan_warns_where_the_change_under_review_supplies_the_council_file(
    tools: Path, repo: Path, person: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Committed in the reviewed range: the change picks its own reviewers and lens.
    _write_config(
        repo / ".outcomebound/council.json", reviewers=[CODEX_REVIEWER], lens="only spelling"
    )
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "add a council file")
    _, out, _ = council(capsys, repo, "--plan", "--range", "HEAD~1..HEAD", pair=False)
    assert "WARNING: the council file" in out and "named in the diff" in out
    # Committed before the range: no warning.
    _, out, _ = council(capsys, repo, "--plan", "--range", "HEAD~2..HEAD~1", pair=False)
    assert "WARNING" not in out
    _, out, _ = council(capsys, repo, "--plan", "--file", "spec.md", pair=False)
    assert "WARNING" not in out  # a clean committed file is the project's own setting
    # Edited and not committed.
    _write_config(repo / ".outcomebound/council.json", reviewers=[CODEX_REVIEWER], lens="edited")
    _, out, _ = council(capsys, repo, "--plan", "--file", "spec.md", pair=False)
    assert "with uncommitted changes" in out
    # A command-line reviewer and lens leave nothing from the file in use.
    _, out, _ = council(
        capsys, repo, "--plan", "--range", "HEAD~1..HEAD", "--lens", "mine", pair=True
    )
    assert "WARNING" not in out


def test_defaults_prints_the_built_in_council_and_the_file_in_effect_and_runs_nothing(
    tools: Path, repo: Path, person: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _, out, _ = council(capsys, repo, "--defaults", pair=False)
    assert "built-in default council: codex:gpt-6-astra:high" in out
    assert "council file in effect: none" in out
    _write_config(person / ".outcomebound/council.json", reviewers=["codex:other:low"])
    _, out, _ = council(capsys, repo, "--defaults", pair=False)
    assert "council file in effect:" in out and "reviewers: codex:other:low" in out
    assert list((tools / "log").iterdir()) == []


def test_every_refusal_of_a_value_from_the_council_file_names_the_file(
    tools: Path, repo: Path, person: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    place = repo / ".outcomebound/council.json"
    for data in (
        {"reviewers": ["gemini:x"]},
        {"reviewers": [CODEX_REVIEWER], "timeout_seconds": 0},
        {"reviewers": ["claude"]},
    ):
        _write_config(place, **data)
        code, _, err = council(capsys, repo, "--plan", "--base", "HEAD~1", pair=False)
        assert code == 1 and "in the council file" in err and "council.json" in err, (data, err)


# --- named councils and the account a reviewer starts with -------------------------------------


def _plan_id(out: str) -> str:
    shown = re.search(r"plan id: ([0-9a-f]{12})", out)
    assert shown, out
    return shown.group(1)


def _real(place: Path) -> str:
    return os.path.realpath(place)


def _line(out: str, start: str) -> str:
    """The one line of `out` that starts with `start` once its indent is dropped."""

    (found,) = [line.strip() for line in out.splitlines() if line.strip().startswith(start)]
    return found


def test_a_named_council_of_the_persons_file_supplies_the_reviewers(
    tools: Path, repo: Path, person: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    place = person / ".outcomebound/council.json"
    _write_config(
        place, councils={"pair": ["codex:m-a:high", "claude:m-b:low"], "trio": ["codex:m-c"]}
    )
    code, out, _ = council(
        capsys, repo, "--plan", "--base", "HEAD~1", "--council", "pair", pair=False
    )
    assert code == 0, out
    assert f"reviewers from: the council pair in the council file {place}" in out
    assert "reviewer r1: codex:m-a:high" in out and "reviewer r2: claude:m-b:low" in out
    assert "reviewer r3" not in out
    # A project file hides the person's reviewers, as before, but not the person's councils.
    _write_config(repo / ".outcomebound/council.json", reviewers=["codex:project-model:high"])
    code, out, _ = council(
        capsys, repo, "--plan", "--base", "HEAD~1", "--council", "trio", pair=False
    )
    assert code == 0 and "reviewer r1: codex:m-c:high" in out and "project-model" not in out
    # The listing shows each seat as the plan resolves it, not as the file spells it.
    _, out, _ = council(capsys, repo, "--defaults", pair=False)
    assert f"the person's council file: {place}" in out
    assert "  council pair: codex:m-a:high, claude:m-b:low" in out
    assert "  council trio: codex:m-c:high" in out


def test_the_host_listing_prints_the_resolved_seats_with_lens_timeout_and_cap(
    tools: Path, repo: Path, person: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    place = person / ".outcomebound/council.json"
    _write_config(place, councils={"pair": ["codex:m-a", "claude:m-b:low"]}, lens="the lens")
    code, out, err = council(
        capsys,
        repo,
        "--defaults",
        "--council",
        "pair",
        "--timeout",
        "90",
        "--budget-usd",
        "2",
        pair=False,
    )
    assert code == 0, err
    lines = out.splitlines()
    assert lines[0] == (
        "COUNCIL SEATS for a host that starts its own agents (nothing has run): the council "
        f"pair, from the council pair in the council file {place}"
    )
    assert lines[1] == f"lens: the lens (from the council file {place})"
    assert lines[2] == "seat r1: codex:m-a:high; timeout 90 s; cap 2 USD"
    assert lines[3] == "seat r2: claude:m-b:low; timeout 90 s; cap 2 USD"
    assert "no spend cap, timeout or read-only mode holds except by the brief" in lines[4]
    assert list((tools / "log").iterdir()) == []
    # A seat the plan would refuse is refused here too.
    _write_config(place, councils={"bad": ["gemini:x"]})
    for args in (("--defaults", "--council", "bad"), ("--defaults",)):
        code, out, err = council(capsys, repo, *args, pair=False)
        assert code == 1 and f"in the council file {place}:" in err, (args, out, err)
        assert "not in the table" in err


def test_a_council_name_is_refused_with_reviewer_and_an_unknown_one_lists_the_names(
    tools: Path, repo: Path, person: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    place = person / ".outcomebound/council.json"
    code, _, err = council(
        capsys, repo, "--plan", "--base", "HEAD~1", "--council", "pair", pair=False
    )
    assert code == 1 and f"the person's council file {place} does not exist" in err
    _write_config(place, councils={"pair": ["codex:m-a:high"], "trio": ["codex:m-c"]})
    code, _, err = council(
        capsys,
        repo,
        "--plan",
        "--base",
        "HEAD~1",
        "--council",
        "pair",
        "--reviewer",
        "codex",
        pair=False,
    )
    assert code == 1 and err == "COUNCIL_REFUSED: give --council or --reviewer, not both\n"
    code, _, err = council(
        capsys, repo, "--plan", "--base", "HEAD~1", "--council", "other", pair=False
    )
    assert code == 1
    assert err == (
        'COUNCIL_REFUSED: there is no council named "other" in the person\'s council file '
        f"{place}; the councils it names: pair, trio\n"
    )
    _write_config(place, councils={"bad": ["gemini:x"]})
    code, _, err = council(
        capsys, repo, "--plan", "--base", "HEAD~1", "--council", "bad", pair=False
    )
    assert code == 1 and f"in the council file {place}:" in err and "not in the table" in err
    for councils, word in (
        ({"no spaces": ["codex"]}, "is not a plain word"),
        (["codex"], "$.councils"),
        ({"empty": []}, "$.councils.empty is not a list"),
        ({"mixed": ["codex", 3]}, "$.councils.mixed is not a list"),
    ):
        _write_config(place, councils=councils)
        code, _, err = council(capsys, repo, "--plan", "--base", "HEAD~1", pair=False)
        assert code == 1 and "COUNCIL_REFUSED" in err and word in err, (councils, err)
    # A project file is checked the same way before it is refused for holding councils.
    place.unlink()
    project = repo / ".outcomebound/council.json"
    _write_config(project, councils=["codex"])
    code, _, err = council(capsys, repo, "--plan", "--base", "HEAD~1", pair=False)
    assert code == 1 and f"the council file {project} is not valid" in err, err
    project.unlink()
    assert list((tools / "log").iterdir()) == []


def test_a_project_file_that_defines_councils_or_homes_is_refused(
    tools: Path, repo: Path, person: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    project = repo / ".outcomebound/council.json"
    for key, value in (("councils", {"pair": ["codex"]}), ("homes", {"codex": str(person)})):
        _write_config(project, reviewers=[CODEX_REVIEWER], **{key: value})
        code, _, err = council(capsys, repo, "--plan", "--base", "HEAD~1", pair=False)
        assert code == 1, err
        assert f"the project's council file {project} defines {key}, which only" in err
        assert str(person / ".outcomebound/council.json") in err
    assert list((tools / "log").iterdir()) == []


@needs_symlinks
@pytest.mark.parametrize("linked", ["file", "folder"])
def test_a_persons_file_that_resolves_inside_the_repository_is_not_the_persons(
    tools: Path, repo: Path, person: Path, capsys: pytest.CaptureFixture[str], linked: str
) -> None:
    inside = repo / "settings" / ".outcomebound"
    _write_config(inside / "council.json", councils={"pair": [CODEX_REVIEWER]})
    if linked == "file":
        (person / ".outcomebound").mkdir()
        (person / ".outcomebound/council.json").symlink_to(inside / "council.json")
    else:
        (person / ".outcomebound").symlink_to(inside, target_is_directory=True)
    code, _, err = council(
        capsys, repo, "--plan", "--base", "HEAD~1", "--council", "pair", pair=False
    )
    assert code == 1, err
    assert f"inside the repository under review {repo}" in err and "councils are refused" in err
    _write_config(inside / "council.json", homes={"codex": str(person)})
    code, _, err = council(capsys, repo, "--plan", "--base", "HEAD~1")
    assert code == 1 and "its homes are refused" in err, err
    # Without councils or homes, the linked file still names reviewers, as any file may.
    _write_config(inside / "council.json", reviewers=["codex:linked-model:high"])
    code, out, _ = council(capsys, repo, "--plan", "--base", "HEAD~1", pair=False)
    assert code == 0 and "reviewer r1: codex:linked-model:high" in out
    assert list((tools / "log").iterdir()) == []


def test_the_plan_shows_each_reviewers_account_folder_and_route_and_its_id_binds_them(
    tools: Path,
    repo: Path,
    person: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def plan() -> str:
        code, out, err = council(capsys, repo, "--plan", "--base", "HEAD~1")
        assert code == 0, err
        return out

    out = plan()
    codex_default, claude_default = _real(person / ".codex"), _real(person / ".claude")
    folders = [line for line in out.splitlines() if "account folder:" in line]
    assert folders == [
        f"  account folder: {codex_default} (unset: the tool's default; the reviewer starts "
        "with CODEX_HOME left unset)",
        f"  account folder: {claude_default} (unset: the tool's default; the reviewer starts "
        "with CLAUDE_CONFIG_DIR left unset)",
    ]
    assert _line(out, "credentials and route: CODEX_API_KEY") == (
        "credentials and route: CODEX_API_KEY not set; OPENAI_API_KEY not set "
        "(a value is never printed)"
    )
    assert _line(out, "credentials and route: ANTHROPIC_API_KEY") == (
        "credentials and route: ANTHROPIC_API_KEY not set; ANTHROPIC_AUTH_TOKEN not set; "
        "CLAUDE_CODE_OAUTH_TOKEN not set; CLAUDE_CODE_USE_BEDROCK off; "
        "CLAUDE_CODE_USE_VERTEX off; CLAUDE_CODE_USE_FOUNDRY off "
        "(a value is never printed; a route switch is on where its value is 1, true, yes or on)"
    )
    assert _line(out, "endpoints: OPENAI") == "endpoints: OPENAI_BASE_URL not set"
    assert "a different key or login in the same mode is not detected" in out
    ids = {_plan_id(out)}
    for folder in ("a", "b"):
        monkeypatch.setenv("CODEX_HOME", str(tools / folder))
        out = plan()
        assert f"account folder: {_real(tools / folder)} (inherited from this environment;" in out
        ids.add(_plan_id(out))
    monkeypatch.delenv("CODEX_HOME")
    # Another home folder moves the tool's default folder.
    other = tools / "other-home"
    other.mkdir()
    monkeypatch.setenv("HOME", str(other))
    monkeypatch.setenv("USERPROFILE", str(other))
    ids.add(_plan_id(plan()))
    monkeypatch.setenv("HOME", str(person))
    monkeypatch.setenv("USERPROFILE", str(person))
    # A credential or a route set, and an endpoint, shown without a secret.
    for name, value in (
        ("OPENAI_API_KEY", "sk-not-a-real-key-0000"),
        ("CLAUDE_CODE_OAUTH_TOKEN", "oauth-not-real-0000"),
        ("CLAUDE_CODE_USE_BEDROCK", "1"),
        ("ANTHROPIC_BASE_URL", "https://user:pw-not-real@proxy.example.test/v1"),
    ):
        monkeypatch.setenv(name, value)
        out = plan()
        # A switch's value "1" is in the plan in other words; every other value is never in it.
        assert (f"={value}" if value == "1" else value) not in out, name
        ids.add(_plan_id(out))
        monkeypatch.delenv(name)
    assert len(ids) == 8, "each of these is a different plan"
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://proxy.example.test/v1")
    out = plan()
    assert "endpoints: ANTHROPIC_BASE_URL=https://proxy.example.test (only the scheme" in out
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://user:pw-not-real@proxy.example.test/v1")
    out = plan()
    assert "ANTHROPIC_BASE_URL=https://proxy.example.test (only the scheme" in out
    assert "pw-not-real" not in out and "user" not in _line(out, "endpoints: ANTHROPIC")
    monkeypatch.delenv("ANTHROPIC_BASE_URL")
    # The person's file sets the folder, over the inherited one.
    _write_config(
        person / ".outcomebound/council.json",
        homes={"codex": str(tools / "set"), "claude": str(tools / "claude-set")},
    )
    monkeypatch.setenv("CODEX_HOME", str(tools / "a"))
    out = plan()
    assert f"account folder: {_real(tools / 'set')} (set by the person's council file;" in out
    assert f"CLAUDE_CONFIG_DIR={_real(tools / 'claude-set')})" in out
    _, shown, _ = council(capsys, repo, "--defaults", pair=False)
    assert f"  home of codex: {tools / 'set'}" in shown


def test_accept_starts_each_reviewer_with_the_planned_account_folder(
    tools: Path,
    repo: Path,
    person: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A project file is in effect: the person's homes still apply.
    _write_config(repo / ".outcomebound/council.json", reviewers=[CODEX_REVIEWER])
    _write_config(person / ".outcomebound/council.json", homes={"codex": str(tools / "set")})
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tools / "inherited"))
    _, plan, _ = council(capsys, repo, "--plan", "--base", "HEAD~1")
    approved = _plan_id(plan)
    # The inherited Claude folder changed after the person's yes: refused, nothing started.
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tools / "other"))
    code, _, err = council(capsys, repo, "--accept", "--base", "HEAD~1", "--plan-id", approved)
    assert code == 1 and "differs from the plan" in err and "account folder" in err
    assert list((tools / "log").iterdir()) == []
    # So did the person's file.
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tools / "inherited"))
    _write_config(person / ".outcomebound/council.json", homes={"codex": str(tools / "moved")})
    code, _, err = council(capsys, repo, "--accept", "--base", "HEAD~1", "--plan-id", approved)
    assert code == 1 and "differs from the plan" in err
    assert list((tools / "log").iterdir()) == []
    # Back as planned, with a variable no reviewer's account uses changed: the plan holds.
    _write_config(person / ".outcomebound/council.json", homes={"codex": str(tools / "set")})
    monkeypatch.setenv("SOME_UNRELATED_SETTING", "changed")
    code, out, err = council(capsys, repo, "--accept", "--base", "HEAD~1", "--plan-id", approved)
    assert code == 0, out + err
    log = tools / "log"
    assert (log / "codex.env").read_text(encoding="utf-8") == f"CODEX_HOME={_real(tools / 'set')}\n"
    assert (log / "claude.env").read_text(encoding="utf-8") == (
        f"CLAUDE_CONFIG_DIR={_real(tools / 'inherited')}\n"
    )


def test_a_default_account_folder_reaches_the_reviewer_as_planned(
    tools: Path, repo: Path, person: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code, out, err = council(capsys, repo, "--accept", "--base", "HEAD~1")
    assert code == 0, out + err
    log = tools / "log"
    # The tool's default folder is bound in the plan, and the variable stays unset, as the tool
    # needs it where that folder does not exist yet.
    assert (log / "codex.env").read_text(encoding="utf-8") == "CODEX_HOME=(unset)\n"
    assert (log / "claude.env").read_text(encoding="utf-8") == "CLAUDE_CONFIG_DIR=(unset)\n"


@needs_symlinks
def test_accept_refuses_a_linked_account_folder_whose_target_changed(
    tools: Path, repo: Path, person: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    for name in ("profile-a", "profile-b"):
        (tools / name).mkdir()
    link = tools / "profile"
    link.symlink_to(tools / "profile-a", target_is_directory=True)
    _write_config(person / ".outcomebound/council.json", homes={"codex": str(link)})
    _, plan, _ = council(capsys, repo, "--plan", "--base", "HEAD~1", "--reviewer", "codex:m")
    assert f"account folder: {_real(tools / 'profile-a')} (set by" in plan
    approved = _plan_id(plan)
    link.unlink()
    link.symlink_to(tools / "profile-b", target_is_directory=True)
    code, _, err = council(
        capsys, repo, "--accept", "--base", "HEAD~1", "--reviewer", "codex:m", "--plan-id", approved
    )
    assert code == 1 and "differs from the plan" in err
    assert list((tools / "log").iterdir()) == []
    link.unlink()
    link.symlink_to(tools / "profile-a", target_is_directory=True)
    code, out, err = council(
        capsys, repo, "--accept", "--base", "HEAD~1", "--reviewer", "codex:m", "--plan-id", approved
    )
    assert code == 0, out + err
    assert (tools / "log/codex.env").read_text(encoding="utf-8") == (
        f"CODEX_HOME={_real(tools / 'profile-a')}\n"
    )


def test_accept_refuses_another_program_a_changed_file_or_a_moved_base(
    tools: Path,
    repo: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    git(repo, "branch", "reviewed-base", "HEAD~1")
    args = ("--base", "reviewed-base", "--file", "spec.md", "--reviewer", CODEX_REVIEWER)
    _, plan, _ = council(capsys, repo, "--plan", *args)
    approved = _plan_id(plan)
    assert _line(plan, "program:").startswith(f"program: {programs.find('codex')} (")
    assert Path(programs.find("codex") or "").parent == tools / "bin"

    def refused() -> None:
        code, _, err = council(capsys, repo, "--accept", *args, "--plan-id", approved)
        assert code == 1 and "differs from the plan" in err, err
        assert list((tools / "log").iterdir()) == []

    # Another codex first on PATH.
    other = tools / "other-bin"
    shell_tool(other, "codex", CODEX)
    path = os.environ["PATH"]
    monkeypatch.setenv("PATH", os.pathsep.join([str(other), path]))
    refused()
    monkeypatch.setenv("PATH", path)
    # A named file edited in the work tree: same name, other text.
    (repo / "spec.md").write_text("# Spec\nSomething else.\n", encoding="utf-8")
    refused()
    (repo / "spec.md").write_text("# Spec\nWhat it does.\n", encoding="utf-8")
    # The base ref moved: same ref name and end commit, another diff.
    git(repo, "branch", "-f", "reviewed-base", "HEAD")
    refused()
    git(repo, "branch", "-f", "reviewed-base", "HEAD~1")
    code, out, err = council(capsys, repo, "--accept", *args, "--plan-id", approved)
    assert code == 0, out + err


def test_an_account_folder_unfit_for_a_child_process_is_refused_before_a_plan(
    tools: Path,
    repo: Path,
    person: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    place = person / ".outcomebound/council.json"
    _write_config(place, homes={"codex": "relative/folder"})
    code, _, err = council(capsys, repo, "--plan", "--base", "HEAD~1")
    assert code == 1
    assert f'in the council file {place}: the home of codex "relative/folder" is not' in err
    _write_config(place, homes={"cursor": str(person)})
    code, _, err = council(capsys, repo, "--plan", "--base", "HEAD~1")
    assert code == 1 and "unknown field" in err and "cursor" in err
    for value in (str(person / "a\u0000b"), str(person / "a\nb")):
        _write_config(place, homes={"codex": value})
        code, out, err = council(capsys, repo, "--accept", "--base", "HEAD~1")
        assert code == 1 and out == "" and "holds a control character" in err, err
    place.unlink()
    monkeypatch.setenv("CODEX_HOME", str(person / "a\nb"))
    code, out, err = council(capsys, repo, "--plan", "--base", "HEAD~1")
    assert code == 1 and out == "" and "holds a control character" in err, err
    assert list((tools / "log").iterdir()) == []
    assert not (repo / ".agents").exists()


# --- route switches, endpoints, file identity, the program and the host route ------------------


def test_a_route_switch_is_bound_by_the_value_the_tool_reads_and_an_unsupported_route_refused(
    tools: Path,
    repo: Path,
    person: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    args = ("--base", "HEAD~1", "--reviewer", CLAUDE_REVIEWER)

    def plan() -> str:
        code, out, err = council(capsys, repo, "--plan", *args)
        assert code == 0, err
        return out

    unset = _plan_id(plan())
    monkeypatch.setenv("CLAUDE_CODE_USE_BEDROCK", "0")
    out = plan()
    assert "CLAUDE_CODE_USE_BEDROCK off" in out
    off = _plan_id(out)
    monkeypatch.setenv("CLAUDE_CODE_USE_BEDROCK", " Yes ")
    out = plan()
    assert "CLAUDE_CODE_USE_BEDROCK on" in out and " Yes " not in out
    on = _plan_id(out)
    # The tool reads "0" as off, as if unset, and " Yes " as on: a yes to one is no yes to the
    # other.
    assert off == unset and on != off
    monkeypatch.setenv("CLAUDE_CODE_USE_BEDROCK", "0")
    code, _, err = council(capsys, repo, "--accept", *args, "--plan-id", on)
    assert code == 1 and "differs from the plan" in err
    assert list((tools / "log").iterdir()) == []
    monkeypatch.delenv("CLAUDE_CODE_USE_BEDROCK")
    # A cloud route the table does not support is refused before a plan; off, it is no route.
    monkeypatch.setenv("CLAUDE_CODE_USE_MANTLE", "1")
    code, out, err = council(capsys, repo, "--plan", *args)
    assert code == 1 and out == ""
    assert "CLAUDE_CODE_USE_MANTLE" in err and "not supported" in err, err
    monkeypatch.setenv("CLAUDE_CODE_USE_MANTLE", "false")
    assert _plan_id(plan()) == unset


def test_an_endpoint_shows_only_its_scheme_host_and_port_and_a_bad_one_is_refused(
    tools: Path,
    repo: Path,
    person: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    args = ("--base", "HEAD~1", "--reviewer", CODEX_REVIEWER)
    endpoint = (
        "https://u:pw-not-real@gw.example.test:8443/v1/tok-not-real?api_key=q-not-real#f-not-real"
    )
    monkeypatch.setenv("OPENAI_BASE_URL", endpoint)
    code, out, err = council(capsys, repo, "--plan", *args)
    assert code == 0, err
    assert _line(out, "endpoints:") == (
        "endpoints: OPENAI_BASE_URL=https://gw.example.test:8443 (only the scheme, host and port "
        "are shown)"
    )
    for part in ("pw-not-real", "tok-not-real", "q-not-real", "f-not-real"):
        assert part not in out, part
    first = _plan_id(out)
    monkeypatch.setenv("OPENAI_BASE_URL", endpoint.replace("q-not-real", "q-other"))
    out = council(capsys, repo, "--plan", *args)[1]
    assert _plan_id(out) != first, "the plan id binds the whole value"
    monkeypatch.setenv("OPENAI_BASE_URL", "https://[::1]:9/v1")
    out = council(capsys, repo, "--plan", *args)[1]
    assert "OPENAI_BASE_URL=https://[::1]:9 (only" in out
    for bad in ("http://[bad", "gw.example.test/v1", "https://gw.example.test:99999/q-not-real"):
        monkeypatch.setenv("OPENAI_BASE_URL", bad)
        code, out, err = council(capsys, repo, "--plan", *args)
        assert code == 1 and out == "" and err.startswith("COUNCIL_REFUSED: "), (bad, err)
        assert "OPENAI_BASE_URL" in err and bad not in err and "q-not-real" not in err
    assert list((tools / "log").iterdir()) == []


def _other_case(place: Path) -> Path | None:
    """`place` spelled with its letters' case swapped, where the volume finds the same folder
    there (a case-insensitive volume), else None."""

    other = Path(str(place).swapcase())
    try:
        return other if other != place and os.path.samefile(other, place) else None
    except OSError:
        return None


@needs_symlinks
@pytest.mark.parametrize("linked", ["file", "folder"])
def test_a_persons_file_inside_the_repository_by_another_spelling_is_still_inside(
    tools: Path, repo: Path, person: Path, capsys: pytest.CaptureFixture[str], linked: str
) -> None:
    spelled = _other_case(repo)
    if spelled is None:
        pytest.skip("the volume of the temporary folder is case-sensitive")
    inside = spelled / "settings" / ".outcomebound"
    _write_config(inside / "council.json", councils={"pair": [CODEX_REVIEWER]})
    if linked == "file":
        (person / ".outcomebound").mkdir()
        (person / ".outcomebound/council.json").symlink_to(inside / "council.json")
    else:
        (person / ".outcomebound").symlink_to(inside, target_is_directory=True)
    code, _, err = council(
        capsys, repo, "--plan", "--base", "HEAD~1", "--council", "pair", pair=False
    )
    assert code == 1 and "councils are refused" in err, err
    assert list((tools / "log").iterdir()) == []


def test_a_repository_that_is_the_home_folder_by_another_spelling_holds_the_persons_file(
    tools: Path, repo: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    spelled = _other_case(repo)
    if spelled is None:
        pytest.skip("the volume of the temporary folder is case-sensitive")
    monkeypatch.setenv("HOME", str(spelled))
    monkeypatch.setenv("USERPROFILE", str(spelled))
    _write_config(repo / ".outcomebound/council.json", councils={"pair": [CODEX_REVIEWER]})
    code, out, err = council(
        capsys, repo, "--plan", "--base", "HEAD~1", "--council", "pair", pair=False
    )
    assert code == 0, err
    assert "reviewer r1: codex:m-codex:high" in out


@needs_symlinks
@pytest.mark.skipif(WINDOWS, reason="the stand-in is a .cmd wrapper on Windows, not a link")
def test_the_run_starts_the_program_the_plan_resolved_also_where_its_link_moves(
    tools: Path,
    repo: Path,
    person: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    marked = {
        name: shell_tool(
            tools / f"pkg-{name}",
            "codex",
            CODEX.replace('log="$FAKE_LOG"\n', f'log="$FAKE_LOG"\necho {name} > "$log/which"\n'),
        )
        for name in ("a", "b")
    }
    link = tools / "bin" / "codex"
    link.unlink()
    link.symlink_to(marked["a"])
    args = ("--base", "HEAD~1", "--reviewer", CODEX_REVIEWER)
    _, plan, _ = council(capsys, repo, "--plan", *args)
    assert _line(plan, "program:").startswith(f"program: {link} (resolves to {_real(marked['a'])};")
    snapshot = review_council._snapshot

    def moved(root: Path, commit: str, into: Path) -> None:
        snapshot(root, commit, into)
        link.unlink()
        link.symlink_to(marked["b"])  # an update between the yes and the start

    monkeypatch.setattr(review_council, "_snapshot", moved)
    code, out, err = council(capsys, repo, "--accept", *args, "--plan-id", _plan_id(plan))
    assert code == 0, out + err
    assert (tools / "log/which").read_text(encoding="utf-8") == "a\n"


TRIO = ["codex:m-a:high", "claude:m-b:low", "cursor:neon-x:high"]


def test_defaults_lists_every_council_and_names_a_refused_one_with_its_reason(
    tools: Path, repo: Path, person: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_config(
        person / ".outcomebound/council.json",
        councils={"pair": TRIO[:2], "trio": TRIO, "solo": ["codex:m-c"]},
    )
    code, out, err = council(capsys, repo, "--defaults", pair=False)
    assert code == 1
    assert "  council pair: codex:m-a:high, claude:m-b:low" in out
    assert "  council solo: codex:m-c:high" in out
    assert _line(out, "council trio:") == (
        'council trio: refused: the harness cursor takes no effort part in "cursor:neon-x:high": '
        "its effort is part of its model id (for example cursor:MODEL)"
    )
    assert err.startswith("COUNCIL_REFUSED: ") and "council trio" in err
    code, out, err = council(
        capsys, repo, "--plan", "--base", "HEAD~1", "--council", "trio", pair=False
    )
    assert code == 1 and out == "" and "the harness cursor takes no effort part" in err


def test_the_host_listing_marks_a_seat_the_engine_cannot_start_and_keeps_its_effort(
    tools: Path, repo: Path, person: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    place = person / ".outcomebound/council.json"
    _write_config(place, councils={"trio": [*TRIO, "gemini:g-1:max"]})
    code, out, err = council(capsys, repo, "--defaults", "--council", "trio", "--host", pair=False)
    assert code == 0, err
    assert _line(out, "seat r1:") == "seat r1: codex:m-a:high; timeout 1800 s; cap none"
    assert _line(out, "seat r3:") == (
        "seat r3: cursor:neon-x:high (harness cursor, model neon-x, effort high); host only: "
        'the harness cursor takes no effort part in "cursor:neon-x:high": its effort is part '
        "of its model id (for example cursor:MODEL); timeout none set; cap none"
    )
    assert _line(out, "seat r4:").startswith(
        "seat r4: gemini:g-1:max (harness gemini, model g-1, effort max); host only: the harness "
        '"gemini" is not in the table'
    )
    # Each seat's answer form, as the engine's filing reads it.
    assert "Verdict: FAIL, Verdict: UNVERIFIED or Verdict: PASS" in out
    assert "### r3-<number> · <short title>" in out
    assert list((tools / "log").iterdir()) == []
    # A malformed seat and an unknown council are still refused; --host goes with a council.
    for seats in (["gemini"], ["codex:bad model"], ["a:b:c:d"]):
        _write_config(place, councils={"trio": seats})
        code, _, err = council(
            capsys, repo, "--defaults", "--council", "trio", "--host", pair=False
        )
        assert code == 1 and f"in the council file {place}:" in err, (seats, err)
    for args in (("--council", "other", "--host"), ("--host",), ("--plan", "--host")):
        mode = () if "--plan" in args else ("--defaults",)
        code, _, err = council(capsys, repo, *mode, *args, pair=False)
        assert code == 1 and err.startswith("COUNCIL_REFUSED: "), (args, err)


def test_a_host_answer_is_filed_only_in_the_engines_form(
    tools: Path, repo: Path, person: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    folder = repo / ".agents/work/council/x"
    folder.mkdir(parents=True)
    raw, review = folder / "r1.answer", folder / "r1-host.md"

    def file(text: str) -> tuple[int, str, str]:
        raw.write_text(text, encoding="utf-8")
        args = ("--file-answer", str(raw), "--revision", "HEAD", "--seat", "r1 cursor:neon-x")
        return council(capsys, repo, *args, "--out", str(review), pair=False)

    for text, why in (
        ("Verdict: MAYBE\n\nNo findings.\n", "does not start with"),
        ("Verdict: FAIL\n\n### Wrong sum\nsrc/app.py:2 is wrong.\n", "names no finding"),
    ):
        code, out, err = file(text)
        assert code == 1 and why in err and not review.exists(), (text, err)
    code, out, err = file(GOOD)
    assert code == 0, err
    filed = review.read_text(encoding="utf-8")
    commit = git(repo, "rev-parse", "HEAD")
    assert filed.startswith(f"Reviewed: {commit}\n\n# Council reviewer r1 cursor:neon-x (host)\n")
    assert "no citation was checked" in filed
    assert "Disposition: fixed" not in filed and "Reviewed: somewhere-else" not in filed
    assert "Disposition: kept in a fence" in filed
    assert "verdict FAIL, 3 finding(s)" in out
    # The record is one `review check` reads; an existing review file is never replaced.
    reviewed, entries, malformed = review_check._parse(filed)
    assert reviewed == commit and not malformed
    assert [entry.id for entry in entries] == ["r1-1", "r1-2", "r1-3"]
    code, _, err = file(CLEAN)
    assert code == 1 and "exists" in err


def test_each_review_council_option_the_skill_names_is_one_the_command_takes() -> None:
    text = (ROOT / "skills/review-council/SKILL.md").read_text(encoding="utf-8")
    named = set(re.findall(r"(?<![\w-])--[a-z][a-z-]+", text)) - {"--verify", "--short"}  # Git's
    taken = {flag for action in review_council._parser()._actions for flag in action.option_strings}
    assert named and named <= taken, named - taken
    # The host route names its listing and its filing.
    host = text.split("## On a host that starts agents itself", 1)[1]
    assert "--defaults --council NAME --host" in host and "--file-answer" in host
