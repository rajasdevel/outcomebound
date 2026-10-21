"""Element arms and the call's skill catalog, with no model call.

An element arm measures one part of an adopted install: `--drop` takes elements from the
current arm, `--add` puts elements into the none arm, `--edits` changes the installed text. Each
is built from adopt's own install, before it joins the seed. The invariants are checked on
replica fixtures as a run builds them; the refusals, edits and records on a fake fixture in a
temporary folder, where every codex is a fake that records being started. The catalog is read
from synthetic native session records.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest

from evals.harnesses import CallResult
from evals.harnesses import codex as codex_harness
from tests.eval_helpers import RUN
from tests.portable import needs_posix_bash

pytestmark = needs_posix_bash

NOTE = "# Team notes\n\nStack: Python. `make test` runs the unit tests (a few seconds).\n"
SETUP = """#!/usr/bin/env bash
set -euo pipefail
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
target="${1:?}"; stage="${2:?}"
mkdir -p "$target" "$stage/checks"
cd "$target"
cat > AGENTS.md <<'NOTE'
@NOTE@
NOTE
printf 'test:\\n\\t@true\\ncheck:\\n\\t@true\\n' > Makefile
git init -q
git add -A
git -c user.name=t -c user.email=t@example.invalid commit -q -m seed
git tag seed
""".replace("@NOTE@", NOTE.rstrip("\n"))
PLAN = {
    "version": 1,
    "cwd": ".",
    "timeout_seconds": 60,
    "claims": [
        {"name": "always", "risk": "none", "kind": "static", "required": True, "command": ["true"]}
    ],
}
INSTALL = {"done": ["make check", "make test"], "fragments": ["commands"], "sandbox": "eval"}
# Files adopt writes that no element owns: the current arm less any element keeps them, the none
# arm plus any element has none of them.
UNOWNED = {".agents/.gitignore", ".outcomebound/.gitignore", ".outcomebound/manifest.json"}
DATE = re.compile(rb"\d{4}-\d{2}-\d{2}(?:[T ][\d:.]+(?:Z|[+-]\d{2}:?\d{2})?)?")
KERNEL_CLAUSE = " Smallest complete, not least work."


def _fixture(root: Path, install: dict[str, Any] | None = INSTALL) -> Path:
    """A fake fixture `replica-fake` under `root/evals/fixtures`, and the folder that holds it."""

    fixture = root / "evals" / "fixtures" / "replica-fake"
    fixture.mkdir(parents=True)
    (fixture / "setup.sh").write_text(SETUP, encoding="utf-8")
    (fixture / "prompt.md").write_text("Record the release in the changelog.\n", encoding="utf-8")
    (fixture / "protected.paths").write_text("Makefile\n", encoding="utf-8")
    (fixture / "post.plan.json").write_text(json.dumps(PLAN), encoding="utf-8")
    if install is not None:
        (fixture / "install.json").write_text(json.dumps(install), encoding="utf-8")
    return fixture.parent


def _fake_codex(bindir: Path, calls: Path) -> None:
    bindir.mkdir(parents=True, exist_ok=True)
    (bindir / "codex").write_text(f'#!/bin/sh\necho "$*" >> "{calls}"\nexit 9\n', "utf-8")
    (bindir / "codex").chmod(0o755)


@pytest.fixture
def fake(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    """The fake fixture, a fake codex first on PATH, a clean Codex home and no skill folders
    outside it."""

    calls = tmp_path / "codex-calls.txt"
    _fake_codex(tmp_path / "fakebin", calls)
    monkeypatch.setenv("PATH", os.pathsep.join([str(tmp_path / "fakebin"), os.environ["PATH"]]))
    home = tmp_path / "codex-home"
    (home / "skills" / ".system").mkdir(parents=True)
    monkeypatch.setenv("CODEX_HOME", str(home))
    monkeypatch.setattr(RUN, "OUTSIDE_SKILLS", ())
    monkeypatch.setattr(RUN, "FIXTURES", _fixture(tmp_path))
    return {"calls": calls}


def _arm(name: str, kind: str, elements: Any = None) -> Any:
    return RUN.fixture_arms(RUN._parser(), kind, [name], elements or RUN.Elements())[name]


def _build(name: str, arm: Any, root: Path) -> tuple[Path, dict[str, str], str]:
    """The fixture built under `arm` as a run builds it: its workspace, the protected digests
    and the prompt."""

    workdir = root / "workspace"
    workdir.mkdir(parents=True)
    stage = root / "stage"
    stage.mkdir()
    extra: dict[str, Any] = {}
    failure, protected, _seed, prompt = RUN.build_workspace(name, arm, workdir, extra, stage)
    assert failure is None, (failure, extra)
    return workdir, protected, prompt


def _files(root: Path) -> dict[str, bytes]:
    """Every file under `root` outside `.git`, by relative path, with any date blanked."""

    return {
        path.relative_to(root).as_posix(): DATE.sub(b"<date>", path.read_bytes())
        for path in sorted(root.rglob("*"))
        if path.is_file() and ".git" not in path.relative_to(root).parts
    }


def _git(workdir: Path, *arguments: str) -> str:
    done = subprocess.run(
        ["git", *arguments],
        cwd=workdir,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, **RUN.HERMETIC_GIT},
        check=True,
    )
    return done.stdout


def _clean(workdir: Path) -> None:
    assert _git(workdir, "status", "--porcelain") == ""
    assert _git(workdir, "rev-parse", "HEAD") == _git(workdir, "rev-parse", "seed^{commit}")


def _kernel_block(workdir: Path) -> str:
    from outcomebound_tools import adopt

    found = adopt.block_text((workdir / "AGENTS.md").read_text("utf-8"), adopt.KERNEL)
    assert found is not None
    return found.decode("utf-8")


# --- the invariants, on replica fixtures ------------------------------------------------------


def test_the_none_arm_plus_the_kernel_is_the_none_tree_and_the_kernel_block(
    tmp_path: Path,
) -> None:
    """Breaks if `--arm none --add kernel` carries anything of the install but the kernel block
    in AGENTS.md: a skill, a fragment, a `.outcomebound/` file, `.agents/.gitignore` or the
    launcher; or if its note differs from the none arm's but for that block."""

    none, _protected, none_prompt = _build(
        "replica-batch", _arm("replica-batch", "none"), tmp_path / "n"
    )
    arm = _arm("replica-batch", "none", RUN.Elements(added=("kernel",)))
    assert arm.launcher is None and arm.files == {} and arm.adopted
    plus, _protected, prompt = _build("replica-batch", arm, tmp_path / "p")
    expected = _files(none)
    expected["AGENTS.md"] = _kernel_block(plus).encode("utf-8") + b"\n\n" + expected["AGENTS.md"]
    assert _files(plus) == expected
    assert _kernel_block(plus) == arm.kernel == RUN.kernel("current")
    assert prompt == none_prompt
    _clean(plus)


