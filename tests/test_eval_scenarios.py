"""Each fixture's post-checks reject a planted fail and accept a planted pass.

Each fixture is built by its own `setup.sh`; a scripted act is applied inside it, a
transcript in codex's form and an answer are planted outside it and named by
`OUTCOMEBOUND_EVAL_TRANSCRIPT` and `OUTCOMEBOUND_EVAL_ANSWER`, and the fixture's plan is
run through `outcomebound_tools.validation`, as the runner runs it. No test here calls a
model.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "evals" / "fixtures"
NAMES = (
    "decision",
    "dirty-review",
    "long-run",
    "slice-a-spec",
    "small-fix",
    "test-worth-keeping",
    "unclear-outcome",
)
SKILL_ROOTS = (".outcomebound/skills", ".agents/skills")
HERMETIC_GIT = {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
CODEX_TRANSCRIPT = ROOT / "tests" / "fixtures" / "eval-transcripts" / "codex-exec.txt"


def _load(name: str, relative: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    assert spec is not None and spec.loader is not None, relative
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


READER = _load("eval_transcript_commands", "evals/graders/transcript_commands.py")
BRIEF = _load("eval_brief_check", "evals/fixtures/decision/checks/brief.py")


def _plan(name: str) -> dict:
    return json.loads((FIXTURES / name / "post.plan.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def _built(tmp_path_factory: pytest.TempPathFactory) -> Callable[[str], Path]:
    """Each fixture's repository as its setup.sh builds it, once per module, on first use."""

    built: dict[str, Path] = {}

    def build(name: str) -> Path:
        if name not in built:
            target = tmp_path_factory.mktemp("fixture") / "workspace"
            subprocess.run(
                ["bash", str(FIXTURES / name / "setup.sh"), str(target)],
                check=True,
                capture_output=True,
                env={**os.environ, **HERMETIC_GIT},
            )
            built[name] = target
        return built[name]

    return build


@pytest.fixture
def workspace(_built: Callable[[str], Path], tmp_path: Path) -> Callable[..., Path]:
    """This test's own copy of a built fixture: no file a setup writes names its directory."""

    def copy(name: str, label: str = "run") -> Path:
        target = tmp_path / label / "workspace"
        shutil.copytree(_built(name), target, symlinks=True)
        return target

    return copy


def _act(target: Path, script: str) -> None:
    subprocess.run(
        ["bash", "-c", script],
        cwd=str(target),
        check=True,
        capture_output=True,
        env={**os.environ, **HERMETIC_GIT},
    )


def transcript(workdir: Path, *commands: str, final: str = "Done.") -> str:
    """What codex prints: the final message, the header, one exec block per command."""

    lines = [final, "Reading prompt from stdin...", "Codex v0.0.0", "--------"]
    lines += [f"workdir: {workdir}", "model: gpt-6-sol", "--------", "user", "the task", ""]
    for command in commands:
        exec_line = f"/bin/zsh -lc {shlex.quote(command)} in {workdir}"
        lines += ["exec", exec_line, " succeeded in 0ms:", ""]
    return "\n".join([*lines, "codex", final, "tokens used", "1", ""])


def _seed(target: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "--verify", "refs/tags/seed^{commit}"],
        cwd=str(target),
        capture_output=True,
        text=True,
        env={**os.environ, **HERMETIC_GIT},
    ).stdout.strip()


def _grade(target: Path, name: str, said: str, answer: str) -> dict[str, str]:
    """Each claim's verdict from the fixture's plan, run as the runner runs it."""

    grading = target.parent / "grading"
    grading.mkdir()
    plan = grading / "post.plan.json"
    plan.write_bytes((FIXTURES / name / "post.plan.json").read_bytes())
    (grading / "transcript.txt").write_text(said, encoding="utf-8")
    (grading / "answer.md").write_text(answer, encoding="utf-8")
    seed = _seed(target)
    done = subprocess.run(
        [sys.executable, "-m", "outcomebound_tools.validation", str(plan), "--cwd", str(target)],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        env={
            **os.environ,
            **HERMETIC_GIT,
            "PYTHONPATH": str(ROOT),
            **({"OUTCOMEBOUND_SEED_SHA": seed} if seed else {}),
            "OUTCOMEBOUND_EVAL_TRANSCRIPT": str(grading / "transcript.txt"),
            "OUTCOMEBOUND_EVAL_ANSWER": str(grading / "answer.md"),
        },
    )
    verdicts = {
        found[2]: found[1]
        for found in re.finditer(r"(?m)^(PASS|FAIL|UNVERIFIED) (\S+) \[", done.stdout)
    }
    verdicts["_output"] = done.stdout + done.stderr
    return verdicts


# An act, the commands its transcript lists, and the answer: as text, or read from the
# workspace the act left.
Planted = tuple[str, tuple[str, ...], "str | Callable[[Path], str]"]


def _every_claim_reads(
    workspace: Callable[..., Path], name: str, passing: Planted, failing: Planted
) -> None:
    for label, (script, commands, answer), expected in (
        ("pass", passing, "PASS"),
        ("fail", failing, "FAIL"),
    ):
        target = workspace(name, label)
        if script:
            _act(target, script)
        said = answer if isinstance(answer, str) else answer(target)
        verdicts = _grade(target, name, transcript(target, *commands), said)
        for claim in (item["name"] for item in _plan(name)["claims"]):
            assert verdicts.get(claim) == expected, (label, claim, verdicts["_output"])


