"""The `publish` verb: the exact `gh` commands that publish a breakdown of drafts.

What this module decides: which drafts may be published (those `check` reports
no ERROR about), the order that lets each relation name an issue that already
exists, what an issue body is (the draft without its `# <title>` line and
without the `blocked-by` and `parent` lines of its block, which the tracker
holds natively, a `discovered-from` naming a sibling rewritten to its issue
number), which labels each issue carries, and the POSIX shell script that does
all of it with `gh`.

What it does not decide: anything a draft says (`tickets_draft`, `tickets_model`)
or whether it is fit to publish (`tickets_check`). **It runs nothing, writes
nothing and holds no credential.** It returns the script as text; `gh` runs it
under the login of whoever runs it. Whether an agent may run it is the
declaration's `writes` grant, which the script's header names: without one, a
person reviews it and runs it. A draft's name in its prose is left as written,
because a word is not decidably a reference to a sibling.
"""

from __future__ import annotations

import argparse
import shlex
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from outcomebound_tools.tickets_check import check_loaded
from outcomebound_tools.tickets_declaration import DECLARATION_PATH, Declaration
from outcomebound_tools.tickets_draft import read_draft
from outcomebound_tools.tickets_model import Ticket, parse_block
from outcomebound_tools.tickets_report import Level, Refusal

__all__ = ["publish"]

_REFUSED = "PUBLISH_REFUSED"
_BOM = "﻿"
# The block keys the tracker holds natively, which a published body does not carry.
_NATIVE = ("blocked-by:", "parent:")
_DISCOVERED = "discovered-from:"


@dataclass(frozen=True, slots=True)
class _Ref:
    """The issue number of a sibling draft, known only once the script created it."""

    variable: str


# A body is literal text and sibling numbers, in order.
_Part = str | _Ref


@dataclass(frozen=True, slots=True)
class _Draft:
    """One draft to publish: the ticket as read, where it came from, and its body."""

    ticket: Ticket
    path: str
    text: str


# --- what may be published ---------------------------------------------------------


def _refuse_findings(root: Path, declaration: Declaration, drafts: Sequence[str]) -> None:
    """Every ERROR `check` reports about these drafts stops the publish."""

    report = check_loaded(root, declaration, argparse.Namespace(input=None, draft=list(drafts)))
    found = [
        item for result in report.tickets for item in result.messages if item.level is Level.ERROR
    ] + [item for item in report.messages if item.level is Level.ERROR]
    if not found:
        return
    said = "; ".join(f"{item.ticket or '-'} {item.code}: {item.text}" for item in found)
    raise Refusal(
        _REFUSED,
        f"`check --draft` reports an error on these drafts, so no script is printed — {said}; "
        "fix what `check` reports and run publish again",
    )


def _read(paths: Sequence[str], declaration: Declaration) -> list[_Draft]:
    """Each draft, read through the one draft reader; `check` has already judged them."""

    drafts: list[_Draft] = []
    for path in paths:
        ticket, _ = read_draft(path, declaration)
        if ticket is None:
            raise Refusal(_REFUSED, f"no draft could be read at {path}")
        text = Path(path).read_text(encoding="utf-8")
        drafts.append(_Draft(ticket, Path(path).as_posix(), text.removeprefix(_BOM)))
    return drafts


# --- the order ---------------------------------------------------------------------


def _siblings(ticket: Ticket, ids: Mapping[str, int]) -> list[str]:
    """The drafts of this run that this one names, each of which must exist first."""

    named = [*ticket.blocked_by, ticket.parent, ticket.discovered_from]
    return [entry for entry in named if entry in ids and entry != ticket.id]


def _ordered(drafts: Sequence[_Draft]) -> list[_Draft]:
    """The drafts in an order where each sibling a draft names comes before it.

    The given order is kept wherever the relations allow. `check` refuses a knot
    of `blocked-by` and `parent`; one that runs through `discovered-from` is
    refused here, because no order creates its first issue.
    """

    ids = {draft.ticket.id: index for index, draft in enumerate(drafts)}
    placed: list[_Draft] = []
    done: set[str] = set()
    waiting = list(drafts)
    while waiting:
        ready = next((d for d in waiting if all(s in done for s in _siblings(d.ticket, ids))), None)
        if ready is None:
            knot = ", ".join(draft.ticket.id for draft in waiting)
            raise Refusal(
                _REFUSED,
                f"the drafts {knot} name one another in a ring through `discovered-from`, so "
                "no order creates the first of them; drop one of those entries",
            )
        placed.append(ready)
        done.add(ready.ticket.id)
        waiting.remove(ready)
    return placed


# --- the body ----------------------------------------------------------------------


def _title_end(text: str) -> int:
    """Where the draft's `# <title>` line, its first line that is not blank, ends."""

    offset = 0
    for line in text.split("\n"):
        if line.strip():
            return offset + len(line)
        offset += len(line) + 1
    return len(text)


def _block_parts(block: str, variables: Mapping[str, str]) -> list[_Part]:
    """The block without the keys the tracker holds, `discovered-from` a sibling's number."""

    parts: list[_Part] = []
    for line in block.splitlines(keepends=True):
        stripped = line.strip()
        if stripped.startswith(_NATIVE):
            continue
        if stripped.startswith(_DISCOVERED):
            named = stripped[len(_DISCOVERED) :].strip()
            if named in variables:
                ending = line[len(line.rstrip("\r\n")) :]
                parts += [f"{_DISCOVERED} #", _Ref(variables[named]), ending]
                continue
        parts.append(line)
    return parts


