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
from collections.abc import Sequence
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
SUBJECT_MAX, CLAIM_MAX, QUOTE_WORDS, FINDING_MAX = 120, 600, 25, 16 * 1024
GIT_SECONDS = 600.0
TAIL = 2000
SMALL = 1 << 20
HEX = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")
REF = re.compile(r"refs/[A-Za-z0-9._/-]+")
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
LINE_BREAKS = "\x85\u2028\u2029"


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

    override = _overridden()
    if override:
        root = Path(os.path.expanduser(override)).resolve()
        if not (root / INDEX).is_file():
            raise _not_configured(f"{ENVIRONMENT} names {root}, which holds no {INDEX}", path)
        return root
    link = _link()
    if not os.path.lexists(link):
        raise _not_configured(
            f"no clone configured: {ENVIRONMENT} is unset and {LINK_TEXT} does not exist", path
        )
    root = link.resolve()
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

    dot = root / ".git"
    if dot.is_symlink():
        return None
    if dot.is_dir():
        return dot
    first = (_small_text(dot) or "").strip().splitlines()[:1]
    if first and first[0].startswith("gitdir:"):
        target = (root / first[0][len("gitdir:") :].strip()).resolve()
        return target if target.is_dir() else None
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
        with path.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            handle.seek(max(0, handle.tell() - 8192))
            lines = handle.read().decode("utf-8", "replace").splitlines()
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


def version(root: Path) -> str:
    """`<12 hex of the commit> (<YYYY-MM-DD>)`, each `unknown` where the `.git` files lack it."""

    git_dir = _git_dir(root)
    commit = _commit(git_dir) if git_dir else None
    day = _moved_on(git_dir) if git_dir else None
    return f"{commit[:12] if commit else 'unknown'} ({day or 'unknown'})"


# --- Print -------------------------------------------------------------------------------------


def show(path: str) -> int:
    root = clone_root(path)
    try:
        data = paths.read_bounded(root, path)
    except paths.PathError as error:
        raise Refusal(f"{path}: {_why_not(root, path, str(error))}") from error
    sys.stdout.write(f"research: {path} @ {version(root)}\n")
    sys.stdout.write(data.decode("utf-8", "replace"))
    return 0


def _why_not(root: Path, path: str, message: str) -> str:
    if not message.startswith("not a readable file") or not paths.admits(path):
        return message
    target = root / path
    if target.is_dir():
        return "a folder, not a document"
    if not target.exists():
        return f"not in the clone; {INDEX} lists every document and MOVED.md every path that moved"
    return message


# --- Clone and pull: the networked acts --------------------------------------------------------


