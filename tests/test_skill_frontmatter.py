# tests/test_skill_frontmatter.py
import glob
import json
import re
from pathlib import Path

import pytest

from outcomebound_tools import adopt
from tests.adopt_helpers import (
    BOUNDARIES,
    CONDITIONAL_READS,
    INSTALLED_RULES,
    MANUAL_SKILLS,
    READ_GUIDANCE,
    ROOT,
    SHORT_DESCRIPTIONS,
    Capture,
    assert_native_skill,
    engine_copy,
    repo,
    run,
    states,
)
from tests.portable import write


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
def test_full_native_install_has_short_catalog_conditional_reads_and_manual_names(
    tmp_path: Path, capsys: Capture, harness: str, root: str
) -> None:
    """Catches lost reread/path safeguards, decision triggers, inline rules or manual names,
    and changes to skill bodies or references when the native catalog is shortened."""

    target = repo(tmp_path / "project", {"CLAUDE.md": "# Project\n"})
    code, _, err = run(capsys, str(target), "--harness", harness)
    assert code == 0, err
    agents = (target / "AGENTS.md").read_text(encoding="utf-8")
    assert set(SHORT_DESCRIPTIONS) == set(adopt.SKILLS)
    assert "\n".join(READ_GUIDANCE) in agents
    assert (
        "Read only when the person names it or a file you are reading directs you to it "
        f"(skills under `{root}/<name>/SKILL.md`): "
    ) in agents
    for name in adopt.SKILLS:
        if name in MANUAL_SKILLS:
            assert f": read {root}/{name}/SKILL.md" not in agents
            assert f"`{name}`" in agents.split("Read only when the person names it", 1)[1]
        else:
            assert f"- {CONDITIONAL_READS[name]}: read {root}/{name}/SKILL.md" in agents
        for native in adopt.routes(ROOT, harness.split(",")):
            data = (target / native.skills / name / "SKILL.md").read_bytes()
            assert_native_skill(data, name)
            fm, _ = _frontmatter(target / native.skills / name / "SKILL.md")
            assert all(not _plain_scalar_problem(line) for line in fm.splitlines())
            for note in (ROOT / "skills" / name / "references").glob("*.md"):
                assert (
                    target / native.skills / name / "references" / note.name
                ).read_bytes() == note.read_bytes()
    assert ": read " + root + "/using-outcomebound/references/continuity.md" not in agents
    for rule in INSTALLED_RULES.values():
        for line in rule:
            assert "- " + line in agents.splitlines()
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
            assert not later or later in installed or later in agents.replace("\n- ", " "), name


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
        assert len(full) > len(SHORT_DESCRIPTIONS[name])
        if name in BOUNDARIES:
            assert BOUNDARIES[name] in full
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


@pytest.mark.parametrize("harness", ["codex,probe", "probe,codex"])
def test_native_and_non_native_routes_sharing_a_directory_keep_full_descriptions(
    tmp_path: Path, capsys: Capture, harness: str
) -> None:
    """Catches shortening a shared copy because one of its routes discovers skills natively.
    The non-native reader needs every full trigger and safeguard, in either selection order.
    """

    source = engine_copy(tmp_path)
    table_path = source / "adapters/harnesses.json"
    table = json.loads(table_path.read_text(encoding="utf-8"))
    table["probe"] = {**table["codex"], "native_skills": False}
    write(table_path, json.dumps(table))
    target = repo(tmp_path / "project")

    code, _, err = run(capsys, str(target), "--harness", harness, source=source)

    assert code == 0, err
    agents = (target / "AGENTS.md").read_text(encoding="utf-8")
    for name in adopt.SKILLS:
        shipped = source / "skills" / name
        installed = target / ".agents/skills" / name
        assert (installed / "SKILL.md").read_bytes() == (shipped / "SKILL.md").read_bytes()
        pointer = f": read .agents/skills/{name}/SKILL.md"
        assert (pointer in agents) is (name not in MANUAL_SKILLS)
        assert not (installed / "agents/openai.yaml").exists()
        for reference in (shipped / "references").glob("*.md"):
            assert (
                installed / "references" / reference.name
            ).read_bytes() == reference.read_bytes()
    code, out, _ = run(capsys, str(target), "--check", source=source)
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


@pytest.mark.parametrize(
    "harness,root", [("codex", ".agents/skills"), ("claude-code", ".claude/skills")]
)
def test_manual_skills_have_both_native_flags_and_auto_skills_have_neither(
    tmp_path: Path, capsys: Capture, harness: str, root: str
) -> None:
    """Catches either missing manual flag, accidental disabling of an auto skill, a manual
    read pointer, or --check looking for a generated policy file in the source skill."""

    target = repo(tmp_path / "project")
    code, _, err = run(capsys, str(target), "--harness", harness)
    assert code == 0, err
    agents = (target / "AGENTS.md").read_text(encoding="utf-8")
    for name in MANUAL_SKILLS:
        fm, _ = _frontmatter(target / root / name / "SKILL.md")
        assert "disable-model-invocation: true" in fm.splitlines()
        assert (target / root / name / "agents/openai.yaml").read_text("utf-8") == (
            "policy:\n  allow_implicit_invocation: false\n"
        )
        assert f": read {root}/{name}/SKILL.md" not in agents
    for name in ("decision-brief", "diagnose"):
        fm, _ = _frontmatter(target / root / name / "SKILL.md")
        assert "disable-model-invocation" not in fm
        assert not (target / root / name / "agents/openai.yaml").exists()
    assert f"- when a fix did not hold: read {root}/diagnose/SKILL.md" in agents
    assert (
        "- when a decision compares several options, the person asks for a brief or a page, or "
        f"a harness refuses an act the person granted: read {root}/decision-brief/SKILL.md"
    ) in agents
    assert run(capsys, str(target), "--check")[0] == 0
