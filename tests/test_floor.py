"""`outcomebound floor`: the quality floor, run against scratch Git repositories."""

from __future__ import annotations

import datetime
import json
import os
import shutil
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
    assert "src/app/__init__.py:arg-type:" in output


# --- Baselines: a multiset of keys, tightened by deletion only ------------------------------

EVAL = 'eval "$1"\n'
EVAL_KEY = "run.sh:eval:`eval` executes text as code"


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
    findings = [floor.Finding("x.sh", "eval", key) for key in found]
    baseline = Counter(floor.Finding("x.sh", "eval", key).key for key in held)

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
    assert f"+1 {EVAL_KEY}" in output


def test_ratchet_deletes_the_lines_no_finding_matches_and_adds_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    held = [EVAL_KEY, EVAL_KEY, "gone.sh:eval:`eval` executes text as code"]
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
    install(root, shipped("python.secrets"))
    base = commit(root, "floor", {})
    (root / "local.env").write_text("untracked\n", encoding="utf-8")

    status, verdicts, output = run(capsys, "check", str(root), "--claim", "python.secrets")
    scanned = (tools / "argv").read_text(encoding="utf-8").split()

    assert (status, verdicts) == (1, {"python.secrets": "FAIL"}), output
    assert scanned[0] == "dir" and "--redact" in scanned
    assert "app.py:3: generic-api-key" in output and "local.env" not in output
    assert "s3cr3t" not in output

    status, _, output = run(capsys, "check", str(root), "--claim", "python.secrets", "--base", base)
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
    install(root, shipped("python.secrets"))
    base = commit(root, "floor", {})
    commit(root, "work", {"app.py": "x = 2\n"})

    for extra in ((), ("--base", base)):
        status, verdicts, output = run(
            capsys, "check", str(root), "--claim", "python.secrets", *extra
        )

        assert (status, verdicts.get("python.secrets")) == (0, "PASS"), output


def test_the_shipped_secrets_claim_keeps_redact_in_both_of_its_argvs() -> None:
    """Both argvs, with a base and without one, carry gitleaks' own `--redact`, so gitleaks
    itself redacts the secret in what it reports."""

    claim = shipped("python.secrets")

    assert "--redact" in claim["argv"] and "--redact" in claim["argv_without_base"]


# --- The loosening check: `check --base` over the merge base with the ref and HEAD ----------


def comment(text: str) -> str:
    """A `#` comment. The suppression markers are never spelled whole in this file, so the
    loosening check does not read the tests that hold it as loosenings."""

    return "# " + text


SPACED = 'x = "a"  '
LINT_BASELINE = floor.BASELINE_DIR + "/python.lint.baseline"
BEFORE = {
    "run.sh": "#!/bin/sh\necho ok\n",
    "ruff.toml": "line-length = 100\n",
    "mypy.ini": "[mypy]\nfiles = src\n",
    ".gitleaks.toml": 'title = "project"\n',
    "pyproject.toml": '[project]\nname = "p"\n\n[tool.ruff]\nline-length = 100\n',
    "setup.cfg": "[metadata]\nname = p\n\n[mypy]\nstrict = True\n",
    "src/app.py": "import os  " + comment("noqa: F401") + "\n",
    LINT_BASELINE: "src/a.py:F401:one\nsrc/a.py:F841:two\n",
}


LOOSENINGS = {
    "a baseline gains a line": {
        LINT_BASELINE: "src/a.py:F401:one\nsrc/a.py:F401:one\nsrc/a.py:F841:two\n"
    },
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
    "a baseline loses a line": {LINT_BASELINE: "src/a.py:F841:two\n"},
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
            floor.BASELINE_DIR + "/python.types.baseline": "src/a.py:misc:one\n",
        },
    )

    output = run(capsys, "check", str(root), "--base", base)[2]

    assert "PASS loosening" in output and "PASS project.own" in output, output