def test_the_current_arm_less_a_fragment_is_the_current_tree_less_its_file_and_line(
    tmp_path: Path,
) -> None:
    """Breaks if `--arm current --drop fragment:commands` differs from the current arm but for
    the fragment's file and its pointer line, or if its record does not digest what it installs."""

    current, _protected, _prompt = _build(
        "replica-batch", _arm("replica-batch", "current"), tmp_path / "c"
    )
    arm = _arm("replica-batch", "current", RUN.Elements(dropped=("fragment:commands",)))
    less, _protected, _prompt = _build("replica-batch", arm, tmp_path / "l")
    expected = _files(current)
    del expected[".outcomebound/fragments/commands.md"]
    line = (
        b"\n- when running a command whose output you read: "
        b"read .outcomebound/fragments/commands.md"
    )
    assert expected["AGENTS.md"].count(line) == 1
    expected["AGENTS.md"] = expected["AGENTS.md"].replace(line, b"")
    assert _files(less) == expected
    assert arm.launcher is not None
    for path, digest in arm.record()["arm_files"].items():
        assert hashlib.sha256((less / path).read_bytes()).hexdigest() == digest, path
    _clean(less)


@pytest.mark.parametrize("fixture", ["replica-batch", "replica-cleanup"])
def test_the_current_arm_less_every_element_is_the_none_tree_but_what_no_element_owns(
    tmp_path: Path, fixture: str
) -> None:
    """Breaks if dropping every element from the current arm leaves anything of the install but
    the files adopt writes that no element owns, which current less an element keeps; or if the
    note differs from the none arm's. replica-cleanup's setup also copies the core skill to the
    path its note names, which the skill's drop takes with it."""

    probe = _arm(fixture, "current")
    every = RUN.install_elements(probe)
    arm = _arm(fixture, "current", RUN.Elements(dropped=every))
    assert arm.kernel == "" and arm.launcher is None and arm.files == {}
    less, _protected, _prompt = _build(fixture, arm, tmp_path / "l")
    none, _protected, _prompt = _build(fixture, _arm(fixture, "none"), tmp_path / "n")
    found = _files(less)
    assert {path for path in found if path not in _files(none)} == UNOWNED
    assert {path: data for path, data in found.items() if path not in UNOWNED} == _files(none)
    _clean(less)


