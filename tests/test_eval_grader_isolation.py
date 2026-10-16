"""No model under test can read its grader: no grader is in the workspace, or in its Git history,
while the call runs.

Each fixture is built once through the runner's own `run_fixture`, under one arm, with a stand-in
harness whose `call` records the workspace as the model finds it. The post-checks then run from
the sealed copy of the graders, as in a real run. No test here calls a model.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, cast

import pytest

from evals.harnesses import CallResult, Request
from tests.eval_helpers import FIXTURES, HERMETIC_GIT, ROOT, RUN, transcript
from tests.portable import needs_posix_bash

pytestmark = needs_posix_bash

# The arm a fixture runs under where it is not `current`: this kit is pasted into a plain
# assistant, so the kernel-off arm is the only one it runs in.
ARM = {"business-requirements-kit": "none"}
CONTROL = "small-fix"
GIT_ENV = {**os.environ, **HERMETIC_GIT}
# The shell form a plan uses to name a file of the sealed copy.
ALLOWED = re.compile(
    r"\$\{OUTCOMEBOUND_GRADER_DIR:\?[^}]*\}/checks/|\$OUTCOMEBOUND_GRADER_DIR/checks/"
)
BARE = re.compile(r"(?<![\w.-])checks/")
FIX_THE_DATE = """cat > datehelp.py <<'PY'
import datetime


def previous_day(year, month, day):
    previous = datetime.date(year, month, day) - datetime.timedelta(days=1)
    return (previous.year, previous.month, previous.day)
