"""scripts/release-check.py on fixture repositories: each disagreement fails its own check, and
only that one."""

import importlib.util
import json
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "release-check.py"
BACKEND = SCRIPT.with_name("build_backend.py")
WORKFLOW = SCRIPT.parent.parent / ".github/workflows/ci.yml"
LINK = "[1.1.0]: https://github.com/rajasdevel/outcomebound/releases/tag/v1.1.0"
COMPARE = "[Unreleased]: https://github.com/rajasdevel/outcomebound/compare/v1.1.0...HEAD"

# Each case, and the one check it fails.
CASES = {
    "agreeing": None,
    "dirty": "the tree matches HEAD",
    "undated": "dated 1.1.0 section",
    "wrong-link": "links 1.1.0",
    "stale-compare": "compares Unreleased from v1.1.0",
    "stale-pin": "pins v1.1.0",
    "stale-readme": "README.md installs v1.1.0",
    "stale-gitlab": "every other install line pins it",
    "stale-scaffold": "every other install line pins it",
    "lightweight": "is annotated",
    "wrong-tag": "names VERSION",
    "tag-behind": "points at HEAD",
    "main-red": "no passing CI run on main",
    "main-unrun": "no passing CI run on main (none)",
    "main-other-commit": "no passing CI run on main (none)",
    "main-other-workflow": "no passing CI run on main (none)",
    "main-by-hand": None,
    "main-fork": "no passing CI run on main (none)",
    "main-pass-then-fail": "no passing CI run on main (failure, success)",
    "pypi-unpinned": "the action is not pinned by full commit",
    "pypi-wide-token": "id-token: write is granted for the whole workflow",
    "pypi-no-environment": "it is not in the environment pypi",
    "pypi-before-release": "it does not need release",
    "metadata-no-license": "the package metadata is what PyPI accepts; no License-Expression",
}

# GitHub's answer for HEAD's CI runs in each case; every other case has a passing run on main.
MAIN = {
    "path": ".github/workflows/ci.yml",
    "event": "push",
    "head_branch": "main",
    "repository": {"full_name": "rajasdevel/outcomebound"},
    "created_at": "2026-10-05T10:00:00Z",
}
RUNS = {
    "main-red": [{**MAIN, "status": "completed", "conclusion": "failure"}],
    "main-unrun": [
        {**MAIN, "event": "pull_request", "status": "completed", "conclusion": "success"}
    ],
    "main-other-commit": [
        {**MAIN, "head_sha": "0" * 40, "status": "completed", "conclusion": "success"}
    ],
    "main-other-workflow": [
        {**MAIN, "path": ".github/workflows/x.yml", "status": "completed", "conclusion": "success"}
    ],
}
PASSING = [{**MAIN, "status": "completed", "conclusion": "success"}]
RUNS["main-fork"] = [
    {
        **MAIN,
        "repository": {"full_name": "someone/outcomebound"},
        "status": "completed",
        "conclusion": "success",
    }
]
RUNS["main-pass-then-fail"] = [
    {**MAIN, "status": "completed", "conclusion": "success"},
    {**MAIN, "created_at": "2026-10-05T11:00:00Z", "status": "completed", "conclusion": "failure"},
]
RUNS["main-by-hand"] = [
    {**MAIN, "event": "workflow_dispatch", "status": "completed", "conclusion": "success"}
]


# The files a release commit holds, and the one each disagreeing case makes stale.
STALE = {
    "undated": ("CHANGELOG.md", " - 2026-09-28", ""),
    "wrong-link": ("CHANGELOG.md", "tag/v1.1.0", "tag/v1.0.0"),
    "stale-compare": ("CHANGELOG.md", "compare/v1.1.0", "compare/v1.0.1"),
    "stale-pin": ("templates/ci/github-actions.yml", "v1.1.0", "v1.0.0"),
    "stale-readme": ("README.md", "v1.1.0", "v1.0.0"),
    "stale-gitlab": ("templates/ci/gitlab-ci.yml", "v1.1.0", "v1.0.0"),
    # The CI workflow the scaffold writes names its release, as the CI templates do.
    "stale-scaffold": ("templates/scaffold/common/ci.yml", "v1.1.0", "v1.0.0"),
    "pypi-unpinned": (
        ".github/workflows/ci.yml",
        "gh-action-pypi-publish@",
        "gh-action-pypi-publish@release/v1 # ",
    ),
    "pypi-wide-token": (
        ".github/workflows/ci.yml",
        "permissions:\n  contents: read\n",
        "permissions:\n  id-token: write\n  contents: read\n",
    ),
    "pypi-no-environment": (".github/workflows/ci.yml", "    environment: pypi\n", ""),
    "pypi-before-release": (".github/workflows/ci.yml", "    needs: [release]\n", ""),
    "metadata-no-license": (
        "scripts/build_backend.py",
        'f"License-Expression: {LICENSE_EXPRESSION}",',
        "",
    ),
}


