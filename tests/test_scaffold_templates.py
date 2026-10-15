"""The rules for the scaffold's template text (docs/specs/scaffold/design.md, "Rules for the
template text"), over every file under `templates/scaffold/` and `templates/lifecycle/`: no claim
of compliance, conformance, a level or a certification, and no scope conclusion; no vendor product
or setting in a Markdown template; each date of a law or a standard beside the day it was read
and its source; and the three review controls in the team and organization text."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCAFFOLD = ROOT / "templates" / "scaffold"
LIFECYCLE = ROOT / "templates" / "lifecycle"
# The files that are a vendor's format by nature, exempt by exact path; their comments name the
# control they serve. The offers are a command or an engine path for the agent, not Markdown.
VENDOR_FORMAT = frozenset({"common/ci.yml", "common/dependabot.yml", "organization/CODEOWNERS"})

CLAIMS = re.compile(
    r"\bcompliant\b|\bcertified\b|\bconformant\b|\bCE-ready\b|\bmeets Annex\b"
    r"|\bSLSA (?:Build |Source )?(?:L|level )\d|\bsafety class [ABC]\b|\bclass [ABC] software\b"
    r"|\bDO-178C level\b|\blevel [A-E] software\b|\bqualified tool\b"
    r"|\bno known exploitable vulnerabilit"
    r"|\bAI (?:review|approval)s? (?:counts|is the second|satisfies)"
    r"|\b(?:the|this) (?:Regulation|Act|law|standard) applies\b"
    r"|\bapplies to (?:this|the) (?:project|product)\b|\b(?:is|are) (?:in|out of) scope\b",
    re.IGNORECASE,
)
VENDOR = re.compile(
    r"\b(?:GitHub|GitLab|Bitbucket|Gitea|Azure DevOps|Dependabot|Renovate|Copilot)\b"
    r"|\brulesets?\b|\bbranch protection\b|\bpush protection\b|\bsecret scanning\b"
    r"|\brequired reviewers\b|\bbypass list\b",
    re.IGNORECASE,
)
MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
DATE = re.compile(rf"\b\d{{4}}-\d{{2}}-\d{{2}}\b|\b\d{{1,2}} (?:{MONTHS}) \d{{4}}\b")
LAW = re.compile(
    r"\bRegulation\b|\bArticle \d|\bIEC\b|\bISO\b|\bSOC 2\b|\bNIST\b|\bSLSA\b|\bAI Act\b"
    r"|\bDirective\b"
)
SOURCE = re.compile(r"https?://|\]\(")
READ = re.compile(r"\bread on\b|\bchecked\b", re.IGNORECASE)


def texts() -> list[tuple[str, str]]:
    found = [
        (f"scaffold/{path.relative_to(SCAFFOLD).as_posix()}", path.read_text(encoding="utf-8"))
        for path in sorted(SCAFFOLD.rglob("*"))
        if path.is_file()
    ]
    found += [
        (f"lifecycle/{path.name}", path.read_text(encoding="utf-8"))
        for path in sorted(LIFECYCLE.glob("*.md"))
    ]
    assert len(found) > 20
    return found


def platform_act_texts() -> list[str]:
    manifest = json.loads((SCAFFOLD / "scaffold.json").read_text(encoding="utf-8"))
    return [act["text"] for act in manifest["platform_acts"]] + [
        status for act in manifest["platform_acts"] for status in act["status"].values()
    ]


def paragraphs(text: str) -> list[str]:
    return [part for part in re.split(r"\n\s*\n", text) if part.strip()]


def test_no_template_claims_compliance_conformance_a_level_or_a_certification() -> None:
    found = [
        f"{name}: {match.group(0)!r}" for name, text in texts() for match in CLAIMS.finditer(text)
    ]
    found += [
        f"scaffold.json: {m.group(0)!r}" for t in platform_act_texts() for m in CLAIMS.finditer(t)
    ]
    assert not found, found


@pytest.mark.parametrize(
    "claim",
    [
        "This project is SOC 2 compliant.",
        "The build is SLSA Build L3.",
        "The product meets Annex I.",
        "The release has no known exploitable vulnerabilities.",
        "An AI review counts as the second approval.",
        "The Regulation applies to this product.",
        "The software is safety class C.",
        "The generator is a qualified tool.",
    ],
)
def test_NEGATIVE_CONTROL_each_claim_is_found(claim: str) -> None:
    assert CLAIMS.search(claim)


def test_no_markdown_template_names_a_vendor_product_or_setting() -> None:
    found = [
        f"{name}: {match.group(0)!r}"
        for name, text in texts()
        if name.endswith(".md")
        for match in VENDOR.finditer(text)
    ]
    found += [
        f"scaffold.json: {m.group(0)!r}" for t in platform_act_texts() for m in VENDOR.finditer(t)
    ]
    assert not found, found
    for name in VENDOR_FORMAT:
        assert (SCAFFOLD / name).is_file(), name
    others = {
        path.relative_to(SCAFFOLD).as_posix()
        for path in SCAFFOLD.rglob("*")
        if path.is_file() and path.suffix not in (".md", ".txt") and path.name != "scaffold.json"
    }
    assert others == VENDOR_FORMAT


def test_every_law_date_in_a_template_names_the_day_it_was_read() -> None:
    unread = []
    for name, text in texts():
        for paragraph in paragraphs(text):
            dated = DATE.search(paragraph) and LAW.search(paragraph)
            if dated and not (READ.search(paragraph) and SOURCE.search(paragraph)):
                unread.append(f"{name}: {paragraph[:120]!r}")
    assert not unread, unread
    assert any(DATE.search(text) and LAW.search(text) for _, text in texts())


REVIEW_CONTROLS = {
    "an AI review never counts": re.compile(r"\bAI review\b[^.]*\bnever counts\b", re.I),
    "the person who directed the agent never approves": re.compile(
        r"neither the author nor the person who directed the agent", re.I
    ),
    "no one, admins included, bypasses it": re.compile(r"no one, admins included, bypasses", re.I),
}
REVIEW_TEXTS = (
    "scaffold/team/local.md",
    "scaffold/team/contributing.md",
    "lifecycle/team.md",
    "lifecycle/organization.md",
)


@pytest.mark.parametrize("name", REVIEW_TEXTS)
def test_the_team_and_organization_templates_state_the_three_review_controls(name: str) -> None:
    text = dict(texts())[name]
    missing = [control for control, rule in REVIEW_CONTROLS.items() if not rule.search(text)]
    assert not missing, (name, missing)
