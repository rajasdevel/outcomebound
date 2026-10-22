"""The facts-only install: the project facts and the local fragment alone, kept on upgrade.

docs/specs/install/design.md, section Facts-only. Every target is a Git repository under
`tmp_path`; the assertions are about bytes on disk, the manifest and exit statuses, and about
`--check` lines only where they are what a person reads.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from outcomebound_tools import adopt, facts, fragments, identity
from tests.adopt_helpers import (
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
from tests.portable import write

LOCAL_EDGE = "dropping the shared staging database"
WORKFLOW = """\
on: push
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: make test
"""


def local_fragment() -> str:
    text = (ROOT / "templates/fragment-local.md").read_text(encoding="utf-8")
    return text.replace("edges: []\n", f'edges: ["{LOCAL_EDGE}"]\n')


def block_ids(target: Path, name: str = "AGENTS.md") -> list[str]:
    text = (target / name).read_text(encoding="utf-8")
    return [block.block_id for block in identity.find_managed_blocks(text)]


def body(target: Path, block_id: str) -> str:
    text = (target / "AGENTS.md").read_text(encoding="utf-8")
    found = {block.block_id: block for block in identity.find_managed_blocks(text)}
    return found[block_id].body


def facts_record(target: Path) -> dict[str, object]:
    [record] = [r for r in manifest(target)["artifacts"] if r["id"] == adopt.FACTS]
    return record


def skill_paths(target: Path) -> set[str]:
    return {r["path"] for r in manifest(target)["artifacts"] if r["kind"] == "skill"}


def all_current(capsys: Capture, target: Path) -> bool:
    code, out, _ = run(capsys, str(target), "--check")
    return code == 0 and set(states(out).values()) == {"current"}


def test_a_facts_only_install_writes_the_facts_and_the_local_fragment_alone(
    tmp_path: Path, capsys: Capture
) -> None:
    """Breaks if the kernel, a pointer line or a fragment copy comes back, if the selection
    stops feeding the edges, or if the mode is not recorded."""

    files = {adopt.LOCAL_FRAGMENT: local_fragment(), "CLAUDE.md": "# Notes\n"}
    target = repo(tmp_path / "t", files)
    selection = ("--harness", "claude-code", "--fragments", "ci-release,local")

    code, _, err = run(capsys, str(target), *selection, "--done", "make test", "--facts-only")

    assert code == 0, err
    assert block_ids(target) == [adopt.FACTS, adopt.POINTERS]
    local = fragments.parse_fragment(local_fragment(), adopt.LOCAL_FRAGMENT)
    assert body(target, adopt.POINTERS) == facts.inline(local)
    edges = [*fragments.load_all(ROOT)["ci-release"].edges, LOCAL_EDGE]
    assert f"- Irreversible edges: {'; '.join(edges)}" in body(target, adopt.FACTS)
    assert sorted(p.name for p in (target / ".outcomebound/fragments").iterdir()) == ["local.md"]
    assert block_ids(target, "CLAUDE.md") == ["pointer-claude-md"]
    assert (target / adopt.LOCAL_IGNORE).read_bytes() == adopt.LOCAL_IGNORE_TEXT
    claude = {f".claude/skills/{name}/SKILL.md" for name in adopt.SKILLS}
    assert claude <= skill_paths(target)
    record = facts_record(target)
    assert (record["mode"], record["fragments"]) == ("facts-only", ["ci-release", "local"])
    assert adopt.KERNEL not in {r["id"] for r in manifest(target)["artifacts"]}
    assert all_current(capsys, target)


def test_a_harness_without_native_skills_gets_none_and_native_ones_get_no_pointer(
    tmp_path: Path, capsys: Capture
) -> None:
    """generic lists no skills itself, so it gets none; codex and Claude Code each get their
    native copies, and with no local fragment AGENTS.md holds the facts block alone."""

    plain = repo(tmp_path / "plain", {"README.md": "# T\n"})
    code, out, err = run(capsys, str(plain), "--harness", "generic", "--facts-only")
    assert code == 0, err
    assert skill_paths(plain) == set()
    assert not (plain / adopt.GENERIC_SKILLS).exists()
    assert "UNVERIFIED generic: that the harness reads AGENTS.md" in out
    assert block_ids(plain) == [adopt.FACTS]

    native = repo(tmp_path / "native", {"README.md": "# T\n", "CLAUDE.md": "# Notes\n"})
    code, _, err = run(
        capsys, str(native), "--harness", "codex,claude-code", "--fragments", "", "--facts-only"
    )
    assert code == 0, err
    assert block_ids(native) == [adopt.FACTS]
    assert ": read " not in (native / "AGENTS.md").read_text(encoding="utf-8")
    roots = {path.split("/skills/", 1)[0] for path in skill_paths(native)}
    assert roots == {".agents", ".claude"}
    assert not (native / adopt.GENERIC_SKILLS).exists()


def test_an_upgrade_keeps_the_mode_and_full_switches_back_and_forth(
    tmp_path: Path, capsys: Capture
) -> None:
    """A run from a newer engine that names no mode stays facts-only; `--full` brings the
    kernel, the pointer lines and the fragment copies; `--facts-only` again takes them out and
    leaves the same bytes as the first facts-only install."""

    files = {adopt.LOCAL_FRAGMENT: local_fragment(), "AGENTS.md": "# Our rules\n"}
    target = repo(tmp_path / "t", files)
    selection = ("--harness", "codex", "--fragments", "python,local", "--facts-only")
    assert run(capsys, str(target), *selection)[0] == 0
    first = snapshot(target)

    newer = engine_copy(tmp_path)
    change_kernel(newer, "99.0.0")
    code, _, err = run(capsys, str(target), source=newer)
    assert code == 0, err
    assert manifest(target)["engine_version"] == "99.0.0"
    assert facts_record(target)["mode"] == "facts-only"
    assert block_ids(target) == [adopt.FACTS, adopt.POINTERS]

    code, _, err = run(capsys, str(target), "--full")
    assert code == 0, err
    assert block_ids(target) == [adopt.KERNEL, adopt.FACTS, adopt.POINTERS]
    assert (target / ".outcomebound/fragments/python.md").is_file()
    assert "mode" not in facts_record(target)
    assert ": read .agents/skills/" in body(target, adopt.POINTERS)
    assert (target / "AGENTS.md").read_text(encoding="utf-8").endswith("# Our rules\n")
    assert all_current(capsys, target)

    code, _, err = run(capsys, str(target), "--facts-only")
    assert code == 0, err
    assert snapshot(target) == first
    assert all_current(capsys, target)


def test_check_reads_a_facts_only_install_stale_when_a_fact_source_changes(
    tmp_path: Path, capsys: Capture
) -> None:
    target = repo(tmp_path / "t", {".github/workflows/ci.yml": WORKFLOW})
    arguments = ("--harness", "codex", "--done", "make test", "--facts-only")
    assert run(capsys, str(target), *arguments)[0] == 0
    assert all_current(capsys, target)
    write(target / ".github/workflows/ci.yml", WORKFLOW.replace("make test", "make test-all"))

    code, out, _ = run(capsys, str(target), "--check")

    assert code == 1
    assert states(out)[f"AGENTS.md ({adopt.FACTS})"] == "stale"
    assert run(capsys, str(target))[0] == 0
    assert "`make test-all`" in body(target, adopt.FACTS)
    assert block_ids(target) == [adopt.FACTS]
    assert all_current(capsys, target)


def test_a_dry_run_writes_nothing_and_remove_restores_every_byte(
    tmp_path: Path, capsys: Capture
) -> None:
    files = {adopt.LOCAL_FRAGMENT: local_fragment(), "CLAUDE.md": "# Notes"}
    target = repo(tmp_path / "t", files)
    before = snapshot(target)
    selection = ("--harness", "claude-code", "--fragments", "local", "--facts-only")

    code, out, _ = run(capsys, str(target), *selection, "--dry-run")
    assert code == 0 and "AGENTS.md" in out
    assert snapshot(target) == before

    assert run(capsys, str(target), *selection)[0] == 0
    assert snapshot(target) != before
    code, _, err = run(capsys, str(target), "--remove")
    assert code == 0, err
    assert snapshot(target) == before


@pytest.mark.parametrize(
    "arguments",
    [("--facts-only", "--full"), ("--check", "--facts-only"), ("--remove", "--full")],
)
def test_the_mode_flags_apply_to_an_install_alone(
    tmp_path: Path, capsys: Capture, arguments: tuple[str, ...]
) -> None:
    target = repo(tmp_path / "t")
    with pytest.raises(SystemExit) as refused:
        adopt.main([str(target), *arguments])
    assert refused.value.code == 2
    assert snapshot(target) == {}


@pytest.mark.parametrize("value", ["bogus", "", None, 5])
def test_a_recorded_mode_this_engine_does_not_know_is_refused(
    tmp_path: Path, capsys: Capture, value: object
) -> None:
    target = repo(tmp_path / "t")
    assert run(capsys, str(target), "--harness", "codex", "--facts-only")[0] == 0
    path = target / adopt.MANIFEST
    data = json.loads(path.read_text(encoding="utf-8"))
    [record] = [r for r in data["artifacts"] if r["id"] == adopt.FACTS]
    record["mode"] = value
    write(path, json.dumps(data, indent=2) + "\n")
    before = snapshot(target)

    code, _, err = run(capsys, str(target))

    assert code != 0
    assert "mode recorded" in err
    assert snapshot(target) == before
