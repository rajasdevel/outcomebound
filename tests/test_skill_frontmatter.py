# tests/test_skill_frontmatter.py
import glob
import re
from pathlib import Path

import pytest

from outcomebound_tools import adopt
from tests.adopt_helpers import (
    ROOT,
    SHORT_DESCRIPTIONS,
    Capture,
    assert_native_skill,
    repo,
    run,
    states,
)


def _frontmatter(p: Path):
    t = p.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", t, re.DOTALL)
    assert m, f"{p} missing YAML frontmatter"
    return m.group(1), t


def test_all_skills_have_name_and_description_only_frontmatter():
    skills = glob.glob("skills/**/SKILL.md", recursive=True)
    assert skills, "no skills yet"
    for s in skills:
        fm, _ = _frontmatter(Path(s))
        keys = {
            line.split(":")[0].strip()
            for line in fm.splitlines()
            if line.strip() and not line.startswith(" ")
        }
        assert keys == {"name", "description"}, (
            f"{s} frontmatter keys = {keys}; portability requires name+description only"
        )
        # name must equal parent dir, lowercase-hyphen
        named = re.search(r"^name:\s*(.+)$", fm, re.M)
        assert named is not None, f"{s}: name has no value"
        name = named.group(1).strip()
        assert name == Path(s).parent.name, f"{s}: name '{name}' != dir"
        assert re.fullmatch(r"[a-z0-9-]+", name), f"{s}: name not lowercase-hyphen"


def test_skill_body_under_500_lines():
    # From the repository, whatever the working directory, and never over nothing.
    skills = sorted((Path(__file__).resolve().parent.parent / "skills").rglob("SKILL.md"))
    assert skills, "no skills found"
    for s in skills:
        assert len(s.read_text(encoding="utf-8").splitlines()) <= 500, f"{s} body >500 lines"


def _plain_scalar_problem(line: str) -> str:
    """Why a `key: value` frontmatter line is not valid YAML as a plain value, else ''.

    A plain value may hold neither `: ` nor ` #` (nor end in `:`), and may not begin with a
    character YAML reserves; a quoted value is left to its quotes."""

    value = line.partition(":")[2].strip()
    if not value or value[0] in "\"'":
        return ""
    if value[0] in "[]{}&*!|>%@`#,":
        return f"begins with {value[0]!r}"
    for bad in (": ", " #"):
        if bad in value:
            return f"holds {bad!r}"
    return "ends in ':'" if value.endswith(":") else ""


def test_skill_frontmatter_values_are_valid_yaml_plain_scalars():
    # PyYAML is not available to the suite; adopt reads the description as one line.
    skills = sorted((Path(__file__).resolve().parent.parent / "skills").rglob("SKILL.md"))
    assert skills, "no skills found"
    for s in skills:
        fm, _ = _frontmatter(s)
        for line in fm.splitlines():
            assert not line.startswith((" ", "\t")), f"{s}: a continued frontmatter value: {line!r}"
            assert ":" in line, f"{s}: frontmatter line without a key: {line!r}"
            problem = _plain_scalar_problem(line)
            assert not problem, f"{s}: `{line.split(':')[0]}` value {problem}; reword or quote it"


def test_NEGATIVE_CONTROL_an_unquoted_colon_or_hash_in_a_value_is_reported():
    old = (
        "description: Use when breaking work into tickets in a project that declares a ticket "
        "store (`.outcomebound/tickets.json`): how many tickets an outcome needs. Not a to-do list."
    )
    assert _plain_scalar_problem(old) == "holds ': '"
    assert _plain_scalar_problem("description: Use when a fix is made #1 priority") == "holds ' #'"
    assert _plain_scalar_problem("description: 'Use when: quoted'") == ""
    assert _plain_scalar_problem("description: Use when plain, with a dash - and a `path`.") == ""


@pytest.mark.parametrize(
    "harness,root",
    [
        ("codex", ".agents/skills"),
        ("claude-code", ".claude/skills"),
        ("amp", ".agents/skills"),
        ("cursor", ".cursor/skills"),
        ("gemini", ".gemini/skills"),
        ("codex,claude-code", ".agents/skills"),
    ],
)
def test_full_native_install_has_short_catalog_and_complete_project_pointers(
    tmp_path: Path, capsys: Capture, harness: str, root: str
) -> None:
    """Catches shortening the pointer conditions or removing the exact-path fallback while
    shortening the catalog. An omitted catalog entry or same-name personal skill still has
    a complete project pointer. Bodies and references must not change with the catalog."""

    target = repo(tmp_path / "project", {"CLAUDE.md": "# Project\n"})
    code, _, err = run(capsys, str(target), "--harness", harness)
    assert code == 0, err
    agents = (target / "AGENTS.md").read_text(encoding="utf-8")
    assert set(SHORT_DESCRIPTIONS) == set(adopt.SKILLS)
    assert (
        "a skill list that lacks it, or a personal skill of the same name, does not replace it"
        in agents
    )
    for name in adopt.SKILLS:
        assert f"- {adopt.CONDITIONS[name]}: read {root}/{name}/SKILL.md" in agents
        for native in adopt.routes(ROOT, harness.split(",")):
            data = (target / native.skills / name / "SKILL.md").read_bytes()
            assert_native_skill(data, name)
            fm, _ = _frontmatter(target / native.skills / name / "SKILL.md")
            assert all(not _plain_scalar_problem(line) for line in fm.splitlines())
            for note in (ROOT / "skills" / name / "references").glob("*.md"):
                assert (
                    target / native.skills / name / "references" / note.name
                ).read_bytes() == note.read_bytes()
    for condition, path in adopt.REFERENCE_POINTERS:
        assert f"- {condition}: read {root}/{path}" in agents
    for rule in adopt.RULES.values():
        assert f"- {rule}" in agents
    code, out, _ = run(capsys, str(target), "--check")
    assert code == 0 and set(states(out).values()) == {"current"}


