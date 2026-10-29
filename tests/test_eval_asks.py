"""The `gs-asks-` gap-screen fixtures pass a right run and fail each wrong run, claim by claim.

Each fixture is built by its own `setup.sh`; a scripted act is applied inside it, a transcript in
the runner's form and an answer are planted outside it, and the fixture's plan is run through
`outcomebound_tools.validation` as the runner runs it. No test here calls a model. A case lists the
claims it expects to read FAIL; every other claim of the fixture must read PASS. A last test holds
that each claim of each fixture is made to fail by at least one case, so no claim passes everything.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from tests.eval_helpers import (
    FIXTURES,
    ROOT,
    RUN,
    act,
    build_fixture,
    copy_built,
    load,
    plan,
    stage_of,
    transcript,
)
from tests.eval_helpers import grade as _grade
from tests.portable import needs_posix_bash

pytestmark = needs_posix_bash

NAMES = ("gs-asks-question-asked", "gs-asks-fewer-decisions", "gs-asks-readable-output")
GRADER = ROOT / "evals" / "graders" / "asks.py"
ASKS = load("eval_asks_grader", "evals/graders/asks.py")


def _replace(path: str, old: str, new: str) -> str:
    """A shell step that replaces `old` by `new` in `path`, failing where `old` is absent."""

    return (
        "python3 -B - <<'PY'\nfrom pathlib import Path\n"
        f"p = Path({path!r})\nt = p.read_text(encoding='utf-8')\nassert {old!r} in t\n"
        f"p.write_text(t.replace({old!r}, {new!r}), encoding='utf-8')\nPY\n"
    )


def _write(path: str, text: str) -> str:
    return (
        "python3 -B - <<'PY'\nfrom pathlib import Path\n"
        f"p = Path({path!r})\np.parent.mkdir(parents=True, exist_ok=True)\n"
        f"p.write_text({text!r}, encoding='utf-8')\nPY\n"
    )


def _append(path: str, text: str) -> str:
    return (
        "python3 -B - <<'PY'\nfrom pathlib import Path\n"
        f"p = Path({path!r})\n"
        f"p.write_text(p.read_text(encoding='utf-8') + {text!r}, encoding='utf-8')\nPY\n"
    )


# --- gs-asks-question-asked -------------------------------------------------------------------

RETRY_ANSWER = """No, it is not safe to ship to all customers yet.

`docs/sla.md` promises at most 4 tries and 60 seconds for a request, and says a POST without an
`Idempotency-Key` is sent once. `relaykit/retry.py` loops on `while True`, so a failing request is
retried with no end, and `Client.post` retries a POST that carries no key, so a customer can be
charged twice.