def release_files(case: str) -> dict[str, str]:
    files = {
        "CHANGELOG.md": f"## [Unreleased]\n\n## [1.1.0] - 2026-09-28\n\n{COMPARE}\n{LINK}\n",
        "templates/ci/github-actions.yml": (
            '        run: python -m pip install "git+https://github.com/example/outcomebound@v1.1.0"\n'
        ),
        "templates/ci/gitlab-ci.yml": "    - pip install git+https://github.com/example/outcomebound@v1.1.0\n",
        "templates/scaffold/common/ci.yml": (
            '        run: python -m pip install "git+https://github.com/example/outcomebound@v1.1.0"\n'
        ),
        "README.md": "uv tool install git+https://github.com/example/outcomebound@v1.1.0\n",
        # The release workflow and the build backend are the repository's own: what the two
        # PyPI checks read.
        ".github/workflows/ci.yml": WORKFLOW.read_text(encoding="utf-8"),
        "scripts/build_backend.py": BACKEND.read_text(encoding="utf-8"),
    }
    if case in STALE:
        name, old, new = STALE[case]
        files[name] = files[name].replace(old, new)
    return files


@pytest.mark.parametrize("case", CASES)
def test_each_disagreement_fails_its_own_check(tmp_path: Path, case: str) -> None:
    def git(*args: str) -> None:
        identity = ("-c", "user.name=Release", "-c", "user.email=release@example.test")
        subprocess.run(["git", *identity, *args], cwd=tmp_path, check=True, capture_output=True)

    for name, text in release_files(case).items():
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_text(text)
    (tmp_path / "VERSION").write_text("1.1.0\n")
    git("init", "-q")
    git("add", ".")
    git("commit", "-qm", "release")
    git("tag", "-a", "v1.0.0", "-m", "an older release's tag")
    if case == "lightweight":
        git("tag", "v1.1.0")
    else:
        git("tag", "-a", "v1.1.0", "-m", "release")
    if case == "tag-behind":
        git("commit", "--allow-empty", "-qm", "later")
    elif case == "dirty":
        (tmp_path / "VERSION").write_text("1.1.0\n\n")

    tag = "v1.0.0" if case == "wrong-tag" else "v1.1.0"
    runs = tmp_path.parent / f"{tmp_path.name}-runs.json"
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=tmp_path, check=True, capture_output=True, text=True
    ).stdout.strip()
    answer = [{"head_sha": head, **run} for run in RUNS.get(case, PASSING)]
    runs.write_text(json.dumps({"workflow_runs": answer}))
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--root",
            str(tmp_path),
            "--tag",
            tag,
            "--ci-runs",
            str(runs),
        ],
        capture_output=True,
        text=True,
    )
    lines = result.stdout.splitlines()
    assert lines[-1].startswith("GRANT none covers v1.1.0"), result.stdout
    failed = [line for line in lines[:-1] if not line.startswith("PASS ")]
    said, expected = result.stdout + result.stderr, CASES[case]
    if expected is None:
        assert failed == [] and result.returncode == 0, said
    else:
        assert len(failed) == 1 and failed[0].startswith("FAIL "), said
        assert expected in failed[0] and result.returncode == 1, said


