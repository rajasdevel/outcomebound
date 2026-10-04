"""The install route: adopt installs, upgrades, checks and removes through one safe writer.

Every target is a Git repository under `tmp_path`, and every assertion is about bytes on
disk, the manifest or an exit status, never about a sentence adopt prints; the printed things
read are the footprint's figure and the finish check's statement per harness, which exist only
as output.
"""

from __future__ import annotations

import hashlib
import json
import os
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from outcomebound_tools import adopt, facts, fileplan, finish_check, fragments, identity

ROOT = Path(__file__).resolve().parent.parent
GIT = shutil.which("git") or "git"
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
CLAUDE_SKILL = ".claude/skills/using-outcomebound/SKILL.md"
CLAUDE_BRIEF = ".claude/skills/decision-brief/SKILL.md"
# One `skill` record per skill an install carries, for each harness directory.
SKILL_RECORDS = ["skill"] * len(adopt.SKILLS)
GENERIC_SKILL = ".outcomebound/skills/using-outcomebound/SKILL.md"
PYTHON_FRAGMENT = ".outcomebound/fragments/python.md"
LAUNCHER = ROOT / "scripts" / "outcomebound"
Capture = pytest.CaptureFixture[str]


def repo(path: Path, files: dict[str, str] | None = None) -> Path:
    """A fresh Git repository at `path` holding `files`, by relative path."""

    path.mkdir(parents=True)
    subprocess.run([GIT, "init", "-q", str(path)], check=True)
    for name, text in (files or {}).items():
        (path / name).parent.mkdir(parents=True, exist_ok=True)
        (path / name).write_text(text, encoding="utf-8")
    return path


def run(capsys: Capture, *argv: str, source: Path = ROOT) -> tuple[int, str, str]:
    code = adopt.main(list(argv), source=source)
    out, err = capsys.readouterr()
    return code, out, err


def snapshot(root: Path) -> dict[str, bytes]:
    """Every file and symlink under `root` outside `.git`, by relative path."""

    found: dict[str, bytes] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if relative.parts[0] == ".git":
            continue
        if path.is_symlink():
            found[relative.as_posix()] = b"-> " + os.readlink(path).encode()
        elif path.is_file():
            found[relative.as_posix()] = path.read_bytes()
    return found


def manifest(target: Path) -> dict[str, Any]:
    document: dict[str, Any] = json.loads((target / adopt.MANIFEST).read_text(encoding="utf-8"))
    return document


def blocks(target: Path, name: str) -> dict[str, identity.ManagedBlock]:
    text = (target / name).read_text(encoding="utf-8")
    return {block.block_id: block for block in identity.find_managed_blocks(text)}


def states(out: str) -> dict[str, str]:
    """`--check` output as {record label: state}, any detail after the label and the closing
    `next:` line left out."""

    rows = [line.split(None, 1) for line in out.splitlines() if not line.startswith("next: ")]
    return {name.split(": ", 1)[0]: found for found, name in rows}


def next_lines(out: str) -> list[str]:
    return [line for line in out.splitlines() if line.startswith("next: ")]


def kinds(target: Path) -> list[str]:
    return [record["kind"] for record in manifest(target)["artifacts"]]


def engine_copy(tmp_path: Path) -> Path:
    """The parts of this checkout adopt renders from, copied so a test can change them."""

    source = tmp_path / "engine"
    for directory in ("fragments", "adapters", "skills"):
        shutil.copytree(ROOT / directory, source / directory)
    for name in ("VERSION", adopt.KERNEL_TEMPLATE, "templates/fragment-local.md"):
        (source / name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, source / name)
    return source


def change_kernel(source: Path, version: str) -> None:
    template = source / adopt.KERNEL_TEMPLATE
    text = template.read_text(encoding="utf-8")
    template.write_text(text.replace("not least work.", "not least work, now."), encoding="utf-8")
    (source / "VERSION").write_text(version + "\n", encoding="utf-8")


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
        ("pointer", "CLAUDE.md", "pointer-claude-md"),
        ("skill", CLAUDE_BRIEF, "decision-brief"),
        ("skill", ".claude/skills/gather-requirements/SKILL.md", "gather-requirements"),
        ("skill", ".claude/skills/tests-worth-keeping/SKILL.md", "tests-worth-keeping"),
        ("skill", CLAUDE_SKILL, "using-outcomebound"),
    ]
    assert records[1]["fragments"] == ["python"]
    assert records[5]["harnesses"] == records[6]["harnesses"] == ["claude-code"]
    for record in records:
        assert adopt.state(target, ROOT, record, records) == "current"
    assert (records[5]["sha256"], records[-1]["sha256"]) == (sha(brief), sha(skill))
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
    agents.write_text(edited, encoding="utf-8")

    code, _, err = run(capsys, str(target))

    assert code == 1 and "AGENTS.md" in err
    assert agents.read_text(encoding="utf-8") == edited

    code, _, err = run(capsys, str(target), "--force")

    assert code == 0, err
    kernel = adopt.kernel_block(ROOT).encode()
    assert adopt.block_text(agents.read_text(encoding="utf-8"), adopt.KERNEL) == kernel


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
    (target / adopt.LOCAL_FRAGMENT).write_text(padded, encoding="utf-8")
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
    assert kinds(target) == ["block", "block", "block", *SKILL_RECORDS]
    assert "CLAUDE.md" not in facts_lines(target)["Precedence"]
    code, out, _ = run(capsys, str(target), "--check")
    assert code == 0 and set(states(out).values()) == {"current"}


