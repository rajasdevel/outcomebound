"""`outcomebound research`: printing is bounded to the clone and runs nothing, the networked acts
preview until `--accept`, and a finding is validated before one file is written."""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import subprocess
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

import pytest

from outcomebound_tools import research

COMMIT = "0123456789abcdef0123456789abcdef01234567"
OTHER = "fedcba9876543210fedcba9876543210fedcba98"
SHA256_COMMIT = "a" * 64
BLOB = "https://github.com/rajasdevel/outcomebound-research/blob/main/"
CLONE_URL = "https://github.com/rajasdevel/outcomebound-research.git"
STAMP = "1700000000"  # 2023-11-14T22:13:20Z
REFLOG = f"{'0' * 40} {COMMIT} A <a@example.org> {STAMP} +0200\tclone: from {CLONE_URL}\n"


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    folder = tmp_path / "home"
    folder.mkdir()
    monkeypatch.setenv("HOME", str(folder))
    monkeypatch.delenv(research.ENVIRONMENT, raising=False)
    return folder


@pytest.fixture
def no_subprocess(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError(f"a subprocess was started: {args}")

    monkeypatch.setattr(research.subprocess, "run", refuse)


def make_clone(root: Path, *, head: str = "ref: refs/heads/main", ref: str | None = COMMIT) -> Path:
    """A clone folder: INDEX.md, a document, and a `.git` folder with a loose ref and a reflog."""

    root.mkdir(parents=True)
    (root / "INDEX.md").write_text("# Index\n", encoding="utf-8")
    (root / "models").mkdir()
    (root / "models" / "guidance.md").write_text("advice\n", encoding="utf-8")
    git = root / ".git"
    (git / "refs" / "heads").mkdir(parents=True)
    (git / "logs").mkdir()
    (git / "HEAD").write_text(head + "\n", encoding="utf-8")
    if ref is not None:
        (git / "refs" / "heads" / "main").write_text(ref + "\n", encoding="utf-8")
    (git / "logs" / "HEAD").write_text(REFLOG, encoding="utf-8")
    return root


def link_to(home: Path, target: Path) -> None:
    (home / ".outcomebound").mkdir(exist_ok=True)
    (home / ".outcomebound" / "research").symlink_to(target)


def run(capsys: pytest.CaptureFixture[str], *arguments: str) -> tuple[int, str, str]:
    status = research.main(list(arguments))
    captured = capsys.readouterr()
    return status, captured.out, captured.err


# --- Print ---------------------------------------------------------------------------------------


def test_print_defaults_to_the_index_and_heads_it_with_the_commit_and_day(
    home: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str], no_subprocess: None
) -> None:
    link_to(home, make_clone(tmp_path / "clone"))
    status, out, err = run(capsys)
    assert (status, err) == (0, "")
    assert out == "research: INDEX.md @ 0123456789ab (2023-11-14)\n# Index\n"
    status, out, _ = run(capsys, "models/guidance.md")
    assert out == "research: models/guidance.md @ 0123456789ab (2023-11-14)\nadvice\n"


def test_the_commit_is_read_from_a_packed_ref(
    home: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str], no_subprocess: None
) -> None:
    clone = make_clone(tmp_path / "clone", ref=None)
    (clone / ".git" / "packed-refs").write_text(
        f"# pack-refs\n{OTHER} refs/heads/other\n{COMMIT} refs/heads/main\n", encoding="utf-8"
    )
    link_to(home, clone)
    assert run(capsys)[1].startswith("research: INDEX.md @ 0123456789ab (")


def test_a_detached_head_is_read_as_it_is(
    home: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str], no_subprocess: None
) -> None:
    link_to(home, make_clone(tmp_path / "clone", head=SHA256_COMMIT, ref=None))
    assert run(capsys)[1].startswith("research: INDEX.md @ aaaaaaaaaaaa (")


