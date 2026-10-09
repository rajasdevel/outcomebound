"""Shipped model-facing text sets no limit and no run stop without its evidence (prompt standard
S23).

A number with a unit of work or time, a bound phrase or a run stop in the contract, the kernel,
the templates, the fragments or the skills fails, unless `ALLOWED` holds it with its evidence.
Frontmatter and fenced code are left out: a fence holds an example or a command, not a rule.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LISTED = """OutcomeBound.md templates/managed-block.agents.md.tmpl templates/goal/goal.md
templates/tickets/issue-template.md templates/fragment-local.md"""
GLOBS = ("templates/spec/*.md", "fragments/**/*.md", "skills/**/*.md")
UNIT = (
    r"words?|lines?|steps?|pages?|files?|commits?|attempts?|retries|runs?|seconds?|minutes?"
    r"|hours?|days?|bytes?|KiB|MiB|characters?|tokens?"
)
LIMITS = (
    re.compile(rf"\b\d[\d,]*\s*(?:{UNIT})\b"),
    re.compile(r"\b\d+\s*%"),
    re.compile(r"\b(?:at most|no more than|one page|within \d|past (?:twice|\d))", re.IGNORECASE),
    # An attempt limit in words: "goes back once", "fails twice", "after two tries".
    re.compile(
        r"\b(?:goes back|sent back|fail(?:s|ed)?|retr(?:y|ies)|tr(?:y|ies)|attempts?)\s+"
        r"(?:once|twice|thrice)\b",
        re.IGNORECASE,
    ),
    # The same limit as an ordinal: "a second miss", "fails a second time".
    re.compile(
        r"\b(?:(?:a|the)\s+(?:second|third)\s+(?:miss|failure|attempt|try|round)"
        r"|fails?\s+(?:a|the)\s+(?:second|third)\s+time)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:after|up to)\s+(?:one|two|three|four|five|six|seven|eight|nine|ten)\s+(?:more\s+)?"
        r"(?:tries|attempts|retries|rounds|passes|failures|misses)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:stop and ask|stop (?:only|there|the run)|end the run|re-plan)\b", re.I),
)
# (path, matched text): the evidence that allows it.
ALLOWED = {
    ("templates/goal/goal.md", "End the run"): (
        "the end condition names the completion bar and the items left, not a stop"
    ),
}
FRONTMATTER = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)
FENCE = re.compile(r"^\s*(?:```|~~~)")


def shipped() -> list[Path]:
    paths = [ROOT / name for name in LISTED.split()]
    return paths + [path for pattern in GLOBS for path in sorted(ROOT.glob(pattern))]


def limits(text: str) -> list[tuple[int, str]]:
    """Each (line number, matched text) of a limit or a run stop, outside frontmatter and
    fenced code."""

    text = FRONTMATTER.sub(lambda found: "\n" * found.group(0).count("\n"), text)
    found, fenced = [], False
    for number, line in enumerate(text.splitlines(), start=1):
        if FENCE.match(line):
            fenced = not fenced
        elif not fenced:
            found += [(number, hit.group(0)) for rule in LIMITS for hit in rule.finditer(line)]
    return found


def test_shipped_model_text_sets_no_limit_without_its_evidence() -> None:
    seen, unexplained = set(), []
    for path in shipped():
        name = path.relative_to(ROOT).as_posix()
        for number, matched in limits(path.read_text(encoding="utf-8")):
            if (name, matched) in ALLOWED:
                seen.add((name, matched))
            else:
                unexplained.append(f"{name}:{number}: {matched!r}")
    assert not unexplained, (
        "a limit or a run stop with no evidence (prompt standard S23); remove it, or add it to "
        "ALLOWED with the evidence that sets it: " + "; ".join(unexplained)
    )
    assert seen == set(ALLOWED), f"ALLOWED entries that match nothing: {set(ALLOWED) - seen}"


def test_NEGATIVE_CONTROL_a_new_limit_and_a_new_stop_are_reported() -> None:
    text = "---\nname: x\n---\nWork at most ten steps.\n```\nwait 30 seconds\n```\nRetry 3 times "
    text += "within 2 hours, then stop and ask.\n"
    assert limits(text) == [
        (4, "at most"),
        (8, "2 hours"),
        (8, "within 2"),
        (8, "stop and ask"),
    ]


def test_NEGATIVE_CONTROL_an_attempt_limit_in_words_is_reported() -> None:
    for sentence, matched in (
        ("A step that fails review goes back once with the finding.", "goes back once"),
        ("A step that fails twice is rewritten.", "fails twice"),
        ("Hand it up after two tries.", "after two tries"),
        ("A second miss says the tier is wrong.", "A second miss"),
        ("One that fails a second time goes up a tier.", "fails a second time"),
    ):
        assert [hit for _, hit in limits(sentence + "\n")] == [matched]
    # A cause, not a count, sets no limit.
    assert limits("Where a fix round repeats the same miss, the tier is wrong.\n") == []
