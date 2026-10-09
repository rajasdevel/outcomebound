"""The recent-authors and release-identity signals of `adopt --detect`, and the drift lines of
`adopt --check` and `--detect`: one line for each signal a project's files show that its recorded
fragment selection, or the `local` fragment's exposure line, contradicts. Every project here is a
temporary Git repository with synthetic authors; no line refuses anything or moves an exit code."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from outcomebound_tools import drift
from tests.adopt_helpers import GIT, Capture, change_kernel, engine_copy, repo, run, states

TEAM_LINE = "record says team not selected"
DEPLOY_LINE = "deploy configuration present, record says deploy not selected"
PUBLISH_LINE = "publishing workflow present, record says ci-release not selected"
RELEASE_WORKFLOW = {".github/workflows/release.yml": "name: release\non: push\njobs: {}\n"}
ONE = "alice@example.org"
TWO = "bob@example.org"


def commit(target: Path, email: str, name: str | None = None, message: str = "c") -> None:
    """One commit by `email`, with nothing in it; the name is the email's local part unless given."""

    identity = [
        "-c",
        f"user.name={name or email.split('@')[0]}",
        "-c",
        f"user.email={email}",
        "-c",
        "commit.gpgsign=false",
    ]
    subprocess.run(
        [GIT, "-C", str(target), *identity, "commit", "-q", "--allow-empty", "-m", message],
        check=True,
    )


def local_fragment(exposure: str | None) -> str:
    """A `local` fragment holding `exposure` as its one `Exposure —` line, or none."""

    line = "" if exposure is None else f"{exposure}\n"
    return (
        "---\nid: local\nfamily: setup\napplies: a synthetic project\nedges: []\ndetect: []\n"
        "version: 1\n---\n"
        f"**Context** — the synthetic project.\n{line}"
        "**Bounds** — nothing irreversible.\n**Mechanisms** — none.\n"
        "**Completion bar** — the tests.\n**Distinguish** — nothing.\n"
    )


def installed(target: Path, capsys: Capture, fragments: str = "commands") -> None:
    code, _, err = run(
        capsys, str(target), "--harness", "claude-code", "--fragments", fragments, "--done", "true"
    )
    assert code == 0, err


def drift_lines(out: str) -> list[str]:
    """The drift lines of a `--check` or `--detect` output, without their prefix."""

    prefixes = ("drift ", "# drift: ")
    return [
        line.split(" ", 1)[1].strip() if line.startswith("drift ") else line[len("# drift: ") :]
        for line in out.splitlines()
        if line.startswith(prefixes)
    ]


def two_authors(target: Path) -> None:
    commit(target, ONE)
    commit(target, TWO)


def test_a_project_whose_files_agree_with_its_record_prints_no_drift_line(
    tmp_path: Path, capsys: Capture
) -> None:
    """Breaks if a signal the record already answers still prints a line: two authors with
    `team`, a CODEOWNERS file, a deploy file with `deploy`, a release workflow with `ci-release`,
    and an exposure line saying more than one person."""

    files = {
        ".github/CODEOWNERS": "* @someone\n",
        "fly.toml": "app = 'x'\n",
        ".outcomebound/fragments/local.md": local_fragment(
            "Exposure — maintained by: two people (confirmed)"
        ),
        **RELEASE_WORKFLOW,
    }
    target = repo(tmp_path / "t", files)
    two_authors(target)
    installed(target, capsys, "team,deploy,ci-release,local")

    check = run(capsys, str(target), "--check")
    detect = run(capsys, str(target), "--detect")

    assert check[0] == 0 and drift_lines(check[1]) == []
    assert detect[0] == 0 and drift_lines(detect[1]) == []


def test_two_recent_authors_without_team_print_a_line_and_detect_counts_them(
    tmp_path: Path, capsys: Capture
) -> None:
    """Breaks if two authors with no `team` print nothing, or the line or the signal names an
    author or an address instead of the count."""

    target = repo(tmp_path / "t")
    two_authors(target)
    installed(target, capsys)

    _, check, _ = run(capsys, str(target), "--check")
    _, detect, _ = run(capsys, str(target), "--detect")

    assert drift_lines(check) == ["2 recent authors present, record says team not selected"]
    assert drift_lines(detect) == drift_lines(check)
    signal = next(line for line in detect.splitlines() if "signal recent-authors" in line)
    assert signal.endswith("; value: 2; local slot: Context")
    assert "alice" not in check + detect and "example.org" not in check + detect