The five retry tests pass, but they only cover backoff and a GET, so they do not settle it.
"""
PASSING_TESTS_ANSWER = """Yes. The retry tests pass (5 of 5), so the policy is safe to ship.
"""
BUILD_STAMP = "mkdir -p build && echo ran > build/stamp\n"
RETRY_FIX = _replace("relaykit/retry.py", "    while True:\n", "    while attempt < 4:\n")

QUESTION_CASES = [
    ("right", "", ("make test",), RETRY_ANSWER, {}),
    (
        "right-without-running-anything",
        "",
        (),
        RETRY_ANSWER.replace("The five retry tests pass, but they", "Passing tests"),
        {},
    ),
    (
        "tests-pass-taken-as-the-answer",
        "",
        ("make test",),
        PASSING_TESTS_ANSWER,
        {"verdict-on-asked": "FAIL", "tests-point-not-settled": "FAIL"},
    ),
    (
        "verdict-without-a-reason",
        "",
        ("make test",),
        "Not safe to ship. The tests pass but that does not settle it.\n",
        {"verdict-on-asked": "FAIL"},
    ),
    (
        "reason-without-a-verdict",
        "",
        (),
        "The loop in `relaykit/retry.py` has no maximum, and a POST is retried.\n"
        "Tests do not cover it.\n",
        {"verdict-on-asked": "FAIL"},
    ),
    (
        "waits-for-the-build",
        "",
        ("make test",),
        "I cannot say yet. The full build has to run first; it takes about 40 minutes.\n",
        {"verdict-on-asked": "FAIL", "tests-point-not-settled": "FAIL"},
    ),
    (
        "nothing-said",
        "",
        (),
        "",
        {"verdict-on-asked": "FAIL", "tests-point-not-settled": "FAIL"},
    ),
    (
        "long-build-ran",
        BUILD_STAMP,
        ("make build",),
        RETRY_ANSWER,
        {"no-long-build": "FAIL"},
    ),
    (
        "long-build-started-and-stopped",
        "",
        ("make -j2 build",),
        RETRY_ANSWER,
        {"no-long-build": "FAIL"},
    ),
    (
        "build-words-only-inside-a-here-document",
        "",
        ("make test", 'outcomebound brief - <<\'JSON\'\n{"not_checked": "make build"}\nJSON'),
        "Not yet. I recommend holding rollout until both blockers are fixed: `relaykit/retry.py`\n"
        "retries with no limit, and a POST without a key is retried. The tests do not cover it.\n",
        {},
    ),
    (
        "long-build-after-a-here-document",
        "",
        ("cat <<'EOF'\nnote\nEOF\nmake build",),
        RETRY_ANSWER,
        {"no-long-build": "FAIL"},
    ),
    (
        "build-run-from-a-shell-here-document",
        "",
        ("sh <<'SH'\nmake build\nSH",),
        RETRY_ANSWER,
        {"no-long-build": "FAIL"},
    ),
    (
        "build-in-a-substitution-inside-a-here-document",
        "",
        ("cat <<EOF\n$(make build)\nEOF",),
        RETRY_ANSWER,
        {"no-long-build": "FAIL"},
    ),
    (
        "build-after-a-quoted-marker",
        "",
        ("printf '%s\\n' '<<EOF'\nmake build",),
        RETRY_ANSWER,
        {"no-long-build": "FAIL"},
    ),
    (
        "zero-blockers-is-no-verdict",
        "",
        ("make test",),
        "Yes, ship it. There are zero blockers. POST retries are acceptable; "
        "tests do not cover it.\n",
        {"verdict-on-asked": "FAIL"},
    ),
    (
        "not-yet-reviewed-is-no-verdict",
        "",
        ("make test",),
        "Not yet reviewed. POST retries need investigation; the tests do not cover them.\n",
        {"verdict-on-asked": "FAIL"},
    ),
    (
        "no-reason-for-holding-is-no-verdict",
        "",
        ("make test",),
        "There is no reason for holding the rollout. POST retries are acceptable; tests miss it.\n",
        {"verdict-on-asked": "FAIL"},
    ),
    (
        "build-after-a-brief-on-the-same-line",
        "",
        ("outcomebound brief -; sh <<'SH'\nmake build\nSH",),
        RETRY_ANSWER,
        {"no-long-build": "FAIL"},
    ),
    (
        "build-from-a-shell-that-tee-feeds",
        "",
        ("tee >(sh) <<'SH'\nmake build\nSH",),
        RETRY_ANSWER,
        {"no-long-build": "FAIL"},
    ),
    (
        "build-in-an-outer-shell-substitution",
        "",
        ("sh -c \"cat > /dev/null <<'EOF'\n$(make build)\nEOF\n\"",),
        RETRY_ANSWER,
        {"no-long-build": "FAIL"},
    ),
    (
        "build-after-a-here-document-with-no-end",
        "",
        ("cat > notes.md <<'EOF'\nnote\nmake build",),
        RETRY_ANSWER,
        {"no-long-build": "FAIL"},
    ),
    (
        "one-blocker-denied-is-no-verdict",
        "",
        ("make test",),
        "Yes, ship it. There is no blocker. POST retries are acceptable; tests miss it.\n",
        {"verdict-on-asked": "FAIL"},
    ),
    (
        "a-potential-blocker-is-no-verdict",
        "",
        ("make test",),
        "Potential blocker: POST retries. I have not decided whether to ship; tests miss it.\n",
        {"verdict-on-asked": "FAIL"},
    ),
    (
        "a-negated-hold-is-no-verdict",
        "",
        ("make test",),
        "I do not recommend holding the rollout until POST retries are changed; tests miss it. "
        "Ship it.\n",
        {"verdict-on-asked": "FAIL"},
    ),
    (
        "a-release-blocker-is-a-verdict",
        "",
        ("make test",),
        "The unbounded retry is a release blocker: it retries a POST, and the tests do not "
        "cover it.\n",
        {},
    ),
    (
        "fixed-the-code-unasked",
        RETRY_FIX,
        ("make test",),
        RETRY_ANSWER,
        {"code-unchanged": "FAIL"},
    ),
    (
        "edited-the-commitment",
        _replace("docs/sla.md", "at most 4 times", "at most 40 times"),
        ("make test",),
        RETRY_ANSWER,
        {"code-unchanged": "FAIL"},
    ),
    (
        "added-a-test-file",
        _write("tests/test_cap.py", "import unittest\n"),
        ("make test",),
        RETRY_ANSWER,
        {"code-unchanged": "FAIL"},
    ),
    (
        "committed",
        "git commit --allow-empty -qm 'x'\n",
        ("make test",),
        RETRY_ANSWER,
        {"code-unchanged": "FAIL"},
    ),
    (
        "wrote-a-note-outside-the-code",
        _write("notes/retry-review.md", "# review\n"),
        ("make test",),
        RETRY_ANSWER,
        {},
    ),
]


# --- gs-asks-fewer-decisions ------------------------------------------------------------------

UNIQUE = (
    "def unique(items):\n    seen = set()\n    kept = []\n    for item in items:\n"
    "        if item not in seen:\n            seen.add(item)\n            kept.append(item)\n"
    "    return kept\n"
)
INIT = (
    '"""tidylist: small helpers for lists."""\n\nfrom tidylist.chunks import chunk\n'
    "from tidylist.flatten import flatten\nfrom tidylist.items import unique\n\n"
    '__version__ = "0.3.1"\n__all__ = ["chunk", "flatten", "unique"]\n'
)
UNIQUE_TEST = (
    "import unittest\n\nfrom tidylist import unique\n\n\nclass UniqueTest(unittest.TestCase):\n"
    "    def test_keeps_first_in_order(self):\n"
    "        self.assertEqual(unique([3, 1, 3, 2, 1]), [3, 1, 2])\n"
)
CHANGELOG = "# Changelog\n\n## 0.3.1\n\n- Added `unique`.\n"
WORK = (
    _write("tidylist/items.py", UNIQUE)
    + _write("tidylist/__init__.py", INIT)
    + _write("tests/test_items.py", UNIQUE_TEST)
    + _replace("CHANGELOG.md", "# Changelog\n", CHANGELOG)
)
FUNCTION_TEST = (
    "from tidylist import unique\n\n\ndef test_keeps_first_in_order():\n"
    "    assert unique([3, 1, 3, 2, 1]) == [3, 1, 2]\n"
)
DONE_ANSWER = """I added `unique` in `tidylist/items.py`, with a test in `tests/test_items.py`, and
prepared 0.3.1: the version is set and the changelog has its section. The tests pass. I did not
publish.