@pytest.mark.parametrize(
    ("messages", "passes"),
    [
        (("widen\n\nFloor-Loosening: a long line in b.py; ruled D12",), True),
        (("widen\n\nFloor-Loosening: drop E501; keep E502; ruled D12",), True),
        (("Floor-Loosening: allow long lines; ruled D12\n\nSigned-off-by: x", "widen"), True),
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
    assert (ruling[:12] in output) == passes


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
        ({"lib/a.py": "x = 1\n"}, ("python",)),
        ({"pyproject.toml": "[project]\n"}, ("python",)),
        ({"bin/run.sh": "echo\n"}, ("shell",)),
        ({"a.py": "x = 1\n", "run.sh": "echo\n"}, ("python", "shell")),
        ({"README": "x\n"}, ()),
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


def test_ruff_json_keys_carry_no_position_and_no_count(tmp_path: Path) -> None:
    root = tmp_path.resolve()

    findings = floor.parse_ruff(
        1, "warning: a notice ruff printed first\n" + fixture("ruff-check.json", root), root
    )

    assert [finding.key for finding in findings] == [
        "pkg/core.py:F401:`os` imported but unused",
        "pkg/core.py:F401:`sys` imported but unused",
        "pkg/core.py:C901:`pick` is too complex",
        "pkg/core.py:F811:Redefinition of unused `pick` from line N: `pick` redefined here",
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

    assert [finding.key for finding in findings] == [
        "pkg/style.py:unformatted:the formatter would rewrite this file"
    ]
    assert floor.parse_ruff_format(0, fixture("ruff-format-clean.txt"), tmp_path) == []
    with pytest.raises(floor.Unreadable):
        floor.parse_ruff_format(2, "error: Failed to parse pkg/x.py", tmp_path)


def test_mypy_keys_count_errors_not_notes(tmp_path: Path) -> None:
    findings = floor.parse_mypy(1, fixture("mypy.jsonl"), tmp_path)

    assert [finding.key for finding in findings] == [
        'pkg/core.py:no-redef:Name "pick" already defined on line N',
        'pkg/core.py:arg-type:Argument 2 to "pick" has incompatible type "str"; expected "int"',
        'pkg/core.py:assignment:Incompatible types in assignment (expression has type "str", '
        'variable has type "int")',
        'pkg/notes.py:import-untyped:Library stubs not installed for "yaml"',
    ]
    assert floor.parse_mypy(0, "\n", tmp_path) == []
    for status, text in ((2, fixture("mypy.jsonl")), (1, "\n"), (2, "mypy: error: bad config")):
        with pytest.raises(floor.Unreadable):
            floor.parse_mypy(status, text, tmp_path)


def test_bash_n_reads_the_first_message_of_a_broken_script() -> None:
    findings = floor.parse_per_file("bash-n", 2, fixture("bash-n.txt"), "scripts/broken.sh")

    assert [(finding.key, finding.where) for finding in findings] == [
        ("scripts/broken.sh:syntax:syntax error near unexpected token `fi'", "4")
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


def test_shellcheck_keys_carry_its_code_and_message_not_the_position() -> None:
    findings = floor.parse_per_file("shellcheck", 1, fixture("shellcheck.json"), "scripts/lint.sh")

    quote = "Double quote to prevent globbing and word splitting."
    assert [(finding.key, finding.where) for finding in findings] == [
        (f"scripts/lint.sh:SC2086:{quote}", "2:6"),
        ("scripts/lint.sh:SC2045:Iterating over ls output is fragile. Use globs.", "3:10"),
        (
            "scripts/lint.sh:SC2035:Use ./*glob* or -- *glob* so names with dashes won't become"
            " options.",
            "3:15",
        ),
        (f"scripts/lint.sh:SC2086:{quote}", "4:7"),
        ("scripts/lint.sh:SC2162:read without -r will mangle backslashes.", "6:1"),
        (
            "scripts/lint.sh:SC2034:name appears unused. Verify use (or export if used"
            " externally).",
            "6:6",
        ),
    ]
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
    assert "+1 a.py:F401:`os` imported but unused" in output

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
        assert "+1 run.sh:pipe-to-shell:" in output
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


def test_apply_leaves_out_a_claim_whose_tool_cannot_read_the_project_and_says_why(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = repository(tmp_path, {"run.sh": EVAL})
    nothing = {**shipped("shell.syntax", files=["*.bash"]), "name": "shell.other"}
    source = proposal(tmp_path, shipped("shell.injection"), nothing)

    status, _, output = run(capsys, "apply", str(root), "--floor", str(source), "--accept")

    assert status == 0, output
    assert modes(root) == {"shell.injection": "baseline"}
    assert "shell.other: left out (no tracked file matches *.bash); once that is fixed" in output
    assert f"apply {source} again" in output
    assert run(capsys, "check", str(root))[:2] == (0, {"shell.injection": "PASS"})


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
    source = proposal(tmp_path, shipped("python.secrets"))

    status, _, output = run(capsys, "apply", str(root), "--floor", str(source), "--accept")

    assert status == 0, output
    assert "  app.py:aws-access-token:1" in output.splitlines(), output
    assert OLD_LEAK not in output
    assert modes(root) == {"python.secrets": "gate"}
    assert "recorded" not in installed(root)["adopted"]
    assert not (root / floor.BASELINE_DIR).exists()
    status, verdicts, output = run(capsys, "check", str(root))
    assert (status, verdicts) == (0, {"python.secrets": "PASS"}), output
    assert "in the commits since adoption on" in output

    base = commit(root, "adopt the floor", {})
    commit(root, "deploy", {"deploy.py": f'aws = "{NEW_LEAK}"\n'})
    for extra in ((), ("--base", base)):
        status, verdicts, output = run(capsys, "check", str(root), *extra)

        assert (status, verdicts["python.secrets"]) == (1, "FAIL"), output
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
    source = proposal(tmp_path, shipped("python.secrets"))
    output = run(capsys, "apply", str(root), "--floor", str(source), "--strict", "--accept")[2]
    line = next(text.strip() for text in output.splitlines() if "aws-access-token" in text)

    for allowed, verdict in ((False, "FAIL"), (True, "PASS")):
        if allowed:
            (root / ".gitleaksignore").write_text(line + "\n", encoding="utf-8")
        for extra in ((), ("--base", base)):
            verdicts = run(capsys, "check", str(root), "--claim", "python.secrets", *extra)[1]

            assert verdicts["python.secrets"] == verdict, (line, extra)


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
    assert "+1 a.py:F401:`sys` imported but unused" in output
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
    assert "+1 run.sh:SC2086:Double quote to prevent globbing" in output


def test_provision_prints_shellchecks_install_command_and_downloads_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = repository(tmp_path, {"run.sh": "echo\n"})
    install(root, shipped("shell.lint"), shipped("python.secrets"))

    status, _, output = run(capsys, "provision", str(root), "--accept")

    assert status == 0
    assert "shellcheck is never downloaded here; install 0.9.0 or later from" in output
    assert "gitleaks is never downloaded here" in output and "pip" not in output


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
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")

    status, _, output = run(capsys, "provision", str(root))

    assert status == 0
    assert f"would run: {python} -m pip install ruff==" in output


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
    install(root, shipped("python.secrets"), adopted=adopted)

    status, verdicts, output = run(capsys, "check", str(root))

    assert (status, verdicts) == (1, {"python.secrets": "UNVERIFIED"}), output
    assert "is not in HEAD's history here; fetch it, or pass --base" in output
    assert run(capsys, "check", str(root), "--base", "HEAD")[1]["python.secrets"] == "PASS"


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
