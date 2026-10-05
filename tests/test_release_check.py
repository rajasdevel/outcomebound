"""scripts/release-check.py on fixture repositories: each disagreement fails its own check, and
only that one."""

import importlib.util
import json
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
    "main-red": "no passing CI run of a push to main",
    "main-unrun": "no passing CI run of a push to main (none)",
}

# GitHub's answer for HEAD's CI runs in each case; every other case has a passing run on main.
RUNS = {
    "main-red": [{"event": "push", "head_branch": "main", "conclusion": "failure"}],
    "main-unrun": [{"event": "pull_request", "head_branch": "x", "conclusion": "success"}],
}
PASSING = [{"event": "push", "head_branch": "main", "conclusion": "success"}]


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
    if case == "lightweight":
        git("tag", "v1.1.0")
    else:
        git("tag", "-a", "v1.1.0", "-m", "release")
        git("tag", "-a", "v1.0.0", "-m", "an older release's tag")
    if case == "tag-behind":
        git("commit", "--allow-empty", "-qm", "later")
    elif case == "dirty":
        (tmp_path / "VERSION").write_text("1.1.0\n\n")

    tag = "v1.0.0" if case == "wrong-tag" else "v1.1.0"
    runs = tmp_path.parent / f"{tmp_path.name}-runs.json"
    runs.write_text(json.dumps({"workflow_runs": RUNS.get(case, PASSING)}))
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
