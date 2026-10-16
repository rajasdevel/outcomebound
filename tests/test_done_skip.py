"""The Done skip (`adopt --done-skip`): the changes a Done command is not run for.

A command is skipped only where every changed path matches one of its globs; every other case,
and every case the paths cannot be read in, runs the whole Done list. Each test names the break
it catches.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from outcomebound_tools import adopt, facts, finish_check
from tests.portable import write
from tests.test_finish_check import counted, hook, person, q, turn

GIT = shutil.which("git") or "git"
IDENTITY = ["-c", "user.name=t", "-c", "user.email=t@example.com"]
DOCS = ["docs/**", "**/*.md"]


def skipping(path: Path, done: list[str], skip: dict[str, list[str]]) -> tuple[Path, str]:
    """A committed repository whose manifest records `done` and `skip`, and the entry digest."""

    record: dict[str, object] = {"kind": "block", "path": "AGENTS.md", "id": "project-facts"}
    record["done"] = done
    record[finish_check.SKIP_KEY] = skip
    manifest = {"format_version": 2, "engine_version": "0", "artifacts": [record]}
    (path / ".outcomebound").mkdir(parents=True)
    write(path / ".outcomebound/manifest.json", json.dumps(manifest))
    write(path / "src.txt", "one\n")
    (path / "docs").mkdir()
    write(path / "docs/guide.md", "one\n")
    subprocess.run([GIT, "init", "-q", str(path)], check=True)
    subprocess.run([GIT, "-C", str(path), "add", "."], check=True)
    subprocess.run([GIT, "-C", str(path), *IDENTITY, "commit", "-qm", "init"], check=True)
    return path, finish_check.done_digest(done, skip)


def counting(tmp_path: Path) -> tuple[Path, str, Path, Path]:
    """A target whose cheap command counts into `fast` and whose slow one, which the skip names
    for documents, counts into `slow`."""

    fast, slow = tmp_path / "fast", tmp_path / "slow"
    cheap, suite = f"echo r >> {q(fast)}", f"echo r >> {q(slow)}"
    root, digest = skipping(tmp_path / "t", [cheap, suite], {suite: DOCS})
    return root, digest, fast, slow


def commit(root: Path, message: str = "c") -> None:
    subprocess.run([GIT, "-C", str(root), "add", "-A"], check=True)
    subprocess.run([GIT, "-C", str(root), *IDENTITY, "commit", "-qm", message], check=True)


# --- The glob grammar ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("glob", "path", "matches"),
    [
        ("docs/*", "docs/a.md", True),
        ("docs/*", "docs/sub/a.md", False),
        ("docs/**", "docs/sub/a.md", True),
        ("docs/**", "docs", True),
        ("**/*.md", "README.md", True),
        ("**/*.md", "a/b/c.md", True),
        ("**/*.md", "a/b/c.py", False),
        ("*.md", "a/b.md", False),
        ("docs/?.md", "docs/a.md", True),
        ("Docs/**", "docs/a.md", False),
    ],
)
def test_a_star_stays_in_one_folder_and_two_cross_any_number(
    glob: str, path: str, matches: bool
) -> None:
    """Breaks if `*` crosses a folder, if `**` does not match zero folders (then `**/*.md` misses
    a top-level document), or if matching ignores case."""

    assert finish_check.glob_matches(glob, path) is matches


@pytest.mark.parametrize("glob", ["", "/docs/**", "../x", "docs/./a", "a\\b", "[ab].md", "a**"])
def test_a_glob_outside_the_grammar_is_refused(glob: str) -> None:
    assert finish_check.glob_refusal(glob) is not None


@pytest.mark.parametrize(
    ("skip", "why"),
    [
        ({"make lint": DOCS}, "not a recorded Done command"),
        ({"make test": ["**"]}, "covers every path"),
        ({"make test": ["*", "*/**", ".*", "**/.*"]}, "covers every path"),
        ({"make test": DOCS, "make check": DOCS}, "no Done command that always runs"),
        ({"make test": ["/docs"]}, "absolute"),
    ],
)
def test_a_skip_that_could_loosen_the_check_unseen_is_refused(
    skip: dict[str, list[str]], why: str
) -> None:
    """Breaks if a skip may name a command Done does not run, cover every path alone or with
    its other globs, or leave nothing that always runs."""

    refused = finish_check.skip_refusal(["make check", "make test"], skip)
    assert refused is not None and why in refused


def test_a_malformed_skip_in_the_manifest_skips_nothing(tmp_path: Path) -> None:
    """Breaks if a hand-edited skip that adopt would refuse is read by the hook."""

    root, _ = skipping(tmp_path / "t", ["make check", "make test"], {"make test": ["**"]})
    assert finish_check.recorded_skip(root) == {}
    assert finish_check.skip_of(["a", "b"], {"b": "docs/**"}) == {}


def test_the_done_digest_is_unchanged_without_a_skip_and_moves_with_one() -> None:
    """Breaks if an install with no skip stops reading current, or if a pull request can widen a
    skip without the hook entry moving."""

    done = ["make check", "make test"]
    assert finish_check.done_digest(done) == finish_check.done_digest(done, {})
    one = finish_check.done_digest(done, {"make test": ["docs/**"]})
    two = finish_check.done_digest(done, {"make test": ["docs/**", "**/*.md"]})
    assert len({finish_check.done_digest(done), one, two}) == 3


def test_the_done_fact_names_the_paths_a_command_is_not_run_for() -> None:
    """Breaks if the model reads an unconditional Done where the hook skips a command, or if a
    project with no skip gets a different line."""

    done = ["make check", "make test"]
    assert facts.done_line(done) == "- Done: `make check` and `make test`"
    assert facts.done_line(done, {"make test": DOCS}) == (
        "- Done: `make check` and `make test`; `make test` is not run when every changed path "
        "matches `docs/**` or `**/*.md`"
    )


# --- The hook ------------------------------------------------------------------------


def test_a_command_is_skipped_only_where_every_changed_path_matches_its_globs(
    tmp_path: Path,
) -> None:
    """Breaks if a documentation-only turn still runs the skipped command, or if the person is
    not told what did not run."""

    root, digest, fast, slow = counting(tmp_path)
    write(root / "docs/guide.md", "two\n")
    write(root / "README.md", "new\n")

    verdict = hook("codex", digest, root)[1]

    assert (counted(fast), counted(slow)) == (1, 0)
    message = person("codex", root, verdict)
    assert "finish-check PASS: " in message
    assert "not run, every changed path is one its --done-skip names: echo r >> " in message


@pytest.mark.parametrize(
    "change",
    ["edit", "untracked", "delete", "move-in", "beside"],
)
def test_one_changed_path_outside_the_globs_runs_every_command(tmp_path: Path, change: str) -> None:
    """Breaks if a code change hides behind a documentation change, an untracked file, a
    deletion, or a move of code into a skipped folder."""

    root, digest, fast, slow = counting(tmp_path)
    if change == "edit":
        write(root / "src.txt", "two\n")
    elif change == "untracked":
        write(root / "tool.py", "x\n")
    elif change == "delete":
        (root / "src.txt").unlink()
    elif change == "move-in":
        subprocess.run([GIT, "-C", str(root), "mv", "src.txt", "docs/src.txt"], check=True)
    else:
        write(root / "docs/guide.md", "two\n")
        write(root / "src.txt", "two\n")

    hook("codex", digest, root)

    assert (counted(fast), counted(slow)) == (1, 1)


def test_a_turn_that_commits_only_matching_paths_skips_with_a_trusted_mark(tmp_path: Path) -> None:
    """Breaks if a turn that commits its documentation change runs the whole Done list: the turn
    began at the mark's commit, so the change is read from there."""

    root, digest, fast, slow = counting(tmp_path)
    turn("codex", digest, root)
    write(root / "docs/guide.md", "two\n")
    commit(root)

    hook("codex", digest, root)

    assert (counted(fast), counted(slow)) == (1, 0)


