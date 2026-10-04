"""`outcomebound floor`: the quality floor, run against scratch Git repositories."""

from __future__ import annotations

import datetime
import json
import os
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from outcomebound_tools import floor
from outcomebound_tools.validation import _execute

STATUSES = ("PASS", "FAIL", "UNVERIFIED")
IDENTITY = {
    "GIT_AUTHOR_NAME": "Floor Tests",
    "GIT_AUTHOR_EMAIL": "floor@example.invalid",
    "GIT_COMMITTER_NAME": "Floor Tests",
    "GIT_COMMITTER_EMAIL": "floor@example.invalid",
}


def git(root: Path, *arguments: str) -> str:
    """One setup or query command in `root` that must have worked."""

    status, output, _ = _execute(
        ["git", "-c", "commit.gpgsign=false", *arguments], root, 60, {**os.environ, **IDENTITY}
    )
    text = output.decode("utf-8", "replace")
    assert status == 0, text
    return text.strip()


def repository(tmp_path: Path, files: dict[str, str]) -> Path:
    """A Git repository holding `files`, committed once on `main`."""

    root = tmp_path / "project"
    root.mkdir()
    git(root, "init", "-q", "-b", "main")
    commit(root, "start", files)
    return root


def commit(root: Path, message: str, files: dict[str, str]) -> str:
    """Write `files` (an empty text deletes one), commit everything, return the commit."""

    for relative, text in files.items():
        path = root / relative
        if text:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        else:
            path.unlink()
    git(root, "add", "-A")
    git(root, "commit", "-q", "--allow-empty", "-m", message)
    return git(root, "rev-parse", "HEAD")


def shipped(name: str, **changes: Any) -> dict[str, Any]:
    """The claim `name` exactly as `propose` ships it, with `changes` applied."""

    for claims in floor.RECIPES.values():
        for claim in claims:
            if claim["name"] == name:
                return {**claim, **changes}
    raise AssertionError(f"no shipped claim is named {name}")


def install(root: Path, *claims: dict[str, Any], adopted: dict[str, str] | None = None) -> None:
    """Write `.outcomebound/floor.json` holding `claims`, and `adopted` when given."""

    path = root / floor.FLOOR_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    document: dict[str, Any] = {"version": 1, "claims": list(claims)}
    if adopted is not None:
        document["adopted"] = adopted
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def run(capsys: pytest.CaptureFixture[str], *arguments: str) -> tuple[int, dict[str, str], str]:
    """Run one floor verb: its exit status, each claim's status word, and its output."""

    status = floor.main(list(arguments))
    output = capsys.readouterr().out
    verdicts = {}
    for line in output.splitlines():
        words = line.split(" ", 2)
        if len(words) > 1 and words[0] in STATUSES:
            verdicts[words[1]] = words[0]
    return status, verdicts, output


def on_path(monkeypatch: pytest.MonkeyPatch, tool: str) -> None:
    """Put `tool` on PATH, from PATH or beside this interpreter, or skip as UNVERIFIED."""

    found = shutil.which(tool) or shutil.which(tool, path=str(Path(sys.executable).parent))
    if found is None:
        pytest.skip(f"UNVERIFIED: {tool} is not installed here")
    parent = str(Path(found).resolve().parent)
    monkeypatch.setenv("PATH", os.pathsep.join([parent, os.environ.get("PATH", "")]))


# --- The project's own mypy config decides what the types claim reads -----------------


@pytest.mark.parametrize("config", ["pyproject.toml", "mypy.ini"])
def test_the_projects_own_mypy_config_fails_the_types_claim(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, config: str
) -> None:
    """mypy reads `pyproject.toml`'s `[tool.mypy]` (or `mypy.ini`) before `setup.cfg`'s
    `[mypy]`, so its own run checks `src/` and reports the error there. A floor that read
    `setup.cfg`'s files instead would check only a clean directory and pass; this one must
    FAIL."""

    on_path(monkeypatch, "mypy")
    own = {"pyproject.toml": '[tool.mypy]\nfiles = ["src"]\n', "mypy.ini": "[mypy]\nfiles = src\n"}
    files = {
        config: own[config],
        "setup.cfg": "[mypy]\nfiles = other\n",
        "other/ok.py": "def ok() -> int:\n    return 1\n",
        "src/app/__init__.py": (
            "def add(a: int, b: int) -> int:\n    return a + b\n\n\n"
            'def use() -> int:\n    return add(1, "2")\n'
        ),
    }
    root = repository(tmp_path, files)
    install(root, shipped("python.types"))

    status, verdicts, output = run(capsys, "check", str(root))

    assert status == 1, output
    assert verdicts == {"python.types": "FAIL"}, output
    assert "+1 src/app/__init__.py:arg-type\n" in output
    assert 'Argument 2 to "add" has incompatible type "str"' in output


# --- Baselines: a multiset of keys, tightened by deletion only ------------------------------

EVAL = 'eval "$1"\n'
EVAL_KEY = "run.sh:eval"


@pytest.mark.parametrize(
    ("found", "held", "new", "baselined", "stale"),
    [
        (["a"], ["a"], 0, 1, 0),
        (["a", "a"], ["a"], 1, 1, 0),
        (["a"], ["a", "a"], 0, 1, 1),
        (["a", "b"], ["b", "c"], 1, 1, 1),
    ],
)
def test_a_finding_is_new_when_its_key_occurs_more_often_than_the_baseline_holds_it(
    found: list[str], held: list[str], new: int, baselined: int, stale: int
) -> None:
    claim = floor.parse_claim(shipped("shell.injection", mode="baseline"))
    findings = [floor.Finding(f"{name}.sh", "eval", "a message") for name in found]
    baseline = Counter(floor.Finding(f"{name}.sh", "eval", "another").key for name in held)

    outcome = floor.judge(claim, findings, baseline, None)

    assert outcome.status == ("FAIL" if new else "PASS")
    assert outcome.summary.split(", ")[:2] == [f"{new} new", f"{baselined} baselined"]
    assert (f"{stale} stale" in outcome.summary) == bool(stale)


