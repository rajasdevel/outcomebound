"""Every default fixture (the ones a run takes when --fixtures names none) has proven reference
outcomes: its suite.json lists `good`, `noop` and at least one wrong outcome, and each one, applied
to a fresh build and graded by the fixture's own plan as `evals/selftest.py` does it, gets the
verdicts its expect.json names. A fixture whose `fixture.json` names a tool this machine lacks is
skipped, with the tool named.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import pytest

from tests.eval_helpers import FIXTURES, RUN, load
from tests.portable import needs_posix_bash

SELFTEST = load("eval_selftest_default_references", "evals/selftest.py")
DEFAULTS = tuple(RUN.default_fixtures())
TOOL = re.compile(r"^([A-Za-z0-9_.+-]+?)(?:[<>=!~].*)?$")


def _suite(name: str) -> dict:
    return json.loads((FIXTURES / name / "suite.json").read_text(encoding="utf-8"))


def _missing(name: str) -> str:
    """Why the fixture's references cannot be graded here, or an empty string: a tool its
    `fixture.json` needs that is not on PATH. Python and Git are needed by every fixture."""

    manifest = FIXTURES / name / "fixture.json"
    needs = (
        json.loads(manifest.read_text(encoding="utf-8")).get("needs", [])
        if manifest.is_file()
        else []
    )
    for need in ("git", *needs):
        found = TOOL.match(need)
        tool = found[1] if found else need
        if tool.startswith("python"):
            continue
        if shutil.which(tool) is None:
            return f"{name} needs {need}, and {tool} is not on PATH"
    return ""


def _cases() -> list:
    cases = []
    for name in DEFAULTS:
        path = FIXTURES / name / "suite.json"
        listed = (
            json.loads(path.read_text(encoding="utf-8")).get("references", [])
            if path.is_file()
            else []
        )
        reason = _missing(name)
        marks = [pytest.mark.skip(reason=reason)] if reason else []
        cases += [pytest.param(name, ref, marks=marks, id=f"{name}/{ref}") for ref in listed]
    return cases


def test_there_are_default_fixtures() -> None:
    assert len(DEFAULTS) >= 31, DEFAULTS


@pytest.mark.parametrize("name", DEFAULTS)
def test_each_default_fixture_has_a_sound_suite_with_good_noop_and_a_wrong_reference(
    name: str,
) -> None:
    folder = FIXTURES / name
    assert (folder / "suite.json").is_file(), f"{name} has no suite.json"
    suite = _suite(name)
    assert SELFTEST.default_fixture(suite), f"{name}: references and no budget"
    assert SELFTEST.suite_problems(SELFTEST.Fixture(name, folder)) == []
    references = suite["references"]
    assert {"good", "noop"} <= set(references) and len(references) >= 3, references
    for reference in references:
        for part in ("act.sh", "answer.md", "commands.txt", "expect.json"):
            assert (folder / "references" / reference / part).is_file(), f"{reference}/{part}"


@needs_posix_bash
@pytest.mark.parametrize(("name", "reference"), _cases())
def test_default_reference_grades_as_its_expect_says(
    tmp_path: Path, name: str, reference: str
) -> None:
    fixture = SELFTEST.Fixture(name, FIXTURES / name)
    suite = _suite(name)
    suite.setdefault("stubs", [])
    verdicts = SELFTEST.grade_reference(
        fixture, suite, reference, RUN.fixture_setup_env(), tmp_path
    )
    expect = json.loads(
        (FIXTURES / name / "references" / reference / "expect.json").read_text(encoding="utf-8")
    )
    assert SELFTEST.mismatches(expect, verdicts) == [], verdicts["_output"]
