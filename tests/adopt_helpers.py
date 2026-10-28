"""Repository construction and install observations shared by adopt tests."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from outcomebound_tools import adopt
from tests.portable import write

ROOT = Path(__file__).resolve().parent.parent
GIT = shutil.which("git") or "git"
Capture = pytest.CaptureFixture[str]

# Literal catalog entries expected at the full native install's public interface.
SHORT_DESCRIPTIONS = {
    "using-outcomebound": "Use for delivery route, stage, exposure, growth or time forecasts.",
    "decision-brief": (
        "Use before asking for a person-owned decision or after a granted act is refused."
    ),
    "gather-requirements": "Use for unsettled source requirements or competing request readings.",
    "tests-worth-keeping": (
        "Use for risky logic, red baselines, skipped, weakened or removed tests, or doubtful "
        "test proof."
    ),
    "diagnose": "Use for reported defects, unknown failure causes or failed fixes.",
    "review-findings": "Use when acting on findings or writing a required review.",
    "review-council": "Use for a second opinion from another model or harness.",
    "explain-spec": "Use when a person must act on an unfamiliar spec or does not follow it.",
    "slice-tickets": "Use when breaking work into tickets.",
    "hand-off-tickets": "Use when handing an accepted ticket from the store to its implementer.",
    "explorable": (
        "Use for interactive pages, learning by trying or options tried with own numbers."
    ),
    "land-change": ("Use when landing a pull or merge request through checks and review."),
    "run-acceptance": (
        "Use when preparing, running or recording acceptance by a person outside the build."
    ),
    "sync-tracker": "Use when reading or writing a card outside the project's ticket store.",
}


# The boundary sentences a full native description keeps after its trigger, word for word from
# the source description; the three skills whose second sentence is a pointer-block rule have none.
BOUNDARIES = {
    "gather-requirements": (
        "For clear requests, accepted tickets, handoffs stating the work or symptom notes, "
        "proceed directly, except when resumed work relies on a recorded direction choice."
    ),
    "diagnose": (
        "A declared stub failing as declared is no defect; handle the requested work directly."
    ),
    "review-findings": "Check each finding as a claim and give it a disposition.",
    "review-council": "Plan first; run only after the person's yes.",
    "explain-spec": (
        "A design walk-through qualifies; ask questions on it only when the person asks to test "
        "their understanding."
    ),
    "slice-tickets": (
        "Needs a declared ticket store (`.outcomebound/tickets.json`); not for a to-do list or "
        "for building a ticket that exists, which are done directly."
    ),
    "hand-off-tickets": (
        "For slicing, use `slice-tickets`; for a prompt or spec outside the ticket store, work "
        "directly."
    ),
    "explorable": "A decision page accompanies the decision brief, never replaces it.",
    "run-acceptance": "The agent prepares and pre-runs; a person accepts.",
    "sync-tracker": "A write needs a grant naming its kind.",
}


def assert_native_skill(data: bytes, name: str, source: Path = ROOT) -> None:
    """The catalog is short; the skill body and name stay as shipped."""

    shipped = (source / "skills" / name / "SKILL.md").read_bytes()
    expected = " ".join(filter(None, (SHORT_DESCRIPTIONS[name], BOUNDARIES.get(name))))
    assert adopt.description(data) == expected
    assert data.split(b"\n---\n", 1)[1] == shipped.split(b"\n---\n", 1)[1]
    assert f"\nname: {name}\n".encode() in data


def repo(path: Path, files: dict[str, str] | None = None) -> Path:
    """A fresh Git repository at `path` holding `files`, by relative path."""

    path.mkdir(parents=True)
    subprocess.run([GIT, "init", "-q", str(path)], check=True)
    for name, text in (files or {}).items():
        (path / name).parent.mkdir(parents=True, exist_ok=True)
        write(path / name, text)
    return path


def run(capsys: Capture, *argv: str, source: Path = ROOT) -> tuple[int, str, str]:
    code = adopt.main(list(argv), source=source)
    out, err = capsys.readouterr()
    return code, out, err


def snapshot(root: Path) -> dict[str, bytes]:
    """Every file and symlink under `root` outside `.git`, by relative path, and every folder,
    as its path with a closing slash mapped to nothing, so a folder left empty is seen."""

    found: dict[str, bytes] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if relative.parts[0] == ".git":
            continue
        if path.is_symlink():
            found[relative.as_posix()] = b"-> " + os.readlink(path).encode()
        elif path.is_dir():
            found[relative.as_posix() + "/"] = b""
        elif path.is_file():
            found[relative.as_posix()] = path.read_bytes()
    return found


def manifest(target: Path) -> dict[str, Any]:
    document: dict[str, Any] = json.loads((target / adopt.MANIFEST).read_text(encoding="utf-8"))
    return document


def states(out: str) -> dict[str, str]:
    """`--check` output as {record label: state}, any detail after the label, the measurement
    note and the closing `next:` line left out."""

    skipped = ("next: ", "note ", "drift ", "warn ")
    lines = [line for line in out.splitlines() if not line.startswith(skipped)]
    rows = [line.split(None, 1) for line in lines]
    return {name.split(": ", 1)[0]: found for found, name in rows}


def engine_copy(tmp_path: Path) -> Path:
    """The parts of this checkout adopt renders from, copied so a test can change them."""

    source = tmp_path / "engine"
    for directory in ("fragments", "adapters", "skills"):
        shutil.copytree(ROOT / directory, source / directory)
    for name in ("VERSION", adopt.KERNEL_TEMPLATE, "templates/fragment-local.md"):
        (source / name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, source / name)
    return source


def change_kernel(source: Path, version: str) -> None:
    template = source / adopt.KERNEL_TEMPLATE
    text = template.read_text(encoding="utf-8")
    write(template, text.replace("not least work.", "not least work, now."))
    write(source / "VERSION", version + "\n")
