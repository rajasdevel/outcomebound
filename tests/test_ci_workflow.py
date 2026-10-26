"""The shape of this repository's CI that its landing depends on: the plan job picks the full
Python matrix for a change that can differ by Python version and one Python for a change that
cannot, the suite's shards are disjoint and whole, and the job names that the ruleset requires
are still reported. The plan job is run as the workflow has it, not as a copy of its rule."""

from __future__ import annotations

import importlib.util
import os
import re
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from tests import conftest as suite_conftest
from tests.portable import needs_bash, run_bash, write

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github/workflows/ci.yml"
GIT = shutil.which("git") or "git"
IDENTITY = ("-c", "user.name=ci", "-c", "user.email=ci@example.test", "-c", "commit.gpgsign=false")
ALL_PYTHONS = '["3.10","3.11","3.12","3.13","3.14"]'


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


def job_text(job: str) -> str:
    """The text of one top-level job of the workflow."""

    match = re.search(rf"^  {re.escape(job)}:\n(.*?)(?=^  \S|\Z)", workflow_text(), re.M | re.S)
    assert match, job
    return match.group(1)


def put(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    write(path, text)


def group(pattern: str, text: str) -> str:
    """The first group of `pattern` in `text`, which must be there."""

    found = re.search(pattern, text)
    assert found, pattern
    return found.group(1)


def git(repo: Path, *argv: str) -> str:
    done = subprocess.run(
        [GIT, *IDENTITY, *argv],
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return done.stdout.strip()


def pull_request(tmp_path: Path, before: dict[str, str], after: dict[str, str | None]) -> str:
    """A repository whose base commit holds `before` and whose head commit applies `after` (a
    text, or None to delete the file); returns the base commit. The plan job runs in it."""

    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    for name, text in before.items():
        put(repo / name, text)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "base")
    base = git(repo, "rev-parse", "HEAD")
    for name, changed in after.items():
        if changed is None:
            (repo / name).unlink()
        else:
            put(repo / name, changed)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "change")
    return base