def test_a_worktree_reads_its_ref_from_the_common_folder(
    home: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str], no_subprocess: None
) -> None:
    main = make_clone(tmp_path / "main")
    admin = main / ".git" / "worktrees" / "w"
    admin.mkdir(parents=True)
    (admin / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (admin / "commondir").write_text("../..\n", encoding="utf-8")
    (admin / "logs").mkdir()
    (admin / "logs" / "HEAD").write_text(REFLOG.replace(STAMP, "1700040000"), encoding="utf-8")
    tree = tmp_path / "tree"
    tree.mkdir()
    (tree / "INDEX.md").write_text("# Tree\n", encoding="utf-8")
    (tree / ".git").write_text(f"gitdir: {admin}\n", encoding="utf-8")
    link_to(home, tree)
    assert run(capsys)[1] == "research: INDEX.md @ 0123456789ab (2023-11-15)\n# Tree\n"
    (tree / ".git").write_text("gitdir: ../main/.git/worktrees/w\n", encoding="utf-8")
    assert run(capsys)[1].startswith("research: INDEX.md @ 0123456789ab (2023-11-15)")


def test_the_header_says_unknown_where_the_git_files_do_not_say(
    home: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str], no_subprocess: None
) -> None:
    exported = tmp_path / "exported"
    exported.mkdir()
    (exported / "INDEX.md").write_text("# Index\n", encoding="utf-8")
    link_to(home, exported)
    assert run(capsys)[1] == "research: INDEX.md @ unknown (unknown)\n# Index\n"

    clone = make_clone(tmp_path / "clone", ref=None)
    (clone / ".git" / "logs" / "HEAD").write_text("garbage\n", encoding="utf-8")
    (home / ".outcomebound" / "research").unlink()
    link_to(home, clone)
    assert run(capsys)[1].startswith("research: INDEX.md @ unknown (unknown)")


def test_a_ref_that_leaves_refs_is_not_followed(
    home: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str], no_subprocess: None
) -> None:
    clone = make_clone(tmp_path / "clone", head="ref: ../../outside")
    (tmp_path / "outside").write_text(COMMIT + "\n", encoding="utf-8")
    link_to(home, clone)
    assert run(capsys)[1].startswith("research: INDEX.md @ unknown (")


@pytest.mark.parametrize(
    "path",
    [
        "/etc/hosts",
        "../outside.md",
        "models/../../outside.md",
        ".git/config",
        "models/.git/x",
        "~/x",
    ],
)
def test_a_path_outside_the_grammar_is_refused_with_nothing_printed(
    home: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    no_subprocess: None,
    path: str,
) -> None:
    link_to(home, make_clone(tmp_path / "clone"))
    status, out, err = run(capsys, path)
    assert (status, out) == (1, "")
    assert err.startswith(f"research: {path}: not a bounded relative path")


def test_a_symlink_out_of_the_clone_is_refused(
    home: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str], no_subprocess: None
) -> None:
    clone = make_clone(tmp_path / "clone")
    secret = tmp_path / "secret.md"
    secret.write_text("secret\n", encoding="utf-8")
    (clone / "leak.md").symlink_to(secret)
    (clone / "outdir").symlink_to(tmp_path)
    link_to(home, clone)
    for path in ("leak.md", "outdir/secret.md"):
        status, out, err = run(capsys, path)
        assert (status, out) == (1, "")
        assert "symlink" in err


def test_a_folder_and_a_missing_file_are_refused_and_the_missing_one_points_at_the_index(
    home: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str], no_subprocess: None
) -> None:
    link_to(home, make_clone(tmp_path / "clone"))
    status, out, err = run(capsys, "models")
    assert (status, out) == (1, "")
    assert "a folder" in err
    status, out, err = run(capsys, "models/absent.md")
    assert (status, out) == (1, "")
    assert "INDEX.md lists every document and MOVED.md every path that moved" in err


def test_the_variable_overrides_the_link(
    home: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    no_subprocess: None,
) -> None:
    link_to(home, make_clone(tmp_path / "linked"))
    other = make_clone(tmp_path / "other")
    (other / "INDEX.md").write_text("# Other\n", encoding="utf-8")
    monkeypatch.setenv(research.ENVIRONMENT, str(other))
    assert run(capsys)[1].endswith("# Other\n")
    monkeypatch.setenv(research.ENVIRONMENT, "")
    assert run(capsys)[1].endswith("# Index\n")


def test_a_variable_naming_a_folder_without_an_index_is_not_a_clone(
    home: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    no_subprocess: None,
) -> None:
    link_to(home, make_clone(tmp_path / "linked"))
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setenv(research.ENVIRONMENT, str(empty))
    status, out, err = run(capsys)
    assert (status, out) == (3, "")
    assert f"{research.ENVIRONMENT} names {empty}, which holds no INDEX.md" in err
    assert f"read it at {BLOB}INDEX.md" in err


