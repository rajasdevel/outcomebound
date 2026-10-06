"""`outcomebound research ...`: how an agent reaches the research repository, and how a finding
goes back to it (`docs/specs/research/design.md`).

What this module decides: where the one clone per machine is (`OUTCOMEBOUND_RESEARCH`, else the
link `~/.outcomebound/research`); that printing a document reads files and never runs anything,
Git included, the clone's commit being read from its `.git` files; which acts reach the network
(`clone` and `pull`, each only with `--accept`, as `floor provision` is); and what a finding is
(`ingest`'s fields, their bounds, the inbox file's name and bytes, and the prefilled issue link).
Exit 0: done or previewed; 1: refused, or Git failed; 2: usage; 3: no clone configured.

What it does not decide: what the research says, or how the research repository takes a finding
in. The clone is written only through Git, and a project only at its inbox file.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
import unicodedata
from collections.abc import Mapping, Sequence
from pathlib import Path
from urllib.parse import quote, urlencode, urlsplit

from outcomebound_tools import fileplan, paths
from outcomebound_tools.gitenv import git_environment

REPOSITORY = "https://github.com/rajasdevel/outcomebound-research"
BLOB = f"{REPOSITORY}/blob/main/"
CLONE_URL = f"{REPOSITORY}.git"
ISSUE_FORM = f"{REPOSITORY}/issues/new?template=finding.yml"
ENVIRONMENT = "OUTCOMEBOUND_RESEARCH"
LINK_TEXT = "~/.outcomebound/research"
INDEX = "INDEX.md"
INBOX = ".outcomebound/research-inbox"
SUBCOMMANDS = ("clone", "pull", "ingest")
KINDS = ("fact", "correction")
FORMAT_VERSION = 1
SUBJECT_MAX, CLAIM_MAX, URL_MAX, QUOTE_WORDS = 200, 2000, 2000, 25
QUOTE_MAX, CORRECTS_MAX, LINK_MAX, FINDING_MAX = 300, 200, 8000, 16 * 1024
FIELDS = ("kind", "subject", "claim", "url", "quote", "observed_on", "corrects")
REQUIRED = ("kind", "subject", "claim", "url", "observed_on")
GIT_SECONDS = 600.0
TAIL = 2000
SMALL = 1 << 20
HEX = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")
REF = re.compile(r"refs/[A-Za-z0-9._/-]+")
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
# What Git inherits from a hook or a caller would point it at another repository, or add
# configuration (`url.*.insteadOf` among it) that the person never wrote.
GIT_UNSET = (
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_COMMON_DIR",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_CEILING_DIRECTORIES",
    "GIT_CONFIG",
    "GIT_CONFIG_COUNT",
    "GIT_CONFIG_PARAMETERS",
    "GIT_TEMPLATE_DIR",
    "GIT_EXEC_PATH",
)
GIT_UNSET_PREFIXES = ("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_")
# The user's and the system's Git configuration, which could rewrite the source with `insteadOf`.
GIT_CONFIG_OFF = {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
# Git, asked so that no hook and no fsmonitor of the clone runs, and only https is spoken.
GIT_CONFIGURATION = (
    "-c",
    "core.hooksPath=/dev/null",
    "-c",
    "core.fsmonitor=false",
    "-c",
    "protocol.allow=never",
    "-c",
    "protocol.https.allow=always",
)
UNREADABLE = (OSError, RuntimeError, ValueError)
# Git runs without the user's and the system's configuration, so a failure that those settings
# would have cured (a proxy, a certificate store) can be ours; the person has this way round it.
OWN_GIT = (
    "git ran without your Git configuration; to use it, clone the repository yourself and set "
    f"{ENVIRONMENT} to the folder"
)


class Refusal(Exception):
    """Exit 1: the text is what goes to standard error, after `research: `."""


class NoClone(Exception):
    """Exit 3: the text is what goes to standard error, whole."""


# --- Where the clone is ------------------------------------------------------------------


def _link() -> Path:
    return Path.home() / ".outcomebound" / "research"


def _overridden() -> str:
    return os.environ.get(ENVIRONMENT, "").strip()


def _not_configured(first: str, path: str) -> NoClone:
    where = quote(path, safe="/")
    return NoClone(
        f"research: {first}\n"
        f"read it at {BLOB}{where}\n"
        "clone it once per machine, with the person's yes: outcomebound research clone "
        "<destination>"
    )


def clone_root(path: str = INDEX) -> Path:
    """The folder research is read from, or `NoClone` saying why there is none."""

    try:
        return _clone_root(path)
    except UNREADABLE as error:
        raise _not_configured(
            f"no clone configured: the clone cannot be read ({type(error).__name__})", path
        ) from error


def _pointer(link: Path) -> Path | None:
    """The folder a pointer file names, where `link` is one: a small regular file whose first
    line is an absolute path. `clone` writes one on Windows, where a link needs rights that a
    normal account lacks."""

    if link.is_symlink() or not link.is_file():
        return None
    first = (_small_text(link) or "").strip().splitlines()[:1]
    return Path(first[0]) if first and os.path.isabs(first[0]) else None


def _clone_root(path: str) -> Path:
    override = _overridden()
    if override:
        root = Path(os.path.expanduser(override)).resolve()
        if not (root / INDEX).is_file():
            raise _not_configured(
                f"no clone configured: {ENVIRONMENT} names {root}, which holds no {INDEX}", path
            )
        return root
    link = _link()
    if not os.path.lexists(link):
        raise _not_configured(
            f"no clone configured: {ENVIRONMENT} is unset and {LINK_TEXT} does not exist", path
        )
    root = _pointer(link) or link.resolve()
    if not root.is_dir():
        raise _not_configured(f"no clone configured: {LINK_TEXT} points at nothing", path)
    if not (root / INDEX).is_file():
        raise _not_configured(f"no clone configured: {LINK_TEXT} holds no {INDEX}", path)
    return root


# --- The clone's commit, read without Git ----------------------------------------------------


def _small_text(path: Path) -> str | None:
    """Up to a mebibyte of a regular file, or None."""

    try:
        if not path.is_file():
            return None
        with path.open("rb") as handle:
            return handle.read(SMALL).decode("utf-8", "replace")
    except OSError:
        return None


def _git_dir(root: Path) -> Path | None:
    """The folder `.git` is, or the one its `gitdir:` line names (a worktree)."""

    try:
        dot = root / ".git"
        if dot.is_symlink():
            return None
        if dot.is_dir():
            return dot
        first = (_small_text(dot) or "").strip().splitlines()[:1]
        if first and first[0].startswith("gitdir:"):
            target = (root / first[0][len("gitdir:") :].strip()).resolve()
            return target if target.is_dir() else None
    except UNREADABLE:
        return None
    return None


def _common_dir(git_dir: Path) -> Path:
    text = _small_text(git_dir / "commondir")
    if text is None or not text.strip():
        return git_dir
    common = (git_dir / text.strip()).resolve()
    return common if common.is_dir() else git_dir


def _packed(common: Path, ref: str) -> str | None:
    for line in (_small_text(common / "packed-refs") or "").splitlines():
        value, _, name = line.partition(" ")
        if name.strip() == ref and HEX.fullmatch(value):
            return value
    return None


def _resolve_ref(git_dir: Path, ref: str) -> str | None:
    if not REF.fullmatch(ref) or ".." in ref.split("/"):
        return None
    common = _common_dir(git_dir)
    for base in (git_dir, common):
        value = (_small_text(base / ref) or "").strip()
        if HEX.fullmatch(value):
            return value
    return _packed(common, ref)


def _commit(git_dir: Path) -> str | None:
    head = (_small_text(git_dir / "HEAD") or "").strip()
    if head.startswith("ref:"):
        return _resolve_ref(git_dir, head[len("ref:") :].strip())
    return head if HEX.fullmatch(head) else None


def _last_line(path: Path) -> str | None:
    try:
        if not path.is_file():
            return None
        with path.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            handle.seek(max(0, handle.tell() - 8192))
            lines = handle.read(8192).decode("utf-8", "replace").splitlines()
    except OSError:
        return None
    return next((line for line in reversed(lines) if line.strip()), None)


def _moved_on(git_dir: Path) -> str | None:
    """The UTC day `HEAD` last moved, from the last line of its reflog."""

    line = _last_line(git_dir / "logs" / "HEAD")
    if line is None:
        return None
    fields = line.split("\t", 1)[0].rsplit(" ", 2)
    try:
        stamp = datetime.datetime.fromtimestamp(int(fields[-2]), datetime.timezone.utc)
    except (ValueError, IndexError, OverflowError, OSError):
        return None
    return stamp.date().isoformat()


def _commit_and_day(root: Path) -> tuple[str, str]:
    """The commit's first 12 hex and the day `HEAD` last moved, each `unknown` where the `.git`
    files lack it."""

    try:
        git_dir = _git_dir(root)
        commit = _commit(git_dir) if git_dir else None
        day = _moved_on(git_dir) if git_dir else None
    except UNREADABLE:
        commit = day = None
    return (commit[:12] if commit else "unknown", day or "unknown")


def version(root: Path) -> str:
    """`<12 hex of the commit> (<YYYY-MM-DD>)`, each `unknown` where the `.git` files lack it."""

    commit, day = _commit_and_day(root)
    return f"{commit} ({day})"


# --- Print -------------------------------------------------------------------------------------


def show(path: str) -> int:
    if not paths.admits(path):
        raise Refusal(f"{path}: not a bounded relative path")
    root = clone_root(path)
    try:
        data = paths.read_bounded(root, path)
    except paths.PathError as error:
        raise Refusal(f"{path}: {_why_not(root, path, str(error))}") from error
    # LF whatever the clone's checkout has, so that one file has one digest on every machine.
    text = data.decode("utf-8", "replace").replace("\r\n", "\n")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
    commit, day = _commit_and_day(root)
    # The bytes are the working tree's, which Git was not asked to compare with the commit.
    sys.stdout.write(
        f"research: {path} (working tree of the clone at {commit}, HEAD moved {day}; "
        f"sha256 {digest} of the text below)\n"
    )
    sys.stdout.write(text)
    sys.stdout.flush()
    return 0


def _why_not(root: Path, path: str, message: str) -> str:
    if not message.startswith("not a readable file") or not paths.admits(path):
        return message
    target = root / path
    if target.is_dir():
        return "a folder, not a document"
    if not target.exists() and path.startswith("models/"):
        return (
            "not in the clone; models/README.md says which models have a file, and a model "
            "with no file takes the spec tier (applications/implementer-tiers.md)"
        )
    if not target.exists():
        return f"not in the clone; {INDEX} lists every document"
    return message


# --- Clone and pull: the networked acts --------------------------------------------------------


def child_environment(inherited: Mapping[str, str] | None = None) -> dict[str, str]:
    """What Git runs under: the caller's environment without the variables that would point it
    at another repository or add configuration, the user's and system configuration off, no
    prompt."""

    kept = {
        key: value
        for key, value in (os.environ if inherited is None else inherited).items()
        if key not in GIT_UNSET and not key.startswith(GIT_UNSET_PREFIXES)
    }
    return {**kept, **GIT_CONFIG_OFF, "GIT_TERMINAL_PROMPT": "0"}


def _run_git(arguments: list[str]) -> str | None:
    """Run Git as an argument list, never through a shell; None on success, else why not."""

    try:
        done = subprocess.run(
            ["git", *arguments],
            env=git_environment(child_environment()),
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=GIT_SECONDS,
        )
    except FileNotFoundError:
        return "git is not on PATH"
    except subprocess.TimeoutExpired:
        return f"git did not finish in {GIT_SECONDS:.0f} seconds"
    if done.returncode == 0:
        return None
    output = f"{done.stdout or ''}{done.stderr or ''}".strip()
    return f"git exited {done.returncode}\n{output[-TAIL:]}\n{OWN_GIT}".strip()


def _inside_work_tree(directory: Path) -> bool:
    return any((folder / ".git").exists() for folder in (directory, *directory.parents))


def _check_destination(destination: Path) -> None:
    if os.path.lexists(destination) and (
        destination.is_symlink() or not destination.is_dir() or any(destination.iterdir())
    ):
        raise Refusal(f"clone: {destination} exists and is not an empty folder")
    if _inside_work_tree(destination.resolve().parent):
        raise Refusal(
            f"clone: {destination} would sit inside a Git work tree, where a harness would load "
            "the clone's AGENTS.md; name a folder outside any project"
        )
    link = _link()
    if os.path.lexists(link) and not link.is_symlink() and _pointer(link) is None:
        raise Refusal(
            f"clone: {LINK_TEXT} exists and is neither a symlink nor a pointer file; "
            "move it aside first"
        )


def _point_link(destination: Path) -> None:
    link = _link()
    link.parent.mkdir(parents=True, exist_ok=True)
    staged = link.with_name(f"research.{os.getpid()}.outcomebound-stage")
    staged.unlink(missing_ok=True)
    try:
        if paths.on_windows():
            # A symbolic link needs Administrator rights or Developer Mode there, and a junction
            # has no call in the standard library's public interface: a pointer file needs
            # neither, and `clone_root` reads it as it reads the link.
            staged.write_text(f"{destination.as_posix()}\n", encoding="utf-8", newline="\n")
            if link.is_symlink():
                link.unlink()
        else:
            staged.symlink_to(destination)
        os.replace(staged, link)
    finally:
        staged.unlink(missing_ok=True)


def _command(arguments: list[str]) -> str:
    """The Git command line a preview shows, quoted for the shell it is read in."""

    return " ".join(paths.shell_word(word) for word in ["git", *arguments])


def clone(destination_text: str, accept: bool) -> int:
    destination = Path(os.path.abspath(os.path.expanduser(destination_text)))
    _check_destination(destination)
    arguments = [*GIT_CONFIGURATION, "clone", CLONE_URL, destination.as_posix()]
    print(f"{'runs' if accept else 'would run'}: {_command(arguments)}")
    if not accept:
        print(f"would link: {LINK_TEXT} -> {destination.as_posix()}")
        if _overridden():
            print(f"{ENVIRONMENT} is set and overrides the link: printing reads that folder")
        print("nothing cloned: pass --accept")
        return 0
    failure = _run_git(arguments)
    if failure is not None:
        left = (
            f"\n{destination} may hold part of a clone: remove it before you try again"
            if os.path.lexists(destination)
            else ""
        )
        raise Refusal(f"clone: {failure}\nthe link is left as it was{left}")
    try:
        _point_link(destination)
    except OSError as error:
        raise Refusal(f"clone: cloned, but the link was not made: {error}") from error
    print(f"linked: {LINK_TEXT} -> {destination.as_posix()}")
    return 0


def pull(accept: bool) -> int:
    root = clone_root()
    if _git_dir(root) is None:
        raise Refusal(f"pull: {root} has no .git, so it is not a Git clone")
    arguments = [*GIT_CONFIGURATION, "-C", root.as_posix(), "pull", "--ff-only", CLONE_URL, "main"]
    print(f"{'runs' if accept else 'would run'}: {_command(arguments)}")
    if not accept:
        print("nothing pulled: pass --accept")
        return 0
    failure = _run_git(arguments)
    if failure is not None:
        raise Refusal(f"pull: {failure}")
    print(f"research: now at {version(root)}")
    return 0


# --- Ingest: a finding goes back ---------------------------------------------------------------


def _text(name: str, value: object) -> str:
    """One line of valid UTF-8 with no control (`Cc`) or format (`Cf`) character: the format
    characters are the zero-width, bidirectional and tag characters that hide text."""

    if not isinstance(value, str):
        raise Refusal(f"ingest: {name} is not text")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        raise Refusal(f"ingest: {name} is not valid UTF-8") from None
    if any(unicodedata.category(char) in ("Cc", "Cf") for char in value):
        raise Refusal(
            f"ingest: {name} holds a line break, a control character or an invisible character"
        )
    return value


def _bounded(name: str, value: object, longest: int) -> str:
    value = _text(name, value)
    if not value.strip() or len(value) > longest:
        raise Refusal(f"ingest: {name} must be 1 to {longest} characters")
    return value


def _checked_url(value: object) -> str:
    value = _text("url", value)
    refusal = Refusal(
        "ingest: url must be http or https, with a host, no userinfo, no space, and at most "
        f"{URL_MAX} characters"
    )
    if not value or len(value) > URL_MAX or any(char.isspace() for char in value):
        raise refusal
    try:
        parts = urlsplit(value)
        host, _ = parts.hostname, parts.port
    except ValueError:
        raise refusal from None
    if parts.scheme not in ("http", "https") or not host or "@" in parts.netloc:
        raise refusal
    return value


def _checked_date(value: object, today: datetime.date) -> str:
    value = _text("observed-on", value)
    try:
        day = datetime.date.fromisoformat(value) if DATE.fullmatch(value) else None
    except ValueError:
        day = None
    if day is None or day > today + datetime.timedelta(days=1):
        raise Refusal(
            "ingest: observed-on must be a real date, YYYY-MM-DD, at most one day after today"
        )
    return day.isoformat()


def _checked_quote(value: object) -> str:
    quoted = _text("quote", value)
    if len(quoted.split()) > QUOTE_WORDS or len(quoted) > QUOTE_MAX:
        raise Refusal(
            f"ingest: quote must be at most {QUOTE_WORDS} words and {QUOTE_MAX} characters"
        )
    return quoted


def checked_fields(
    data: Mapping[str, object], today: datetime.date | None = None
) -> dict[str, str]:
    """The finding in `data`, every field checked; each failure is one `Refusal`. A value that is
    absent, `None` or empty is not given; `observed_on` defaults to today."""

    today = today or datetime.date.today()
    given = {name: data.get(name) for name in FIELDS if data.get(name) not in (None, "")}
    kind = _text("kind", given.get("kind", ""))
    if kind not in KINDS:
        raise Refusal(f"ingest: kind must be one of {', '.join(KINDS)}")
    fields = {
        "kind": kind,
        "subject": _bounded("subject", given.get("subject", ""), SUBJECT_MAX),
        "claim": _bounded("claim", given.get("claim", ""), CLAIM_MAX),
        "url": _checked_url(given.get("url", "")),
        "observed_on": _checked_date(given.get("observed_on", today.isoformat()), today),
    }
    if "quote" in given:
        fields["quote"] = _checked_quote(given["quote"])
    if "corrects" in given:
        fields["corrects"] = _text("corrects", given["corrects"])
        if len(fields["corrects"]) > CORRECTS_MAX:
            raise Refusal(f"ingest: corrects must be at most {CORRECTS_MAX} characters")
    if kind == "correction" and not fields.get("corrects", "").strip():
        raise Refusal("ingest: a correction needs --corrects: the path or evidence id it corrects")
    return fields


def checked_document(data: object, today: datetime.date | None = None) -> dict[str, str]:
    """The finding in an inbox file's decoded JSON, or a `Refusal`: an object of `version` 1 and
    the finding's fields, no other key."""

    if not isinstance(data, dict):
        raise Refusal("ingest: not a JSON object")
    unknown = sorted(set(data) - {"version", *FIELDS})
    if unknown:
        raise Refusal(f"ingest: unknown key: {', '.join(unknown)}")
    missing = [name for name in REQUIRED if name not in data]
    if missing:
        raise Refusal(f"ingest: missing key: {', '.join(missing)}")
    version_value = data.get("version")
    if version_value != FORMAT_VERSION or isinstance(version_value, bool):
        raise Refusal(f"ingest: version is not {FORMAT_VERSION}")
    empty = [name for name in REQUIRED if data[name] in (None, "")]
    if empty:
        raise Refusal(f"ingest: {', '.join(empty)} is empty")
    return checked_fields(data, today)


