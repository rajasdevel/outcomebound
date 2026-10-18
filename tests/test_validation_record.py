"""`outcomebound validation` keeps a result for each claim it runs, `--claim` selects claims, and
`validation status` says which declared paths changed since: against scratch Git repositories."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from outcomebound_tools import schemacheck, validation

ROOT = Path(__file__).resolve().parent.parent
IDENTITY = ("-c", "user.name=T", "-c", "user.email=t@example.test", "-c", "commit.gpgsign=false")
OK = [sys.executable, "-c", "raise SystemExit(0)"]
BAD = [sys.executable, "-c", "raise SystemExit(3)"]


@pytest.fixture(autouse=True)
def hermetic_git(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


def git(where: Path, *args: str) -> str:
    done = subprocess.run(["git", *IDENTITY, *args], cwd=where, check=True, capture_output=True)
    return done.stdout.decode("utf-8").strip()


def put(root: Path, name: str, text: str) -> None:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def commit(root: Path) -> None:
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "change")


def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    put(root, ".gitignore", ".outcomebound-checks/\n")
    put(root, "src/a.py", "a = 1\n")
    put(root, "docs/readme.md", "hello\n")
    commit(root)
    return root


def claim(name: str = "unit", **fields):
    return {
        "name": name,
        "risk": "r",
        "kind": "test",
        "command": OK,
        "paths": ["src"],
        **fields,
    }


def plan(root: Path, claims, name: str = "plan.json") -> Path:
    path = root / name
    path.write_text(json.dumps({"version": 1, "claims": claims}), encoding="utf-8")
    return path


def main(capsys, *argv: str) -> tuple[int, str, str]:
    capsys.readouterr()
    code = validation._main(list(argv))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def record(root: Path, name: str = "unit") -> dict:
    return json.loads((root / ".outcomebound-checks" / f"{name}.result.json").read_text())


def status_line(capsys, path: Path, name: str = "unit") -> str:
    code, out, _ = main(capsys, "status", str(path))
    assert code == 0
    return next(line for line in out.splitlines() if f" {name} " in line)


def test_a_run_keeps_one_record_with_what_it_observed(tmp_path, capsys):
    root = repo(tmp_path)
    put(root, "docs/readme.md", "edited\n")
    path = plan(root, [claim(), claim("bad", command=BAD, required=False)])
    code, _, _ = main(capsys, str(path))
    assert code == 0
    first = record(root)
    assert (
        schemacheck.validate(
            first, json.loads((ROOT / "schemas/validation-result.schema.json").read_text())
        )
        == []
    )
    assert first["claim"] == "unit" and first["argv"] == OK and first["exit_code"] == 0
    assert first["verdict"] == "PASS" and first["log"] == "unit.log"
    assert first["head"] == git(root, "rev-parse", "HEAD")
    assert [d["path"] for d in first["dirty"]] == ["docs/readme.md", "plan.json"]
    assert len(first["plan_digest"]) == 64 and first["started"] <= first["ended"]
    assert record(root, "bad")["exit_code"] == 3 and record(root, "bad")["verdict"] == "FAIL"


def test_claim_runs_only_the_named_claims_and_the_verdict_says_so(tmp_path, capsys):
    root = repo(tmp_path)
    path = plan(root, [claim("one"), claim("two", command=BAD), claim("three", required=False)])
    code, out, _ = main(capsys, str(path), "--claim", "one", "--claim", "three")
    assert code == 0 and "two" not in out
    assert "2 of 3 claims, selected by --claim" in out
    assert not (root / ".outcomebound-checks" / "two.result.json").exists()
    assert (root / ".outcomebound-checks" / "one.result.json").exists()

    code, out, _ = main(capsys, str(path), "--claim", "three")
    assert code == 2 and "VERDICT: UNVERIFIED (no required claim was selected)" in out

    code, _, err = main(capsys, str(path), "--claim", "nope")
    assert code == 2 and "nope" in err
    code, _, err = main(capsys, str(path), "--claim", "one", "--waive", "two=because")
    assert code == 2 and "two" in err


def test_a_claim_not_run_keeps_its_earlier_record(tmp_path, capsys):
    root = repo(tmp_path)
    path = plan(root, [claim("one"), claim("two")])
    main(capsys, str(path))
    before = record(root, "two")
    put(root, "src/a.py", "a = 2\n")
    main(capsys, str(path), "--claim", "one")
    assert record(root, "two") == before


def test_status_is_current_until_a_declared_path_changes(tmp_path, capsys):
    root = repo(tmp_path)
    path = plan(root, [claim()])
    main(capsys, str(path))
    assert status_line(capsys, path).startswith("CURRENT unit")
    put(root, "docs/readme.md", "other\n")
    commit(root)
    line = status_line(capsys, path)
    assert line.startswith("CURRENT unit") and "no declared path changed" in line
    put(root, "src/a.py", "a = 3\n")
    line = status_line(capsys, path)
    assert line.startswith("CHANGED unit") and "src/a.py" in line
    commit(root)
    assert status_line(capsys, path).startswith("CHANGED unit")


def test_a_path_dirty_at_the_start_and_edited_again_is_changed(tmp_path, capsys):
    root = repo(tmp_path)
    put(root, "src/a.py", "a = 9\n")
    path = plan(root, [claim()])
    main(capsys, str(path))
    assert status_line(capsys, path).startswith("CURRENT unit")  # control: same content
    put(root, "src/a.py", "a = 10\n")
    assert status_line(capsys, path).startswith("CHANGED unit")
    git(root, "checkout", "-q", "--", "src/a.py")  # reverted: not what ran
    assert status_line(capsys, path).startswith("CHANGED unit")


def test_an_untracked_file_under_a_declared_path_is_changed(tmp_path, capsys):
    root = repo(tmp_path)
    path = plan(root, [claim()])
    main(capsys, str(path))
    put(root, "src/new.py", "x\n")
    assert "src/new.py" in status_line(capsys, path)


def test_no_declared_paths_reads_unverified_with_the_count(tmp_path, capsys):
    root = repo(tmp_path)
    path = plan(root, [claim(paths=[])])
    main(capsys, str(path))
    put(root, "docs/readme.md", "z\n")
    put(root, "src/a.py", "a = 4\n")
    line = status_line(capsys, path)
    assert line.startswith("UNVERIFIED unit") and "declares no paths" in line
    assert "2 file(s) changed since" in line


def test_a_changed_claim_or_no_record_or_no_commit_reads_unverified(tmp_path, capsys):
    root = repo(tmp_path)
    path = plan(root, [claim()])
    assert "no result kept" in status_line(capsys, path)
    main(capsys, str(path))
    plan(root, [claim(command=BAD)])
    assert "differ from the record" in status_line(capsys, path)
    plan(root, [claim()])
    made = record(root)
    made["head"] = "0" * 40
    (root / ".outcomebound-checks" / "unit.result.json").write_text(json.dumps(made))
    line = status_line(capsys, path)
    assert line.startswith("UNVERIFIED unit") and "cannot compare with the recorded commit" in line


def test_outside_git_status_reads_unverified_and_the_run_still_keeps_a_record(tmp_path, capsys):
    folder = tmp_path / "plain"
    folder.mkdir()
    path = plan(folder, [claim()])
    code, _, _ = main(capsys, str(path))
    assert code == 0 and record(folder)["head"] is None and record(folder)["dirty"] is None
    assert status_line(capsys, path).startswith("UNVERIFIED unit")


def test_a_plan_below_the_repository_root_matches_paths_from_its_own_directory(tmp_path, capsys):
    root = repo(tmp_path)
    put(root, "app/src/b.py", "b\n")
    put(root, "other/c.py", "c\n")
    commit(root)
    path = plan(root / "app", [claim()])
    main(capsys, str(path))
    put(root, "other/c.py", "c2\n")
    put(root, "src/a.py", "a = 5\n")  # root-level src is not app/src
    assert status_line(capsys, path).startswith("CURRENT unit")
    put(root, "app/src/b.py", "b2\n")
    assert "app/src/b.py" in status_line(capsys, path)


def test_status_runs_nothing_writes_nothing_and_makes_no_verdict(tmp_path, capsys):
    root = repo(tmp_path)
    marker = root / "ran"
    touching = [sys.executable, "-c", f"open({str(marker)!r}, 'w').close()"]
    path = plan(root, [claim(command=touching)])
    main(capsys, str(path))
    marker.unlink()
    before = sorted(p.name for p in (root / ".outcomebound-checks").iterdir())
    code, out, _ = main(capsys, "status", str(path))
    assert code == 0 and "VERDICT" not in out and not marker.exists()
    assert sorted(p.name for p in (root / ".outcomebound-checks").iterdir()) == before


def test_a_declared_path_may_not_leave_the_project(tmp_path, capsys):
    root = repo(tmp_path)
    for bad in (["../x"], ["/etc"], [".git/config"]):
        code, _, err = main(capsys, str(plan(root, [claim(paths=bad)])))
        assert code == 2 and "paths" in err
    code, _, _ = main(capsys, str(plan(root, [claim(paths=["."])])))
    assert code == 0


def test_edit_run_commit_stays_current_because_the_content_is_what_ran(tmp_path, capsys):
    root = repo(tmp_path)
    put(root, "src/a.py", "a = 7\n")
    path = plan(root, [claim()])
    main(capsys, str(path))
    commit(root)
    assert status_line(capsys, path).startswith("CURRENT unit")
    git(root, "status")  # a refreshed index changes nothing
    assert status_line(capsys, path).startswith("CURRENT unit")


def test_a_declared_link_or_a_path_git_does_not_read_is_unverified(tmp_path, capsys):
    root = repo(tmp_path)
    (root / "lib").mkdir()
    put(root, "lib/x.py", "x\n")
    (root / "ln").symlink_to("lib", target_is_directory=True)
    commit(root)
    for declared, why in ((["ln"], "is a link"), (["srcc"], "names nothing Git reads")):
        path = plan(root, [claim(paths=declared)])
        main(capsys, str(path))
        line = status_line(capsys, path)
        assert line.startswith("UNVERIFIED unit") and why in line


def test_a_changed_contract_is_not_current(tmp_path, capsys):
    root = repo(tmp_path)
    path = plan(root, [claim()])
    main(capsys, str(path))
    plan(root, [claim(executes_tests={"no_tests_exit": 5})])
    assert "differ from the record" in status_line(capsys, path)


def test_a_record_cannot_make_status_pass_git_an_option(tmp_path, capsys):
    root = repo(tmp_path)
    path = plan(root, [claim()])
    main(capsys, str(path))
    forged = record(root)
    forged["head"] = "--output=" + str(tmp_path / "written")
    (root / ".outcomebound-checks" / "unit.result.json").write_text(json.dumps(forged))
    assert "no result kept" in status_line(capsys, path)
    assert not (tmp_path / "written").exists()


def test_a_claim_run_is_not_called_the_plans_verdict_and_status_counts(tmp_path, capsys):
    root = repo(tmp_path)
    path = plan(root, [claim("one"), claim("two")])
    _, out, _ = main(capsys, str(path), "--claim", "one")
    assert "VERDICT: PASS (1 of 2 claims, selected by --claim; not the plan's verdict)" in out
    assert "all required" not in out
    _, out, _ = main(capsys, "status", str(path))
    assert out.splitlines()[0].startswith("status: 1 CURRENT, 0 CHANGED, 1 UNVERIFIED of 2")