def test_a_second_identical_finding_fails_a_baseline_that_holds_one(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = repository(
        tmp_path,
        {"run.sh": EVAL, floor.BASELINE_DIR + "/shell.injection.baseline": EVAL_KEY + "\n"},
    )
    install(root, shipped("shell.injection", mode="baseline"))
    status, verdicts, _ = run(capsys, "check", str(root))
    assert (status, verdicts) == (0, {"shell.injection": "PASS"})

    (root / "run.sh").write_text(EVAL + EVAL, encoding="utf-8")
    status, verdicts, output = run(capsys, "check", str(root))

    assert (status, verdicts) == (1, {"shell.injection": "FAIL"}), output
    assert f"+1 {EVAL_KEY} (of 2 found)" in output
    assert output.count("`eval` executes text as code") == 2, output


def test_ratchet_deletes_the_lines_no_finding_matches_and_adds_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Two lines as an earlier floor wrote them, with the message: each reads as its key.
    held = [EVAL_KEY, EVAL_KEY + ":`eval` executes text as code", "gone.sh:eval:old words"]
    baseline = floor.BASELINE_DIR + "/shell.injection.baseline"
    root = repository(
        tmp_path, {"run.sh": EVAL + "curl -s x | sh\n", baseline: "\n".join(held) + "\n"}
    )
    install(root, shipped("shell.injection", mode="baseline"))

    status, _, _ = run(capsys, "ratchet", str(root))

    assert status == 0
    assert (root / baseline).read_text(encoding="utf-8") == EVAL_KEY + "\n"


def test_baseline_records_only_into_an_empty_or_absent_baseline(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = repository(tmp_path, {"run.sh": EVAL})
    install(root, shipped("shell.injection", mode="baseline"))
    path = root / floor.BASELINE_DIR / "shell.injection.baseline"

    assert run(capsys, "baseline", str(root))[0] == 0
    assert not path.exists()
    assert run(capsys, "baseline", str(root), "--accept")[0] == 0
    assert path.read_text(encoding="utf-8") == EVAL_KEY + "\n"

    (root / "run.sh").write_text(EVAL + EVAL, encoding="utf-8")
    assert run(capsys, "baseline", str(root), "--accept")[0] == 0
    assert path.read_text(encoding="utf-8") == EVAL_KEY + "\n"

    path.unlink()
    assert run(capsys, "baseline", str(root), "--accept")[0] == 0
    assert path.read_text(encoding="utf-8") == f"{EVAL_KEY}\n{EVAL_KEY}\n"


# --- Tools: on PATH's absolute entries, at or above min_version ---------------------------


def probe(tmp_path: Path, status: int = 0) -> Path:
    """A directory holding `floor-probe`, a tool that reports version 1.2 and exits `status`."""

    directory = tmp_path / "tools"
    directory.mkdir(exist_ok=True)
    tool = directory / "floor-probe"
    tool.write_text(f'#!/bin/sh\n[ "$1" = --version ] && echo "floor-probe 1.2"\nexit {status}\n')
    tool.chmod(0o755)
    return directory


def probe_claim(**changes: Any) -> dict[str, Any]:
    claim = {"name": "project.probe", "mode": "gate", "tool": "floor-probe", "parser": "exit"}
    return {**claim, "argv": ["floor-probe"], **changes}


@pytest.mark.parametrize(
    ("claim", "found"),
    [
        (probe_claim(), True),
        (probe_claim(min_version="1.2"), True),
        (probe_claim(tool="floor-absent", argv=["floor-absent"]), False),
        (probe_claim(min_version="1.10"), False),
    ],
)
def test_a_gating_tool_that_is_missing_or_older_than_its_minimum_is_unverified(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    claim: dict[str, Any],
    found: bool,
) -> None:
    root = repository(tmp_path, {"README": "x\n"})
    install(root, claim)
    monkeypatch.setenv("PATH", os.pathsep.join([str(probe(tmp_path)), os.environ["PATH"]]))

    status, verdicts, output = run(capsys, "check", str(root))

    assert (status, verdicts) == (
        (0, {"project.probe": "PASS"}) if found else (1, {"project.probe": "UNVERIFIED"})
    ), output


def test_a_tool_on_a_relative_path_entry_is_never_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A checkout cannot supply its own tool through `PATH=bin:…`: a relative entry is
    never searched."""

    root = repository(tmp_path, {"README": "x\n"})
    install(root, probe_claim())
    probe(root)
    monkeypatch.chdir(root)
    monkeypatch.setenv("PATH", os.pathsep.join(["tools", os.environ["PATH"]]))

    status, verdicts, _ = run(capsys, "check", str(root))

    assert (status, verdicts) == (1, {"project.probe": "UNVERIFIED"})


def test_a_failing_exit_status_fails_its_gate(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    root = repository(tmp_path, {"README": "x\n"})
    install(root, probe_claim())
    monkeypatch.setenv("PATH", os.pathsep.join([str(probe(tmp_path, 3)), os.environ["PATH"]]))

    assert run(capsys, "check", str(root))[:2] == (1, {"project.probe": "FAIL"})


def test_check_without_a_floor_cannot_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = repository(tmp_path, {"run.sh": EVAL})

    assert run(capsys, "check", str(root))[:2] == (2, {})


# --- Secrets: gitleaks over the pushed range, or the tracked files; never the secret --------

FAKE_GITLEAKS = """#!/bin/sh
[ "$1" = version ] && { echo 8.21.2; exit 0; }
echo "$@" > "$(dirname "$0")/argv"
while [ $# -gt 0 ]; do [ "$1" = --report-path ] && report=$2; shift; done
printf '%s' '[{"RuleID": "generic-api-key", "File": "app.py", "StartLine": 3,
 "Secret": "s3cr3t-value", "Match": "token = s3cr3t-value"},
 {"RuleID": "generic-api-key", "File": "local.env", "StartLine": 1,
 "Secret": "s3cr3t-value", "Match": "token = s3cr3t-value"}]' > "$report"
exit 1
"""


def test_secrets_scan_the_range_with_base_and_the_tracked_files_without_it(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A stand-in gitleaks (none is installed here) pins the argv, the report path and
    the reading: `path:line` and the rule, never the secret, and an untracked file dropped."""

    tools = tmp_path / "tools"
    tools.mkdir()
    (tools / "gitleaks").write_text(FAKE_GITLEAKS, encoding="utf-8")
    (tools / "gitleaks").chmod(0o755)
    monkeypatch.setenv("PATH", os.pathsep.join([str(tools), os.environ["PATH"]]))
    root = repository(tmp_path, {"app.py": "token = 1\n"})
    install(root, shipped("secrets"))
    base = commit(root, "floor", {})
    (root / "local.env").write_text("untracked\n", encoding="utf-8")

    status, verdicts, output = run(capsys, "check", str(root), "--claim", "secrets")
    scanned = (tools / "argv").read_text(encoding="utf-8").split()

    assert (status, verdicts) == (1, {"secrets": "FAIL"}), output
    assert scanned[0] == "dir" and "--redact" in scanned
    assert "app.py:3: generic-api-key" in output and "local.env" not in output
    assert "s3cr3t" not in output

    status, _, output = run(capsys, "check", str(root), "--claim", "secrets", "--base", base)
    scanned = (tools / "argv").read_text(encoding="utf-8").split()

    assert scanned[:2] == ["git", f"--log-opts={base}..HEAD"] and "--redact" in scanned
    assert "local.env:1" in output and "s3cr3t" not in output


CLEAN_GITLEAKS = """#!/bin/sh
[ "$1" = version ] && { echo 8.21.2; exit 0; }
while [ $# -gt 0 ]; do [ "$1" = --report-path ] && report=$2; shift; done
printf '[]' > "$report"
exit 0
"""


def test_a_clean_gitleaks_run_passes_through_its_report_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A clean scan reads PASS through the report file, with a base and without one."""

    tools = tmp_path / "tools"
    tools.mkdir()
    (tools / "gitleaks").write_text(CLEAN_GITLEAKS, encoding="utf-8")
    (tools / "gitleaks").chmod(0o755)
    monkeypatch.setenv("PATH", os.pathsep.join([str(tools), os.environ["PATH"]]))
    root = repository(tmp_path, {"app.py": "x = 1\n"})
    install(root, shipped("secrets"))
    base = commit(root, "floor", {})
    commit(root, "work", {"app.py": "x = 2\n"})

    for extra in ((), ("--base", base)):
        status, verdicts, output = run(capsys, "check", str(root), "--claim", "secrets", *extra)

        assert (status, verdicts.get("secrets")) == (0, "PASS"), output


def test_the_shipped_secrets_claim_keeps_redact_in_both_of_its_argvs() -> None:
    """Both argvs, with a base and without one, carry gitleaks' own `--redact`, so gitleaks
    itself redacts the secret in what it reports."""

    claim = shipped("secrets")

    assert "--redact" in claim["argv"] and "--redact" in claim["argv_without_base"]


# --- The loosening check: `check --base` over the merge base with the ref and HEAD ----------


def comment(text: str) -> str:
    """A `#` comment. The suppression markers are never spelled whole in this file, so the
    loosening check does not read the tests that hold it as loosenings."""

    return "# " + text


SPACED = 'x = "a"  '
LINT_BASELINE = floor.BASELINE_DIR + "/python.lint.baseline"
F401 = "src/a.py:F401:`os` imported but unused"
F841 = "src/a.py:F841:Local variable `x` is assigned to but never used"
BEFORE = {
    "run.sh": "#!/bin/sh\necho ok\n",
    "ruff.toml": "line-length = 100\n",
    "mypy.ini": "[mypy]\nfiles = src\n",
    ".gitleaks.toml": 'title = "project"\n',
    "pyproject.toml": '[project]\nname = "p"\n\n[tool.ruff]\nline-length = 100\n',
    "setup.cfg": "[metadata]\nname = p\n\n[mypy]\nstrict = True\n",
    "src/app.py": "import os  " + comment("noqa: F401") + "\n",
    LINT_BASELINE: F401 + "\n" + F841 + "\n",
}


LOOSENINGS = {
    "a baseline gains a line": {LINT_BASELINE: F401 + "\n" + F401 + "\n" + F841 + "\n"},
    "floor.json drops a claim": {floor.FLOOR_PATH: '{"version": 1, "claims": []}\n'},
    "floor.json narrows a claim": {
        floor.FLOOR_PATH: json.dumps(
            {"version": 1, "claims": [shipped("shell.injection", files=["bin/*.sh"])]}
        )
    },
    "ruff.toml changes": {"ruff.toml": "line-length = 120\n"},
    "a nested ruff.toml appears": {"tests/ruff.toml": '[lint]\nignore = ["ALL"]\n'},
    "mypy.ini changes": {"mypy.ini": "[mypy]\nfiles = src, tests\n"},
    ".gitleaks.toml changes": {".gitleaks.toml": 'title = "other"\n'},
    "[tool.ruff] changes": {
        "pyproject.toml": '[project]\nname = "p"\n\n[tool.ruff]\nline-length = 120\n'
    },
    "[tool.mypy] appears": {
        "pyproject.toml": BEFORE["pyproject.toml"] + "\n[tool.mypy]\nstrict = false\n"
    },
    "[mypy] changes": {"setup.cfg": "[metadata]\nname = p\n\n[mypy]\nstrict = False\n"},
    "a noqa is added": {"src/b.py": SPACED + comment("noqa: E501") + "\n"},
    "a noqa widens": {"src/app.py": "import os  " + comment("noqa: F401, E501") + "\n"},
    "a type ignore is added": {
        "src/b.py": "y: int = x  " + comment("type: ignore[assignment]") + "\n"
    },
    "a mypy comment is added": {"src/b.py": comment("mypy: ignore-errors") + "\n"},
    "a shellcheck disable is added": {
        "run.sh": "#!/bin/sh\n" + comment("shellcheck disable=SC2086") + "\necho $1\n"
    },
    "a gitleaks allow is added": {
        "src/b.py": "token = 1  " + comment("gitleaks" + ":allow") + "\n"
    },
    "a .shellcheckrc appears": {".shellcheckrc": "disable=SC2086\n"},
    "a document adds a gitleaks allow": {
        "docs/notes.md": "token = 1  " + comment("gitleaks" + ":allow") + "\n"
    },
}
TIGHTENINGS = {
    "nothing changes": {},
    "a baseline loses a line": {LINT_BASELINE: F841 + "\n"},
    "a baseline line drops its message": {LINT_BASELINE: "src/a.py:F401\n" + F841 + "\n"},
    "a baseline is deleted": {LINT_BASELINE: ""},
    "pyproject.toml changes outside its tool tables": {
        "pyproject.toml": BEFORE["pyproject.toml"].replace('"p"', '"q"')
    },
    "setup.cfg changes outside [mypy]": {"setup.cfg": BEFORE["setup.cfg"].replace("= p", "= q")},
    "a line keeps its noqa": {"src/app.py": "import os, sys  " + comment("noqa: F401") + "\n"},
    "a noqa is removed": {"src/app.py": "import os\n"},
    "a file with a noqa is renamed": {"src/app.py": "", "src/moved.py": BEFORE["src/app.py"]},
    "a document quotes suppression comments": {
        "docs/floor.md": "The check prints: adds "
        + comment("noqa: S307")
        + "\nand "
        + comment("type: ignore")
        + "\n"
    },
}


def loosen(tmp_path: Path, change: dict[str, str], *messages: str) -> tuple[Path, str]:
    """A repository holding `BEFORE` and a floor at a base commit, then one commit per
    message (`change` in the last): the repository and the base commit."""

    root = repository(tmp_path, BEFORE)
    install(root, shipped("shell.injection"))
    base = commit(root, "floor", {})
    for message in messages[:-1]:
        commit(root, message, {})
    commit(root, messages[-1] if messages else "change", change)
    return root, base


@pytest.mark.parametrize("change", LOOSENINGS.values(), ids=LOOSENINGS.keys())
def test_a_loosening_fails_the_check_against_its_base(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], change: dict[str, str]
) -> None:
    root, base = loosen(tmp_path, change)

    status, verdicts, output = run(capsys, "check", str(root), "--base", base)

    assert (status, verdicts.get("loosening")) == (1, "FAIL"), output


@pytest.mark.parametrize("change", TIGHTENINGS.values(), ids=TIGHTENINGS.keys())
def test_what_loosens_nothing_passes_the_check_against_its_base(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], change: dict[str, str]
) -> None:
    root, base = loosen(tmp_path, change)

    status, verdicts, output = run(capsys, "check", str(root), "--base", base)

    assert (status, verdicts) == (0, {"shell.injection": "PASS", "loosening": "PASS"}), output


def test_a_claim_floor_json_adds_with_its_first_baseline_loosens_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    own = {"name": "project.own", "mode": "gate", "tool": "true", "argv": ["true"]}
    claims = [shipped("shell.injection"), {**own, "parser": "exit"}, shipped("python.types")]
    root, base = loosen(
        tmp_path,
        {
            floor.FLOOR_PATH: json.dumps({"version": 1, "claims": claims}),
            floor.BASELINE_DIR
            + "/python.types.baseline": "src/a.py:misc:Unused section in config\n",
        },
    )

    output = run(capsys, "check", str(root), "--base", base)[2]

    assert "PASS loosening" in output and "PASS project.own" in output, output


@pytest.mark.parametrize(
    ("messages", "passes"),
    [
        (("widen\n\nFloor-Loosening: a long line in b.py; ruled D12",), True),
        (("widen\n\nFloor-Loosening: drop E501; keep E502; ruled D12",), True),
        (("Floor-Loosening: allow long lines; ruled D12\n\nSigned-off-by: x", "widen"), False),
        (("widen\n\nFloor-Loosening: a long line in b.py",), False),
        (("widen\n\nFloor-Loosening: ; ruled D12",), False),
    ],
)
def test_a_floor_loosening_line_in_the_range_lets_it_pass_and_is_named(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], messages: tuple[str, ...], passes: bool
) -> None:
    root, base = loosen(tmp_path, LOOSENINGS["a noqa is added"], *messages)
    ruling = git(root, "log", "--format=%H", "--grep=^Floor-Loosening:", f"{base}..HEAD")

    status, verdicts, output = run(capsys, "check", str(root), "--base", base)

    assert (status, verdicts.get("loosening")) == ((0, "PASS") if passes else (1, "FAIL")), output
    assert (f"{ruling[:12]} Floor-Loosening:" in output) == passes


def test_a_ruling_at_or_before_the_base_does_not_cover_the_range(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = repository(tmp_path, BEFORE)
    install(root, shipped("shell.injection"))
    base = commit(root, "floor\n\nFloor-Loosening: an earlier one; ruled D1", {})
    commit(root, "widen", LOOSENINGS["a noqa is added"])

    assert run(capsys, "check", str(root), "--base", base)[:2] == (
        1,
        {"shell.injection": "PASS", "loosening": "FAIL"},
    )


@pytest.mark.parametrize(
    ("second", "passes"),
    [("widen", False), ("widen\n\nFloor-Loosening: a long line in b.py; ruled D13", True)],
)
def test_a_ruling_covers_the_loosenings_its_own_commit_makes_and_no_other(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], second: str, passes: bool
) -> None:
    root = repository(tmp_path, BEFORE)
    install(root, shipped("shell.injection"))
    base = commit(root, "floor", {})
    ruled = "record\n\nFloor-Loosening: python.lint baseline; ruled X1"
    commit(root, ruled, LOOSENINGS["a baseline gains a line"])
    widened = commit(root, second, LOOSENINGS["a noqa is added"])

    status, verdicts, output = run(capsys, "check", str(root), "--base", base)

    assert (status, verdicts.get("loosening")) == ((0, "PASS") if passes else (1, "FAIL")), output
    assert f"{LINT_BASELINE} gained 1 line (ruled in " in output
    assert (f"not ruled: {widened[:12]} carries no Floor-Loosening line" in output) != passes


def test_a_ruled_commit_does_not_cover_a_later_loosening_of_the_same_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = repository(tmp_path, BEFORE)
    install(root, shipped("shell.injection"))
    base = commit(root, "floor", {})
    line = SPACED + comment("noqa: E501") + "\n"
    commit(root, "one\n\nFloor-Loosening: one long line; ruled D1", {"src/b.py": line})
    later = commit(root, "two", {"src/b.py": line + line})

    status, verdicts, output = run(capsys, "check", str(root), "--base", base)

    assert (status, verdicts.get("loosening")) == (1, "FAIL"), output
    assert f"src/b.py adds {comment('noqa: e501')} (x2) (not ruled: {later[:12]}" in output


@pytest.mark.parametrize("ruled", [False, True])
def test_a_loosening_only_a_merge_makes_passes_where_a_commit_touching_its_file_is_ruled(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], ruled: bool
) -> None:
    root = repository(tmp_path, BEFORE)
    install(root, shipped("shell.injection"))
    base = commit(root, "floor", {})
    git(root, "checkout", "-q", "-b", "side")
    commit(root, "side", {"src/c.py": "z = 1\n"})
    git(root, "checkout", "-q", "main")
    commit(root, "main", {"src/d.py": "w = 1\n"})
    git(root, "merge", "-q", "--no-ff", "--no-commit", "side")
    (root / "src" / "b.py").write_text(SPACED + comment("noqa: E501") + "\n", encoding="utf-8")
    trailer = "\n\nFloor-Loosening: a long line; ruled D2" if ruled else ""
    commit(root, "merge side" + trailer, {})

    status, verdicts, output = run(capsys, "check", str(root), "--base", base)

    assert (status, verdicts.get("loosening")) == ((0, "PASS") if ruled else (1, "FAIL")), output
    assert ("no one commit makes it, and none that touches it" in output) != ruled


def test_the_range_starts_at_the_merge_base_so_a_tightening_on_the_base_is_not_a_loosening(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The ref moved on (a ratchet on `main`) after this branch left it: comparing the two
    tips would read the branch's untouched baseline as having gained a line."""

    root = repository(tmp_path, BEFORE)
    install(root, shipped("shell.injection"))
    fork = commit(root, "floor", {})
    tightened = commit(root, "ratchet", TIGHTENINGS["a baseline loses a line"])
    git(root, "checkout", "-q", "-b", "work", fork)
    commit(root, "work", {"src/c.py": "z = 3\n"})

    assert run(capsys, "check", str(root), "--base", tightened)[:2] == (
        0,
        {"shell.injection": "PASS", "loosening": "PASS"},
    )


def test_a_base_that_does_not_resolve_is_unverified(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root, _ = loosen(tmp_path, {})

    for base in ("no-such-ref", "--output=x"):
        assert run(capsys, "check", str(root), f"--base={base}")[:2] == (
            1,
            {"shell.injection": "PASS", "loosening": "UNVERIFIED"},
        )


# --- propose, apply and remove --------------------------------------------------------------


def tree(root: Path) -> dict[str, bytes]:
    """Each file under `root`, leaving out Git's and the caches the tools apply runs keep."""

    skipped = {".git", ".mypy_cache", ".ruff_cache"}
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file() and not skipped & set(path.relative_to(root).parts)
    }


@pytest.mark.parametrize(
    ("files", "stacks"),
    [
        ({"lib/a.py": "x = 1\n"}, ("python", "secrets")),
        ({"pyproject.toml": "[project]\n"}, ("python", "secrets")),
        ({"bin/run.sh": "echo\n"}, ("shell", "secrets")),
        ({"a.py": "x = 1\n", "run.sh": "echo\n"}, ("python", "shell", "secrets")),
        ({"README": "x\n"}, ("secrets",)),
        ({}, ()),
    ],
)
def test_propose_offers_the_stacks_git_tracks_and_writes_nothing(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    files: dict[str, str],
    stacks: tuple[str, ...],
) -> None:
    root = repository(tmp_path, files)
    (root / "untracked.py").write_text("x = 1\n", encoding="utf-8")
    before = tree(root)

    status = floor.main(["propose", str(root)])
    printed = capsys.readouterr().out

    assert tree(root) == before
    assert status == (0 if stacks else 1)
    offered = [claim["name"] for claim in json.loads(printed)["claims"]] if stacks else []
    assert offered == [claim["name"] for stack in stacks for claim in floor.RECIPES[stack]]


def test_propose_for_typescript_offers_secrets_and_says_why_it_proposes_no_type_or_lint_claim(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    files = {"package.json": "{}\n", "tsconfig.json": "{}\n", "src/a.ts": "export const a = 1;\n"}
    root = repository(tmp_path, {**files, "bin/run.sh": "echo\n"})

    status = floor.main(["propose", str(root)])
    printed = capsys.readouterr()

    assert status == 0
    offered = [claim["name"] for claim in json.loads(printed.out)["claims"]]
    assert offered == ["shell.syntax", "shell.injection", "shell.lint", "secrets"]
    assert "no claim is proposed for its types or its lint" in printed.err
    for claim in floor.TYPESCRIPT_CLAIMS:
        assert json.dumps(claim) in printed.err
        assert floor.parse_claim(claim).mode == "gate"


PACKAGES = {
    "src/pkg/__init__.py": "\n",
    "src/pkg/sub/__init__.py": "\n",
    "src/pkg/a.py": "x: int = 1\n",
    "scripts/tool.py": "y = 1\n",
    "docs/tool.py": "y = 2\n",
}


@pytest.mark.parametrize(
    ("config", "targets"),
    [
        ({}, ["src/pkg"]),
        ({"mypy.ini": "[mypy]\nfiles = src\n"}, []),
        ({"pyproject.toml": '[tool.mypy]\nfiles = ["src"]\n'}, []),
        ({"setup.cfg": "[mypy-yaml]\nfiles = x\n"}, ["src/pkg"]),
        ({"__init__.py": "\n"}, []),
    ],
)
def test_propose_names_each_outermost_package_where_the_mypy_config_names_no_files(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], config: dict[str, str], targets: list[str]
) -> None:
    root = repository(tmp_path, {**PACKAGES, **config})

    assert floor.main(["propose", str(root)]) == 0
    claims = {claim["name"]: claim for claim in json.loads(capsys.readouterr().out)["claims"]}

    assert claims["python.types"]["argv"] == ["mypy", "--output", "json", *targets]


def test_the_proposed_types_claim_reads_a_project_whose_scripts_share_a_module_name(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    on_path(monkeypatch, "mypy")
    root = repository(tmp_path, PACKAGES)
    assert floor.main(["propose", str(root)]) == 0
    proposed = json.loads(capsys.readouterr().out)["claims"]
    source = proposal(tmp_path, *(c for c in proposed if c["name"] == "python.types"))

    output = run(capsys, "apply", str(root), "--floor", str(source), "--accept")[2]

    assert "python.types: passes" in output, output
    assert run(capsys, "check", str(root))[:2] == (0, {"python.types": "PASS"})


def test_mypy_stopping_is_named_by_the_error_that_stopped_it_with_its_hint(tmp_path: Path) -> None:
    hint = "Common resolutions include:\n    a) adding `__init__.py` somewhere"
    records = [
        {"file": "src/pkg/a.py", "line": 1, "column": 0, "code": "import-not-found"},
        {"file": "scripts/tool.py", "line": -1, "column": -1, "code": None, "hint": hint},
    ]
    messages = ['Cannot find a stub for "missing"', "Source file found twice: tool, scripts.tool"]
    text = "".join(
        json.dumps({**record, "message": message, "severity": "error"}) + "\n"
        for record, message in zip(records, messages, strict=True)
    )

    with pytest.raises(floor.Unreadable) as stopped:
        floor.parse_mypy(2, text, tmp_path)

    shown = str(stopped.value)
    assert "scripts/tool.py: Source file found twice: tool, scripts.tool" in shown
    assert "(Common resolutions include: a) adding `__init__.py` somewhere)" in shown
    assert "missing" not in shown and "`files` or `exclude`" in shown


def test_apply_then_remove_leaves_the_tree_as_it_was(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = repository(tmp_path, {"a.py": "x = 1\n", "run.sh": "echo\n"})
    proposal = tmp_path / "floor.json"
    assert floor.main(["propose", str(root)]) == 0
    proposal.write_text(capsys.readouterr().out, encoding="utf-8")
    before = tree(root)

    assert run(capsys, "apply", str(root), "--floor", str(proposal))[0] == 0
    assert tree(root) == before
    assert run(capsys, "apply", str(root), "--floor", str(proposal), "--strict", "--accept")[0] == 0
    applied = tree(root)
    assert applied[floor.FLOOR_PATH] == proposal.read_bytes()
    assert {path: applied[path] for path in applied if path.endswith(".baseline")} == {
        f"{floor.BASELINE_DIR}/python.lint.baseline": b"",
        f"{floor.BASELINE_DIR}/python.types.baseline": b"",
        f"{floor.BASELINE_DIR}/shell.lint.baseline": b"",
    }

    assert run(capsys, "remove", str(root), "--accept")[0] == 0
    assert tree(root) == before
    assert not (root / ".outcomebound").exists()


@pytest.mark.parametrize(
    "claim",
    [
        {"name": "Bad Name", "mode": "gate", "parser": "exit", "tool": "t", "argv": ["t"]},
        {"name": "a.b", "mode": "observe", "parser": "exit", "tool": "t", "argv": ["t"]},
        {"name": "a.b", "mode": "gate", "parser": "exit", "tool": "t", "argv": ["u"]},
        {"name": "a.b", "mode": "gate", "parser": "exit", "tool": "../t", "argv": ["../t"]},
        {"name": "a.b", "mode": "baseline", "parser": "exit", "tool": "t", "argv": ["t"]},
        {"name": "a.b", "mode": "gate", "parser": "bash-n", "tool": "t", "argv": ["t"]},
        {"name": "a.b", "mode": "baseline", "parser": "shellcheck", "tool": "t", "argv": ["t"]},
        {"name": "a.b", "mode": "gate", "parser": "injection", "tool": "t", "files": ["*.sh"]},
        {"name": "a.b", "mode": "gate", "parser": "injection", "prefix": ["p"], "files": ["*.sh"]},
        {"name": "a.b", "mode": "gate", "parser": "exit", "tool": "t", "argv": ["p", "t"]},
        {"name": "a.b", "mode": "gate", "parser": "exit", "tool": "t", "argv": ["t"], "prefix": []},
        {
            "name": "a.b",
            "mode": "gate",
            "parser": "exit",
            "tool": "t",
            "argv": ["t"],
            "prefix": ["./p"],
        },
        *(
            {
                "name": "a.b",
                "mode": "gate",
                "parser": "exit",
                "tool": "t",
                "argv": ["t"],
                "timeout_seconds": bad,
            }
            for bad in (0, -5, True, "60", float("inf"))
        ),
        {
            "name": "a.b",
            "mode": "gate",
            "parser": "exit",
            "tool": "t",
            "argv": ["t"],
            "bin_dirs": ["x"],
        },
    ],
)
def test_a_claim_that_cannot_run_as_written_is_refused(claim: dict[str, Any]) -> None:
    with pytest.raises(floor.FloorError):
        floor.parse_claim(claim)


# --- The parsers, on output captured from ruff 0.16.7, mypy 2.3.1, bash 5.3, shellcheck 0.11.0 --
#
# tests/fixtures/floor/ holds what each tool printed, stdout and stderr merged as the floor
# reads them, over one scratch project: `ruff check --output-format json .` (the project's
# root path replaced by `{root}`), `ruff format --check .`, `mypy --output json`,
# `bash -n scripts/broken.sh` and `shellcheck -f json1 scripts/lint.sh` (shellcheck 0.9.0
# and 0.10.0 printed the same comments). The gitleaks parser is read against a stated report
# here, and against real gitleaks where it is installed (the adoption tests below).

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "floor"


def fixture(name: str, root: Path | None = None) -> str:
    text = (FIXTURES / name).read_text(encoding="utf-8")
    return text if root is None else text.replace("{root}", str(root))


def test_ruff_json_keys_carry_path_and_code_and_the_message_stays_for_the_reader(
    tmp_path: Path,
) -> None:
    root = tmp_path.resolve()

    findings = floor.parse_ruff(
        1, "warning: a notice ruff printed first\n" + fixture("ruff-check.json", root), root
    )

    assert [(finding.key, finding.message) for finding in findings] == [
        ("pkg/core.py:F401", "`os` imported but unused"),
        ("pkg/core.py:F401", "`sys` imported but unused"),
        ("pkg/core.py:C901", "`pick` is too complex (3 > 2)"),
        ("pkg/core.py:F811", "Redefinition of unused `pick` from line 5: `pick` redefined here"),
    ]
    assert [finding.where for finding in findings] == ["1:8", "2:8", "5:5", "13:5"]


def test_a_file_ruff_format_cannot_parse_is_named_by_ruffs_own_error(tmp_path: Path) -> None:
    """ruff 0.16 prints the files it would rewrite first; the reason is the syntax error."""

    with pytest.raises(floor.Unreadable) as raised:
        floor.parse_ruff_format(2, fixture("ruff-format-invalid.txt"), tmp_path)

    assert str(raised.value) == (
        "ruff format exited 2: bad.py:1:7: invalid-syntax: Expected a parameter or the end of"
        " the parameter list"
    )


def test_ruff_format_names_each_file_it_would_rewrite(tmp_path: Path) -> None:
    findings = floor.parse_ruff_format(1, fixture("ruff-format.txt"), tmp_path)

    assert [finding.key for finding in findings] == ["pkg/style.py:unformatted"]
    assert floor.parse_ruff_format(0, fixture("ruff-format-clean.txt"), tmp_path) == []
    with pytest.raises(floor.Unreadable):
        floor.parse_ruff_format(2, "error: Failed to parse pkg/x.py", tmp_path)


def test_mypy_keys_count_errors_not_notes(tmp_path: Path) -> None:
    findings = floor.parse_mypy(1, fixture("mypy.jsonl"), tmp_path)

    assert [(finding.key, finding.message) for finding in findings] == [
        ("pkg/core.py:no-redef", 'Name "pick" already defined on line 5'),
        (
            "pkg/core.py:arg-type",
            'Argument 2 to "pick" has incompatible type "str"; expected "int"',
        ),
        (
            "pkg/core.py:assignment",
            'Incompatible types in assignment (expression has type "str", variable has type "int")',
        ),
        ("pkg/notes.py:import-untyped", 'Library stubs not installed for "yaml"'),
    ]
    assert floor.parse_mypy(0, "\n", tmp_path) == []
    for status, text in ((2, fixture("mypy.jsonl")), (1, "\n"), (2, "mypy: error: bad config")):
        with pytest.raises(floor.Unreadable):
            floor.parse_mypy(status, text, tmp_path)


def test_bash_n_reads_the_first_message_of_a_broken_script() -> None:
    findings = floor.parse_per_file("bash-n", 2, fixture("bash-n.txt"), "scripts/broken.sh")

    assert [(finding.key, finding.message, finding.where) for finding in findings] == [
        ("scripts/broken.sh:syntax", "syntax error near unexpected token `fi'", "4")
    ]
    assert floor.parse_per_file("bash-n", 0, "", "scripts/ok.sh") == []


def test_gitleaks_reads_path_line_and_rule_from_a_stated_report(tmp_path: Path) -> None:
    """A stated report in gitleaks 8's documented shape, not a captured one: UNVERIFIED
    against the real tool."""

    report = json.dumps(
        [
            {
                "RuleID": "aws-access-token",
                "File": "deploy/settings.py",
                "StartLine": 12,
                "Commit": "0123456789abcdef",
                "Secret": "AKIA0SECRET",
                "Match": "k = AKIA0SECRET",
            },
            {
                "RuleID": "generic-api-key",
                "File": "local.env",
                "StartLine": 1,
                "Secret": "AKIA0SECRET",
                "Match": "k = AKIA0SECRET",
            },
        ]
    )

    findings = floor.parse_gitleaks(1, report, tmp_path, frozenset({"deploy/settings.py"}))

    assert [finding.shown() for finding in findings] == [
        "deploy/settings.py:12 in 0123456789ab: aws-access-token a secret may be committed here"
    ]
    assert len(floor.parse_gitleaks(1, report, tmp_path, None)) == 2
    assert floor.parse_gitleaks(0, "[]", tmp_path, None) == []
    for status, text in ((1, "[]"), (1, ""), (2, "[]")):
        with pytest.raises(floor.Unreadable):
            floor.parse_gitleaks(status, text, tmp_path, None)


def test_shellcheck_keys_carry_its_code_not_the_message_or_the_position() -> None:
    findings = floor.parse_per_file("shellcheck", 1, fixture("shellcheck.json"), "scripts/lint.sh")

    assert [(finding.key, finding.where) for finding in findings] == [
        ("scripts/lint.sh:SC2086", "2:6"),
        ("scripts/lint.sh:SC2045", "3:10"),
        ("scripts/lint.sh:SC2035", "3:15"),
        ("scripts/lint.sh:SC2086", "4:7"),
        ("scripts/lint.sh:SC2162", "6:1"),
        ("scripts/lint.sh:SC2034", "6:6"),
    ]
    assert findings[0].message == "Double quote to prevent globbing and word splitting."
    assert floor.parse_per_file("shellcheck", 0, '{"comments":[]}\n', "ok.sh") == []


@pytest.mark.parametrize(
    ("status", "text"),
    [
        (1, '{"comments":[]}'),
        (1, "not a report"),
        (1, '{"comments":[2086]}'),
        (0, "[]"),
        (2, 'x.sh: openBinaryFile: does not exist\n{"comments":[]}'),
        (4, "Unknown format json9"),
    ],
)
def test_a_shellcheck_run_without_a_readable_report_is_unreadable(status: int, text: str) -> None:
    with pytest.raises(floor.Unreadable):
        floor.parse_per_file("shellcheck", status, text, "x.sh")


def test_the_injection_scan_reads_code_not_comments(tmp_path: Path) -> None:
    script = (
        "#!/bin/sh\n# eval is fine in a comment\n"
        'if true; then eval "$x"; fi\ncurl -s x | bash\n. <(cat x)\n'
    )
    (tmp_path / "a.sh").write_text(script, encoding="utf-8")

    findings = floor.scan_injection(tmp_path, ["a.sh"])

    assert [(finding.code, finding.where) for finding in findings] == [
        ("eval", "3"),
        ("pipe-to-shell", "4"),
        ("source-process-substitution", "5"),
    ]


# --- The real ruff, end to end -----------------------------------------------------------------


def test_the_real_ruff_fails_format_and_new_lint_then_passes_on_a_recorded_baseline(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    on_path(monkeypatch, "ruff")
    files = {"ruff.toml": '[lint]\nselect = ["F401"]\n', "a.py": "import os\nx=1\n"}
    root = repository(tmp_path, files)
    install(root, shipped("python.format"), shipped("python.lint"))

    status, verdicts, output = run(capsys, "check", str(root))

    assert (status, verdicts) == (1, {"python.format": "FAIL", "python.lint": "FAIL"}), output
    assert "+1 a.py:F401\n    1:8 `os` imported but unused" in output

    assert run(capsys, "baseline", str(root), "--accept")[0] == 0
    (root / "a.py").write_text("import os\n\nx = 1\n", encoding="utf-8")

    assert run(capsys, "check", str(root))[:2] == (
        0,
        {"python.format": "PASS", "python.lint": "PASS"},
    )


# --- apply fits the floor to what a project already holds -----------------------------------

SYNTAX_ERROR = "if true; then\n  echo ok\nfi fi\n"
# Secret-shaped values are joined here, so no line of this file holds one whole.
OLD_LEAK = "AKIA" + "QYLPMN5HHHFPZAM2"
NEW_LEAK = "AKIA" + "ZXCVBNM5ASDFGHJ7"


def today() -> str:
    return datetime.date.today().isoformat()


def proposal(tmp_path: Path, *claims: dict[str, Any]) -> Path:
    """A floor file outside the project holding `claims`, as `propose` prints one."""

    path = tmp_path / "proposal.json"
    path.write_text(json.dumps({"version": 1, "claims": list(claims)}), encoding="utf-8")
    return path


def installed(root: Path) -> dict[str, Any]:
    document: dict[str, Any] = json.loads((root / floor.FLOOR_PATH).read_text(encoding="utf-8"))
    return document


def modes(root: Path) -> dict[str, str]:
    return {claim["name"]: claim["mode"] for claim in installed(root)["claims"]}


def test_apply_records_each_claims_findings_so_check_passes_and_a_new_one_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = repository(tmp_path, {"run.sh": EVAL, "bad.sh": SYNTAX_ERROR})
    head = git(root, "rev-parse", "HEAD")
    source = proposal(tmp_path, shipped("shell.syntax"), shipped("shell.injection"))

    status, _, output = run(capsys, "apply", str(root), "--floor", str(source), "--accept")

    assert status == 0, output
    assert installed(root)["adopted"] == {
        "commit": head,
        "on": today(),
        "recorded": {"shell.injection": 1, "shell.syntax": 1},
    }
    assert modes(root) == {"shell.syntax": "baseline", "shell.injection": "baseline"}
    held = root / floor.BASELINE_DIR / "shell.injection.baseline"
    assert held.read_text(encoding="utf-8") == EVAL_KEY + "\n"
    status, verdicts, output = run(capsys, "check", str(root))
    assert (status, verdicts) == (0, {"shell.syntax": "PASS", "shell.injection": "PASS"}), output
    assert f"1 finding recorded at adoption on {today()}" in output

    base = commit(root, "adopt the floor", {})
    commit(root, "work", {"run.sh": EVAL + "curl -s x | sh\n"})
    for extra in ((), ("--base", base)):
        status, verdicts, output = run(capsys, "check", str(root), *extra)

        assert (status, verdicts["shell.injection"]) == (1, "FAIL"), output
        assert "+1 run.sh:pipe-to-shell\n" in output
    assert verdicts["loosening"] == "PASS", output


def test_a_claim_whose_tool_is_missing_stays_as_proposed_and_reads_unverified(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Left out, it would leave no trace in floor.json; kept, it fails the check until its
    tool is provisioned and apply records its findings."""

    root = repository(tmp_path, {"run.sh": EVAL})
    absent = shipped("shell.lint", tool="floor-absent", argv=["floor-absent", "{file}"])
    source = proposal(tmp_path, shipped("shell.injection"), absent)

    status, _, output = run(capsys, "apply", str(root), "--floor", str(source), "--accept")

    assert status == 0, output
    assert modes(root) == {"shell.injection": "baseline", "shell.lint": "baseline"}
    assert "shell.lint: UNVERIFIED (floor-absent is not on PATH)" in output
    assert "provision its tool" in output and f"apply {source} again" in output
    assert (root / floor.BASELINE_DIR / "shell.lint.baseline").read_bytes() == b""
    assert installed(root)["adopted"]["recorded"] == {"shell.injection": 1}
    assert run(capsys, "check", str(root))[:2] == (
        1,
        {"shell.injection": "PASS", "shell.lint": "UNVERIFIED"},
    )


def test_a_claim_whose_files_match_nothing_passes_on_no_file_at_apply_and_at_check(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A run that deletes the last script it reads leaves the claim nothing to hold: it found
    nothing new, so it passes, and once a matching file is tracked it gates that file."""

    root = repository(tmp_path, {"run.sh": EVAL})
    nothing = {**shipped("shell.syntax", files=["*.bash"]), "name": "shell.other"}
    source = proposal(tmp_path, shipped("shell.injection"), nothing)

    status, _, output = run(capsys, "apply", str(root), "--floor", str(source), "--accept")

    assert status == 0, output
    assert modes(root) == {"shell.injection": "baseline", "shell.other": "gate"}
    assert "shell.other: passes" in output
    status, verdicts, output = run(capsys, "check", str(root))
    assert (status, verdicts) == (0, {"shell.injection": "PASS", "shell.other": "PASS"}), output
    assert "PASS shell.other (0 findings in 0 files)" in output

    commit(root, "a script arrives", {"new.bash": SYNTAX_ERROR})
    assert run(capsys, "check", str(root))[1]["shell.other"] == "FAIL"


def test_apply_leaves_out_the_types_claim_when_mypy_stops_at_a_blocking_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two scripts with one module name stop mypy before it reads a type."""

    on_path(monkeypatch, "mypy")
    files = {
        "mypy.ini": "[mypy]\nfiles = scripts\n",
        "scripts/one/tool.py": "x: int = 1\n",
        "scripts/two/tool.py": "y: int = 2\n",
    }
    root = repository(tmp_path, files)
    source = proposal(tmp_path, shipped("python.types"))

    output = run(capsys, "apply", str(root), "--floor", str(source), "--accept")[2]

    assert "python.types: left out (mypy stopped at a blocking error:" in output, output
    assert installed(root)["claims"] == []
    assert run(capsys, "check", str(root))[:2] == (0, {})


def test_an_exit_status_claim_stays_a_gate_and_apply_names_its_failure(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    root = repository(tmp_path, {"README": "x\n"})
    monkeypatch.setenv("PATH", os.pathsep.join([str(probe(tmp_path, 3)), os.environ["PATH"]]))
    source = proposal(tmp_path, probe_claim())

    output = run(capsys, "apply", str(root), "--floor", str(source), "--accept")[2]

    assert "project.probe: fails now (exited 3: no output); it stays a gate" in output
    assert modes(root) == {"project.probe": "gate"}
    assert "recorded" not in installed(root)["adopted"]


def test_apply_strict_fits_nothing_and_says_what_each_claim_fails_on_now(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = repository(tmp_path, {"run.sh": EVAL + EVAL})
    held = {**shipped("shell.injection", mode="baseline"), "name": "shell.held"}
    absent = shipped("shell.lint", tool="floor-absent", argv=["floor-absent", "{file}"])
    source = proposal(tmp_path, shipped("shell.syntax"), shipped("shell.injection"), held, absent)

    status, _, output = run(
        capsys, "apply", str(root), "--floor", str(source), "--strict", "--accept"
    )

    assert status == 0, output
    written = (root / floor.FLOOR_PATH).read_bytes()
    assert written == floor.parse_floor(json.loads(source.read_text(encoding="utf-8"))).text()
    assert "adopted" not in installed(root)
    assert (root / floor.BASELINE_DIR / "shell.held.baseline").read_bytes() == b""
    assert "shell.syntax: passes" in output
    assert "shell.injection: fails now on 2 findings" in output
    assert "shell.held: fails now on 2 findings" in output
    assert "shell.lint: UNVERIFIED (floor-absent is not on PATH)" in output
    assert run(capsys, "check", str(root))[:2] == (
        1,
        {
            "shell.syntax": "PASS",
            "shell.injection": "FAIL",
            "shell.held": "FAIL",
            "shell.lint": "UNVERIFIED",
        },
    )


def test_apply_again_keeps_the_adoption_record_and_each_recorded_baseline(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A later apply, after a new finding, records nothing over what is held, so the new
    finding still fails; the adoption record and its day stay as they were."""

    root = repository(tmp_path, {"run.sh": EVAL})
    source = proposal(tmp_path, shipped("shell.injection"))
    assert run(capsys, "apply", str(root), "--floor", str(source), "--accept")[0] == 0
    adopted = installed(root)["adopted"]
    commit(root, "adopt the floor", {"run.sh": EVAL + EVAL})

    output = run(capsys, "apply", str(root), "--floor", str(source), "--accept")[2]

    assert "shell.injection: fails now on 1 finding; its baseline of 1 line is kept" in output
    assert installed(root)["adopted"] == adopted
    assert run(capsys, "check", str(root))[:2] == (1, {"shell.injection": "FAIL"})


def test_an_old_secret_is_listed_once_never_recorded_and_a_new_one_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    on_path(monkeypatch, "gitleaks")
    root = repository(tmp_path, {"app.py": f'aws = "{OLD_LEAK}"\n'})
    source = proposal(tmp_path, shipped("secrets"))

    status, _, output = run(capsys, "apply", str(root), "--floor", str(source), "--accept")

    assert status == 0, output
    assert "  app.py:aws-access-token:1" in output.splitlines(), output
    assert OLD_LEAK not in output
    assert modes(root) == {"secrets": "gate"}
    assert "recorded" not in installed(root)["adopted"]
    assert not (root / floor.BASELINE_DIR).exists()
    status, verdicts, output = run(capsys, "check", str(root))
    assert (status, verdicts) == (0, {"secrets": "PASS"}), output
    assert "in the commits since adoption on" in output

    base = commit(root, "adopt the floor", {})
    commit(root, "deploy", {"deploy.py": f'aws = "{NEW_LEAK}"\n'})
    for extra in ((), ("--base", base)):
        status, verdicts, output = run(capsys, "check", str(root), *extra)

        assert (status, verdicts["secrets"]) == (1, "FAIL"), output
        assert "deploy.py:1 in " in output and "app.py" not in output
        assert NEW_LEAK not in output


def test_the_fingerprint_apply_prints_allowlists_the_secret_in_gitleaksignore(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """`path:rule:line` in `.gitleaksignore` holds for a directory scan and for a commit
    range alike, with the floor's `--redact`."""

    on_path(monkeypatch, "gitleaks")
    root = repository(tmp_path, {"README": "x\n"})
    base = git(root, "rev-parse", "HEAD")
    commit(root, "leak", {"app.py": f'aws = "{OLD_LEAK}"\n'})
    source = proposal(tmp_path, shipped("secrets"))
    output = run(capsys, "apply", str(root), "--floor", str(source), "--strict", "--accept")[2]
    line = next(text.strip() for text in output.splitlines() if "aws-access-token" in text)

    for allowed, verdict in ((False, "FAIL"), (True, "PASS")):
        if allowed:
            (root / ".gitleaksignore").write_text(line + "\n", encoding="utf-8")
        for extra in ((), ("--base", base)):
            verdicts = run(capsys, "check", str(root), "--claim", "secrets", *extra)[1]

            assert verdicts["secrets"] == verdict, (line, extra)


def test_apply_fits_the_real_ruff_and_mypy_and_a_new_lint_finding_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    on_path(monkeypatch, "ruff")
    on_path(monkeypatch, "mypy")
    files = {
        "ruff.toml": '[lint]\nselect = ["F401"]\n',
        "mypy.ini": "[mypy]\nfiles = a.py\n",
        "a.py": 'import os\nx=1\nNAME: int = "n"\n',
    }
    root = repository(tmp_path, files)
    claims = [shipped(name) for name in ("python.format", "python.lint", "python.types")]

    output = run(
        capsys, "apply", str(root), "--floor", str(proposal(tmp_path, *claims)), "--accept"
    )[2]

    assert set(modes(root).values()) == {"baseline"}, output
    assert installed(root)["adopted"]["recorded"] == dict.fromkeys(modes(root), 1)
    assert run(capsys, "check", str(root))[:2] == (0, dict.fromkeys(modes(root), "PASS"))

    commit(root, "work", {"a.py": 'import os\nimport sys\nx=1\nNAME: int = "n"\n'})
    status, verdicts, output = run(capsys, "check", str(root))

    assert (status, verdicts["python.lint"]) == (1, "FAIL"), output
    assert "+1 a.py:F401 (of 2 found)" in output and "`sys` imported but unused" in output
    assert (verdicts["python.format"], verdicts["python.types"]) == ("PASS", "PASS"), output


def test_apply_fits_the_real_shellcheck_and_a_new_warning_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    on_path(monkeypatch, "shellcheck")
    root = repository(tmp_path, {"run.sh": "#!/bin/sh\necho $1\n"})
    source = proposal(tmp_path, shipped("shell.lint"))

    output = run(capsys, "apply", str(root), "--floor", str(source), "--accept")[2]

    assert "shell.lint: 1 finding recorded" in output, output
    assert run(capsys, "check", str(root))[:2] == (0, {"shell.lint": "PASS"})

    commit(root, "work", {"run.sh": "#!/bin/sh\necho $1\necho $2\n"})
    status, verdicts, output = run(capsys, "check", str(root))

    assert (status, verdicts) == (1, {"shell.lint": "FAIL"}), output
    assert "+1 run.sh:SC2086 (of 2 found)" in output
    assert "3:6 Double quote to prevent globbing" in output


def test_provision_prints_shellchecks_install_command_and_downloads_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    root = repository(tmp_path, {"run.sh": "echo\n"})
    install(root, shipped("shell.lint"), shipped("secrets"))
    (tmp_path / "empty").mkdir()
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))

    status, _, output = run(capsys, "provision", str(root), "--accept")

    assert status == 0
    assert "shellcheck is never downloaded here; install 0.9.0 or later from" in output
    assert "gitleaks is never downloaded here" in output and "pip" not in output


def test_provision_installs_no_tool_path_has_at_its_min_version_or_later(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """An externally managed python3 refuses pip, and needs no install of a tool PATH has."""

    root = repository(tmp_path, {"a.py": "x = 1\n", "run.sh": "echo\n"})
    install(
        root,
        *(shipped(name) for name in ("python.lint", "python.types", "secrets", "shell.lint")),
    )
    bin_dir = tmp_path / "tools"
    bin_dir.mkdir()
    versions = {"ruff": "ruff 0.16.7", "mypy": "mypy 2.3.0", "gitleaks": "8.30.1"}
    versions["shellcheck"] = "ShellCheck - shell script analysis tool\nversion: 0.11.0"
    for tool, text in {**versions, "python3": "Python 3.12.0"}.items():
        (bin_dir / tool).write_text(f"#!/bin/sh\nprintf '%s\\n' '{text}'\n", encoding="utf-8")
        (bin_dir / tool).chmod(0o755)
    monkeypatch.setenv("PATH", str(bin_dir))

    status, _, output = run(capsys, "provision", str(root))

    assert status == 0, output
    for tool, version in (("ruff", "0.16.7"), ("gitleaks", "8.21.2"), ("shellcheck", "0.9.0")):
        assert f"{tool} is on PATH at {version} or later ({bin_dir / tool}): present" in output
    assert "never downloaded" not in output
    assert f"would run: {bin_dir / 'python3'} -I -m pip install mypy==2.3.1" in output, output
    assert "ruff==" not in output


def test_provision_installs_into_the_python3_on_path(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The floor finds its tools on PATH, so they go into the environment PATH names, not into
    the one running the engine, which an installed tool keeps to itself."""

    root = repository(tmp_path, {"a.py": "x = 1\n"})
    install(root, shipped("python.lint"))
    bin_dir = tmp_path / "project-env" / "bin"
    bin_dir.mkdir(parents=True)
    python = bin_dir / "python3"
    python.write_text("#!/bin/sh\n", encoding="utf-8")
    python.chmod(0o755)
    monkeypatch.setenv("PATH", str(bin_dir))

    status, _, output = run(capsys, "provision", str(root))

    assert status == 0
    assert f"would run: {python} -I -m pip install ruff==" in output


def test_provision_runs_pip_isolated_so_a_pip_package_in_the_target_does_not_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """`python -m pip` runs with the target as its working directory, and puts that directory
    first on `sys.path`; `-I` drops it."""

    root = repository(tmp_path, {"a.py": "x = 1\n"})
    install(root, shipped("python.lint"))
    marker = tmp_path / "hostile-ran"
    (root / "pip").mkdir()
    (root / "pip" / "__main__.py").write_text(
        f"import pathlib\npathlib.Path({str(marker)!r}).write_text('ran')\n", encoding="utf-8"
    )
    bin_dir = tmp_path / "project-env" / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "python3").symlink_to(sys.executable)
    monkeypatch.setenv("PATH", str(bin_dir))
    seen: list[list[str]] = []

    def fake_execute(argv: list[str], *_: Any) -> tuple[int, bytes, bytes]:
        seen.append(argv)
        # The engine's own argv up to `install`, asked for a version in place of an install.
        done = subprocess.run([*argv[:4], "--version"], cwd=root, capture_output=True, check=False)
        return done.returncode, done.stdout, done.stderr

    monkeypatch.setattr(floor.validation, "_execute", fake_execute)

    run(capsys, "provision", str(root), "--accept")

    assert seen and seen[0][:4] == [str(bin_dir / "python3"), "-I", "-m", "pip"], seen
    assert not marker.exists()


# --- The adoption record: additive to floor.json, and what moving it loosens ---------------------

ADOPTED = {"commit": "a" * 40, "on": "2026-01-15"}
HELD = floor.BASELINE_DIR + "/shell.injection.baseline"


def floor_text(*claims: dict[str, Any], adopted: dict[str, Any] | None = None) -> str:
    document: dict[str, Any] = {"version": 1, "claims": list(claims)}
    if adopted is not None:
        document["adopted"] = adopted
    return json.dumps(document)


@pytest.mark.parametrize("where", ["a side branch", "nowhere"])
def test_an_adoption_commit_outside_heads_history_leaves_the_secrets_claim_unverified(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    where: str,
) -> None:
    """A rewritten history or a shallow clone: `<adoption>..HEAD` would not be the commits
    since adoption, so the scan does not run without --base."""

    tools = tmp_path / "tools"
    tools.mkdir()
    (tools / "gitleaks").write_text(CLEAN_GITLEAKS, encoding="utf-8")
    (tools / "gitleaks").chmod(0o755)
    monkeypatch.setenv("PATH", os.pathsep.join([str(tools), os.environ["PATH"]]))
    root = repository(tmp_path, {"app.py": "x = 1\n"})
    git(root, "checkout", "-q", "-b", "side")
    side = commit(root, "side", {"app.py": "x = 2\n"})
    git(root, "checkout", "-q", "main")
    adopted = {"commit": side if where == "a side branch" else "d" * 40, "on": "2026-01-15"}
    install(root, shipped("secrets"), adopted=adopted)

    status, verdicts, output = run(capsys, "check", str(root))

    assert (status, verdicts) == (1, {"secrets": "UNVERIFIED"}), output
    assert "is not in HEAD's history here; fetch it, or pass --base" in output
    assert run(capsys, "check", str(root), "--base", "HEAD")[1]["secrets"] == "PASS"


def test_the_adoption_record_round_trips_one_field_a_line() -> None:
    adopted = floor.Adoption("c" * 40, "2026-01-15", (("python.lint", 120), ("shell.lint", 3)))
    written = floor.Floor((floor.parse_claim(shipped("shell.injection")),), adopted)

    text = written.text().decode("utf-8")

    assert floor.parse_floor(json.loads(text)) == written
    assert '\n    "on": "2026-01-15",\n' in text and '\n      "python.lint": 120,\n' in text
    assert floor.parse_floor(json.loads(floor.Floor(written.claims).text())).adopted is None


@pytest.mark.parametrize(
    "adopted",
    [
        {"commit": "abc", "on": "2026-01-15"},
        {"commit": "c" * 40, "on": "2026-13-01"},
        {"commit": "c" * 40},
        {"commit": "c" * 40, "on": "2026-01-15", "by": "x"},
        {"commit": "c" * 40, "on": "2026-01-15", "recorded": {"python.lint": 0}},
        {"commit": "c" * 40, "on": "2026-01-15", "recorded": {"python.lint": True}},
        ["c" * 40, "2026-01-15"],
    ],
)
def test_an_adoption_record_that_cannot_be_read_whole_is_refused(adopted: object) -> None:
    with pytest.raises(floor.FloorError):
        floor.parse_floor({"version": 1, "adopted": adopted, "claims": []})


FLOOR_CHANGES = {
    "a baseline claim becomes a gate": (
        {floor.FLOOR_PATH: floor_text(shipped("shell.injection", mode="baseline"))},
        {floor.FLOOR_PATH: floor_text(shipped("shell.injection"))},
        "PASS",
    ),
    "a gate becomes a baseline claim": (
        {floor.FLOOR_PATH: floor_text(shipped("shell.injection"))},
        {floor.FLOOR_PATH: floor_text(shipped("shell.injection", mode="baseline"))},
        "FAIL",
    ),
    "a first floor arrives with its adoption record and its baselines": (
        {},
        {
            floor.FLOOR_PATH: floor_text(
                shipped("shell.injection", mode="baseline"), adopted=ADOPTED
            ),
            HELD: EVAL_KEY + "\n",
        },
        "PASS",
    ),
    "an adoption record appears where there was none": (
        {floor.FLOOR_PATH: floor_text(shipped("shell.injection"))},
        {floor.FLOOR_PATH: floor_text(shipped("shell.injection"), adopted=ADOPTED)},
        "PASS",
    ),
    "a claim left out comes back with its first baseline": (
        {floor.FLOOR_PATH: floor_text(shipped("shell.syntax"), adopted=ADOPTED)},
        {
            floor.FLOOR_PATH: floor_text(
                shipped("shell.syntax"),
                shipped("shell.injection", mode="baseline"),
                adopted=ADOPTED,
            ),
            HELD: EVAL_KEY + "\n",
        },
        "PASS",
    ),
    "a floor without an adoption record is fitted: its empty baseline gains a line": (
        {floor.FLOOR_PATH: floor_text(shipped("shell.injection", mode="baseline")), HELD: "\n"},
        {
            floor.FLOOR_PATH: floor_text(
                shipped("shell.injection", mode="baseline"), adopted=ADOPTED
            ),
            HELD: EVAL_KEY + "\n",
        },
        "FAIL",
    ),
    "an adoption record appears while a gate becomes a baseline claim": (
        {floor.FLOOR_PATH: floor_text(shipped("shell.injection"))},
        {
            floor.FLOOR_PATH: floor_text(
                shipped("shell.injection", mode="baseline"), adopted=ADOPTED
            ),
            HELD: EVAL_KEY + "\n",
        },
        "FAIL",
    ),
    "a baseline grows under an adoption record already there": (
        {
            floor.FLOOR_PATH: floor_text(
                shipped("shell.injection", mode="baseline"), adopted=ADOPTED
            ),
            HELD: "\n",
        },
        {HELD: EVAL_KEY + "\n"},
        "FAIL",
    ),
    "the adoption record moves": (
        {floor.FLOOR_PATH: floor_text(shipped("shell.injection"), adopted=ADOPTED)},
        {
            floor.FLOOR_PATH: floor_text(
                shipped("shell.injection"), adopted={**ADOPTED, "commit": "b" * 40}
            )
        },
        "FAIL",
    ),
    "the adoption record is removed": (
        {floor.FLOOR_PATH: floor_text(shipped("shell.injection"), adopted=ADOPTED)},
        {floor.FLOOR_PATH: floor_text(shipped("shell.injection"))},
        "FAIL",
    ),
    "a claim's timeout_seconds is set": (
        {floor.FLOOR_PATH: floor_text(shipped("shell.syntax"))},
        {floor.FLOOR_PATH: floor_text(shipped("shell.syntax", timeout_seconds=1800))},
        "PASS",
    ),
    "a claim is dropped after the last file it reads is deleted": (
        {floor.FLOOR_PATH: floor_text(shipped("shell.syntax"), shipped("shell.injection"))},
        {floor.FLOOR_PATH: floor_text(shipped("shell.injection")), "run.sh": ""},
        "FAIL",
    ),
    "a claim is dropped after its script is renamed out of its pattern": (
        {floor.FLOOR_PATH: floor_text(shipped("shell.syntax"), shipped("shell.injection"))},
        {
            floor.FLOOR_PATH: floor_text(shipped("shell.injection")),
            "run.sh": "",
            "run": "echo ok\n",
        },
        "FAIL",
    ),
    "a renamed file carries its baselined finding, an earlier floor's line included": (
        {
            floor.FLOOR_PATH: floor_text(shipped("shell.injection", mode="baseline")),
            "run.sh": EVAL,
            HELD: "run.sh:eval:`eval` executes text as code\n",
        },
        {"run.sh": "", "bin/run.sh": EVAL, HELD: "bin/run.sh:eval\n"},
        "PASS",
    ),
    "a renamed file's baseline line comes back with another code": (
        {
            floor.FLOOR_PATH: floor_text(shipped("shell.injection", mode="baseline")),
            "run.sh": EVAL,
            HELD: "run.sh:eval\n",
        },
        {"run.sh": "", "bin/run.sh": EVAL, HELD: "bin/run.sh:pipe-to-shell\n"},
        "FAIL",
    ),
    "a new file's finding joins the baseline": (
        {
            floor.FLOOR_PATH: floor_text(shipped("shell.injection", mode="baseline")),
            "run.sh": EVAL,
            HELD: "run.sh:eval\n",
        },
        {"other.sh": "#!/bin/sh\n" + EVAL, HELD: "other.sh:eval\nrun.sh:eval\n"},
        "FAIL",
    ),
}


@pytest.mark.parametrize(
    ("before", "after", "verdict"), FLOOR_CHANGES.values(), ids=FLOOR_CHANGES.keys()
)
def test_what_an_adoption_record_or_a_mode_change_loosens(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    before: dict[str, str],
    after: dict[str, str],
    verdict: str,
) -> None:
    root = repository(tmp_path, {"run.sh": "echo ok\n", **before})
    base = git(root, "rev-parse", "HEAD")
    commit(root, "change", after)

    output = run(capsys, "check", str(root), "--base", base)[2]

    assert f"{verdict} loosening" in output, output


# --- No limit the project did not set: time, output, a container prefix -------------------


def test_no_tool_probe_or_git_read_has_a_time_limit_unless_the_claim_sets_one(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PATH", os.pathsep.join([str(probe(tmp_path)), os.environ["PATH"]]))
    root = repository(tmp_path, {"a.txt": "x\n"})
    install(root, probe_claim(min_version="1.2"))
    base = commit(root, "floor", {})
    seen: list[float | None] = []
    real: Any = floor.validation._execute

    def spy(argv: list[str], cwd: Path, seconds: float | None, env: Any = None) -> Any:
        seen.append(seconds)
        return real(argv, cwd, seconds, env)

    monkeypatch.setattr(floor.validation, "_execute", spy)

    status, verdicts, output = run(capsys, "check", str(root), "--base", base)

    assert (status, verdicts) == (0, {"project.probe": "PASS", "loosening": "PASS"}), output
    assert len(seen) > 3 and set(seen) == {None}, seen


def test_a_claim_that_runs_past_its_own_timeout_seconds_is_unverified(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    tools = tmp_path / "tools"
    tools.mkdir()
    (tools / "floor-slow").write_text("#!/bin/sh\nsleep 5\n", encoding="utf-8")
    (tools / "floor-slow").chmod(0o755)
    monkeypatch.setenv("PATH", os.pathsep.join([str(tools), os.environ["PATH"]]))
    root = repository(tmp_path, {"a.txt": "x\n"})
    slow = {"tool": "floor-slow", "argv": ["floor-slow"], "timeout_seconds": 0.2}
    install(root, probe_claim(**slow))

    status, verdicts, output = run(capsys, "check", str(root))

    assert (status, verdicts) == (1, {"project.probe": "UNVERIFIED"}), output
    assert "floor-slow did not finish in its timeout_seconds, 0.2" in output


def test_every_new_finding_is_printed() -> None:
    gate = floor.parse_claim(shipped("shell.injection"))
    held = floor.parse_claim(shipped("shell.injection", mode="baseline"))
    findings = [
        floor.Finding(f"s{n}.sh", "eval", "`eval` executes text as code") for n in range(45)
    ]

    assert len(floor.judge(gate, findings, Counter(), 45).details) == 45
    listed = floor.judge(held, findings, Counter(), 45).details
    assert sum(line.startswith("+1 ") for line in listed) == 45
    assert not any("more" in line for line in listed)


@pytest.mark.parametrize(
    ("line", "key"),
    [
        ("a:b:c.py:E501", "a:b:c.py:E501"),
        ("src/a.py:F401", "src/a.py:F401"),
        ("src/a.py:F401:`os` imported but unused", "src/a.py:F401"),
        ("src/x.py:misc:Bad: very bad", "src/x.py:misc"),
    ],
)
def test_a_baseline_line_reads_its_code_as_the_last_field_or_an_earlier_floors_message(
    line: str, key: str
) -> None:
    assert floor._key(line) == key


def test_a_path_with_colons_matches_its_baseline_line() -> None:
    claim = floor.parse_claim(shipped("python.lint"))
    finding = floor.Finding("a:b:c.py", "E501", "Line too long")

    outcome = floor.judge(claim, [finding], floor._lines(finding.key + "\n"), None)

    assert outcome.status == "PASS", outcome


def test_a_baselined_finding_stays_baselined_when_the_tool_rewords_its_message() -> None:
    claim = floor.parse_claim(shipped("python.lint"))
    held = floor._lines("src/a.py:F401:`os` imported but unused\n")

    outcome = floor.judge(claim, [floor.Finding("src/a.py", "F401", "`os` is unused")], held, None)

    assert (outcome.status, outcome.summary) == ("PASS", "0 new, 1 baselined")


# --- The range starts where the floor began ---------------------------------------------------


def adopted_on_the_branch(tmp_path: Path, floor_at_fork: bool) -> tuple[Path, str, str]:
    """A fork, a commit that adds a noqa, then a floor adopted at that commit: the repository,
    the fork and the adoption commit. With `floor_at_fork`, the fork already holds a floor
    without an adoption record."""

    root = repository(tmp_path, BEFORE)
    if floor_at_fork:
        install(root, shipped("shell.injection"))
    fork = commit(root, "fork", {})
    adopted = commit(root, "before the floor", LOOSENINGS["a noqa is added"])
    record = {"commit": adopted, "on": "2026-01-15"}
    commit(
        root, "adopt", {floor.FLOOR_PATH: floor_text(shipped("shell.injection"), adopted=record)}
    )
    commit(root, "work", {"src/c.py": "z = 3\n"})
    return root, fork, adopted


def test_commits_from_before_the_floor_was_adopted_never_fail_the_loosening_check(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root, fork, adopted = adopted_on_the_branch(tmp_path, floor_at_fork=False)

    status, verdicts, output = run(capsys, "check", str(root), "--base", fork)

    assert (status, verdicts["loosening"]) == (0, "PASS"), output
    assert f"none in {adopted[:12]}..HEAD, the commits since the floor's adoption" in output

    commit(root, "widen", {"src/d.py": SPACED + comment("noqa: E501") + "\n"})
    assert run(capsys, "check", str(root), "--base", fork)[1]["loosening"] == "FAIL"


def test_an_adoption_record_added_to_a_floor_the_fork_holds_does_not_move_the_range(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Otherwise a loosening, then a record naming its commit, would hide the loosening."""

    root, fork, _ = adopted_on_the_branch(tmp_path, floor_at_fork=True)

    status, verdicts, output = run(capsys, "check", str(root), "--base", fork)

    assert (status, verdicts["loosening"]) == (1, "FAIL"), output
    assert "src/b.py adds" in output


RECORDING_GITLEAKS = """#!/bin/sh
[ "$1" = version ] && { echo 8.21.2; exit 0; }
here=$(dirname "$0")
echo "$@" >> "$here/argv"
find . -type f | sort > "$here/listing"
while [ $# -gt 0 ]; do [ "$1" = --report-path ] && report=$2; shift; done
printf '[]' > "$report"
exit 0
"""


def recording_gitleaks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    tools = tmp_path / "tools"
    tools.mkdir()
    (tools / "gitleaks").write_text(RECORDING_GITLEAKS, encoding="utf-8")
    (tools / "gitleaks").chmod(0o755)
    monkeypatch.setenv("PATH", os.pathsep.join([str(tools), os.environ["PATH"]]))
    return tools


def test_the_secrets_range_starts_at_the_adoption_when_the_floor_was_adopted_on_the_branch(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    tools = recording_gitleaks(tmp_path, monkeypatch)
    root = repository(tmp_path, {"app.py": "x = 1\n"})
    fork = commit(root, "fork", {})
    adopted = commit(root, "before the floor", {"app.py": "x = 2\n"})
    record = {"commit": adopted, "on": "2026-01-15"}
    commit(root, "adopt", {floor.FLOOR_PATH: floor_text(shipped("secrets"), adopted=record)})

    verdicts = run(capsys, "check", str(root), "--base", fork)[1]

    assert verdicts == {"secrets": "PASS", "loosening": "PASS"}
    runs = [line.split() for line in (tools / "argv").read_text(encoding="utf-8").splitlines()]
    assert [words[:2] for words in runs] == [
        ["git", f"--log-opts={adopted}..HEAD"],
        ["dir", "--redact"],
    ]
    listing = (tools / "listing").read_text(encoding="utf-8").split()
    assert listing == ["./.outcomebound/floor.json", "./app.py"]


def test_a_secret_committed_before_an_adoption_on_the_branch_still_fails_the_secrets_claim(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The range skips the commits before the adoption, but the secret is still in the tree."""

    on_path(monkeypatch, "gitleaks")
    root = repository(tmp_path, {"README": "x\n"})
    fork = git(root, "rev-parse", "HEAD")
    adopted = commit(root, "a secret before the floor", {"app.py": f'aws = "{OLD_LEAK}"\n'})
    record = {"commit": adopted, "on": "2026-01-15"}
    commit(root, "adopt", {floor.FLOOR_PATH: floor_text(shipped("secrets"), adopted=record)})

    status, verdicts, output = run(capsys, "check", str(root), "--base", fork)

    assert (status, verdicts["secrets"]) == (1, "FAIL"), output
    assert "app.py:1: aws-access-token" in output and OLD_LEAK not in output


def test_a_floor_removed_and_adopted_again_does_not_move_the_range_past_a_loosening(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Re-adopting at the commit that deleted the floor would otherwise hide the noqa added
    while the first floor held."""

    root = repository(tmp_path, BEFORE)
    fork = git(root, "rev-parse", "HEAD")
    first = commit(root, "work", {"src/c.py": "z = 3\n"})
    claims = shipped("shell.injection")
    commit(
        root,
        "adopt",
        {floor.FLOOR_PATH: floor_text(claims, adopted={"commit": first, "on": "2026-01-15"})},
    )
    commit(root, "widen", LOOSENINGS["a noqa is added"])
    deleted = commit(root, "remove the floor", {floor.FLOOR_PATH: ""})
    commit(
        root,
        "adopt again",
        {floor.FLOOR_PATH: floor_text(claims, adopted={"commit": deleted, "on": "2026-01-16"})},
    )

    status, verdicts, output = run(capsys, "check", str(root), "--base", fork)

    assert (status, verdicts["loosening"]) == (1, "FAIL"), output
    assert "src/b.py adds" in output


def test_secrets_without_a_base_or_an_adoption_read_only_the_files_git_tracks(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """gitleaks scans a directory whole, so it runs where only tracked files are: an ignored
    environment or secrets file is never read. Its own allowlist comes along, tracked or not."""

    tools = recording_gitleaks(tmp_path, monkeypatch)
    root = repository(tmp_path, {"app.py": "x = 1\n", ".gitignore": ".venv/\n.env\n"})
    (root / ".venv").mkdir()
    (root / ".venv" / "lib.py").write_text("token = 1\n", encoding="utf-8")
    (root / ".env").write_text("token = 1\n", encoding="utf-8")
    (root / ".gitleaksignore").write_text("app.py:generic-api-key:1\n", encoding="utf-8")
    install(root, shipped("secrets"))

    verdicts = run(capsys, "check", str(root), "--claim", "secrets")[1]

    assert verdicts == {"secrets": "PASS"}
    listing = (tools / "listing").read_text(encoding="utf-8").split()
    assert listing == ["./.gitignore", "./.gitleaksignore", "./app.py"]


def test_the_tracked_files_scan_never_follows_a_symlinked_folder_out_of_the_root(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    tools = recording_gitleaks(tmp_path, monkeypatch)
    root = repository(tmp_path, {"app.py": "x = 1\n", "dir/file.txt": "inside\n"})
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "file.txt").write_text("outside\n", encoding="utf-8")
    shutil.rmtree(root / "dir")
    (root / "dir").symlink_to(outside, target_is_directory=True)
    install(root, shipped("secrets"))

    assert run(capsys, "check", str(root), "--claim", "secrets")[1] == {"secrets": "PASS"}
    assert (tools / "listing").read_text(encoding="utf-8").split() == ["./app.py"]


# --- A claim's tool may run through a prefix: a container, uv run, poetry run ---------------

WRAP = """#!/bin/sh
echo "$@" >> "$(dirname "$0")/wrapped"
shift
PATH="{inside}:$PATH" exec "$@"
"""


def wrapped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """`floor-wrap BOX TOOL ...` runs TOOL where only it can find it, as a container would:
    `floor-probe` is in a directory PATH does not name."""

    inside = probe(tmp_path / "box")
    tools = tmp_path / "host"
    tools.mkdir()
    (tools / "floor-wrap").write_text(WRAP.format(inside=inside), encoding="utf-8")
    (tools / "floor-wrap").chmod(0o755)
    monkeypatch.setenv("PATH", os.pathsep.join([str(tools), os.environ["PATH"]]))
    return tools


def test_a_prefixed_claim_asks_its_version_and_runs_its_tool_through_the_prefix(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "box").mkdir()
    tools = wrapped(tmp_path, monkeypatch)
    root = repository(tmp_path, {"a.txt": "x\n"})
    install(root, probe_claim(prefix=["floor-wrap", "app"], min_version="1.2"))

    status, verdicts, output = run(capsys, "check", str(root))

    assert (status, verdicts) == (0, {"project.probe": "PASS"}), output
    calls = (tools / "wrapped").read_text(encoding="utf-8").splitlines()
    assert calls == ["app floor-probe --version", "app floor-probe"]


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        ({"prefix": ["floor-absent", "app"]}, "floor-absent is not on PATH"),
        (
            {"prefix": ["floor-wrap", "app"], "tool": "floor-gone", "argv": ["floor-gone"]},
            "floor-gone did not report a version through floor-wrap app",
        ),
        (
            {"prefix": ["floor-wrap", "app"], "min_version": "1.10"},
            "floor-probe through floor-wrap app is 1.2, older than 1.10",
        ),
    ],
)
def test_a_prefixed_claim_whose_prefix_or_tool_is_missing_or_old_is_unverified(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    changes: dict[str, Any],
    reason: str,
) -> None:
    (tmp_path / "box").mkdir()
    wrapped(tmp_path, monkeypatch)
    root = repository(tmp_path, {"a.txt": "x\n"})
    install(root, probe_claim(**{"min_version": "1.2", **changes}))

    status, verdicts, output = run(capsys, "check", str(root))

    assert (status, verdicts) == (1, {"project.probe": "UNVERIFIED"}), output
    assert reason in output


def test_provision_says_a_prefixed_tool_is_installed_where_its_prefix_runs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = repository(tmp_path, {"a.py": "x = 1\n"})
    install(root, shipped("python.types", prefix=["docker", "compose", "run", "--rm", "app"]))

    status, _, output = run(capsys, "provision", str(root))

    assert status == 0
    assert "mypy runs through docker compose run --rm app: install it there" in output
    assert "pip" not in output


# --- What a project's install and its sandbox need from the floor ---------------------------


@pytest.mark.parametrize("adopted", [False, True])
def test_apply_and_remove_name_the_adopt_step_where_outcomebound_is_installed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], adopted: bool
) -> None:
    """The project facts name a floor loosening as an edge only while a floor is installed."""

    manifest = {floor.MANIFEST: "{}\n"} if adopted else {}
    root = repository(tmp_path, {"run.sh": "echo\n", **manifest})
    source = proposal(tmp_path, shipped("shell.injection"))
    step = f"next: outcomebound adopt {root}\n  the floor is"

    first = run(capsys, "apply", str(root), "--floor", str(source), "--accept")[2]
    again = run(capsys, "apply", str(root), "--floor", str(source), "--accept")[2]
    removed = run(capsys, "remove", str(root), "--accept")[2]

    assert (f"{step} installed" in first, f"{step} removed" in removed) == (adopted, adopted)
    assert "next:" not in again


def test_a_tree_that_cannot_be_written_gets_ruff_and_mypy_caches_in_a_scratch_folder(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    root = repository(tmp_path, {"README": "x\n"})
    seen = tmp_path / "seen"
    tools = tmp_path / "tools"
    tools.mkdir()
    for tool, variable in floor.CACHES.items():
        script = f'#!/bin/sh\nprintf "%s\\n" "${variable}" >> "{seen}"\n'
        (tools / tool).write_text(script, encoding="utf-8")
        (tools / tool).chmod(0o755)
        monkeypatch.delenv(variable, raising=False)
    claims = [
        {"name": f"project.{tool}", "mode": "gate", "tool": tool, "argv": [tool], "parser": "exit"}
        for tool in floor.CACHES
    ]
    install(root, *claims)
    monkeypatch.setenv("PATH", os.pathsep.join([str(tools), os.environ["PATH"]]))
    passed = (0, {"project.ruff": "PASS", "project.mypy": "PASS"})

    assert run(capsys, "check", str(root))[:2] == passed
    assert seen.read_text(encoding="utf-8") == "\n\n"
    seen.unlink()
    root.chmod(0o555)
    try:
        if floor._writable(root):
            pytest.skip("UNVERIFIED: this user can write a folder whose mode forbids it")
        assert run(capsys, "check", str(root))[:2] == passed
    finally:
        root.chmod(0o755)
    caches = seen.read_text(encoding="utf-8").split()
    assert len(caches) == 2 and all(root not in Path(c).parents for c in caches), caches
    assert not any(Path(cache).exists() for cache in caches)
