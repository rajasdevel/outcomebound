"""scripts/release-check.py on fixture repositories: each disagreement fails its own check, and
only that one."""

import importlib.util
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "release-check.py"
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
}


def release_files(case: str) -> dict[str, str]:
    files = {
        "CHANGELOG.md": f"## [Unreleased]\n\n## [1.1.0] - 2026-09-28\n\n{COMPARE}\n{LINK}\n",
        "templates/ci/github-actions.yml": (
            '        run: python -m pip install "git+https://github.com/example/outcomebound@v1.1.0"\n'
        ),
        "templates/ci/gitlab-ci.yml": "    - pip install git+https://github.com/example/outcomebound@v1.1.0\n",
        "README.md": "uv tool install git+https://github.com/example/outcomebound@v1.1.0\n",
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
    missing = {"test", "windows", "container"} - needed
    assert not missing, "release omits required jobs: " + ", ".join(sorted(missing))
    assert fields.get("if") == "startsWith(github.ref, 'refs/tags/v')", (
        "release must run only for a version tag after its dependencies succeed"
    )


def test_release_publication_waits_for_every_platform_job() -> None:
    workflow = SCRIPT.parent.parent / ".github/workflows/ci.yml"
    _assert_release_waits_for_platforms(workflow.read_text(encoding="utf-8"))


@pytest.mark.parametrize("omitted", ["test", "windows", "container"])
def test_release_contract_rejects_an_omitted_platform_job(omitted: str) -> None:
    workflow = (SCRIPT.parent.parent / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    needed = ", ".join(name for name in ("test", "windows", "container") if name != omitted)
    broken = re.sub(r"(?m)^    needs: .+$", f"    needs: [{needed}]", workflow)
    with pytest.raises(AssertionError, match=f"release omits required jobs: {omitted}"):
        _assert_release_waits_for_platforms(broken)