def test_a_clean_tree_with_no_mark_runs_every_command(tmp_path: Path) -> None:
    """Breaks if a tree with no change to read is taken as matching every glob."""

    root, digest, fast, slow = counting(tmp_path)
    write(root / "docs/guide.md", "two\n")
    commit(root)

    hook("codex", digest, root)

    assert (counted(fast), counted(slow)) == (1, 1)


def test_a_change_outside_the_target_folder_runs_every_command(tmp_path: Path) -> None:
    """Breaks if, in a repository that holds the target in a folder, a change beside the target
    is read as one of its documents."""

    repository = tmp_path / "repo"
    fast, slow = tmp_path / "fast", tmp_path / "slow"
    cheap, suite = f"echo r >> {q(fast)}", f"echo r >> {q(slow)}"
    record: dict[str, object] = {"kind": "block", "path": "AGENTS.md", "id": "project-facts"}
    record["done"] = [cheap, suite]
    record[finish_check.SKIP_KEY] = {suite: DOCS}
    manifest = {"format_version": 2, "engine_version": "0", "artifacts": [record]}
    for folder in ("app/.outcomebound", "app/docs", "lib/docs"):
        (repository / folder).mkdir(parents=True)
    write(repository / "app/.outcomebound/manifest.json", json.dumps(manifest))
    write(repository / "app/docs/a.md", "one\n")
    write(repository / "lib/docs/b.md", "one\n")
    subprocess.run([GIT, "init", "-q", str(repository)], check=True)
    commit(repository, "init")
    root = repository / "app"
    write(repository / "lib/docs/b.md", "two\n")
    write(root / "docs/a.md", "two\n")

    assert finish_check.changed_paths(root, "HEAD") is None
    assert finish_check.skipped_for(root, [cheap, suite], {suite: DOCS}, "HEAD") == ()