def _body(draft: _Draft, variables: Mapping[str, str]) -> list[_Part]:
    """The issue body: the draft after its title line, its block as the tracker reads it."""

    text = draft.text
    fields, _ = parse_block(text)
    start = _title_end(text)
    head = text[start : fields.begin].lstrip("\r\n")
    parts: list[_Part] = [head, *_block_parts(text[fields.begin : fields.end], variables)]
    parts.append(text[fields.end :])
    merged: list[_Part] = []
    for part in parts:
        if isinstance(part, str) and merged and isinstance(merged[-1], str):
            merged[-1] += part
        elif part != "":
            merged.append(part)
    return merged


# --- the script --------------------------------------------------------------------


def _issue(entry: str, variables: Mapping[str, str]) -> str:
    """One relation as `gh` takes it: a sibling's number, a number, or an issue URL."""

    if entry in variables:
        return f'"${variables[entry]}"'
    owner_repo, _, number = entry.partition("#")
    if not owner_repo:
        return number
    return shlex.quote(f"https://github.com/{owner_repo}/issues/{number}")


def _labels(ticket: Ticket, declaration: Declaration) -> list[str]:
    """The acceptance label, and the label that says one thing with the block's hold."""

    held = {"yes": declaration.human_label, "requested": declaration.request_label}
    extra = held.get(ticket.human_only, "")
    return [declaration.label, *([extra] if extra else [])]


def _printed(parts: Sequence[_Part]) -> str:
    """The commands that print a body: each literal part quoted whole, so no byte of
    it is read by the shell, and each sibling's number from its variable."""

    return "; ".join(
        f"printf '%s' \"${part.variable}\""
        if isinstance(part, _Ref)
        else f"printf '%s' {shlex.quote(part)}"
        for part in parts
    )


def _create(
    draft: _Draft, variable: str, declaration: Declaration, variables: Mapping[str, str]
) -> str:
    """The lines that create one issue and keep its number in `variable`."""

    ticket = draft.ticket
    flags = [f"--title {shlex.quote(ticket.title)}"]
    flags += [f"--label {shlex.quote(label)}" for label in _labels(ticket, declaration)]
    if ticket.parent:
        flags.append(f"--parent {_issue(ticket.parent, variables)}")
    if ticket.blocked_by:
        joined = ",".join(_issue(entry, variables) for entry in ticket.blocked_by)
        flags.append(f"--blocked-by {joined}")
    body = _printed(_body(draft, variables))
    return "\n".join(
        [
            f"# {_comment(draft.path)}",
            f'url=$( {{ {body}; }} | gh issue create --repo "$repo" {" ".join(flags)} '
            "--body-file - )",
            f'{variable}=$(ob_number "$url")',
            f'echo {shlex.quote(f"{draft.path} -> #")}"${variable}"',
        ]
    )


_HELPERS = """ob_number() {
  case $1 in
    */issues/*) ob_n=${1##*/} ;;
    *) ob_n= ;;
  esac
  case $ob_n in
    ''|*[!0-9]*) echo "publish: gh printed no issue URL: $1" >&2; exit 1 ;;
  esac
  printf '%s\\n' "$ob_n"
}"""

_RELATIONS_CHECK = """gh issue create --help | grep -q -- '--blocked-by' || {
  echo "publish: this gh has no --parent or --blocked-by on gh issue create; upgrade gh" >&2
  exit 1
}"""


def _comment(text: str) -> str:
    """Text safe on a comment line: a control character, a line end above all, would
    end the comment and leave the rest to the shell, so each becomes `?`."""

    return "".join(
        "?" if ord(character) < 32 or ord(character) == 127 else character for character in text
    )


def _grant(declaration: Declaration) -> str:
    if declaration.writes is None:
        return (
            f"# {DECLARATION_PATH} records no `writes` grant: a person reviews this script "
            "and runs it."
        )
    return (
        f"# Tracker writes granted by {_comment(declaration.writes.granted_by)} on "
        f"{_comment(declaration.writes.on)} in {DECLARATION_PATH}."
    )


def _script(drafts: Sequence[_Draft], declaration: Declaration) -> str:
    variables = {draft.ticket.id: f"ob_{index}" for index, draft in enumerate(drafts, 1)}
    relations = any(draft.ticket.parent or draft.ticket.blocked_by for draft in drafts)
    lines = [
        "#!/bin/sh",
        f"# Publishes {len(drafts)} draft(s) to {_comment(declaration.repo)} as tickets, "
        "in an order where each relation names an issue that exists.",
        "# Printed by `outcomebound tickets publish`, which runs nothing and holds no "
        "credential; gh runs under your own login.",
        _grant(declaration),
        "set -eu",
        f"repo={shlex.quote(declaration.repo)}",
        _HELPERS,
        *([_RELATIONS_CHECK] if relations else []),
        *(_create(draft, variables[draft.ticket.id], declaration, variables) for draft in drafts),
        'echo "publish: done; make a new export and run outcomebound tickets check on it"',
    ]
    return "\n".join(lines) + "\n"


# --- the seam ----------------------------------------------------------------------


def publish(target: Path, declaration: Declaration, options: argparse.Namespace) -> str:
    """The script that publishes the drafts `--draft` names, returned for `tickets.py`.

    `check` is asked first, about all of the drafts together, and any ERROR it
    reports is a refusal; then the drafts are ordered so that each relation names
    an issue the script has already created.
    """

    root = Path(target)
    paths = list(options.draft)
    _refuse_findings(root, declaration, paths)
    return _script(_ordered(_read(paths, declaration)), declaration)