# --- what the build checks, and the dump shows -------------------------------------------------


def test_an_element_arm_that_holds_more_than_its_elements_is_found(tmp_path: Path) -> None:
    """Breaks if a skill folder or a block outside the none arm's added elements goes unnoticed
    by the build's check or by the dump's isolation rules."""

    arm = _arm("replica-batch", "none", RUN.Elements(added=("kernel", "skill:diagnose")))
    workdir, protected, _prompt = _build("replica-batch", arm, tmp_path / "p")
    assert ".agents/skills/diagnose/SKILL.md" in protected, "the installed skill is protected"
    assert RUN.element_problems(workdir, arm) == []
    leak = workdir / ".agents" / "skills" / "tests-worth-keeping"
    leak.mkdir(parents=True)
    (leak / "SKILL.md").write_text("x\n", encoding="utf-8")
    note = workdir / "AGENTS.md"
    facts = (
        "<!-- outcomebound:begin id=project-facts v=1.0.0 -->\n- Done: x\n"
        "<!-- outcomebound:end id=project-facts -->\n\n"
    )
    note.write_text(facts + note.read_text("utf-8"), encoding="utf-8")
    problems = RUN.element_problems(workdir, arm)
    assert "skill:tests-worth-keeping's folder present" in problems
    assert "the project-facts block present" in problems
    assert "the arm does not hold exactly its elements" in RUN.element_problem(workdir, arm)
    rows = {row[0]: row for row in RUN.isolation(arm, workdir, "Task:\nx\n", "", tmp_path)}
    assert rows["elements"][1] == "FAIL"
    assert rows["no-outcomebound-text"][1] == "FAIL", rows


