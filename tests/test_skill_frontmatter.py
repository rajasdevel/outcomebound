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