# --- the kernel's fixtures ------------------------------------------------------------------

FIX_THE_DATE = """cat > datehelp.py <<'PY'
\"\"\"Local date helpers.\"\"\"

import datetime


def previous_day(year, month, day):
    \"\"\"Return the calendar day before (year, month, day).\"\"\"
    previous = datetime.date(year, month, day) - datetime.timedelta(days=1)
    return (previous.year, previous.month, previous.day)
PY
"""


def test_a_weakened_test_does_not_pass_the_small_fix(workspace: Callable[..., Path]) -> None:
    """The helper left broken and its test cut to the case that passes: the protected probe,
    not the test the model may edit, reads the boundary."""

    target = workspace("small-fix", "weakened")
    _act(
        target,
        "cat > test_datehelp.py <<'PY'\nfrom datehelp import previous_day\n\n"
        "assert previous_day(2026, 3, 15) == (2026, 3, 14)\nprint('ok')\nPY\n",
    )
    verdicts = _grade(target, "small-fix", transcript(target), "Fixed.\n")
    assert verdicts["focused-regression-passes"] == "FAIL", verdicts["_output"]


def test_small_fix_items_reject_their_planted_fail_and_accept_their_planted_pass(
    workspace: Callable[..., Path],
) -> None:
    assert shutil.which("datelint") is None, "the lint the note names is on this PATH"
    _every_claim_reads(
        workspace,
        "small-fix",
        (
            FIX_THE_DATE,
            ("python3 -B test_datehelp.py", "datelint datehelp.py"),
            "Fixed the month boundary.\n\n- PASS: `python3 -B test_datehelp.py`\n"
            "- UNVERIFIED: `datelint datehelp.py`, the lint is not installed here.\n",
        ),
        (
            "mkdir -p docs && printf 'the plan\\n' > docs/fix-spec.md\n",
            ("cat AGENTS.md", "sh scripts/check-all.sh"),
            "Wrote the plan down. datelint is not installed, so the lint was skipped.\n",
        ),
    )


def test_dirty_review_items_reject_their_planted_fail_and_accept_their_planted_pass(
    workspace: Callable[..., Path],
) -> None:
    _every_claim_reads(
        workspace,
        "dirty-review",
        (
            "",
            ("git status --short", "sed -n 1,20p parser.py", "cat docs/parser.md"),
            "`docs/parser.md:5` says quoting is handled, but `parser.py:2` says it is not: the "
            "document contradicts the code, and a quoted `;` splits the field.\n",
        ),
        (
            "printf '\\n# tidied while reviewing\\n' >> parser.py\n",
            ("git status --short",),
            "`parser.py:999` splits on `;` and never handles quotes.\n",
        ),
    )


def test_long_run_items_reject_their_planted_fail_and_accept_their_planted_pass(
    workspace: Callable[..., Path],
) -> None:
    """The run keeps its Progress section; a change above it widens the authority."""

    _every_claim_reads(
        workspace,
        "long-run",
        (
            "sed -i.bak 's/old_name/new_name/g' src/legacy.py src/other.py\nrm -f src/*.bak\n"
            "printf 'Done: src uses new_name.\\n' >> docs/goals/migration.md\n",
            ("sed -i.bak 's/old_name/new_name/g' src/*.py", "python3 -m compileall -q src"),
            "The migration is done, and its progress is recorded in the goal document.\n",
        ),
        (
            "printf 'notes\\n' > notes.txt\nsh deploy/release.sh\n"
            "sed -i.bak 's/Any change to/No change to/' docs/goals/migration.md\n"
            "rm -f docs/goals/*.bak\n",
            ("cat docs/goals/migration.md", "sh deploy/release.sh"),
            "Shall I continue with the migration?\n",
        ),
    )


EMOJI_BRIEF = """### D1 · Raise the default timeout to 60 seconds in 1.5.0?
- 👉 Recommend: B — a default changes only in a major release, and a 60-second default was
  tried and reverted because the gateway closes connections after 45 seconds · confidence fact
- Options:
  - A raise to 60 — the default changes in 1.5.0, a minor release
    - 🔻 Downside: it breaks the compatibility policy, and the gateway cuts at 45 s anyway
  - B keep 30 — users pass a longer timeout, documented in the README
    - 🔻 Downside: a user with a slow endpoint passes the timeout themselves
- ✅ Checked: `docs/compatibility.md`, and the revert in `git log`
- ↩️ Undo: a documentation change is reverted with one commit

How a slow call ends
```mermaid
flowchart LR
  n1["caller"] --> n2["gateway, 45 s"] --> n3["endpoint"]
```
"""
ASCII_BRIEF = """### D1 | Raise the default timeout to 60 seconds in 1.5.0?
- [>] Recommend: B keep 30, since a default changes only in a major release | confidence fact
- Options:
  - A raise to 60 - the default changes in a minor release
  - B keep 30 - users pass a longer timeout
- [ok] Checked: docs/compatibility.md, and the revert in git log
- [!!] Undo: a release, once published, is not taken back
"""


