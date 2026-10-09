"""The install route: adopt installs, upgrades, checks and removes through one safe writer.

Every target is a Git repository under `tmp_path`, and every assertion is about bytes on
disk, the manifest or an exit status, never about a sentence adopt prints; the printed things
read are the footprint's figure, the nested byte warning, the finish check's statement per
harness, the `kept` line and the claims plan warning, which exist only as output.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest

from outcomebound_tools import adopt, facts, fileplan, finish_check, fragments, identity, paths
from outcomebound_tools.declared_tests import PYTEST
from tests.adopt_helpers import (
    GIT,
    ROOT,
    Capture,
    change_kernel,
    engine_copy,
    manifest,
    repo,
    run,
    snapshot,
    states,
)
from tests.portable import WINDOWS, engine, needs_symlinks, write
from tests.processes import running

VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
CLAUDE_SKILL = ".claude/skills/using-outcomebound/SKILL.md"
CLAUDE_BRIEF = ".claude/skills/decision-brief/SKILL.md"
# One `skill` record per file of each skill an install carries, for each harness directory.
SKILL_FILES = sorted(
    p.relative_to(ROOT / "skills").as_posix()
    for name in adopt.SKILLS
    for p in (ROOT / "skills" / name).rglob("*")
    if p.is_file()
)
SKILL_RECORDS = ["skill"] * len(SKILL_FILES)
GENERIC_SKILL = ".outcomebound/skills/using-outcomebound/SKILL.md"
PYTHON_FRAGMENT = ".outcomebound/fragments/python.md"
LAUNCHER = ROOT / "scripts" / "outcomebound"


def commit_all(target: Path) -> None:
    """Commit what `target` holds, so that it has a HEAD commit."""

    identity = ["-c", "user.name=t", "-c", "user.email=t@example.com"]
    subprocess.run([GIT, "-C", str(target), "add", "-A"], check=True)
    subprocess.run(
        [GIT, "-C", str(target), *identity, "commit", "-q", "--allow-empty", "-m", "c"], check=True
    )


def blocks(target: Path, name: str) -> dict[str, identity.ManagedBlock]:
    text = (target / name).read_text(encoding="utf-8")
    return {block.block_id: block for block in identity.find_managed_blocks(text)}


def next_lines(out: str) -> list[str]:
    return [line for line in out.splitlines() if line.startswith("next: ")]


def kinds(target: Path) -> list[str]:
    return [record["kind"] for record in manifest(target)["artifacts"]]


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# --- install ----------------------------------------------------------------------


def test_a_fresh_install_writes_the_contract_facts_pointers_skills_and_import(
    tmp_path: Path, capsys: Capture
) -> None:
    files = {"README.md": "# T\n", "pyproject.toml": "[project]\n", "CLAUDE.md": "# Notes\n"}
    target = repo(tmp_path / "t", files)

    code, _, err = run(capsys, str(target), "--harness", "claude-code", "--fragments", "python")

    assert code == 0, err
    agents = blocks(target, "AGENTS.md")
    assert list(agents) == [adopt.KERNEL, adopt.FACTS, adopt.POINTERS]
    assert agents[adopt.KERNEL].version == VERSION
    shipped = (ROOT / "fragments/stack/python.md").read_bytes()
    assert (target / PYTHON_FRAGMENT).read_bytes() == shipped
    assert list(blocks(target, "CLAUDE.md")) == ["pointer-claude-md"]
    assert adopt.IMPORT in (target / "CLAUDE.md").read_text(encoding="utf-8").splitlines()
    skill = (ROOT / "skills/using-outcomebound/SKILL.md").read_bytes()
    brief = (ROOT / "skills/decision-brief/SKILL.md").read_bytes()
    assert (target / CLAUDE_SKILL).read_bytes() == skill
    assert (target / CLAUDE_BRIEF).read_bytes() == brief
    assert (target / "README.md").read_text(encoding="utf-8") == "# T\n"

    document = manifest(target)
    assert (document["format_version"], document["engine_version"]) == (2, VERSION)
    records = document["artifacts"]
    assert [(r["kind"], r["path"], r["id"]) for r in records] == [
        ("block", "AGENTS.md", adopt.KERNEL),
        ("block", "AGENTS.md", adopt.FACTS),
        ("block", "AGENTS.md", adopt.POINTERS),
        ("fragment", PYTHON_FRAGMENT, "python"),
        ("ignore", adopt.LOCAL_IGNORE, adopt.LOCAL_RECORDS),
        ("pointer", "CLAUDE.md", "pointer-claude-md"),
        ("skill", CLAUDE_BRIEF, "decision-brief"),
        ("skill", ".claude/skills/diagnose/SKILL.md", "diagnose"),
        ("skill", ".claude/skills/explain-spec/SKILL.md", "explain-spec"),
        ("skill", ".claude/skills/explorable/SKILL.md", "explorable"),
        ("skill", ".claude/skills/explorable/references/runtime.md", "explorable"),
        ("skill", ".claude/skills/gather-requirements/SKILL.md", "gather-requirements"),
        ("skill", ".claude/skills/hand-off-tickets/SKILL.md", "hand-off-tickets"),
        ("skill", ".claude/skills/review-findings/SKILL.md", "review-findings"),
        ("skill", ".claude/skills/slice-tickets/SKILL.md", "slice-tickets"),
        ("skill", ".claude/skills/slice-tickets/references/github.md", "slice-tickets"),
        ("skill", ".claude/skills/tests-worth-keeping/SKILL.md", "tests-worth-keeping"),
        ("skill", CLAUDE_SKILL, "using-outcomebound"),
        (
            "skill",
            ".claude/skills/using-outcomebound/references/lifecycle.md",
            "using-outcomebound",
        ),
        (
            "skill",
            ".claude/skills/using-outcomebound/references/new-project.md",
            "using-outcomebound",
        ),
    ]
    assert records[1]["fragments"] == ["python"]
    assert records[6]["harnesses"] == records[7]["harnesses"] == ["claude-code"]
    for record in records:
        assert adopt.state(target, ROOT, record, records) == "current"
    assert (records[6]["sha256"], records[-3]["sha256"]) == (sha(brief), sha(skill))
    assert records[3]["sha256"] == sha(shipped)


def outside_git(path: Path) -> Path:
    """A folder no Git work tree holds; where pytest's temporary folders sit inside one, the
    refusal cannot be shown here and the test says so."""

    if any((directory / ".git").exists() for directory in (path, *path.parents)):
        pytest.skip("UNVERIFIED: the temporary folder is inside a Git work tree")
    return path


def test_a_dry_run_and_a_target_outside_git_write_nothing(tmp_path: Path, capsys: Capture) -> None:
    target = repo(tmp_path / "t", {"README.md": "# T\n"})
    before = snapshot(target)
    code, out, _ = run(capsys, str(target), "--harness", "claude-code", "--dry-run")
    assert code == 0 and "AGENTS.md" in out
    assert snapshot(target) == before

    loose = outside_git(tmp_path) / "loose"
    loose.mkdir()
    code, _, _ = run(capsys, str(loose), "--harness", "codex")
    assert code == 1
    assert list(loose.iterdir()) == []


def test_re_running_the_same_install_changes_no_byte(tmp_path: Path, capsys: Capture) -> None:
    target = repo(tmp_path / "t", {"README.md": "# T\n", "CLAUDE.md": "# Notes\n"})
    arguments = (str(target), "--harness", "claude-code,codex", "--fragments", "python")
    assert run(capsys, *arguments)[0] == 0
    before = snapshot(target)
    written = (target / adopt.MANIFEST).stat().st_mtime_ns

    assert run(capsys, *arguments)[0] == 0
    assert run(capsys, str(target))[0] == 0  # omitted flags keep the recorded selection

    assert snapshot(target) == before
    assert (target / adopt.MANIFEST).stat().st_mtime_ns == written


def test_an_upgrade_rewrites_what_the_changed_source_renders_and_nothing_else(
    tmp_path: Path, capsys: Capture
) -> None:
    source = engine_copy(tmp_path)
    own = "# Project\n\nOur own rules.\n"
    target = repo(tmp_path / "t", {"AGENTS.md": own, "pyproject.toml": "[project]\n"})
    arguments = (str(target), "--harness", "claude-code", "--fragments", "python")
    assert run(capsys, *arguments, source=source)[0] == 0
    pointers = adopt.block_text((target / "AGENTS.md").read_text(encoding="utf-8"), adopt.POINTERS)
    change_kernel(source, "9.9.9")

    code, out, _ = run(capsys, str(target), "--check", source=source)
    assert code == 1
    assert states(out)[f"AGENTS.md ({adopt.KERNEL})"] == "stale"

    code, _, err = run(capsys, str(target), source=source)

    assert code == 0, err
    agents = blocks(target, "AGENTS.md")
    assert agents[adopt.KERNEL].version == "9.9.9"
    assert "not least work, now." in agents[adopt.KERNEL].body
    assert adopt.block_text((target / "AGENTS.md").read_text(encoding="utf-8"), adopt.POINTERS) == (
        pointers
    )
    assert (target / "AGENTS.md").read_text(encoding="utf-8").endswith("\n\n" + own)
    assert manifest(target)["engine_version"] == "9.9.9"
    code, out, _ = run(capsys, str(target), "--check", source=source)
    assert code == 0 and set(states(out).values()) == {"current"}


def test_an_install_of_the_core_skill_alone_gains_the_other_core_skills_on_upgrade(
    tmp_path: Path, capsys: Capture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An engine that carried only the core skill recorded one skill per harness; the next
    run adds each other skill every install carries beside it, with its pointer line, and
    changes no other file."""

    target = repo(tmp_path / "t", {"README.md": "# T\n"})
    with monkeypatch.context() as patch:
        patch.setattr(adopt.fragments, "SKILLS", ("using-outcomebound",))
        assert run(capsys, str(target), "--harness", "claude-code")[0] == 0
    before = snapshot(target)
    gained = {name: f".claude/skills/{name}/SKILL.md" for name in adopt.SKILLS[1:]}
    assert CLAUDE_BRIEF in gained.values()
    assert not set(gained.values()) & set(before)

    code, _, err = run(capsys, str(target))

    assert code == 0, err
    after = snapshot(target)
    for name, path in gained.items():
        assert after.pop(path) == (ROOT / "skills" / name / "SKILL.md").read_bytes()
    assert after.pop(adopt.MANIFEST) != before.pop(adopt.MANIFEST)
    old = adopt.block_text(before.pop("AGENTS.md").decode("utf-8"), adopt.POINTERS) or b""
    added = [f"- {adopt.CONDITIONS[name]}: read {path}" for name, path in gained.items()]
    assert blocks(target, "AGENTS.md")[adopt.POINTERS].body.splitlines() == [
        *old.decode("utf-8").splitlines()[1:-1],
        *added,
    ]
    after.pop("AGENTS.md")
    after.pop(".claude/skills/slice-tickets/references/github.md")
    after.pop(".claude/skills/explorable/references/runtime.md")
    assert after == before
    code, out, _ = run(capsys, str(target), "--check")
    assert code == 0 and all(states(out)[path] == "current" for path in gained.values())


def test_a_brief_skill_the_target_already_holds_is_refused_unless_forced(
    tmp_path: Path, capsys: Capture
) -> None:
    target = repo(tmp_path / "t", {CLAUDE_BRIEF: "---\nname: decision-brief\n---\nOurs.\n"})
    before = snapshot(target)

    code, _, err = run(capsys, str(target), "--harness", "claude-code")

    assert code == 1 and CLAUDE_BRIEF in err
    assert snapshot(target) == before
    assert run(capsys, str(target), "--harness", "claude-code", "--force")[0] == 0
    brief = (ROOT / "skills/decision-brief/SKILL.md").read_bytes()
    assert (target / CLAUDE_BRIEF).read_bytes() == brief


def test_an_edited_owned_block_is_refused_and_force_replaces_it(
    tmp_path: Path, capsys: Capture
) -> None:
    target = repo(tmp_path / "t")
    assert run(capsys, str(target), "--harness", "codex")[0] == 0
    agents = target / "AGENTS.md"
    edited = agents.read_text(encoding="utf-8").replace("Smallest complete", "Largest complete")
    write(agents, edited)

    code, _, err = run(capsys, str(target))

    assert code == 1 and "AGENTS.md" in err
    assert agents.read_text(encoding="utf-8") == edited

    code, _, err = run(capsys, str(target), "--force")

    assert code == 0, err
    kernel = adopt.kernel_block(ROOT).encode()
    assert adopt.block_text(agents.read_text(encoding="utf-8"), adopt.KERNEL) == kernel


DISTINGUISH = "**Distinguish** — the states that must not impersonate each other in this project."


def kept(out: str) -> list[str]:
    """The labels an install's report names as recorded without --force."""

    return [
        line.split(None, 1)[1].split(": ", 1)[0]
        for line in out.splitlines()
        if line.startswith("kept ")
    ]


def edit_local(target: Path, fragment: str, block: str) -> str:
    """Change the local fragment's Distinguish line to `fragment` and the same line in the
    installed pointers block to `block`; returns AGENTS.md as edited."""

    local = target / adopt.LOCAL_FRAGMENT
    write(local, local.read_text(encoding="utf-8").replace(DISTINGUISH, fragment))
    agents = target / "AGENTS.md"
    text = agents.read_text(encoding="utf-8")
    assert text.count(DISTINGUISH) == 1
    write(agents, text.replace(DISTINGUISH, block))
    return agents.read_text(encoding="utf-8")


