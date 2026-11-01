# tests/test_skill_frontmatter.py
import glob
import json
import re
from pathlib import Path

import pytest

from outcomebound_tools import adopt
from tests.adopt_helpers import ROOT, Capture, assert_native_skill, engine_copy, repo, run, states
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
    ("harness", "roots"),
    [
        ("codex", {".agents/skills"}),
        ("claude-code", {".claude/skills"}),
        ("amp", {".outcomebound/skills"}),
        ("cursor", {".cursor/skills"}),
        ("gemini", {".outcomebound/skills"}),
        ("generic", {".outcomebound/skills"}),
        ("codex,claude-code", {".agents/skills", ".claude/skills"}),
        ("codex,generic", {".agents/skills", ".outcomebound/skills"}),
        ("codex,claude-code,generic", {".agents/skills", ".claude/skills", ".outcomebound/skills"}),
        ("gemini,codex", {".outcomebound/skills"}),
        ("codex,gemini", {".outcomebound/skills"}),
        ("amp,claude-code", {".outcomebound/skills"}),
        ("claude-code,amp", {".outcomebound/skills"}),
        ("gemini,cursor", {".outcomebound/skills"}),
        ("amp,codex,claude-code,cursor,gemini,generic", {".outcomebound/skills"}),
    ],
)
@pytest.mark.parametrize("facts_only", [False, True])
def test_every_installed_skill_is_manual_and_keeps_its_description(
    tmp_path: Path, capsys: Capture, harness: str, roots: set[str], facts_only: bool
) -> None:
    """Catch discoverable copies without a manual mechanism, missing flags or wrong pointers."""

    target = repo(tmp_path / "project", {"CLAUDE.md": "# Project\n"})
    flags = ["--facts-only"] if facts_only else []
    code, _, err = run(capsys, str(target), "--harness", harness, *flags)
    assert code == 0, err
    routes = adopt.routes(ROOT, harness.split(","))
    installed = {p.parent.parent.relative_to(target).as_posix() for p in target.rglob("SKILL.md")}
    expected = roots
    if (
        facts_only
        and "generic" in harness.split(",")
        and not {"amp", "gemini"}.intersection(harness.split(","))
    ):
        expected = roots - {".outcomebound/skills"}
    assert installed == expected
    carriers = [route for route in routes if not facts_only or route.native]
    for route in carriers:
        for name in adopt.SKILLS:
            file = target / route.skills / name / "SKILL.md"
            assert_native_skill(file.read_bytes(), name)
            assert (file.parent / "agents/openai.yaml").read_text("utf-8") == (
                "policy:\n  allow_implicit_invocation: false\n"
            )
            for note in (ROOT / "skills" / name / "references").glob("*.md"):
                assert (file.parent / "references" / note.name).read_bytes() == note.read_bytes()
    agents = (target / "AGENTS.md").read_text(encoding="utf-8")
    if facts_only:
        assert "Optional:" not in agents
    else:
        root = ".outcomebound/skills" if ".outcomebound/skills" in roots else sorted(roots)[0]
        (optional,) = [line for line in agents.splitlines() if line.startswith("Optional: ")]
        assert re.findall(r"`([^`]+)`", optional) == [
            f"{root}/{name}/SKILL.md" for name in adopt.SKILLS
        ]
        assert "adopt-outcomebound" not in optional
    code, out, _ = run(capsys, str(target), "--check")
    assert code == 0 and set(states(out).values()) == {"current"}