@pytest.mark.parametrize("harness", ["codex", "claude-code"])
def test_full_native_install_keeps_every_later_sentence_of_each_source_description(
    tmp_path: Path, capsys: Capture, harness: str
) -> None:
    """Catches a short catalog line that drops a boundary (a declared stub is no defect; not for
    an accepted ticket): each sentence after a source description's first is in the installed
    description or among the pointer block's rules."""

    target = repo(tmp_path / "project", {"CLAUDE.md": "# Project\n"})
    code, _, err = run(capsys, str(target), "--harness", harness)
    assert code == 0, err
    agents = (target / "AGENTS.md").read_text(encoding="utf-8")
    for name in adopt.SKILLS:
        source = adopt.description((ROOT / "skills" / name / "SKILL.md").read_bytes())
        later = source.split(". ", 1)[1] if ". " in source else ""
        for native in adopt.routes(ROOT, [harness]):
            installed = adopt.description((target / native.skills / name / "SKILL.md").read_bytes())
            assert not later or later in installed or f"- {later}" in agents, name


@pytest.mark.parametrize(
    "harness,facts_only",
    [
        ("generic", False),
        ("codex,generic", False),
        ("codex", True),
        ("claude-code", True),
        ("amp", True),
        ("cursor", True),
        ("gemini", True),
        ("codex,claude-code,generic", True),
        ("generic", True),
    ],
)
def test_other_install_routes_and_standalone_sources_keep_full_descriptions(
    tmp_path: Path, capsys: Capture, harness: str, facts_only: bool
) -> None:
    """Catches applying short descriptions to the source, generic copies or facts-only
    copies, including facts-only native discovery of the common rules and continuity route."""

    target = repo(tmp_path / "project", {"CLAUDE.md": "# Project\n"})
    flags = ["--facts-only"] if facts_only else []
    code, _, err = run(capsys, str(target), "--harness", harness, *flags)
    assert code == 0, err
    agents = (target / "AGENTS.md").read_text(encoding="utf-8")
    if facts_only:
        assert ": read " not in agents
    for name in adopt.SKILLS:
        source = (ROOT / "skills" / name / "SKILL.md").read_bytes()
        full = adopt.description(source)
        assert full.startswith(f"Use {adopt.CONDITIONS[name]}.")
        assert len(full) > len(SHORT_DESCRIPTIONS[name])
        if name in adopt.RULES:
            assert adopt.RULES[name] in full
        # The unqualified source/standalone reader must never receive installed shortening.
        assert adopt.skill_file(ROOT, name) == source
        assert adopt.skill_files(ROOT, name)["SKILL.md"] == source
        for route in adopt.routes(ROOT, harness.split(",")):
            file = target / route.skills / name / "SKILL.md"
            if facts_only and not route.native:
                assert not file.exists()
            elif route.native and not facts_only:
                assert_native_skill(file.read_bytes(), name)
            else:
                assert file.read_bytes() == source
    if not facts_only:
        assert ": read .outcomebound/skills/diagnose/SKILL.md" in agents
    code, out, _ = run(capsys, str(target), "--check")
    assert code == 0 and set(states(out).values()) == {"current"}


def test_native_upgrade_and_mode_switches_render_and_check_the_selected_description(
    tmp_path: Path, capsys: Capture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Catches an upgrade mistaking a previously full description for a local edit, and
    --check comparing installed short bytes with source bytes or the wrong recorded mode."""

    target = repo(tmp_path / "project")
    with monkeypatch.context() as patch:
        patch.setattr(adopt, "NATIVE_DESCRIPTIONS", {})
        assert run(capsys, str(target), "--harness", "codex")[0] == 0
    code, out, _ = run(capsys, str(target), "--check")
    assert code > 0 and states(out)[".agents/skills/diagnose/SKILL.md"] == "stale"
    assert run(capsys, str(target))[0] == 0
    for flags in [("--facts-only",), ("--full",), ("--facts-only",), ("--full",)]:
        code, _, err = run(capsys, str(target), *flags)
        assert code == 0, err
        data = (target / ".agents/skills/diagnose/SKILL.md").read_bytes()
        if flags == ("--facts-only",):
            assert data == (ROOT / "skills/diagnose/SKILL.md").read_bytes()
        else:
            assert_native_skill(data, "diagnose")
        code, out, _ = run(capsys, str(target), "--check")
        assert code == 0 and set(states(out).values()) == {"current"}


def test_each_reference_pointer_names_a_shipped_reference():
    from outcomebound_tools import adopt

    for _, path in adopt.REFERENCE_POINTERS:
        assert (Path("skills") / path).is_file(), path