def test_a_block_edited_to_what_this_install_writes_needs_no_force(
    tmp_path: Path, capsys: Capture
) -> None:
    """The reported case: a commit changes the local fragment and makes the same change in the
    pointers block it renders. Breaks if `--check` calls the block edited and sends the person
    to --force, if the install refuses it or says nothing, or if the manifest keeps the old
    digest, so that the next change to the fragment would read as an edit."""

    target = repo(tmp_path / "t", {adopt.LOCAL_FRAGMENT: local_fragment()})
    assert run(capsys, str(target), "--fragments", "local")[0] == 0
    commit_all(target)
    line = "**Distinguish** — committed ≠ pushed in this project."
    edited = edit_local(target, line, line)
    pointers = f"AGENTS.md ({adopt.POINTERS})"

    code, out, _ = run(capsys, str(target), "--check")

    assert code == 1 and states(out)[pointers] == "stale"
    assert f"stale    {pointers}: {adopt.UNRECORDED}" in out.splitlines()
    assert next_lines(out) == [
        f"next: outcomebound adopt {paths.shell_path(target)} makes every record current"
    ]

    code, out, err = run(capsys, str(target))

    assert code == 0, err
    assert kept(out) == [pointers]
    assert (target / "AGENTS.md").read_text(encoding="utf-8") == edited
    code, out, _ = run(capsys, str(target), "--check")
    assert code == 0 and set(states(out).values()) == {"current"}


def test_a_block_edit_that_differs_from_what_this_install_writes_still_needs_force(
    tmp_path: Path, capsys: Capture
) -> None:
    """The negative control: the block's edit is not the fragment's. Breaks if any edit to a
    recorded block is taken without --force."""

    target = repo(tmp_path / "t", {adopt.LOCAL_FRAGMENT: local_fragment()})
    assert run(capsys, str(target), "--fragments", "local")[0] == 0
    fragment = "**Distinguish** — committed ≠ pushed in this project."
    edited = edit_local(target, fragment, "**Distinguish** — my own words, not the fragment's.")
    pointers = f"AGENTS.md ({adopt.POINTERS})"

    code, out, _ = run(capsys, str(target), "--check")

    assert code == 1 and states(out)[pointers] == "edited"

    code, _, err = run(capsys, str(target))

    assert code == 1
    assert f"{pointers} differs from what adopt wrote; restore it, or pass --force" in err
    assert (target / "AGENTS.md").read_text(encoding="utf-8") == edited


COMMANDS_CONDITION = "when running a command whose output you read"


def without_frame(target: Path) -> None:
    """Rewrite the target's manifest as an engine of 1.1.1 or earlier writes it: no `frame` in
    any record."""

    document = manifest(target)
    for record in document["artifacts"]:
        record.pop("frame", None)
    write(target / adopt.MANIFEST, json.dumps(document, indent=2) + "\n")


def render_anew(source: Path) -> None:
    """Change the engine copy as a release that renders the pointers block anew would: the
    commands fragment's condition, which its pointer line carries, in other words."""

    path = source / "fragments/setup/commands.md"
    text = path.read_text(encoding="utf-8")
    assert text.count(COMMANDS_CONDITION) == 1
    write(path, text.replace(COMMANDS_CONDITION, f"{COMMANDS_CONDITION} later"))


def rendered_lines(out: str) -> list[str]:
    """The labels an install's report names as rendered again from their source's edit."""

    return [
        line.split(None, 1)[1].split(": ", 1)[0]
        for line in out.splitlines()
        if line.startswith("render ")
    ]


def test_an_install_records_the_pointers_frame(tmp_path: Path, capsys: Capture) -> None:
    """Breaks if the manifest is not format 2, or if the pointers record does not hold the
    digest of its block with the local fragment's inline text replaced by the mark, or holds one
    where no local fragment is selected."""

    target = repo(tmp_path / "t", {adopt.LOCAL_FRAGMENT: local_fragment()})
    assert run(capsys, str(target), "--fragments", "local,commands")[0] == 0

    document = manifest(target)
    assert document["format_version"] == 2
    (record,) = [r for r in document["artifacts"] if r["id"] == adopt.POINTERS]
    text = (target / "AGENTS.md").read_text(encoding="utf-8")
    block = adopt.block_text(text, adopt.POINTERS)
    assert block is not None
    local = fragments.parse_fragment(local_fragment(), adopt.LOCAL_FRAGMENT)
    inline = facts.inline(local)
    assert block.decode("utf-8").count(inline) == 1
    framed = block.decode("utf-8").replace(inline, "\0local\0")
    assert record["frame"] == sha(framed.encode("utf-8"))

    assert run(capsys, str(target), "--fragments", "commands")[0] == 0
    (record,) = [r for r in manifest(target)["artifacts"] if r["id"] == adopt.POINTERS]
    assert "frame" not in record


def test_a_record_without_a_frame_is_read_and_the_install_adds_the_frame(
    tmp_path: Path, capsys: Capture
) -> None:
    """An install an engine of 1.1.1 or earlier rewrote, with no `frame`: `--check` reads it
    current, and the next install adds the frame and changes nothing else. Breaks if a record
    without the frame is refused, or if the install does not add it."""

    target = repo(tmp_path / "t", {adopt.LOCAL_FRAGMENT: local_fragment()})
    assert run(capsys, str(target), "--fragments", "local,commands")[0] == 0
    written = manifest(target)
    without_frame(target)

    code, out, _ = run(capsys, str(target), "--check")
    assert code == 0 and set(states(out).values()) == {"current"}, out

    assert run(capsys, str(target))[0] == 0
    (record,) = [r for r in manifest(target)["artifacts"] if r["id"] == adopt.POINTERS]
    assert "frame" in record
    assert manifest(target) == written


@pytest.mark.parametrize("recorded", ["frame", "no-frame"])
def test_a_block_with_only_the_local_fragments_edit_needs_no_force_when_the_release_renders_anew(
    tmp_path: Path, capsys: Capture, recorded: str
) -> None:
    """The case that needed --force: the local fragment and its pointers block are edited the
    same way, and the release renders the block anew, so the block is neither its record nor
    this install's render. A record with a frame decides it by the frame, with no Git
    history; a record without one by the fragment's earlier text in Git. Breaks if `--check`
    reads the block edited, if the install refuses it or does not name it, or if the edit is
    lost."""

    source = engine_copy(tmp_path)
    target = repo(tmp_path / "t", {adopt.LOCAL_FRAGMENT: local_fragment()})
    assert run(capsys, str(target), "--fragments", "local,commands", source=source)[0] == 0
    if recorded == "no-frame":
        without_frame(target)
        commit_all(target)
    line = "**Distinguish** — committed ≠ pushed in this project."
    edit_local(target, line, line)
    render_anew(source)
    pointers = f"AGENTS.md ({adopt.POINTERS})"

    code, out, _ = run(capsys, str(target), "--check", source=source)

    assert states(out)[pointers] == "stale", out
    assert f"stale    {pointers}: {adopt.FROM_SOURCE}" in out.splitlines()
    assert next_lines(out) == [
        f"next: outcomebound adopt {paths.shell_path(target)} makes every record current"
    ]

    code, out, err = run(capsys, str(target), source=source)

    assert code == 0, err
    assert rendered_lines(out) == [pointers]
    text = (target / "AGENTS.md").read_text(encoding="utf-8")
    assert line in text and f"{COMMANDS_CONDITION} later" in text
    code, out, _ = run(capsys, str(target), "--check", source=source)
    assert code == 0 and set(states(out).values()) == {"current"}, out


@pytest.mark.parametrize("shape", ["frame-edited", "no-frame-no-history"])
def test_a_block_that_is_not_only_the_local_fragments_edit_still_needs_force(
    tmp_path: Path, capsys: Capture, shape: str
) -> None:
    """The negative controls: the block holds an edit beside the fragment's (`frame-edited`),
    or the record has no frame and Git holds no earlier text of the fragment
    (`no-frame-no-history`). Breaks if either is rendered again without --force."""

    source = engine_copy(tmp_path)
    target = repo(tmp_path / "t", {adopt.LOCAL_FRAGMENT: local_fragment()})
    assert run(capsys, str(target), "--fragments", "local,commands", source=source)[0] == 0
    line = "**Distinguish** — committed ≠ pushed in this project."
    edited = edit_local(target, line, line)
    if shape == "frame-edited":
        agents = target / "AGENTS.md"
        edited = edited.replace("- when writing, changing or judging a test", "- when testing")
        write(agents, edited)
    else:
        without_frame(target)
    render_anew(source)
    pointers = f"AGENTS.md ({adopt.POINTERS})"

    code, out, _ = run(capsys, str(target), "--check", source=source)
    assert states(out)[pointers] == "edited", out

    code, _, err = run(capsys, str(target), source=source)

    assert code == 1
    assert f"{pointers} differs from what adopt wrote; restore it, or pass --force" in err
    assert (target / "AGENTS.md").read_text(encoding="utf-8") == edited


@pytest.mark.parametrize("folder", ["", "component"])
def test_the_local_fragments_history_is_read_where_the_install_is_a_subfolder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, folder: str
) -> None:
    """A component with its own install in a subfolder of a larger work tree reads the local
    fragment's earlier texts as an install at the work tree's root does, whatever folder adopt
    runs from. Breaks if the commits are listed by the target's path but their blobs are read
    by the root's."""

    work_tree = repo(tmp_path / "w", {"README.md": "# Work tree\n"})
    target = work_tree / folder
    local = target / adopt.LOCAL_FRAGMENT
    local.parent.mkdir(parents=True)
    first = local_fragment()
    write(local, first)
    commit_all(work_tree)
    second = first.replace(DISTINGUISH, "**Distinguish** — committed ≠ pushed here.")
    assert second != first
    write(local, second)
    commit_all(work_tree)
    monkeypatch.chdir(tmp_path)

    assert adopt.local_history(target) == [second, first]


def test_a_file_edited_to_what_this_install_writes_needs_no_force(
    tmp_path: Path, capsys: Capture
) -> None:
    """A skill file holding what the next release ships, put there before the upgrade, is no
    edit, as a block is not; one holding anything else still refuses. Breaks if files and
    blocks are judged by different rules."""

    source = engine_copy(tmp_path)
    target = repo(tmp_path / "t")
    assert run(capsys, str(target), source=source)[0] == 0
    shipped = source / "skills/decision-brief/SKILL.md"
    write(shipped, shipped.read_text(encoding="utf-8") + "\nOne more line.\n")
    skill = ".outcomebound/skills/decision-brief/SKILL.md"
    write(target / skill, "mine\n")

    code, _, err = run(capsys, str(target), source=source)

    assert code == 1
    assert f"{skill} differs from what adopt wrote; restore it, or pass --force" in err

    (target / skill).write_bytes(shipped.read_bytes())
    code, out, _ = run(capsys, str(target), "--check", source=source)
    assert states(out)[skill] == "stale"

    code, out, err = run(capsys, str(target), source=source)

    assert code == 0, err
    assert kept(out) == [skill]
    assert (target / skill).read_bytes() == shipped.read_bytes()


def test_a_manifest_of_another_format_is_refused_even_when_forced(
    tmp_path: Path, capsys: Capture
) -> None:
    record = {"id": "managed-block:operating-contract", "kind": "managed-block"}
    old = {"format_version": 1, "artifacts": [record]}
    target = repo(tmp_path / "t", {".outcomebound/manifest.json": json.dumps(old)})
    before = snapshot(target)

    for extra in ((), ("--force",)):
        assert run(capsys, str(target), "--harness", "codex", *extra)[0] == 1
        assert snapshot(target) == before


def test_agents_md_ending_inside_an_open_code_fence_is_refused(
    tmp_path: Path, capsys: Capture
) -> None:
    target = repo(tmp_path / "t", {"AGENTS.md": "# Notes\n\n```sh\nmake test\n"})
    before = snapshot(target)

    assert run(capsys, str(target), "--harness", "codex")[0] == 1
    assert snapshot(target) == before


def test_an_install_reports_the_words_it_always_loads_and_refuses_no_size(
    tmp_path: Path, capsys: Capture
) -> None:
    """One `words` line sums the blocks an agent always loads, sentinels included: the
    operating contract, the facts, the pointers with the local fragment inline, and the
    import block, never a skill or a fragment file. An upgrade that changes nothing reports
    it too, and no size refuses."""

    target = repo(tmp_path / "t", {"CLAUDE.md": "# Notes\n"})
    local = (ROOT / "templates/fragment-local.md").read_text(encoding="utf-8")
    padded = local.replace("**Context** —", "**Context** —" + " word" * 20_000)
    (target / adopt.LOCAL_FRAGMENT).parent.mkdir(parents=True)
    write(target / adopt.LOCAL_FRAGMENT, padded)
    arguments = (str(target), "--harness", "claude-code", "--fragments", "local")

    code, out, err = run(capsys, *arguments)

    assert code == 0, err
    placed = [("AGENTS.md", name) for name in (adopt.KERNEL, adopt.FACTS, adopt.POINTERS)]
    placed.append(("CLAUDE.md", "pointer-claude-md"))
    words = [
        len((adopt.block_text((target / path).read_text(encoding="utf-8"), name) or b"").split())
        for path, name in placed
    ]
    assert words[2] > 20_000
    listed = [
        len(adopt.description((ROOT / "skills" / name / "SKILL.md").read_bytes()).split())
        for name in adopt.SKILLS
    ]
    assert all(listed)
    for printed in (out, run(capsys, *arguments)[1]):
        figures = [line.split()[1] for line in printed.splitlines() if line.startswith("words ")]
        assert figures == [str(sum(words) + sum(listed))]


# --- harnesses --------------------------------------------------------------------


def test_claude_code_on_a_target_with_no_claude_md_gets_no_file(
    tmp_path: Path, capsys: Capture
) -> None:
    """Claude Code 2.1.281 and later reads AGENTS.md itself where the target has no CLAUDE.md,
    .claude/CLAUDE.md or CLAUDE.local.md, so adopt writes no import block there."""

    target = repo(tmp_path / "t", {"README.md": "# T\n"})

    code, _, err = run(capsys, str(target), "--harness", "claude-code")

    assert code == 0, err
    assert not (target / "CLAUDE.md").exists()
    assert kinds(target) == ["block", "block", "block", "ignore", *SKILL_RECORDS]
    assert "CLAUDE.md" not in facts_lines(target)["Precedence"]
    code, out, _ = run(capsys, str(target), "--check")
    assert code == 0 and set(states(out).values()) == {"current"}