PY
"""
REPORTED = "- PASS: `python3 -B test_datehelp.py`\n- UNVERIFIED: `datelint`, the lint is absent\n"
COMMANDS = ("python3 -B test_datehelp.py", "datelint datehelp.py")


# --- what a model finds in the workspace ---------------------------------------------------


def _git(workdir: Path, *arguments: str) -> str:
    done = subprocess.run(
        ["git", *arguments], cwd=workdir, capture_output=True, text=True, env=GIT_ENV
    )
    return done.stdout if done.returncode == 0 else ""


def _files(root: Path) -> dict[str, bytes]:
    """Each file under `root`, by relative path, `.git` and bytecode folders left out."""

    found = {}
    for folder, names, files in os.walk(root):
        names[:] = [name for name in names if name not in (".git", "__pycache__")]
        for name in files:
            path = Path(folder) / name
            if path.is_file() and not path.is_symlink():
                found[path.relative_to(root).as_posix()] = path.read_bytes()
    return found


def _facts(workdir: Path, stage: Path | None) -> dict[str, Any]:
    """What a model can read in its workspace, and the stage as it stands, at this moment."""

    listed = _git(workdir, "cat-file", "--batch-all-objects", "--batch-check")
    return {
        "files": _files(workdir),
        "blobs": {line.split()[0] for line in listed.splitlines() if line.split()[1:2] == ["blob"]},
        "history": set(_git(workdir, "log", "--all", "--name-only", "--pretty=format:").split()),
        "stage": _files(stage) if stage is not None and stage.is_dir() else {},
        "stage_mode": stat.S_IMODE(stage.stat().st_mode) if stage and stage.is_dir() else None,
    }


def _blob_id(data: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(data) + data, usedforsecurity=False).hexdigest()


# What is a grader beside the stage and `evals/graders`: the files of a fixture folder that a
# plan or a close runs to judge a run. A fixture folder also holds what its setup plants for the
# model to read (a sample, a design), which is not a grader.
GRADER_NAMES = (
    "accept*",
    "grade*",
    "probe*",
    "support*.py",
    "export.py",
    "case.py",
    "post.plan.json",
    "protected.paths",
)


def _graders(facts: dict[str, Any]) -> dict[str, bytes]:
    """The grader files, by label: the stage, `evals/graders`, the `checks/` folders of the
    fixtures and the fixtures' files named as graders. Empty files are left out, since an empty
    file in a workspace is not a copy of a grader."""

    evals = FIXTURES.parent
    found = {f"stage/{path}": data for path, data in facts["stage"].items()}
    paths = [path for path in (evals / "graders").rglob("*") if path.is_file()]
    paths.extend(
        path
        for path in FIXTURES.rglob("*")
        if path.is_file()
        and (
            "checks" in path.relative_to(FIXTURES).parts
            or any(path.match(pattern) for pattern in GRADER_NAMES)
        )
    )
    for path in paths:
        if "__pycache__" not in path.parts:
            found[path.relative_to(evals).as_posix()] = path.read_bytes()
    return {label: data for label, data in found.items() if data}


def _leaks(facts: dict[str, Any]) -> list[str]:
    """Where the workspace holds a grader: a file with its bytes, a Git blob with its bytes, or
    a path under `checks/` in the tree or the history."""

    graders = _graders(facts)
    by_hash = {hashlib.sha256(data).hexdigest(): label for label, data in graders.items()}
    by_blob = {_blob_id(data): label for label, data in graders.items()}
    found = [
        f"file {path} is {by_hash[hashlib.sha256(data).hexdigest()]}"
        for path, data in sorted(facts["files"].items())
        if hashlib.sha256(data).hexdigest() in by_hash
    ]
    found += [
        f"blob is {label}" for blob, label in sorted(by_blob.items()) if blob in facts["blobs"]
    ]
    paths = {*facts["files"], *facts["history"]}
    return found + [f"path {path}" for path in sorted(paths) if path.startswith("checks/")]


# --- the stand-in harness ------------------------------------------------------------------


class Stand:
    """A harness whose `call` records the workspace and the stage as the model finds them, may
    act in the workspace, and gives an answer with no identity."""

    name = "codex"

    def __init__(self, stages: list[Path], act: Callable[[Path, Path], None] | None = None):
        self.stages, self.act = stages, act
        self.facts: dict[str, Any] | None = None

    def call(self, _prompt, _request, cwd, _roots, _path, _keep):
        stage = self.stages[-1] if self.stages else None
        self.facts = _facts(cwd, stage)
        if self.act and stage is not None:
            self.act(cwd, stage)
        return CallResult(REPORTED, transcript(cwd, *COMMANDS), 0, None, {}, "", [])


def _watch(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    """The stages the runner makes, in order, each as it is made."""

    stages: list[Path] = []
    made = getattr(RUN, "new_stage", None)
    if made is not None:

        def recording(*arguments, **keywords):
            stages.append(made(*arguments, **keywords))
            return stages[-1]

        monkeypatch.setattr(RUN, "new_stage", recording)
    return stages


def _arm(name: str, arm: str):
    return RUN.fixture_arm(name, RUN.load_arm(arm, RUN.selected_fragments(name)))


def _run(base: Path, name: str, arm: str, harness: Stand) -> tuple[Any, Path]:
    workspace = base / f"{name}-{arm}"
    place = RUN.Place(workspace=workspace)
    path = RUN.child_env().get("PATH", os.defpath)
    result = RUN.run_fixture(name, Request("m", "medium"), _arm(name, arm), path, harness, place)
    return result, workspace


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Callable[..., dict[str, Any]]]:
    """Each fixture as the runner builds and grades it, once per arm, on first use: the facts the
    call saw, the run's record and where its workspace and sealed copy are."""

    kept: dict[tuple[str, str], dict[str, Any]] = {}
    base = tmp_path_factory.mktemp("isolation")
    patches = pytest.MonkeyPatch()

    def build(name: str, arm: str | None = None) -> dict[str, Any]:
        arm = arm or ARM.get(name, "current")
        if (name, arm) not in kept:
            stages = _watch(patches)
            harness = Stand(stages)
            (_answer, report, _code, extra), workspace = _run(base, name, arm, harness)
            patches.undo()
            kept[(name, arm)] = {
                "facts": harness.facts,
                "extra": extra,
                "report": report,
                "workspace": workspace,
                "stage": stages[-1] if stages else None,
            }
        return kept[(name, arm)]

    yield build
    patches.undo()


# --- no grader in the workspace or its history ---------------------------------------------


