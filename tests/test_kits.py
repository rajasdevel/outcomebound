"""kits/: each folder holds one SKILL.md that a person pastes into their own assistant. The file
has frontmatter, stays within the size target, uses none of this project's vocabulary, and
`make kits` packs it into an archive whose one entry is that file."""

import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
KITS = ROOT / "kits"
MAX_CHARACTERS = 7500
FORBIDDEN = (
    "four inputs",
    "completion bar",
    "UNVERIFIED",
    "fragment",
    "ticket store",
    "OutcomeBound",
    "decision brief",
    "kernel",
)


def _kit_folders() -> list[Path]:
    return sorted(path for path in KITS.iterdir() if path.is_dir())


def _frontmatter(text: str) -> dict[str, str]:
    """The `key: value` lines between the opening and closing `---`, read by hand."""

    lines = text.splitlines()
    assert lines and lines[0] == "---", "the first line must be ---"
    fields: dict[str, str] = {}
    for line in lines[1:]:
        if line == "---":
            return fields
        key, sep, value = line.partition(":")
        assert sep and key.isidentifier(), f"not a key: value line: {line!r}"
        fields[key] = value.strip()
    raise AssertionError("the frontmatter is not closed by ---")


def test_every_kit_folder_holds_a_skill_named_after_it() -> None:
    folders = _kit_folders()
    assert folders, "kits/ holds no kit"
    for folder in folders:
        skill = folder / "SKILL.md"
        assert skill.is_file(), f"{folder.name}: no SKILL.md"
        fields = _frontmatter(skill.read_text(encoding="utf-8"))
        assert fields.get("name") == folder.name, f"{folder.name}: name must be the folder name"
        assert fields.get("description"), f"{folder.name}: description is empty or missing"


def test_every_kit_file_is_within_the_size_target() -> None:
    for folder in _kit_folders():
        text = (folder / "SKILL.md").read_text(encoding="utf-8")
        assert len(text) <= MAX_CHARACTERS, f"{folder.name}: {len(text)} characters"


def test_kit_text_holds_no_outcomebound_vocabulary() -> None:
    for folder in _kit_folders():
        lowered = (folder / "SKILL.md").read_text(encoding="utf-8").lower()
        found = [term for term in FORBIDDEN if term.lower() in lowered]
        assert not found, f"{folder.name} uses project vocabulary: {found}"


def test_make_kits_packs_each_kit_as_its_source(tmp_path: Path) -> None:
    if shutil.which("make") is None:
        pytest.skip("make is not installed here")

    out = tmp_path / "out"
    done = subprocess.run(
        ["make", "kits", f"KITS_OUT={out}"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, done.stdout + done.stderr

    for folder in _kit_folders():
        archive = out / f"{folder.name}.zip"
        assert archive.is_file(), f"{folder.name}: no archive"
        entry = f"{folder.name}/SKILL.md"
        with zipfile.ZipFile(archive) as packed:
            assert packed.namelist() == [entry]
            content = packed.read(entry)
        assert content == (folder / "SKILL.md").read_bytes()