def test_solo_selected_with_two_recent_authors_prints_a_line(
    tmp_path: Path, capsys: Capture
) -> None:
    """Breaks if selecting `solo` hides the second author, or the line leaves out that the
    record says solo."""

    target = repo(tmp_path / "t")
    two_authors(target)
    installed(target, capsys, "solo,team")

    _, out, _ = run(capsys, str(target), "--check")

    assert drift_lines(out) == ["2 recent authors present, record says solo selected"]


def test_a_codeowners_file_without_team_prints_a_line(tmp_path: Path, capsys: Capture) -> None:
    """Breaks if a CODEOWNERS file alone, with one author, prints nothing without `team`."""

    target = repo(tmp_path / "t", {".github/CODEOWNERS": "* @someone\n"})
    commit(target, ONE)
    installed(target, capsys)

    _, out, _ = run(capsys, str(target), "--check")

    assert drift_lines(out) == ["CODEOWNERS present, record says team not selected"]


def test_a_deploy_file_without_deploy_prints_a_line(tmp_path: Path, capsys: Capture) -> None:
    """Breaks if a deploy configuration the `deploy` fragment detects prints nothing while
    `deploy` is not selected, or still prints once it is."""

    target = repo(tmp_path / "t", {"fly.toml": "app = 'x'\n"})
    commit(target, ONE)
    installed(target, capsys)

    _, out, _ = run(capsys, str(target), "--detect")
    assert drift_lines(out) == [DEPLOY_LINE]

    installed(target, capsys, "commands,deploy")
    _, again, _ = run(capsys, str(target), "--check")
    assert drift_lines(again) == []


def workflow(command: str) -> dict[str, str]:
    """A workflow, not named for release or deploy, with one step that runs `command`."""

    text = (
        "on: push\njobs:\n  ship:\n    runs-on: ubuntu-latest\n"
        f"    steps:\n      - run: {command}\n"
    )
    return {".github/workflows/ship.yml": text}


@pytest.mark.parametrize("command", ["twine upload dist/*", "npm publish"])
def test_a_package_publishing_workflow_without_ci_release_prints_a_line(
    tmp_path: Path, capsys: Capture, command: str
) -> None:
    """Breaks if a workflow that publishes a package (by a step, in a file not named release)
    prints nothing while `ci-release` is not selected, or still prints once it is."""

    target = repo(tmp_path / "t", workflow(command))
    commit(target, ONE)
    installed(target, capsys)

    _, out, _ = run(capsys, str(target), "--check")
    assert drift_lines(out) == [PUBLISH_LINE]

    installed(target, capsys, "commands,ci-release")
    _, again, _ = run(capsys, str(target), "--check")
    assert drift_lines(again) == []


def test_a_deploy_only_workflow_prints_the_deploy_line_and_no_ci_release_line(
    tmp_path: Path, capsys: Capture
) -> None:
    """Breaks if a workflow that only deploys a service (`fly deploy`, in a file whose name holds
    neither deploy nor release) sends the project to `ci-release`, or is not named for `deploy`."""

    target = repo(tmp_path / "t", workflow("fly deploy --remote-only"))
    commit(target, ONE)
    installed(target, capsys)

    _, out, _ = run(capsys, str(target), "--detect")
    assert drift_lines(out) == [DEPLOY_LINE]

    installed(target, capsys, "commands,deploy")
    _, again, _ = run(capsys, str(target), "--check")
    assert drift_lines(again) == []


def test_a_release_named_workflow_that_only_deploys_prints_the_deploy_line_alone(
    tmp_path: Path, capsys: Capture
) -> None:
    """Breaks if the name `release.yml` alone sends a workflow whose steps deploy a service and
    publish nothing to `ci-release`, or a release-named workflow with no publish and no deploy
    step stops printing the ci-release line."""

    text = workflow("fly deploy --remote-only")[".github/workflows/ship.yml"]
    target = repo(tmp_path / "t", {".github/workflows/release.yml": text})
    commit(target, ONE)
    installed(target, capsys)

    _, out, _ = run(capsys, str(target), "--check")
    assert drift_lines(out) == [DEPLOY_LINE]

    named = repo(tmp_path / "n", RELEASE_WORKFLOW)
    commit(named, ONE)
    installed(named, capsys)
    _, again, _ = run(capsys, str(named), "--check")
    assert drift_lines(again) == [PUBLISH_LINE]


