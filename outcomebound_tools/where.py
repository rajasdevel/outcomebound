"""`outcomebound where`: the work in flight in a project, read from what the project keeps
(`docs/specs/lifecycle/design.md`, "Where the work stands"; `schemas/where.schema.json`).

What this module decides: which sources it reads (Git, `gh` where it answers, the ticket export,
validation results, review files, decision briefs and the newest handoff), the verdict of each line
(OPEN, STALE, CLEAR, NOTE, UNVERIFIED), which briefs and reviews are named (the ones something in
flight points to) and which are only counted, and the one table from a kind of open item to the
shipped skill that serves its next step. Each source is read by the module that owns it; this one
holds no second copy of a reader.

What it does not decide: whether a line is current beyond the moment it was read, what to do next,
or any stage of a project's route: the table is keyed by the kind of open item, never by a stage.
It writes nothing and starts no process but `git` and, where it is on PATH and answers, `gh`.
Exits: 0 once a report is printed, whatever its verdicts; 2 for a usage error.
Standard library only.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from outcomebound_tools import (
    adopt,
    adopt_worktrees,
    brief_lookup,
    home,
    programs,
    review_check,
    review_since,
    size,
    textio,
    validation,
    validation_record,
)
from outcomebound_tools.gitenv import git_environment
from outcomebound_tools.tickets_declaration import Declaration, load_declaration
from outcomebound_tools.tickets_model import Ticket
from outcomebound_tools.tickets_report import EngineError, PlanningError, Refusal
from outcomebound_tools.tickets_store import read_store

VERSION = 1
OPEN, STALE, CLEAR, NOTE, UNVERIFIED = "OPEN", "STALE", "CLEAR", "NOTE", "UNVERIFIED"
VERDICTS = (OPEN, STALE, CLEAR, NOTE, UNVERIFIED)
# The order of reading. It says nothing about the order of work.
KINDS = ("git", "worktree", "pr", "ticket", "validation", "review", "brief", "handoff")
EXPORT = "issues.json"
GH_SECONDS = 30
PR_LIMIT = 1000
SEE = textio.visible

# The one table: the kind of open item to the shipped skill that serves its next step. It holds
# kinds of item found in files, never a stage of a route, and no line is derived from another.
NEXT_SKILL = {
    "unanswered-brief": "decision-brief",
    "failed-claim": "diagnose",
    "changed-claim": "tests-worth-keeping",
    "review-open": "review-findings",
    "open-pull-request": "land-change",
    "ready-ticket": "hand-off-tickets",
}
LIMITS = (
    "that a line is current beyond the moment it was read: an export, a result and a handoff are "
    "each as old as their line says",
    "that a pull request has passed CI or been reviewed",
    "that a ticket has no branch or worktree under way: no line joins a ticket to a branch",
    "that a brief with no Decided line is open outside the briefs an open ticket or the newest "
    "handoff names",
    "that a review of other commits holds no finding",
    "what the person intends next, or how long anything will take",
)


@dataclass(frozen=True)
class Item:
    kind: str
    source: str
    verdict: str
    text: str
    subject: str | None = None
    next: str | None = None


def _item(
    kind: str,
    source: str,
    verdict: str,
    text: str,
    *,
    subject: str | None = None,
    item: str | None = None,
) -> Item:
    """One line; `item` is the kind of open item whose row of `NEXT_SKILL` names its skill."""

    return Item(kind, source, verdict, text, subject, NEXT_SKILL[item] if item else None)


def _age(seconds: float) -> str:
    minutes = int(max(seconds, 0) // 60)
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    return f"{hours}h" if hours < 48 else f"{hours // 24}d"


def _git(root: Path, *arguments: str) -> str | None:
    """The text of one read-only Git command, or None where it fails."""

    status, output, _ = size._git(root, *arguments)
    return output.decode("utf-8", "replace").strip() if status == 0 else None


def _dirty(root: Path) -> int:
    """How many paths differ from HEAD or are untracked and not ignored. The plumbing, since the
    porcelain refreshes the index."""

    tracked = size._git_ok(root, "diff-index", "--name-only", "-z", "--no-renames", "HEAD", "--")
    untracked = size._git_ok(root, "ls-files", "--others", "--exclude-standard", "-z")
    return len({name for name in (tracked + untracked).split(b"\0") if name})


def _shown(path: Path, top: Path) -> str:
    """`path` relative to the work tree; a file of the main checkout reads `main checkout: <path>`."""

    for base, prefix in ((top, ""), (brief_lookup.main_checkout(top), "main checkout: ")):
        if base is not None:
            try:
                return prefix + path.relative_to(base).as_posix()
            except ValueError:
                pass
    return str(path)


# --- git and worktrees ----------------------------------------------------------------


def _uncommitted(root: Path) -> str:
    try:
        return f"{_dirty(root)} uncommitted path(s)"
    except size.SizeError as error:
        return f"uncommitted paths UNVERIFIED: {textio.plain(str(error))}"


def _branch_line(top: Path) -> Item:
    branch = _git(top, "symbolic-ref", "-q", "--short", "HEAD")
    detached = f"detached at {_git(top, 'rev-parse', '--short', 'HEAD')}"
    parts = [f"branch {SEE(branch)}" if branch else detached]
    upstream = _git(top, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}")
    counts = _git(top, "rev-list", "--left-right", "--count", "HEAD...@{upstream}")
    if upstream and counts:
        ahead, behind = counts.split()
        parts.append(f"{ahead} ahead and {behind} behind {SEE(upstream)}")
    else:
        parts.append("no upstream")
    parts.append(_uncommitted(top))
    return _item("git", "git", NOTE, ", ".join(parts), subject=branch)


def _git_items(top: Path, inside: bool) -> list[Item]:
    if not inside:
        text = "the folder is not in a Git work tree, or git is absent"
        return [_item("git", "git", UNVERIFIED, text)]
    items = [_branch_line(top)]
    source = "git worktree list"
    listed = _git(top, "worktree", "list", "--porcelain")
    if listed is None:
        return [*items, _item("worktree", source, UNVERIFIED, "Git did not list the worktrees")]
    here, clean = top.resolve(), []
    for tree in adopt_worktrees.parse(listed):
        if tree.path.resolve() == here:
            continue
        label = f"worktree {SEE(str(tree.path))}, branch {SEE(tree.branch)}"
        if not tree.path.is_dir():
            items.append(_item("worktree", source, UNVERIFIED, f"{label}: the folder is gone"))
        elif (state := _uncommitted(tree.path)) != "0 uncommitted path(s)":
            items.append(_item("worktree", source, NOTE, f"{label}: {state}", subject=tree.branch))
        else:
            clean.append(SEE(tree.branch))
    if clean:
        text = f"{len(clean)} other worktree(s) with nothing uncommitted: {', '.join(clean)}"
        items.append(_item("worktree", source, NOTE, text))
    older = adopt_worktrees.lines(top, listed, adopt.engine_version(home.ROOT))
    if older:
        text = (
            f"{len(older)} worktree(s) have an install older than the engine; "
            "`outcomebound adopt . --check` names each"
        )
        items.append(_item("worktree", "adopt_worktrees", NOTE, text))
    return items


# --- pull requests ----------------------------------------------------------------------


def _pr_items(top: Path, offline: bool) -> list[Item]:
    source = "gh pr list"
    if offline:
        return [_item("pr", source, UNVERIFIED, "--offline: gh was not run")]
    gh = programs.find("gh")
    if gh is None:
        return [_item("pr", source, UNVERIFIED, "gh is not on PATH")]
    fields = "number,title,headRefName,isDraft,reviewDecision"
    try:
        done = subprocess.run(
            [gh, "pr", "list", "--state", "open", "--limit", str(PR_LIMIT), "--json", fields],
            cwd=top,
            capture_output=True,
            stdin=subprocess.DEVNULL,
            timeout=GH_SECONDS,
            check=False,
            env={**git_environment(), "GH_PROMPT_DISABLED": "1", "GH_NO_UPDATE_NOTIFIER": "1"},
        )
        listed = json.loads(done.stdout) if done.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired, ValueError) as error:
        return [_item("pr", source, UNVERIFIED, f"gh did not answer: {SEE(type(error).__name__)}")]
    if not isinstance(listed, list):
        reason = done.stderr.decode("utf-8", "replace").strip().splitlines()
        return [
            _item(
                "pr",
                source,
                UNVERIFIED,
                f"gh did not list: {SEE(reason[0] if reason else 'no message')}",
            )
        ]
    if not listed:
        return [_item("pr", source, CLEAR, "no open pull request")]
    found = []
    here = _git(top, "symbolic-ref", "-q", "--short", "HEAD")
    prs = [p for p in listed if isinstance(p, dict)]
    prs.sort(key=lambda p: (p.get("headRefName") != here, p.get("number", 0)))
    for pr in prs:
        state = "draft" if pr.get("isDraft") else "ready"
        review = pr.get("reviewDecision") or "no review decision"
        title = textio.quote(str(pr.get("title", "")))
        mine = ", this branch's" if here and pr.get("headRefName") == here else ""
        text = (
            f"{title} (branch {SEE(str(pr.get('headRefName', '')))}, {state}, "
            f"{SEE(str(review))}{mine})"
        )
        found.append(
            _item(
                "pr", source, OPEN, text, subject=f"#{pr.get('number')}", item="open-pull-request"
            )
        )
    if len(listed) >= PR_LIMIT:
        text = f"gh was asked for {PR_LIMIT} pull requests and returned that many: more may be open"
        found.append(_item("pr", source, UNVERIFIED, text))
    return found


# --- tickets ----------------------------------------------------------------------------


@dataclass(frozen=True)
class Store:
    """What the ticket export gave: the open tickets and the ids of the others, or the line that
    says it could not be read. `declaration` is None where the project declares no store."""

    declaration: Declaration | None
    source: str = "tickets"
    stamp: str = ""
    age_seconds: int | None = None
    open: tuple[Ticket, ...] = ()
    closed: frozenset[str] = frozenset()
    failure: Item | None = None


def _default_export(top: Path) -> Path:
    """`issues.json` at the work tree's root, else at the main checkout's (an ignored file does
    not reach a linked worktree)."""

    main = brief_lookup.main_checkout(top)
    here = top / EXPORT
    return (
        main / EXPORT
        if not here.is_file() and main is not None and (main / EXPORT).is_file()
        else here
    )


def _read_tickets(top: Path, export: Path | None) -> Store:
    try:
        declaration = load_declaration(top)
    except Refusal as stop:
        if stop.code == "DECLARATION_MISSING":
            text = "no ticket store is declared in .outcomebound/tickets.json"
            return Store(None, failure=_item("ticket", "tickets", NOTE, text))
        return Store(
            None, failure=_item("ticket", "tickets", UNVERIFIED, f"{stop.code}: {SEE(stop.text)}")
        )
    path = export or _default_export(top)
    source = _shown(path, top)
    if not path.is_file():
        text = (
            f"no export at {SEE(source)}; `outcomebound tickets export` prints the command "
            "that makes one"
        )
        return Store(declaration, failure=_item("ticket", "tickets", UNVERIFIED, text))
    try:
        result = read_store(top, declaration, str(path))
    except (Refusal, PlanningError) as stop:
        return Store(
            declaration,
            failure=_item("ticket", source, UNVERIFIED, f"{stop.code}: {SEE(stop.text)}"),
        )
    except EngineError as error:
        return Store(declaration, failure=_item("ticket", source, UNVERIFIED, SEE(str(error))))
    age = result.input.age_seconds if result.input else None
    stamp = f"export written {_age(age)} ago" if age is not None else "export age unknown"
    return Store(
        declaration,
        source,
        stamp,
        age,
        tuple(t for t in result.tickets if t.state == "open"),
        frozenset(t.id for t in result.tickets if t.state != "open"),
    )


def _ticket_items(store: Store, status: dict[str, str]) -> list[Item]:
    """The ticket lines; `status` maps a brief id (case folded) to ANSWERED or UNANSWERED."""

    if store.failure is not None:
        return [store.failure]
    source = store.source
    items = [_item("ticket", source, NOTE, f"{len(store.open)} open ticket(s); {store.stamp}")]
    for ticket in store.open:
        label = textio.quote(ticket.title)
        waits = [w for w in ticket.waits_on if status.get(w.casefold()) != "ANSWERED"]
        blockers = [b for b in ticket.blocked_by if b not in store.closed]
        if ticket.hold != "no":
            text, ready = f"{label} is held for a person ({SEE(ticket.hold)})", False
        elif waits:
            text, ready = (
                f"{label} waits on brief(s) {SEE(', '.join(waits))} (an answer in a ticket comment "
                "is not read)",
                False,
            )
        elif blockers:
            text, ready = (
                f"{label} is blocked by {SEE(', '.join(blockers))}, not shown closed",
                False,
            )
        else:
            named = (
                f"; waits-on {SEE(', '.join(ticket.waits_on))} is answered but still named"
                if ticket.waits_on
                else ""
            )
            text, ready = f"{label} is ready: no hold, no open blocker{named}", True
        if ready:
            items.append(
                _item("ticket", source, OPEN, text, subject=ticket.id, item="ready-ticket")
            )
        else:
            items.append(_item("ticket", source, NOTE, text, subject=ticket.id))
    if store.open:
        text = "whether a ticket is claimed: the pinned export carries no assignee or comment"
        items.append(_item("ticket", source, UNVERIFIED, text))
    return items


# --- validation -------------------------------------------------------------------------


def _validation_items(
    top: Path, plans: Sequence[Path], declaration: Declaration | None, cwd: str | None
) -> list[Item]:
    named = list(plans)
    if (
        not named
        and declaration is not None
        and declaration.claims
        and (top / declaration.claims).is_file()
    ):
        named = [top / declaration.claims]
    if not named:
        return [
            _item(
                "validation",
                "validation status",
                UNVERIFIED,
                "no validation plan: name one with --plan",
            )
        ]
    items = []
    for path in named:
        source = _shown(path, top)
        try:
            states = validation.claim_states(validation.load_plan(path, cwd_override=cwd))
        except (validation.PlanError, OSError) as error:
            items.append(
                _item(
                    "validation",
                    source,
                    UNVERIFIED,
                    f"the plan could not be read: {SEE(str(error))}",
                )
            )
            continue
        shown = []
        for state in states:
            name = state.claim.name
            if state.verdict == validation.FAIL:
                shown.append(
                    _item(
                        "validation",
                        source,
                        OPEN,
                        f"last result FAIL; {SEE(state.text)}",
                        subject=name,
                        item="failed-claim",
                    )
                )
            elif state.state == validation_record.CHANGED:
                shown.append(
                    _item(
                        "validation",
                        source,
                        STALE,
                        SEE(state.text),
                        subject=name,
                        item="changed-claim",
                    )
                )
            elif state.verdict is not None and (
                state.state != validation_record.CURRENT or state.verdict != validation.PASSED
            ):
                shown.append(_item("validation", source, UNVERIFIED, SEE(state.text), subject=name))
        counts = {
            s: sum(1 for st in states if st.state == s)
            for s in (validation_record.CURRENT, validation_record.CHANGED, UNVERIFIED)
        }
        unkept = sum(1 for st in states if st.verdict is None)
        clear = counts["CURRENT"] == len(states) and not shown
        text = (
            f"{len(states)} claim(s): "
            + ", ".join(f"{n} {s}" for s, n in counts.items())
            + f" ({unkept} with no result kept)"
        )
        items.append(_item("validation", source, CLEAR if clear else NOTE, text))
        items += shown
    return items


# --- reviews, briefs and the handoff ----------------------------------------------------


def _roots(top: Path, name: str) -> list[Path]:
    return [root for root in brief_lookup.default_roots(top) if root.name == name]


def _review_items(top: Path, base_ref: str | None) -> tuple[list[Item], dict[str, str] | None]:
    """The review lines, and the base that told which reviews concern this branch."""

    roots = _roots(top, "work")
    swept = [review_check.sweep(root) for root in roots]
    files = [(path, found, s.reviewed.get(path)) for s in swept for path, found in s.files]
    items = []
    tied: list[tuple[str, str]] = []
    base = None
    try:
        base = size.resolve_base(top, base_ref)
        branch = set((_git(top, "rev-list", f"{base['commit']}..HEAD") or "").split())
    except size.SizeError as error:
        branch = set()
        items.append(
            _item(
                "review",
                "review since",
                UNVERIFIED,
                "no base tells which reviews concern this branch "
                f"({SEE(textio.plain(str(error)))}); only open findings are listed",
            )
        )
    others = 0
    for path, found, ref in files:
        shown = SEE(_shown(Path(path), top))
        if review_check.verdict(found) == review_check.FAIL:
            codes = sorted({f.code for f in found if f.verdict == review_check.FAIL})
            items.append(_item("review", shown, OPEN, f"{', '.join(codes)}", item="review-open"))
        elif ref and not review_since._moving(top, ref) and size._commit_of(top, ref) in branch:
            tied.append((path, shown))
        else:
            others += 1
    for path, shown in tied:
        report = review_since.build(Path(path), None, top)
        if report["result"] == "UNVERIFIED":
            items.append(_item("review", shown, UNVERIFIED, SEE(report["reason"])))
        elif report["files"]:
            names = ", ".join(SEE(f["path"]) for f in report["files"][:5])
            more = "" if len(report["files"]) <= 5 else f" and {len(report['files']) - 5} more"
            text = (
                f"read {SEE(report['reviewed'])}; {len(report['files'])} file(s) differ now: "
                f"{names}{more} (whether to review again is the project's call)"
            )
            items.append(_item("review", shown, NOTE, text))
        else:
            items.append(
                _item(
                    "review",
                    shown,
                    CLEAR,
                    f"read {SEE(report['reviewed'])}; no tracked file differs now",
                )
            )
    unread = sum(len(s.unread) for s in swept)
    if others or unread or not roots:
        text = (
            f"{others} other review file(s) with every finding dispositioned, not tied to a fixed "
            "commit of this branch"
        )
        text += f"; {unread} file(s) not read" if unread else ""
        text += "" if roots else "; no .agents/work folder"
        items.append(_item("review", "review check", NOTE, text))
    return items, base


def _handoff(top: Path) -> tuple[Path | None, list[Item]]:
    found = []
    for root in _roots(top, "handoffs"):
        found += [(p.stat().st_mtime, p) for p in root.glob("*.md") if p.is_file()]
    if not found:
        return None, [_item("handoff", ".agents/handoffs", NOTE, "no handoff file")]
    mtime, path = max(found)
    since = _git(top, "rev-list", "--count", f"--since={int(mtime)}", "HEAD")
    commits = f"; {since} commit(s) on HEAD since" if since is not None else ""
    text = (
        f"newest handoff of the folder (it may belong to another task), written "
        f"{_age(time.time() - mtime)} ago{commits} by commit date, which a rebase moves; it is a "
        "claim, check its facts against the lines above"
    )
    return path, [_item("handoff", SEE(_shown(path, top)), NOTE, text)]


def _brief_items(
    top: Path, tickets: Sequence[Ticket], handoff: Path | None
) -> tuple[list[Item], dict[str, str]]:
    briefs, answers, _, unread, unreadable = brief_lookup.scan(brief_lookup.default_roots(top))
    answered = {a.id.casefold() for a in answers}
    wanted: dict[str, str] = {}
    for ticket in tickets:
        for brief_id in ticket.waits_on:
            wanted.setdefault(brief_id.casefold(), f"{ticket.id} waits on it")
    for brief in briefs:
        if handoff is not None and Path(brief.source) == handoff:
            wanted.setdefault(brief.id.casefold(), "defined in the newest handoff")
    items, status = [], {}
    for key, why in sorted(wanted.items()):
        found = [b for b in briefs if b.id.casefold() == key]
        if len(found) != 1:
            text = f"brief {SEE(key)} ({why}): " + (
                "no brief file defines it"
                if not found
                else f"{len(found)} briefs carry this id, so an answer cannot be told apart"
            )
            items.append(_item("brief", "brief lookup", UNVERIFIED, text, subject=key))
        elif key in answered:
            status[key] = "ANSWERED"
            if "waits" in why:
                items.append(
                    _item(
                        "brief",
                        SEE(_shown(Path(found[0].source), top)),
                        CLEAR,
                        f"{SEE(found[0].id)} is answered; {why}",
                        subject=found[0].id,
                    )
                )
        else:
            status[key] = "UNANSWERED"
            where = SEE(_shown(Path(found[0].source), top))
            items.append(
                _item(
                    "brief",
                    where,
                    OPEN,
                    f"{textio.quote(found[0].heading)} has no Decided line ({why})",
                    subject=found[0].id,
                    item="unanswered-brief",
                )
            )
    rest = sum(
        1 for b in briefs if b.id.casefold() not in wanted and b.id.casefold() not in answered
    )
    if rest or unread or unreadable:
        text = (
            f"{rest} other brief heading(s) have no Decided line and are not listed: an answer "
            "recorded before that form shows as unanswered"
        )
        text += (
            f"; {len(unread) + len(unreadable)} path(s) not read" if unread or unreadable else ""
        )
        items.append(_item("brief", "brief lookup", NOTE, text))
    return items, status


# --- the report -------------------------------------------------------------------------


def build(
    top: Path,
    *,
    export: Path | None,
    plans: Sequence[Path],
    offline: bool,
    base: str | None = None,
    cwd: str | None = None,
) -> dict[str, Any]:
    inside = _git(top, "rev-parse", "--show-toplevel") is not None
    no_tree = "no Git work tree"
    store = _read_tickets(top, export)
    if inside:
        handoff, handoff_items = _handoff(top)
        review_items, base_used = _review_items(top, base)
    else:
        handoff, handoff_items = None, [_item("handoff", ".agents/handoffs", UNVERIFIED, no_tree)]
        review_items, base_used = [_item("review", "review check", UNVERIFIED, no_tree)], None
    brief_items, status = _brief_items(top, store.open, handoff)
    everything = [
        *_git_items(top, inside),
        *(_pr_items(top, offline) if inside else [_item("pr", "gh pr list", UNVERIFIED, no_tree)]),
        *_ticket_items(store, status),
        *_validation_items(top, plans, store.declaration, cwd),
        *review_items,
        *brief_items,
        *handoff_items,
    ]
    everything.sort(key=lambda item: KINDS.index(item.kind))
    return {
        "version": VERSION,
        "items": [
            {
                key: value
                for key, value in (
                    ("kind", i.kind),
                    ("source", i.source),
                    ("subject", i.subject),
                    ("verdict", i.verdict),
                    ("text", i.text),
                    ("next", i.next),
                )
                if value is not None
            }
            for i in everything
        ],
        "counts": {v: sum(1 for i in everything if i.verdict == v) for v in VERDICTS},
        "read": {
            "base": base_used,
            "export": None
            if store.failure is not None
            else {"source": store.source, "age_seconds": store.age_seconds},
            "searched": [str(root) for root in brief_lookup.default_roots(top)],
        },
        "does_not_establish": list(LIMITS),
    }


def render_text(report: dict[str, Any]) -> str:
    counts = ", ".join(f"{n} {v}" for v, n in report["counts"].items() if n)
    lines = [
        f"where: {len(report['items'])} line(s): {counts or 'none'} (a report; it decides nothing)"
    ]
    for item in report["items"]:
        subject = f" {SEE(item['subject'])}" if "subject" in item else ""
        follow = f"; next: {item['next']}" if "next" in item else ""
        lines.append(
            f"{item['verdict']:<11} {item['kind']}{subject}: {item['text']} "
            f"[{SEE(item['source'])}]{follow}"
        )
    lines.append("Does not establish: " + "; ".join(report["does_not_establish"]) + ".")
    return "\n".join(lines) + "\n"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="outcomebound where",
        description=(
            "Print the work in flight in this project: one line for each item, with the source "
            "it was read from and a verdict (OPEN, STALE, CLEAR, NOTE, UNVERIFIED), and for an "
            "unfinished item the shipped skill that serves its next step. It reads Git, `gh` "
            "where it answers, the ticket export, validation results, review files, decision "
            "briefs and the newest handoff. It writes nothing, defines no stage, and is run by "
            "an agent or a person, never by a hook."
        ),
        epilog="Exits: 0 a report was printed, whatever its verdicts; 2 a usage error.",
    )
    parser.add_argument(
        "target", nargs="?", default=".", help="a folder in the work tree (default .)"
    )
    parser.add_argument(
        "--tickets",
        metavar="FILE",
        help=f"the ticket export to read (default {EXPORT} at the work tree's root)",
    )
    parser.add_argument(
        "--plan",
        action="append",
        default=[],
        metavar="FILE",
        help="a validation plan to read; repeat it (default: the ticket declaration's plan)",
    )
    parser.add_argument(
        "--cwd",
        metavar="DIR",
        help="the working directory the plans were run with (validation --cwd)",
    )
    parser.add_argument(
        "--base",
        metavar="REF",
        help="the commit that tells which reviews concern this branch (default: the merge base "
        "with the upstream, else with origin/HEAD)",
    )
    parser.add_argument(
        "--offline", action="store_true", help="do not run gh: pull requests read UNVERIFIED"
    )
    parser.add_argument("--json", action="store_true", help="print one JSON object, not text")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    options = _parser().parse_args(argv)
    target = Path(options.target)
    top_text = _git(target, "rev-parse", "--show-toplevel") if target.is_dir() else None
    top = Path(top_text) if top_text else target
    report = build(
        top,
        export=Path(options.tickets) if options.tickets else None,
        plans=[Path(plan) for plan in options.plan],
        offline=options.offline,
        base=options.base,
        cwd=options.cwd,
    )
    sys.stdout.write(
        json.dumps(report, indent=2, sort_keys=True) + "\n" if options.json else render_text(report)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