def test_a_pass_read_from_a_saved_file_says_it_is_a_snapshot(tmp_path: Path) -> None:
    """Breaks if a CI pass read from a saved file reads as GitHub's current answer: a later
    failure of the same commit would not show in it."""

    spec = importlib.util.spec_from_file_location("release_check", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    head = "a" * 40
    saved = tmp_path / "runs.json"
    saved.write_text(json.dumps({"workflow_runs": [{"head_sha": head, **PASSING[0]}]}))
    passed, what = module.main_ci(head, saved)
    assert passed and "snapshot" in what and "runs.json" in what, what


CODE_ALERT = {
    "number": 7,
    "rule": {"id": "py/example"},
    "most_recent_instance": {"location": {"path": "a.py", "start_line": 3}},
}


@pytest.mark.parametrize(
    ("saved", "failing"),
    [
        ({"code-scanning": [], "dependabot": [], "secret-scanning": []}, []),
        (
            {"code-scanning": [CODE_ALERT], "dependabot": [], "secret-scanning": []},
            ["no open code scanning alert; open: #7 py/example in a.py:3"],
        ),
        (
            {"code-scanning": [], "dependabot": [{"number": 2}], "secret-scanning": []},
            ["no open Dependabot alert; open: #2"],
        ),
        (
            {"code-scanning": [], "dependabot": []},
            ["no open secret scanning alert: UNVERIFIED"],
        ),
    ],
)
def test_each_open_or_unreadable_kind_of_alert_fails_its_own_line(
    tmp_path: Path, saved: dict[str, list[object]], failing: list[str]
) -> None:
    """Breaks if an open alert of one kind passes, or a kind that could not be read passes, or one
    kind's alert fails another kind's line."""

    file = tmp_path / "alerts.json"
    file.write_text(json.dumps(saved))
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(SCRIPT.parent.parent), "--alerts", str(file)],
        capture_output=True,
        text=True,
    )
    lines = [line for line in result.stdout.splitlines() if " alert" in line]
    assert len(lines) == 3, result.stdout
    failed = [line.removeprefix("FAIL ") for line in lines if line.startswith("FAIL ")]
    assert len(failed) == len(failing), result.stdout
    for line, expected in zip(failed, failing, strict=True):
        assert line.startswith(expected), line


@pytest.mark.parametrize(
    ("version", "today", "covered"),
    [
        ("2.0.0", date(2026, 10, 31), True),
        ("1.4.3", date(2026, 10, 1), True),
        ("2.0.1", date(2026, 10, 1), False),
        ("1.40.0", date(2026, 10, 1), False),
        ("2.0.0", date(2026, 11, 1), False),
    ],
)
def test_the_grant_line_names_a_grant_only_in_scope_and_in_time(
    tmp_path: Path, version: str, today: date, covered: bool
) -> None:
    spec = importlib.util.spec_from_file_location("release_check", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    (tmp_path / "VERSION").write_text(f"{version}\n")
    (tmp_path / ".outcomebound").mkdir()
    grants = [
        {"scope": scope, "granted_by": "example-user", "on": "2026-10-01", "until": "2026-10-31"}
        for scope in ("1.4.x", "2.0.0")
    ]
    (tmp_path / ".outcomebound/tag-grants.json").write_text(json.dumps({"grants": grants}))
    line = module.grant(tmp_path, today)
    assert line.startswith(f"GRANT v{version}:" if covered else f"GRANT none covers v{version}")


@pytest.mark.parametrize("named", [True, False])
def test_the_section_names_each_pull_request_since_the_previous_release(
    tmp_path: Path, named: bool
) -> None:
    """Breaks if a release section leaves out a pull request that landed since the previous
    release, now that the section is written at release and not by each pull request."""

    def git(*args: str) -> None:
        identity = ("-c", "user.name=Release", "-c", "user.email=release@example.test")
        subprocess.run(["git", *identity, *args], cwd=tmp_path, check=True, capture_output=True)

    files = release_files("agreeing")
    for name, text in files.items():
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_text(text.replace("1.1.0", "1.0.0"))
    (tmp_path / "VERSION").write_text("1.0.0\n")
    git("init", "-q")
    git("add", ".")
    git("commit", "-qm", "release: 1.0.0")
    git("tag", "-a", "v1.0.0", "-m", "release")
    (tmp_path / "src.txt").write_text("x\n")
    git("add", ".")
    git("commit", "-qm", "fix: a change (#5)")
    for name, text in files.items():
        entry = "- A change (#5).\n\n" if named else ""
        (tmp_path / name).write_text(text.replace(" - 2026-09-28\n\n", f" - 2026-09-28\n\n{entry}"))
    (tmp_path / "VERSION").write_text("1.1.0\n")
    git("add", ".")
    git("commit", "-qm", "release: 1.1.0 (#6)")

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(tmp_path)], capture_output=True, text=True
    )

    line = next(x for x in result.stdout.splitlines() if "names each pull request" in x)
    if named:
        assert line.startswith("PASS "), result.stdout
    else:
        assert line.startswith("FAIL ") and "not named: #5" in line, result.stdout
        assert "#6" not in line, "the release commit itself is not counted"