def test_a_claude_md_in_a_folder_above_brings_the_import_block_back(
    tmp_path: Path, capsys: Capture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A CLAUDE.md above the target stops Claude Code reading AGENTS.md there too, so the
    import block is written; the person's own ~/.claude/CLAUDE.md is user memory and does not."""

    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "CLAUDE.md").write_text("# Mine\n", encoding="utf-8")
    plain = repo(tmp_path / "plain")
    assert run(capsys, str(plain), "--harness", "claude-code")[0] == 0
    assert not (plain / "CLAUDE.md").exists()

    (tmp_path / "work").mkdir()
    (tmp_path / "work" / "CLAUDE.md").write_text("# Team\n", encoding="utf-8")
    below = repo(tmp_path / "work" / "t")
    assert run(capsys, str(below), "--harness", "claude-code")[0] == 0
    assert "@AGENTS.md" in (below / "CLAUDE.md").read_text(encoding="utf-8")


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
        (target / seeded).write_text("# Mine\n", encoding="utf-8")
    before = {path: data for path, data in snapshot(target).items() if path != "CLAUDE.md"}

    code, _, err = run(capsys, str(target), "--harness", "claude-code")

    assert code == 0, err
    assert list(blocks(target, "CLAUDE.md")) == ["pointer-claude-md"]
    assert {path: snapshot(target)[path] for path in before} == before
    assert kinds(target) == ["block", "block", "block", "pointer", *SKILL_RECORDS]


def test_an_import_block_an_older_engine_wrote_is_kept_until_its_file_is_gone(
    tmp_path: Path, capsys: Capture
) -> None:
    """An upgrade changes no byte of a CLAUDE.md that an engine without the rule wrote. Once
    the project deletes it, the next run drops its record and writes it no more."""

    source = engine_copy(tmp_path)
    table_path = source / "adapters/harnesses.json"
    table = json.loads(table_path.read_text(encoding="utf-8"))
    table["claude-code"]["reads_agents_md"] = None  # an engine without the rule
    table_path.write_text(json.dumps(table), encoding="utf-8")
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
    assert kinds(target) == ["block", "block", "block", *SKILL_RECORDS]
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
    table_path.write_text(json.dumps(table), encoding="utf-8")
    alone, shared = repo(tmp_path / "alone"), repo(tmp_path / "shared")

    assert run(capsys, str(alone), "--harness", "gemini", source=source)[0] == 0
    assert run(capsys, str(shared), "--harness", "gemini,probe", source=source)[0] == 0

    assert not (alone / "GEMINI.md").exists()
    assert list(blocks(shared, "GEMINI.md")) == ["pointer-gemini-md"]


