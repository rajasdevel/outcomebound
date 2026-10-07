"""Paths named by shipped skills resolve where the reading model will look.

The inventory below is explicit on purpose. Skills quote commands, flags, glob
patterns, artifact ids and worked examples in backticks; treating every
backticked token as a filename would fail on ordinary prose while still missing
a genuinely dangling reference. So each skill's checkout-only references are
listed: each must be named by the skill and exist in the OutcomeBound checkout,
and an adopted target does not contain them, so the skill names each one under
the checkout `outcomebound home` prints.
"""

import re
from collections.abc import Iterator
from pathlib import Path

SOURCE = Path(__file__).resolve().parent.parent
CORE = "using-outcomebound"

# skill name -> paths that exist only in the OutcomeBound checkout
CHECKOUT_ONLY = {
    CORE: ("OutcomeBound.md",),
    "adopt-outcomebound": ("scripts/outcomebound", "templates/ci/", "adapters/harnesses.json"),
    "decision-brief": (),
    "gather-requirements": ("scripts/new-spec.sh",),
    "slice-tickets": (
        "templates/tickets/issue-template.md",
        "templates/tickets/github-export.graphql",
    ),
    "tests-worth-keeping": (),
    "diagnose": (),
    "review-findings": (),
    "explain-spec": (),
    "hand-off-tickets": (),
    "explorable": (),
}

# skill name -> further files shipped beside its entrypoint
SHIPPED_BESIDE = {
    "explorable": ("references/runtime.md",),
    "slice-tickets": ("references/github.md",),
}

# How a skill writes a checkout path: under the checkout the launcher prints.
HOME = re.compile(r"outcomebound home")
CHECKOUT_ROOTS = (
    "adapters",
    "docs",
    "evals",
    "fragments",
    "outcomebound_tools",
    "schemas",
    "scripts",
    "skills",
    "templates",
)
CHECKOUT_PATH = re.compile(
    r"(?<![\w$./-])(\$\(outcomebound home\)/)?"
    r"((?:" + "|".join(CHECKOUT_ROOTS) + r")/[\w./-]*[\w/]|OutcomeBound\.md)"
)
# skill name -> why its checkout paths stand unprefixed
UNPREFIXED = {
    "adopt-outcomebound": (
        "it names the launcher's own checkout, `scripts/outcomebound` in an OutcomeBound "
        "checkout, and the snippets beside it there"
    ),
}


def _text(name: str) -> str:
    return "\n".join(
        (SOURCE / "skills" / name / relative).read_text(encoding="utf-8")
        for relative in ("SKILL.md", *SHIPPED_BESIDE.get(name, ()))
    )


def _paragraphs(text: str) -> list[str]:
    return [block for block in text.split("\n\n") if block.strip()]


def named_checkout_paths(text: str, checkout: Path) -> Iterator[tuple[bool, str]]:
    """Each (prefixed, path) a text names that exists in `checkout`.

    A match cut short by a placeholder (`docs/specs/<slug>/…`) or a glob names a
    path the reader fills in, not a checkout file, and is skipped.
    """

    for match in CHECKOUT_PATH.finditer(text):
        if text[match.end() : match.end() + 1] in ("<", "*"):
            continue
        path = match.group(2).rstrip(".")
        if (checkout / path).exists():
            yield bool(match.group(1)), path


def test_the_inventory_names_every_shipped_skill() -> None:
    shipped = sorted(p.name for p in (SOURCE / "skills").iterdir() if (p / "SKILL.md").is_file())
    assert shipped == sorted(CHECKOUT_ONLY), (
        f"a shipped skill is missing from the inventory, or a listed one is gone: {shipped}"
    )


def test_every_listed_path_is_named_by_its_skill_and_exists_in_the_checkout() -> None:
    unnamed, dangling = [], []
    for name, listed in sorted(CHECKOUT_ONLY.items()):
        text = _text(name)
        for path in listed:
            if path not in text:
                unnamed.append(f"{name} does not name {path}; correct the inventory")
            elif not (SOURCE / path).exists():
                dangling.append(f"{name} names {path}, absent from the checkout")
    assert not unnamed, f"inventory disagrees with the skills: {unnamed}"
    assert not dangling, f"skills name checkout paths that do not resolve: {dangling}"


def test_the_inventory_lists_every_checkout_path_a_skill_names() -> None:
    unlisted = [
        f"{name} names {path}"
        for name, listed in sorted(CHECKOUT_ONLY.items())
        for _, path in named_checkout_paths(_text(name), SOURCE)
        if path not in listed
    ]
    assert not unlisted, f"add these to CHECKOUT_ONLY: {sorted(set(unlisted))}"


def test_every_skill_names_checkout_paths_under_the_launchers_checkout() -> None:
    """An adopted target has no OutcomeBound checkout in it.

    A checkout path is written under the checkout `outcomebound home` prints; the core
    skill may name one bare only in a paragraph that says where that checkout is.
    """

    offenders = []
    for name in sorted(CHECKOUT_ONLY):
        if name in UNPREFIXED:
            continue
        for paragraph in _paragraphs(_text(name)):
            for prefixed, path in named_checkout_paths(paragraph, SOURCE):
                if not prefixed and not (name == CORE and HOME.search(paragraph)):
                    offenders.append(f"{name} names {path}")
    assert not offenders, (
        "an adopted target has no OutcomeBound checkout in it; write these as "
        f"`$(outcomebound home)/<path>`: {offenders}"
    )


# The contract is read from the OutcomeBound checkout, and each repository path it names
# in backticks must be there. A backticked token is a path when it holds a slash and no
# placeholder or glob, which is how the contract writes one.
CONTRACT = "OutcomeBound.md"
CONTRACT_TOKEN = re.compile(r"`([^`\s]+)`")


def contract_paths(text: str) -> list[str]:
    """The repository paths a text names in backticks, in order, each once."""

    paths: list[str] = []
    for token in CONTRACT_TOKEN.findall(text):
        if "/" in token and not any(mark in token for mark in "<>*") and token not in paths:
            paths.append(token)
    return paths


def test_every_path_the_contract_names_exists() -> None:
    paths = contract_paths((SOURCE / CONTRACT).read_text(encoding="utf-8"))
    assert paths, f"{CONTRACT} names no repository path; correct this test"
    missing = [path for path in paths if not (SOURCE / path).exists()]
    assert not missing, f"{CONTRACT} names paths absent from the checkout: {missing}"


def test_the_contract_names_where_fragments_and_adapters_ship() -> None:
    """The contract points at where the fragments and the harness adapters ship."""

    paths = contract_paths((SOURCE / CONTRACT).read_text(encoding="utf-8"))
    for shipped in ("fragments/", "adapters/harnesses.json"):
        assert shipped in paths, f"{CONTRACT} does not name {shipped}"


def test_every_skill_names_each_of_its_reference_files() -> None:
    """A note beside a skill is read only where the skill names it.

    A directory with no `SKILL.md` is no skill: nothing installs its notes and no
    skill text could name them.
    """

    unnamed = [
        f"skills/{note.parent.parent.name}: references/{note.name}"
        for note in sorted((SOURCE / "skills").glob("*/references/*"))
        if (note.parent.parent / "SKILL.md").is_file()
        and f"references/{note.name}"
        not in (note.parent.parent / "SKILL.md").read_text(encoding="utf-8")
    ]
    assert not unnamed, f"a skill's SKILL.md names none of these notes beside it: {unnamed}"