@pytest.mark.parametrize(
    ("subject", "counted"),
    [("release: 1.1.0 (#7)", False), ("release: 1.1.0", False), ("fix: another change (#7)", True)],
)
def test_a_release_cut_again_is_known_by_its_subject(
    tmp_path: Path, subject: str, counted: bool
) -> None:
    """Breaks if a release commit that does not change VERSION, because an earlier cut of the
    same release already set it, is counted as a pull request the section must name; or if an
    ordinary commit at HEAD escapes the count."""

    def git(*args: str) -> None:
        identity = ("-c", "user.name=Release", "-c", "user.email=release@example.test")
        subprocess.run(["git", *identity, *args], cwd=tmp_path, check=True, capture_output=True)

    files = release_files("agreeing")
    for name, text in files.items():
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_text(text.replace("1.1.0", "1.0.0"))
    (tmp_path / "VERSION").write_text("1.0.0\n")
    git("init", "-q")
    git("add", ".")
    git("commit", "-qm", "release: 1.0.0")
    git("tag", "-a", "v1.0.0", "-m", "release")
    for name, text in files.items():
        (tmp_path / name).write_text(
            text.replace(" - 2026-09-28\n\n", " - 2026-09-28\n\n- First cut (#6).\n\n")
        )
    (tmp_path / "VERSION").write_text("1.1.0\n")
    git("add", ".")
    git("commit", "-qm", "release: 1.1.0 (#6)")
    (tmp_path / "CHANGELOG.md").write_text(
        (tmp_path / "CHANGELOG.md")
        .read_text()
        .replace("- First cut (#6).", "- First cut (#6), cut again.")
    )
    git("add", ".")
    git("commit", "-qm", subject)

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(tmp_path)], capture_output=True, text=True
    )

    line = next(x for x in result.stdout.splitlines() if "names each pull request" in x)
    if counted:
        assert line.startswith("FAIL ") and "not named: #7" in line, result.stdout
    else:
        assert line.startswith("PASS "), result.stdout


def _assert_release_waits_for_platforms(workflow: str) -> None:
    """Read this workflow's release fields, not an arbitrary YAML document."""

    found = re.search(r"(?ms)^  release:\n(.*?)(?=^  [\w-]+:\n|\Z)", workflow)
    assert found is not None, "CI has no release job"
    fields = dict(re.findall(r"(?m)^    (needs|if): (.+)$", found[1]))
    needed = {name.strip().strip("'\"") for name in fields.get("needs", "").strip("[]").split(",")}
    missing = {"verify-tag", "test", "windows", "container"} - needed
    assert not missing, "release omits required jobs: " + ", ".join(sorted(missing))
    assert fields.get("if") == "startsWith(github.ref, 'refs/tags/v')", (
        "release must run only for a version tag after its dependencies succeed"
    )


def test_release_publication_waits_for_every_platform_job() -> None:
    workflow = SCRIPT.parent.parent / ".github/workflows/ci.yml"
    _assert_release_waits_for_platforms(workflow.read_text(encoding="utf-8"))


@pytest.mark.parametrize("omitted", ["verify-tag", "test", "windows", "container"])
def test_release_contract_rejects_an_omitted_platform_job(omitted: str) -> None:
    workflow = (SCRIPT.parent.parent / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    needed = ", ".join(
        name for name in ("verify-tag", "test", "windows", "container") if name != omitted
    )
    broken = re.sub(r"(?m)^    needs: .+$", f"    needs: [{needed}]", workflow)
    with pytest.raises(AssertionError, match=f"release omits required jobs: {omitted}"):
        _assert_release_waits_for_platforms(broken)


def test_release_tag_is_verified_once_not_in_each_matrix_leg() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert workflow.count("scripts/release-check.py --tag") == 1
    found = re.search(r"(?ms)^  verify-tag:\n(.*?)(?=^  [\w-]+:\n|\Z)", workflow)
    assert found is not None and "scripts/release-check.py --tag" in found[1]


@pytest.mark.skipif(shutil.which("make") is None, reason="no make on this machine")
def test_release_check_with_a_tag_leaves_gate_floor_and_suite_to_ci_and_runs_scrub() -> None:
    root = SCRIPT.parent.parent
    base = subprocess.run(["make", "-n", "release-check"], cwd=root, capture_output=True, text=True)
    tagged = subprocess.run(
        ["make", "-n", "release-check", "TAG=v1.0.0"], cwd=root, capture_output=True, text=True
    )
    assert base.returncode == 0 and tagged.returncode == 0, base.stderr + tagged.stderr
    for out in (base.stdout, tagged.stdout):
        assert "check-public-text.py --private" in out
    assert "pytest" in base.stdout
    assert "pytest" not in tagged.stdout and "floor check" not in tagged.stdout