def test_a_file_the_fixtures_setup_wrote_under_outcomebound_is_the_fixtures_own(
    tmp_path: Path, fake: dict[str, Path]
) -> None:
    """Breaks if an element arm removes, or the isolation rule counts as carried, a file the
    fixture's setup wrote under `.outcomebound/` (a declared ticket store), if the none arm plus
    an element differs from the none tree but for that element, or if a file the setup did not
    write there stops counting as carried."""

    fixtures = RUN.FIXTURES
    store = fixtures / "replica-store"
    store.mkdir()
    for child in (fixtures / "replica-fake").iterdir():
        (store / child.name).write_bytes(child.read_bytes())
    own = '{"version": 1, "store": "github"}'
    write = f"mkdir -p .outcomebound\nprintf '%s' '{own}' > .outcomebound/tickets.json\n"
    (store / "setup.sh").write_text(SETUP.replace("git init -q", write + "git init -q", 1), "utf-8")

    def rules(arm: Any, workdir: Path) -> dict[str, list[str]]:
        return {row[0]: row for row in RUN.isolation(arm, workdir, "Task:\nx\n", "", tmp_path)}

    none, _protected, _prompt = _build(
        "replica-store", _arm("replica-store", "none"), tmp_path / "n"
    )
    assert (none / ".outcomebound" / "tickets.json").read_text("utf-8") == own
    assert rules(_arm("replica-store", "none"), none)["no-outcomebound-text"][1] == "PASS"
    arm = _arm("replica-store", "none", RUN.Elements(added=("kernel",)))
    plus, _protected, _prompt = _build("replica-store", arm, tmp_path / "p")
    expected = _files(none)
    expected["AGENTS.md"] = _kernel_block(plus).encode("utf-8") + b"\n\n" + expected["AGENTS.md"]
    assert _files(plus) == expected
    assert rules(arm, plus)["no-outcomebound-text"][1] == "PASS", rules(arm, plus)
    _clean(plus)
    (plus / ".outcomebound" / "leak.json").write_text("{}\n", encoding="utf-8")
    row = rules(arm, plus)["no-outcomebound-text"]
    assert row[1] == "FAIL" and ".outcomebound/leak.json" in row[2], row
    assert "tickets.json" not in row[2], row
    dropped = _arm("replica-store", "current", RUN.Elements(dropped=("fragment:commands",)))
    less, _protected, _prompt = _build("replica-store", dropped, tmp_path / "l")
    assert (less / ".outcomebound" / "tickets.json").read_text("utf-8") == own
    assert not (less / ".outcomebound" / "fragments" / "commands.md").exists()
    _clean(less)


def test_the_dump_shows_an_element_arm_and_passes_its_rules(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], fake: dict[str, Path]
) -> None:
    root = tmp_path / "dumps"
    arguments = ["--dump-arm", "replica-fake", "--model", "m", "--workspace-root", str(root)]
    assert RUN._main([*arguments, "--arm", "none", "--add", "kernel"]) == 0
    printed = capsys.readouterr().out
    assert "fixture replica-fake, arm none-plus-kernel;" in printed
    assert "--- elements ---\nnone arm, added ['kernel']\nkept: kernel\nnot held: facts" in printed
    for rule in ("launcher-on-path", "elements", "no-outcomebound-text", "no-engine-import"):
        assert f"{rule} PASS" in printed, printed
    assert "features.plugins=false" in printed
    assert RUN._main([*arguments, "--arm", "current", "--drop", "fragment:commands"]) == 0
    printed = capsys.readouterr().out
    assert "arm current-minus-fragment.commands;" in printed
    assert "not held: fragment:commands" in printed and "elements PASS" in printed
    assert ".outcomebound/fragments/commands.md" not in printed
    assert not fake["calls"].exists(), "the dump started codex"


# --- refusals ----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("options", "reason"),
    [
        (["--arm", "none", "--drop", "kernel"], "--drop takes an element from the current install"),
        (["--arm", "current", "--add", "kernel"], "--add puts an element into the none arm"),
        (["--arm", "unsized", "--drop", "kernel"], "use --arm current"),
        (["--arm", "current", "--drop", "colour"], "no element 'colour'"),
        (["--arm", "current", "--drop", "kernel", "--drop", "kernel"], "name each element once"),
        (
            ["--arm", "current", "--drop", "fragment:python"],
            "replica-fake: fragment:python: its install.json selects no fragment python "
            "(it selects commands)",
        ),
        (["--arm", "none", "--add", "skill:nope"], "the install carries no skill nope"),
        (["--arm", "none", "--edits", "{edits}", "--arm-label", "x"], "--edits changes an install"),
        (["--arm", "current", "--edits", "{edits}"], "--edits needs --arm-label"),
    ],
)
def test_an_element_arm_the_runner_cannot_build_is_refused_before_anything_runs(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    fake: dict[str, Path],
    options: list[str],
    reason: str,
) -> None:
    edits = tmp_path / "edits.json"
    edits.write_text(json.dumps([{"path": "AGENTS.md", "old": "x", "new": ""}]), "utf-8")
    out = tmp_path / "out"
    arguments = ["--model", "m", "--fixtures", "replica-fake", "--out", str(out)]
    with pytest.raises(SystemExit) as stopped:
        RUN._main([*arguments, *(item.format(edits=edits) for item in options)])
    assert stopped.value.code == 2
    assert reason in capsys.readouterr().err
    assert not fake["calls"].exists() and not out.exists()


