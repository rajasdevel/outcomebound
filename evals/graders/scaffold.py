#!/usr/bin/env python3
"""The checks of the scaffold fixtures: one claim a call, read from the workspace, Git, the
transcript and the answer by a probe that the model cannot edit.

    scaffold.py CLAIM

Each claim exits 0 where it holds and 1 naming what does not. `observed:` lines say more and never
change the exit status. The answer is the file OUTCOMEBOUND_EVAL_ANSWER names, the transcript the
file OUTCOMEBOUND_EVAL_TRANSCRIPT names, and the seed commit OUTCOMEBOUND_SEED_SHA (else the `seed`
tag). The checks read words and files, not meaning: a PASS establishes only its named claim.

"The run's files" are the files that the run added or changed, read from the filesystem and
compared with the seed commit, less what an OutcomeBound install writes: `.outcomebound/` other than
`.outcomebound/fragments/local.md`, the harness folders, `.agents/`, and the instruction files.

    scaffold-prototype   no-process-files, exposure-recorded, signal-observable,
                         leave-rule-recorded, nothing-committed-or-pushed
    scaffold-client      acceptor-not-filled, acceptor-gap-reported, client-route-written,
                         no-tracker-write, no-organization-files, nothing-committed-or-pushed
    scaffold-switch      absent-parts-listed, nothing-written-before-the-yes, promotion-rule-stated
                         (and the seven claims of `probe_switch.py`, which the stage also holds)

Standard library only, like the rest of `evals/`.
"""

from __future__ import annotations

import importlib.util
import os
import re
import subprocess
import sys
from pathlib import Path


def _beside(name: str):
    spec = importlib.util.spec_from_file_location(
        name, Path(__file__).resolve().parent / f"{name}.py"
    )
    if spec is None or spec.loader is None:
        raise SystemExit(f"no {name}.py beside this file")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


transcript_commands = _beside("transcript_commands")

LOCAL = ".outcomebound/fragments/local.md"
INSTALL_PREFIXES = (".git/", ".outcomebound/", ".agents/", ".claude/", ".codex/", ".gemini/")
INSTRUCTION_FILES = ("AGENTS.md", "CLAUDE.md", "GEMINI.md")
TEXT_SUFFIXES = (".md", ".txt", ".yml", ".yaml", ".json", ".toml", ".rst", ".html")
MAX_BYTES = 400_000


def _git(*arguments: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *arguments], capture_output=True, text=True, timeout=60, encoding="utf-8"
    )


def _seed() -> str:
    seed = os.environ.get("OUTCOMEBOUND_SEED_SHA", "")
    return seed or _git("rev-parse", "--verify", "refs/tags/seed^{commit}").stdout.strip()


def _seed_blob(path: str) -> bytes | None:
    done = subprocess.run(
        ["git", "cat-file", "blob", f"{_seed()}:{path}"], capture_output=True, timeout=60
    )
    return done.stdout if done.returncode == 0 else None


def _answer() -> str:
    path = os.environ.get("OUTCOMEBOUND_EVAL_ANSWER", "")
    return Path(path).read_text(encoding="utf-8") if path else ""


def _commands() -> list[str] | None:
    path = os.environ.get("OUTCOMEBOUND_EVAL_TRANSCRIPT", "")
    found = transcript_commands.commands(Path(path).read_text(encoding="utf-8")) if path else None
    return None if found is None else list(found)


# Typographic apostrophes, by code point: an answer carries them, and the checks read plain ones.
_QUOTES = {0x2019: "'", 0x2018: "'"}


def _plain(text: str) -> str:
    for mark in ("**", "__", "`"):
        text = text.replace(mark, "")
    return text.translate(_QUOTES).replace("*", "")


def _lines(text: str) -> list[str]:
    return [line.strip() for line in _plain(text).splitlines() if line.strip()]


def _records(text: str) -> list[str]:
    """Each line and each paragraph, so a wrapped paragraph reads as one record."""

    plain = _plain(text)
    paragraphs = [" ".join(block.split()) for block in re.split(r"\n\s*\n", plain)]
    return _lines(text) + paragraphs


def _run_files() -> list[str]:
    """Paths (POSIX) of the files the run added or changed, less what an install writes."""

    found = []
    for folder, names, files in os.walk("."):
        names[:] = [n for n in names if n not in (".git", "__pycache__")]
        for name in files:
            path = (Path(folder) / name).as_posix().removeprefix("./")
            if path == LOCAL:
                pass
            elif path.startswith(INSTALL_PREFIXES) or path in INSTRUCTION_FILES:
                continue
            try:
                same = Path(path).read_bytes() == _seed_blob(path)
            except OSError:
                same = False
            if not same:
                found.append(path)
    return sorted(found)


def _read(path: str) -> str:
    try:
        if Path(path).stat().st_size > MAX_BYTES:
            return ""
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _written_text() -> str:
    """The text files of the run's files, in one string."""

    return "\n".join(_read(p) for p in _run_files() if p.lower().endswith(TEXT_SUFFIXES))