def test_a_claude_md_link_or_import_line_already_loads_agents_md(
    tmp_path: Path, capsys: Capture
) -> None:
    linked = repo(tmp_path / "linked", {"AGENTS.md": "# P\n"})
    (linked / "CLAUDE.md").symlink_to("AGENTS.md")
    imported = repo(tmp_path / "imported", {"CLAUDE.md": "# Notes\n\n@AGENTS.md\n"})

    for target in (linked, imported):
        code, _, err = run(capsys, str(target), "--harness", "claude-code")
        assert code == 0, err
        assert kinds(target) == ["block", "block", "block", *SKILL_RECORDS]
    assert os.readlink(linked / "CLAUDE.md") == "AGENTS.md"
    assert (imported / "CLAUDE.md").read_text(encoding="utf-8") == "# Notes\n\n@AGENTS.md\n"


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
    assert kinds(target) == ["block", "block", "block", *SKILL_RECORDS]


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
        f"{root}/skills/{name}/SKILL.md": [harness]
        for root, harness in (
            (".agents", "codex"),
            (".claude", "claude-code"),
            (".cursor", "cursor"),
        )
        for name in adopt.SKILLS
    }

    assert run(capsys, str(target), "--harness", "codex")[0] == 0

    assert not (target / ".claude").exists() and not (target / ".cursor").exists()
    assert not (target / "CLAUDE.md").exists()
    for name in adopt.SKILLS:
        assert (target / f".agents/skills/{name}/SKILL.md").is_file()
    assert kinds(target) == ["block", "block", "block", *SKILL_RECORDS]


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
    table_path.write_text(json.dumps(table), encoding="utf-8")
    target = repo(tmp_path / "t", {"README.md": "# T\n"})
    before = snapshot(target)

    code, _, err = run(capsys, str(target), "--harness", "claude-code,probe,nope", source=source)

    assert code == 1
    assert "probe" in err and "nope" in err
    assert snapshot(target) == before


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
    (target / adopt.MANIFEST).write_text(json.dumps(document), encoding="utf-8")

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
    (target / adopt.MANIFEST).write_text(json.dumps(document), encoding="utf-8")

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

    (target / CLAUDE_SKILL).write_text("mine\n", encoding="utf-8")
    (target / "CLAUDE.md").write_text("# no import any more\n", encoding="utf-8")
    change_kernel(source, "9.9.9")
    brief = source / "skills/decision-brief/SKILL.md"
    brief.write_text(brief.read_text(encoding="utf-8") + "\nOne more line.\n", encoding="utf-8")

    code, out, _ = run(capsys, str(target), "--check", source=source)

    assert code == 4
    assert states(out) == {
        f"AGENTS.md ({adopt.KERNEL})": "stale",
        f"AGENTS.md ({adopt.FACTS})": "current",
        f"AGENTS.md ({adopt.POINTERS})": "current",
        PYTHON_FRAGMENT: "current",
        "CLAUDE.md (pointer-claude-md)": "missing",
        CLAUDE_BRIEF: "stale",
        CLAUDE_SKILL: "edited",
        ".claude/skills/gather-requirements/SKILL.md": "current",
        ".claude/skills/tests-worth-keeping/SKILL.md": "current",
    }
    assert out.splitlines()[-1] == (
        "next: move each edit out of OutcomeBound's blocks and files, then "
        f"outcomebound adopt {shlex.quote(str(target))} --force makes every record current"
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
        f"next: outcomebound adopt {shlex.quote(str(target))} makes every record current"
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
        f"next: outcomebound adopt {shlex.quote(str(target))} --detect prints the command "
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
    (target / CLAUDE_SKILL).write_text("mine\n", encoding="utf-8")
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
    assert words[:3] == ["outcomebound", "adopt", str(target.resolve())]
    assert words[words.index("--harness") + 1] == "claude-code"
    assert words[words.index("--fragments") + 1] == "python,commands"
    assert run(capsys, *words[2:])[0] == 0
    assert (target / "AGENTS.md").is_file()


def test_detect_proposes_the_test_command_ci_runs(tmp_path: Path, capsys: Capture) -> None:
    """Where the project's CI names its tests, Done is that command, not discovery's guess."""

    workflow = "jobs:\n  test:\n    steps:\n      - run: pytest -q\n"
    files = {"pyproject.toml": "[project]\n", ".github/workflows/ci.yml": workflow}
    target = repo(tmp_path / "t", files)

    code, out, _ = run(capsys, str(target), "--detect")

    words = shlex.split(out, comments=True)
    assert code == 0 and words[words.index("--done") + 1] == "pytest -q"


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
    (target / ".gitignore").write_text(f".agents/{folder}/\n", encoding="utf-8")

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
    workflow.write_text(WORKFLOW.replace("make test", "make test-all"), encoding="utf-8")

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
    agents.write_text(agents.read_text(encoding="utf-8").replace("make test-all", "make x"))
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


def test_the_tickets_fragment_installs_its_skill_and_its_pointer_while_selected(
    tmp_path: Path, capsys: Capture
) -> None:
    target = repo(tmp_path / "t", {"README.md": "# T\n"})
    before = snapshot(target)
    name = "slice-tickets"

    arguments = ("--harness", "claude-code", "--fragments", "tickets")
    assert run(capsys, str(target), *arguments)[0] == 0

    agents = (target / "AGENTS.md").read_text(encoding="utf-8")
    shipped = sorted(p for p in (ROOT / "skills" / name).rglob("*") if p.is_file())
    assert len(shipped) > 1
    for file in shipped:
        relative = file.relative_to(ROOT / "skills").as_posix()
        assert (target / ".claude/skills" / relative).read_bytes() == file.read_bytes()
    path = f".claude/skills/{name}/SKILL.md"
    assert f"{adopt.CONDITIONS[name]}: read {path}" in agents
    code, out, _ = run(capsys, str(target), "--check")
    assert code == 0
    assert states(out)[f".claude/skills/{name}/references/github.md"] == "current"

    assert run(capsys, str(target), "--harness", "claude-code", "--fragments", "")[0] == 0
    assert not (target / ".claude/skills" / name).exists()
    assert name not in (target / "AGENTS.md").read_text(encoding="utf-8")
    assert run(capsys, str(target), "--remove")[0] == 0
    assert snapshot(target) == before


def test_a_skill_the_engine_retired_reads_stale_and_an_upgrade_removes_it(
    tmp_path: Path, capsys: Capture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An install whose fragment once named a skill this engine has since retired keeps no copy
    of it once upgraded."""

    older = engine_copy(tmp_path)
    for relative in ("SKILL.md", "references/github.md"):
        (older / "skills/old-skill" / relative).parent.mkdir(parents=True, exist_ok=True)
        (older / "skills/old-skill" / relative).write_text(f"{relative}\n", encoding="utf-8")
    fragment = older / "fragments/setup/tickets.md"
    text = fragment.read_text(encoding="utf-8")
    fragment.write_text(
        text.replace('"hand-off-tickets"]', '"hand-off-tickets", "old-skill"]'),
        encoding="utf-8",
    )
    target = repo(tmp_path / "t", {"README.md": "# T\n"})
    arguments = ("--harness", "claude-code", "--fragments", "tickets")
    assert run(capsys, str(target), *arguments, source=older)[0] == 0
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
    assert run(capsys, str(target), "--harness", "claude-code", "--fragments", "tickets")[0] == 0
    extra = ".claude/skills/slice-tickets/references/extra.md"
    (target / extra).write_text("ours\n", encoding="utf-8")
    document = manifest(target)
    for record in document["artifacts"]:
        if record["path"] == ".claude/skills/slice-tickets/references/github.md":
            record.update(path=extra, sha256=sha(b"ours\n"))
    (target / adopt.MANIFEST).write_text(json.dumps(document), encoding="utf-8")

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
        note.write_text("x\n", encoding="utf-8")
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

    assert proposed(with_floor) == [adopt.FLOOR_RUNNER, "python3 -m pytest"]
    assert proposed(without) == ["python3 -m pytest"]
    assert proposed(bare) == []


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
    assert sorted(r["path"] for r in skills) == sorted(generic.values())
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
    """Run an entry's command as its harness would, the launcher standing in for the name on
    PATH, with the stop input both rows send when the guard is unset."""

    words = shlex.split(command)
    assert words[0] == "outcomebound"
    done = subprocess.run(
        [str(LAUNCHER), *words[1:]],
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
    assert hook_records(target) == [
        {
            "kind": "hook",
            "path": path,
            "id": "finish-check",
            "harness": row,
            "timeout": 600,
            "created": not seeded,
            "sha256": sha(finish_check.canonical(ours)),
        }
    ]
    assert fire(target, ours["hooks"][0]["command"])["systemMessage"].startswith(
        "finish-check PASS: true, "
    )
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
    settings.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")

    assert states(run(capsys, str(target), "--check")[1])[name] == "edited"
    edited = snapshot(target)
    assert run(capsys, str(target))[0] == 1 and snapshot(target) == edited
    assert run(capsys, str(target), "--force")[0] == 0
    assert states(run(capsys, str(target), "--check")[1])[name] == "current"

    recorded = manifest(target)
    for record in recorded["artifacts"]:
        if record["id"] == adopt.FACTS:
            record["done"] = ["false"]
    (target / adopt.MANIFEST).write_text(json.dumps(recorded), encoding="utf-8")
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
    assert [record["timeout"] for record in hook_records(target)] == [1200]
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
    assert [record["harness"] for record in hook_records(target)] == ["claude-code", "codex"]
    for name in ("gemini", "cursor"):
        assert f"{name} finish-check: not available yet: {finish_check.unavailable(name)}" in out
    table = json.loads((ROOT / "adapters/harnesses.json").read_text(encoding="utf-8"))
    for name in ("claude-code", "codex"):
        accept = f"the one-time accept: {table[name]['finish_hook']['accept']}, and `outcomebound`"
        assert accept in out and "on the harness process's PATH" in out
    assert finish_check.CAUTION["codex"] in out


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