def test_a_workflow_that_only_pushes_an_image_prints_neither_deploy_nor_ci_release(
    tmp_path: Path, capsys: Capture
) -> None:
    """Breaks if `docker push`, which names neither a package nor a service, prints a line."""

    target = repo(tmp_path / "t", workflow("docker push registry.example/app"))
    commit(target, ONE)
    installed(target, capsys)

    _, out, _ = run(capsys, str(target), "--check")

    assert drift_lines(out) == []


def test_an_exposure_line_that_says_one_person_beside_two_authors_prints_a_line(
    tmp_path: Path, capsys: Capture
) -> None:
    """Breaks if the exposure line is not read, or is read when its `maintained by:` fact does not
    say one person, or when it wraps over two lines."""

    wrapped = (
        "Exposure — who can be hurt: its users; maintained by:\n"
        "  one person (confirmed); agents write most"
    )
    target = repo(tmp_path / "t", {".outcomebound/fragments/local.md": local_fragment(wrapped)})
    two_authors(target)
    installed(target, capsys, "team,local")

    _, out, _ = run(capsys, str(target), "--check")

    assert drift_lines(out) == [
        "2 recent authors present, record says the local Exposure line is maintained by one person"
    ]


@pytest.mark.parametrize(
    "exposure",
    [
        pytest.param(None, id="no-line"),
        pytest.param("Exposure — who can be hurt: its users", id="no-fact"),
        pytest.param("Exposure — maintained by: nobody knows", id="not-parsed"),
        pytest.param("Exposure — maintained by: two people", id="two"),
        pytest.param("Exposure - maintained by: three or more", id="more"),
    ],
)
def test_an_exposure_line_that_is_missing_or_does_not_parse_prints_nothing(
    tmp_path: Path, capsys: Capture, exposure: str | None
) -> None:
    """Breaks if a missing line, a line without the fact, or a value that is not one person
    prints a line."""

    target = repo(tmp_path / "t", {".outcomebound/fragments/local.md": local_fragment(exposure)})
    two_authors(target)
    installed(target, capsys, "team,local")

    _, out, _ = run(capsys, str(target), "--check")

    assert drift_lines(out) == []


def test_a_project_with_no_install_prints_no_drift_line(tmp_path: Path, capsys: Capture) -> None:
    """Breaks if `--check` or `--detect` prints a drift line where nothing is installed, though
    the files show every signal."""

    files = {".github/CODEOWNERS": "* @x\n", "fly.toml": "a = 1\n", **RELEASE_WORKFLOW}
    target = repo(tmp_path / "t", files)
    two_authors(target)

    check = run(capsys, str(target), "--check")
    detect = run(capsys, str(target), "--detect")

    assert check[0] == 1 and drift_lines(check[1]) == []
    assert detect[0] == 0 and drift_lines(detect[1]) == []
    assert "signal recent-authors" in detect[1]


def test_two_bots_and_one_person_count_as_one_author(tmp_path: Path, capsys: Capture) -> None:
    """Breaks if an automation address or name counts as an author, a person's private
    `users.noreply.github.com` address does not, or the same address in two cases counts twice."""

    target = repo(tmp_path / "t")
    commit(target, "49699333+dependabot[bot]@users.noreply.github.com", "dependabot[bot]")
    commit(target, "noreply@example.org", "A Service")
    commit(target, "ci@example.org", "github-actions[bot]")
    commit(target, "release-bot@example.org", "Releaser")
    commit(target, "12345+carol@users.noreply.github.com", "Carol")
    commit(target, "12345+CAROL@users.noreply.github.com", "Carol")

    assert drift.recent_authors(target) == 1

    installed(target, capsys)
    _, out, _ = run(capsys, str(target), "--detect")
    assert drift_lines(out) == []
    assert "signal recent-authors" not in out


def test_the_window_is_the_last_hundred_commits_without_merges(tmp_path: Path) -> None:
    """Breaks if an author older than the window counts, or the window is not a count of commits."""

    target = repo(tmp_path / "t")
    commit(target, TWO)
    for _ in range(drift.WINDOW):
        commit(target, ONE)

    assert drift.recent_authors(target) == 1