def test_an_element_arm_on_a_fixture_without_install_json_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(RUN, "FIXTURES", _fixture(tmp_path, install=None))
    with pytest.raises(SystemExit) as stopped:
        _arm("replica-fake", "current", RUN.Elements(dropped=("kernel",)))
    assert stopped.value.code == 2
    error = capsys.readouterr().err
    assert "replica-fake: an element arm is built from an adopted install" in error
    assert "the fixture has no install.json" in error


def _edits(tmp_path: Path, edits: Any) -> Path:
    path = tmp_path / "edits.json"
    path.write_text(edits if isinstance(edits, str) else json.dumps(edits), encoding="utf-8")
    return path


SKILL = ".agents/skills/diagnose/SKILL.md"


def _skill_line() -> str:
    """A line of the diagnose skill that occurs in it once."""

    text = (RUN.REPO / "skills" / "diagnose" / "SKILL.md").read_text("utf-8")
    return next(line for line in text.splitlines() if len(line) > 30 and text.count(line) == 1)


@pytest.mark.parametrize(
    ("edits", "reason"),
    [
        ("{not json", "not readable JSON"),
        ([], "not empty"),
        ([{"path": "AGENTS.md", "old": "x"}], "each edit is exactly"),
        ([{"path": "AGENTS.md", "old": 1, "new": ""}], "are strings"),
        ([{"path": "/etc/x", "old": "x", "new": ""}], "not a workspace-relative path"),
        ([{"path": "../x", "old": "x", "new": ""}], "not a workspace-relative path"),
        ([{"path": "AGENTS.md", "old": "", "new": "x"}], "old is empty"),
        ([{"path": "Makefile", "old": "test", "new": ""}], "an edit changes AGENTS.md"),
        ([{"path": SKILL, "old": "no such text in the skill", "new": ""}], "occurs 0 times"),
        ([{"path": SKILL, "old": "the", "new": ""}], "not once"),
        ([{"path": "AGENTS.md", "old": "no such text in the note", "new": ""}], "occurs 0 times"),
        ([{"path": "AGENTS.md", "old": "the", "new": ""}], "not once"),
    ],
)
def test_an_edit_that_does_not_apply_once_is_refused_before_the_run_starts(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    fake: dict[str, Path],
    edits: Any,
    reason: str,
) -> None:
    """Breaks if an edit whose text occurs zero or two times, or names a file the install does
    not write, reaches a run: the refusal comes before codex starts and before the run directory
    is made, an edit of AGENTS.md through a build of the fixture in a temporary folder."""

    out = tmp_path / "out"
    arguments = ["--arm", "current", "--model", "m", "--fixtures", "replica-fake"]
    arguments += ["--edits", str(_edits(tmp_path, edits)), "--arm-label", "edited"]
    with pytest.raises(SystemExit) as stopped:
        RUN._main([*arguments, "--out", str(out)])
    assert stopped.value.code == 2
    assert reason in capsys.readouterr().err
    assert not fake["calls"].exists() and not out.exists()


# --- edits, labels and records ------------------------------------------------------------------


class Recorder:
    """A harness that answers at once, with no session record."""

    name = "codex"

    def call(self, _prompt, request, _cwd, _roots, _path, _keep):
        return CallResult("done", "", 0, {"model": request.model}, {}, "", [])