def test_a_path_read_past_its_deadline_skips_nothing(tmp_path: Path) -> None:
    root, _, _, _ = counting(tmp_path)
    write(root / "docs/guide.md", "two\n")
    done = ["a", "b"]
    assert finish_check.skipped_for(root, done, {"b": DOCS}, "HEAD", deadline=0.0) == ()
    assert finish_check.skipped_for(root, done, {"b": DOCS}, "HEAD") == ("b",)


# --- adopt ---------------------------------------------------------------------------


def adopted(tmp_path: Path) -> Path:
    root = tmp_path / "p"
    root.mkdir()
    subprocess.run([GIT, "init", "-q", str(root)], check=True)
    write(root / "README.md", "p\n")
    commit(root, "init")
    return root


def run_adopt(root: Path, *words: str) -> subprocess.CompletedProcess[str]:
    from tests.portable import engine

    return subprocess.run(
        engine("adopt", str(root), *words),
        capture_output=True,
        text=True,
        check=False,
        encoding="utf-8",
    )


def test_done_skip_is_recorded_shown_and_the_install_checks_current(tmp_path: Path) -> None:
    """Breaks if the skip is not recorded, not in the facts line, or makes the install read
    stale on its own check."""

    root = adopted(tmp_path)
    done = run_adopt(
        root, "--done", "make check", "--done", "make test", "--done-skip", "make test", "docs/**"
    )
    assert done.returncode == 0, done.stderr
    own = adopt.load_manifest(root).own
    assert adopt.recorded_skip(own) == {"make test": ["docs/**"]}
    text = (root / "AGENTS.md").read_text(encoding="utf-8")
    assert "`make test` is not run when every changed path matches `docs/**`" in text
    assert run_adopt(root, "--check").returncode == 0

    cleared = run_adopt(root, "--done-skip", "", "")
    assert cleared.returncode == 0, cleared.stderr
    assert adopt.recorded_skip(adopt.load_manifest(root).own) == {}
    assert "is not run when" not in (root / "AGENTS.md").read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("words", "why"),
    [
        (["--done-skip", "make lint", "docs/**"], "not a recorded Done command"),
        (["--done-skip", "make test", "**"], "covers every path"),
        (["--done-skip", "make test", "docs/**", "--done-skip", "make check", "docs/**"], "always"),
    ],
)
def test_adopt_refuses_a_skip_that_loosens_the_check(
    tmp_path: Path, words: list[str], why: str
) -> None:
    root = adopted(tmp_path)
    done = run_adopt(root, "--done", "make check", "--done", "make test", *words)
    assert done.returncode != 0 and why in done.stderr, done.stderr
    assert not (root / ".outcomebound").exists()


def test_the_install_report_notes_a_slow_command_before_shorter_ones() -> None:
    """Breaks if the order note is missing where a failure of a quick later command reruns the
    slow suite, or is printed where the order is already right."""

    slow = finish_check.Result("make test", finish_check.PASS, 300.0)
    quick = finish_check.Result("make check", finish_check.PASS, 9.0)
    noted = adopt.order_notes([slow, quick])
    assert len(noted) == 1 and "`make test` (300 s) runs before `make check` (9 s)" in noted[0][1]
    assert adopt.order_notes([quick, slow]) == []