def test_no_clone_exits_three_naming_the_public_link(
    home: Path, capsys: pytest.CaptureFixture[str], no_subprocess: None
) -> None:
    status, out, err = run(capsys, "models/guidance.md")
    assert (status, out) == (3, "")
    assert err == (
        "research: no clone configured: OUTCOMEBOUND_RESEARCH is unset and "
        "~/.outcomebound/research does not exist\n"
        f"read it at {BLOB}models/guidance.md\n"
        "clone it once per machine, with the person's yes: outcomebound research clone "
        "<destination>\n"
    )


def test_a_dangling_link_exits_three(
    home: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str], no_subprocess: None
) -> None:
    link_to(home, tmp_path / "gone")
    status, out, err = run(capsys)
    assert (status, out) == (3, "")
    assert "points at nothing" in err


# --- Clone ---------------------------------------------------------------------------------------


class FakeGit:
    """`subprocess.run` for Git: records each argument list and optionally fails."""

    def __init__(self, returncode: int = 0, stderr: str = "") -> None:
        self.calls: list[list[str]] = []
        self.environments: list[dict[str, str]] = []
        self.returncode, self.stderr = returncode, stderr

    def __call__(self, argv: list[str], **options: object) -> subprocess.CompletedProcess[str]:
        self.calls.append(argv)
        self.environments.append(dict(options["env"]))  # type: ignore[call-overload]
        assert options.get("shell") is None
        return subprocess.CompletedProcess(argv, self.returncode, "", self.stderr)


def test_clone_previews_and_runs_nothing_without_accept(
    home: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str], no_subprocess: None
) -> None:
    destination = tmp_path / "somewhere" / "research"
    status, out, err = run(capsys, "clone", str(destination))
    assert (status, err) == (0, "")
    assert out == (
        f"would run: git clone {CLONE_URL} {destination}\n"
        f"would link: ~/.outcomebound/research -> {destination}\n"
        "nothing cloned: pass --accept\n"
    )
    assert not destination.exists()
    assert not (home / ".outcomebound").exists()


def test_clone_preview_says_where_the_variable_overrides_the_link(
    home: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    no_subprocess: None,
) -> None:
    monkeypatch.setenv(research.ENVIRONMENT, str(tmp_path / "elsewhere"))
    out = run(capsys, "clone", str(tmp_path / "research"))[1]
    assert "OUTCOMEBOUND_RESEARCH is set and overrides the link" in out
    assert out.endswith("nothing cloned: pass --accept\n")


