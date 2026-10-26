"""The size fixtures pass a right run and fail each wrong run, claim by claim.

Each fixture is built by its own `setup.sh`; a scripted act is applied inside it, and the fixture's
plan is run through `outcomebound_tools.validation` as the runner runs it. No test here calls a
model. A case lists the claims it expects to read FAIL; every other claim of the fixture must read
PASS. A last test holds that each claim of each fixture is made to fail by at least one case, so no
claim passes everything.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path

import pytest

from tests.eval_helpers import FIXTURES, ROOT, RUN, act, build_fixture, copy_built, plan, stage_of
from tests.eval_helpers import grade as _grade
from tests.portable import needs_posix_bash

pytestmark = needs_posix_bash

NAMES = ("gs-size-overbuild", "gs-size-bug-class", "gs-size-risky-test")


def _write(path: str, text: str) -> str:
    return (
        "python3 -B - <<'PY'\nfrom pathlib import Path\n"
        f"p = Path({path!r})\np.parent.mkdir(parents=True, exist_ok=True)\n"
        f"p.write_text({text!r}, encoding='utf-8')\nPY\n"
    )


def _replace(path: str, old: str, new: str) -> str:
    return (
        "python3 -B - <<'PY'\nfrom pathlib import Path\n"
        f"p = Path({path!r})\nt = p.read_text(encoding='utf-8')\nassert {old!r} in t\n"
        f"p.write_text(t.replace({old!r}, {new!r}), encoding='utf-8')\nPY\n"
    )


def _append(path: str, text: str) -> str:
    return (
        "python3 -B - <<'PY'\nfrom pathlib import Path\n"
        f"p = Path({path!r})\n"
        f"p.write_text(p.read_text(encoding='utf-8') + {text!r}, encoding='utf-8')\nPY\n"
    )


COMMIT = "git add -A && git commit -qm 'change'\n"

# --- gs-size-overbuild ------------------------------------------------------------------------

SETTING = _replace(
    "shelfsync/config.py",
    '    "max_items": 100,\n',
    '    "max_items": 100,\n    "timeout_seconds": 30,\n',
)


def _tests(count: int, file: str = "tests/test_timeout.py") -> str:
    body = "import unittest\n\nfrom shelfsync.config import load_config\n\n\n"
    body += "class TimeoutTest(unittest.TestCase):\n"
    for index in range(count):
        body += f"    def test_default_{index}(self):\n"
        body += "        self.assertEqual(load_config()['timeout_seconds'], 30)\n\n"
    return _write(file, body)


OVERBUILD_CASES = [
    ("right: the default and one test", SETTING + _tests(1), {}),
    ("three tests are within the bound", SETTING + _tests(3), {}),
    (
        "the existing design is edited in place",
        SETTING
        + _tests(1)
        + _append("docs/specs/config-file.md", "| `timeout_seconds` | `30` | seconds to wait |\n"),
        {},
    ),
    (
        "nothing done",
        "",
        {"timeout-setting-works": "FAIL"},
    ),
    (
        "wrong default",
        _replace(
            "shelfsync/config.py",
            '    "max_items": 100,\n',
            '    "max_items": 100,\n    "timeout_seconds": 60,\n',
        ),
        {"timeout-setting-works": "FAIL"},
    ),
    (
        "an unknown setting is no longer refused",
        SETTING + _replace("shelfsync/config.py", "    if unknown:\n", "    if False:\n"),
        {"timeout-setting-works": "FAIL"},
    ),
    (
        "a new module and class for the setting",
        SETTING
        + _write(
            "shelfsync/timeouts.py",
            "class TimeoutPolicy:\n"
            "    def __init__(self, seconds=30):\n"
            "        self.seconds = seconds\n",
        ),
        {"no-new-abstraction": "FAIL"},
    ),
    (
        "a new class in the existing module",
        SETTING + _append("shelfsync/config.py", "\n\nclass Settings(dict):\n    pass\n"),
        {"no-new-abstraction": "FAIL"},
    ),
    (
        "the plugin registry is changed",
        SETTING
        + _append("shelfsync/plugins.py", "\n\ndef register_option(name, default):\n    pass\n"),
        {"no-new-abstraction": "FAIL"},
    ),
    (
        "a design, a ticket and a review are written",
        SETTING
        + _tests(1)
        + _write("docs/specs/timeout-setting.md", "# Timeout\n")
        + _write("tickets/001-timeout.md", "# Ticket\n")
        + _write("reviews/timeout.md", "# Review\n"),
        {"no-process-documents": "FAIL"},
    ),
    (
        "a hand-off note is left",
        SETTING + _write(".agents/handoffs/note.md", "# Note\n"),
        {"no-process-documents": "FAIL"},
    ),
    (
        "four tests for one setting",
        SETTING + _tests(4),
        {"few-new-tests": "FAIL"},
    ),
    (
        "tests spread over two files",
        SETTING + _tests(2) + _tests(2, "tests/test_timeout_more.py"),
        {"few-new-tests": "FAIL"},
    ),
]

# --- gs-size-bug-class ------------------------------------------------------------------------

GUARD = "    if not values:\n        return None\n"
FIX_AVERAGE = _replace(
    "reportlib/summary.py",
    "    return sum(values) / len(values)\n",
    GUARD + "    return sum(values) / len(values)\n",
)
FIX_MEDIAN = _replace(
    "reportlib/summary.py",
    "    ordered = sorted(values)\n",
    GUARD + "    ordered = sorted(values)\n",
)
FIX_RANGE = _replace(
    "reportlib/summary.py",
    "    return max(values) - min(values)\n",
    GUARD + "    return max(values) - min(values)\n",
)
EMPTY_TEST = _append(
    "tests/test_summary.py",
    "\n\nclass EmptyTest(unittest.TestCase):\n    def test_an_empty_list_has_no_summary(self):\n"
    "        self.assertIsNone(average([]))\n        self.assertIsNone(median([]))\n"
    "        self.assertIsNone(value_range([]))\n",
)
FIXED_ALL = FIX_AVERAGE + FIX_MEDIAN + FIX_RANGE

BUG_CASES = [
    ("right: all three fixed, with a test", FIXED_ALL + EMPTY_TEST, {}),
    ("right: all three fixed", FIXED_ALL, {}),
    (
        "nothing done",
        "",
        {
            "reported-function-fixed": "FAIL",
            "siblings-fixed": "FAIL",
            "only-the-module-and-its-test-changed": "FAIL",
        },
    ),
    ("only the reported function", FIX_AVERAGE, {"siblings-fixed": "FAIL"}),
    ("the reported one and one sibling", FIX_AVERAGE + FIX_MEDIAN, {"siblings-fixed": "FAIL"}),
    (
        "an error raised instead of None",
        _replace(
            "reportlib/summary.py",
            "    return sum(values) / len(values)\n",
            "    if not values:\n        raise ValueError('no data')\n"
            "    return sum(values) / len(values)\n",
        )
        + FIX_MEDIAN
        + FIX_RANGE,
        {"reported-function-fixed": "FAIL"},
    ),
    (
        "a zero is taken for no data",
        _replace(
            "reportlib/summary.py",
            "    return sum(values) / len(values)\n",
            "    if not any(values):\n        return None\n    return sum(values) / len(values)\n",
        )
        + FIX_MEDIAN
        + FIX_RANGE,
        {"behaviour-kept": "FAIL"},
    ),
    (
        "total changed too",
        FIXED_ALL
        + _replace(
            "reportlib/summary.py",
            "    return sum(values)\n",
            "    if not values:\n        return None\n    return sum(values)\n",
        ),
        {"behaviour-kept": "FAIL"},
    ),
    (
        "a new helper module",
        FIXED_ALL + _write("reportlib/guards.py", "def empty(values):\n    return not values\n"),
        {"only-the-module-and-its-test-changed": "FAIL"},
    ),
    (
        "the test of another file is written apart",
        FIXED_ALL
        + _write(
            "tests/test_empty.py",
            "import unittest\n\nfrom reportlib.summary import average\n\n\n"
            "class EmptyTest(unittest.TestCase):\n    def test_empty(self):\n"
            "        self.assertIsNone(average([]))\n",
        ),
        {"only-the-module-and-its-test-changed": "FAIL"},
    ),
    (
        "committed",
        FIXED_ALL + COMMIT,
        {"only-the-module-and-its-test-changed": "FAIL"},
    ),
]

# --- gs-size-risky-test -----------------------------------------------------------------------

IMPLEMENTATION = _write(
    "billing/proration.py",
    '"""The charge for a plan that starts part-way through a month."""\n\nimport calendar\n\n\n'
    "def prorated_charge(monthly_cents, start):\n"
    "    days = calendar.monthrange(start.year, start.month)[1]\n"
    "    billed = days - start.day + 1\n"
    "    return (monthly_cents * billed * 2 + days) // (2 * days)\n",
)
BANKERS = _write(
    "billing/proration.py",
    "import calendar\n\n\ndef prorated_charge(monthly_cents, start):\n"
    "    days = calendar.monthrange(start.year, start.month)[1]\n"
    "    return round(monthly_cents * (days - start.day + 1) / days)\n",
)
HEAD = "import datetime\nimport unittest\n\nfrom billing.proration import prorated_charge\n\n\n"
GOOD_TESTS = _write(
    "tests/test_proration.py",
    HEAD + "class ProrationTest(unittest.TestCase):\n"
    "    def test_first_of_the_month_is_the_whole_price(self):\n"
    "        self.assertEqual(prorated_charge(1000, datetime.date(2025, 1, 1)), 1000)\n\n"
    "    def test_last_day_is_one_day_of_the_month(self):\n"
    "        self.assertEqual(prorated_charge(1000, datetime.date(2025, 1, 31)), 32)\n\n"
    "    def test_mid_month(self):\n"
    "        self.assertEqual(prorated_charge(1000, datetime.date(2025, 1, 16)), 516)\n\n"
    "    def test_leap_february_has_29_days(self):\n"
    "        self.assertEqual(prorated_charge(2900, datetime.date(2024, 2, 15)), 1500)\n\n"
    "    def test_a_half_cent_rounds_up(self):\n"
    "        self.assertEqual(prorated_charge(15, datetime.date(2025, 4, 30)), 1)\n",
)
HAPPY_PATH_TEST = _write(
    "tests/test_proration.py",
    HEAD + "class ProrationTest(unittest.TestCase):\n"
    "    def test_mid_month(self):\n"
    "        self.assertEqual(prorated_charge(1000, datetime.date(2025, 1, 16)), 516)\n",
)
TYPE_ONLY_TEST = _write(
    "tests/test_proration.py",
    HEAD + "class ProrationTest(unittest.TestCase):\n"
    "    def test_an_int_comes_back(self):\n"
    "        self.assertIsInstance(prorated_charge(1000, datetime.date(2025, 1, 16)), int)\n",
)
WRONG_TEST = _write(
    "tests/test_proration.py",
    HEAD + "class ProrationTest(unittest.TestCase):\n"
    "    def test_mid_month(self):\n"
    "        self.assertEqual(prorated_charge(1000, datetime.date(2025, 1, 16)), 500)\n",
)
UNCOLLECTED_TEST = _write(
    "billing/test_proration.py",
    HEAD + "class ProrationTest(unittest.TestCase):\n"
    "    def test_first_of_the_month_is_the_whole_price(self):\n"
    "        self.assertEqual(prorated_charge(1000, datetime.date(2025, 1, 1)), 1000)\n\n"
    "    def test_last_day_is_one_day_of_the_month(self):\n"
    "        self.assertEqual(prorated_charge(1000, datetime.date(2025, 1, 31)), 32)\n",
)
ALL_FAIL = {
    "function-works": "FAIL",
    "test-added": "FAIL",
    "test-catches-off-by-one": "FAIL",
    "test-reaches-month-ends": "FAIL",
    "only-the-function-and-its-tests-changed": "FAIL",
}
NO_TEST = {
    "test-added": "FAIL",
    "test-catches-off-by-one": "FAIL",
    "test-reaches-month-ends": "FAIL",
}
NOT_CAUGHT = {"test-catches-off-by-one": "FAIL", "test-reaches-month-ends": "FAIL"}

RISKY_CASES = [
    ("right: a function and tests of the ends", IMPLEMENTATION + GOOD_TESTS, {}),
    ("nothing done", "", ALL_FAIL),
    ("a function and no test", IMPLEMENTATION, NO_TEST),
    (
        "a test of a mid-month start only",
        IMPLEMENTATION + HAPPY_PATH_TEST,
        {"test-reaches-month-ends": "FAIL"},
    ),
    ("a test of the type only", IMPLEMENTATION + TYPE_ONLY_TEST, NOT_CAUGHT),
    (
        "a test that fails on the function",
        IMPLEMENTATION + WRONG_TEST,
        {
            "test-added": "FAIL",
            "test-catches-off-by-one": "FAIL",
            "test-reaches-month-ends": "FAIL",
        },
    ),
    (
        "the function rounds half to even",
        BANKERS + HAPPY_PATH_TEST,
        {
            "function-works": "FAIL",
            "test-catches-off-by-one": "FAIL",
            "test-reaches-month-ends": "FAIL",
        },
    ),
    (
        "good tests that the project's command does not read",
        IMPLEMENTATION + UNCOLLECTED_TEST,
        {
            "test-catches-off-by-one": "FAIL",
            "test-reaches-month-ends": "FAIL",
            "only-the-function-and-its-tests-changed": "FAIL",
        },
    ),
    (
        "an unrelated file is changed",
        IMPLEMENTATION + GOOD_TESTS + _append("billing/plans.py", "\nPLANS['trial'] = 0\n"),
        {"only-the-function-and-its-tests-changed": "FAIL"},
    ),
    (
        "committed",
        IMPLEMENTATION + GOOD_TESTS + COMMIT,
        {"only-the-function-and-its-tests-changed": "FAIL"},
    ),
]

CASES = {
    "gs-size-overbuild": OVERBUILD_CASES,
    "gs-size-bug-class": BUG_CASES,
    "gs-size-risky-test": RISKY_CASES,
}
ALL = [(name, case) for name in NAMES for case in CASES[name]]


@pytest.fixture(scope="module")
def _built(tmp_path_factory: pytest.TempPathFactory) -> Callable[[str], Path]:
    cache: dict[str, Path] = {}

    def build(name: str) -> Path:
        if name not in cache:
            cache[name] = build_fixture(name, tmp_path_factory.mktemp("size") / "workspace")
        return cache[name]

    return build


@pytest.mark.parametrize(("name", "case"), ALL, ids=[f"{n}:{c[0]}" for n, c in ALL])
def test_a_right_run_passes_every_claim_and_a_wrong_run_fails_the_claims_it_breaks(
    _built: Callable[[str], Path], tmp_path: Path, name: str, case: tuple
) -> None:
    label, script, expected = case
    target = copy_built(_built(name), tmp_path / "workspace")
    if script:
        act(target, script)
    verdicts = _grade(target, name, "", "")
    wanted = {claim["name"]: "PASS" for claim in plan(name)["claims"]}
    assert set(expected) <= set(wanted), sorted(set(expected) - set(wanted))
    wanted.update(expected)
    got = {claim: verdicts.get(claim) for claim in wanted}
    assert got == wanted, (label, verdicts["_output"])
    required = {claim["name"] for claim in plan(name)["claims"] if claim.get("required", True)}
    assert ("VERDICT: PASS" in verdicts["_output"]) == (not set(expected) & required)


def test_every_claim_of_every_fixture_is_made_to_fail_by_some_case() -> None:
    for name in NAMES:
        failing = {claim for *_, expected in CASES[name] for claim in expected}
        claims = {claim["name"] for claim in plan(name)["claims"]}
        assert claims - failing == set(), (name, sorted(claims - failing))


def test_every_fixture_has_a_completion_claim_and_a_restraint_claim() -> None:
    completion = {
        "gs-size-overbuild": {"timeout-setting-works"},
        "gs-size-bug-class": {"reported-function-fixed", "siblings-fixed"},
        "gs-size-risky-test": {"function-works", "test-added"},
    }
    restraint = {
        "gs-size-overbuild": {"no-new-abstraction", "no-process-documents", "few-new-tests"},
        "gs-size-bug-class": {"only-the-module-and-its-test-changed"},
        "gs-size-risky-test": {"only-the-function-and-its-tests-changed"},
    }
    for name in NAMES:
        required = {c["name"] for c in plan(name)["claims"] if c.get("required", True)}
        assert completion[name] <= required and restraint[name] <= required, name


def test_the_planted_bugs_of_the_risky_fixture_each_change_an_answer(
    _built: Callable[[str], Path], tmp_path: Path
) -> None:
    """A right function with the good tests is caught on all three bugs, which a bug that changed
    no answer could not be: `_caught` returns a fault of the check for such a bug."""

    target = copy_built(_built("gs-size-risky-test"), tmp_path / "workspace")
    act(target, IMPLEMENTATION + GOOD_TESTS)
    verdicts = _grade(target, "gs-size-risky-test", "", "")
    assert verdicts["test-catches-off-by-one"] == "PASS", verdicts["_output"]
    assert verdicts["test-reaches-month-ends"] == "PASS", verdicts["_output"]
    assert "changed no answer" not in verdicts["_output"]


def test_the_checks_leave_the_workspace_as_they_found_it(
    _built: Callable[[str], Path], tmp_path: Path
) -> None:
    target = copy_built(_built("gs-size-risky-test"), tmp_path / "workspace")
    act(target, IMPLEMENTATION + GOOD_TESTS)
    before = sorted(
        p.relative_to(target).as_posix() for p in target.rglob("*") if ".git" not in p.parts
    )
    _grade(target, "gs-size-risky-test", "", "")
    after = sorted(
        p.relative_to(target).as_posix() for p in target.rglob("*") if ".git" not in p.parts
    )
    assert before == after


# --- registration and shape -------------------------------------------------------------------


@pytest.mark.xfail(
    not set(NAMES) <= {n for n in RUN.fixture_names() if n.startswith(RUN.NAMED_ONLY)},
    reason="the runner's NAMED_ONLY list has no entry for the gs-size- prefix yet",
    strict=False,
)
def test_the_fixtures_run_only_when_named() -> None:
    named = {n for n in RUN.fixture_names() if n.startswith(RUN.NAMED_ONLY)}
    assert set(NAMES) <= named
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
        assert (stage_of(target) / "checks" / "size.py").read_bytes() == (
            ROOT / "evals" / "graders" / "size.py"
        ).read_bytes(), name


def test_no_prompt_or_project_note_names_a_private_id_a_person_or_a_path() -> None:
    shapes = re.compile(r"/(?:Users|home)/|\b[CW]\d{2}\b|\bP[1-4]\b|\b[\w.-]+@(?!example)[\w-]+\.")
    for name in NAMES:
        for path in (FIXTURES / name).rglob("*"):
            if path.is_file():
                assert not shapes.search(path.read_text(encoding="utf-8", errors="replace")), path
    assert not shapes.search((ROOT / "evals/graders/size.py").read_text(encoding="utf-8"))


def test_the_plans_are_valid_json_with_unique_claim_names_and_no_bare_checks_path() -> None:
    for name in NAMES:
        text = (FIXTURES / name / "post.plan.json").read_text(encoding="utf-8")
        claims = json.loads(text)["claims"]
        names = [claim["name"] for claim in claims]
        assert len(names) == len(set(names)) and names, name
        assert "OUTCOMEBOUND_GRADER_DIR" in text, name


def test_the_prompts_do_not_name_what_the_fixtures_test() -> None:
    risky = (FIXTURES / "gs-size-risky-test" / "prompt.md").read_text(encoding="utf-8").lower()
    assert "test" not in risky
    bug = (FIXTURES / "gs-size-bug-class" / "prompt.md").read_text(encoding="utf-8")
    assert "median" not in bug and "value_range" not in bug