@pytest.mark.parametrize("mechanism", [None, "unknown"])
def test_a_missing_or_unknown_manual_mechanism_keeps_all_copies_outside_discovery(
    tmp_path: Path, capsys: Capture, mechanism: str | None
) -> None:
    """A new route must not gain implicit invocation from another route's shared directory."""

    source = engine_copy(tmp_path)
    table_path = source / "adapters/harnesses.json"
    table = json.loads(table_path.read_text(encoding="utf-8"))
    table["probe"] = {**table["codex"]}
    if mechanism is None:
        table["probe"].pop("manual_skill_invocation")
    else:
        table["probe"]["manual_skill_invocation"] = mechanism
    write(table_path, json.dumps(table))
    target = repo(tmp_path / "project")
    assert run(capsys, str(target), "--harness", "codex,probe", source=source)[0] == 0
    assert not (target / ".agents/skills").exists()
    assert (target / ".outcomebound/skills/diagnose/SKILL.md").is_file()
    assert run(capsys, str(target), "--check", source=source)[0] == 0


@pytest.mark.parametrize("harness", ["gemini", "amp"])
@pytest.mark.parametrize("facts_only", [False, True])
def test_an_upgrade_removes_native_copies_that_have_no_manual_mechanism(
    tmp_path: Path, capsys: Capture, harness: str, facts_only: bool
) -> None:
    """An upgrade must remove recorded discoverable copies, including other routes' aliases."""

    source = engine_copy(tmp_path)
    table_path = source / "adapters/harnesses.json"
    table = json.loads(table_path.read_text(encoding="utf-8"))
    table[harness]["manual_skill_invocation"] = "disable-model-invocation"
    write(table_path, json.dumps(table))
    target = repo(tmp_path / "project")
    flags = ["--facts-only"] if facts_only else []
    assert (
        run(
            capsys, str(target), "--harness", f"{harness},codex,claude-code", *flags, source=source
        )[0]
        == 0
    )
    assert (target / ".agents/skills/diagnose/SKILL.md").is_file()
    assert (target / ".claude/skills/diagnose/SKILL.md").is_file()
    table[harness]["manual_skill_invocation"] = None
    write(table_path, json.dumps(table))
    assert run(capsys, str(target), source=source)[0] == 0
    assert {p.parent.parent.relative_to(target).as_posix() for p in target.rglob("SKILL.md")} == {
        ".outcomebound/skills"
    }
    assert run(capsys, str(target), "--check", source=source)[0] == 0


@pytest.mark.parametrize("harness", ["codex,probe", "probe,codex"])
def test_shared_skill_directory_is_manual_for_native_and_generic_readers(
    tmp_path: Path, capsys: Capture, harness: str
) -> None:
    """Catch either route's selection order disabling manual flags in a shared directory."""

    source = engine_copy(tmp_path)
    table_path = source / "adapters/harnesses.json"
    table = json.loads(table_path.read_text(encoding="utf-8"))
    table["probe"] = {**table["codex"], "native_skills": False}
    write(table_path, json.dumps(table))
    target = repo(tmp_path / "project")
    assert run(capsys, str(target), "--harness", harness, source=source)[0] == 0
    for name in adopt.SKILLS:
        file = target / ".agents/skills" / name / "SKILL.md"
        assert_native_skill(file.read_bytes(), name, source)
        assert (file.parent / "agents/openai.yaml").read_text("utf-8") == (
            "policy:\n  allow_implicit_invocation: false\n"
        )
    assert run(capsys, str(target), "--check", source=source)[0] == 0


def test_mode_switches_keep_manual_flags_and_descriptions(tmp_path: Path, capsys: Capture) -> None:
    """Catch a mode switch changing native skill content or losing generated policy files."""

    target = repo(tmp_path / "project")
    assert run(capsys, str(target), "--harness", "codex")[0] == 0
    original = (target / ".agents/skills/diagnose/SKILL.md").read_bytes()
    for flag in ("--facts-only", "--full", "--facts-only", "--full"):
        assert run(capsys, str(target), flag)[0] == 0
        assert (target / ".agents/skills/diagnose/SKILL.md").read_bytes() == original
        assert (target / ".agents/skills/diagnose/agents/openai.yaml").read_text("utf-8") == (
            "policy:\n  allow_implicit_invocation: false\n"
        )
        assert run(capsys, str(target), "--check")[0] == 0
