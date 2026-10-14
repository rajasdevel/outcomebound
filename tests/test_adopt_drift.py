"""The recent-authors and release-identity signals of `adopt --detect`, and the drift lines of
`adopt --check` and `--detect`: one line for each signal a project's files show that its recorded
fragment selection, or the `local` fragment's exposure line, contradicts. Every project here is a
temporary Git repository with synthetic authors; no line refuses anything or moves an exit code."""

from __future__ import annotations

import json
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
    """One commit by `email`, with nothing in it; the name is the email's local part unless
    given."""

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


def local_fragment(
    exposure: str | list[str] | None, edges: list[str] | None = None, bounds: str = ""
) -> str:
    """A `local` fragment holding `exposure` as its `Exposure —` line (or one for each stream, or
    none), the declared `edges` and, in its Bounds slot, the extra `bounds` lines."""

    lines = [exposure] if isinstance(exposure, str) else exposure or []
    text = "".join(f"{line}\n" for line in lines)
    declared = json.dumps(edges or [])
    extra = f"{bounds}\n" if bounds else ""
    return (
        f"---\nid: local\nfamily: setup\napplies: a synthetic project\nedges: {declared}\n"
        "detect: []\nversion: 1\n---\n"
        f"**Context** — the synthetic project.\n{text}"
        f"**Bounds** — nothing irreversible.\n{extra}**Mechanisms** — none.\n"
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


def test_two_recent_authors_without_team_print_no_line_and_detect_counts_them(
    tmp_path: Path, capsys: Capture
) -> None:
    """Breaks if two authors alone claim a team (a contributor is not a maintainer, and a project
    that selected neither `solo` nor `team` has said nothing), or the signal names an author or an
    address instead of the count."""

    target = repo(tmp_path / "t")
    two_authors(target)
    installed(target, capsys)

    _, check, _ = run(capsys, str(target), "--check")
    _, detect, _ = run(capsys, str(target), "--detect")

    assert drift_lines(check) == [] and drift_lines(detect) == []
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
        pytest.param("Exposure — maintained by: one developer and a lead", id="and"),
        pytest.param("Exposure — maintained by: One of the two maintainers, by rota", id="of-the"),
        pytest.param("Exposure — maintained by: a single team of four", id="team"),
        pytest.param(
            "Exposure — maintained by: one person (the owner) and a contractor", id="note-then-and"
        ),
        pytest.param(
            [
                "Exposure — stream api: maintained by: one person",
                "Exposure — stream web: maintained by: two people",
            ],
            id="one-stream-of-two",
        ),
    ],
)
def test_an_exposure_line_that_is_missing_or_does_not_parse_prints_nothing(
    tmp_path: Path, capsys: Capture, exposure: str | list[str] | None
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
    """Breaks if the author of the 101st commit back counts, or the 100th does not. The history is
    fixed here, not built from the constant, so that changing the window fails this test."""

    assert drift.WINDOW == 100
    target = repo(tmp_path / "t")
    commit(target, TWO)
    for _ in range(99):
        commit(target, ONE)
    assert drift.recent_authors(target) == 2
    commit(target, ONE)

    assert drift.recent_authors(target) == 1


def test_an_author_present_only_on_a_merge_commit_does_not_count(tmp_path: Path) -> None:
    """Breaks if whoever merged counts as a recent author: a merge commit names the person who
    pressed the button, not who wrote the change."""

    target = repo(tmp_path / "t")
    commit(target, ONE)
    git = [GIT, "-C", str(target)]
    subprocess.run([*git, "checkout", "-q", "-b", "topic"], check=True)
    commit(target, ONE, message="on the topic")
    subprocess.run([*git, "checkout", "-q", "-"], check=True)
    commit(target, ONE, message="on the trunk")
    who = ["-c", "user.name=bob", "-c", f"user.email={TWO}", "-c", "commit.gpgsign=false"]
    subprocess.run([*git, *who, "merge", "-q", "--no-ff", "-m", "merge", "topic"], check=True)

    assert drift.recent_authors(target) == 1


def test_a_mailmap_joins_two_emails_into_one_author(tmp_path: Path) -> None:
    """Breaks if the project's `.mailmap` is not applied, so that one person under two addresses
    and two names reads as two authors."""

    target = repo(tmp_path / "t")
    commit(target, ONE, "Alice Doe")
    commit(target, "alice.doe@work.example", "A. Doe")
    assert drift.recent_authors(target) == 2
    (target / ".mailmap").write_text(f"Alice Doe <{ONE}> <alice.doe@work.example>\n")

    assert drift.recent_authors(target) == 1


def test_two_people_with_one_display_name_count_as_one_author(tmp_path: Path) -> None:
    """The chosen trade-off, not a claim that it is right: identities that share a display name
    are one author. One person under two emails is common, a name collision between two people
    in the recent history of one repository is rare, and the line is information a person reads;
    a count one too low costs one missed line, a count one too high prints a false claim."""

    target = repo(tmp_path / "t")
    commit(target, ONE, "Sam Lee")
    commit(target, TWO, "Sam Lee")

    assert drift.recent_authors(target) == 1


@pytest.mark.parametrize(
    ("mailbox", "counted"),
    [
        pytest.param("talbot", True, id="ends-in-the-letters-bot"),
        pytest.param("abbot", True, id="abbot"),
        pytest.param("release-bot", False, id="hyphen"),
        pytest.param("release_bot", False, id="underscore"),
        pytest.param("release.bot", False, id="dot"),
        pytest.param("bot", False, id="equal-to-bot"),
    ],
)
def test_a_mailbox_is_a_bot_only_with_the_separator(
    tmp_path: Path, mailbox: str, counted: bool
) -> None:
    """Breaks if a person whose mailbox ends in the letters `bot` (Talbot) is left out, or a
    mailbox equal to `bot` or ending in `-bot`, `_bot` or `.bot` is counted."""

    target = repo(tmp_path / "t")
    commit(target, f"{mailbox}@example.org", f"Name of {mailbox}")

    assert drift.recent_authors(target) == (1 if counted else 0)


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
        pytest.param("pkg@1.2.3", True, id="at-prefix"),
        pytest.param("@scope/pkg@1.2.3", True, id="scoped-at-prefix"),
        pytest.param("pkg-v1.2.3", True, id="hyphen-v-prefix"),
        pytest.param("sub/v1.2.3", True, id="slash-v-prefix"),
        pytest.param("release/1.2.3", True, id="release-slash"),
        pytest.param("seed", False, id="word"),
        pytest.param("release-2024", False, id="release-word"),
        pytest.param("v1", False, id="one-number"),
        pytest.param("release/2024", False, id="release-slash-year"),
        pytest.param("pkg-1.2.3", False, id="hyphen-without-v"),
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
    assert code == 0 and len(drift_lines(out)) == 2
    assert set(states(out).values()) == {"current"}

    change_kernel(source, "9.9.9")
    code, out, _ = run(capsys, str(target), "--check", source=source)
    assert code == 1 and len(drift_lines(out)) == 2


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


def test_a_tag_that_is_not_utf8_does_not_stop_the_reading(tmp_path: Path) -> None:
    """Breaks if a tag name with byte 0xff raises, or hides the version tag beside it. The tag is
    written to `packed-refs`, since some file systems refuse such a name as a file."""

    target = repo(tmp_path / "t")
    commit(target, ONE)
    sha = subprocess.run(
        [GIT, "-C", str(target), "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()
    refs = sha.encode() + b" refs/tags/v0.\xff\n" + sha.encode() + b" refs/tags/v1.0.0\n"
    (target / ".git" / "packed-refs").write_bytes(b"# pack-refs with: peeled\n" + refs)

    assert drift.release_identity(target) == [drift.RELEASE_TAGS]


def release_workflow(command: str) -> dict[str, str]:
    """A `release.yml` with one step that runs `command`."""

    return {
        ".github/workflows/release.yml": (
            "on: push\njobs:\n  go:\n    runs-on: ubuntu-latest\n"
            f"    steps:\n      - run: {command}\n"
        )
    }


@pytest.mark.parametrize(
    "command", ["docker push registry.example/app", "docker buildx build --push -t app ."]
)
def test_a_release_named_workflow_that_only_pushes_an_image_prints_no_line(
    tmp_path: Path, capsys: Capture, command: str
) -> None:
    """Breaks if the name `release.yml` alone sends a workflow whose steps only push a container
    image to `ci-release`: an image is neither a package nor a release."""

    target = repo(tmp_path / "t", release_workflow(command))
    commit(target, ONE)
    installed(target, capsys)

    _, out, _ = run(capsys, str(target), "--check")

    assert drift_lines(out) == []


def test_a_release_workflow_that_pushes_an_image_and_publishes_a_package_prints_the_line(
    tmp_path: Path, capsys: Capture
) -> None:
    """Breaks if an image push in the same workflow hides a package publish."""

    target = repo(tmp_path / "t", release_workflow("docker push app && twine upload dist/*"))
    commit(target, ONE)
    installed(target, capsys)

    _, out, _ = run(capsys, str(target), "--check")

    assert drift_lines(out) == [PUBLISH_LINE]


@pytest.mark.parametrize(
    ("edge", "silenced"),
    [
        pytest.param("pushing a release tag", "publishing", id="release-tag"),
        pytest.param("publishing a package", "publishing", id="package"),
        pytest.param("uploading to the registry", "publishing", id="registry"),
        pytest.param("deploying to production", "deploy", id="production"),
        pytest.param("promoting a build", "deploy", id="promotion"),
        pytest.param("deleting a branch", None, id="neither"),
        pytest.param("deleting production data", None, id="production-data"),
        pytest.param("deleting a tag from the cache", None, id="tag-word"),
    ],
)
def test_an_edge_the_local_fragment_declares_answers_the_act_it_names(
    tmp_path: Path, capsys: Capture, edge: str, silenced: str | None
) -> None:
    """Breaks if a project that lists publishing (or deploying) as an irreversible edge by hand,
    with `ci-release` (or `deploy`) off, still gets the line, or if an edge that names neither
    silences either."""

    files = {
        ".outcomebound/fragments/local.md": local_fragment(None, edges=[edge]),
        "fly.toml": "app = 'x'\n",
        **release_workflow("twine upload dist/*"),
    }
    target = repo(tmp_path / "t", files)
    commit(target, ONE)
    installed(target, capsys, "local")

    _, out, _ = run(capsys, str(target), "--check")

    expected = {"deploy": DEPLOY_LINE, "publishing": PUBLISH_LINE}
    assert drift_lines(out) == [line for name, line in expected.items() if name != silenced]


ALL_FIVE = {
    "recent-authors": "2 recent authors present, record says solo selected",
    "codeowners": "CODEOWNERS present, record says team not selected and solo selected",
    "deploy": DEPLOY_LINE,
    "publishing": PUBLISH_LINE,
    "exposure": (
        "2 recent authors present, record says the local Exposure line is maintained by one person"
    ),
}


def all_five(tmp_path: Path, capsys: Capture, bounds: str) -> list[str]:
    """The drift lines of a project that shows all five signals against its record."""

    files = {
        ".outcomebound/fragments/local.md": local_fragment(
            "Exposure — maintained by: one person", bounds=bounds
        ),
        ".github/CODEOWNERS": "* @x\n",
        "fly.toml": "app = 'x'\n",
        **release_workflow("twine upload dist/*"),
    }
    target = repo(tmp_path / "t", files)
    two_authors(target)
    installed(target, capsys, "solo,local")
    return drift_lines(run(capsys, str(target), "--check")[1])


def test_each_of_the_five_signals_prints_a_line_without_an_acknowledgement(
    tmp_path: Path, capsys: Capture
) -> None:
    """Breaks if the five-signal project used by the acknowledgement tests does not print all
    five lines, which would make those tests prove nothing."""

    assert all_five(tmp_path, capsys, "") == list(ALL_FIVE.values())


@pytest.mark.parametrize("signal", list(ALL_FIVE))
def test_a_drift_line_in_the_bounds_slot_settles_its_signal_and_no_other(
    tmp_path: Path, capsys: Capture, signal: str
) -> None:
    """Breaks if `Drift — <signal>: <reason>` does not mark its own signal as settled with the
    reason while the current evidence still prints, or marks another."""

    found = all_five(tmp_path, capsys, f"Drift — {signal}: a reason the person wrote")

    assert found == [
        f"{line}; settled by the person: a reason the person wrote" if name == signal else line
        for name, line in ALL_FIVE.items()
    ]


def test_an_unknown_signal_id_in_a_drift_line_is_ignored(tmp_path: Path, capsys: Capture) -> None:
    """Breaks if an id outside the five, or a line that is not `Drift — <id>: <reason>`, settles
    a line; the ids are read case-insensitively and a hyphen in place of the dash is read."""

    ignored = "Drift — nonsense: x\nDrift deploy without a colon\nDrifting — deploy; no"
    assert all_five(tmp_path / "a", capsys, ignored) == list(ALL_FIVE.values())

    found = all_five(tmp_path / "b", capsys, "Drift - Recent-Authors: outside contributions")
    assert found[0] == f"{ALL_FIVE['recent-authors']}; settled by the person: outside contributions"
    assert found[1:] == list(ALL_FIVE.values())[1:]


@pytest.mark.parametrize(
    "bounds",
    [
        pytest.param("Drift — deploy:", id="no-reason"),
        pytest.param("Drift — deploy:   ", id="blank-reason"),
        pytest.param("e.g. Drift — deploy: because", id="inside-a-sentence"),
        pytest.param("> Drift — deploy: quoted", id="quoted"),
        pytest.param("`Drift — deploy: code span`", id="code-span"),
        pytest.param("```\nDrift — deploy: fenced\n```", id="fenced"),
    ],
)
def test_a_drift_line_without_a_reason_or_outside_a_line_of_its_own_settles_nothing(
    tmp_path: Path, capsys: Capture, bounds: str
) -> None:
    """Breaks if an empty, quoted, fenced or in-sentence `Drift —` mention settles a signal."""

    assert all_five(tmp_path, capsys, bounds) == list(ALL_FIVE.values())


def test_a_drift_line_outside_the_bounds_slot_settles_nothing(
    tmp_path: Path, capsys: Capture
) -> None:
    """Breaks if a `Drift —` line in the Context slot settles a signal."""

    files = {
        ".outcomebound/fragments/local.md": local_fragment(
            ["Exposure — maintained by: one person", "Drift — deploy: a reason"]
        ),
        "fly.toml": "app = 'x'\n",
    }
    target = repo(tmp_path / "t", files)
    commit(target, ONE)
    installed(target, capsys, "local")

    assert drift_lines(run(capsys, str(target), "--check")[1]) == [DEPLOY_LINE]


def test_the_exposure_claim_needs_every_stream_to_say_one_person(
    tmp_path: Path, capsys: Capture
) -> None:
    """Breaks if a project with two streams, one maintained by one person and one by two, or one
    whose second stream line does not parse, prints the claim, or if all streams saying one
    person do not."""

    for name, streams, line in (
        (
            "two",
            ["Exposure — api: maintained by: one person", "Exposure — web: maintained by: ab"],
            [],
        ),
        (
            "both",
            ["Exposure — api: maintained by: one person", "Exposure — web: maintained by: solo"],
            [ALL_FIVE["exposure"]],
        ),
    ):
        target = repo(
            tmp_path / name, {".outcomebound/fragments/local.md": local_fragment(streams)}
        )
        two_authors(target)
        installed(target, capsys, "team,local")

        _, out, _ = run(capsys, str(target), "--check")

        assert drift_lines(out) == line, name