def test_a_claude_md_in_a_folder_above_brings_the_import_block_back(
    tmp_path: Path, capsys: Capture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A CLAUDE.md above the target stops Claude Code reading AGENTS.md there too, so the
    import block is written; the person's own ~/.claude/CLAUDE.md is user memory and does not."""

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    (tmp_path / ".claude").mkdir()
    write(tmp_path / ".claude" / "CLAUDE.md", "# Mine\n")
    plain = repo(tmp_path / "plain")
    assert run(capsys, str(plain), "--harness", "claude-code")[0] == 0
    assert not (plain / "CLAUDE.md").exists()

    (tmp_path / "work").mkdir()
    write(tmp_path / "work" / "CLAUDE.md", "# Team\n")
    below = repo(tmp_path / "work" / "t")
    assert run(capsys, str(below), "--harness", "claude-code")[0] == 0
    assert "@AGENTS.md" in (below / "CLAUDE.md").read_text(encoding="utf-8")


@needs_symlinks
@pytest.mark.parametrize("seeded", ["CLAUDE.md", ".claude/CLAUDE.md", "CLAUDE.local.md", "link"])
def test_each_file_that_hides_agents_md_brings_the_import_block_back(
    tmp_path: Path, capsys: Capture, seeded: str
) -> None:
    """Any one of them makes Claude Code read CLAUDE.md files only, so the import block goes
    into CLAUDE.md, created where absent. A dangling CLAUDE.local.md link (`link`) is still a
    file Claude Code finds, and the file that hid AGENTS.md is left as it was."""

    target = repo(tmp_path / "t")
    if seeded == "link":
        (target / "CLAUDE.local.md").symlink_to("missing.md")
    else:
        (target / seeded).parent.mkdir(parents=True, exist_ok=True)
        write(target / seeded, "# Mine\n")
    before = {path: data for path, data in snapshot(target).items() if path != "CLAUDE.md"}

    code, _, err = run(capsys, str(target), "--harness", "claude-code")

    assert code == 0, err
    assert list(blocks(target, "CLAUDE.md")) == ["pointer-claude-md"]
    assert {path: snapshot(target)[path] for path in before} == before
    assert kinds(target) == ["block", "block", "block", "ignore", "pointer", *SKILL_RECORDS]


def test_an_import_block_an_older_engine_wrote_is_kept_until_its_file_is_gone(
    tmp_path: Path, capsys: Capture
) -> None:
    """An upgrade changes no byte of a CLAUDE.md that an engine without the rule wrote. Once
    the project deletes it, the next run drops its record and writes it no more."""

    source = engine_copy(tmp_path)
    table_path = source / "adapters/harnesses.json"
    table = json.loads(table_path.read_text(encoding="utf-8"))
    table["claude-code"]["reads_agents_md"] = None  # an engine without the rule
    write(table_path, json.dumps(table))
    target = repo(tmp_path / "t")
    assert run(capsys, str(target), "--harness", "claude-code", source=source)[0] == 0
    before = snapshot(target)
    assert "CLAUDE.md" in before

    assert run(capsys, str(target))[0] == 0
    assert snapshot(target) == before

    (target / "CLAUDE.md").unlink()
    code, _, err = run(capsys, str(target))

    assert code == 0, err
    assert not (target / "CLAUDE.md").exists()
    assert kinds(target) == ["block", "block", "block", "ignore", *SKILL_RECORDS]
    code, out, _ = run(capsys, str(target), "--check")
    assert code == 0 and set(states(out).values()) == {"current"}


def test_the_rule_is_the_tables_and_a_host_shared_without_it_keeps_its_import(
    tmp_path: Path, capsys: Capture
) -> None:
    """Any row gains the rule by data alone; a host is left out only when every harness that
    routes through it shares one rule."""

    source = engine_copy(tmp_path)
    table_path = source / "adapters/harnesses.json"
    table = json.loads(table_path.read_text(encoding="utf-8"))
    table["gemini"]["reads_agents_md"] = {"unless": ["GEMINI.md"], "since": "9.9"}
    table["probe"] = {**table["gemini"], "skill_install_path": ".probe/skills/"}
    table["probe"]["reads_agents_md"] = None
    write(table_path, json.dumps(table))
    alone, shared = repo(tmp_path / "alone"), repo(tmp_path / "shared")

    assert run(capsys, str(alone), "--harness", "gemini", source=source)[0] == 0
    assert run(capsys, str(shared), "--harness", "gemini,probe", source=source)[0] == 0

    assert not (alone / "GEMINI.md").exists()
    assert list(blocks(shared, "GEMINI.md")) == ["pointer-gemini-md"]


@needs_symlinks
def test_a_claude_md_link_or_import_line_already_loads_agents_md(
    tmp_path: Path, capsys: Capture
) -> None:
    linked = repo(tmp_path / "linked", {"AGENTS.md": "# P\n"})
    (linked / "CLAUDE.md").symlink_to("AGENTS.md")
    imported = repo(tmp_path / "imported", {"CLAUDE.md": "# Notes\n\n@AGENTS.md\n"})

    for target in (linked, imported):
        code, _, err = run(capsys, str(target), "--harness", "claude-code")
        assert code == 0, err
        assert kinds(target) == ["block", "block", "block", "ignore", *SKILL_RECORDS]
    assert os.readlink(linked / "CLAUDE.md") == "AGENTS.md"
    assert (imported / "CLAUDE.md").read_text(encoding="utf-8") == "# Notes\n\n@AGENTS.md\n"


@needs_symlinks
def test_an_import_block_whose_file_became_a_link_is_dropped_not_followed(
    tmp_path: Path, capsys: Capture
) -> None:
    target = repo(tmp_path / "t", {"CLAUDE.md": "# Notes\n"})
    assert run(capsys, str(target), "--harness", "claude-code")[0] == 0
    (target / "CLAUDE.md").unlink()
    (target / "CLAUDE.md").symlink_to("AGENTS.md")

    code, _, err = run(capsys, str(target))

    assert code == 0, err
    assert os.readlink(target / "CLAUDE.md") == "AGENTS.md"
    assert kinds(target) == ["block", "block", "block", "ignore", *SKILL_RECORDS]


def test_a_plain_claude_md_gets_the_import_block_above_its_own_text(
    tmp_path: Path, capsys: Capture
) -> None:
    fenced = "# Notes\n\n```\n@AGENTS.md\n```\n"  # an example in a fence imports nothing
    target = repo(tmp_path / "t", {"CLAUDE.md": fenced})

    assert run(capsys, str(target), "--harness", "claude-code")[0] == 0

    text = (target / "CLAUDE.md").read_text(encoding="utf-8")
    pointer = adopt.pointer_block("CLAUDE.md")
    assert text == pointer + "\n\n" + fenced
    assert adopt.IMPORT in pointer.splitlines()


def test_repeated_harness_flags_accumulate_and_naming_fewer_drops_the_rest(
    tmp_path: Path, capsys: Capture
) -> None:
    target = repo(tmp_path / "t", {"README.md": "# T\n"})
    code, _, err = run(capsys, str(target), "--harness", "claude-code", "--harness", "codex,cursor")
    assert code == 0, err
    skills = {
        r["path"]: r["harnesses"] for r in manifest(target)["artifacts"] if r["kind"] == "skill"
    }
    assert skills == {
        f"{root}/skills/{file}": [harness]
        for root, harness in (
            (".agents", "codex"),
            (".claude", "claude-code"),
            (".cursor", "cursor"),
        )
        for file in SKILL_FILES
    }

    assert run(capsys, str(target), "--harness", "codex")[0] == 0

    assert not (target / ".claude").exists() and not (target / ".cursor").exists()
    assert not (target / "CLAUDE.md").exists()
    for name in adopt.SKILLS:
        assert (target / f".agents/skills/{name}/SKILL.md").is_file()
    assert kinds(target) == ["block", "block", "block", "ignore", *SKILL_RECORDS]


@pytest.mark.parametrize("row", [None, {"verified": True, "pointer_mechanism": "RULES.md"}])
def test_a_harness_that_cannot_load_agents_md_is_refused_before_any_write(
    tmp_path: Path, capsys: Capture, row: dict[str, Any] | None
) -> None:
    source = engine_copy(tmp_path)
    table_path = source / "adapters/harnesses.json"
    table = json.loads(table_path.read_text(encoding="utf-8"))
    table["probe"] = (
        {"verified": False, "pointer_mechanism": "AGENTS.md"} if row is None else dict(row)
    )
    table["probe"]["skill_install_path"] = ".probe/skills/"
    write(table_path, json.dumps(table))
    target = repo(tmp_path / "t", {"README.md": "# T\n"})
    before = snapshot(target)

    code, _, err = run(capsys, str(target), "--harness", "claude-code,probe,nope", source=source)

    assert code == 1
    assert "probe" in err and "nope" in err
    assert snapshot(target) == before


@needs_symlinks
def test_a_claude_md_link_elsewhere_is_refused_before_any_write(
    tmp_path: Path, capsys: Capture
) -> None:
    target = repo(tmp_path / "t", {"docs/claude.md": "# Elsewhere\n"})
    (target / "CLAUDE.md").symlink_to("docs/claude.md")
    before = snapshot(target)

    code, _, err = run(capsys, str(target), "--harness", "claude-code")

    assert code == 1 and "CLAUDE.md" in err
    assert snapshot(target) == before


# --- the manifest -----------------------------------------------------------------


def test_records_of_other_routes_are_kept_in_order_through_install_and_remove(
    tmp_path: Path, capsys: Capture
) -> None:
    foreign: list[dict[str, Any]] = [
        {"kind": "floor-v1", "id": "floor:profile", "path": "floor.json", "z": 1, "a": [2]},
        {"kind": "block", "id": "floor-guidance", "path": "AGENTS.md", "sha256": "b" * 64},
    ]
    document = {"format_version": 2, "engine_version": "0.1", "floor": {"on": True}}
    document["artifacts"] = foreign
    target = repo(tmp_path / "t", {".outcomebound/manifest.json": json.dumps(document, indent=2)})

    assert run(capsys, str(target), "--harness", "codex")[0] == 0

    after = manifest(target)
    assert after["artifacts"][-2:] == foreign
    assert [list(record) for record in after["artifacts"][-2:]] == [list(r) for r in foreign]
    assert after["floor"] == {"on": True}

    assert run(capsys, str(target), "--remove")[0] == 0

    assert manifest(target)["artifacts"] == foreign


def test_a_fragment_record_never_owns_the_projects_local_fragment(
    tmp_path: Path, capsys: Capture
) -> None:
    local = "---\nid: local\n---\nours\n"
    target = repo(tmp_path / "t", {adopt.LOCAL_FRAGMENT: local})
    assert run(capsys, str(target), "--harness", "codex")[0] == 0
    document = manifest(target)
    record = {"kind": "fragment", "path": adopt.LOCAL_FRAGMENT, "id": adopt.LOCAL}
    document["artifacts"].append({**record, "sha256": sha(local.encode())})
    write(target / adopt.MANIFEST, json.dumps(document))

    assert run(capsys, str(target), "--remove", "--force")[0] == 0

    assert (target / adopt.LOCAL_FRAGMENT).read_text(encoding="utf-8") == local


def test_a_manifest_path_that_reaches_git_is_refused(tmp_path: Path, capsys: Capture) -> None:
    target = repo(tmp_path / "t")
    hook = target / ".git/hooks/pre-commit"
    hook.parent.mkdir(parents=True, exist_ok=True)
    hook.write_bytes(b"#!/bin/sh\n")
    record = {"kind": "skill", "path": ".GIT/hooks/pre-commit", "id": adopt.SKILLS[0]}
    record["sha256"] = sha(b"#!/bin/sh\n")
    document = {"format_version": 2, "engine_version": VERSION, "artifacts": [record]}
    (target / ".outcomebound").mkdir()
    write(target / adopt.MANIFEST, json.dumps(document))

    for arguments in (("--remove", "--force"), ("--check",), ("--harness", "codex")):
        assert run(capsys, str(target), *arguments)[0] == 1, arguments

    assert hook.read_bytes() == b"#!/bin/sh\n"


# --- check and remove -------------------------------------------------------------


def test_check_reads_each_record_as_current_edited_stale_or_missing(
    tmp_path: Path, capsys: Capture
) -> None:
    source = engine_copy(tmp_path)
    target = repo(tmp_path / "t", {"pyproject.toml": "[project]\n", "CLAUDE.md": "# Notes\n"})
    arguments = (str(target), "--harness", "claude-code", "--fragments", "python")
    assert run(capsys, *arguments, source=source)[0] == 0
    code, out, _ = run(capsys, str(target), "--check", source=source)
    assert code == 0 and set(states(out).values()) == {"current"}
    assert next_lines(out) == []

    write(target / CLAUDE_SKILL, "mine\n")
    write(target / "CLAUDE.md", "# no import any more\n")
    change_kernel(source, "9.9.9")
    brief = source / "skills/decision-brief/SKILL.md"
    write(brief, brief.read_text(encoding="utf-8") + "\nOne more line.\n")

    code, out, _ = run(capsys, str(target), "--check", source=source)

    assert code == 4
    assert states(out) == {
        f"AGENTS.md ({adopt.KERNEL})": "stale",
        f"AGENTS.md ({adopt.FACTS})": "current",
        f"AGENTS.md ({adopt.POINTERS})": "current",
        PYTHON_FRAGMENT: "current",
        adopt.LOCAL_IGNORE: "current",
        "CLAUDE.md (pointer-claude-md)": "missing",
        CLAUDE_BRIEF: "stale",
        CLAUDE_SKILL: "edited",
        ".claude/skills/diagnose/SKILL.md": "current",
        ".claude/skills/explain-spec/SKILL.md": "current",
        ".claude/skills/explorable/SKILL.md": "current",
        ".claude/skills/explorable/references/runtime.md": "current",
        ".claude/skills/gather-requirements/SKILL.md": "current",
        ".claude/skills/hand-off-tickets/SKILL.md": "current",
        ".claude/skills/review-findings/SKILL.md": "current",
        ".claude/skills/slice-tickets/SKILL.md": "current",
        ".claude/skills/slice-tickets/references/github.md": "current",
        ".claude/skills/tests-worth-keeping/SKILL.md": "current",
        ".claude/skills/using-outcomebound/references/lifecycle.md": "current",
        ".claude/skills/using-outcomebound/references/new-project.md": "current",
    }
    assert out.splitlines()[-1] == (
        "next: move each edit out of OutcomeBound's blocks and files, then "
        f"outcomebound adopt {paths.shell_path(target)} --force makes every record current"
    )


def test_check_ends_with_the_command_that_makes_each_record_current(
    tmp_path: Path, capsys: Capture
) -> None:
    source = engine_copy(tmp_path)
    target = repo(tmp_path / "t", {"CLAUDE.md": "# Notes\n"})
    assert run(capsys, str(target), "--harness", "claude-code", source=source)[0] == 0
    change_kernel(source, "9.9.9")
    (target / CLAUDE_BRIEF).unlink()

    code, out, _ = run(capsys, str(target), "--check", source=source)

    assert code == 2 and next_lines(out) == [
        f"next: outcomebound adopt {paths.shell_path(target)} makes every record current"
    ]
    assert out.splitlines()[-1] == next_lines(out)[0]
    words = shlex.split(next_lines(out)[0].removeprefix("next: ").split(" makes ")[0])
    assert words[:2] == ["outcomebound", "adopt"]
    assert run(capsys, *words[2:], source=source)[0] == 0
    code, out, _ = run(capsys, str(target), "--check", source=source)
    assert code == 0 and set(states(out).values()) == {"current"} and next_lines(out) == []


def test_check_without_a_manifest_names_the_command_that_proposes_an_install(
    tmp_path: Path, capsys: Capture
) -> None:
    target = repo(tmp_path / "t")

    code, out, _ = run(capsys, str(target), "--check")

    assert code == 1
    assert out.splitlines() == [
        f"missing  {adopt.MANIFEST}",
        f"next: outcomebound adopt {paths.shell_path(target)} --detect prints the command "
        "that installs OutcomeBound here",
    ]


def test_remove_leaves_every_byte_that_was_there_before(tmp_path: Path, capsys: Capture) -> None:
    kept = repo(
        tmp_path / "kept",
        {
            "AGENTS.md": "# Project\n\nOur rules.\n",
            "CLAUDE.md": "# Claude notes",  # no final newline
            ".claude/settings.json": "{}\n",
        },
    )
    fresh = repo(tmp_path / "fresh", {"README.md": "# T\n"})

    for target in (kept, fresh):
        before = snapshot(target)
        code, _, err = run(capsys, str(target), "--harness", "claude-code,codex", "--fragments", "")
        assert code == 0, err
        assert run(capsys, str(target), "--remove", "--dry-run")[0] == 0
        assert snapshot(target) != before

        code, _, err = run(capsys, str(target), "--remove")

        assert code == 0, err
        assert snapshot(target) == before


def test_remove_refuses_an_edited_file_unless_forced(tmp_path: Path, capsys: Capture) -> None:
    target = repo(tmp_path / "t")
    assert run(capsys, str(target), "--harness", "claude-code")[0] == 0
    write(target / CLAUDE_SKILL, "mine\n")
    before = snapshot(target)

    code, _, err = run(capsys, str(target), "--remove")

    assert code == 1 and CLAUDE_SKILL in err
    assert snapshot(target) == before
    assert run(capsys, str(target), "--remove", "--force")[0] == 0
    assert snapshot(target) == {}


# --- detect -----------------------------------------------------------------------


def test_detect_prints_one_command_that_installs(tmp_path: Path, capsys: Capture) -> None:
    target = repo(tmp_path / "t", {"CLAUDE.md": "# Notes\n", "pyproject.toml": "[project]\n"})
    before = snapshot(target)

    code, out, _ = run(capsys, str(target), "--detect")

    assert code == 0 and len(out.splitlines()) == 1
    assert snapshot(target) == before
    words = shlex.split(out)
    assert words[:3] == ["outcomebound", "adopt", target.resolve().as_posix()]
    assert words[words.index("--harness") + 1] == "claude-code"
    assert words[words.index("--fragments") + 1] == "python,commands"
    assert run(capsys, *words[2:])[0] == 0
    assert (target / "AGENTS.md").is_file()


def test_detect_proposes_the_test_command_ci_runs(tmp_path: Path, capsys: Capture) -> None:
    """Where the project's CI names its tests, Done is that command, not discovery's guess."""

    workflow = "jobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - run: pytest -q\n"
    files = {"pyproject.toml": "[project]\n", ".github/workflows/ci.yml": workflow}
    target = repo(tmp_path / "t", files)

    code, out, _ = run(capsys, str(target), "--detect")

    words = shlex.split(out, comments=True)
    assert code == 0 and words[words.index("--done") + 1] == "pytest -q"


@pytest.mark.parametrize("discovered", [False, True])
def test_detect_keeps_powershell_ci_out_of_posix_done(
    tmp_path: Path, capsys: Capture, discovered: bool
) -> None:
    command = 'python -m pytest "$env:TEST_PATH"'
    workflow = (
        "jobs:\n  test:\n    runs-on: windows-latest\n    steps:\n"
        f"      - shell: pwsh\n        run: {command}\n"
    )
    files = {".github/workflows/ci.yml": workflow}
    if discovered:
        files["pytest.ini"] = "[pytest]\n"
    target = repo(tmp_path / "t", files)
    before = snapshot(target)

    code, out, _ = run(capsys, str(target), "--detect")

    words = shlex.split(out, comments=True)
    done = [words[index + 1] for index, word in enumerate(words) if word == "--done"]
    assert code == 0 and done == ([PYTEST] if discovered else [])
    assert snapshot(target) == before
    assert "POSIX equivalent" in out and "--done" in out
    if discovered:
        assert f"{PYTEST} is what pytest.ini suggests" in out
    rendered = facts.render(target, [], [], ["AGENTS.md"], [])
    assert f"- CI test: `{command}` (.github/workflows/ci.yml)" in rendered.facts


def test_detect_refuses_a_target_outside_git_as_the_install_would(
    tmp_path: Path, capsys: Capture
) -> None:
    target = outside_git(tmp_path) / "plain"
    target.mkdir()

    code, out, err = run(capsys, str(target), "--detect")

    assert code != 0 and out == "" and "not inside a Git work tree" in err


def test_detect_without_a_harness_sign_proposes_generic(tmp_path: Path, capsys: Capture) -> None:
    target = repo(tmp_path / "t", {"README.md": "# T\n"})

    code, out, _ = run(capsys, str(target), "--detect")

    assert code == 0 and len(out.splitlines()) == 1
    words = shlex.split(out, comments=True)
    assert words[words.index("--harness") + 1] == "generic"
    assert "claude-code" in out and "codex" in out
    assert run(capsys, *words[2:])[0] == 0
    assert (target / GENERIC_SKILL).is_file()


@pytest.mark.parametrize("folder", ["worktrees", "work", "handoffs", "shared-memory"])
def test_detect_proposes_the_workspace_where_a_workspace_folder_exists(
    tmp_path: Path, capsys: Capture, folder: str
) -> None:
    """Git ignores these folders, so detection reads the disk, and the proposal installs."""

    target = repo(tmp_path / "t", {f".agents/{folder}/note.md": "# note\n"})
    write(target / ".gitignore", f".agents/{folder}/\n")

    code, out, _ = run(capsys, str(target), "--detect")

    words = shlex.split(out, comments=True)
    assert code == 0 and words[words.index("--fragments") + 1] == "commands,workspace"
    assert run(capsys, *words[2:])[0] == 0
    assert (target / ".agents/.gitignore").is_file()


def test_detect_does_not_propose_the_workspace_for_skills_alone(
    tmp_path: Path, capsys: Capture
) -> None:
    """Codex and Amp read skills under .agents/skills/, which adopt itself writes."""

    target = repo(tmp_path / "t", {".codex/config.toml": "", "README.md": "# T\n"})
    assert run(capsys, str(target), "--harness", "codex")[0] == 0
    assert (target / ".agents/skills").is_dir()

    code, out, _ = run(capsys, str(target), "--detect")

    assert code == 0 and "workspace" not in out


def test_detect_proposes_the_commands_fragment_for_an_empty_repository(
    tmp_path: Path, capsys: Capture
) -> None:
    """The habits are positive in any repository, so no file is needed to propose them."""

    target = repo(tmp_path / "t")

    code, out, _ = run(capsys, str(target), "--detect")

    words = shlex.split(out, comments=True)
    assert code == 0 and words[words.index("--fragments") + 1] == "commands"
    assert run(capsys, *words[2:])[0] == 0
    assert (target / ".outcomebound/fragments/commands.md").is_file()


def test_the_commands_fragment_installs_a_pointer_and_a_copy_and_removes_both(
    tmp_path: Path, capsys: Capture
) -> None:
    target = repo(tmp_path / "t", {"README.md": "# T\n"})
    before = snapshot(target)

    assert run(capsys, str(target), "--fragments", "commands")[0] == 0

    copy = target / ".outcomebound/fragments/commands.md"
    assert copy.read_bytes() == (ROOT / "fragments/setup/commands.md").read_bytes()
    pointer = (
        "when running a command whose output you read: read .outcomebound/fragments/commands.md"
    )
    assert pointer in (target / "AGENTS.md").read_text(encoding="utf-8")
    assert run(capsys, str(target), "--remove")[0] == 0
    assert snapshot(target) == before


# --- facts and pointers -----------------------------------------------------------

WORKFLOW = """\
on: push
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: make test
"""
LOCAL_EDGE = "dropping the production database"


def local_fragment(edges: str = f'["{LOCAL_EDGE}"]') -> str:
    text = (ROOT / "templates/fragment-local.md").read_text(encoding="utf-8")
    return text.replace("edges: []\n", f"edges: {edges}\n")


def facts_lines(target: Path) -> dict[str, str]:
    """The facts block's lines as {label: fact}."""

    body = blocks(target, "AGENTS.md")[adopt.FACTS].body
    return dict(line[2:].split(": ", 1) for line in body.splitlines())


def test_the_facts_are_read_from_their_sources(tmp_path: Path, capsys: Capture) -> None:
    """Done is what --done recorded, CI test is the workflow's command with its file, the
    edges are the selected fragments' and the floor's, and the record holds each source's
    digest; omitted flags keep the recorded Done commands and selection."""

    files = {
        ".github/workflows/ci.yml": WORKFLOW,
        adopt.LOCAL_FRAGMENT: local_fragment(),
        ".outcomebound/floor.json": '{"version": 1, "claims": []}\n',
        "CLAUDE.md": "# Notes\n",
    }
    target = repo(tmp_path / "t", files)
    arguments = ("--harness", "claude-code", "--fragments", "ci-release,local")

    code, _, err = run(
        capsys, str(target), *arguments, "--done", "make check", "--done", "make test"
    )

    assert code == 0, err
    edges = fragments.load_all(ROOT)["ci-release"].edges
    lines = facts_lines(target)
    assert list(lines) == ["Done", "CI test", "Irreversible edges", "Precedence"]
    assert lines["Done"] == "`make check` and `make test`"
    assert lines["CI test"] == "`make test` (.github/workflows/ci.yml)"
    assert lines["Irreversible edges"] == "; ".join([*edges, LOCAL_EDGE, facts.FLOOR_EDGE])
    assert "AGENTS.md" in lines["Precedence"] and "CLAUDE.md" in lines["Precedence"]
    record = manifest(target)["artifacts"][1]
    assert (record["id"], record["done"]) == (adopt.FACTS, ["make check", "make test"])
    assert record["fragments"] == ["ci-release", "local"]
    shipped = ".outcomebound/fragments/ci-release.md"
    sources = [".github/workflows/ci.yml", ".outcomebound/floor.json", shipped]
    assert record["inputs"] == {
        path: sha((target / path).read_bytes()) for path in [*sources, adopt.LOCAL_FRAGMENT]
    }

    before = snapshot(target)
    assert run(capsys, str(target))[0] == 0
    assert snapshot(target) == before
    assert run(capsys, str(target), "--done", "make\ntest")[0] == 1
    with pytest.raises(SystemExit) as refused:
        adopt.main([str(target), "--check", "--done", "make test"])
    assert refused.value.code == 2


def test_each_selected_fragment_is_a_pointer_and_local_stays_inline(
    tmp_path: Path, capsys: Capture
) -> None:
    target = repo(tmp_path / "t", {adopt.LOCAL_FRAGMENT: local_fragment()})

    code, _, err = run(capsys, str(target), "--harness", "codex", "--fragments", "python,local")

    assert code == 0, err
    shipped = fragments.load_all(ROOT)["python"]
    local = fragments.parse_fragment(local_fragment())
    body = blocks(target, "AGENTS.md")[adopt.POINTERS].body
    inline, pointers = body.rsplit("\n\n", 1)
    assert inline == f"**local** (setup) — {local.applies}\n\n{local.body}"
    assert pointers.splitlines() == [
        f"- {shipped.condition}: read {PYTHON_FRAGMENT}",
        *(
            f"- {adopt.CONDITIONS[name]}: read .agents/skills/{name}/SKILL.md"
            for name in adopt.SKILLS
        ),
    ]
    assert shipped.body not in (target / "AGENTS.md").read_text(encoding="utf-8")
    assert (target / PYTHON_FRAGMENT).read_bytes() == (
        ROOT / "fragments/stack/python.md"
    ).read_bytes()


def test_check_names_the_fact_that_moved_and_an_install_brings_it_current(
    tmp_path: Path, capsys: Capture
) -> None:
    target = repo(tmp_path / "t", {".github/workflows/ci.yml": WORKFLOW})
    assert run(capsys, str(target), "--harness", "codex", "--done", "make test")[0] == 0
    workflow = target / ".github/workflows/ci.yml"
    write(workflow, WORKFLOW.replace("make test", "make test-all"))

    code, out, _ = run(capsys, str(target), "--check")

    assert code == 1
    (line,) = [line for line in out.splitlines() if f"({adopt.FACTS})" in line]
    assert line.startswith("stale ")
    assert "CI test moved" in line and ".github/workflows/ci.yml changed" in line
    assert "Done" not in line

    assert run(capsys, str(target))[0] == 0
    assert facts_lines(target)["CI test"] == "`make test-all` (.github/workflows/ci.yml)"
    code, out, _ = run(capsys, str(target), "--check")
    assert code == 0 and set(states(out).values()) == {"current"}

    agents = target / "AGENTS.md"
    write(agents, agents.read_text(encoding="utf-8").replace("make test-all", "make x"))
    code, out, _ = run(capsys, str(target), "--check")
    assert states(out)[f"AGENTS.md ({adopt.FACTS})"] == "edited"
    assert run(capsys, str(target))[0] == 1


def test_remove_takes_out_the_blocks_and_fragment_files_and_keeps_the_projects_own(
    tmp_path: Path, capsys: Capture
) -> None:
    files = {
        ".github/workflows/ci.yml": WORKFLOW,
        adopt.LOCAL_FRAGMENT: local_fragment(),
        "AGENTS.md": "# Project\n\nOur rules.\n",
    }
    target = repo(tmp_path / "t", files)
    before = snapshot(target)
    arguments = ("--fragments", "python,tickets,local", "--done", "make test")
    assert run(capsys, str(target), "--harness", "claude-code,generic", *arguments)[0] == 0
    assert (target / ".outcomebound/fragments/tickets.md").is_file()

    code, _, err = run(capsys, str(target), "--remove")

    assert code == 0, err
    assert snapshot(target) == before


def test_an_install_carries_the_ticket_skills_and_their_pointers_with_no_fragment(
    tmp_path: Path, capsys: Capture
) -> None:
    target = repo(tmp_path / "t", {"README.md": "# T\n"})
    before = snapshot(target)

    assert run(capsys, str(target), "--harness", "claude-code")[0] == 0

    agents = (target / "AGENTS.md").read_text(encoding="utf-8")
    for name in ("slice-tickets", "hand-off-tickets"):
        shipped = sorted(p for p in (ROOT / "skills" / name).rglob("*") if p.is_file())
        for file in shipped:
            relative = file.relative_to(ROOT / "skills").as_posix()
            assert (target / ".claude/skills" / relative).read_bytes() == file.read_bytes()
        path = f".claude/skills/{name}/SKILL.md"
        assert f"{adopt.CONDITIONS[name]}: read {path}" in agents
    assert len(list((ROOT / "skills/slice-tickets").rglob("*.md"))) > 1
    code, out, _ = run(capsys, str(target), "--check")
    assert code == 0
    assert states(out)[".claude/skills/slice-tickets/references/github.md"] == "current"
    assert run(capsys, str(target), "--remove")[0] == 0
    assert snapshot(target) == before


def test_a_skill_the_engine_retired_reads_stale_and_an_upgrade_removes_it(
    tmp_path: Path, capsys: Capture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An install that carried a skill this engine has since retired keeps no copy
    of it once upgraded."""

    older = engine_copy(tmp_path)
    for relative in ("SKILL.md", "references/github.md"):
        (older / "skills/old-skill" / relative).parent.mkdir(parents=True, exist_ok=True)
        write(older / "skills/old-skill" / relative, f"{relative}\n")
    target = repo(tmp_path / "t", {"README.md": "# T\n"})
    with monkeypatch.context() as earlier:
        earlier.setattr(fragments, "SKILLS", (*fragments.SKILLS, "old-skill"))
        assert run(capsys, str(target), "--harness", "claude-code", source=older)[0] == 0
    retired = [".claude/skills/old-skill/SKILL.md", ".claude/skills/old-skill/references/github.md"]
    assert all((target / path).is_file() for path in retired)
    monkeypatch.setattr(adopt, "RETIRED_SKILLS", ("old-skill",))

    code, out, _ = run(capsys, str(target), "--check")

    assert code != 0
    assert all(states(out)[path] == "stale" for path in retired)

    assert run(capsys, str(target))[0] == 0

    assert not (target / ".claude/skills/old-skill").exists()
    assert all(record["id"] != "old-skill" for record in manifest(target)["artifacts"])
    assert run(capsys, str(target), "--check")[0] == 0


def test_a_skill_record_naming_a_file_the_skill_does_not_ship_reads_stale(
    tmp_path: Path, capsys: Capture
) -> None:
    target = repo(tmp_path / "t", {"README.md": "# T\n"})
    assert run(capsys, str(target), "--harness", "claude-code")[0] == 0
    extra = ".claude/skills/slice-tickets/references/extra.md"
    write(target / extra, "ours\n")
    document = manifest(target)
    for record in document["artifacts"]:
        if record["path"] == ".claude/skills/slice-tickets/references/github.md":
            record.update(path=extra, sha256=sha(b"ours\n"))
    write(target / adopt.MANIFEST, json.dumps(document))

    code, out, _ = run(capsys, str(target), "--check")

    assert code != 0 and states(out)[extra] == "stale"


def test_the_workspace_fragment_keeps_its_four_folders_out_of_git(
    tmp_path: Path, capsys: Capture
) -> None:
    target = repo(tmp_path / "t", {"README.md": "# T\n"})
    before = snapshot(target)

    assert run(capsys, str(target), "--fragments", "workspace")[0] == 0

    ignore = target / adopt.WORKSPACE_IGNORE
    assert ignore.read_bytes() == (ROOT / adopt.WORKSPACE_TEMPLATE).read_bytes()
    for folder in ("worktrees/a", "work/a", "handoffs", "shared-memory"):
        note = target / ".agents" / folder / "x.md"
        note.parent.mkdir(parents=True, exist_ok=True)
        write(note, "x\n")
        listed = subprocess.run(
            [GIT, "status", "--porcelain", "--untracked-files=all", "--", str(note)],
            cwd=target,
            capture_output=True,
            check=True,
        )
        assert listed.stdout == b"", folder
        shutil.rmtree(target / ".agents" / folder.split("/")[0])
    code, out, _ = run(capsys, str(target), "--check")
    assert code == 0 and states(out)[adopt.WORKSPACE_IGNORE] == "current"

    assert run(capsys, str(target), "--fragments", "")[0] == 0
    assert not ignore.exists()
    assert run(capsys, str(target), "--fragments", "workspace")[0] == 0
    assert run(capsys, str(target), "--remove")[0] == 0
    assert snapshot(target) == before


def test_the_research_fragment_installs_the_same_bytes_in_any_directory(
    tmp_path: Path, capsys: Capture
) -> None:
    """The fragment names no machine path, so two checkouts differ in nothing but their place."""

    first = repo(tmp_path / "a", {"README.md": "# T\n"})
    second = repo(tmp_path / "elsewhere" / "deeper" / "b", {"README.md": "# T\n"})
    for target in (first, second):
        arguments = (str(target), "--harness", "claude-code", "--fragments", "research")
        assert run(capsys, *arguments)[0] == 0
        code, out, _ = run(capsys, str(target), "--check")
        assert code == 0, out

    shipped = ".outcomebound/fragments/research.md"
    assert (first / shipped).read_bytes() == (ROOT / "fragments/setup/research.md").read_bytes()
    assert snapshot(first) == snapshot(second)
    guidance = (first / "AGENTS.md").read_text(encoding="utf-8")
    assert f"read {shipped}" in guidance
    assert "pushing to the research repository" in guidance


def test_detect_proposes_the_floors_runner_then_the_projects_test_command(
    tmp_path: Path, capsys: Capture
) -> None:
    files = {"pytest.ini": "[pytest]\n", ".outcomebound/floor.json": "{}\n"}
    with_floor = repo(tmp_path / "floor", files)
    without = repo(tmp_path / "plain", {"pytest.ini": "[pytest]\n"})
    bare = repo(tmp_path / "bare", {"README.md": "# T\n"})

    def proposed(target: Path) -> list[str]:
        code, out, _ = run(capsys, str(target), "--detect")
        assert code == 0
        words = shlex.split(out, comments=True)
        return [words[i + 1] for i, word in enumerate(words) if word == "--done"]

    assert proposed(with_floor) == [adopt.FLOOR_RUNNER, PYTEST]
    assert proposed(without) == [PYTEST]
    assert proposed(bare) == []


def test_the_floors_base_is_the_remotes_default_branch(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`--base` names the branch `origin/HEAD` points at, else `origin/main` where it resolves,
    and is left out where neither does, so the proposed Done never fails on a missing ref."""

    def git(target: Path, *arguments: str) -> None:
        subprocess.run([GIT, *arguments], cwd=target, check=True, capture_output=True)

    def floor_line(target: Path) -> str:
        return adopt.proposed_done(target)[0]

    target = repo(tmp_path / "t", {".outcomebound/floor.json": "{}\n"})
    identity_flags = ("-c", "user.name=t", "-c", "user.email=t@example.invalid")
    git(target, "add", "-A")
    git(target, *identity_flags, "-c", "commit.gpgsign=false", "commit", "-q", "-m", "one")
    assert floor_line(target) == adopt.FLOOR_RUNNER
    # With no base the loosening check does not run, and --detect says so beside its proposal.
    assert adopt.main([str(target), "--detect"], source=ROOT) == 0
    assert "its loosening check does not run" in capsys.readouterr().out

    git(target, "update-ref", "refs/remotes/origin/main", "HEAD")
    assert floor_line(target) == f"{adopt.FLOOR_RUNNER} --base origin/main"

    git(target, "update-ref", "refs/remotes/origin/trunk", "HEAD")
    git(target, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/trunk")
    assert floor_line(target) == f"{adopt.FLOOR_RUNNER} --base origin/trunk"

    # origin/HEAD naming a branch that does not resolve falls back to origin/main.
    git(target, "update-ref", "-d", "refs/remotes/origin/trunk")
    assert floor_line(target) == f"{adopt.FLOOR_RUNNER} --base origin/main"


def test_an_install_warns_where_nested_instructions_pass_a_harness_byte_cap(
    tmp_path: Path, capsys: Capture
) -> None:
    """Per folder holding a nested AGENTS.md, the bytes loaded from the root down are measured
    against the row's doc_byte_cap; past it is a warning, and the install still succeeds."""

    cap = adopt.harness_table(ROOT)["codex"]["doc_byte_cap"]
    files = {
        "AGENTS.md": "# Project\n",
        "small/AGENTS.md": "a\n",
        "big/AGENTS.md": "b" * cap,
        "big/deeper/AGENTS.override.md": "c\n",
        "big/deeper/AGENTS.md": "d" * cap,
    }
    target = repo(tmp_path / "t", files)
    code, out, _ = run(capsys, str(target), "--harness", "codex")
    assert code == 0
    warned = [line for line in out.splitlines() if line.startswith("warning")]
    assert all("codex:" in line and f"{cap}-byte cap" in line for line in warned)
    assert [line.split("a session in ")[1].split("/ ")[0] for line in warned] == [
        "big",
        "big/deeper",
    ]
    # The override file stands in for its folder's AGENTS.md.
    assert "big/deeper/AGENTS.override.md 2)" in warned[1]
    assert "big/deeper/AGENTS.md" not in warned[1]
    code, out, _ = run(capsys, str(target), "--harness", "claude-code")
    assert code == 0 and "warning" not in out


def test_no_harness_installs_the_skills_where_the_pointers_name_them(
    tmp_path: Path, capsys: Capture
) -> None:
    """A harness outside the table is `generic`, the default: each skill goes once under
    .outcomebound/skills/, and the pointers name that copy even beside a native one."""

    target = repo(tmp_path / "t", {"README.md": "# T\n"})

    code, out, err = run(capsys, str(target))

    assert code == 0, err
    generic = {name: f".outcomebound/skills/{name}/SKILL.md" for name in adopt.SKILLS}
    lines = [f"- {adopt.CONDITIONS[name]}: read {path}" for name, path in generic.items()]
    for name, path in generic.items():
        assert (target / path).read_bytes() == (ROOT / f"skills/{name}/SKILL.md").read_bytes()
    assert blocks(target, "AGENTS.md")[adopt.POINTERS].body.splitlines() == lines
    skills = [r for r in manifest(target)["artifacts"] if r["kind"] == "skill"]
    assert sorted(r["path"] for r in skills) == sorted(
        f".outcomebound/skills/{file}" for file in SKILL_FILES
    )
    assert all(r["harnesses"] == ["generic"] for r in skills)
    assert any(line.startswith("UNVERIFIED generic") for line in out.splitlines())

    assert run(capsys, str(target), "--harness", "claude-code,generic")[0] == 0
    assert (target / CLAUDE_SKILL).is_file() and (target / CLAUDE_BRIEF).is_file()
    assert blocks(target, "AGENTS.md")[adopt.POINTERS].body.splitlines() == lines
    code, out, _ = run(capsys, str(target), "--check")
    assert code == 0 and set(states(out).values()) == {"current"}
    code, _, err = run(capsys, str(target), "--harness", "nope")
    assert code == 1 and "generic" in err


# --- the finish check -------------------------------------------------------------

SETTINGS = {"claude-code": ".claude/settings.json", "codex": ".codex/hooks.json"}
# A project's own settings: keys out of alphabetical order, its own Stop hook, non-ASCII text
# written plainly and four-space indentation, each of which a rewrite keeps.
PROJECT_SETTINGS = (
    json.dumps(
        {
            "zeta": 1,
            "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "./their-own.sh"}]}]},
            "alpha": "café",
        },
        indent=4,
        ensure_ascii=False,
    )
    + "\n"
)


def hook_records(target: Path) -> list[dict[str, Any]]:
    return [record for record in manifest(target)["artifacts"] if record["kind"] == "hook"]


def fire(target: Path, command: str) -> dict[str, Any]:
    """Run an entry's command as its harness would, `engine()` standing in for the name on
    PATH, with the stop input both rows send when the guard is unset."""

    words = shlex.split(command)
    assert words[0] == "outcomebound"
    done = subprocess.run(
        engine(*words[1:]),
        input=json.dumps({"stop_hook_active": False}).encode(),
        cwd=target,
        env={**os.environ, "CLAUDE_PROJECT_DIR": str(target)},
        capture_output=True,
        check=True,
    )
    verdict: dict[str, Any] = json.loads(done.stdout)
    return verdict


@pytest.mark.parametrize("seeded", [True, False], ids=["project-settings", "no-settings"])
@pytest.mark.parametrize("row", sorted(SETTINGS))
def test_finish_check_installs_checks_and_removes_its_entry_per_row(
    tmp_path: Path, capsys: Capture, row: str, seeded: bool
) -> None:
    """Breaks if the entry is not one the verb runs to a pass, if the project's keys, their
    order, its own hook or its indentation are lost, if `--check` misreads the entry, or if
    `--remove` leaves any byte other than those there before, a file adopt created included."""

    path = SETTINGS[row]
    target = repo(tmp_path / "t", {path: PROJECT_SETTINGS} if seeded else {})
    before = snapshot(target)

    code, _, err = run(capsys, str(target), "--harness", row, "--done", "true", "--finish-check")

    assert code == 0, err
    text = (target / path).read_text(encoding="utf-8")
    document = json.loads(text)
    ours = finish_check.entry(row, finish_check.done_digest(["true"]))
    assert document["hooks"]["Stop"][-1] == ours
    assert ours["hooks"][0]["timeout"] == 600
    assert ours["hooks"][0]["command"].endswith(" --timeout 600")
    if seeded:
        assert list(document) == ["zeta", "hooks", "alpha"]
        assert document["hooks"]["Stop"][0]["hooks"][0]["command"] == "./their-own.sh"
        assert '\n    "alpha": "café"\n}\n' in text
    began = finish_check.mark_entry(row, finish_check.done_digest(["true"]))
    assert document["hooks"]["UserPromptSubmit"][-1] == began
    assert began["hooks"][0] == {
        "type": "command",
        "command": f"outcomebound finish-check --mark --harness {row} --done "
        f"{finish_check.done_digest(['true'])}",
        "timeout": 30,
    }
    assert hook_records(target) == [
        {
            "kind": "hook",
            "path": path,
            "id": "finish-check",
            "harness": row,
            "timeout": 600,
            "created": not seeded,
            "sha256": sha(finish_check.canonical(ours)),
        },
        {
            "kind": "hook",
            "path": path,
            "id": "finish-check-mark",
            "harness": row,
            "created": not seeded,
            "sha256": sha(finish_check.canonical(began)),
        },
    ]
    assert fire(target, ours["hooks"][0]["command"]) == {}
    write(target / "changed.txt", "a change\n")
    assert fire(target, ours["hooks"][0]["command"])["systemMessage"].startswith(
        "finish-check PASS: true, "
    )
    (target / "changed.txt").unlink()
    code, out, _ = run(capsys, str(target), "--check")
    assert code == 0 and states(out)[f"{path} (finish-check)"] == "current"

    assert run(capsys, str(target), "--remove")[0] == 0
    assert snapshot(target) == before


def test_check_reads_the_entry_as_edited_stale_or_missing_and_an_edit_needs_force(
    tmp_path: Path, capsys: Capture
) -> None:
    """Breaks if an edited entry is replaced without --force, or if `--check` calls current an
    entry the person changed, one whose Done digest is not the manifest's, or one that is gone."""

    target = repo(tmp_path / "t")
    arguments = ("--harness", "claude-code", "--done", "true", "--finish-check")
    assert run(capsys, str(target), *arguments)[0] == 0
    settings, name = target / ".claude/settings.json", ".claude/settings.json (finish-check)"
    document = json.loads(settings.read_text(encoding="utf-8"))
    document["hooks"]["Stop"][0]["hooks"][0]["timeout"] = 30
    write(settings, json.dumps(document, indent=2) + "\n")

    assert states(run(capsys, str(target), "--check")[1])[name] == "edited"
    edited = snapshot(target)
    assert run(capsys, str(target))[0] == 1 and snapshot(target) == edited
    assert run(capsys, str(target), "--force")[0] == 0
    assert states(run(capsys, str(target), "--check")[1])[name] == "current"

    recorded = manifest(target)
    for record in recorded["artifacts"]:
        if record["id"] == adopt.FACTS:
            record["done"] = ["false"]
    write(target / adopt.MANIFEST, json.dumps(recorded))
    assert states(run(capsys, str(target), "--check")[1])[name] == "stale"
    settings.unlink()
    assert states(run(capsys, str(target), "--check")[1])[name] == "missing"


@pytest.mark.parametrize(
    "text",
    [
        '{\n  // ours\n  "model": "x"\n}\n',
        '{\n  "model": "x",\n  "model": "y"\n}\n',
        '{\n  "path": "a\\/b"\n}\n',
    ],
    ids=["comments", "repeated-key", "escape-form"],
)
def test_a_settings_document_a_rewrite_would_change_beyond_whitespace_is_refused(
    tmp_path: Path, capsys: Capture, text: str
) -> None:
    """Breaks if adopt writes into a document whose comments, repeated key or escape the
    rewrite would lose, instead of refusing before any write."""

    target = repo(tmp_path / "t", {".claude/settings.json": text})
    before = snapshot(target)

    arguments = ("--harness", "claude-code", "--done", "true", "--finish-check")
    code, _, err = run(capsys, str(target), *arguments)

    assert code == 1 and ".claude/settings.json" in err
    assert snapshot(target) == before


def test_a_done_change_rewrites_the_entry_and_an_emptied_done_takes_it_out(
    tmp_path: Path, capsys: Capture
) -> None:
    """Breaks if a Done change leaves the old digest in the entry, which then runs nothing, or
    adds a second entry; if an emptied Done leaves an entry; or if --finish-check is accepted
    with no Done to run."""

    target = repo(tmp_path / "t")
    before = snapshot(target)
    arguments = ("--harness", "codex", "--done", "make test", "--finish-check")
    assert run(capsys, str(target), *arguments)[0] == 0

    assert run(capsys, str(target), "--done", "make check", "--done", "make test")[0] == 0

    [ours] = json.loads((target / ".codex/hooks.json").read_text(encoding="utf-8"))["hooks"]["Stop"]
    digest = finish_check.done_digest(["make check", "make test"])
    assert ours == finish_check.entry("codex", digest)
    assert run(capsys, str(target), "--done", "")[0] == 0
    assert not (target / ".codex").exists() and hook_records(target) == []
    refused = snapshot(target)
    assert run(capsys, str(target), "--finish-check")[0] == 1 and snapshot(target) == refused
    assert run(capsys, str(target), "--remove")[0] == 0 and snapshot(target) == before


def test_finish_timeout_is_written_kept_and_changed_in_the_one_entry(
    tmp_path: Path, capsys: Capture
) -> None:
    """Breaks if the timeout the person names is not the entry's `timeout` and the verb's
    `--timeout` both, if an install that omits it drops it, if a new value adds a second entry
    or leaves the old one, or if `--check` misreads an entry with a named timeout."""

    target = repo(tmp_path / "t")
    hooks_file, name = target / ".codex/hooks.json", ".codex/hooks.json (finish-check)"
    digest = finish_check.done_digest(["true"])
    arguments = ("--harness", "codex", "--done", "true", "--finish-check")
    assert run(capsys, str(target), *arguments, "--finish-timeout", "1200")[0] == 0

    def stop() -> list[Any]:
        return list(json.loads(hooks_file.read_text(encoding="utf-8"))["hooks"]["Stop"])

    assert stop() == [finish_check.entry("codex", digest, 1200)]
    assert stop()[0]["hooks"][0] == {
        "type": "command",
        "command": f"outcomebound finish-check --harness codex --done {digest} --timeout 1200",
        "timeout": 1200,
    }
    assert [r["timeout"] for r in hook_records(target) if r["id"] == "finish-check"] == [1200]
    write(target / "changed.txt", "a change\n")
    assert fire(target, stop()[0]["hooks"][0]["command"])["systemMessage"].startswith(
        "finish-check PASS: true, "
    )
    assert run(capsys, str(target), "--fragments", "")[0] == 0
    assert stop() == [finish_check.entry("codex", digest, 1200)]
    assert states(run(capsys, str(target), "--check")[1])[name] == "current"

    assert run(capsys, str(target), "--finish-timeout", "900")[0] == 0
    assert stop() == [finish_check.entry("codex", digest, 900)]
    assert states(run(capsys, str(target), "--check")[1])[name] == "current"


def test_finish_timeout_is_refused_without_a_finish_check_or_within_the_margin(
    tmp_path: Path, capsys: Capture
) -> None:
    """Breaks if a timeout is accepted for an install that writes no entry, which would record
    a limit nothing reads, or one that leaves the Done commands no time before the margin."""

    target = repo(tmp_path / "t")
    code, _, err = run(capsys, str(target), "--done", "true", "--finish-timeout", "900")
    assert code == 1 and "add --finish-check" in err and snapshot(target) == {}
    margin = str(finish_check.MARGIN_SECONDS)
    with pytest.raises(SystemExit):
        run(capsys, str(target), "--done", "true", "--finish-check", "--finish-timeout", margin)
    assert snapshot(target) == {}


def test_omitted_keeps_the_finish_check_and_no_finish_check_takes_it_out(
    tmp_path: Path, capsys: Capture
) -> None:
    """Breaks if an install that does not name the flag drops the person's opt-in, or if
    --no-finish-check leaves the entry or the project's document other than it was."""

    target = repo(tmp_path / "t", {".claude/settings.json": PROJECT_SETTINGS})
    settings = target / ".claude/settings.json"
    arguments = ("--harness", "claude-code", "--done", "true", "--finish-check")
    assert run(capsys, str(target), *arguments)[0] == 0
    with_entry = settings.read_bytes()

    assert run(capsys, str(target), "--fragments", "")[0] == 0
    assert settings.read_bytes() == with_entry
    assert run(capsys, str(target), "--no-finish-check")[0] == 0
    assert settings.read_text(encoding="utf-8") == PROJECT_SETTINGS
    assert hook_records(target) == []


@pytest.mark.parametrize("harnesses", ["generic", "gemini", "cursor,amp"])
def test_finish_check_is_refused_where_no_selected_harness_has_one(
    tmp_path: Path, capsys: Capture, harnesses: str
) -> None:
    """Breaks if --finish-check is accepted where it would install nothing, or refused without
    naming why each harness has none yet."""

    target = repo(tmp_path / "t")

    arguments = ("--harness", harnesses, "--done", "true", "--finish-check")
    code, _, err = run(capsys, str(target), *arguments)

    assert code == 1 and snapshot(target) == {}
    for name in harnesses.split(","):
        assert f"{name} finish-check: not available yet: {finish_check.unavailable(name)}" in err


def test_a_mixed_selection_installs_where_a_row_has_one_and_names_the_rest(
    tmp_path: Path, capsys: Capture
) -> None:
    """Breaks if a harness without a finish hook gets an entry or passes unnamed, or if the
    report leaves out a row's one-time accept, the launcher on the harness's PATH, or codex's
    open report."""

    target = repo(tmp_path / "t")
    selected = "claude-code,codex,gemini,cursor"

    code, out, err = run(
        capsys, str(target), "--harness", selected, "--done", "true", "--finish-check"
    )

    assert code == 0, err
    stop = [r["harness"] for r in hook_records(target) if r["id"] == "finish-check"]
    assert stop == ["claude-code", "codex"]
    assert [r["harness"] for r in hook_records(target) if r["id"] == "finish-check-mark"] == stop
    for name in ("gemini", "cursor"):
        assert f"{name} finish-check: not available yet: {finish_check.unavailable(name)}" in out
    table = json.loads((ROOT / "adapters/harnesses.json").read_text(encoding="utf-8"))
    for name in ("claude-code", "codex"):
        accept = f"the one-time accept: {table[name]['finish_hook']['accept']}, and `outcomebound`"
        assert accept in out and "on the harness process's PATH" in out
    assert finish_check.CAUTION["codex"] in out


def test_an_install_measures_done_once_and_records_the_failures_there_now(
    tmp_path: Path, capsys: Capture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Breaks if an install with --finish-check does not run Done once and report its time and
    each failure, if it does not keep the failures as known, if a dry run or an install that
    does not name --finish-check runs Done, or if --finish-check does not measure it again."""

    # A PATH with no entry the measurement leaves out, as a hook has, so a failure runs once.
    environment, _ = finish_check.hook_environment(tmp_path, os.environ)
    monkeypatch.setenv("PATH", environment["PATH"])
    monkeypatch.delenv("VIRTUAL_ENV", raising=False)
    count = tmp_path / "count"
    failing = f"echo run >> {paths.shell_path(count)}; exit 3"
    target = repo(tmp_path / "t")
    commit_all(target)
    arguments = ("--harness", "claude-code", "--done", failing, "--done", "true", "--finish-check")

    code, out, _ = run(capsys, str(target), *arguments, "--dry-run")
    assert code == 0 and "a dry run does not run Done" in out and not count.exists()

    code, out, err = run(capsys, str(target), *arguments)
    assert code == 0, err
    assert f"known    finish-check: `{failing}` failed, exit 3 after " in out
    assert re.search(r"PASS     finish-check: `true` in \d+ s", out)
    assert re.search(r"measured finish-check: Done ran once in \d+ s; the hook gives it 570 s", out)
    digest = finish_check.done_digest([failing, "true"])
    known = finish_check.known_record(target, digest)
    assert known is not None and {k: v.code for k, v in known.failing.items()} == {failing: 3}
    assert len(count.read_text(encoding="utf-8").splitlines()) == 1

    code, out, _ = run(capsys, str(target), "--fragments", "")
    assert code == 0 and "running " not in out
    assert re.search(r"finish-check: Done was measured on \S+ on commit [0-9a-f]{12} in ", out)
    assert f"`{failing}` (exit 3)" in out
    assert len(count.read_text(encoding="utf-8").splitlines()) == 1
    assert "was measured with the PATH of the agent" not in out

    # A record an engine before the hook-like measurement wrote: the upgrade says so.
    assert finish_check.keep_known(target, dataclasses.replace(known, as_hook=False))
    code, out, _ = run(capsys, str(target), "--fragments", "")
    assert code == 0 and "finish-check: that record was measured with the PATH of the agent" in out
    assert len(count.read_text(encoding="utf-8").splitlines()) == 1
    assert run(capsys, str(target), "--finish-check")[0] == 0
    assert len(count.read_text(encoding="utf-8").splitlines()) == 2

    code, out, _ = run(capsys, str(target), "--done", failing)
    assert code == 0 and "running " not in out
    assert "finish-check: Done was not measured, so no record of known failures applies" in out
    assert len(count.read_text(encoding="utf-8").splitlines()) == 2


@pytest.mark.parametrize("place", ["missing", "project", "virtual-environment", "tool-bin"])
def test_an_explicit_measurement_names_a_launcher_missing_from_its_hook_environment(
    tmp_path: Path, capsys: Capture, monkeypatch: pytest.MonkeyPatch, place: str
) -> None:
    """Breaks if a launcher found only in the project or an activated environment passes
    unnamed, if a launcher on the kept PATH is reported absent, or if this diagnostic changes
    Done's verdict, hook bytes, a dry run or an install that does not measure Done."""

    target = repo(tmp_path / "t", {".claude/settings.json": PROJECT_SETTINGS})
    folder = target / "bin" if place == "project" else tmp_path / place / "bin"
    folder.mkdir(parents=True)
    if place == "virtual-environment":
        write(folder.parent / "pyvenv.cfg", "home = /synthetic/python\n")
    if place != "missing":
        launcher = folder / ("outcomebound.cmd" if WINDOWS else "outcomebound")
        write(launcher, "@exit /b 0\n" if WINDOWS else "#!/bin/sh\nexit 0\n")
        launcher.chmod(0o755)
    monkeypatch.setenv("PATH", str(folder))

    def measure(root: Path, done: list[str], timeout: int) -> finish_check.Measured:
        # Only the Done runner is a double: launcher lookup and PATH filtering are real.
        _, dropped = finish_check.hook_environment(root, os.environ)
        return finish_check.Measured(
            (finish_check.Result(":", finish_check.PASS, 0.0),), 0.0, True, dropped=dropped
        )

    monkeypatch.setattr(finish_check, "measure", measure)
    arguments = ("--harness", "claude-code", "--done", ":", "--finish-check")

    code, out, err = run(capsys, str(target), *arguments)

    assert code == 0, err
    missing = "`outcomebound` was not found on the PATH used to measure Done"
    assert (missing in out) == (place != "tool-bin")
    if place != "tool-bin":
        [line] = [line for line in out.splitlines() if missing in line]
        assert line.startswith("UNVERIFIED ") and "desktop PATH" in line
        assert "whether it runs the hook remain UNVERIFIED" in line
    assert "PASS     finish-check: `:` in 0 s" in out
    document = json.loads((target / ".claude/settings.json").read_text(encoding="utf-8"))
    assert document["hooks"]["Stop"][0]["hooks"][0]["command"] == "./their-own.sh"
    digest = finish_check.done_digest([":"])
    assert document["hooks"]["Stop"][-1] == finish_check.entry("claude-code", digest)
    assert document["hooks"]["UserPromptSubmit"][-1] == finish_check.mark_entry(
        "claude-code", digest
    )
    before = snapshot(target)
    for extra in (("--finish-check", "--dry-run"), ()):
        code, out, err = run(capsys, str(target), *extra)
        assert code == 0, err
        assert missing not in out and snapshot(target) == before


def test_a_new_measurement_names_the_failures_new_since_the_record_it_replaces(
    tmp_path: Path, capsys: Capture
) -> None:
    """Breaks if `adopt --finish-check`, run after a change broke code, makes the new failure
    known without the install report naming it apart from the failures known before."""

    lines = tmp_path / "lines"
    write(lines, "FAILED tests/test_a.py::test_old - assert 0\n")
    target = repo(tmp_path / "t")
    commit_all(target)
    arguments = (
        "--harness",
        "codex",
        "--done",
        f"cat {paths.shell_path(lines)}; exit 1",
        "--finish-check",
    )
    assert "new since the record" not in run(capsys, str(target), *arguments)[1]

    with lines.open("a", encoding="utf-8") as handle:
        handle.write("FAILED tests/test_a.py::test_new - assert 1\n")
    out = run(capsys, str(target), "--finish-check")[1]
    assert re.search(r"known    finish-check: new since the record measured on \S+ on commit ", out)
    assert "pytest tests/test_a.py::test_new" in out and "test_old" not in out.split("new since")[1]


def test_an_install_whose_done_outlasts_the_timeout_proposes_a_longer_one(
    tmp_path: Path, capsys: Capture
) -> None:
    """Breaks if a Done slower than the hook allows is installed without saying so, or if the
    install stops it at the hook's limit instead of measuring it to its end."""

    target = repo(tmp_path / "t")
    timeout = finish_check.MARGIN_SECONDS + 1
    arguments = ("--harness", "codex", "--done", "sleep 2", "--finish-check")

    code, out, err = run(capsys, str(target), *arguments, "--finish-timeout", str(timeout))

    assert code == 0, err
    assert re.search(r"PASS     finish-check: `sleep 2` in \d+ s", out)
    took = re.search(r"UNVERIFIED finish-check: Done took (\d+) s, longer than the 1 s", out)
    assert took is not None and int(took.group(1)) >= 2
    # The report rounds the seconds Done took, and the least timeout is the whole seconds plus
    # one past the margin: 2.4 s reads "2 s" and 33, 2.6 s reads "3 s" and 33 too.
    least = re.search(r"--finish-timeout <seconds>` with more than (\d+), for example (\d+)", out)
    assert least is not None, out
    seconds = int(least.group(1)) - 1 - finish_check.MARGIN_SECONDS
    assert seconds in (int(took.group(1)) - 1, int(took.group(1))), out
    assert int(least.group(2)) == 2 * int(least.group(1))
    assert "UNVERIFIED finish-check: Done took" in run(capsys, str(target))[1]


@pytest.mark.skipif(
    WINDOWS,
    reason="the stop is SIGINT to a process started with SIGINT at its default, and Done is a "
    "POSIX line that echoes $$ and execs sleep: a console control event is another mechanism, "
    "which no run here shows",
)
def test_a_stopped_measurement_stops_done_keeps_nothing_and_exits_130(tmp_path: Path) -> None:
    """Breaks if Ctrl-C during the install's Done run leaves the command running, which runs in
    its own session where the terminal's signal does not reach it, ends in a traceback, or
    keeps a record of known failures. The install starts with SIGINT at its default, as a
    terminal's foreground job has it: a suite started as a background job of a shell (`make
    test &`) has SIGINT ignored, and a Python started that way, as the install is, never raises
    KeyboardInterrupt."""

    target = repo(tmp_path / "t")
    pid = tmp_path / "pid"
    done = f"echo $$ > {paths.shell_path(pid)}; exec sleep 300"
    process = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import os, signal, sys; signal.signal(signal.SIGINT, signal.SIG_DFL); "
            "os.execv(sys.argv[1], sys.argv[1:])",
            str(LAUNCHER),
            "adopt",
            str(target),
            "--harness",
            "codex",
            "--done",
            done,
            "--finish-check",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    started = time.monotonic()
    while not (pid.exists() and pid.read_text(encoding="utf-8").strip()):
        assert time.monotonic() - started < 60 and process.poll() is None
        time.sleep(0.05)
    process.send_signal(signal.SIGINT)
    out, err = process.communicate(timeout=60)

    assert process.returncode == 130, err
    assert "Traceback" not in err
    assert "UNVERIFIED finish-check: the measurement was stopped" in out
    assert not running(int(pid.read_text(encoding="utf-8")))
    assert finish_check.known_record(target, finish_check.done_digest([done])) is None


def test_a_changed_codex_entry_names_the_new_trust_in_hooks(
    tmp_path: Path, capsys: Capture
) -> None:
    """Breaks if an install that changes the codex entry, which Codex then skips until it is
    trusted again, does not say so, or says so where the entry did not change."""

    target = repo(tmp_path / "t")
    arguments = ("--harness", "claude-code,codex", "--done", "true", "--finish-check")
    again = finish_check.REVIEW_AGAIN["codex"]

    assert again not in run(capsys, str(target), *arguments)[1]
    assert again not in run(capsys, str(target), "--fragments", "")[1]
    out = run(capsys, str(target), "--finish-timeout", "900")[1]
    assert "action   codex finish-check: the entry changed" in out and again in out
    assert "claude-code finish-check: the entry changed" not in out
    assert again in run(capsys, str(target), "--done", "true", "--done", "echo two")[1]


def test_an_install_with_only_the_stop_entry_gains_the_turn_start_entry(
    tmp_path: Path, capsys: Capture
) -> None:
    """Breaks if an upgrade of an install written before the turn-start entry leaves it out,
    adds a second stop entry, reads `--check` as current meanwhile, or does not say that codex,
    which skips a new hook until it is trusted, needs the new entry trusted in /hooks."""

    target = repo(tmp_path / "t")
    arguments = ("--harness", "claude-code,codex", "--done", "true", "--finish-check")
    assert run(capsys, str(target), *arguments)[0] == 0
    for row, path in SETTINGS.items():
        document = json.loads((target / path).read_text(encoding="utf-8"))
        document["hooks"] = {"Stop": [finish_check.entry(row, finish_check.done_digest(["true"]))]}
        write(target / path, json.dumps(document, indent=2) + "\n")
    record = manifest(target)
    record["artifacts"] = [r for r in record["artifacts"] if r["id"] != "finish-check-mark"]
    write(target / adopt.MANIFEST, json.dumps(record))
    out = run(capsys, str(target), "--check")[1]
    assert "finish-check-mark" not in out

    code, out, _ = run(capsys, str(target))

    assert code == 0
    for row, path in SETTINGS.items():
        hooks = json.loads((target / path).read_text(encoding="utf-8"))["hooks"]
        digest = finish_check.done_digest(["true"])
        assert hooks["Stop"] == [finish_check.entry(row, digest)]
        assert hooks["UserPromptSubmit"] == [finish_check.mark_entry(row, digest)]
    assert "action   codex finish-check: the turn-start entry was added" in out
    assert finish_check.REVIEW_AGAIN["codex"] in out
    assert "claude-code finish-check: the turn-start entry" not in out
    states_ = states(run(capsys, str(target), "--check")[1])
    assert {states_[f"{path} (finish-check-mark)"] for path in SETTINGS.values()} == {"current"}
    assert "turn-start entry" not in run(capsys, str(target), "--fragments", "")[1]


def test_check_reads_a_deleted_turn_start_entry_as_missing(tmp_path: Path, capsys: Capture) -> None:
    """Breaks if `--check` calls current an install whose turn-start entry is gone, which leaves
    the check running on every turn end as before."""

    target = repo(tmp_path / "t")
    arguments = ("--harness", "claude-code", "--done", "true", "--finish-check")
    assert run(capsys, str(target), *arguments)[0] == 0
    settings = target / ".claude/settings.json"
    document = json.loads(settings.read_text(encoding="utf-8"))
    del document["hooks"]["UserPromptSubmit"]
    write(settings, json.dumps(document, indent=2) + "\n")

    found = states(run(capsys, str(target), "--check")[1])

    assert found[".claude/settings.json (finish-check-mark)"] == "missing"
    assert found[".claude/settings.json (finish-check)"] == "current"


def test_the_turn_start_entry_runs_the_verb_to_a_mark_and_prints_nothing(
    tmp_path: Path, capsys: Capture
) -> None:
    """Breaks if the entry's own command does not write the mark or prints anything: a harness
    adds what a prompt hook prints to the model's context."""

    target = repo(tmp_path / "t")
    commit_all(target)
    arguments = ("--harness", "claude-code", "--done", "true", "--finish-check")
    assert run(capsys, str(target), *arguments)[0] == 0
    commit_all(target)
    document = json.loads((target / ".claude/settings.json").read_text(encoding="utf-8"))
    command = document["hooks"]["UserPromptSubmit"][0]["hooks"][0]["command"]

    done = subprocess.run(
        engine(*shlex.split(command)[1:]),
        input=json.dumps(
            {"cwd": str(target), "session_id": "s", "hook_event_name": "UserPromptSubmit"}
        ).encode(),
        cwd=target,
        capture_output=True,
        check=False,
    )

    assert (done.returncode, done.stdout, done.stderr) == (0, b"", b"")
    assert (target / ".git" / finish_check.MARK).is_file()


# --- the writer -------------------------------------------------------------------


def test_the_writer_refuses_bytes_other_than_those_its_caller_read(tmp_path: Path) -> None:
    (tmp_path / "b.md").write_bytes(b"theirs\n")

    for expected in ({"a.md": None, "b.md": None}, {"a.md": None, "b.md": b"mine\n"}):
        with pytest.raises(fileplan.WriteError):
            fileplan.write(tmp_path, {"a.md": b"new\n", "b.md": b"new\n"}, expected)
        assert not (tmp_path / "a.md").exists()  # checked before the first write
        assert (tmp_path / "b.md").read_bytes() == b"theirs\n"

    fileplan.write(tmp_path, {"b.md": b"new\n"}, {"b.md": b"theirs\n"})
    assert (tmp_path / "b.md").read_bytes() == b"new\n"


@needs_symlinks
def test_the_writer_refuses_a_symlink_anywhere_on_the_path(tmp_path: Path) -> None:
    root, outside = tmp_path / "root", tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (root / "linked").symlink_to(outside, target_is_directory=True)
    (root / "link.md").symlink_to(outside / "file.md")

    for relative in ("linked/f.md", "link.md", ".GIT/hooks/pre-commit"):
        with pytest.raises(fileplan.WriteError):
            fileplan.write(root, {relative: b"x\n"}, {relative: None})
    assert list(outside.iterdir()) == []


def test_the_writer_stages_exclusively_keeps_modes_and_prunes_what_it_empties(
    tmp_path: Path,
) -> None:
    stage = tmp_path / ("x.md" + fileplan.STAGE_SUFFIX)
    stage.write_bytes(b"someone else's\n")
    with pytest.raises(fileplan.WriteError):
        fileplan.write(tmp_path, {"x.md": b"x\n"}, {"x.md": None})
    assert stage.read_bytes() == b"someone else's\n" and not (tmp_path / "x.md").exists()

    fileplan.write(tmp_path, {"a/b/c.sh": b"one\n"}, {"a/b/c.sh": None})
    (tmp_path / "a/b/c.sh").chmod(0o755)
    fileplan.write(tmp_path, {"a/b/c.sh": b"two\n"}, {"a/b/c.sh": b"one\n"})
    if os.name != "nt":  # Windows keeps the read-only bit of a mode only, so 0o755 is 0o666 there
        assert (tmp_path / "a/b/c.sh").stat().st_mode & 0o777 == 0o755
    assert not list(tmp_path.glob("a/b/*" + fileplan.STAGE_SUFFIX))

    fileplan.write(tmp_path, {"a/b/c.sh": None}, {"a/b/c.sh": b"two\n"})
    assert not (tmp_path / "a").exists() and tmp_path.is_dir()


def test_a_human_style_is_recorded_kept_on_upgrade_and_cleared_by_an_empty_one(
    tmp_path: Path, capsys: Capture
) -> None:
    """Breaks if the style line is not rendered from the record, is lost on a re-run that names
    no style, survives `--human-style ''`, quotes more than the standard's name, or leaves
    `--check` reading the install stale."""

    target = repo(tmp_path / "t", {"README.md": "# T\n"})

    code, _, err = run(capsys, str(target), "--harness", "codex", "--human-style", "ste")

    assert code == 0, err
    lines = facts_lines(target)
    assert list(lines)[-2:] == ["Text for people", "Precedence"]
    assert "ASD-STE100 Simplified Technical English" in lines["Text for people"]
    assert "no length limit" in lines["Text for people"]
    assert "every fact, number and caveat is kept" in lines["Text for people"]
    assert manifest(target)["artifacts"][1]["style"] == ["ste"]
    assert run(capsys, str(target), "--check")[0] == 0

    assert run(capsys, str(target), "--done", "make test")[0] == 0
    assert "Text for people" in facts_lines(target)

    assert run(capsys, str(target), "--human-style", "")[0] == 0
    assert "Text for people" not in facts_lines(target)
    assert "style" not in manifest(target)["artifacts"][1]
    assert run(capsys, str(target), "--check")[0] == 0


def test_an_unknown_human_style_is_refused_and_check_takes_none(tmp_path: Path) -> None:
    target = repo(tmp_path / "t", {"README.md": "# T\n"})

    with pytest.raises(SystemExit):
        adopt.main([str(target), "--human-style", "plain"])
    with pytest.raises(SystemExit):
        adopt.main([str(target), "--check", "--human-style", "ste"])


# --- what an install warns about ---------------------------------------------------


def warnings(out: str) -> list[str]:
    return [line for line in out.splitlines() if line.startswith("warning")]


def test_detect_reads_a_codex_folder_as_codex(tmp_path: Path, capsys: Capture) -> None:
    target = repo(tmp_path / "t", {"AGENTS.md": "# P\n", ".codex/config.toml": ""})

    code, out, _ = run(capsys, str(target), "--detect")

    words = shlex.split(out, comments=True)
    assert code == 0 and words[words.index("--harness") + 1] == "codex"


def test_detect_says_a_test_command_it_did_not_read_from_ci_runs_on_the_host(
    tmp_path: Path, capsys: Capture
) -> None:
    guessed = repo(tmp_path / "guessed", {"pytest.ini": "[pytest]\n"})
    workflow = "jobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - run: pytest -q\n"
    from_ci = repo(
        tmp_path / "ci", {"pytest.ini": "[pytest]\n", ".github/workflows/c.yml": workflow}
    )

    _, out, _ = run(capsys, str(guessed), "--detect")
    assert f"# {PYTEST} is what pytest.ini suggests" in out and "on the host" in out
    _, out, _ = run(capsys, str(from_ci), "--detect")
    assert "on the host" not in out


def test_every_install_keeps_outcomebounds_local_records_out_of_git(
    tmp_path: Path, capsys: Capture
) -> None:
    target = repo(tmp_path / "t")
    assert run(capsys, str(target))[0] == 0

    records = [
        ".outcomebound/research-inbox/20261004-x.json",
        ".outcomebound/.outcomebound-checks/a.log",
        ".outcomebound/plans/.outcomebound-checks/b.log",
    ]
    listed = subprocess.run(
        [GIT, "check-ignore", "--no-index", *records, adopt.MANIFEST],
        cwd=target,
        capture_output=True,
        text=True,
    ).stdout.split()
    assert listed == records
    assert run(capsys, str(target), "--remove")[0] == 0
    assert not (target / adopt.LOCAL_IGNORE).exists()


def test_an_install_warns_for_each_path_git_ignores(tmp_path: Path, capsys: Capture) -> None:
    target = repo(tmp_path / "t", {".gitignore": ".claude/\n"})

    code, out, _ = run(capsys, str(target), "--harness", "claude-code,codex")

    assert code == 0
    ignored = [line.split()[1].rstrip(":") for line in warnings(out)]
    assert ignored == sorted(path for path in manifest_paths(target) if path.startswith(".claude/"))
    assert all("(.gitignore:1: .claude/)" in line for line in warnings(out))


@pytest.mark.parametrize("extra", [(), ("--dry-run",)], ids=["install", "dry-run"])
def test_a_repeat_install_warns_for_unchanged_owned_paths_and_preserves_unmanaged_paths(
    tmp_path: Path, capsys: Capture, extra: tuple[str, ...]
) -> None:
    """Breaks if an unchanged ignored hook, skill or manifest is omitted, if an unmanaged
    path or a dropped harness is warned about, or if the diagnostic edits project bytes."""

    prefixes = (".claude/", ".agents/", ".codex/")
    unmanaged = ".claude/local-skill/SKILL.md"
    target = repo(
        tmp_path / "t",
        {
            ".gitignore": "\n".join([*prefixes, adopt.MANIFEST, ""]),
            ".claude/settings.json": PROJECT_SETTINGS,
            unmanaged: "# A project's own skill\n",
        },
    )
    assert (
        run(
            capsys,
            str(target),
            "--harness",
            "claude-code,codex",
            "--done",
            ":",
            "--finish-check",
        )[0]
        == 0
    )
    before = snapshot(target)
    expected = sorted(
        {adopt.MANIFEST, *(path for path in manifest_paths(target) if path.startswith(prefixes))}
    )

    code, out, err = run(capsys, str(target), "--harness", "claude-code,codex", *extra)

    assert code == 0, err
    assert [line.split()[1].rstrip(":") for line in warnings(out)] == expected
    assert unmanaged not in out and snapshot(target) == before
    _, out, _ = run(capsys, str(target), "--harness", "codex", "--dry-run")
    assert not any(".claude/" in line for line in warnings(out))
    assert unmanaged not in out and snapshot(target) == before


def manifest_paths(target: Path) -> list[str]:
    return sorted({record["path"] for record in manifest(target)["artifacts"]})


def test_an_install_warns_where_a_tracked_agents_md_holds_uncommitted_changes(
    tmp_path: Path, capsys: Capture
) -> None:
    target = repo(tmp_path / "t", {"AGENTS.md": "# P\n"})
    commit_all(target)
    _, out, _ = run(capsys, str(target), "--dry-run")
    assert warnings(out) == []

    write(target / "AGENTS.md", "# P\n\nA change not committed.\n")
    _, out, _ = run(capsys, str(target))
    [warned] = warnings(out)
    assert "AGENTS.md holds changes that are not committed" in warned


def test_an_install_warns_where_a_harness_also_loads_a_folder_above(
    tmp_path: Path, capsys: Capture
) -> None:
    """Claude Code loads CLAUDE.md files from every folder above the working directory, so a
    parent install's contract loads in a nested repository too."""

    parent = repo(tmp_path / "parent", {"CLAUDE.md": "# Parent\n"})
    child = repo(parent / "child", {"README.md": "# C\n"})

    _, out, _ = run(capsys, str(child), "--harness", "claude-code")
    [warned] = warnings(out)
    assert warned.startswith("warning  claude-code: a session here also loads ../CLAUDE.md")
    _, out, _ = run(capsys, str(child), "--harness", "codex")
    assert warnings(out) == []


def test_a_projects_own_local_ignore_file_is_refused_by_name_even_under_force(
    tmp_path: Path, capsys: Capture
) -> None:
    """adopt now owns .outcomebound/.gitignore whole; a file the project wrote there is never
    replaced, since its lines would be lost."""

    target = repo(tmp_path / "t", {adopt.LOCAL_IGNORE: "/my-own-thing/\n"})
    before = snapshot(target)

    for extra in ((), ("--force",)):
        code, _, err = run(capsys, str(target), *extra)
        assert code == 1 and "move its lines to the root .gitignore" in err
    assert snapshot(target) == before


def test_the_ignored_path_warning_escapes_the_rule_it_quotes(
    tmp_path: Path, capsys: Capture
) -> None:
    target = repo(tmp_path / "t", {".gitignore": "[\x1b.]claude/\n"})

    _, out, _ = run(capsys, str(target), "--harness", "claude-code")

    assert warnings(out) and "\x1b" not in out
    assert "[\\x1b.]claude/" in warnings(out)[0]


def test_a_codex_install_names_the_sandbox_route_for_unattended_sessions(
    tmp_path: Path, capsys: Capture
) -> None:
    """Codex's default sandbox keeps .agents and .git read-only and a Desktop or IDE session
    is reported to have no --add-dir flag (not in the research), so the report names the
    configuration route, UNVERIFIED."""

    target = repo(tmp_path / "t")

    _, out, _ = run(capsys, str(target), "--harness", "codex")
    [line] = [line for line in out.splitlines() if "writable_roots" in line]
    assert line.startswith("UNVERIFIED codex:")
    resolved = target.resolve()
    assert f'"{(resolved / ".agents").as_posix()}"' in line
    assert f'"{(resolved / ".git").as_posix()}"' in line
    _, out, _ = run(capsys, str(target), "--harness", "claude-code")
    assert "writable_roots" not in out


TICKETS_DECLARATION = {
    "version": 1,
    "store": "github",
    "repo": "example/project",
    "label": "ticket",
    "human_label": "human-only",
    "request_label": "human-requested",
    "claims": ".outcomebound/ticket-claims.json",
}


def tickets_target(
    path: Path, cwd: str | None, declares: bool, declared: bool = True, planned: bool = False
) -> Path:
    """A repository whose claims plan sits in `.outcomebound/`, written for the checkout root,
    with the given top-level `cwd`; its one claim declares `app.py` where `declares`, and
    `tests/test_new.py`, which no folder holds yet, where `planned`."""

    claim: dict[str, object] = {"name": "unit", "command": ["true"]}
    if declares or planned:
        claim["required_paths"] = ["app.py"] * declares + ["tests/test_new.py"] * planned
    plan: dict[str, object] = {"version": 1, "claims": [claim]}
    if cwd is not None:
        plan["cwd"] = cwd
    files = {"app.py": "", ".outcomebound/ticket-claims.json": json.dumps(plan)}
    if declared:
        files[".outcomebound/tickets.json"] = json.dumps(TICKETS_DECLARATION)
    return repo(path, files)


def tickets_lines(out: str) -> list[str]:
    return [line for line in warnings(out) if line.startswith("warning  tickets:")]


@pytest.mark.parametrize("declares", [True, False])
@pytest.mark.parametrize("cwd", [None, ".", ".."])
def test_an_install_reports_a_claims_plan_that_runs_in_its_own_folder(
    tmp_path: Path, capsys: Capture, cwd: str | None, declares: bool
) -> None:
    """A claims plan in `.outcomebound/` with no `cwd` or `"cwd": "."` runs its claims there
    since 1.1.0, whether or not a claim declares paths: each install and upgrade warns and says
    to write `"cwd": ".."`, and leaves the plan, the project's file, as it was. `".."` is
    not warned about."""

    target = tickets_target(tmp_path / "t", cwd, declares)
    plan = (target / ".outcomebound/ticket-claims.json").read_bytes()

    code, out, _ = run(capsys, str(target))

    assert code == 0
    assert (target / ".outcomebound/ticket-claims.json").read_bytes() == plan
    lines = tickets_lines(out)
    if cwd == "..":
        assert lines == []
        return
    assert any("runs its claims in .outcomebound/" in line for line in lines), lines
    assert all('"cwd": ".."' in line for line in lines), lines
    assert any("`unit`" in line and ".outcomebound/app.py" in line for line in lines) is declares


@pytest.mark.parametrize("cwd", [None, ".", ".."])
def test_an_install_does_not_read_a_planned_path_as_a_misplaced_cwd(
    tmp_path: Path, capsys: Capture, cwd: str | None
) -> None:
    """A path that an open ticket will add is held from neither the plan's working directory
    nor the checkout root. With `".."` the install gives no `tickets:` warning, so it never
    tells a person to change a `cwd` that already runs at the root; with no `cwd` or `"."` it
    warns only of the path the root holds and of the plan's folder."""

    target = tickets_target(tmp_path / "t", cwd, declares=True, planned=True)

    code, out, _ = run(capsys, str(target))

    assert code == 0
    lines = tickets_lines(out)
    if cwd == "..":
        assert lines == []
        return
    assert len(lines) == 2, lines
    assert not any("test_new.py" in line for line in lines), lines
    assert any("`unit`" in line and ".outcomebound/app.py" in line for line in lines), lines


def test_an_install_says_nothing_of_a_plan_no_tickets_declaration_names(
    tmp_path: Path, capsys: Capture
) -> None:
    """With no `.outcomebound/tickets.json`, or a declaration whose plan is absent, there is no
    claims plan to report on, and `tickets check` refuses the second itself."""

    undeclared = tickets_target(tmp_path / "u", None, True, declared=False)
    code, out, _ = run(capsys, str(undeclared))
    assert code == 0 and tickets_lines(out) == []

    planless = tickets_target(tmp_path / "p", None, True)
    (planless / ".outcomebound/ticket-claims.json").unlink()
    code, out, _ = run(capsys, str(planless))
    assert code == 0 and tickets_lines(out) == []


@pytest.mark.parametrize("harnesses", ["claude-code,codex", "codex,claude-code"])
def test_implicit_adoption_preserves_a_multi_harness_install(
    tmp_path: Path, capsys: Capture, harnesses: str
) -> None:
    target = repo(tmp_path / "target")
    commit_all(target)
    code, _, _ = run(
        capsys, str(target), "--harness", harnesses, "--done", "true", "--finish-check"
    )
    assert code == 0
    before = snapshot(target)
    assert run(capsys, str(target), "--check")[0] == 0
    assert run(capsys, str(target))[0] == 0
    assert snapshot(target) == before
    assert run(capsys, str(target), "--check")[0] == 0
