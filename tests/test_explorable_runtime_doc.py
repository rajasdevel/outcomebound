"""The runtime reference and the runtime script describe the same object and the same attributes.

Every `explorable.<name>` and every `data-*` attribute that `runtime.md` names exists in
`explorable.js`, and every one that `explorable.js` defines or reads is named in `runtime.md`.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "templates" / "explorable" / "explorable.js"
DOC = ROOT / "skills" / "explorable" / "references" / "runtime.md"
ATTRIBUTE = re.compile(r"\bdata-[a-z]+(?:-[a-z]+)*")
DOC_MEMBER = re.compile(r"\bexplorable\.([A-Za-z]+)")


def script_members(text: str) -> set[str]:
    """The keys of the object assigned to `window.explorable`."""

    start = text.index("window.explorable = {")
    body = text[start : text.index("\n  };", start)]
    return set(re.findall(r"^    ([A-Za-z]+):", body, re.MULTILINE))


def test_documented_members_are_the_objects_members() -> None:
    members = script_members(SCRIPT.read_text(encoding="utf-8"))
    documented = set(DOC_MEMBER.findall(DOC.read_text(encoding="utf-8")))
    assert members, "no members found in explorable.js"
    assert documented - members == set(), f"documented but missing: {documented - members}"
    assert members - documented == set(), f"defined but not documented: {members - documented}"


def test_documented_attributes_are_the_scripts_attributes() -> None:
    script = set(ATTRIBUTE.findall(SCRIPT.read_text(encoding="utf-8")))
    documented = set(ATTRIBUTE.findall(DOC.read_text(encoding="utf-8")))
    assert script, "no attributes found in explorable.js"
    assert documented - script == set(), f"documented but missing: {documented - script}"
    assert script - documented == set(), f"in the script but not documented: {script - documented}"


def test_NEGATIVE_CONTROL_a_missing_name_is_reported() -> None:
    members = script_members("window.explorable = {\n    ready: ready,\n    show: show\n  };")
    assert members == {"ready", "show"}
    assert set(DOC_MEMBER.findall("use explorable.nothing here")) - members == {"nothing"}