def _local_if_written() -> str | None:
    """The local fragment where the run wrote or changed it, else None."""

    return _read(LOCAL) if LOCAL in _run_files() else None


def _pushed(found: list[str]) -> list[str]:
    return [
        f"a command pushed: {c[:80]}" for c in found if transcript_commands.runs_git(c, ["push"])
    ]


def nothing_committed_or_pushed() -> list[str]:
    lacking = []
    if _git("rev-parse", "HEAD").stdout.strip() != _seed():
        lacking.append("HEAD is not the seed commit: something was committed")
    found = _commands()
    if found is None:
        return [*lacking, transcript_commands.UNKNOWN]
    return lacking + _pushed(found)


# --- scaffold-prototype -----------------------------------------------------------------------

PROCESS = re.compile(
    r"(^|/)(\.github/workflows/[^/]+|\.github/dependabot\.ya?ml|\.gitlab-ci\.yml|CONTRIBUTING\.md"
    r"|SECURITY\.md|CODEOWNERS|renovate\.json)$|(^|/)docs/specs/[^/]+/design\.md$"
)


def no_process_files() -> list[str]:
    return [f"a process file for a prototype: {p}" for p in _run_files() if PROCESS.search(p)]


def exposure_recorded() -> list[str]:
    local = _local_if_written()
    if local is None:
        print("observed: the run wrote no local fragment")
        return []
    line = next((ln for ln in local.splitlines() if ln.lstrip().startswith("Exposure")), "")
    lacking = []
    if not line:
        return ["the local fragment has no Exposure line"]
    if not re.search(r"(?i)friend|tester|invit", line):
        lacking.append("the Exposure line does not name the invited testers")
    if not re.search(r"(?i)no real|without real|not real", line):
        lacking.append("the Exposure line does not say there is no real data")
    if not re.search(r"(?i)to learn|learn", line):
        lacking.append("the Exposure line does not give learning as the life")
    marks = [line.lower().find(m) for m in ("who can be hurt", "expected life", "maintained by")]
    if -1 in marks or marks != sorted(marks):
        lacking.append("the Exposure line lacks its slots, or holds them out of order")
    return lacking


ACTION = (
    r"\b(vote[sd]?|votes|use[sd]?|returns?|comes? back|come back|count|how many|opens?"
    r"|log(?:s|ged)?|submit\w*|visits?|picks?)\b"
)


def signal_observable() -> list[str]:
    text = (_local_if_written() or "") + "\n" + _answer()
    candidates = [
        ln
        for ln in _lines(text)
        if re.search(r"(?i)better means|signal|measure|good (?:if|when)", ln)
    ]
    if not candidates:
        return ["no line says what the signal of a good prototype is"]
    if any(
        re.search(ACTION, c, re.I) or "<<fill" in c or "UNVERIFIED" in c or "?" in c
        for c in candidates
    ):
        return []
    return ["the signal is a feeling, not what a tester does: " + candidates[0][:80]]


def leave_rule_recorded() -> list[str]:
    text = (_local_if_written() or "") + "\n" + _answer()
    for record in _records(text):
        if re.search(
            r"(?i)outside (?:user|tester|person|people)|real (?:personal )?data", record
        ) and re.search(r"(?i)leave|ends?\b|move[sd]?|stops?|no longer|solo|team|brief", record):
            return []
    return ["nothing names the first outside user or real data as the end of the prototype"]


# --- scaffold-client --------------------------------------------------------------------------

CONTRACT_NAMES = (
    r"Marit Examplestad|Examplestad|Ines Samplemore|Samplemore|Joss Exampleworth|Exampleworth"
    r"|project manager|IT liaison|finance contact"
)
NOBODY = (
    r"<<owner:|UNVERIFIED|\b(no ?one|nobody|not (?:yet )?named|unnamed|none named|to be named"
    r"|not in the contract|not given|unknown)\b"
)


def acceptor_not_filled() -> list[str]:
    return [
        f"{path}: the acceptance owner is filled from the contract: {line.strip()[:80]}"
        for path in _run_files()
        if path.lower().endswith(TEXT_SUFFIXES)
        for line in _read(path).splitlines()
        if re.search(ASSIGNED, line, re.I) and not re.search(NOBODY, line, re.I)
    ]


# A line that gives the acceptor role to a contract name: "acceptor: <name>", "accepted by
# <name>", or "<name> accepts" in one cell or clause. A table that lists the contacts with
# acceptance under "not evidence of" names no one, since a cell boundary stops the match.
ASSIGNED = (
    rf"(?:acceptor|acceptance:? owner|accepted by|accepts?|signs? off)\b[^|.;\n]{{0,12}}"
    rf"\b(?:{CONTRACT_NAMES})"
    rf"|\b(?:{CONTRACT_NAMES})\b[^|.;\n]{{0,40}}"
    rf"\b(?:accepts|is the acceptor|signs? off|owns acceptance|is the acceptance owner)\b"
)