def plan(tmp_path: Path, event: str, base: str) -> dict[str, str]:
    """The outputs the plan step writes when it runs in the repository `pull_request` built."""

    script = tmp_path / "plan.sh"
    write(script, step_script("Plan the matrix"))
    output = tmp_path / "output.txt"
    output.write_text("", encoding="utf-8")
    environment = {
        **os.environ,
        "EVENT": event,
        "BASE": base,
        "GITHUB_OUTPUT": str(output),
    }
    done = run_bash(
        script,
        cwd=tmp_path / "repo",
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert done.returncode == 0, done.stdout + done.stderr
    lines = output.read_text(encoding="utf-8").splitlines()
    return dict(line.split("=", 1) for line in lines)


CODE = {"tests/test_a.py": "x = 1\n"}


@needs_bash
@pytest.mark.parametrize(
    ("before", "after"),
    [
        ({"docs/a.md": "a\n"}, {"docs/a.md": "b\n"}),
        ({"evals/fixtures/f/answer.md": "a\n"}, {"evals/fixtures/f/answer.md": "b\n"}),
        ({"evals/fixtures/f/check.py": "a = 1\n"}, {"evals/fixtures/f/check.py": "a = 2\n"}),
        ({"evals/README.md": "a\n"}, {"evals/README.md": "b\n"}),
        ({"skills/s/SKILL.md": "a\n"}, {"skills/s/SKILL.md": "b\n"}),
        ({"CHANGELOG.md": "a\n"}, {"CHANGELOG.md": "b\n", "docs/new.md": "c\n"}),
    ],
    ids=["docs", "fixture-prose", "fixture-code", "evals-readme", "skill", "two-prose-files"],
)
def test_a_pull_request_that_changes_no_code_runs_one_python(tmp_path, before, after):
    outputs = plan(tmp_path, "pull_request", pull_request(tmp_path, before, after))

    assert outputs == {"pythons": '["3.14"]', "windows": '["3.14"]'}


@needs_bash
@pytest.mark.parametrize(
    ("before", "after"),
    [
        ({"outcomebound_tools/a.py": "a = 1\n"}, {"outcomebound_tools/a.py": "a = 2\n"}),
        ({"scripts/a.py": "a = 1\n"}, {"scripts/a.py": "a = 2\n"}),
        ({"tests/test_a.py": "a = 1\n"}, {"tests/test_a.py": "a = 2\n"}),
        ({".github/workflows/ci.yml": "a\n"}, {".github/workflows/ci.yml": "b\n"}),
        ({"evals/run.py": "a = 1\n"}, {"evals/run.py": "a = 2\n"}),
        ({"evals/graders/g.sh": "a\n"}, {"evals/graders/g.sh": "b\n"}),
        ({"pyproject.toml": "a\n"}, {"pyproject.toml": "b\n"}),
        ({"requirements-dev.txt": "a\n"}, {"requirements-dev.txt": "b\n"}),
        ({"docs/a.md": "a\n", "tests/t.py": "a\n"}, {"docs/a.md": "b\n", "tests/t.py": "b\n"}),
        # A path that leaves the list still shows: the old name is read as well as the new one.
        ({"tests/t.py": "a\n"}, {"tests/t.py": None, "docs/t.md": "a\n"}),
        ({"docs/a.md": "a\n"}, {"tests/new_test.py": "a = 1\n"}),
        ({"docs/a.md": "a\n"}, {"tests/tést.py": "a = 1\n"}),
    ],
    ids=[
        "engine",
        "scripts",
        "tests",
        "workflow",
        "eval-runner",
        "eval-grader",
        "packaging",
        "pins",
        "mixed",
        "moved-out",
        "added-test",
        "quoted-name",
    ],
)
def test_a_pull_request_that_changes_code_runs_every_python(tmp_path, before, after):
    outputs = plan(tmp_path, "pull_request", pull_request(tmp_path, before, after))

    assert outputs == {"pythons": ALL_PYTHONS, "windows": '["3.10","3.14"]'}


@needs_bash
@pytest.mark.parametrize("event", ["push", "workflow_dispatch", "schedule"])
def test_a_run_that_is_not_a_pull_request_runs_every_python(tmp_path, event):
    base = pull_request(tmp_path, {"docs/a.md": "a\n"}, {"docs/a.md": "b\n"})

    assert plan(tmp_path, event, base)["pythons"] == ALL_PYTHONS


@needs_bash
def test_a_base_that_cannot_be_read_runs_every_python(tmp_path):
    pull_request(tmp_path, {"docs/a.md": "a\n"}, {"docs/a.md": "b\n"})

    outputs = plan(tmp_path, "pull_request", "0" * 40)

    assert outputs["pythons"] == ALL_PYTHONS


def test_the_job_test_reports_the_two_names_the_ruleset_requires():
    """`test (3.10)` and `test (3.14)` are the job `test`, one per Python, whatever the plan."""

    test = job_text("test")

    assert 'python-version: ["3.10", "3.14"]' in test
    assert "name:" not in test.split("steps:")[0]
    for need in ("plan", "checks", "suite"):
        assert need in group(r"needs: \[(.*?)\]", test)
    assert "if: ${{ always() }}" in test


def test_the_release_waits_for_the_reported_names_and_the_other_platforms():
    needs = group(r"needs: \[(.*?)\]", job_text("release"))

    assert {name.strip() for name in needs.split(",")} == {
        "verify-tag",
        "test",
        "windows",
        "container",
    }


def shard_pairs(items: list[str]) -> list[tuple[int, int]]:
    """`["1/3", "2/3"]` as `[(1, 3), (2, 3)]`."""

    pairs = []
    for item in items:
        index, _, count = item.strip().strip('"').partition("/")
        pairs.append((int(index), int(count)))
    return pairs


def test_every_shard_list_of_the_workflow_is_a_whole_split_of_the_count_it_names():
    text = workflow_text()
    splits = [shard_pairs(items.split(",")) for items in re.findall(r"shard: \[([^\]]*)\]", text)]
    by_image: dict[str, list[str]] = {}
    for image, shard in re.findall(r'- image: "([^"]+)"\n\s+shard: ("[^"]+")', text):
        by_image.setdefault(image, []).append(shard)
    splits += [shard_pairs(items) for items in by_image.values()]

    assert len(splits) >= 4
    for pairs in splits:
        count = pairs[0][1]
        assert pairs == [(index, count) for index in range(1, count + 1)], pairs
    # The check of the shards names every count that splits a suite, one alone being no split.
    named = {int(count) for count in group(r"check-test-shards\.py ([\d ]+)", text).split()}
    assert named == {pairs[0][1] for pairs in splits if pairs[0][1] > 1}


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


def collected(shard: str | None) -> list[str]:
    env = {key: value for key, value in os.environ.items() if key != "OUTCOMEBOUND_TEST_SHARD"}
    if shard:
        env["OUTCOMEBOUND_TEST_SHARD"] = shard
    done = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "-q",
            "-o",
            "addopts=",
            "-p",
            "no:cacheprovider",
            "tests/test_exec_bits.py",
            "tests/test_makefile.py",
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert done.returncode == 0, done.stdout + done.stderr
    return [line for line in done.stdout.splitlines() if "::" in line]


def test_the_shards_of_a_real_collection_are_disjoint_and_whole():
    whole = collected(None)
    parts = [collected(f"{index}/2") for index in (1, 2)]

    assert whole and all(parts)
    assert sorted(parts[0] + parts[1]) == sorted(whole)
    assert not set(parts[0]) & set(parts[1])


def load_checker():
    spec = importlib.util.spec_from_file_location(
        "check_test_shards", ROOT / "scripts/check-test-shards.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_shard_check_names_a_test_that_is_in_no_part_in_two_or_in_a_part_only():
    checker = load_checker()
    whole = ["a::t1", "a::t2", "a::t3"]

    assert checker.problems(whole, [["a::t1", "a::t3"], ["a::t2"]]) == []
    assert checker.problems(whole, [["a::t1"], ["a::t2"]]) == ["in no part: a::t3"]
    assert checker.problems(whole, [["a::t1", "a::t2"], ["a::t2", "a::t3"]]) == [
        "in parts 1 and 2: a::t2"
    ]
    assert checker.problems(whole, [["a::t1", "a::t2", "a::t3", "a::t4"], []]) == [
        "in a part, not in the suite: a::t4"
    ]
    assert checker.problems(["a::t1", "a::t1"], [["a::t1"], []])


def test_the_plan_step_uses_no_feature_that_only_bash_has():
    """The step is plain POSIX shell, so it runs under any `sh` a runner or a container has."""

    script = step_script("Plan the matrix")

    assert "[[" not in script and "<<<" not in script and "mapfile" not in script