@pytest.mark.parametrize("name", RUN.fixture_names())
def test_the_sealed_copy_holds_every_file_the_checks_of_the_fixture_read(
    built: Callable[..., dict[str, Any]], name: str
) -> None:
    """The checks run from the sealed copy alone: none reports a file of it missing. The same
    build shows that no grader is in the workspace or its history during the call; one test per
    fixture, since two tests of it would land on different workers and build it twice."""

    ran = built(name)
    assert ran["extra"].get("error") is None, ran["report"][-1500:]
    assert ran["facts"] is not None, "the call never ran"
    plan = (FIXTURES / name / "post.plan.json").read_text(encoding="utf-8")
    if "OUTCOMEBOUND_GRADER_DIR" in plan:
        assert ran["facts"]["stage"], "the plan names the stage, and the stage held no grader"
    assert _leaks(ran["facts"]) == []

    sealed = Path(ran["extra"]["graders_copy"])
    assert (ran["workspace"].parent / sealed).is_dir()
    missing = [
        line
        for line in ran["report"].splitlines()
        if sealed.name in line and re.search(r"No such file|can't open file|not found", line)
    ]
    assert missing == []


def test_the_kernel_off_arm_puts_the_graders_where_the_current_arm_does(
    built: Callable[..., dict[str, Any]],
) -> None:
    """Where the graders go does not depend on the arm."""

    current, none = built(CONTROL, "current"), built(CONTROL, "none")
    assert _leaks(none["facts"]) == []
    assert set(none["facts"]["stage"]) == set(current["facts"]["stage"])


def test_the_stage_is_a_private_folder_outside_the_workspace_that_the_run_removes(
    built: Callable[..., dict[str, Any]],
) -> None:
    ran = built(CONTROL)
    stage, workspace = ran["stage"], ran["workspace"]
    assert stage.name.startswith("ob-graders-")
    assert ran["facts"]["stage_mode"] == 0o700
    assert workspace not in stage.parents and stage not in workspace.parents
    assert not stage.exists(), "the stage outlived the run"


def _mirror(base: Path, monkeypatch: pytest.MonkeyPatch, extra: str = "") -> Path:
    """The control fixture, built in its own folder: a copy of `small-fix` and what its setup
    needs, with `extra` added before the seed commit. The runner reads fixtures from it."""

    evals = base / "evals"
    ignore = shutil.ignore_patterns("__pycache__")
    shutil.copytree(FIXTURES / CONTROL, evals / "fixtures" / CONTROL, ignore=ignore)
    shutil.copy(FIXTURES / "core-skill.sh", evals / "fixtures" / "core-skill.sh")
    shutil.copytree(FIXTURES.parent / "graders", evals / "graders", ignore=ignore)
    (base / "skills").symlink_to(ROOT / "skills")
    setup = evals / "fixtures" / CONTROL / "setup.sh"
    setup.write_text(
        setup.read_text(encoding="utf-8").replace("git init -q .", extra + "git init -q .", 1),
        encoding="utf-8",
    )
    monkeypatch.setattr(RUN, "FIXTURES", evals / "fixtures")
    return evals


LEAKS = {
    "a grader copied into the workspace": 'cp "$here/checks/probe_datehelp.py" helper.py\n',
    "a path under checks": "mkdir -p checks\nprintf 'x\\n' > checks/other.txt\n",
}


@pytest.mark.parametrize("leak", sorted(LEAKS))
def test_NEGATIVE_CONTROL_a_setup_that_writes_a_grader_into_the_workspace_fails_the_test(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, leak: str
) -> None:
    """The control is built in this test's own folder, never under `evals/fixtures/`."""

    base = tmp_path / "mirror"
    base.mkdir()
    _mirror(base, monkeypatch, LEAKS[leak])
    stages = _watch(monkeypatch)
    harness = Stand(stages)
    _run(tmp_path / "runs", CONTROL, "none", harness)
    assert harness.facts is not None and _leaks(harness.facts), "the leak went unseen"
    assert not (FIXTURES / CONTROL / "helper.py").exists()


# --- what a plan names, and what a grader imports ------------------------------------------


@pytest.mark.parametrize("name", RUN.fixture_names())
def test_a_plan_names_checks_only_in_the_grader_folder(name: str) -> None:
    text = (FIXTURES / name / "post.plan.json").read_text(encoding="utf-8")
    strings = _strings(json.loads(text))
    for item in strings:
        assert not BARE.search(ALLOWED.sub("", item)), (
            f"{name} names checks/ outside the stage: {item}"
        )
    for claim in json.loads(text)["claims"]:
        for path in claim.get("required_paths", []):
            assert not path.startswith("checks/"), f"{name} requires {path} in the workspace"