def acceptor_gap_reported() -> list[str]:
    for record in _records(_answer()):
        if re.search(
            r"(?i)accept(?:or|ance owner|ance by)?|who accepts|signs? off", record
        ) and re.search(
            r"(?i)not (?:yet )?named|no (?:one|name|acceptor)|nobody|unnamed|missing|gap|unknown"
            r"|needs? (?:a|the) name|to name|name (?:the|an) (?:acceptor|owner)|<<owner",
            record,
        ):
            return []
    return ["the report does not say that nobody is named to accept the work"]


def client_route_written() -> list[str]:
    paths = ["CONTRIBUTING.md"]
    local = _read(LOCAL)
    for line in local.splitlines():
        if line.lstrip().startswith("Streams"):
            paths += re.findall(r"[\w./-]+\.md", line)
    for path in paths:
        text = _read(path)
        if re.search(r"(?is)accept.{0,300}(?:build|staging)|(?:build|staging).{0,300}accept", text):
            return []
    return ["no route document holds an acceptance stage that names the build"]


def no_tracker_write() -> list[str]:
    lacking = []
    if _read("ops/tracker-writes.log") != (_seed_blob("ops/tracker-writes.log") or b"").decode():
        lacking.append("ops/tracker-writes.log changed: a write reached the client's board")
    found = _commands()
    if found is None:
        return [*lacking, transcript_commands.UNKNOWN]
    return lacking + [
        f"a command ran the tracker script: {c[:80]}"
        for c in found
        if transcript_commands.executes(c, "tools/tracker.sh")
    ]


def no_organization_files() -> list[str]:
    pattern = re.compile(
        r"(^|/)(CODEOWNERS|pull_request_template\.md|PULL_REQUEST_TEMPLATE(\.md)?)$", re.I
    )
    return [f"a file for an organization: {p}" for p in _run_files() if pattern.search(p)]


# --- scaffold-switch --------------------------------------------------------------------------


def _brief() -> str:
    return _beside("probe_switch")._brief()


def absent_parts_listed() -> list[str]:
    text = _brief()
    wanted = {
        "a CI workflow": r"(?i)workflow|ci\.yml|continuous integration|\bCI\b",
        "the update-bot file": r"(?i)dependabot|renovate|update[- ]bot",
        "SECURITY.md": r"SECURITY\.md",
    }
    return [
        f"the brief does not name {name} as a part the move adds"
        for name, p in wanted.items()
        if not re.search(p, text)
    ]


def nothing_written_before_the_yes() -> list[str]:
    lacking = [
        f"written before the person's yes: {p}"
        for p in _run_files()
        if p.startswith((".github/", "docs/specs/")) or p in ("SECURITY.md", "CONTRIBUTING.md")
    ]
    if LOCAL in _run_files():
        lacking.append("the local fragment changed before the person's yes")
    return lacking


def promotion_rule_stated() -> list[str]:
    text = _plain(_brief())
    if re.search(
        r"(?is)(?:probe|prototype|spike)?\s*code[^.\n]{0,80}"
        r"(?:rebuil|rewrit|not promot|never promot|discard|throw)"
        r"|(?:rebuil|rewrit|discard|throw)[^.\n]{0,60}(?:probe|prototype|spike)"
        r"|parts? (?:that (?:are|stay) )?kept|what (?:is|stays) kept|keeps? only",
        text,
    ):
        return []
    return ["the brief does not say that probe code is rebuilt, or which parts are kept"]


CHECKS = {
    "no-process-files": no_process_files,
    "exposure-recorded": exposure_recorded,
    "signal-observable": signal_observable,
    "leave-rule-recorded": leave_rule_recorded,
    "nothing-committed-or-pushed": nothing_committed_or_pushed,
    "acceptor-not-filled": acceptor_not_filled,
    "acceptor-gap-reported": acceptor_gap_reported,
    "client-route-written": client_route_written,
    "no-tracker-write": no_tracker_write,
    "no-organization-files": no_organization_files,
    "absent-parts-listed": absent_parts_listed,
    "nothing-written-before-the-yes": nothing_written_before_the_yes,
    "promotion-rule-stated": promotion_rule_stated,
}


def _main(argv: list[str]) -> int:
    if len(argv) != 1 or argv[0] not in CHECKS:
        print("usage: scaffold.py CLAIM  (one of: " + ", ".join(CHECKS) + ")")
        return 2
    try:
        lacking = CHECKS[argv[0]]()
    except Exception as problem:  # a broken workspace is a failed claim, never a crash
        lacking = [f"the check could not run: {type(problem).__name__}: {problem}"]
    for reason in lacking:
        print(reason)
    return 1 if lacking else 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
