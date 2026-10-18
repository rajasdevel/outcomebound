"""`outcomebound review since`: the ref, the changes against it (hunks with no context, renames,
deletions, binary and untracked files), the findings that cite a changed path, each UNVERIFIED
reason, the JSON shape, and that nothing is written."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from outcomebound_tools import review_check, review_since
from outcomebound_tools.schemacheck import validate

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = json.loads((ROOT / "schemas/review-since.schema.json").read_text("utf-8"))
IDENTITY = ("-c", "user.name=T", "-c", "user.email=t@example.test", "-c", "commit.gpgsign=false")


@pytest.fixture(autouse=True)
def hermetic_git(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


def git(where: Path, *args: str) -> str:
    done = subprocess.run(["git", *IDENTITY, *args], cwd=where, check=True, capture_output=True)
    return done.stdout.decode("utf-8").strip()


def put(root: Path, name: str, text: str | bytes) -> None:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode() if isinstance(text, str) else text)


def numbered(count: int) -> str:
    return "".join(f"line {n}\n" for n in range(1, count + 1))


def commit(root: Path) -> str:
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "c")
    return git(root, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    put(root, "src/app.py", numbered(20))
    put(root, "src/other.py", numbered(5))
    put(root, "lib/app.py", numbered(5))
    put(root, "old.txt", numbered(8))
    put(root, "gone.txt", numbered(4))
    put(root, "bin.dat", b"\x00\x01\x02")
    commit(root)
    return root


def review(tmp_path: Path, ref: str | None, body: str) -> Path:
    path = tmp_path / "review.md"
    head = f"Reviewed: {ref}\n\n" if ref else ""
    path.write_text(f"# R\n\n{head}### F1 · One\n\n{body}\n\nDisposition: fixed — x\n", "utf-8")
    return path


def test_changes_are_hunks_with_no_context_and_cited_lines_are_judged_by_the_old_side(
    repo, tmp_path
):
    base = git(repo, "rev-parse", "HEAD")
    lines = numbered(20).replace("line 13\n", "changed\n")
    put(repo, "src/app.py", lines)
    commit(repo)
    note = review(tmp_path, base, "See `src/app.py:11`, src/app.py:13 and src/app.py:12-14.")
    result = review_since.build(note, None, repo)
    assert validate(result, SCHEMA) == []
    entry = next(f for f in result["files"] if f["path"] == "src/app.py")
    assert entry["hunks"] == [{"old_start": 13, "old_count": 1, "new_start": 13, "new_count": 1}]
    cites = result["findings"][0]["cites"]
    by_line = {(c["line"], c.get("line_end")): c["line_changed"] for c in cites}
    # A line beside the edit is not a changed line: default context would say it is.
    assert by_line == {(11, None): False, (13, None): True, (12, 14): True}


def test_status_renames_deletions_binary_and_untracked(repo, tmp_path):
    base = git(repo, "rev-parse", "HEAD")
    git(repo, "mv", "old.txt", "new.txt")
    (repo / "gone.txt").unlink()
    put(repo, "bin.dat", b"\x00\x09\x09\x09")
    put(repo, "fresh.txt", "x\n")
    os.symlink("fresh.txt", repo / "link.txt")
    put(repo, "ignored.log", "x")
    put(repo, ".gitignore", "*.log\n")
    note = review(tmp_path, base, "`old.txt:2` and `gone.txt:3` and bin.dat")
    result = review_since.build(note, None, repo)
    assert validate(result, SCHEMA) == []
    by_path = {f["path"]: f for f in result["files"]}
    assert by_path["new.txt"]["status"] == "renamed" and by_path["new.txt"]["old_path"] == "old.txt"
    assert by_path["gone.txt"]["status"] == "deleted"
    assert by_path["bin.dat"]["added"] is None and by_path["bin.dat"]["hunks"] == []
    assert by_path["fresh.txt"]["status"] == "untracked"
    assert "link.txt" not in by_path and result["untracked_skipped"] == 1
    assert "ignored.log" not in by_path
    cites = {c["path"]: c for c in result["findings"][0]["cites"]}
    assert cites["gone.txt"]["line_changed"] is True  # every line of a deleted file is lost
    assert cites["new.txt"]["line_changed"] is False  # a pure rename keeps line 2
    assert "bin.dat" in cites and "line" not in cites["bin.dat"]


def test_a_suffix_names_one_changed_path_or_is_ambiguous(repo, tmp_path):
    base = git(repo, "rev-parse", "HEAD")
    put(repo, "src/app.py", numbered(20) + "more\n")
    put(repo, "lib/app.py", numbered(5) + "more\n")
    put(repo, "src/other.py", numbered(5) + "more\n")
    note = review(tmp_path, base, "app.py:3 and other.py:2 and src/other.py:9")
    cites = review_since.build(note, None, repo)["findings"][0]["cites"]
    ambiguous = [c for c in cites if "candidates" in c]
    assert {c["path"] for c in ambiguous} == {"src/app.py", "lib/app.py"}
    assert ambiguous[0]["candidates"] == ["lib/app.py", "src/app.py"]
    assert {c["path"] for c in cites if "candidates" not in c} == {"src/other.py"}


def test_references_outside_prose_are_not_read(repo, tmp_path):
    base = git(repo, "rev-parse", "HEAD")
    put(repo, "src/other.py", numbered(5) + "more\n")
    body = "```\nsrc/other.py:1\n```\nSee https://host.example:80/src/other.py:2 and 12:30."
    assert review_since.build(review(tmp_path, base, body), None, repo)["findings"] == []
    unchanged = review(tmp_path, base, "src/app.py:3")
    assert review_since.build(unchanged, None, repo)["findings"] == []


def test_a_ref_in_a_subfolder_root_and_moving_refs(repo, tmp_path):
    base = git(repo, "rev-parse", "HEAD")
    put(repo, "src/app.py", numbered(21))
    commit(repo)
    note = review(tmp_path, "main", "src/app.py:21")
    result = review_since.build(note, None, repo / "src")
    assert result["result"] == "REPORT" and result["ref_is_moving"] is True
    assert result["files"] == []  # the tip of main is the work tree
    over = review_since.build(note, base, repo)
    assert over["ref_source"] == "--since" and "ref_is_moving" not in over
    assert [f["path"] for f in over["files"]] == ["src/app.py"]
    git(repo, "tag", "v1")
    tagged = review_since.build(review(tmp_path, "v1", "x"), None, repo)
    assert "ref_is_moving" not in tagged


@pytest.mark.parametrize(
    ("ref", "fragment"),
    [
        (None, "no `Reviewed:` ref"),
        ("nonesuch", "does not resolve"),
        ("--output=x", "starts with a dash"),
        ("v1 (prose)", "does not resolve"),
    ],
)
def test_each_unverified_reason_names_itself(repo, tmp_path, ref, fragment):
    result = review_since.build(review(tmp_path, ref, "x"), None, repo)
    assert result["result"] == "UNVERIFIED" and fragment in result["reason"]
    assert validate(result, SCHEMA) == []
    assert "files" not in result


def test_unverified_for_a_missing_file_and_a_root_with_no_work_tree(repo, tmp_path):
    assert review_since.build(tmp_path / "no.md", None, repo)["result"] == "UNVERIFIED"
    plain = tmp_path / "plain"
    plain.mkdir()
    result = review_since.build(review(tmp_path, "main", "x"), None, plain)
    assert result["result"] == "UNVERIFIED"


def test_the_work_tree_and_index_are_left_as_found(repo, tmp_path, capsys):
    base = git(repo, "rev-parse", "HEAD")
    put(repo, "src/app.py", numbered(21))
    put(repo, "new.txt", "n\n")
    before = (git(repo, "status", "--porcelain"), (repo / ".git/index").read_bytes())
    note = review(tmp_path, base, "src/app.py:3")
    code = review_check.main(["since", str(note), "--root", str(repo), "--json"])
    out = json.loads(capsys.readouterr().out)
    assert code == 0 and validate(out, SCHEMA) == []
    assert before == (git(repo, "status", "--porcelain"), (repo / ".git/index").read_bytes())


def test_text_report_and_exit_codes(repo, tmp_path, capsys):
    base = git(repo, "rev-parse", "HEAD")
    put(repo, "src/app.py", numbered(20).replace("line 5\n", "x\n"))
    note = review(tmp_path, base, "src/app.py:5")
    assert review_check.main(["since", str(note), "--root", str(repo)]) == 0
    out = capsys.readouterr().out
    assert out.startswith("REPORT: 1 changed path(s), 1 finding(s) cite one")
    assert "@@ -5,1 +5,1 @@" in out and "[line changed]" in out
    assert out.count("Does not establish:") == 1
    assert review_check.main(["since", str(tmp_path / "no.md"), "--root", str(repo)]) == 1
    assert capsys.readouterr().out.startswith("UNVERIFIED:")
    with pytest.raises(SystemExit) as stop:
        review_check.main(["since"])
    assert stop.value.code == 2


def test_check_and_sweep_still_import_no_git():
    source = Path(review_check.__file__).read_text("utf-8")
    assert "subprocess" not in source and "outcomebound_tools import size" not in source