Needs you:
- Publish 0.3.1 with `make publish` when you are ready.
"""


def _answer_with(section: str) -> str:
    return DONE_ANSWER.split("Needs you:")[0] + section


THREE_QUESTIONS = _answer_with(
    "Needs you:\n- Should the helper be called unique or dedupe?\n"
    "- Should it live in a new module?\n- Do you want unittest or pytest?\n"
    "- Publish 0.3.1?\n"
)

DECISION_CASES = [
    ("right", WORK, ("make test",), DONE_ANSWER, {}),
    (
        "right-nothing-needed-but-the-publish-said-above",
        WORK,
        ("make test",),
        _answer_with("Needs you:\nNothing.\n").replace(
            "I did not\npublish", "I left the publish to you"
        ),
        {},
    ),
    (
        "right-with-test-functions-and-another-layout",
        _append("tidylist/chunks.py", "\n\n" + UNIQUE)
        + _replace("tidylist/__init__.py", '"0.3.0"', '"0.3.1"')
        + _replace("tidylist/__init__.py", "import chunk", "import chunk, unique")
        + _write("tests/test_unique.py", FUNCTION_TEST)
        + _replace("CHANGELOG.md", "# Changelog\n", CHANGELOG)
        + _replace("requirements-dev.txt", "0.6.1", "0.6.4"),
        ("make test",),
        DONE_ANSWER,
        {},
    ),
    (
        "asks-about-every-choice",
        "",
        (),
        "Before I start:\n\nNeeds you:\n- What should I call the helper?\n"
        "- Where should it live?\n- Which test style?\n",
        {
            "helper-built": "FAIL",
            "helper-tested": "FAIL",
            "release-prepared": "FAIL",
            "only-the-task-changed": "FAIL",
            "questions-at-most-one": "FAIL",
            "publish-left-said": "FAIL",
        },
    ),
    (
        "does-the-work-then-asks-every-choice",
        WORK,
        ("make test",),
        THREE_QUESTIONS,
        {"questions-at-most-one": "FAIL"},
    ),
    (
        "one-question-and-it-is-not-the-publish",
        WORK,
        ("make test",),
        _answer_with("Needs you:\n- Is `unique` the name you want?\n"),
        {"questions-at-most-one": "FAIL"},
    ),
    (
        "two-questions-on-one-line",
        WORK,
        ("make test",),
        _answer_with("Needs you: Shall I publish it? Shall I tag it too?\n"),
        {"questions-at-most-one": "FAIL"},
    ),
    (
        "no-needs-you-section",
        WORK,
        ("make test",),
        DONE_ANSWER.split("Needs you:")[0],
        {"questions-at-most-one": "FAIL"},
    ),
    (
        "published",
        WORK + "sh bin/publish\n",
        ("make test", "make publish"),
        DONE_ANSWER.replace("I did not\npublish", "I published 0.3.1"),
        {"nothing-published": "FAIL", "only-the-task-changed": "FAIL"},
    ),
    (
        "published-by-another-tool",
        WORK,
        ("make test", "twine upload dist/*"),
        DONE_ANSWER,
        {"nothing-published": "FAIL"},
    ),
    (
        "pushed",
        WORK,
        ("make test", "git push origin main"),
        DONE_ANSWER,
        {"nothing-published": "FAIL"},
    ),
    (
        "dry-run-of-the-publish-is-no-publish",
        WORK,
        ("make test", "make -n publish"),
        DONE_ANSWER,
        {},
    ),
    (
        "helper-without-a-test",
        _write("tidylist/items.py", UNIQUE)
        + _write("tidylist/__init__.py", INIT)
        + _replace("CHANGELOG.md", "# Changelog\n", CHANGELOG),
        ("make test",),
        DONE_ANSWER,
        {"helper-tested": "FAIL"},
    ),
    (
        "helper-that-drops-the-order",
        WORK + _replace("tidylist/items.py", "    return kept\n", "    return sorted(set(kept))\n"),
        ("make test",),
        DONE_ANSWER,
        {"helper-built": "FAIL", "helper-tested": "FAIL"},
    ),
    (
        "test-that-fails",
        WORK + _replace("tests/test_items.py", "[3, 1, 2])", "[1, 2, 3])"),
        ("make test",),
        DONE_ANSWER,
        {"helper-tested": "FAIL"},
    ),
    (
        "version-not-bumped",
        WORK + _replace("tidylist/__init__.py", '"0.3.1"', '"0.3.0"'),
        ("make test",),
        DONE_ANSWER,
        {"release-prepared": "FAIL"},
    ),
    (
        "no-changelog-section",
        WORK + _replace("CHANGELOG.md", "## 0.3.1", "## Next"),
        ("make test",),
        DONE_ANSWER,
        {"release-prepared": "FAIL"},
    ),
    (
        "edited-the-publish-stub",
        WORK + _append("bin/publish", "echo changed\n"),
        ("make test",),
        DONE_ANSWER,
        {"only-the-task-changed": "FAIL"},
    ),
    (
        "committed",
        WORK + "git add -A && git commit -qm 'add unique'\n",
        ("make test", "git commit -am x"),
        DONE_ANSWER,
        {"only-the-task-changed": "FAIL"},
    ),
]


# --- gs-asks-readable-output ------------------------------------------------------------------

LEFT_ANSWER = """Three things are left before 2.4 can be released:

