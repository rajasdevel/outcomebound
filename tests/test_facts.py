"""The project facts: the CI test command read lexically from realistic CI files, and what a
fact the engine cannot observe becomes.

Each target is a directory under `tmp_path` holding CI files as projects write them; nothing in
them is run. Assertions are about the commands read, the lines rendered and what is left out.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from outcomebound_tools import facts
from outcomebound_tools.fragments import load_all

ROOT = Path(__file__).resolve().parent.parent

PYTHON = """\
name: Python
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.12"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - name: Install
        run: |
          python -m pip install --upgrade pip
          pip install pytest pytest-cov
          echo "pytest is installed"
      - name: Test
        run: python -m pytest -q --cov=pkg  # coverage too
"""
NODE = """\
on: push
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 20 }
      - run: npm ci
      - run: npm run build
      - run: npm test -- --coverage
        env:
          CI: "true"
"""
MONOREPO = """\
on: pull_request
defaults:
  run:
    working-directory: services
jobs:
  api:
    runs-on: ubuntu-latest
    steps:
      - name: Test the API
        working-directory: api
        run: go test ./...
      - run: cd api && go vet ./... && go test -race ./...
  web:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: packages/web
    steps:
      - run: npm ci
      - run: |
          npm test \\
            --reporter=dot
  root:
    runs-on: ubuntu-latest
    steps:
      - run: pytest tests/contract
"""
MATRIX = """\
on: push
jobs:
  check:
    strategy:
      matrix:
        command: ["make lint", "make test"]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: ${{ matrix.command }}
"""
RELEASE = """\
on:
  push:
    tags: ["v*"]
jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - run: python -m build
      - run: twine upload dist/*
"""
GITLAB = """\
stages: [test]
unit:
  stage: test
  before_script:
    - pip install -r requirements.txt
  script:
    - pytest --junitxml=report.xml
    - |
      coverage report
lint:
  script: ruff check .
"""


def project(root: Path, files: dict[str, str]) -> Path:
    for name, text in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text, encoding="utf-8")
    return root


def workflows(**texts: str) -> dict[str, str]:
    return {f".github/workflows/{name}.yml": text for name, text in texts.items()}


@pytest.mark.parametrize(
    ("text", "tests"),
    [
        (PYTHON, ("python -m pytest -q --cov=pkg",)),
        (NODE, ("npm test -- --coverage",)),
        (
            MONOREPO,
            (
                "cd api && go test ./...",
                "cd services && cd api && go vet ./... && go test -race ./...",
                "cd packages/web && npm test --reporter=dot",
                "cd services && pytest tests/contract",
            ),
        ),
        (RELEASE, ()),
    ],
    ids=["python", "node", "monorepo", "release"],
)
def test_each_workflow_yields_the_test_commands_it_runs(
    tmp_path: Path, text: str, tests: tuple[str, ...]
) -> None:
    target = project(tmp_path, workflows(ci=text))

    (read,) = facts.read_ci(target)

    assert (read.path, read.tests, read.unread) == (".github/workflows/ci.yml", tests, ())


def test_every_workflow_file_is_read_however_many_there_are(tmp_path: Path) -> None:
    """No count of files cuts the reading short: the test command in the last of a hundred
    workflow files, in path order, is read."""

    quiet = "on: push\njobs:\n  lint:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo\n"
    files = workflows(**{f"a{index:03}": quiet for index in range(99)}, zz=PYTHON)
    read = facts.read_ci(project(tmp_path, files))
    assert len(read) == 100
    assert read[-1].path == ".github/workflows/zz.yml"
    assert read[-1].tests == ("python -m pytest -q --cov=pkg",)


def test_a_gitlab_pipeline_yields_its_script_test_command(tmp_path: Path) -> None:
    target = project(tmp_path, {".gitlab-ci.yml": GITLAB})

    (read,) = facts.read_ci(target)

    assert (read.path, read.tests, read.unread) == (
        ".gitlab-ci.yml",
        ("pytest --junitxml=report.xml",),
        (),
    )


def test_a_step_that_runs_an_expression_cannot_be_settled(tmp_path: Path) -> None:
    target = project(tmp_path, workflows(ci=MATRIX))

    (read,) = facts.read_ci(target)

    assert read.tests == ()
    assert len(read.unread) == 1 and "${{ matrix.command }}" in read.unread[0]


def test_the_ci_test_line_names_each_settled_file_and_leaves_the_unsettled_one_unverified(
    tmp_path: Path,
) -> None:
    files = workflows(matrix=MATRIX, monorepo=MONOREPO, node=NODE, release=RELEASE)
    target = project(tmp_path, {**files, ".gitlab-ci.yml": GITLAB})

    rendered = facts.render(target, [], [], ["AGENTS.md"], [])

    ci = [line for line in rendered.facts.splitlines() if line.startswith("- CI test: ")]
    assert ci == [
        "- CI test: `cd api && go test ./...`, "
        "`cd services && cd api && go vet ./... && go test -race ./...`, "
        "`cd packages/web && npm test --reporter=dot`, `cd services && pytest tests/contract` "
        "(.github/workflows/monorepo.yml); "
        "`npm test -- --coverage` (.github/workflows/node.yml); "
        "`pytest --junitxml=report.xml` (.gitlab-ci.yml)"
    ]
    unsettled = [note for note in rendered.unverified if note.startswith("CI test: ")]
    assert len(unsettled) == 1 and ".github/workflows/matrix.yml" in unsettled[0]
    for path in [*files, ".gitlab-ci.yml"]:
        digest = hashlib.sha256((target / path).read_bytes()).hexdigest()
        assert rendered.inputs[path] == digest


UNSETTLED = """\
on: push
jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.12"]
    steps:
      - run: pytest --basetemp="$RUNNER_TEMP/t-${{ matrix.python-version }}"
      - run: |
          cd integration
          make test
      - working-directory: ${{ matrix.package }}
        run: npm test
      - run: >
          pytest
          -k smoke
      - run: make test-data && npm run test:watch
      - run: bash scripts/run-tests.sh
      - run: make test  # the suite
"""


def test_each_command_it_cannot_settle_is_named_and_the_rest_of_its_file_stays(
    tmp_path: Path,
) -> None:
    """An expression anywhere in a test command, a `cd` earlier in its step, an expression for
    its directory and a folded value each leave that one command out; the settled ones stay."""

    target = project(tmp_path, workflows(ci=UNSETTLED))

    (read,) = facts.read_ci(target)

    assert read.tests == ("bash scripts/run-tests.sh", "make test")
    assert len(read.unread) == 4
    notes = "\n".join(read.unread)
    for fragment in ("${{ matrix.python-version }}", "`make test` runs after", "`npm test`"):
        assert fragment in notes
    assert "test-data" not in notes and "test:watch" not in notes
    rendered = facts.render(target, [], [], ["AGENTS.md"], [])
    line = "- CI test: `bash scripts/run-tests.sh`, `make test` (.github/workflows/ci.yml)"
    assert line in rendered.facts.splitlines()
    assert sum(note.startswith("CI test: .github") for note in rendered.unverified) == 4


GITLAB_CD = """\
unit:
  before_script:
    - cd app
  script:
    - npm test
  after_script:
    - make test
"""


def test_a_cd_earlier_in_a_gitlab_job_leaves_its_later_tests_unsettled(tmp_path: Path) -> None:
    target = project(tmp_path, {".gitlab-ci.yml": GITLAB_CD})

    (read,) = facts.read_ci(target)

    assert read.tests == ("make test",)
    assert len(read.unread) == 1 and "`npm test` runs after" in read.unread[0]


def test_the_edges_the_shipped_stack_fragments_share_read_once(tmp_path: Path) -> None:
    catalog = load_all(ROOT)
    selected = [catalog[name] for name in ("ci-release", "node-typescript", "python")]

    lines = facts.render(tmp_path, selected, [], ["AGENTS.md"], []).facts.splitlines()

    (edges,) = [line for line in lines if line.startswith("- Irreversible edges: ")]
    acts = edges.removeprefix("- Irreversible edges: ").split("; ")
    assert len(acts) == len(set(acts)) and sum("publish" in act for act in acts) == 2


def test_done_names_every_command_in_run_order(tmp_path: Path) -> None:
    for done, line in [
        (["make test"], "- Done: `make test`"),
        (["make check", "make test"], "- Done: `make check` and `make test`"),
        (["a", "b", "c"], "- Done: `a`, `b` and `c`"),
    ]:
        assert line in facts.render(tmp_path, [], done, ["AGENTS.md"], []).facts.splitlines()


def test_a_linked_workflow_is_not_followed(tmp_path: Path) -> None:
    outside = project(tmp_path / "outside", {"ci.yml": NODE})
    target = project(tmp_path / "t", {".github/workflows/.keep": ""})
    (target / ".github/workflows/ci.yml").symlink_to(outside / "ci.yml")

    (read,) = facts.read_ci(target)

    assert read.tests == () and read.unread and read.data is None


@pytest.mark.parametrize(
    ("files", "left_out"),
    [
        ({}, {"Done", "CI test", "Irreversible edges"}),
        (workflows(release=RELEASE), {"Done", "CI test", "Irreversible edges"}),
        (workflows(ci=MATRIX), {"Done", "CI test", "Irreversible edges"}),
        ({**workflows(ci=NODE), facts.FLOOR: "{}\n"}, {"Done"}),
    ],
    ids=["nothing", "no-test", "unsettled", "floor-and-ci"],
)
def test_a_fact_it_cannot_observe_is_left_out_and_named_unverified(
    tmp_path: Path, files: dict[str, str], left_out: set[str]
) -> None:
    target = project(tmp_path, files)

    rendered = facts.render(target, [], [], ["AGENTS.md"], [])

    written = {line[2:].split(":", 1)[0] for line in rendered.facts.splitlines()[1:-1]}
    named = {note.split(":", 1)[0] for note in rendered.unverified}
    assert named == left_out
    # Text for people is chosen with --human-style, not observed: absent, it is not unverified.
    assert written == set(facts.LABELS) - left_out - {"Text for people"}
    assert "Precedence" in written


def test_moved_names_each_fact_whose_line_changed(tmp_path: Path) -> None:
    target = project(tmp_path, workflows(ci=NODE))
    before = facts.render(target, [], ["make test"], ["AGENTS.md"], []).facts
    project(target, workflows(ci=NODE.replace("npm test -- --coverage", "npm test")))

    after = facts.render(target, [], ["make test"], ["AGENTS.md"], []).facts

    assert facts.moved(before, after) == ["CI test"]
    assert facts.moved(before, before) == []


def test_a_command_with_backticks_stays_one_code_span() -> None:
    assert facts.code("echo `date`") == "`` echo `date` ``"
    assert facts.code("make test") == "`make test`"