def test_edits_apply_to_the_install_and_the_records_digest_what_was_installed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], fake: dict[str, Path]
) -> None:
    """Breaks if an edit does not reach the installed AGENTS.md or skill file, if the workspace
    does not start on a clean `git status`, or if the meta's file and kernel digests, elements,
    kind and edit digests do not match what was installed and asked for."""

    line = _skill_line()
    path = _edits(
        tmp_path,
        [
            {"path": "AGENTS.md", "old": KERNEL_CLAUSE, "new": ""},
            {"path": SKILL, "old": line, "new": "Edited line."},
        ],
    )
    out = tmp_path / "out"
    arguments = ["--arm", "current", "--drop", "fragment:commands", "--edits", str(path)]
    arguments += ["--arm-label", "no-smallest", "--model", "m", "--fixtures", "replica-fake"]
    assert RUN._main([*arguments, "--out", str(out)]) == RUN.PREFLIGHT_EXIT
    status = json.loads((out / "STATUS.json").read_text(encoding="utf-8"))
    assert (status["arm"], status["arm_kind"]) == ("no-smallest", "current")
    assert status["elements"] == {"dropped": ["fragment:commands"], "added": []}
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    assert status["edits"]["sha256"] == digest
    capsys.readouterr()

    elements = RUN.Elements(("fragment:commands",), (), *RUN.read_edits(path))
    arm = _arm("replica-fake", "current", elements)
    record = tmp_path / "record"
    record.mkdir()
    failed, _row = RUN.run_one(record, status, "replica-fake", arm, "", Recorder())
    assert not failed
    meta = json.loads((record / "replica-fake.meta.json").read_text(encoding="utf-8"))
    workdir = Path(meta["fixture_repo"])
    _clean(workdir)
    note = (workdir / "AGENTS.md").read_text("utf-8")
    assert KERNEL_CLAUSE.strip() not in note and "Never claim a check" in note
    assert "Edited line." in (workdir / SKILL).read_text("utf-8")
    assert not (workdir / ".outcomebound" / "fragments" / "commands.md").exists()
    assert meta["arm"] == "no-smallest" and meta["arm_kind"] == "current"
    assert meta["elements"] == {"dropped": ["fragment:commands"], "added": []}
    assert meta["edits"] == {
        "sha256": digest,
        "items": [
            {
                "path": "AGENTS.md",
                "old_sha256": hashlib.sha256(KERNEL_CLAUSE.encode()).hexdigest(),
                "new_sha256": hashlib.sha256(b"").hexdigest(),
            },
            {
                "path": SKILL,
                "old_sha256": hashlib.sha256(line.encode()).hexdigest(),
                "new_sha256": hashlib.sha256(b"Edited line.").hexdigest(),
            },
        ],
    }
    assert meta["arm_files"] == {
        name: hashlib.sha256((workdir / name).read_bytes()).hexdigest()
        for name in meta["arm_files"]
    }
    assert meta["arm_files"][SKILL] == hashlib.sha256((workdir / SKILL).read_bytes()).hexdigest()
    assert meta["kernel_sha256"] == hashlib.sha256(_kernel_block(workdir).encode()).hexdigest()
    assert (record / "replica-fake.prompt.md").read_text("utf-8") == (
        "Task:\nRecord the release in the changelog.\n"
    )


def test_an_element_arms_default_label_names_its_elements() -> None:
    label = RUN.element_label
    assert label("current", RUN.Elements(dropped=("fragment:commands",))) == (
        "current-minus-fragment.commands"
    )
    assert label("none", RUN.Elements(added=("kernel", "skill:diagnose"))) == (
        "none-plus-kernel-skill.diagnose"
    )
    assert label("current", RUN.Elements()) == "current"


def test_the_none_arm_plus_the_launcher_reaches_it_and_nothing_else(
    tmp_path: Path, fake: dict[str, Path]
) -> None:
    arm = _arm("replica-fake", "none", RUN.Elements(added=("launcher",)))
    workdir, _protected, _prompt = _build("replica-fake", arm, tmp_path / "w")
    assert (workdir / "AGENTS.md").read_text("utf-8") == NOTE
    assert arm.launcher == RUN.REPO / RUN.LAUNCHER and arm.kernel == ""
    reached = RUN.launchers(RUN.call_path(arm, str(tmp_path)))
    assert [item.rsplit(" -> ", 1)[1] for item in reached] == [os.path.realpath(arm.launcher)]
    _clean(workdir)


