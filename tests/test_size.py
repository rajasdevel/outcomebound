"""`outcomebound size`: the kind of each path, the count against a base (committed, uncommitted,
renamed, untracked and binary files), the default base, the refusals, the JSON shape, and that
nothing is written."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from outcomebound_tools import size

IDENTITY = (
    "-c",
    "user.name=Size",
    "-c",
    "user.email=size@example.test",
    "-c",
    "commit.gpgsign=false",
)


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
    path.write_bytes(text.encode("utf-8") if isinstance(text, str) else text)


def lines(count: int) -> str:
    return "".join(f"line {number}\n" for number in range(count))


def commit(root: Path, message: str = "change") -> str:
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", message)
    return git(root, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "work"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    put(root, "app/main.py", lines(10))
    put(root, "README.md", lines(2))
    commit(root, "start")
    return root


def report(root: Path, capsys: pytest.CaptureFixture[str], *extra: str) -> dict:
    assert size.main([str(root), "--json", *extra]) == 0
    return json.loads(capsys.readouterr().out)


@pytest.mark.parametrize(
    ("path", "kind"),
    [
        (".agents/work/plan.md", "records"),
        (".outcomebound/manifest.json", "records"),
        (".agents/tests/test_x.py", "records"),
        ("tests/test_a.py", "tests"),
        ("pkg/test/helper.py", "tests"),
        ("web/__tests__/a.js", "tests"),
        ("pkg/spec/a.rb", "tests"),
        ("tests/data.json", "tests"),
        ("tests/notes.md", "tests"),
        ("evals/fixtures/case/input.txt", "tests"),
        ("pkg/testdata/a.bin", "tests"),
        ("pkg/test_core.py", "tests"),
        ("pkg/core_test.go", "tests"),
        ("web/app.test.ts", "tests"),
        ("web/app.spec.ts", "tests"),
        ("pkg/conftest.py", "tests"),
        ("docs/specs/size/design.md", "docs"),
        ("docs/specs/size/notes.json", "docs"),
        ("README.md", "docs"),
        ("notes.txt", "docs"),
        ("guide.rst", "docs"),
        ("guide.adoc", "docs"),
        ("docs/diagram.svg", "docs"),
        ("pkg/docs/a.py", "docs"),
        (".github/workflows/ci.yml", "config"),
        (".gitlab-ci.yml", "config"),
        ("package.json", "config"),
        ("settings.yaml", "config"),
        ("pyproject.toml", "config"),
        ("tox.ini", "config"),
        ("setup.cfg", "config"),
        ("package-lock.json", "config"),
        ("Cargo.lock", "config"),
        ("uv.lock", "config"),
        ("go.sum", "config"),
        ("app/main.py", "code"),
        ("src/Makefile", "code"),
        ("outcomebound_tools/size.py", "code"),
        ("src/specimen.py", "code"),
    ],
)
def test_the_first_matching_kind_wins(path: str, kind: str) -> None:
    assert size.kind_of(path) == kind


def test_committed_and_uncommitted_changes_are_counted_by_kind(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    base = git(repo, "rev-parse", "HEAD")
    put(repo, "app/main.py", lines(10) + lines(5))
    put(repo, "tests/test_main.py", lines(7))
    commit(repo)
    put(repo, "README.md", lines(1))  # uncommitted: one line kept, one removed
    put(repo, ".agents/work/plan.md", lines(3))
    git(repo, "add", ".agents/work/plan.md")  # staged
    put(repo, "ci.yml", lines(4))  # untracked

    result = report(repo, capsys, "--base", base)

    assert result["base"] == {"ref": base, "how": "--base", "commit": base}
    assert result["kinds"] == {
        "code": {"files": 1, "added": 5, "removed": 0, "net": 5},
        "tests": {"files": 1, "added": 7, "removed": 0, "net": 7},
        "docs": {"files": 1, "added": 0, "removed": 1, "net": -1},
        "config": {"files": 1, "added": 4, "removed": 0, "net": 4},
        "records": {"files": 1, "added": 3, "removed": 0, "net": 3},
    }
    assert result["total"] == {"files": 5, "added": 19, "removed": 1, "net": 18}
    assert result["non_code_share_of_added"] == round(14 / 19, 4)
    assert result["untracked_files"] == 1


def test_the_text_report_has_a_line_for_each_kind_present_a_total_and_the_share(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    put(repo, "app/main.py", lines(10) + lines(6))
    put(repo, "tests/test_a.py", lines(2))

    assert size.main([str(repo), "--base", "HEAD"]) == 0
    out = capsys.readouterr().out.splitlines()

    assert out[0].startswith("size against HEAD (--base), commit ")
    assert [line.split()[0] for line in out[2:-1]] == ["code", "tests", "total"]
    assert out[2].split() == ["code", "1", "6", "0", "+6"]
    assert out[-2].split() == ["total", "2", "8", "0", "+8"]
    assert out[-1] == "non-code share of added lines: 25.0%"


def test_a_renamed_file_counts_once_at_its_new_path(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    git(repo, "mv", "app/main.py", "app/moved.py")
    put(repo, "app/moved.py", lines(10) + "extra\n")

    result = report(repo, capsys, "--base", "HEAD")

    assert result["kinds"] == {"code": {"files": 1, "added": 1, "removed": 0, "net": 1}}


def test_untracked_files_count_as_added_and_ignored_files_do_not(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    put(repo, ".gitignore", "build/\n")
    commit(repo)
    put(repo, "build/out.py", lines(100))
    put(repo, "new.py", "one\ntwo")  # no final newline: two lines
    put(repo, "empty.py", "")
    put(repo, "sub/deep/a.py", lines(3))

    result = report(repo, capsys, "--base", "HEAD")

    assert result["kinds"] == {"code": {"files": 3, "added": 5, "removed": 0, "net": 5}}
    assert result["untracked_files"] == 3


def test_binary_files_count_as_files_with_no_lines(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    put(repo, "logo.bin", b"\x00\x01\x02" * 50)
    commit(repo)
    put(repo, "logo.bin", b"\x00\x09\x02" * 50)  # tracked, changed
    put(repo, "new.bin", b"\x00" * 10)  # untracked

    assert size.main([str(repo), "--base", "HEAD"]) == 0
    text = capsys.readouterr().out
    result = report(repo, capsys, "--base", "HEAD")

    assert result["kinds"] == {"code": {"files": 2, "added": 0, "removed": 0, "net": 0}}
    assert result["binary"] == ["logo.bin", "new.bin"]
    assert "note: 2 binary file(s) count as files, with no lines" in text


def test_an_untracked_file_over_the_bound_is_named_and_adds_no_lines(
    repo: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(size, "UNTRACKED_BYTES", 20)
    put(repo, "big.txt", lines(50))
    put(repo, "small.txt", lines(1))

    assert size.main([str(repo), "--base", "HEAD"]) == 0
    text = capsys.readouterr().out
    result = report(repo, capsys, "--base", "HEAD")

    assert result["kinds"]["docs"] == {"files": 2, "added": 1, "removed": 0, "net": 1}
    assert result["too_large"] == ["big.txt"]
    assert "over 20 bytes count as files, with no lines: big.txt" in text


def test_the_default_base_is_the_merge_base_with_the_upstream(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fork = git(repo, "rev-parse", "HEAD")
    git(repo, "checkout", "-q", "-b", "feature")
    git(repo, "branch", "-q", "--set-upstream-to=main")
    put(repo, "app/feature.py", lines(4))
    commit(repo)
    git(repo, "checkout", "-q", "main")  # the upstream moves on after the fork
    put(repo, "app/other.py", lines(9))
    commit(repo)
    git(repo, "checkout", "-q", "feature")

    result = report(repo, capsys)

    assert result["base"] == {
        "ref": "main",
        "how": "merge base of HEAD with its upstream",
        "commit": fork,
    }
    assert result["kinds"] == {"code": {"files": 1, "added": 4, "removed": 0, "net": 4}}


def test_without_an_upstream_the_default_base_is_origin_head(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fork = git(repo, "rev-parse", "HEAD")
    git(repo, "update-ref", "refs/remotes/origin/main", fork)
    git(repo, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main")
    put(repo, "app/more.py", lines(2))
    commit(repo)

    result = report(repo, capsys)

    assert result["base"]["ref"] == "origin/HEAD"
    assert result["base"]["commit"] == fork
    assert result["kinds"] == {"code": {"files": 1, "added": 2, "removed": 0, "net": 2}}


def test_an_explicit_base_is_used_as_it_is_not_as_a_merge_base(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    git(repo, "tag", "v1.0.0")
    put(repo, "app/more.py", lines(2))
    commit(repo)
    git(repo, "checkout", "-q", "-b", "other", "v1.0.0")
    put(repo, "app/side.py", "alpha\nbeta\ngamma\n")  # unlike more.py, so no rename is seen
    commit(repo)

    result = report(repo, capsys, "--base", "main")

    # Against the tip of `main`: the file main added is removed, the file this branch added is new.
    assert result["kinds"] == {"code": {"files": 2, "added": 3, "removed": 2, "net": 1}}


def test_with_no_upstream_and_no_origin_head_the_default_base_is_refused(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert size.main([str(repo)]) == 1
    captured = capsys.readouterr()

    assert captured.out == ""
    assert captured.err.startswith("SIZE_BASE_MISSING: the current branch has no upstream")
    assert "--base REF" in captured.err


@pytest.mark.parametrize("ref", ["no-such-tag", "--output=x"])
def test_a_base_that_names_no_commit_is_refused(
    repo: Path, capsys: pytest.CaptureFixture[str], ref: str
) -> None:
    assert size.main([str(repo), f"--base={ref}"]) == 1
    captured = capsys.readouterr()

    assert captured.err.startswith(f'SIZE_BASE_MISSING: --base "{ref}" names no commit')
    assert not (repo / "x").exists()


def test_a_folder_that_is_no_work_tree_fails_with_gits_message(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()

    assert size.main([str(plain), "--base", "HEAD"]) == 1
    assert capsys.readouterr().err.startswith("SIZE_GIT_FAILED: fatal: not a git repository")


def test_usage_errors_exit_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert size.main([str(tmp_path / "missing")]) == 2
    assert capsys.readouterr().err.startswith("SIZE_TARGET: ")
    with pytest.raises(SystemExit) as stopped:
        size.main(["--nope"])
    assert stopped.value.code == 2


def test_a_folder_inside_the_work_tree_measures_the_whole_work_tree(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    put(repo, "app/main.py", lines(10) + lines(1))
    put(repo, "README.md", lines(2) + lines(1))

    assert size.main([str(repo / "app"), "--json", "--base", "HEAD"]) == 0
    result = json.loads(capsys.readouterr().out)

    assert result["total"]["files"] == 2


def test_no_change_is_a_report_of_zeros_with_no_share(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    result = report(repo, capsys, "--base", "HEAD")
    assert result["kinds"] == {}
    assert result["total"] == {"files": 0, "added": 0, "removed": 0, "net": 0}
    assert result["non_code_share_of_added"] is None

    assert size.main([str(repo), "--base", "HEAD"]) == 0
    assert capsys.readouterr().out.splitlines()[-1] == (
        "non-code share of added lines: none (no line added)"
    )


def test_the_json_report_has_the_documented_shape(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    put(repo, "new.py", lines(1))
    head = git(repo, "rev-parse", "HEAD")

    result = report(repo, capsys, "--base", "HEAD")

    assert sorted(result) == [
        "base",
        "binary",
        "kinds",
        "non_code_share_of_added",
        "skipped_untracked",
        "too_large",
        "total",
        "untracked_files",
        "version",
    ]
    assert result["version"] == 1
    assert result["base"] == {"ref": "HEAD", "how": "--base", "commit": head}
    assert len(result["base"]["commit"]) == 40
    assert result["non_code_share_of_added"] == 0.0


def snapshot(root: Path) -> dict[str, tuple[int, bytes]]:
    found = {}
    for current, folders, names in os.walk(root):
        folders.sort()
        for name in sorted(names):
            path = Path(current) / name
            found[str(path.relative_to(root))] = (path.stat().st_mtime_ns, path.read_bytes())
    return found


def test_a_run_writes_nothing_not_even_the_index(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    put(repo, "new.py", lines(3))
    put(repo, "app/main.py", lines(11))
    # A rewrite with the same bytes stales the index entry, which an unlocked Git would refresh.
    put(repo, "README.md", lines(2))
    os.utime(repo / "README.md", ns=(10**18, 10**18))
    before = snapshot(repo)

    assert size.main([str(repo), "--base", "HEAD"]) == 0
    assert size.main([str(repo), "--base", "HEAD", "--json"]) == 0
    capsys.readouterr()

    assert snapshot(repo) == before