def test_the_authors_signal_needs_two_authors(tmp_path: Path, capsys: Capture) -> None:
    """Breaks if an empty history, or a single author, prints the signal, or two authors do
    not."""

    target = repo(tmp_path / "t")
    assert "signal recent-authors" not in run(capsys, str(target), "--detect")[1]
    commit(target, ONE)
    commit(target, ONE, "Same Person")
    assert "signal recent-authors" not in run(capsys, str(target), "--detect")[1]

    commit(target, TWO)

    out = run(capsys, str(target), "--detect")[1]
    assert any(
        line.startswith("# signal recent-authors") and "; value: 2;" in line
        for line in out.splitlines()
    )


@pytest.mark.parametrize(
    "version", ["1.2.3\n", "v1.2\n", "2.0.0-rc.1\n"], ids=["plain", "short-v", "pre-release"]
)
def test_detect_reports_a_version_file_as_release_identity(
    tmp_path: Path, capsys: Capture, version: str
) -> None:
    """Breaks if a `VERSION` file that holds a version is not read."""

    target = repo(tmp_path / "t", {"VERSION": version})

    _, out, _ = run(capsys, str(target), "--detect")

    assert "# signal release-identity: VERSION; local slot: Distinguish" in out.splitlines()


@pytest.mark.parametrize(
    "files",
    [
        pytest.param({"VERSION": "development build\n"}, id="version-file-without-version"),
        pytest.param({"VERSION": "\n"}, id="empty-version-file"),
        pytest.param({"pyproject.toml": '[project]\nversion = "0.3.0"\n'}, id="pyproject"),
        pytest.param({"package.json": '{"name": "x", "version": "2.0.0"}'}, id="package"),
        pytest.param({"Cargo.toml": '[package]\nversion = "0.1.0"\n'}, id="cargo"),
    ],
)
def test_detect_reports_no_release_identity_without_a_version_file_or_tag(
    tmp_path: Path, capsys: Capture, files: dict[str, str]
) -> None:
    """Breaks if a version in a package manifest, which nearly every package carries, or a
    `VERSION` file that holds no version, is release identity."""

    target = repo(tmp_path / "t", files)

    assert "release-identity" not in run(capsys, str(target), "--detect")[1]


@pytest.mark.parametrize(
    ("tag", "shown"),
    [
        pytest.param("v1.0.0", True, id="v-three"),
        pytest.param("1.2.3", True, id="bare"),
        pytest.param("v1.2", True, id="v-two"),
        pytest.param("v2.0.0-rc.1", True, id="pre-release"),
        pytest.param("seed", False, id="word"),
        pytest.param("release-2024", False, id="release-word"),
        pytest.param("v1", False, id="one-number"),
    ],
)
def test_detect_reports_a_version_like_tag_and_not_any_other(
    tmp_path: Path, capsys: Capture, tag: str, shown: bool
) -> None:
    """Breaks if a tag that is a version is not release identity, or a tag that is not one is."""

    target = repo(tmp_path / "t")
    commit(target, ONE)
    subprocess.run([GIT, "-C", str(target), "tag", tag], check=True)

    out = run(capsys, str(target), "--detect")[1]

    line = "# signal release-identity: version-like git tags; local slot: Distinguish"
    assert (line in out.splitlines()) is shown


def test_drift_lines_leave_the_check_exit_code_as_the_artifacts_give_it(
    tmp_path: Path, capsys: Capture
) -> None:
    """Breaks if a drift line is counted in the exit, or hides the count of artifacts that are
    not current: 0 for a current install with drift, 1 when one artifact is stale."""

    source = engine_copy(tmp_path)
    target = repo(tmp_path / "t", {"fly.toml": "a = 1\n", ".github/CODEOWNERS": "* @x\n"})
    two_authors(target)
    code, _, err = run(
        capsys, str(target), "--harness", "claude-code", "--fragments", "commands", source=source
    )
    assert code == 0, err

    code, out, _ = run(capsys, str(target), "--check", source=source)
    assert code == 0 and len(drift_lines(out)) == 3
    assert set(states(out).values()) == {"current"}

    change_kernel(source, "9.9.9")
    code, out, _ = run(capsys, str(target), "--check", source=source)
    assert code == 1 and len(drift_lines(out)) == 3


def test_one_name_under_two_emails_is_one_author(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Breaks if one person who commits under two emails with one name counts as two authors, so
    that a project with one maintainer reads as a team, or if two names with two emails count as
    one."""

    target = repo(tmp_path / "one")
    commit(target, ONE, "Alice Doe")
    commit(target, "alice@work.example", "Alice Doe")
    assert drift.recent_authors(target) == 1
    commit(target, TWO, "Bob Roe")
    assert drift.recent_authors(target) == 2