def finding(options: argparse.Namespace) -> dict[str, str]:
    """The finding `options` give, every field checked, and its issue link within bounds."""

    given = {
        "kind": options.kind,
        "subject": options.subject,
        "claim": options.claim,
        "url": options.url,
        "quote": options.quote,
        "observed_on": options.observed_on,
        "corrects": options.corrects,
    }
    stripped = {name: value.strip() for name, value in given.items() if isinstance(value, str)}
    fields = checked_fields(stripped)
    if len(issue_link(fields)) > LINK_MAX:
        raise Refusal(
            f"ingest: the issue link would pass {LINK_MAX} characters, which GitHub may refuse; "
            "shorten the claim, quote or url"
        )
    return fields


def finding_bytes(fields: dict[str, str]) -> bytes:
    document = {"version": FORMAT_VERSION, **fields}
    data = (json.dumps(document, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode(
        "utf-8"
    )
    if len(data) > FINDING_MAX:
        raise Refusal(f"ingest: the finding is larger than {FINDING_MAX // 1024} KiB")
    return data


def inbox_name(fields: dict[str, str]) -> str:
    digest = hashlib.sha256((fields["claim"] + fields["url"]).encode("utf-8")).hexdigest()
    return f"{fields['observed_on'].replace('-', '')}-{digest}.json"


def issue_link(fields: dict[str, str]) -> str:
    order = ("kind", "subject", "claim", "url", "quote", "observed_on", "corrects")
    pairs = [(name, fields[name]) for name in order if fields.get(name)]
    return f"{ISSUE_FORM}&{urlencode(pairs, quote_via=quote)}"


def _project(given: Path | None) -> Path:
    if given is not None:
        if not given.is_dir():
            raise Refusal(f"ingest: {given} is not a directory")
        return _outside_git(given.resolve())
    here = Path.cwd().resolve()
    for folder in (here, *here.parents):
        if (folder / ".git").exists():
            return _outside_git(folder)
    raise Refusal("ingest: not inside a Git work tree; name the project with --project DIR")


def _outside_git(project: Path) -> Path:
    if any(paths.names_git(part) for part in project.parts):
        raise Refusal(f"ingest: {project} is inside a .git folder; name the project itself")
    return project


def ingest(options: argparse.Namespace) -> int:
    fields = finding(options)
    data = finding_bytes(fields)
    project = _project(options.project)
    relative = f"{INBOX}/{inbox_name(fields)}"
    try:
        present = fileplan.current(project, relative)
        if present is not None and present != data:
            raise Refusal(f"ingest: {relative} holds a different finding; change the claim or url")
        if present is None:
            fileplan.write(project, {relative: data}, {relative: None})
    except (fileplan.WriteError, OSError) as error:
        raise Refusal(f"ingest: {error}") from error
    print(f"issue: {issue_link(fields)}")
    print(f"{'unchanged' if present is not None else 'wrote'}: {(project / relative).as_posix()}")
    print(
        "open the issue link in a browser to send the finding: that, or a pull request, is how it "
        "reaches the research repository; the file is a local record, which "
        "nothing reads or sends"
    )
    return 0


# --- The command line --------------------------------------------------------------------------

DESCRIPTION = f"""\
Read the research repository, and send a finding back to it.

  outcomebound research [PATH]     print PATH (default {INDEX}) from the clone's working tree,
                                   its first line the clone's commit and the sha256 of the
                                   text; with no clone configured, name the public link, exit 3
  outcomebound research clone DESTINATION [--accept]
                                   git clone it into DESTINATION, outside any project, and
                                   link {LINK_TEXT} to it
  outcomebound research pull [--accept]
                                   git pull --ff-only in the clone, from the public repository,
                                   with hooks, fsmonitor and your Git configuration off
  outcomebound research ingest ... write a finding under {INBOX}/
                                   and print the prefilled issue link (ingest --help)

The clone is the folder {ENVIRONMENT} names when that is set, else {LINK_TEXT}.
Printing reads files and runs nothing, Git included. clone and pull reach the network and
change nothing without --accept.
Exit 0: done or previewed; 1: refused, or Git failed; 2: usage; 3: no clone configured."""
INGEST_DESCRIPTION = f"""\
Write one finding under {INBOX}/ in the project, and print the link that opens the research
repository's finding issue form with it filled in. The engine opens no connection. The link,
opened in a browser, or a pull request is how a finding reaches the research repository; the file
is a local record that nothing reads or sends.

Write the claim in your own words; name no project, client or person. A finding is refused
when a value holds a line break, a control character or an invisible one (zero-width, bidirectional
or tag), the subject is not 1 to {SUBJECT_MAX} characters, the claim not 1 to {CLAIM_MAX}, the url
not http or https with a host, no userinfo and at most {URL_MAX} characters, the quote more than
{QUOTE_WORDS} words or {QUOTE_MAX} characters, corrects more than {CORRECTS_MAX} characters, the
date not real or more than a day after today, a correction names nothing it corrects, or the issue
link would pass {LINK_MAX} characters."""


def _print_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="outcomebound research",
        usage="outcomebound research [PATH | clone | pull | ingest] [option ...]",
        description=DESCRIPTION,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("path", nargs="?", default=INDEX, metavar="PATH")
    return parser


def _verb_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="outcomebound research")
    verbs = parser.add_subparsers(dest="verb", required=True, prog="outcomebound research")
    cloning = verbs.add_parser("clone", description="Clone the research repository.")
    cloning.add_argument("destination", metavar="DESTINATION")
    pulling = verbs.add_parser("pull", description="Fast-forward the clone.")
    for networked in (cloning, pulling):
        networked.add_argument("--accept", action="store_true", help="run; without it, preview")
    sending = verbs.add_parser(
        "ingest",
        description=INGEST_DESCRIPTION,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sending.add_argument("--kind", required=True, metavar="fact|correction")
    sending.add_argument("--subject", required=True, help="e.g. claude-opus-5-5, harness:codex")
    sending.add_argument("--claim", required=True, help="one or two sentences, your own words")
    sending.add_argument("--url", required=True, help="the source")
    sending.add_argument("--quote", help=f"at most {QUOTE_WORDS} words, verbatim from the source")
    sending.add_argument("--observed-on", help="the day the source was read; default today")
    sending.add_argument("--corrects", help="the research path or evidence id a correction fixes")
    sending.add_argument("--project", type=Path, metavar="DIR", help="default: the Git work tree")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    try:
        if not arguments or arguments[0] not in SUBCOMMANDS:
            return show(_print_parser().parse_args(arguments).path)
        options = _verb_parser().parse_args(arguments)
        if options.verb == "clone":
            return clone(options.destination, options.accept)
        if options.verb == "pull":
            return pull(options.accept)
        return ingest(options)
    except NoClone as problem:
        print(problem, file=sys.stderr)
        return 3
    except Refusal as problem:
        print(f"research: {problem}", file=sys.stderr)
        return 1
    except BrokenPipeError:
        # The reader closed the pipe (`| head`): stop quietly, not with Python's flush complaint.
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