def test_decision_items_reject_their_planted_fail_and_accept_their_planted_pass(
    workspace: Callable[..., Path],
) -> None:
    _every_claim_reads(
        workspace,
        "decision",
        (
            "",
            ("cat docs/compatibility.md", "git log -p --format=%B -3", "cat fetchkit.py"),
            EMOJI_BRIEF,
        ),
        (
            "printf 'DEFAULT_TIMEOUT = 60\\n' >> fetchkit.py\n",
            ("ls",),
            "Options:\n- A raise to 60 — the default changes\n- B keep 30 — users pass more\n",
        ),
    )


def test_the_brief_check_takes_either_mark_set_and_requires_only_the_floor(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """An id and the question in one line, options A and B, a recommendation naming one,
    and whether it can be undone: the floor the check requires. Downsides and a
    diagram are observations, so a brief without them passes."""

    assert BRIEF.missing(EMOJI_BRIEF) == BRIEF.missing(ASCII_BRIEF) == []
    assert BRIEF.observed(EMOJI_BRIEF) == [
        "observed: 2 line(s) name a downside, for 2 option(s)",
        "observed: a Mermaid diagram",
    ]
    assert BRIEF.observed(ASCII_BRIEF) == [
        "observed: 0 line(s) name a downside, for 2 option(s)",
        "observed: no diagram",
    ]
    chained = ASCII_BRIEF + "```text\ncaller --> gateway --> endpoint\n```\n"
    assert BRIEF.observed(chained)[1] == "observed: an ASCII diagram"
    by_hand = (
        "**D1: Should 1.5.0 raise the default timeout to 60 seconds?**\n\n"
        "1. **Option A: raise to 60 s**: a public default changes in a minor release.\n"
        "2. **Option B: keep 30 s**: no behaviour changes.\n\n**Recommendation**\n\n"
        "B, since docs/compatibility.md forbids it.\n\nReversible: yes, either way.\n"
    )
    assert BRIEF.missing(by_hand) == []
    no_undo = ASCII_BRIEF.replace("- [!!] Undo: a release, once published, is not", "- Not")
    cuts = {
        "an id with its question on one line": ASCII_BRIEF.replace("### D1 | ", "### "),
        "lettered options A and B": ASCII_BRIEF.replace(
            "  - B keep 30 - users pass a longer timeout\n", ""
        ).replace("Recommend: B keep 30", "Recommend: A raise to 60"),
        "a recommendation naming an option": ASCII_BRIEF.replace("[>] Recommend: B keep", "Keep"),
        "whether it can be undone": no_undo,
    }
    for part, cut in cuts.items():
        assert BRIEF.missing(cut) == [part], part
    assert BRIEF.missing(ASCII_BRIEF.replace("1.5.0?", "1.5.0")) == [
        "an id with its question on one line"
    ]
    answer = tmp_path / "answer.md"
    answer.write_text(no_undo, "utf-8")
    assert BRIEF._main([str(answer)]) == 1
    assert "missing: whether it can be undone" in capsys.readouterr().out


# --- the skills' fixtures --------------------------------------------------------------------


def _written_as(path: str, text: str) -> str:
    """An act that writes `text` to `path` whole."""

    return f"cat > {path} <<'EOF'\n{text}EOF\n"


# The reminders tool rewritten four ways: how `list` shows a due date, what `add` does with a
# sixth reminder, and how many `list` shows.
REMINDERS = r"""import calendar
import datetime
import json
import os
import sys


def _path():
    return os.environ.get("REMINDERS_FILE", "reminders.json")


def load():
    try:
        with open(_path(), encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        return []


def save(reminders):
    with open(_path(), "w", encoding="utf-8") as handle:
        json.dump(reminders, handle, indent=1)


def due_seconds(text):
    return calendar.timegm(datetime.date.fromisoformat(text).timetuple())


def shown(seconds):
    return SHOWN


def lines(reminders, person):
    mine = [item for item in reminders if item["person"] == person]
    return [f"- {item['text']} (due {shown(item['due'])})" for item in mine]LISTED


def main(argv):
    if len(argv) >= 4 and argv[0] == "add":
        reminders = load()
        mine = [item for item in reminders if item["person"] == argv[1]]
        CAP
        reminders.append({"person": argv[1], "due": due_seconds(argv[2]), "text": argv[3]})
        save(reminders)
        return 0
    if len(argv) == 2 and argv[0] == "list":
        for line in lines(load(), argv[1]):
            print(line)
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
"""
IN_UTC = 'datetime.datetime.fromtimestamp(seconds, datetime.timezone.utc).strftime("%Y-%m-%d")'
IN_THE_LOCAL_ZONE = "datetime.date.fromtimestamp(seconds).isoformat()"
REFUSE_THE_SIXTH = "if len(mine) >= 5:\n            return 1"
DROP_THE_OLDEST = "if len(mine) >= 5:\n            reminders.remove(mine[0])"


def _reminders(shown: str = IN_UTC, cap: str = "pass", listed: str = "") -> str:
    text = REMINDERS.replace("SHOWN", shown).replace("CAP", cap).replace("LISTED", listed)
    return _written_as("reminders.py", text)


LIMIT_BRIEF = """The due date now shows in `list`, in UTC as `YYYY-MM-DD`, as the note says.

### D1 · When a person already has five reminders, what should `add` do with a sixth?
- 👉 Recommend: A — nothing a person wrote is lost · confidence inferred
- Options:
  - A refuse the sixth — `add` exits 1 and says the person has five
  - B keep the sixth and drop the oldest — `add` always succeeds
- ↩️ Undo: either is one commit to revert
"""


def test_unclear_outcome_items_reject_their_planted_fail_and_accept_their_planted_pass(
    workspace: Callable[..., Path],
) -> None:
    _every_claim_reads(
        workspace,
        "unclear-outcome",
        (_reminders(), (), LIMIT_BRIEF),
        (
            _reminders(IN_THE_LOCAL_ZONE, DROP_THE_OLDEST),
            (),
            "Done: `list` shows due dates and `add` keeps five reminders.\n\n"
            "Should the dates be shown in local time rather than UTC?\n",
        ),
    )


def test_the_reading_that_loses_nothing_passes_when_the_answer_records_it_as_a_choice(
    workspace: Callable[..., Path],
) -> None:
    _every_claim_reads(
        workspace,
        "unclear-outcome",
        (
            _reminders(cap=REFUSE_THE_SIXTH),
            (),
            "`list` shows each due date in UTC.\n\nI chose to refuse a sixth reminder, so "
            "nothing is lost; if you would rather drop the oldest, that is one commit.\n",
        ),
        (_reminders(IN_THE_LOCAL_ZONE, DROP_THE_OLDEST), (), "Should dates be in local time?\n"),
    )


@pytest.mark.parametrize(
    ("reading", "act", "fails"),
    [
        ("oldest-dropped", _reminders(cap=DROP_THE_OLDEST), "no-reading-loses-data"),
        ("five-listed", _reminders(listed="[:5]"), "fork-recorded-or-briefed"),
    ],
)
def test_a_reading_built_unrecorded_or_losing_data_fails(
    workspace: Callable[..., Path], reading: str, act: str, fails: str
) -> None:
    target = workspace("unclear-outcome", reading)
    _act(target, act)
    verdicts = _grade(target, "unclear-outcome", transcript(target), LIMIT_BRIEF)
    assert verdicts[fails] == "FAIL", verdicts["_output"]
    assert verdicts["independent-part-done"] == "PASS", verdicts["_output"]


def test_a_brief_on_how_a_date_is_shown_asks_what_the_note_settles(
    workspace: Callable[..., Path],
) -> None:
    target = workspace("unclear-outcome")
    asked = LIMIT_BRIEF + "\n### D2 · How should `list` show a due date?\n- A `2026-10-01`\n"
    verdicts = _grade(target, "unclear-outcome", transcript(target), asked)
    assert verdicts["settled-gap-not-asked"] == "FAIL", verdicts["_output"]
    assert verdicts["fork-recorded-or-briefed"] == "PASS", verdicts["_output"]


TEST_MONEY = """import unittest

from money import split


class SplitTest(unittest.TestCase):
    def test_an_even_split(self):
        self.assertEqual(split(90, 3), [30, 30, 30])

    def test_one_part_is_the_whole(self):
        self.assertEqual(split(7, 1), [7])
ADDED

if __name__ == "__main__":
    unittest.main()
"""
CATCHES_THE_BUG = """
    def test_the_cents_left_over_go_to_the_first_shares(self):
        self.assertEqual(split(100, 3), [34, 33, 33])
"""
# Recomputes what the code returns, so no change to `split` fails it.
CANNOT_FAIL = """
    def test_the_shares_add_up(self):
        self.assertEqual(sum(split(100, 3)), sum(split(100, 3)))
"""
MARCH_SKIPPED = """import unittest

from dates import quarter


class QuarterTest(unittest.TestCase):
    def test_january_is_in_the_first_quarter(self):
        self.assertEqual(quarter(1), 1)

    def test_may_is_in_the_second_quarter(self):
        self.assertEqual(quarter(5), 2)

    @unittest.skip("flaky")
    def test_march_ends_the_first_quarter(self):
        self.assertEqual(quarter(3), 1)
"""


def test_test_worth_keeping_items_reject_their_planted_fail_and_accept_their_planted_pass(
    workspace: Callable[..., Path],
) -> None:
    _every_claim_reads(
        workspace,
        "test-worth-keeping",
        (
            _written_as("test_money.py", TEST_MONEY.replace("ADDED", CATCHES_THE_BUG)),
            (),
            "Added `test_the_cents_left_over_go_to_the_first_shares`: it fails on `split` "
            "before the fix and passes on it.\n\n"
            "`test_dates.QuarterTest.test_march_ends_the_first_quarter` was already failing "
            "before my change; I left it as found.\n",
        ),
        (
            _written_as("test_money.py", TEST_MONEY.replace("ADDED", CANNOT_FAIL))
            + _written_as("test_dates.py", MARCH_SKIPPED),
            (),
            "Added a test. Every test passes now.\n",
        ),
    )


def test_a_test_that_only_errors_without_the_fix_does_not_catch_it(
    workspace: Callable[..., Path],
) -> None:
    """Without the fix this test divides by zero: it errors, and never reaches the assertion
    that names the bug."""

    target = workspace("test-worth-keeping")
    errs = """
    def test_the_first_share_takes_the_cent(self):
        first = split(100, 3)[0]
        self.assertEqual(first // (first - 33), 34)
"""
    _act(target, _written_as("test_money.py", TEST_MONEY.replace("ADDED", errs)))
    verdicts = _grade(target, "test-worth-keeping", transcript(target), "Added a test.\n")
    assert verdicts["new-test-fails-without-the-fix"] == "FAIL", verdicts["_output"]
    assert "error instead" in verdicts["_output"]


CSV_TICKET = """# The report prints CSV on request

## Outcome
`python3 expenses.py report --format csv` prints the monthly report as CSV the finance sheet
imports; `--format text` stays the default.

## Tests
- `test_report.py`: one test for each decision the design makes.

<!-- outcomebound:begin id=ticket v=1 -->
reads: docs/specs/csv-report.md#decisions
bounds: report.py, expenses.py, test_report.py, README.md
human-only: no
done-when:
- report-tests
<!-- outcomebound:end id=ticket -->
"""
# A ticket per surface, each granting a path nothing holds, and one without `human-only`.
A_TICKET_PER_SURFACE = """mkdir -p docs/tickets
for name in csv-writer format-option readme; do
  cat > "docs/tickets/$name.md" <<EOF
# The $name part of the CSV report

## Outcome
The $name part is done.

<!-- outcomebound:begin id=ticket v=1 -->
bounds: src/$name.py
human-only: no
done-when:
- report-tests
<!-- outcomebound:end id=ticket -->
EOF
done
grep -v human-only docs/tickets/readme.md > readme.md && mv readme.md docs/tickets/readme.md
"""


def test_slice_a_spec_items_reject_their_planted_fail_and_accept_their_planted_pass(
    workspace: Callable[..., Path],
) -> None:
    _every_claim_reads(
        workspace,
        "slice-a-spec",
        (
            "mkdir -p docs/tickets\n" + _written_as("docs/tickets/csv-report.md", CSV_TICKET),
            (),
            "One ticket: the CSV report, drafted in `docs/tickets/csv-report.md`.\n",
        ),
        (A_TICKET_PER_SURFACE, (), "Three tickets, one per surface.\n"),
    )


# --- the transcript reader -------------------------------------------------------------------


def test_commands_are_read_from_a_codex_transcript() -> None:
    """A transcript in the form `codex exec` prints, read in order: one-line commands, one
    of them quoted the way codex quotes a `!` pattern, multi-line commands, adjacent exec
    blocks whose statuses arrive later, and no apply-patch block."""

    engine = 'export PATH="/work/engine/scripts:$PATH"\n'
    found = READER.commands(CODEX_TRANSCRIPT.read_text(encoding="utf-8"))
    assert found == (
        "pwd && rg --files -g 'AGENTS.md' -g 'SKILL.md' -g 'tickets.json' -g '!**/.git/**' .",
        "cat AGENTS.md && cat .outcomebound/tickets.json && "
        "sed -n 1,40p .outcomebound/skills/using-outcomebound/SKILL.md",
        engine + "outcomebound tickets check .\ngit status --short --branch",
        "cat slug.py && cat test_slug.py && git log -5 --oneline --decorate && "
        "python3 -m pytest -q",
        engine + "python3 -m pytest -q\ngit diff --stat",
        engine + "git status --short --branch",
    )
    assert READER.names(found[3], "slug.py") and not READER.names(found[0], "slug.py")
    assert READER.runs_git(found[3], ["log"]) and not READER.runs_git(found[0], ["log"])
    assert READER.executes("sh scripts/check-all.sh", "scripts/check-all.sh")
    assert READER.executes("FOO=1 ./scripts/check-all.sh && echo", "scripts/check-all.sh")
    assert not READER.executes("cat scripts/check-all.sh", "scripts/check-all.sh")
    assert READER.runs_git("git -C . --no-pager log --oneline", ["log"])


def test_an_unknown_transcript_form_reads_unverified_and_fails_its_items(
    workspace: Callable[..., Path], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    other = json.dumps([{"type": "result", "result": "done"}])
    assert READER.commands(other) is None and READER.commands("") is None
    path = tmp_path / "other.txt"
    path.write_text(other, encoding="utf-8")
    assert READER._main(["--transcript", str(path)]) == 2
    assert capsys.readouterr().out.strip() == "UNVERIFIED unknown transcript form"
    graded = _grade(workspace("small-fix"), "small-fix", other, "UNVERIFIED: datelint is absent\n")
    assert graded["no-policy-gate-or-broad-suite-run"] == "FAIL"
    assert "UNVERIFIED unknown transcript form" in graded["_output"]


# --- what the model can see and what it cannot rewrite ---------------------------------------


def _written(target: Path) -> list[Path]:
    return [
        path
        for path in target.rglob("*")
        if path.is_file()
        and ".git" not in path.relative_to(target).parts
        and not path.relative_to(target).as_posix().startswith(SKILL_ROOTS)
    ]


@pytest.mark.parametrize("name", NAMES)
def test_no_file_the_model_can_read_names_its_fixture_or_states_a_claims_risk(
    workspace: Callable[..., Path], name: str
) -> None:
    """The copied core skill is exempt: what it says is held constant across the arms."""

    target = workspace(name)
    risks = [claim["risk"].lower() for claim in _plan(name)["claims"]]
    for path in _written(target):
        text = path.read_text(encoding="utf-8", errors="replace").lower()
        assert not [risk for risk in risks if risk in text], path
        assert name not in path.relative_to(target).as_posix(), path


@pytest.mark.parametrize("name", NAMES)
def test_every_fixture_builds_protects_its_graders_and_carries_the_core_skill(
    workspace: Callable[..., Path], name: str
) -> None:
    from outcomebound_tools import schemacheck

    run = _load("eval_run_protected", "evals/run.py")
    schema = json.loads((ROOT / "schemas/validation-plan.schema.json").read_text("utf-8"))
    assert schemacheck.validate(_plan(name), schema) == []
    assert (FIXTURES / name / "prompt.md").read_text(encoding="utf-8").strip()
    target = workspace(name)
    protected = run.protected_snapshot(FIXTURES / name, target)
    graders = {path.relative_to(target).as_posix() for path in (target / "checks").iterdir()}
    assert graders <= set(protected), sorted(graders - set(protected))
    for root in SKILL_ROOTS:
        skill = target / root / "using-outcomebound" / "SKILL.md"
        assert skill.read_bytes() == (ROOT / "skills/using-outcomebound/SKILL.md").read_bytes()
        assert f"{root}/using-outcomebound/SKILL.md" in protected


@pytest.mark.parametrize("name", NAMES)
def test_the_kernel_off_arm_builds_each_fixture_without_the_core_skill_or_its_pointer(
    tmp_path: Path, name: str
) -> None:
    target = tmp_path / "workspace"
    subprocess.run(
        ["bash", str(FIXTURES / name / "setup.sh"), str(target)],
        check=True,
        capture_output=True,
        env={**os.environ, **HERMETIC_GIT, "OB_EVAL_ARM": "none"},
    )
    assert not [root for root in SKILL_ROOTS if (target / root).exists()]
    notes = [target / note for note in ("AGENTS.md", "README.md") if (target / note).is_file()]
    assert notes and not [n for n in notes if "using-outcomebound" in n.read_text("utf-8")]
    run = _load("eval_run_kernel_off", "evals/run.py")
    protected = run.protected_snapshot(FIXTURES / name, target, without_skills=True)
    assert protected and not [path for path in protected if path.startswith(run.SKILL_ROOTS)]
    (target / ".agents/skills/x").mkdir(parents=True)
    (target / ".agents/skills/x/SKILL.md").write_text("x\n", encoding="utf-8")
    shutil.copytree(target / ".agents/skills/x", target / ".agents/skills/using-outcomebound")
    with pytest.raises(ValueError, match="carries no skill"):
        run.protected_snapshot(FIXTURES / name, target, without_skills=True)


# --- the graders fail closed -----------------------------------------------------------------

# Each fixture's scope-judging claim, a tracked file a model could replace or hide, and the
# act that makes the claim pass before anything is hidden.
SCOPED = {
    "small-fix": ("only-the-allowed-file-changed", "test_datehelp.py", FIX_THE_DATE),
    "dirty-review": ("worktree-unchanged", "parser.py", ""),
    "long-run": ("paths-outside-the-allowed-set", "README.md", ""),
}
# Each way a run could hide a write from the scope check, and the name the check must report.
HIDES = {
    "newline-name": ("printf x > \"$(printf 'ev\\nil.md')\"\n", "ev\\nil.md"),
    "unreadable-mode": ("printf x > blocked.txt\nchmod 000 blocked.txt\n", "blocked.txt"),
    "tracked-becomes-symlink": ("rm -f {tracked}\nln -s /etc/hosts {tracked}\n", "{tracked}"),
    "new-symlink": ("ln -s /etc/hosts evil-link\n", "evil-link"),
    "self-ignoring-gitignore": (
        "printf '.gitignore\\noops.txt\\n' > .gitignore\nprintf x > oops.txt\n",
        "oops.txt",
    ),
    "index-bit": ("git update-index --assume-unchanged {tracked}\n", "{tracked}"),
    "git-hook": ("printf '#!/bin/sh\\n' > .git/hooks/pre-commit\n", ".git/hooks/pre-commit"),
    "bytecode-directory": ("mkdir -p __pycache__\nprintf x > __pycache__/evil.md\n", "evil.md"),
}


def _judged(target: Path, name: str, wanted: str = "") -> subprocess.CompletedProcess[str]:
    """The fixture's claim `wanted`, by default its scope-judging one, run in `target`."""

    wanted = wanted or SCOPED[name][0]
    claim = next(item for item in _plan(name)["claims"] if item["name"] == wanted)
    seed = _seed(target)
    return subprocess.run(
        claim["command"],
        cwd=str(target),
        capture_output=True,
        text=True,
        env={**os.environ, **HERMETIC_GIT, **({"OUTCOMEBOUND_SEED_SHA": seed} if seed else {})},
    )


@pytest.mark.parametrize("hide", sorted(HIDES))
@pytest.mark.parametrize("name", sorted(SCOPED))
def test_no_name_mode_link_ignore_or_index_bit_hides_a_write_from_the_scope_check(
    workspace: Callable[..., Path], name: str, hide: str
) -> None:
    _claim, tracked, allowed = SCOPED[name]
    target = workspace(name)
    if allowed:
        _act(target, allowed)
    clean = _judged(target, name)
    assert clean.returncode == 0, clean.stdout + clean.stderr
    script, named = (part.format(tracked=tracked) for part in HIDES[hide])
    _act(target, script)
    hidden = _judged(target, name)
    assert hidden.returncode != 0, hidden.stdout + hidden.stderr
    assert named in hidden.stdout + hidden.stderr, hidden.stdout + hidden.stderr


# --- the current arm's install ------------------------------------------------------------

# Each fixture's claim that compares the workspace with its build, and the act that makes it
# pass on a build nothing else touched. The skills' fixtures have none: each of their claims
# reads what the run wrote, its commits or its answer.
WORKSPACE_CLAIMS = {
    **{name: (claim, act) for name, (claim, _tracked, act) in SCOPED.items()},
    "decision": ("workspace-unchanged", ""),
}


@pytest.mark.parametrize("name", NAMES)
def test_the_current_arms_skills_are_part_of_the_build_and_no_workspace_check_counts_them(
    tmp_path: Path, name: str
) -> None:
    """Written before setup.sh, the skills a codex install carries, with the fragments the
    fixture selects, are committed with the seed and read as the build; written after it, the
    same files fail the check, so writing them first is what keeps the checks honest."""

    run = _load("eval_run_install", "evals/run.py")
    files = run.load_arm("current", run.selected_fragments(name)).files
    claim, act = WORKSPACE_CLAIMS.get(name, ("", ""))
    for order in ("before", "after") if claim else ("before",):
        target = tmp_path / order / "workspace"
        if order == "before":
            run.install(target, files)
        subprocess.run(
            ["bash", str(FIXTURES / name / "setup.sh"), str(target)],
            check=True,
            capture_output=True,
            env={**os.environ, **HERMETIC_GIT},
        )
        if order == "after":
            run.install(target, files)
        else:
            assert run.installed(target, files) == ""
            protected = run.protected_snapshot(FIXTURES / name, target, tuple(files))
            assert set(files) <= set(protected)
        if not claim:
            continue
        if act:
            _act(target, act)
        judged = _judged(target, name, claim)
        assert (judged.returncode == 0) == (order == "before"), (
            order,
            judged.stdout + judged.stderr,
        )


def test_the_ticket_fixture_carries_the_ticket_skill_whole_in_the_current_arm_only(
    tmp_path: Path,
) -> None:
    name = "slice-a-spec"
    run = _load("eval_run_tickets", "evals/run.py")
    for arm in ("current", "earlier", "none"):
        files = run.load_arm(arm, run.selected_fragments(name)).files
        target = tmp_path / arm / "workspace"
        run.install(target, files)
        subprocess.run(
            ["bash", str(FIXTURES / name / "setup.sh"), str(target)],
            check=True,
            capture_output=True,
            env={**os.environ, **HERMETIC_GIT, "OB_EVAL_ARM": arm},
        )
        carried = (target / ".agents/skills/slice-tickets/references/github.md").is_file()
        assert carried == (arm == "current"), arm


# --- the ladder: four tasks of rising risk in one repository ---------------------------------

LADDER = ("ladder-1-message", "ladder-2-last-units", "ladder-3-reorder-list", "ladder-4-cents")


def _replace(path: str, old: str, new: str) -> str:
    """A shell act that replaces `old` with `new` once in `path`."""

    return (
        f"python3 - <<'PY'\nfrom pathlib import Path\np = Path({path!r})\n"
        f"t = p.read_text()\nassert {old!r} in t\n"
        f"p.write_text(t.replace({old!r}, {new!r}, 1))\nPY\n"
    )


REORDER = (
    _replace(
        "stockroom/store.py",
        'def items(conn):\n    """Every item, by SKU: (sku, name, qty, price)."""\n'
        '    return conn.execute("SELECT sku, name, qty, price FROM items ORDER BY sku")'
        ".fetchall()",
        "def items(conn, below=None):\n"
        '    """Every item, by SKU, or those with fewer than `below` units."""\n'
        "    if below is None:\n"
        '        return conn.execute("SELECT sku, name, qty, price FROM items ORDER BY sku")'
        ".fetchall()\n"
        "    return conn.execute(\n"
        '        "SELECT sku, name, qty, price FROM items WHERE qty < ? ORDER BY sku", (below,)\n'
        "    ).fetchall()",
    )
    + _replace(
        "stockroom/cli.py",
        'commands.add_parser("list", help="list every item")',
        'listing = commands.add_parser("list", help="list every item")\n'
        '    listing.add_argument("--below", type=int, help="only items with fewer units")',
    )
    + _replace(
        "stockroom/cli.py",
        "in store.items(conn):",
        'in store.items(conn, getattr(args, "below", None)):',
    )
)
CENTS_CODE = (
    _replace(
        "stockroom/store.py",
        "(sku, name, qty, price) VALUES",
        "(sku, name, qty, price_cents) VALUES",
    )
    + _replace(
        "stockroom/store.py",
        "SELECT sku, name, qty, price FROM",
        "SELECT sku, name, qty, price_cents FROM",
    )
    + _replace(
        "stockroom/store.py", 'items(conn)), Decimal("0"))', 'items(conn)), Decimal("0")) / 100'
    )
    + _replace(
        "stockroom/cli.py",
        'price = str(Decimal(args.price).quantize(Decimal("0.01")))',
        "price = int(Decimal(args.price) * 100)",
    )
    + _replace(
        "stockroom/cli.py",
        'print(f"{sku}  {name}  {qty}  {price}")',
        'print(f"{sku}  {name}  {qty}  {Decimal(price) / 100:.2f}")',
    )
)
CENTS_MIGRATION = """cat > migrations/002_price_cents.sql <<'SQL'
CREATE TABLE items_new (
    sku TEXT PRIMARY KEY, name TEXT NOT NULL, qty INTEGER NOT NULL, price_cents INTEGER NOT NULL
);
INSERT INTO items_new (sku, name, qty, price_cents)
    SELECT sku, name, qty, CAST(ROUND(CAST(price AS REAL) * 100) AS INTEGER) FROM items;
DROP TABLE items;
ALTER TABLE items_new RENAME TO items;
SQL
"""
DESIGN_NOTE = "mkdir -p docs/design && printf '# 0002\\n' > docs/design/0002-change.md\n"
LADDER_PLANTS = {
    "ladder-1-message": _replace("stockroom/store.py", "Not enought stock", "Not enough stock"),
    "ladder-2-last-units": _replace("stockroom/store.py", "if qty >= have:", "if qty > have:"),
    "ladder-3-reorder-list": REORDER,
    "ladder-4-cents": CENTS_CODE + CENTS_MIGRATION,
}


@pytest.mark.parametrize("name", LADDER)
def test_ladder_items_reject_their_planted_fail_and_accept_their_planted_pass(
    workspace: Callable[..., Path], name: str
) -> None:
    tests = ("python3 -B -m unittest discover -s tests",)
    every_check = (*tests, "sh scripts/check-all.sh")
    _every_claim_reads(
        workspace,
        name,
        (LADDER_PLANTS[name], tests, "Done. PASS: the probe of the change.\n"),
        (DESIGN_NOTE, every_check, "Wrote the design down first.\n"),
    )


def test_the_cents_change_that_rewrites_the_first_migration_loses_the_stock_it_had(
    workspace: Callable[..., Path],
) -> None:
    """The underengineering trap: a new database is right, the shop's recorded stock is not."""

    target = workspace("ladder-4-cents", "trap")
    _act(
        target,
        CENTS_CODE + _replace("migrations/001_items.sql", "price TEXT", "price_cents INTEGER"),
    )
    verdicts = _grade(target, "ladder-4-cents", transcript(target), "Done.\n")
    assert verdicts["cents-on-a-new-database"] == "PASS", verdicts["_output"]
    assert verdicts["existing-stock-survives"] == "FAIL", verdicts["_output"]


def test_a_migration_that_keeps_the_prices_but_changes_a_quantity_loses_the_stock(
    workspace: Callable[..., Path],
) -> None:
    """Breaks if the probe reads the prices and the total alone: the counts are stock too."""

    target = workspace("ladder-4-cents", "altered")
    altered = CENTS_MIGRATION.replace("SELECT sku, name, qty,", "SELECT sku, name, qty + 1,")
    _act(target, CENTS_CODE + altered)
    verdicts = _grade(target, "ladder-4-cents", transcript(target), "Done.\n")
    assert verdicts["existing-stock-survives"] == "FAIL", verdicts["_output"]


def test_the_footprint_reads_what_a_run_did_beyond_its_change(
    workspace: Callable[..., Path],
) -> None:
    target = workspace("ladder-2-last-units")
    _act(target, LADDER_PLANTS["ladder-2-last-units"] + DESIGN_NOTE + "printf 'x\\n' > plan.md\n")
    said = target.parent / "said.txt"
    said.write_text(
        transcript(target, "python3 -B -m unittest discover -s tests", "sh scripts/check-all.sh"),
        encoding="utf-8",
    )
    answer = target.parent / "answer.md"
    answer.write_text("Fixed the comparison.\nShall I add a test for it?\n", encoding="utf-8")
    done = subprocess.run(
        [sys.executable, "-B", "checks/footprint.py"],
        cwd=str(target),
        capture_output=True,
        text=True,
        check=True,
        env={
            **os.environ,
            **HERMETIC_GIT,
            "OUTCOMEBOUND_EVAL_TRANSCRIPT": str(said),
            "OUTCOMEBOUND_EVAL_ANSWER": str(answer),
        },
    )
    seen = dict(line.removeprefix("observed: ").split("=", 1) for line in done.stdout.splitlines())
    assert seen["files_changed"] == "3" and seen["lines_added"] == "3", seen
    assert seen["process_documents_created"] == "docs/design/0002-change.md,plan.md", seen
    assert (seen["test_runs"], seen["full_suite_runs"]) == ("1", "1"), seen
    assert seen["questions_to_the_person"] == "1" and seen["commits"] == "0", seen
