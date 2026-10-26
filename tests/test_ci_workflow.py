"""CI always tests every supported Python, binds every shard to its matrix entry, and reports
required job names only after the checks and every shard pass. The shard guard observes real
xdist worker selections and rejects an omission that occurs only inside a worker."""

from __future__ import annotations

import importlib.util
import itertools
import json
import os
import re
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from tests import conftest as suite_conftest
from tests.portable import needs_bash, run_bash, write

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github/workflows/ci.yml"
CHECKER = ROOT / "scripts/check-test-shards.py"


def workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def step_script(name: str) -> str:
    """The shell text of the step `name`, as the workflow has it, indentation removed."""

    lines = workflow_text().splitlines()
    start = next(i for i, line in enumerate(lines) if line.strip() == f"- name: {name}")
    run = next(i for i in range(start, len(lines)) if lines[i].strip() == "run: |")
    indent = len(lines[run]) - len(lines[run].lstrip())
    body: list[str] = []
    for line in lines[run + 1 :]:
        if line.strip() and len(line) - len(line.lstrip()) <= indent:
            break
        body.append(line)
    return textwrap.dedent("\n".join(body)) + "\n"


def group(pattern: str, text: str) -> str:
    """The first group of `pattern` in `text`, which must be there."""

    found = re.search(pattern, text, re.M)
    assert found, pattern
    return found.group(1)


def job_text(job: str) -> str:
    """The text of one top-level job of the workflow."""

    match = re.search(rf"^  {re.escape(job)}:\n(.*?)(?=^  \S|\Z)", workflow_text(), re.M | re.S)
    assert match, job
    return match.group(1)


def test_every_run_tests_the_full_python_matrix():
    text = workflow_text()
    trigger = text.split("concurrency:")[0]
    for event in ("push", "pull_request", "workflow_dispatch"):
        assert re.search(rf"^  {event}:", trigger, re.M)
    assert 'tags: ["v*"]' in trigger
    assert not re.search(r"^\s+paths(?:-ignore)?:", trigger, re.M)
    assert not re.search(r"^  plan:", text, re.M)
    for job, versions in (
        ("suite", ["3.10", "3.11", "3.12", "3.13", "3.14"]),
        ("windows", ["3.10", "3.14"]),
    ):
        body = job_text(job)
        assert json.loads(group(r"^        python-version: (\[.*\])$", body)) == versions
    for job in ("suite", "windows", "container", "checks"):
        assert not re.search(r"^    (?:if|needs):", job_text(job), re.M)


def test_the_job_test_reports_the_two_names_the_ruleset_requires():
    """`test (3.10)` and `test (3.14)` are the job `test`, one per Python, on every run."""

    test = job_text("test")
    assert 'python-version: ["3.10", "3.14"]' in test
    assert "name:" not in test.split("steps:")[0]
    assert {need.strip() for need in group(r"needs: \[(.*?)\]", test).split(",")} == {
        "checks",
        "suite",
    }
    assert "if: ${{ always() }}" in test
    assert "CHECKS: ${{ needs.checks.result }}" in test
    assert "SUITE: ${{ needs.suite.result }}" in test