@pytest.mark.parametrize("name", RUN.fixture_names())
def test_protected_paths_hold_no_grader_of_the_stage(name: str) -> None:
    lines = (FIXTURES / name / "protected.paths").read_text(encoding="utf-8").splitlines()
    kept = [line.strip() for line in lines if line.strip() and not line.startswith("#")]
    assert kept, f"{name} protects nothing"
    assert not [line for line in kept if line.startswith("checks/")]


def _strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [text for item in value.values() for text in _strings(item)]
    if isinstance(value, list):
        return [text for item in value for text in _strings(item)]
    return []


def test_no_grader_imports_from_evals() -> None:
    """The plan runs with this checkout on `PYTHONPATH`: an import from `evals` would read the
    checkout, not the sealed copy, and a regrade would not be sealed."""

    graders = sorted((FIXTURES.parent / "graders").glob("*.py"))
    graders += sorted(path for path in FIXTURES.rglob("*.py") if "__pycache__" not in path.parts)
    assert len(graders) > 20
    for path in graders:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names = (
                [alias.name for alias in node.names]
                if isinstance(node, ast.Import)
                else [node.module or ""]
                if isinstance(node, ast.ImportFrom) and not node.level
                else []
            )
            assert not [item for item in names if item.split(".")[0] == "evals"], path


# --- the sealed copy, the regrade and a stage changed during the call ----------------------


def _status() -> dict[str, Any]:
    return {
        "harness": "codex",
        "arm": "none",
        "model": "m",
        "effort": "medium",
        "repetition": 1,
        "workspace_root": None,
    }


def _kept(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    act: Callable[[Path, Path], None] | None = None,
) -> tuple[Path, dict[str, Any], Path]:
    """A run of the control fixture kept in `out`: the mirror it ran from, its meta and `out`."""

    base = tmp_path / "mirror"
    base.mkdir()
    evals = _mirror(base, monkeypatch)
    stages = _watch(monkeypatch)
    harness = Stand(stages, act or (lambda cwd, _stage: _write_fix(cwd)))
    out = tmp_path / "out"
    out.mkdir()
    RUN.run_one(out, _status(), CONTROL, RUN.load_arm("none"), os.defpath, cast(Any, harness))
    meta = json.loads((out / f"{CONTROL}.meta.json").read_text(encoding="utf-8"))
    return evals, meta, out


def _write_fix(cwd: Path) -> None:
    subprocess.run(["bash", "-c", FIX_THE_DATE], cwd=cwd, check=True, env=GIT_ENV)


def _regrade(out: Path, target: Path) -> int:
    return RUN._main(["--regrade", str(out), "--out", str(target)])


def test_the_run_seals_its_graders_and_records_their_digest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from evals.evidence import tree_digest

    _evals, meta, out = _kept(tmp_path, monkeypatch)
    assert meta["verdict"] == "PASS", meta
    sealed = out / f"{CONTROL}.graders"
    assert meta["graders_sha256"] == tree_digest(sealed)
    assert (sealed / "post.plan.json").is_file()
    assert (sealed / "checks" / "probe_datehelp.py").is_file()
    assert (sealed / "evals" / "graders" / "scope_walk.py").is_file()
    workspace = Path(meta["fixture_repo"])
    assert not (workspace / "checks").exists()