def test_clone_with_accept_runs_git_as_an_argument_list_and_links(
    home: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    git = FakeGit()
    monkeypatch.setattr(research.subprocess, "run", git)
    destination = tmp_path / "research"
    status, out, err = run(capsys, "clone", str(destination), "--accept")
    assert (status, err) == (0, "")
    assert git.calls == [["git", "clone", CLONE_URL, str(destination)]]
    assert git.environments[0]["GIT_TERMINAL_PROMPT"] == "0"
    assert git.environments[0]["LC_ALL"] == "C"
    assert out.splitlines() == [
        f"runs: git clone {CLONE_URL} {destination}",
        f"linked: ~/.outcomebound/research -> {destination}",
    ]
    assert (home / ".outcomebound" / "research").readlink() == destination


def test_clone_repoints_a_link_it_made_before(
    home: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(research.subprocess, "run", FakeGit())
    link_to(home, tmp_path / "old")
    destination = tmp_path / "new"
    assert run(capsys, "clone", str(destination), "--accept")[0] == 0
    assert (home / ".outcomebound" / "research").readlink() == destination
    assert os.listdir(home / ".outcomebound") == ["research"]


def test_a_failed_git_leaves_the_link_as_it_was(
    home: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(research.subprocess, "run", FakeGit(128, "fatal: unable to access"))
    link_to(home, tmp_path / "old")
    status, out, err = run(capsys, "clone", str(tmp_path / "new"), "--accept")
    assert status == 1
    assert "fatal: unable to access" in err and "git exited 128" in err
    assert (home / ".outcomebound" / "research").readlink() == tmp_path / "old"
    assert out.startswith("runs: git clone")


def test_a_missing_git_is_named(
    home: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    def absent(*args: object, **kwargs: object) -> None:
        raise FileNotFoundError("git")

    monkeypatch.setattr(research.subprocess, "run", absent)
    status, _, err = run(capsys, "clone", str(tmp_path / "new"), "--accept")
    assert status == 1
    assert "git is not on PATH" in err
    assert not (home / ".outcomebound").exists()


def test_clone_refuses_before_anything_runs(
    home: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str], no_subprocess: None
) -> None:
    full = tmp_path / "full"
    full.mkdir()
    (full / "x").write_text("x", encoding="utf-8")
    status, out, err = run(capsys, "clone", str(full), "--accept")
    assert (status, out) == (1, "")
    assert "is not an empty folder" in err

    afile = tmp_path / "afile"
    afile.write_text("x", encoding="utf-8")
    assert run(capsys, "clone", str(afile), "--accept")[0] == 1

    project = tmp_path / "project"
    (project / ".git").mkdir(parents=True)
    status, out, err = run(capsys, "clone", str(project / "research"), "--accept")
    assert (status, out) == (1, "")
    assert "inside a Git work tree" in err

    (home / ".outcomebound").mkdir()
    (home / ".outcomebound" / "research").mkdir()
    status, out, err = run(capsys, "clone", str(tmp_path / "ok"), "--accept")
    assert (status, out) == (1, "")
    assert "is not a symlink" in err


def test_clone_accepts_an_empty_folder_and_expands_a_tilde(
    home: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    git = FakeGit()
    monkeypatch.setattr(research.subprocess, "run", git)
    (home / "empty").mkdir()
    assert run(capsys, "clone", "~/empty", "--accept")[0] == 0
    assert git.calls[0][3] == str(home / "empty")


# --- Pull ----------------------------------------------------------------------------------------


def test_pull_previews_then_runs_with_accept(
    home: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    clone = make_clone(tmp_path / "clone")
    link_to(home, clone)
    monkeypatch.setattr(research.subprocess, "run", pytest.fail)
    status, out, err = run(capsys, "pull")
    assert (status, err) == (0, "")
    assert out == f"would run: git -C {clone} pull --ff-only\nnothing pulled: pass --accept\n"

    git = FakeGit()
    monkeypatch.setattr(research.subprocess, "run", git)
    status, out, _ = run(capsys, "pull", "--accept")
    assert status == 0
    assert git.calls == [["git", "-C", str(clone), "pull", "--ff-only"]]
    assert out.splitlines() == [
        f"runs: git -C {clone} pull --ff-only",
        "research: now at 0123456789ab (2023-11-14)",
    ]


def test_pull_without_a_clone_exits_three_and_without_git_exits_one(
    home: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str], no_subprocess: None
) -> None:
    assert run(capsys, "pull", "--accept")[0] == 3
    exported = tmp_path / "exported"
    exported.mkdir()
    (exported / "INDEX.md").write_text("# Index\n", encoding="utf-8")
    link_to(home, exported)
    status, out, err = run(capsys, "pull", "--accept")
    assert (status, out) == (1, "")
    assert "no .git" in err


def test_a_failed_pull_exits_one(
    home: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    link_to(home, make_clone(tmp_path / "clone"))
    monkeypatch.setattr(
        research.subprocess, "run", FakeGit(1, "fatal: Not possible to fast-forward")
    )
    status, _, err = run(capsys, "pull", "--accept")
    assert status == 1
    assert "Not possible to fast-forward" in err


# --- Ingest --------------------------------------------------------------------------------------

CLAIM = "The harness reads a skills folder at start."
URL = "https://example.org/docs?a=1&b=two words"
GOOD = (
    "ingest",
    "--kind",
    "fact",
    "--subject",
    "harness:codex",
    "--claim",
    CLAIM,
    "--url",
    "https://example.org/docs",
    "--observed-on",
    "2026-10-01",
)


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, home: Path) -> Path:
    folder = tmp_path / "project"
    (folder / ".git").mkdir(parents=True)
    (folder / "src").mkdir()
    monkeypatch.chdir(folder / "src")
    return folder


def inbox(project: Path) -> list[Path]:
    folder = project / ".outcomebound" / "research-inbox"
    return sorted(folder.iterdir()) if folder.is_dir() else []


def test_ingest_writes_one_file_and_prints_the_issue_link_first(
    project: Path, capsys: pytest.CaptureFixture[str], no_subprocess: None
) -> None:
    status, out, err = run(capsys, *GOOD)
    assert (status, err) == (0, "")
    digest = hashlib.sha256((CLAIM + "https://example.org/docs").encode()).hexdigest()[:8]
    written = project / ".outcomebound" / "research-inbox" / f"20261001-{digest}.json"
    assert inbox(project) == [written]
    assert written.read_bytes() == (
        b"{\n"
        b'  "claim": "The harness reads a skills folder at start.",\n'
        b'  "kind": "fact",\n'
        b'  "observed_on": "2026-10-01",\n'
        b'  "subject": "harness:codex",\n'
        b'  "url": "https://example.org/docs",\n'
        b'  "version": 1\n'
        b"}\n"
    )
    first, second, third = out.splitlines()
    assert first.startswith(
        "issue: https://github.com/rajasdevel/outcomebound-research/issues/new?template=finding.yml&"
    )
    assert second == f"wrote: {written}"
    assert "collect pass" in third


def test_the_issue_link_encodes_each_field_in_order_and_leaves_empty_ones_out() -> None:
    fields = {
        "kind": "correction",
        "subject": "practice:review",
        "claim": "A & B = 50% of #1; ünï",
        "url": URL.replace(" ", "%20"),
        "quote": "two words",
        "observed_on": "2026-10-01",
        "corrects": "practices/review.md",
    }
    link = research.issue_link(fields)
    parts = urlsplit(link)
    assert (parts.netloc, parts.path) == (
        "github.com",
        "/rajasdevel/outcomebound-research/issues/new",
    )
    pairs = parse_qsl(parts.query, keep_blank_values=True)
    assert [name for name, _ in pairs] == ["template", *fields]
    assert dict(pairs[1:]) == fields
    assert " " not in link and "&B" not in link.split("claim=")[1].split("&url=")[0]
    assert "quote" not in research.issue_link({**fields, "quote": ""})


def test_ingest_prints_every_field_that_was_given(
    project: Path, capsys: pytest.CaptureFixture[str], no_subprocess: None
) -> None:
    status, out, _ = run(
        capsys,
        *GOOD,
        "--quote",
        "one two three",
        "--corrects",
        "models/guidance.md",
    )
    assert status == 0
    names = [name for name, _ in parse_qsl(urlsplit(out.splitlines()[0]).query)]
    assert names == [
        "template",
        "kind",
        "subject",
        "claim",
        "url",
        "quote",
        "observed_on",
        "corrects",
    ]
    saved = json.loads(inbox(project)[0].read_text(encoding="utf-8"))
    assert saved["quote"] == "one two three" and saved["corrects"] == "models/guidance.md"
    assert saved["version"] == 1


def test_a_repeat_is_unchanged_and_other_bytes_are_refused_with_nothing_printed(
    project: Path, capsys: pytest.CaptureFixture[str], no_subprocess: None
) -> None:
    assert run(capsys, *GOOD)[0] == 0
    status, out, _ = run(capsys, *GOOD)
    assert status == 0
    assert out.splitlines()[1].startswith("unchanged: ")
    target = inbox(project)[0]
    target.write_text("{}\n", encoding="utf-8")
    status, out, err = run(capsys, *GOOD)
    assert (status, out) == (1, "")
    assert "holds a different finding" in err
    assert target.read_text(encoding="utf-8") == "{}\n"


def replaced(arguments: tuple[str, ...], flag: str, value: str) -> list[str]:
    changed = list(arguments)
    changed[changed.index(flag) + 1] = value
    return changed


def test_the_default_day_is_today(
    project: Path, capsys: pytest.CaptureFixture[str], no_subprocess: None
) -> None:
    arguments = [a for a in GOOD if a not in ("--observed-on", "2026-10-01")]
    assert run(capsys, *arguments)[0] == 0
    saved = json.loads(inbox(project)[0].read_text(encoding="utf-8"))
    assert saved["observed_on"] == datetime.date.today().isoformat()
    assert inbox(project)[0].name.startswith(datetime.date.today().strftime("%Y%m%d"))


@pytest.mark.parametrize(
    ("flag", "value", "why"),
    [
        ("--kind", "opinion", "kind must be one of"),
        ("--subject", "", "subject must be 1 to 120"),
        ("--subject", "s" * 121, "subject must be 1 to 120"),
        ("--claim", "c" * 601, "claim must be 1 to 600"),
        ("--claim", "two\nlines", "line break"),
        ("--claim", "two\r\nlines", "line break"),
        ("--claim", "tab\there", "control character"),
        ("--claim", "separator\u2028here", "line break"),
        ("--subject", "a\x00b", "control character"),
        ("--url", "ftp://example.org/x", "url must be http or https"),
        ("--url", "https://", "url must be http or https"),
        ("--url", "example.org/docs", "url must be http or https"),
        ("--url", "https://example.org/a b", "url must be http or https"),
        ("--url", "https://[bad", "url must be http or https"),
        ("--quote", " ".join(["w"] * 26), "at most 25 words"),
        ("--observed-on", "2026-13-01", "real date"),
        ("--observed-on", "20261001", "real date"),
        ("--observed-on", "2999-01-01", "not after today"),
        ("--corrects", "a\nb", "line break"),
    ],
)
def test_each_refusal_names_the_field_and_writes_nothing(
    project: Path,
    capsys: pytest.CaptureFixture[str],
    no_subprocess: None,
    flag: str,
    value: str,
    why: str,
) -> None:
    arguments = list(GOOD)
    if flag in arguments:
        arguments = replaced(GOOD, flag, value)
    else:
        arguments += [flag, value]
    status, out, err = run(capsys, *arguments)
    assert (status, out) == (1, "")
    assert why in err
    assert inbox(project) == []


def test_a_quote_of_twenty_five_words_is_accepted(
    project: Path, capsys: pytest.CaptureFixture[str], no_subprocess: None
) -> None:
    assert run(capsys, *GOOD, "--quote", " ".join(["w"] * 25))[0] == 0


def test_a_correction_needs_something_to_correct(
    project: Path, capsys: pytest.CaptureFixture[str], no_subprocess: None
) -> None:
    arguments = replaced(GOOD, "--kind", "correction")
    status, out, err = run(capsys, *arguments)
    assert (status, out) == (1, "")
    assert "--corrects" in err
    assert run(capsys, *arguments, "--corrects", "practices/git.md")[0] == 0


def test_a_missing_required_field_is_a_usage_error(
    project: Path, capsys: pytest.CaptureFixture[str], no_subprocess: None
) -> None:
    with pytest.raises(SystemExit) as stop:
        research.main(["ingest", "--kind", "fact"])
    assert stop.value.code == 2
    capsys.readouterr()


def test_a_finding_over_sixteen_kib_is_refused(
    project: Path, capsys: pytest.CaptureFixture[str], no_subprocess: None
) -> None:
    status, out, err = run(capsys, *GOOD, "--corrects", "x" * 17000)
    assert (status, out) == (1, "")
    assert "16 KiB" in err


def test_ingest_refuses_a_symlinked_inbox_path(
    project: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str], no_subprocess: None
) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (project / ".outcomebound").symlink_to(outside)
    status, out, err = run(capsys, *GOOD)
    assert (status, out) == (1, "")
    assert "symlink" in err
    assert list(outside.iterdir()) == []


def test_ingest_outside_a_work_tree_needs_a_project(
    tmp_path: Path,
    home: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    no_subprocess: None,
) -> None:
    bare = tmp_path / "bare"
    bare.mkdir()
    monkeypatch.chdir(bare)
    status, out, err = run(capsys, *GOOD)
    assert (status, out) == (1, "")
    assert "--project" in err
    status, out, _ = run(capsys, *GOOD, "--project", str(bare))
    assert status == 0
    assert (bare / ".outcomebound" / "research-inbox").is_dir()


# --- The launcher and the help -------------------------------------------------------------------


def test_the_verb_is_in_the_launcher_table_and_help_answers_without_a_clone(
    home: Path, capsys: pytest.CaptureFixture[str], no_subprocess: None
) -> None:
    from outcomebound_tools.__main__ import VERBS

    assert VERBS["research"] == "research"
    with pytest.raises(SystemExit) as stop:
        research.main(["--help"])
    assert stop.value.code == 0
    text = capsys.readouterr().out
    for word in ("clone", "pull", "ingest", "--accept", "OUTCOMEBOUND_RESEARCH", "Exit 0"):
        assert word in text
    with pytest.raises(SystemExit):
        research.main(["ingest", "--help"])
    assert "collect pass" in capsys.readouterr().out