def test_a_pointer_line_added_without_its_block_keeps_the_markers_and_read_once_line(
    tmp_path: Path, fake: dict[str, Path]
) -> None:
    from outcomebound_tools import facts

    arm = _arm("replica-fake", "none", RUN.Elements(added=("fragment:commands",)))
    workdir, _protected, _prompt = _build("replica-fake", arm, tmp_path / "w")
    note = (workdir / "AGENTS.md").read_text("utf-8")
    block = note.split("\n\n", 1)[0].splitlines()
    assert block[0].startswith("<!-- outcomebound:begin id=guidance-pointers ")
    assert block[1:] == [
        facts.ONCE,
        "- when running a command whose output you read: read .outcomebound/fragments/commands.md",
        "<!-- outcomebound:end id=guidance-pointers -->",
    ]
    assert sorted(_files(workdir)) == [
        ".outcomebound/fragments/commands.md",
        "AGENTS.md",
        "Makefile",
    ]
    _clean(workdir)


# --- the catalog and the summary ----------------------------------------------------------------


def _message(role: str, *texts: str) -> dict[str, Any]:
    content = [{"type": "input_text", "text": text} for text in texts]
    return {
        "type": "response_item",
        "payload": {"type": "message", "role": role, "content": content},
    }


SKILLS_TEXT = (
    "<skills_instructions>\n## Skills\n### Skill roots\n- `r0` = `/x`\n"
    "### Available skills\n"
    "- pdf: Read PDFs. (file: r0/pdf/SKILL.md)\n"
    "- diagnose: Find a cause. (file: r1/diagnose/SKILL.md)\n"
    "- sites:sites: Build a site. (file: r2/sites/SKILL.md)\n"
    "- notion:notion-digest: Digest. (file: r3/x/SKILL.md)\n"
    "- notion:notion-spec: Spec. (file: r3/y/SKILL.md)\n"
    "</skills_instructions>"
)


def test_the_catalog_is_read_from_the_developer_messages_before_the_first_user_message() -> None:
    """Breaks if the catalog counts a message after the first user message, a skill-roots line as
    a skill, or a skill with no plugin as a plugin's."""

    records = [
        {"type": "session_meta", "payload": {"id": "t"}},
        _message("developer", SKILLS_TEXT, "<permissions>p</permissions>"),
        _message("developer", "<role>r</role>"),
        _message("user", "# AGENTS.md instructions"),
        _message("developer", "later, not counted"),
    ]
    assert codex_harness.catalog(records) == {
        "developer_characters": sum(
            map(len, (SKILLS_TEXT, "<permissions>p</permissions>", "<role>r</role>"))
        ),
        "skills": 5,
        "plugins": {"notion": 2, "sites": 1},
    }
    assert codex_harness.catalog(records[:3]) is None, "no user message: nothing delimits it"
    assert codex_harness.catalog([records[0], records[3]]) is None
    assert codex_harness.catalog(None) is None
    assert codex_harness.catalog([_message("developer", "no list"), records[3]]) == {
        "developer_characters": 7,
        "skills": 0,
        "plugins": {},
    }


def test_every_call_turns_plugins_off(tmp_path: Path) -> None:
    argv = RUN.make_harness().command("m", "medium", tmp_path, tmp_path / "last.md")
    assert argv[argv.index("features.plugins=false") - 1] == "-c"
    assert argv.index("features.plugins=false") < argv.index("-m")


