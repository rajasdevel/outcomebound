"""The install route: adopt installs, upgrades, checks and removes through one safe writer.

Every target is a Git repository under `tmp_path`, and every assertion is about bytes on
disk, the manifest or an exit status. A printed line is asserted only where it is what a person
reads and acts on: the footprint's figure, the nested byte warning, the `kept` line, the claims
plan warning, the stale and edited lines of `--check` and the command it ends with, which exist
only as output.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from outcomebound_tools import adopt, facts, fileplan, fragments, identity, paths
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
from tests.portable import WINDOWS, needs_symlinks, write

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


def names_plain_adopt(out: str, target: Path) -> bool:
    """Whether `--check` ends with one `next:` line that sends the person to `adopt` on the
    target and not to `--force`; the check that runs the command it prints is the one that holds
    its wording."""

    [line] = next_lines(out)
    return f"adopt {paths.shell_path(target)}" in line and "--force" not in line


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
        *[("skill", f".claude/skills/{file}", file.split("/")[0]) for file in SKILL_FILES],
    ]
    assert records[1]["fragments"] == ["python"]
    by_path = {record["path"]: record for record in records}
    assert all(r["harnesses"] == ["claude-code"] for r in records if r["kind"] == "skill")
    for record in records:
        assert adopt.state(target, ROOT, record, records) == "current"
    assert (by_path[CLAUDE_BRIEF]["sha256"], by_path[CLAUDE_SKILL]["sha256"]) == (
        sha(brief),
        sha(skill),
    )
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
    # Beside each gained skill arrive its folders and reference files, and nothing else.
    extra = {key for key in after if key not in before}
    assert all(
        any(key.startswith(f".claude/skills/{name}/") for name in gained) for key in extra
    ), extra
    assert {key: v for key, v in after.items() if key in before} == before
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
    assert names_plain_adopt(out, target)

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
    assert names_plain_adopt(out, target)

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
        **{
            f".claude/skills/{file}": "current"
            for file in SKILL_FILES
            if f".claude/skills/{file}" not in (CLAUDE_BRIEF, CLAUDE_SKILL)
        },
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


def command_of(out: str) -> list[str]:
    """The install command `--detect` printed: its first line alone, every other line a comment
    that a shell reads as nothing, so that pasting the output runs the command only."""

    first, *rest = out.splitlines()
    assert all(line.startswith("# ") for line in rest), rest
    return shlex.split(first)


def test_detect_prints_one_command_that_installs(tmp_path: Path, capsys: Capture) -> None:
    target = repo(tmp_path / "t", {"CLAUDE.md": "# Notes\n", "pyproject.toml": "[project]\n"})
    before = snapshot(target)

    code, out, _ = run(capsys, str(target), "--detect")

    assert code == 0 and out.splitlines()[0].startswith("outcomebound adopt ")
    assert snapshot(target) == before
    words = command_of(out)
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
    assert "`git init` there, then `outcomebound adopt . --detect`" in err
    for arguments in (("--harness", "codex"), ("--remove",)):
        err = run(capsys, str(target), *arguments)[2]
        assert "`git init` there, then `outcomebound adopt . --detect`" in err


def test_detect_without_a_harness_sign_proposes_generic(tmp_path: Path, capsys: Capture) -> None:
    target = repo(tmp_path / "t", {"README.md": "# T\n"})

    code, out, _ = run(capsys, str(target), "--detect")

    assert code == 0
    words = command_of(out)
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


def notes_of(out: str) -> list[str]:
    """Every line of `--detect` after the command, each a comment."""

    command_of(out)
    return out.splitlines()[1:]


GUIDE_LINE = (
    f"# onboarding guide for an agent: {(ROOT / 'skills/adopt-outcomebound/SKILL.md').as_posix()}"
)


def test_detect_puts_every_note_on_a_comment_line_and_ends_on_the_guide(
    tmp_path: Path, capsys: Capture
) -> None:
    """Breaks if a note trails the command on its line, so that a shell runs more than the
    command, a note lacks `#`, or the last line does not name the guide as an absolute path from
    the engine."""

    target = repo(tmp_path / "t", {"pytest.ini": "[pytest]\n"})
    before = snapshot(target)

    code, out, _ = run(capsys, str(target), "--detect")

    assert code == 0 and snapshot(target) == before
    first, *rest = out.splitlines()
    assert "#" not in first and first.count("\n") == 0
    assert f"# {PYTEST} is what pytest.ini suggests, not a command CI runs" in rest[0]
    assert "# no harness file found; or one of: " in "\n".join(rest)
    assert rest[-1] == GUIDE_LINE and Path(rest[-1].split(": ", 1)[1]).is_absolute()


@pytest.mark.parametrize(
    ("files", "command"),
    [
        pytest.param({"Makefile": "setup:\n\tpip install -e .\n"}, "make setup", id="make-setup"),
        pytest.param({"GNUmakefile": "bootstrap: deps\n\techo\n"}, "make bootstrap", id="gnu"),
        pytest.param({"makefile": ".PHONY: setup\nsetup::\n\ttrue\n"}, "make setup", id="double"),
        pytest.param({"package.json": '{"scripts": {"setup": "x"}}'}, "npm run setup", id="npm"),
        pytest.param(
            {"package.json": '{"scripts": {"bootstrap": "x"}}', "pnpm-lock.yaml": ""},
            "pnpm run bootstrap",
            id="pnpm",
        ),
        pytest.param(
            {"Makefile": "setup:\n\ttrue\n", "bin/setup": "#!/bin/sh\n"}, "make setup", id="first"
        ),
    ],
)
def test_detect_proposes_setup_for_the_projects_own_entry_point_and_runs_nothing(
    tmp_path: Path, capsys: Capture, files: dict[str, str], command: str
) -> None:
    """Breaks if a Make target, a package.json script or an executable script named setup or
    bootstrap is not proposed with `--setup`, if more than the first entry point is proposed,
    or if detection runs the entry point."""

    target = repo(tmp_path / "t", files)
    before = snapshot(target)

    code, out, _ = run(capsys, str(target), "--detect")

    assert code == 0 and snapshot(target) == before
    words = command_of(out)
    assert [words[i + 1] for i, word in enumerate(words) if word == "--setup"] == [command]
    assert f"# setup candidate: {command} (" in out and "proposed with --setup" in out
    assert run(capsys, *words[2:])[0] == 0
    assert facts_lines(target)["Setup"] == f"`{command}`"


@pytest.mark.skipif(WINDOWS, reason="a script is executable by its mode, which Windows lacks")
@pytest.mark.parametrize(
    "relative", ["bin/setup", "script/setup", "script/bootstrap", "scripts/setup.sh"]
)
def test_detect_proposes_an_executable_setup_script_only_where_it_is_executable(
    tmp_path: Path, capsys: Capture, relative: str
) -> None:
    target = repo(tmp_path / "t", {relative: "#!/bin/sh\ntouch ran\n"})
    assert "--setup" not in command_of(run(capsys, str(target), "--detect")[1])

    (target / relative).chmod(0o755)
    before = snapshot(target)
    _, out, _ = run(capsys, str(target), "--detect")

    assert command_of(out)[-2:] == ["--setup", f"./{relative}"] and snapshot(target) == before
    assert not (target / "ran").exists()


@pytest.mark.parametrize(
    "files",
    [
        {"Makefile": "setup := yes\ninstall:\n\ttrue\n"},
        {"Makefile": ".PHONY: setup\n"},
        {"package.json": '{"scripts": {"test": "x", "setup-db": "x"}}'},
        {"package.json": "not json"},
        {"package.json": '{"scripts": ["setup"]}'},
        {"docs/setup": "#!/bin/sh\n"},
    ],
    ids=["variable", "phony", "other-script", "broken", "list", "elsewhere"],
)
def test_detect_proposes_no_setup_without_an_entry_point(
    tmp_path: Path, capsys: Capture, files: dict[str, str]
) -> None:
    target = repo(tmp_path / "t", files)

    _, out, _ = run(capsys, str(target), "--detect")

    assert "--setup" not in command_of(out)
    assert "# no Setup entry point found" in out


@pytest.mark.parametrize(
    ("lockfile", "install"),
    [
        ("package-lock.json", "npm ci"),
        ("pnpm-lock.yaml", "pnpm install --frozen-lockfile"),
        ("uv.lock", "uv sync --frozen"),
        ("Cargo.lock", "cargo fetch --locked"),
        ("go.sum", "go mod download"),
    ],
)
def test_detect_names_a_lockfiles_install_command_as_a_comment_only(
    tmp_path: Path, capsys: Capture, lockfile: str, install: str
) -> None:
    target = repo(tmp_path / "t", {lockfile: ""})

    _, out, _ = run(capsys, str(target), "--detect")

    assert f"# lockfile {lockfile}: {install} installs from it; a candidate for --setup" in out
    assert install not in out.splitlines()[0] and "--setup" not in command_of(out)


GENERATED = """\
# comment
src/gen/** linguist-generated
*.pb.go linguist-generated=true
"quoted dir/*"\tlinguist-generated -diff
docs/** linguist-generated -linguist-generated
vendor/** -linguist-generated
other/** linguist-generated=false
[attr]macro linguist-generated
*.png binary
"""


def test_detect_names_the_generated_paths_the_project_marks(
    tmp_path: Path, capsys: Capture
) -> None:
    target = repo(tmp_path / "t", {".gitattributes": GENERATED})

    _, out, _ = run(capsys, str(target), "--detect")

    assert (
        "# signal generated: .gitattributes; value: src/gen/**, *.pb.go, quoted dir/*; "
        "local slot: Bounds\n"
    ) in out


def test_detect_names_each_tracked_migration_folder_once(tmp_path: Path, capsys: Capture) -> None:
    """Breaks if a folder of many migrations prints once for each file, if an untracked folder
    is read as applied migrations, or if the names discovery reads are not all read."""

    tracked = [
        "db/migrate/001_a.rb",
        "db/migrate/002_b.rb",
        "app/migrations/0001.py",
        "app/migrations/0002.py",
        "service/alembic/versions/x.py",
        "migrate/not-under-db.sql",
    ]
    target = repo(tmp_path / "t", dict.fromkeys(tracked, "x\n"))
    commit_all(target)
    (target / "new/migrations").mkdir(parents=True)
    write(target / "new/migrations/0001.py", "x\n")

    _, out, _ = run(capsys, str(target), "--detect")

    [line] = [text for text in out.splitlines() if "signal migrations" in text]
    assert line == (
        "# signal migrations: app/migrations, db/migrate, service/alembic; local slot: Bounds"
    )


WORKFLOW_PUBLISH = """\
on: push
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - run: echo npm publish
      - run: pytest -q
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: pypa/gh-action-pypi-publish@release/v1
      - uses: actions/checkout@v4
      - run: |
          sudo docker push example/app
          twine upload dist/*
      - run: npm publish --access public && gh release create v1
"""


def test_detect_names_the_publishing_steps_of_a_workflow(tmp_path: Path, capsys: Capture) -> None:
    """Breaks if a step that only mentions a publishing command is a signal, or a step that
    runs one through a wrapper, in a block, or after `&&`, or a publishing action, is missed."""

    target = repo(tmp_path / "t", {".github/workflows/release.yml": WORKFLOW_PUBLISH})

    _, out, _ = run(capsys, str(target), "--detect")

    path = ".github/workflows/release.yml"
    lines = [line for line in out.splitlines() if "signal publishing-workflow" in line]
    assert lines == [
        f"# signal publishing-workflow: {path}; value: job {job}; local slot: Bounds (edges:)"
        for job in (
            "release uses pypa/gh-action-pypi-publish",
            "release runs docker push",
            "release runs twine upload",
            "release runs npm publish",
            "release runs gh release create",
        )
    ]


def test_detect_names_pnpm_flyctl_and_goreleaser_publishing(
    tmp_path: Path, capsys: Capture
) -> None:
    """Breaks if a common publishing form a realistic repository uses is missed."""

    workflow = (
        "on: push\njobs:\n  ship:\n    runs-on: ubuntu-latest\n    steps:\n"
        "      - run: pnpm publish --no-git-checks\n"
        "      - run: flyctl deploy --remote-only\n"
        "      - uses: goreleaser/goreleaser-action@v6\n"
    )
    target = repo(tmp_path / "t", {".github/workflows/ship.yml": workflow})

    _, out, _ = run(capsys, str(target), "--detect")

    found = [line for line in out.splitlines() if "signal publishing-workflow" in line]
    assert any("runs pnpm publish" in line for line in found), found
    assert any("runs flyctl deploy" in line for line in found), found
    assert any("uses goreleaser/goreleaser-action" in line for line in found), found


def test_detect_names_the_runtime_versions_the_project_pins(
    tmp_path: Path, capsys: Capture
) -> None:
    files = {
        ".python-version": "3.12\n",
        ".nvmrc": "v20.11.0\n",
        ".tool-versions": "python 3.12.1\n# comment\nnodejs 20.11.0\n",
        "rust-toolchain.toml": '[toolchain]\nchannel = "1.75"\n',
        "pyproject.toml": (
            '[tool.x]\nrequires-python = "<2"\n[project]\nrequires-python = ">=3.10"\n'
        ),
        "go.mod": "module x\n\ngo 1.22\n",
    }
    target = repo(tmp_path / "t", files)

    _, out, _ = run(capsys, str(target), "--detect")

    found = [line for line in out.splitlines() if "signal runtime-version" in line]
    assert found == [
        "# signal runtime-version: .python-version; value: 3.12; local slot: Context",
        "# signal runtime-version: .nvmrc; value: v20.11.0; local slot: Context",
        "# signal runtime-version: .tool-versions; value: python 3.12.1; nodejs 20.11.0; "
        "local slot: Context",
        "# signal runtime-version: rust-toolchain.toml; value: 1.75; local slot: Context",
        "# signal runtime-version: pyproject.toml; value: requires-python >=3.10; "
        "local slot: Context",
        "# signal runtime-version: go.mod; value: go 1.22; local slot: Context",
    ]


def test_detect_names_the_environment_variables_and_never_a_value(
    tmp_path: Path, capsys: Capture
) -> None:
    env = (
        "# a comment\nAPI_URL=https://s3cr3t.example\nexport TOKEN='s3cr3t-value'\n"
        "EMPTY=\nbad line\n"
    )
    target = repo(tmp_path / "t", {".env.example": env, ".env.sample": "OTHER=1\n"})

    _, out, _ = run(capsys, str(target), "--detect")

    names = "API_URL, TOKEN, EMPTY"
    assert f"# signal environment-names: .env.example; value: {names}; local slot: Context" in out
    assert "# signal environment-names: .env.sample; value: OTHER; local slot: Context" in out
    assert "s3cr3t" not in out


WORKFLOW_ENV = """\
on: push
env:
  SHARED: ${{ secrets.WORKFLOW_WIDE }}
jobs:
  test:
    runs-on: ubuntu-latest
    env:
      KEY: ${{ secrets.API_KEY }}
      TOKEN: ${{ secrets.GITHUB_TOKEN }}
    steps:
      - run: pytest -q
  lint:
    runs-on: ubuntu-latest
    steps:
      - run: echo ${{ secrets['LINT_KEY'] }}
"""


def test_detect_names_the_secrets_a_workflow_uses_with_their_jobs_and_no_value(
    tmp_path: Path, capsys: Capture
) -> None:
    target = repo(tmp_path / "t", {".github/workflows/ci.yml": WORKFLOW_ENV})

    _, out, _ = run(capsys, str(target), "--detect")

    assert (
        "# signal ci-secrets: .github/workflows/ci.yml; value: API_KEY in job test; "
        "LINT_KEY in job lint; WORKFLOW_WIDE in the workflow; local slot: Distinguish\n"
    ) in out
    assert "GITHUB_TOKEN" not in out.split("signal ci-secrets")[1].split("\n")[0]
    [line] = [text for text in out.splitlines() if "readiness" in text and "secrets." in text]
    assert line == (
        "# readiness UNVERIFIED: the CI test command `pytest -q` runs in job test of "
        ".github/workflows/ci.yml, which names secrets.API_KEY, secrets.WORKFLOW_WIDE; next: that "
        "command cannot run on the host without the secret"
    )


def test_a_secret_another_step_uses_does_not_reach_the_test_command(
    tmp_path: Path, capsys: Capture
) -> None:
    """Breaks if a secret one step of a job uses is read as needed by the job's test command,
    which another step runs; the job's own `env` reaches every step and still counts."""

    workflow = (
        "on: push\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n"
        "      - run: pytest -q\n"
        "      - run: ./scrub\n        env:\n          LIST: ${{ secrets.SCRUB_LIST }}\n"
    )
    target = repo(tmp_path / "t", {".github/workflows/ci.yml": workflow})
    _, out, _ = run(capsys, str(target), "--detect")
    assert "signal ci-secrets" in out and "readiness UNVERIFIED: the CI test command" not in out

    job_wide = workflow.replace(
        "    runs-on: ubuntu-latest\n",
        "    runs-on: ubuntu-latest\n    env:\n      K: ${{ secrets.JOB_KEY }}\n",
    )
    shared = repo(tmp_path / "s", {".github/workflows/ci.yml": job_wide})
    _, out, _ = run(capsys, str(shared), "--detect")
    assert "which names secrets.JOB_KEY;" in out


def test_detect_names_no_secret_for_a_test_job_that_names_none(
    tmp_path: Path, capsys: Capture
) -> None:
    workflow = WORKFLOW_ENV.replace("  SHARED: ${{ secrets.WORKFLOW_WIDE }}\n", "").replace(
        "      KEY: ${{ secrets.API_KEY }}\n", ""
    )
    target = repo(tmp_path / "t", {".github/workflows/ci.yml": workflow})

    _, out, _ = run(capsys, str(target), "--detect")

    assert "signal ci-secrets" in out and "readiness UNVERIFIED: the CI test command" not in out


def test_detect_reads_no_done_candidate_and_a_missing_lockfile_as_unverified(
    tmp_path: Path, capsys: Capture
) -> None:
    target = repo(tmp_path / "t", {"package.json": "{}"})

    _, out, _ = run(capsys, str(target), "--detect")

    assert "# readiness UNVERIFIED: no Done candidate; next: record one with --done" in out
    assert (
        "# readiness UNVERIFIED: package.json has no lockfile beside it; next: a library may "
        "commit none; an application pins its dependencies"
    ) in out
    write(target / "yarn.lock", "")
    _, out, _ = run(capsys, str(target), "--detect")
    assert "has no lockfile beside it" not in out
    assert "no Done candidate" in out
    assert run(capsys, str(target), "--done", "true")[0] == 0
    assert "no Done candidate" not in run(capsys, str(target), "--detect")[1]


def test_detect_on_a_folder_with_only_git_names_the_new_project_route(
    tmp_path: Path, capsys: Capture
) -> None:
    """Breaks if the reference is named where the engine lacks the file, is not named by its
    engine path where it has it, or is named for a folder that holds code or any other file."""

    source = engine_copy(tmp_path)
    empty = repo(tmp_path / "empty")
    code_only = repo(tmp_path / "code", {"app.py": "x = 1\n"})
    reference = source / "skills/using-outcomebound/references/new-project.md"
    reference.unlink(missing_ok=True)

    _, out, _ = run(capsys, str(empty), "--detect", source=source)
    assert "# nothing here but .git: a new project starts from this command\n" in out
    assert "new-project.md" not in out and "README" not in out

    write(reference, "# New project\n")
    _, out, _ = run(capsys, str(empty), "--detect", source=source)
    assert f"a new project starts from this command; read {reference.resolve().as_posix()}" in out
    assert out.splitlines()[-1].endswith(
        f"{source.resolve().as_posix()}/skills/adopt-outcomebound/SKILL.md"
    )

    _, out, _ = run(capsys, str(code_only), "--detect", source=source)
    assert "a new project starts" not in out and "Start a new project" not in out


SCAFFOLD_LINE = (
    "# a new project: outcomebound scaffold . --lifecycle <preset> previews the files of its "
    "lifecycle; the new-project reference says how to choose\n"
)


def test_detect_on_an_empty_repository_names_the_scaffold_preview(
    tmp_path: Path, capsys: Capture
) -> None:
    """Breaks if `--detect` in a folder with only `.git` does not name the scaffold's preview
    where the engine holds the scaffold manifest, names it where the engine has none, or names it
    for a folder that holds any other file."""

    source = engine_copy(tmp_path)
    empty = repo(tmp_path / "empty")
    code_only = repo(tmp_path / "code", {"app.py": "x = 1\n"})

    _, out, _ = run(capsys, str(empty), "--detect", source=source)
    assert "outcomebound scaffold" not in out

    manifest = source / "templates/scaffold/scaffold.json"
    manifest.parent.mkdir(parents=True)
    shutil.copy2(ROOT / "templates/scaffold/scaffold.json", manifest)
    _, out, _ = run(capsys, str(empty), "--detect", source=source)
    assert SCAFFOLD_LINE in out
    assert out.index("a new project starts from this command") < out.index(SCAFFOLD_LINE)

    _, out, _ = run(capsys, str(code_only), "--detect", source=source)
    assert "outcomebound scaffold" not in out


@pytest.mark.skipif(WINDOWS, reason="a control character cannot be part of a Windows file name")
def test_detect_escapes_every_string_the_target_gave(tmp_path: Path, capsys: Capture) -> None:
    """Breaks if a path, a CI command, a pattern or a value that the target holds reaches the
    terminal with a control or bidirectional character in it, on the command line or a note."""

    workflow = (
        "jobs:\n  t:\n    runs-on: ubuntu-latest\n    steps:\n      - run: pytest -q 'a\u202eb'\n"
    )
    files = {
        ".github/workflows/ci.yml": workflow,
        ".gitattributes": "gen/\u202e** linguist-generated\n",
        ".python-version": "3.12\x1b[2J\n",
    }
    target = repo(tmp_path / "dir\x1b[31mred", files)

    code, out, _ = run(capsys, str(target), "--detect")

    assert code == 0
    assert all(" " <= char <= "~" or char == "\n" for char in out), out
    for escaped in ("\\u001b[31mred", "\\u202e", "\\u001b[2J"):
        assert escaped in out


def test_detect_prints_the_engines_own_paths_as_they_are(tmp_path: Path, capsys: Capture) -> None:
    """Breaks if the guide's path, which an agent opens, is escaped though no target gave it,
    or if letters beyond ASCII in the target's own path are escaped in the command a person
    pastes, which would then name a folder that does not exist."""

    source = tmp_path / "engine-\u65e5\u672c"
    shutil.copytree(engine_copy(tmp_path), source)
    write(source / "skills/using-outcomebound/references/new-project.md", "# New\n")
    target = repo(tmp_path / "t-\u65e5\u672c")

    _, out, _ = run(capsys, str(target), "--detect", source=source)

    first, *rest = out.splitlines()
    assert "t-\u65e5\u672c" in first and "\\u65e5" not in first
    reference = f"{source.resolve().as_posix()}/skills/using-outcomebound/references/new-project.md"
    assert (
        f"# nothing here but .git: a new project starts from this command; read {reference}" in rest
    )
    assert rest[-1] == (
        f"# onboarding guide for an agent: {source.resolve().as_posix()}"
        "/skills/adopt-outcomebound/SKILL.md"
    )


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
    assert lines["Done"] == "`make check` and `make test` (the full suite)"
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


def test_setup_is_recorded_in_run_order_kept_cleared_and_never_run(
    tmp_path: Path, capsys: Capture
) -> None:
    """Breaks if `--setup` runs a command, loses run order, is lost on a re-run that names none,
    survives `--setup ''`, or the report stops naming the fact when none is recorded."""

    target = repo(tmp_path / "t", {".github/workflows/ci.yml": WORKFLOW})
    ran = tmp_path / "setup-ran"
    first = ("--harness", "codex", "--done", "make test")

    _, out, _ = run(capsys, str(target), *first)

    assert "Setup (none recorded; --setup records one)" in out
    assert "UNVERIFIED Setup" not in out
    assert "Setup" not in facts_lines(target)

    code, out, err = run(
        capsys, str(target), "--setup", f"touch {ran.as_posix()}", "--setup", "make deps"
    )

    assert code == 0, err
    assert not ran.exists() and "UNVERIFIED Setup" not in out
    lines = facts_lines(target)
    assert list(lines) == ["Done", "Setup", "CI test", "Precedence"]
    assert lines["Setup"] == f"`touch {ran.as_posix()}` and `make deps`"
    assert manifest(target)["artifacts"][1]["setup"] == [f"touch {ran.as_posix()}", "make deps"]
    assert run(capsys, str(target), "--check")[0] == 0

    before = snapshot(target)
    assert run(capsys, str(target))[0] == 0
    assert run(capsys, str(target), "--done", "make check")[0] == 0
    assert snapshot(target)["AGENTS.md"] != before["AGENTS.md"]
    assert facts_lines(target)["Setup"] == lines["Setup"]

    code, out, _ = run(capsys, str(target), "--setup", "")
    assert code == 0 and "Setup (none recorded; --setup records one)" in out
    assert "Setup" not in facts_lines(target)
    assert "setup" not in manifest(target)["artifacts"][1]
    assert run(capsys, str(target), "--check")[0] == 0


def test_a_setup_command_is_one_line_and_check_takes_none(tmp_path: Path, capsys: Capture) -> None:
    target = repo(tmp_path / "t", {"README.md": "# T\n"})

    code, _, err = run(capsys, str(target), "--setup", "make\ndeps")

    assert code == 1 and "a --setup command is one line" in err
    assert not (target / adopt.MANIFEST).exists()
    for mode in ("--check", "--detect", "--remove"):
        with pytest.raises(SystemExit) as refused:
            adopt.main([str(target), mode, "--setup", "make deps"])
        assert refused.value.code == 2


def test_check_recomputes_the_facts_from_the_recorded_setup(
    tmp_path: Path, capsys: Capture
) -> None:
    """A Setup list in the record that the block does not show reads the block stale, naming
    the fact; a record that is not a list of commands is refused."""

    target = repo(tmp_path / "t", {"README.md": "# T\n"})
    assert run(capsys, str(target), "--done", "make test", "--setup", "make deps")[0] == 0
    path = target / adopt.MANIFEST
    document = json.loads(path.read_text(encoding="utf-8"))
    document["artifacts"][1]["setup"] = ["make deps", "make more"]
    write(path, json.dumps(document, indent=2) + "\n")

    code, out, _ = run(capsys, str(target), "--check")

    assert code == 1
    assert "stale    AGENTS.md (project-facts): Setup moved" in out

    document["artifacts"][1]["setup"] = "make deps"
    write(path, json.dumps(document, indent=2) + "\n")

    code, _, err = run(capsys, str(target), "--check")

    assert code == 1 and "the setup recorded for AGENTS.md are not a list of names" in err


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
        facts.ONCE,
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
    lines = [facts.ONCE]
    lines += [f"- {adopt.CONDITIONS[name]}: read {path}" for name, path in generic.items()]
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
    assert "has not used is explained or left out" in lines["Text for people"]
    assert "save one a check or the project's rule requires" in lines["Text for people"]
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
        encoding="utf-8",
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
    """Breaks if an unchanged ignored skill or manifest is omitted, if an unmanaged
    path or a dropped harness is warned about, or if the diagnostic edits project bytes."""

    prefixes = (".claude/", ".agents/", ".codex/")
    unmanaged = ".claude/local-skill/SKILL.md"
    target = repo(
        tmp_path / "t",
        {
            ".gitignore": "\n".join([*prefixes, adopt.MANIFEST, ""]),
            ".claude/settings.json": '{"model": "x"}\n',
            unmanaged: "# A project's own skill\n",
        },
    )
    assert run(capsys, str(target), "--harness", "claude-code,codex", "--done", ":")[0] == 0
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


def test_a_linked_worktree_under_its_own_project_does_not_warn_of_the_project_file(
    tmp_path: Path, capsys: Capture
) -> None:
    """The workspace fragment puts worktrees under the project's .agents/worktrees, where the
    folder above is the same project's own checkout: its instruction file is not foreign. A
    nested repository of another project still warns."""

    main = repo(tmp_path / "main", {"CLAUDE.md": "# Project\n"})
    git = ["git", "-c", "user.name=t", "-c", "user.email=t@example.com"]
    subprocess.run([*git, "add", "-A"], cwd=main, check=True)
    subprocess.run([*git, "commit", "-qm", "init"], cwd=main, check=True)
    linked = main / ".agents" / "worktrees" / "w"
    subprocess.run([*git, "worktree", "add", "-q", str(linked)], cwd=main, check=True)
    foreign = repo(main / "other", {"README.md": "# O\n"})

    _, out, _ = run(capsys, str(linked), "--harness", "claude-code")
    assert warnings(out) == []
    _, out, _ = run(capsys, str(foreign), "--harness", "claude-code")
    assert any("also loads ../CLAUDE.md" in line for line in warnings(out))


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
    code, _, _ = run(capsys, str(target), "--harness", harnesses, "--done", "true")
    assert code == 0
    before = snapshot(target)
    assert run(capsys, str(target), "--check")[0] == 0
    assert run(capsys, str(target))[0] == 0
    assert snapshot(target) == before
    assert run(capsys, str(target), "--check")[0] == 0


def test_an_install_warns_of_each_stale_reference_and_refuses_nothing(
    tmp_path: Path, capsys: Capture
) -> None:
    """Breaks if an install or an upgrade stays silent about a script the project's own
    instructions name and the target no longer holds, or refuses the install for it."""

    files = {
        "AGENTS.md": "# Project\n\nRun `npm run gone` and read `docs/kept.md`.\n",
        "package.json": '{"scripts": {"build": "x"}}\n',
        "docs/kept.md": "# Kept\n",
    }
    target = repo(tmp_path / "t", files)

    code, out, _ = run(capsys, str(target), "--harness", "claude-code")

    assert code == 0
    stale = [line for line in out.splitlines() if "stale reference" in line]
    assert len(stale) == 1 and stale[0].startswith("warning") and "AGENTS.md:3" in stale[0]
    assert "gone" in stale[0] and "kept.md" not in stale[0]


def test_an_install_warns_of_each_hook_that_names_a_project_file_from_the_working_directory(
    tmp_path: Path, capsys: Capture
) -> None:
    """Breaks if an install stays silent about a project hook that Claude Code cannot find once
    the agent's `cd` moves the working directory (#113), warns of a hook that names its file
    from `$CLAUDE_PROJECT_DIR`, runs a command on PATH or names no file of the target, or
    refuses the install for it."""

    settings = {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "Bash",
                    "hooks": [
                        {"type": "command", "command": "bash scripts/hooks/guard.sh"},
                        {
                            "type": "command",
                            "command": 'bash "$CLAUDE_PROJECT_DIR"/scripts/hooks/guard.sh',
                        },
                        {"type": "command", "command": "echo not/a/file"},
                    ],
                }
            ],
            "Stop": [{"hooks": [{"type": "command", "command": "./scripts/hooks/guard.sh"}]}],
        }
    }
    files = {
        ".claude/settings.json": json.dumps(settings) + "\n",
        "scripts/hooks/guard.sh": "exit 0\n",
    }
    target = repo(tmp_path / "t", files)

    code, out, _ = run(capsys, str(target), "--harness", "claude-code", "--done", "true")

    assert code == 0
    warned = [line for line in out.splitlines() if "relative to the working directory" in line]
    assert len(warned) == 2 and all(line.startswith("warning") for line in warned)
    assert "PreToolUse hook `bash scripts/hooks/guard.sh`" in warned[0]
    assert "Stop hook `./scripts/hooks/guard.sh`" in warned[1]
    assert all("$CLAUDE_PROJECT_DIR" in line for line in warned)


def test_a_report_counts_skill_files_and_keeps_every_other_file_on_its_own_line(
    tmp_path: Path, capsys: Capture
) -> None:
    """A three-harness install writes hundreds of skill files; one summary line per skills
    folder keeps the warnings and the other files in view, and a dry run does not list each
    new skill file again."""

    target = repo(tmp_path / "t", {"README.md": "# T\n"})

    _, out, _ = run(capsys, str(target), "--harness", "claude-code,codex,gemini", "--dry-run")
    lines = out.splitlines()
    assert len(lines) < 60
    assert (
        sum(
            re.fullmatch(r"create   \.\w+/skills/: \d+ files in 14 skills", x) is not None
            for x in lines
        )
        == 3
    )
    assert not any("SKILL.md" in line for line in lines)
    assert any(line.startswith("create   AGENTS.md") for line in lines)

    run(capsys, str(target), "--harness", "claude-code,codex,gemini")
    path = target / ".claude" / "skills" / "diagnose" / "SKILL.md"
    path.write_text("changed\n", encoding="utf-8")
    _, out, _ = run(capsys, str(target), "--force")
    assert re.search(r"^update   \.claude/skills/: 1 file in 1 skill$", out, re.MULTILINE)
