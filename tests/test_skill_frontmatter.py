# tests/test_skill_frontmatter.py
import glob
import re
from pathlib import Path


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
        name = re.search(r"^name:\s*(.+)$", fm, re.M).group(1).strip()
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
