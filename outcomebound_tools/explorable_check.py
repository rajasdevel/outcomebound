"""The explorable's verdicts: the shell, the hosts, the parts a kind needs, and the run.

What this module decides: what each verdict reads and when it is PASS, FAIL or UNVERIFIED; that
the overall verdict is the worst of them (FAIL, then UNVERIFIED, then PASS); and that the page is
run only where the shell, the hosts and the parts pass.

What it does not decide: that the page's content is right. Every verdict rests on data the agent
wrote, except the shell, the pins and the policy, which come from the engine's templates. A pass
says that the page is the shell plus the agent's content, with the parts its kind needs, and that
for the declared inputs it shows what the agent expected.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from outcomebound_tools import explorable_shell, explorable_source

__all__ = [
    "Verdict",
    "hosts",
    "no_result",
    "not_run",
    "overall",
    "parts",
    "run",
    "script_literals",
    "shell",
]

PASS, FAIL, UNVERIFIED = "PASS", "FAIL", "UNVERIFIED"
_LITERAL = re.compile(r"""'(?:[^'\\\n]|\\.)*'|"(?:[^"\\\n]|\\.)*"|`(?:[^`\\]|\\.)*`""", re.DOTALL)
_ADDRESS = re.compile(r"(?i)\b(?:https?|wss?|ftp|file):|(?:^|[\s'\"`(=])//[a-z0-9]")


@dataclass(frozen=True, slots=True)
class Verdict:
    """One verdict: its name, its status, a summary and the lines under it."""

    name: str
    status: str
    summary: str
    details: list[str] = field(default_factory=list)


def overall(verdicts: list[Verdict]) -> str:
    """The worst status among `verdicts`."""

    statuses = {item.status for item in verdicts}
    return FAIL if FAIL in statuses else UNVERIFIED if UNVERIFIED in statuses else PASS


def shell(page: str) -> tuple[Verdict, explorable_shell.Parts | None]:
    """The shell verdict, and the page's slots where the frame matched."""

    found = explorable_shell.match(page)
    if found is None:
        return (
            Verdict(
                "shell",
                FAIL,
                "the page does not hold the engine's frame",
                ["next: build again"],
            ),
            None,
        )
    problems = explorable_shell.differences(found)
    if problems:
        return Verdict(
            "shell", FAIL, "the shell differs from the engine's", [*problems, "next: build again"]
        ), found
    return (
        Verdict(
            "shell",
            PASS,
            "the policy, generator, kind, stylesheet, runtime and library pins are the engine's",
        ),
        found,
    )


def script_literals(text: str) -> list[str]:
    """Each string literal in script text that could name an address."""

    return [item for item in _LITERAL.findall(text) if _ADDRESS.search(item)]


def hosts(found: explorable_shell.Parts) -> Verdict:
    """The hosts verdict: a static read of the content region."""

    scanned = explorable_source.scan(
        found.briefs, source=False, first_line=found.region_line, reserved=False
    )
    after = found.region_line + found.briefs.count("\n") + 1
    own = explorable_source.scan(found.content, source=False, first_line=after, reserved=True)
    scanned.findings.extend(own.findings)
    scanned.scripts.extend(own.scripts)
    details = [f"line {item.line}: {item.text}" for item in scanned.findings]
    allowed = tuple(explorable_shell.pin_paths())
    details.extend(
        f"line {line}: a script string could name an address: {literal[:80]}"
        for line, text in scanned.scripts
        for literal in script_literals(text)
        if not literal[1:].startswith(allowed)
    )
    if details:
        return Verdict(
            "hosts", FAIL, "the content holds what the policy and the citation rule refuse", details
        )
    return Verdict(
        "hosts",
        PASS,
        "no attribute, style value or script string names an address the policy refuses "
        "(an address that page code builds when it runs is not seen)",
    )


def parts(kind: str, found: explorable_shell.Parts) -> Verdict:
    """The parts verdict: what the kind needs. The reply section is the shell's own."""

    if kind == "decision":
        if 'data-brief="' in found.briefs:
            return Verdict("parts", PASS, "decision: a brief and the reply")
        return Verdict(
            "parts", FAIL, "a decision explorable holds a brief, and this page holds none"
        )
    scanned = explorable_source.scan(found.content, source=False, first_line=found.region_line)
    if "data-question" in scanned.attributes:
        return Verdict("parts", PASS, f"{kind}: at least one data-question and the reply")
    return Verdict(
        "parts",
        FAIL,
        f"a {kind} explorable holds at least one `data-question`, and this page holds none",
    )


def not_run(reason: str) -> Verdict:
    return Verdict("run", UNVERIFIED, f"not run: {reason}")


def no_result(reason: str) -> Verdict:
    """The page ran and wrote no usable check result."""

    return Verdict("run", FAIL, reason)


def run(result: Mapping[str, Any]) -> Verdict:
    """The run verdict from the check result the page wrote."""

    details: list[str] = []
    failed = False
    for error in result.get("errors") or []:
        failed = True
        details.append(f"script error: {error}")
    for item in result.get("expectations") or []:
        if not item.get("pass"):
            failed = True
            details.append(
                f"expectation {item.get('label')!r} failed: expected {item.get('expected')}, "
                f"shown {item.get('shown')}"
            )
    uncovered = (result.get("outputs") or {}).get("uncovered") or []
    unverified = [f"output {name}: UNVERIFIED (no expectation reads it)" for name in uncovered]
    libraries = result.get("libraries") or {}
    if libraries:
        details.append(
            "libraries (informational, never a failure): "
            + ", ".join(f"{name} {state}" for name, state in libraries.items())
        )
    count = len(result.get("expectations") or [])
    if failed:
        return Verdict(
            "run",
            FAIL,
            "the page ran with a script error or a failed expectation",
            details + unverified,
        )
    if unverified:
        return Verdict(
            "run",
            UNVERIFIED,
            f"{count} expectation(s) pass; some outputs are not read by one",
            unverified + details,
        )
    return Verdict("run", PASS, f"no script error; {count} expectation(s) pass", details)
