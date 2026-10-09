"""The two lifecycle signals `adopt --detect` reads from Git and the version files, and the
drift lines `adopt --check` and `--detect` print where the files contradict the install's record.

What this module decides: how many distinct people wrote the recent history (authors counted by
email, bots and automation left out, never a name or an address kept); whether the project has a
release identity (a tag, or a version file); and which lines say that a signal is present while
the recorded fragment selection, or the exposure line of the project's `local` fragment, says
otherwise. Each line is `<signal> present, record says <what>`.

What it does not decide: whether a line is right (a person reads it), or any exit code: a drift
line refuses nothing. It reads files and runs read-only Git commands; it writes nothing.
"""

from __future__ import annotations

import json
import re
from collections.abc import Collection, Sequence
from pathlib import Path

from outcomebound_tools import discovery, facts

# "Recent" is the last 100 commits of the current branch that are not merges. A count, not a
# date: a project that was quiet for a year still shows who maintains it, and a busy one shows
# who works on it now. Merges are left out because a merge commit names whoever pressed the button.
WINDOW = 100
RELEASE_TAGS = "git tags"
VERSION_FILES = ("VERSION", "pyproject.toml", "package.json", "Cargo.toml")
CODEOWNERS = ("CODEOWNERS", ".github/CODEOWNERS", "docs/CODEOWNERS")
TEAM, SOLO, DEPLOY, CI_RELEASE = "team", "solo", "deploy", "ci-release"

# An author is a bot or automation when the name or address holds `[bot]`, or the part of the
# address before `@` is a no-reply mailbox or ends in `bot`. A person's private GitHub address,
# `<id>+<login>@users.noreply.github.com`, is neither: its part before `@` holds the login.
_NO_REPLY = re.compile(r"^(no-?reply|do-?not-?reply)$")
_BOT_MAILBOX = re.compile(r"(^|[-_.+])bot$")
_VERSION_LINE = re.compile(r"""^\s*version\s*=\s*["'][^"']+["']""", re.MULTILINE)
_EXPOSURE = re.compile(r"Exposure\s+[—-]", re.IGNORECASE)
_NEXT_PART = re.compile(r"^(\*\*|[A-Z][A-Za-z ]*\s—\s)")
_MAINTAINED = re.compile(r"maintained\s+by\s*:\s*([^;(\n]*)", re.IGNORECASE)
_ONE = re.compile(r"^\W*(one|1|a\s+single|single|sole|just\s+one|solo)\b", re.IGNORECASE)


def _is_bot(name: str, email: str) -> bool:
    if "[bot]" in name.lower() or "[bot]" in email:
        return True
    mailbox = email.split("@", 1)[0]
    return bool(_NO_REPLY.match(mailbox) or _BOT_MAILBOX.search(mailbox))


def recent_authors(target: Path) -> int | None:
    """The distinct author emails, lower-cased and after the project's `.mailmap`, of the last
    `WINDOW` commits that are not merges on the current branch, bots and automation left out;
    None where Git cannot read a history (no commit yet, or no Git)."""

    output = discovery.git_read(
        target, "log", f"--max-count={WINDOW}", "--no-merges", "--format=%aE%x1f%aN"
    )
    if output is None or not output.strip():
        return None
    people: set[str] = set()
    for line in output.decode("utf-8", "replace").splitlines():
        email, _, name = line.partition("\x1f")
        email = email.strip().lower()
        if email and not _is_bot(name, email):
            people.add(email)
    return len(people)


def release_identity(target: Path) -> list[str]:
    """The evidence of a release identity, in a fixed order: the repository has tags, and each
    version file that holds a version. Empty where there is none."""

    found: list[str] = []
    tags = discovery.git_read(target, "tag", "--list")
    if tags is not None and tags.strip():
        found.append(RELEASE_TAGS)
    for name in VERSION_FILES:
        text, _ = facts.read_small(target, name)
        if text is not None and _has_version(name, text):
            found.append(name)
    return found


def _has_version(name: str, text: str) -> bool:
    if name == "VERSION":
        return bool(text.strip())
    if name == "package.json":
        try:
            document = json.loads(text)
        except ValueError:
            return False
        return isinstance(document, dict) and isinstance(document.get("version"), str)
    return _VERSION_LINE.search(text) is not None


def signals(target: Path) -> list[facts.Signal]:
    """The recent-authors and release-identity signals, for `--detect`'s signal lines."""

    found: list[facts.Signal] = []
    authors = recent_authors(target)
    if authors is not None:
        where = f"git log, the last {WINDOW} commits without merges, bots left out"
        found.append(facts.Signal("recent-authors", where, str(authors), "Context"))
    evidence = release_identity(target)
    if evidence:
        found.append(facts.Signal("release-identity", ", ".join(evidence), "", "Distinguish"))
    return found


def _publishes(files: Sequence[facts.CiFile]) -> bool:
    """Whether `--detect` recognises a publishing workflow: a step that publishes, or a workflow
    file whose name starts with `release` or `publish`, as the `ci-release` fragment detects."""

    if any(item.kind == "publishing-workflow" for item in facts.workflow_signals(files)):
        return True
    return any(
        Path(item.path).name.startswith(("release", "publish"))
        for item in files
        if item.path.startswith(f"{facts.WORKFLOWS}/")
    )


def _has_codeowners(target: Path) -> bool:
    return any((target / name).is_file() for name in CODEOWNERS)


def maintained_by_one(local_text: str) -> bool:
    """Whether an `Exposure —` line of the `local` fragment says one person maintains the
    project. Lenient: a missing line, a missing `maintained by:` fact, or a value that does not
    start with one of the words for one, reads False."""

    lines = local_text.splitlines()
    for index, line in enumerate(lines):
        if not _EXPOSURE.search(line):
            continue
        parts = [line]
        for following in lines[index + 1 :]:
            if not following.strip() or _NEXT_PART.match(following):
                break
            parts.append(following.strip())
        match = _MAINTAINED.search(" ".join(parts))
        if match is not None and _ONE.match(match.group(1).strip()):
            return True
    return False


def lines(
    target: Path,
    selected: Collection[str],
    detected: Collection[str],
    files: Sequence[facts.CiFile],
    local_text: str | None,
) -> list[str]:
    """The drift lines, one for each signal the files show that the record contradicts.
    `selected` is the fragment selection the manifest records, `detected` the fragment ids
    `--detect` proposes from the files, `local_text` the `local` fragment's text where the
    record selects it."""

    found: list[str] = []
    authors = recent_authors(target) or 0
    claims = ((TEAM not in selected, "team not selected"), (SOLO in selected, "solo selected"))
    said = [phrase for held, phrase in claims if held]
    if said:
        if authors >= 2:
            found.append(f"{authors} recent authors present, record says {' and '.join(said)}")
        if _has_codeowners(target):
            found.append(f"CODEOWNERS present, record says {' and '.join(said)}")
    if DEPLOY in detected and DEPLOY not in selected:
        found.append("deploy configuration present, record says deploy not selected")
    if _publishes(files) and CI_RELEASE not in selected:
        found.append("publishing workflow present, record says ci-release not selected")
    if authors >= 2 and local_text is not None and maintained_by_one(local_text):
        found.append(
            f"{authors} recent authors present, record says the local Exposure line is "
            "maintained by one person"
        )
    return found