def _run_git(arguments: list[str]) -> str | None:
    """Run Git as an argument list, never through a shell; None on success, else why not."""

    try:
        done = subprocess.run(
            ["git", *arguments],
            env=git_environment({**os.environ, "GIT_TERMINAL_PROMPT": "0"}),
            capture_output=True,
            text=True,
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
    return f"git exited {done.returncode}\n{output[-TAIL:]}".strip()


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
    if os.path.lexists(link) and not link.is_symlink():
        raise Refusal(f"clone: {LINK_TEXT} exists and is not a symlink; move it aside first")


def _point_link(destination: Path) -> None:
    link = _link()
    link.parent.mkdir(parents=True, exist_ok=True)
    staged = link.with_name(f"research.{os.getpid()}.outcomebound-stage")
    staged.unlink(missing_ok=True)
    try:
        staged.symlink_to(destination)
        os.replace(staged, link)
    finally:
        staged.unlink(missing_ok=True)


def clone(destination_text: str, accept: bool) -> int:
    destination = Path(os.path.abspath(os.path.expanduser(destination_text)))
    _check_destination(destination)
    arguments = ["clone", CLONE_URL, str(destination)]
    command = f"git {' '.join(arguments)}"
    print(f"{'runs' if accept else 'would run'}: {command}")
    if not accept:
        print(f"would link: {LINK_TEXT} -> {destination}")
        if _overridden():
            print(f"{ENVIRONMENT} is set and overrides the link: printing reads that folder")
        print("nothing cloned: pass --accept")
        return 0
    failure = _run_git(arguments)
    if failure is not None:
        raise Refusal(f"clone: {failure}\nthe link is left as it was")
    try:
        _point_link(destination)
    except OSError as error:
        raise Refusal(f"clone: cloned, but the link was not made: {error}") from error
    print(f"linked: {LINK_TEXT} -> {destination}")
    return 0


def pull(accept: bool) -> int:
    root = clone_root()
    if _git_dir(root) is None:
        raise Refusal(f"pull: {root} has no .git, so it is not a Git clone")
    arguments = ["-C", str(root), "pull", "--ff-only"]
    print(f"{'runs' if accept else 'would run'}: git {' '.join(arguments)}")
    if not accept:
        print("nothing pulled: pass --accept")
        return 0
    failure = _run_git(arguments)
    if failure is not None:
        raise Refusal(f"pull: {failure}")
    print(f"research: now at {version(root)}")
    return 0


# --- Ingest: a finding goes back ---------------------------------------------------------------


def _one_line(name: str, value: str) -> str:
    value = value.strip()
    if any(paths.is_control(char) or char in LINE_BREAKS for char in value):
        raise Refusal(f"ingest: {name} holds a line break or a control character")
    return value


def _bounded(name: str, value: str, longest: int) -> str:
    value = _one_line(name, value)
    if not value or len(value) > longest:
        raise Refusal(f"ingest: {name} must be 1 to {longest} characters")
    return value


def _checked_url(value: str) -> str:
    value = _one_line("url", value)
    try:
        parts = urlsplit(value)
        host = parts.hostname
    except ValueError:
        parts, host = None, None
    if (
        parts is None
        or not host
        or parts.scheme not in ("http", "https")
        or any(char.isspace() for char in value)
    ):
        raise Refusal("ingest: url must be http or https, with a host and no space")
    return value


def _checked_date(value: str | None) -> str:
    today = datetime.date.today()
    if value is None:
        return today.isoformat()
    value = _one_line("observed-on", value)
    try:
        day = datetime.date.fromisoformat(value) if DATE.fullmatch(value) else None
    except ValueError:
        day = None
    if day is None or day > today:
        raise Refusal("ingest: observed-on must be a real date, YYYY-MM-DD, not after today")
    return day.isoformat()


def _checked_quote(value: str | None) -> str:
    quoted = _one_line("quote", value or "")
    if len(quoted.split()) > QUOTE_WORDS:
        raise Refusal(f"ingest: quote must be at most {QUOTE_WORDS} words")
    return quoted


def finding(options: argparse.Namespace) -> dict[str, str]:
    """The finding `options` give, every field checked; each failure is one `Refusal`."""

    kind = _one_line("kind", options.kind)
    if kind not in KINDS:
        raise Refusal(f"ingest: kind must be one of {', '.join(KINDS)}")
    fields = {
        "kind": kind,
        "subject": _bounded("subject", options.subject, SUBJECT_MAX),
        "claim": _bounded("claim", options.claim, CLAIM_MAX),
        "url": _checked_url(options.url),
        "quote": _checked_quote(options.quote),
        "observed_on": _checked_date(options.observed_on),
        "corrects": _one_line("corrects", options.corrects or ""),
    }
    if kind == "correction" and not fields["corrects"]:
        raise Refusal("ingest: a correction needs --corrects: the path or evidence id it corrects")
    return {name: value for name, value in fields.items() if value}


def finding_bytes(fields: dict[str, str]) -> bytes:
    document = {"version": FORMAT_VERSION, **fields}
    data = (json.dumps(document, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode()
    if len(data) > FINDING_MAX:
        raise Refusal(f"ingest: the finding is larger than {FINDING_MAX // 1024} KiB")
    return data


def inbox_name(fields: dict[str, str]) -> str:
    digest = hashlib.sha256((fields["claim"] + fields["url"]).encode("utf-8")).hexdigest()
    return f"{fields['observed_on'].replace('-', '')}-{digest[:8]}.json"


def issue_link(fields: dict[str, str]) -> str:
    order = ("kind", "subject", "claim", "url", "quote", "observed_on", "corrects")
    pairs = [(name, fields[name]) for name in order if fields.get(name)]
    return f"{ISSUE_FORM}&{urlencode(pairs, quote_via=quote)}"


def _project(given: Path | None) -> Path:
    if given is not None:
        if not given.is_dir():
            raise Refusal(f"ingest: {given} is not a directory")
        return given.resolve()
    here = Path.cwd().resolve()
    for folder in (here, *here.parents):
        if (folder / ".git").exists():
            return folder
    raise Refusal("ingest: not inside a Git work tree; name the project with --project DIR")


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
    print(f"{'unchanged' if present is not None else 'wrote'}: {project / relative}")
    print(
        "the issue link sends the finding now; the file, once your project commits it, waits "
        "for the research maintainer's collect pass"
    )
    return 0


# --- The command line --------------------------------------------------------------------------

DESCRIPTION = f"""\
Read the research repository, and send a finding back to it.

  outcomebound research [PATH]     print PATH (default {INDEX}) from the clone, its first line
                                   `research: PATH @ <commit> (<date>)`; with no clone
                                   configured, name the public link and exit 3
  outcomebound research clone DESTINATION [--accept]
                                   git clone it into DESTINATION, outside any project, and
                                   link {LINK_TEXT} to it
  outcomebound research pull [--accept]
                                   git pull --ff-only in the clone
  outcomebound research ingest ... write a finding under {INBOX}/
                                   and print the prefilled issue link (ingest --help)

The clone is the folder {ENVIRONMENT} names when that is set, else {LINK_TEXT}.
Printing reads files and runs nothing, Git included. clone and pull reach the network and
change nothing without --accept.
Exit 0: done or previewed; 1: refused, or Git failed; 2: usage; 3: no clone configured."""
INGEST_DESCRIPTION = f"""\
Write one finding under {INBOX}/ in the project, and print the link that opens the research
repository's finding issue form with it filled in. The engine opens no connection: open the
link to send the finding now; the file waits for the research maintainer's collect pass.

Write the claim in your own words; name no project, client or person. A finding is refused
when a value holds a line break or a control character, the subject is not 1 to {SUBJECT_MAX}
characters, the claim not 1 to {CLAIM_MAX}, the url not http or https, the quote more than
{QUOTE_WORDS} words, the date not real or after today, or a correction names nothing it
corrects."""


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


if __name__ == "__main__":
    raise SystemExit(main())