@needs_bash
@pytest.mark.parametrize(
    ("checks", "suite"),
    list(itertools.product(("success", "failure", "cancelled", "skipped", ""), repeat=2)),
)
def test_the_aggregator_fails_on_every_non_success(tmp_path, checks, suite):
    script = tmp_path / "aggregate.sh"
    write(script, step_script("Read the jobs behind this name"))
    done = run_bash(
        script,
        env={**os.environ, "CHECKS": checks, "SUITE": suite},
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert (done.returncode == 0) == (checks == suite == "success"), done.stdout + done.stderr


def test_the_release_waits_for_the_reported_names_and_the_other_platforms():
    needs = group(r"needs: \[(.*?)\]", job_text("release"))
    assert {name.strip() for name in needs.split(",")} == {
        "verify-tag",
        "test",
        "windows",
        "container",
    }


@pytest.mark.parametrize("job", ["suite", "windows", "container"])
def test_each_matrix_entry_selects_its_own_shard_once_per_python(job):
    body = job_text(job)
    # Every entry must use its own matrix value, with no step override of the job's value.
    environment = group(r"^    env:\n((?:      [^\n]*\n)+)", body)
    assert group(r"^      OUTCOMEBOUND_TEST_SHARD: (.+)$", environment) == "${{ matrix.shard }}"
    assert len(re.findall(r"^\s+OUTCOMEBOUND_TEST_SHARD:", body, re.M)) == 1
    if job == "container":
        entries = re.findall(r'- image: "([^"]+)"\n\s+shard: "([^"]+)"', body)
        assert {image for image, _ in entries} == {"python:3.13-slim", "python:3.13-alpine"}
    else:
        versions = json.loads(group(r"^        python-version: (\[.*\])$", body))
        shards = json.loads(group(r"^        shard: (\[.*\])$", body))
        entries = list(itertools.product(versions, shards))
    by_python: dict[str, list[tuple[int, int]]] = {}
    for python, shard in entries:
        selected = environment.split("OUTCOMEBOUND_TEST_SHARD: ", 1)[1].strip()
        selected = selected.replace("${{ matrix.shard }}", shard)
        index, total = suite_conftest.parse_shard(selected)
        assert selected == shard
        by_python.setdefault(python, []).append((index, total))
    assert by_python
    for pairs in by_python.values():
        total = pairs[0][1]
        assert sorted(pairs) == [(index, total) for index in range(1, total + 1)]
    assert {total for pairs in by_python.values() for _, total in pairs} == (
        {1, 2} if job == "container" else {3} if job == "suite" else {2}
    )
    named = {
        int(count) for count in group(r"check-test-shards\.py ([\d ]+)", workflow_text()).split()
    }
    assert {total for pairs in by_python.values() for _, total in pairs if total > 1} <= named


def test_a_test_belongs_to_one_shard_and_a_shard_spec_is_checked():
    ids = [f"tests/test_x.py::test_{n}[case-{n % 7}]" for n in range(500)]
    parts = [
        [test for test in ids if suite_conftest.shard_of(test, 3) == index] for index in (1, 2, 3)
    ]
    assert sorted(part_id for part in parts for part_id in part) == sorted(ids)
    assert all(len(part) > 100 for part in parts)
    assert suite_conftest.parse_shard("2/3") == (2, 3)
    for bad in ("", "3", "0/3", "4/3", "a/b", "1/0", "1/2/3", "-1/2"):
        with pytest.raises(pytest.UsageError):
            suite_conftest.parse_shard(bad)


@pytest.mark.parametrize("broken", [False, True], ids=["whole", "worker-only-omission"])
def test_the_checker_observes_worker_selection_without_running_tests(tmp_path, broken):
    write(
        tmp_path / "conftest.py",
        textwrap.dedent(f"""\
            from tests.conftest import pytest_collection_modifyitems as select

            def pytest_collection_modifyitems(config, items):
                select(config, items)
                if {broken!r} and hasattr(config, "workerinput"):
                    items[:] = [item for item in items if item.name != "test_omitted"]
            """),
    )
    write(
        tmp_path / "test_sample.py",
        "\n".join(
            f'def test_{name}():\n    raise AssertionError("a collection check must run no test")\n'
            for name in ["omitted", *map(str, range(30))]
        ),
    )
    done = subprocess.run(
        [sys.executable, str(CHECKER), "2"],
        cwd=tmp_path,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert done.returncode == int(broken), done.stdout + done.stderr
    if broken:
        assert "in no part: test_sample.py::test_omitted" in done.stdout
    else:
        assert "2 shards of 31 tests: disjoint and whole" in done.stdout


def load_checker():
    spec = importlib.util.spec_from_file_location("check_test_shards", CHECKER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_shard_check_rejects_missing_repeated_extra_or_empty_selections():
    checker = load_checker()
    whole = ["a::t1", "a::t2", "a::t3"]
    assert checker.problems(whole, [["a::t1", "a::t3"], ["a::t2"]]) == []
    assert checker.problems(whole, [["a::t1"], ["a::t2"]]) == ["in no part: a::t3"]
    assert checker.problems(whole, [["a::t1", "a::t2"], ["a::t2", "a::t3"]]) == [
        "in parts 1 and 2: a::t2"
    ]
    assert checker.problems(whole, [["a::t1", "a::t2", "a::t3", "a::t4"], []]) == [
        "part 2 is empty",
        "in a part, not in the suite: a::t4",
    ]
    assert checker.problems(whole, [whole, []]) == ["part 2 is empty"]
    assert checker.problems(whole, [["a::t1", "a::t1"], ["a::t2", "a::t3"]]) == [
        "in parts 1 and 1: a::t1"
    ]
    assert checker.problems(["a::t1", "a::t1"], [["a::t1"], ["a::t1"]])
    assert checker.problems([], [[], []])