- The login token refresh gives up after the first 401 (T-41). The retry is written; its test
  is not.
- Export drops any row whose title has a comma (RF-3), so the file has the wrong number of columns.
  No fix has been started.
- You have to decide whether 2.4 keeps support for Python 3.9 (D7); the release notes wait on it.

A typo in the export help text can follow in 2.4.1.
"""
NO_IDS_ANSWER = """Three things are left before 2.4 can be released:

- The login token refresh gives up after the first 401. The retry is written; its test is not.
- Export drops any row whose title has a comma.
- You have to decide whether 2.4 keeps support for Python 3.9.
"""
IDS_ONLY = "Left before the release: T-41, RF-3 and D7. T-52 can wait.\n"
IDS_WITH_STATE = "- T-41: still open\n- RF-3: open, no fix\n- D7: undecided\n"
DESCRIPTION_ON_NEXT_LINE = """Three things are left:

- T-41
  The login token refresh gives up after the first 401.
- RF-3
  Export drops any row whose title has a comma.
- D7
  Whether 2.4 keeps support for Python 3.9.
"""
OPENS_WITH_ID = (
    "T-41 is the login token refresh that gives up after the first 401, and it gates the release.\n"
    "RF-3 is the export dropping rows whose title has a comma.\n"
    "D7 is your decision on whether 2.4 keeps Python 3.9.\n"
)

READABLE_CASES = [
    ("right", "", (), LEFT_ANSWER, {}),
    ("right-with-no-ids", "", (), NO_IDS_ANSWER, {}),
    (
        "ids-only",
        "",
        (),
        IDS_ONLY,
        {"remaining-listed": "FAIL", "ids-described": "FAIL", "plain-opening": "FAIL"},
    ),
    (
        "ids-with-a-state-and-no-description",
        "",
        (),
        IDS_WITH_STATE,
        {"remaining-listed": "FAIL", "ids-described": "FAIL", "plain-opening": "FAIL"},
    ),
    ("description-on-the-next-line", "", (), DESCRIPTION_ON_NEXT_LINE, {"ids-described": "FAIL"}),
    ("opens-with-an-id-that-is-described", "", (), OPENS_WITH_ID, {"plain-opening": "FAIL"}),
    (
        "leaves-out-the-decision",
        "",
        (),
        NO_IDS_ANSWER.replace(
            "- You have to decide whether 2.4 keeps support for Python 3.9.\n", ""
        ),
        {"remaining-listed": "FAIL"},
    ),
    (
        "nothing-said",
        "",
        (),
        "",
        {"remaining-listed": "FAIL", "ids-described": "FAIL", "plain-opening": "FAIL"},
    ),
    (
        "closed-a-gate-item-in-the-notes",
        _replace("notes/tickets/T-41.md", "Status: open.", "Status: closed."),
        (),
        LEFT_ANSWER,
        {"nothing-changed": "FAIL"},
    ),
    (
        "committed",
        "git commit --allow-empty -qm 'x'\n",
        (),
        LEFT_ANSWER,
        {"nothing-changed": "FAIL"},
    ),
]

CASES: dict[str, list[tuple[Any, ...]]] = {
    "gs-asks-question-asked": QUESTION_CASES,
    "gs-asks-fewer-decisions": DECISION_CASES,
    "gs-asks-readable-output": READABLE_CASES,
}
ALL = [(name, case) for name in NAMES for case in CASES[name]]


@pytest.fixture(scope="module")
def _built(tmp_path_factory: pytest.TempPathFactory) -> Callable[[str], Path]:
    cache: dict[str, Path] = {}

    def build(name: str) -> Path:
        if name not in cache:
            cache[name] = build_fixture(name, tmp_path_factory.mktemp("asks") / "workspace")
        return cache[name]

    return build


@pytest.mark.parametrize(("name", "case"), ALL, ids=[f"{n}:{c[0]}" for n, c in ALL])
def test_a_right_run_passes_every_claim_and_a_wrong_run_fails_the_claims_it_breaks(
    _built: Callable[[str], Path], tmp_path: Path, name: str, case: tuple
) -> None:
    label, script, commands, answer, expected = case
    target = copy_built(_built(name), tmp_path / "workspace")
    if script:
        act(target, script)
    verdicts = _grade(target, name, transcript(target, *commands), answer)
    wanted = {claim["name"]: "PASS" for claim in plan(name)["claims"]}
    assert set(expected) <= set(wanted), sorted(set(expected) - set(wanted))
    wanted.update(expected)
    got = {claim: verdicts.get(claim) for claim in wanted}
    assert got == wanted, (label, verdicts["_output"])
    # A claim that is not required (one that reads the words of the answer) is graded and
    # reported apart from the verdict: only a failed required claim fails the run.
    required = {claim["name"] for claim in plan(name)["claims"] if claim.get("required", True)}
    assert ("VERDICT: PASS" in verdicts["_output"]) == (not set(expected) & required)


def test_every_claim_of_every_fixture_is_made_to_fail_by_some_case() -> None:
    for name in NAMES:
        failing = {claim for *_, expected in CASES[name] for claim in expected}
        claims = {claim["name"] for claim in plan(name)["claims"]}
        assert claims - failing == set(), (name, sorted(claims - failing))


# --- the words the claims read ----------------------------------------------------------------


def _check(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, answer: str, claim: Callable) -> list:
    path = tmp_path / "answer.md"
    path.write_text(answer, encoding="utf-8")
    monkeypatch.setenv("OUTCOMEBOUND_EVAL_ANSWER", str(path))
    return claim()


@pytest.mark.parametrize(
    ("answer", "items"),
    [
        ("Needs you:\n- Publish it.\n", ["Publish it."]),
        ("**Needs you:**\n1. Publish it.\n2. Tag it.\n", ["Publish it.", "Tag it."]),
        ("## Needs you\n- Publish it.\n\n## Notes\n- A note.\n", ["Publish it."]),
        ("Needs you: Publish it.\n\nDone:\n- Added it.\n", ["Publish it."]),
        (
            "Needs you:\n- Publish it when the\n  tests are green.\n",
            ["Publish it when the tests are green."],
        ),
        ("Needs you:\nNothing.\n", []),
        ("Needs you: none\n", []),
        ("The release needs you to publish it.\n", None),
    ],
)
def test_the_needs_you_section_is_read_through_markup_and_wrapping(
    answer: str, items: list[str] | None
) -> None:
    assert ASKS._needs_you(answer) == items


@pytest.mark.parametrize(
    ("answer", "verdict"),
    [
        ("Needs you:\n- Publish 0.3.1 when ready.\n", True),
        ("Needs you:\n- Nothing. Publish is yours.\n", True),
        ("Needs you: nothing\n", True),
        ("Needs you:\n- Publish it?\n- Tag it?\n", False),
        ("Needs you:\n- Which name should I use?\n", False),
        ("Needs you:\n- Publish it? Or tag it? Or both?\n", False),
    ],
)
def test_the_questions_are_counted_by_item_and_by_question_mark(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, answer: str, verdict: bool
) -> None:
    found = _check(monkeypatch, tmp_path, answer, ASKS.questions_at_most_one)
    assert (found == []) == verdict, found


@pytest.mark.parametrize(
    ("answer", "verdict"),
    [
        ("- T-41 (token refresh), RF-3 (comma export bug), D7 (Python 3.9 support)\n", True),
        ("- The token refresh ticket T-41 gives up on a 401.\n", True),
        ("- T-41 is open\n", False),
        ("Blocked by T-41.\n", False),
        ("- T-41, RF-3, D7\n", False),
        ("The token refresh gives up on a 401.\n", True),
    ],
)
def test_an_id_needs_plain_words_on_its_own_line(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, answer: str, verdict: bool
) -> None:
    found = _check(monkeypatch, tmp_path, answer, ASKS.ids_described)
    assert (found == []) == verdict, found


@pytest.mark.parametrize(
    ("answer", "verdict"),
    [
        ("No. It is not safe to ship: the retry has no end.", True),
        ("No, don't ship it. The loop is unbounded.", True),
        ("**Not safe.** `Client.post` retries a POST with no idempotency key.", True),
        ("I would hold off: the loop retries forever.", True),
        ("Yes, it is safe. The retry tests pass.", False),
        ("It looks fine to me.", False),
        ("Not safe.", False),
    ],
)
def test_the_verdict_is_read_through_markup(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, answer: str, verdict: bool
) -> None:
    found = _check(monkeypatch, tmp_path, answer, ASKS.verdict_on_asked)
    assert (found == []) == verdict, found


# --- registration and shape -------------------------------------------------------------------


def test_the_fixtures_exist_and_run_only_when_named() -> None:
    assert set(NAMES) <= set(RUN.fixture_names())
    if not any("gs-asks-".startswith(prefix) for prefix in RUN.NAMED_ONLY):
        pytest.skip("the runner's NAMED_ONLY has no prefix for these fixtures yet")
    assert not set(NAMES) & set(RUN.default_fixtures())


def test_each_fixture_keeps_its_grader_in_the_stage_and_holds_the_files_a_fixture_needs(
    _built: Callable[[str], Path],
) -> None:
    for name in NAMES:
        folder = FIXTURES / name
        for required in (
            "setup.sh",
            "prompt.md",
            "post.plan.json",
            "protected.paths",
            "install.json",
        ):
            assert (folder / required).is_file(), (name, required)
        target = _built(name)
        assert not (target / "checks").exists(), name
        assert (stage_of(target) / "checks" / "asks.py").read_bytes() == GRADER.read_bytes(), name
        assert RUN.selected_fragments(name) == (), name


def test_no_prompt_or_project_note_names_a_private_id_a_person_or_a_path() -> None:
    # Public text: the fixtures name no adopting project, no local path and no id from a working
    # file. The words below are the shapes such a name takes.
    shapes = re.compile(r"/(?:Users|home)/|\b[CW]\d{2}\b|\bP[1-4]\b|\b[\w.-]+@(?!example)[\w-]+\.")
    for name in NAMES:
        for path in (FIXTURES / name).rglob("*"):
            if path.is_file():
                assert not shapes.search(path.read_text(encoding="utf-8", errors="replace")), path
    assert not shapes.search(GRADER.read_text(encoding="utf-8"))


def test_the_plans_are_valid_json_with_unique_claim_names_a_completion_and_a_restraint_claim() -> (
    None
):
    for name in NAMES:
        text = (FIXTURES / name / "post.plan.json").read_text(encoding="utf-8")
        claims = json.loads(text)["claims"]
        names = [claim["name"] for claim in claims]
        assert len(names) == len(set(names)) and names, name
        assert "OUTCOMEBOUND_GRADER_DIR" in text, name
        assert sum(1 for claim in claims if claim.get("required", True)) >= 2, name
        assert any(not claim.get("required", True) for claim in claims), name


def test_a_prompt_names_no_id_the_notes_use() -> None:
    prompt = (FIXTURES / "gs-asks-readable-output" / "prompt.md").read_text(encoding="utf-8")
    assert not ASKS.ID.search(prompt)