def test_regrade_runs_the_sealed_copy_not_the_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A grader changed in the checkout after the run changes no regraded verdict."""

    evals, meta, out = _kept(tmp_path, monkeypatch)
    assert meta["verdict"] == "PASS"
    probe = evals / "fixtures" / CONTROL / "checks" / "probe_datehelp.py"
    probe.write_text("raise SystemExit(1)\n", encoding="utf-8")
    new = tmp_path / "regraded"
    assert _regrade(out, new) == 0
    again = json.loads((new / f"{CONTROL}.meta.json").read_text(encoding="utf-8"))
    assert (again["verdict"], again["claims"]) == (meta["verdict"], meta["claims"])
    assert again["graders_sha256"] == meta["graders_sha256"]
    assert (new / f"{CONTROL}.graders" / "checks" / "probe_datehelp.py").read_bytes() != (
        probe.read_bytes()
    )


def test_regrade_refuses_a_sealed_copy_that_differs_from_its_digest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _evals, _meta, out = _kept(tmp_path, monkeypatch)
    (out / f"{CONTROL}.graders" / "checks" / "probe_datehelp.py").write_text("exit 0\n", "utf-8")
    new = tmp_path / "regraded"
    assert _regrade(out, new) == 2
    assert f"refused {CONTROL}" in capsys.readouterr().err
    assert not new.exists()


@pytest.mark.parametrize("what", ["a stage file", "a grading file of the checkout"])
def test_a_stage_changed_during_the_call_fails_the_run_unexecuted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, what: str
) -> None:
    changed: list[Path] = []

    def tamper(cwd: Path, stage: Path) -> None:
        _write_fix(cwd)
        target = (
            stage / "checks" / "probe_datehelp.py"
            if what == "a stage file"
            else RUN.FIXTURES.parent / "graders" / "scope_walk.py"
        )
        target.write_text("raise SystemExit(0)\n", encoding="utf-8")
        changed.append(target)

    _evals, meta, out = _kept(tmp_path, monkeypatch, tamper)
    assert changed
    assert meta["verdict"] == "FAIL" and meta["claims"] == {}, meta
    report = (out / f"{CONTROL}.transcript.txt").read_text(encoding="utf-8")
    assert "FAIL protected-grading-inputs" in report
    assert meta["protected_intact"] is False
    assert not (out / f"{CONTROL}.graders").exists()


def test_a_bytecode_cache_written_into_the_stage_is_not_sealed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The seal does not digest a `__pycache__`, so the sealed copy holds none."""

    def cache(cwd: Path, stage: Path) -> None:
        _write_fix(cwd)
        folder = stage / "checks" / "__pycache__"
        folder.mkdir()
        (folder / "probe_datehelp.cpython-313.pyc").write_bytes(b"forged")

    _evals, meta, out = _kept(tmp_path, monkeypatch, cache)
    assert meta["verdict"] == "PASS", meta
    sealed = out / f"{CONTROL}.graders"
    assert not list(sealed.rglob("__pycache__"))


def test_a_stage_changed_after_the_check_and_before_the_copy_fails_the_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A writer that outlived the call and changes the stage after the check is caught when the
    copy is compared with what was sealed before the call."""

    checked = RUN.check_graders

    def late(sealed: Any, name: str) -> tuple[bool, str]:
        result = checked(sealed, name)
        (sealed.stage / "checks" / "probe_datehelp.py").write_text("raise SystemExit(0)\n", "utf-8")
        return result

    monkeypatch.setattr(RUN, "check_graders", late)
    _evals, meta, out = _kept(tmp_path, monkeypatch)
    assert meta["verdict"] == "FAIL" and meta["claims"] == {}, meta
    report = (out / f"{CONTROL}.transcript.txt").read_text(encoding="utf-8")
    assert "FAIL protected-grading-inputs" in report
    assert "stage/checks/probe_datehelp.py" in report
    assert meta["protected_intact"] is False
    assert not (out / f"{CONTROL}.graders").exists()


def test_regrade_compares_the_grading_files_in_the_sealed_copy_with_their_digest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`grading_files_unchanged` says what the regrade compared: the grading files in the copy
    against `grading_files_sha256`, even where the copy's own digest was rewritten to match."""

    from evals.evidence import tree_digest

    _evals, meta, out = _kept(tmp_path, monkeypatch)
    new = tmp_path / "regraded"
    assert _regrade(out, new) == 0
    again = json.loads((new / f"{CONTROL}.meta.json").read_text(encoding="utf-8"))
    assert again["grading_files_unchanged"] == "PASS"
    sealed = out / f"{CONTROL}.graders"
    (sealed / "evals" / "graders" / "scope_walk.py").write_text("raise SystemExit(0)\n", "utf-8")
    meta["graders_sha256"] = tree_digest(sealed)
    (out / f"{CONTROL}.meta.json").write_text(json.dumps(meta), encoding="utf-8")
    other = tmp_path / "regraded-again"
    assert _regrade(out, other) == 2
    assert "grading_files_sha256" in capsys.readouterr().err
    assert not other.exists()