BASE = {
    "fixture": "replica-fake",
    "harness": "codex",
    "model": "m",
    "effort": "medium",
    "claims": {},
    "protected_intact": True,
    "observations": [],
    "kernel_sha256": "k",
    "commit": "c" * 40,
    "dirty": False,
    "verdict": "PASS",
    "error": "",
    "session_tokens": {
        "input_tokens": 1000,
        "cached_input_tokens": 800,
        "output_tokens": 50,
        "reasoning_output_tokens": 20,
    },
}
PLAIN = {"developer_characters": 100, "skills": 29, "plugins": {}}
PLUGGED = {"developer_characters": 300, "skills": 65, "plugins": {"notion": 5, "sites": 2}}


def test_the_summary_flags_calls_and_arms_that_saw_different_catalogs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Breaks if a group whose calls saw different skill catalogs, or two arms on one fixture
    whose calls were given different plugin skills, is not flagged; if a record with no catalog
    is not `unrecorded`; or if the uncached input is not shown."""

    runs = [
        {"arm": "current", "repetition": 1, "catalog": PLAIN},
        {"arm": "current", "repetition": 2, "catalog": PLUGGED},
        {"arm": "none", "repetition": 1, "catalog": {**PLAIN, "developer_characters": 90}},
        {"arm": "none", "repetition": 2, "catalog": {**PLAIN, "developer_characters": 95}},
        {"arm": "older", "repetition": 1},
    ]
    for index, run in enumerate(runs):
        meta = {**BASE, **run, "thread_id": f"t{index}"}
        (tmp_path / f"{index}.meta.json").write_text(json.dumps(meta), encoding="utf-8")
    assert RUN.summarize([tmp_path]) == 0
    printed = capsys.readouterr().out.splitlines()
    current = printed[printed.index("replica-fake | codex | current | m medium: PASS 2/2") :]
    assert "  UNVERIFIED: these calls saw 2 different skill catalogs" in current
    assert (
        "  repetition 2 catalog: 65 skills, plugin skills notion 5, sites 2; developer messages "
        "300 characters"
    ) in current
    none = printed[printed.index("replica-fake | codex | none | m medium: PASS 2/2") :]
    assert none[1:4] == [
        "  median cost input 1000 (cached 800, uncached 200), output 50 (reasoning 20) tokens "
        "over 2 counted run(s)",
        "  spent on 2 call(s), 0 failed among them: input 2000 (cached 1600, uncached 400), "
        "output 100 (reasoning 40) tokens; 0.0 seconds over all 2",
        "  repetition 1: PASS; input 1000 (cached 800, uncached 200), output 50 (reasoning 20) "
        "tokens; unrecorded seconds",
    ]
    assert (
        "  catalog: 29 skills, plugin skills none; developer messages 90 to 95 characters" in none
    )
    older = printed[printed.index("replica-fake | codex | older | m medium: PASS 1/1") :]
    assert "  catalog: unrecorded" in older
    flagged = [line for line in printed if line.startswith("UNVERIFIED: the arms on")]
    assert flagged == [
        "UNVERIFIED: the arms on replica-fake were given different plugin skills: current "
        '{"notion": 5, "sites": 2} or {}; none {}; older unrecorded'
    ]


def test_the_summary_keeps_element_arms_of_one_label_apart_by_their_elements(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    one = {**BASE, "arm": "variant", "repetition": 1, "thread_id": "a"}
    one["elements"] = {"dropped": ["facts"], "added": []}
    two = {**one, "thread_id": "b", "elements": {"dropped": ["pointers"], "added": []}}
    plain = {**BASE, "arm": "current", "repetition": 1, "thread_id": "c"}
    plain["elements"] = {"dropped": [], "added": []}
    older = {**plain, "thread_id": "d", "repetition": 2}
    del older["elements"]
    for index, meta in enumerate((one, two, plain, older)):
        (tmp_path / f"{index}.meta.json").write_text(json.dumps(meta), encoding="utf-8")
    assert RUN.summarize([tmp_path]) == 0
    printed = capsys.readouterr().out.splitlines()
    headers = [line for line in printed if line.startswith("replica-fake |")]
    assert headers.count("replica-fake | codex | variant | m medium: PASS 1/1") == 2, printed
    assert "replica-fake | codex | current | m medium: PASS 2/2" in headers, printed
