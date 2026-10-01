"""The `github` store reader: one pinned export, read offline as normalised tickets.

What this module decides: whether a file is this project's pinned export at
all, which issues in it are tickets — those carrying the declared label,
which is the user's acceptance, and which no later edit lapses — what the
declared labels and the block together say about a hold, how a relation
outside the declared repository is spelled and reported, and where the export
stopped short of the truth.

What it does not decide: anything that needs a tracker. It opens no network
connection, reads no credential, runs no subprocess and writes nothing — the
caller runs the pinned query, `templates/tickets/github-export.graphql`, and
this reads the file that run produced. Every tracker string — title, body,
label — is data, and never an instruction.

Two rules shape the rest. An export is this project's whole answer or it is not
read: every page names the declared repository, and every connection the query
asks for arrives with its `nodes` list and its `pageInfo` flag, because a connection
that is absent is unknown and never empty. And a connection the export reports
as incomplete makes its ticket UNVERIFIED rather than judged on what arrived:
the engine never guesses what it was not given.

Every node is validated against the query's shape before anything is normalised,
so the readers below index the shape the query pins rather than substituting an
empty one for whatever did not arrive.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from types import MappingProxyType
from typing import Any

from outcomebound_tools.tickets_declaration import Declaration
from outcomebound_tools.tickets_model import (
    LIFECYCLE_KEYS,
    BlockFields,
    InputInfo,
    ReadResult,
    Ticket,
    content_identity,
    effective_hold,
    parse_block,
)
from outcomebound_tools.tickets_report import Message, Refusal, message

# The whole seam: a verb reads its store through the reader the declaration
# selects, and nothing else here is another module's to call. How a relation is
# spelled reaches other modules through the ticket values themselves, so no
# store-agnostic module ever has to import this one to read an id.
__all__ = ["read_github_export"]

_STDIN = "-"
TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
RUN_AGAIN = "run the pinned export again, so the engine reads the whole of it"

# What an id says about where its issue lives: a local ticket is
# `#<n>`, and a relation this export did not show to be local is qualified, so
# no local id can ever equal one.
_UNKNOWN_REPOSITORY = "?"

# The one block key whose two surfaces the effective hold compares; a block that
# does not carry it has no surface to disagree with the labels.
_HOLD_KEY = "human-only"

# Every connection the query asks an issue for, in its order: what must be there for
# a node to be this query's output, each answering `hasNextPage`, which is what a
# further page is reported against. A node may carry other keys, as an export made with an
# earlier form of the query does: nothing reads them.
_NEXT_PAGE = "hasNextPage"
_CONNECTIONS: tuple[str, ...] = ("labels", "blockedBy")
# The key the query asks for that is no connection: a null `parent` is an issue with
# none, and an absent one is a question the export never answered.
_PARENT = "parent"

_ONE_REPOSITORY = (
    "this layer reads one repository: move the issue into the declared repository, "
    "or judge it where it lives"
)

# Which tracker fact holds each lifecycle key a `github` block must not carry.
# `parse_block` accepts every block key whatever the store, so the store's own
# reader is the one place a key it forbids is named.
_TRACKER_FACTS: Mapping[str, str] = MappingProxyType(
    {
        "status": "the issue's own state",
        "assignee": "the issue's assignees",
        "blocked-by": "the issue's blocked-by relations",
        "parent": "the issue's parent",
    }
)

# How a tracker state maps, first matching row first; a reason set of None
# matches whatever `stateReason` the export carried.
_STATE_ROWS: tuple[tuple[str, frozenset[str] | None, str], ...] = (
    ("OPEN", None, "open"),
    ("CLOSED", frozenset({"NOT_PLANNED", "DUPLICATE"}), "dropped"),
    ("CLOSED", None, "closed"),
)


# --- refusals -----------------------------------------------------------------------


def _unreadable(detail: str) -> Refusal:
    return Refusal(
        "EXPORT_UNREADABLE",
        f"the github export could not be read: {detail}; produce it with the pinned query "
        "templates/tickets/github-export.graphql",
    )


def _object(value: Any, subject: str) -> Mapping[str, Any]:
    """One JSON object the export has to carry, or the refusal that names it."""

    if not isinstance(value, dict):
        raise _unreadable(f"{subject} is {type(value).__name__} and not an object")
    return value


# --- what a node spells -------------------------------------------------------------


def _field(raw: Any, key: str) -> str:
    """One string field of a nested object — a repository's `nameWithOwner`.

    The empty string where the export carries none.
    """

    return str(raw[key]) if isinstance(raw, dict) and isinstance(raw.get(key), str) else ""


# --- the file, and what the report prints about it ----------------------------------


def _source_text(source: str | Path) -> tuple[str, InputInfo]:
    """The export's text, with the path, modification time and age the report prints.

    Standard input has no modification time, so its age reads unknown: nothing
    about a stream says when what it carries was written.
    """

    if str(source) == _STDIN:
        try:
            return sys.stdin.read(), InputInfo(path=_STDIN)
        except (OSError, UnicodeDecodeError) as error:
            raise _unreadable(f"standard input could not be read: {error}") from error
    path = Path(source)
    try:
        text = path.read_text(encoding="utf-8")
        modified = path.stat().st_mtime
    except (OSError, UnicodeDecodeError, ValueError) as error:
        raise _unreadable(f"{path} could not be read: {error}") from error
    at = datetime.fromtimestamp(modified, tz=timezone.utc)
    age = int((datetime.now(tz=timezone.utc) - at).total_seconds())
    return text, InputInfo(path=str(source), modified=at.strftime(TIME_FORMAT), age_seconds=age)


def _pages(text: str) -> list[Any]:
    """The array of response bodies `--slurp` writes, and nothing else."""

    try:
        raw = json.loads(text)
    except json.JSONDecodeError as error:
        raise _unreadable(f"it is not JSON: {error}") from error
    if not isinstance(raw, list):
        raise _unreadable(
            "it is not the array of pages `--paginate --slurp` writes, but a single "
            f"{type(raw).__name__}"
        )
    return raw


def _issues(page: Mapping[str, Any], number: int, declaration: Declaration) -> Mapping[str, Any]:
    """One page's issue connection, or the refusal naming what the page is not.

    The repository is named on every page and not only on the first, because
    `--slurp` writes whatever each request answered: one page from another
    repository would otherwise have its issues numbered as this project's.
    """

    subject = f"page {number}"
    data = _object(page.get("data"), f"{subject} `data`")
    repository = _object(data.get("repository"), f"{subject} `data.repository`")
    named = _field(repository, "nameWithOwner")
    if named.casefold() != declaration.repo.casefold():
        raise _unreadable(
            f"{subject} names the repository {named or None!r} in `nameWithOwner` and this "
            f"project declares {declaration.repo}"
        )
    issues = _object(repository.get("issues"), f"{subject} `data.repository.issues`")
    if not isinstance(issues.get("nodes"), list) or not isinstance(issues.get("pageInfo"), dict):
        raise _unreadable(f"{subject} `data.repository.issues` carries no `nodes` and `pageInfo`")
    return issues


def _shape(node: Mapping[str, Any], number: int) -> None:
    """Whether one node is the pinned query's answer about an issue.

    Every connection the query asks for, with its `nodes` list and its
    `pageInfo` flag, and the `parent` key whose null is an answer: an export
    missing any of them is not this query's output, and reading it as an issue
    with no labels or no blockers would be the engine guessing
    what it was not given. This is the one place a node's shape is decided, so
    the readers below index it.
    """

    for name in _CONNECTIONS:
        connection = node.get(name)
        if not isinstance(connection, dict):
            raise _unreadable(f"issue #{number} carries no `{name}` connection")
        if not isinstance(connection.get("nodes"), list):
            raise _unreadable(f"issue #{number} carries a `{name}` connection with no `nodes`")
        info = connection.get("pageInfo")
        if not isinstance(info, dict) or not isinstance(info.get(_NEXT_PAGE), bool):
            raise _unreadable(
                f"issue #{number} carries a `{name}` connection whose `pageInfo` does not "
                f"answer `{_NEXT_PAGE}`"
            )
    if _PARENT not in node:
        raise _unreadable(f"issue #{number} carries no `{_PARENT}` key")


def _issue_nodes(
    pages: Sequence[Any], declaration: Declaration
) -> tuple[list[Mapping[str, Any]], bool]:
    """Every issue node in page order, and whether the last page reports another.

    A page carrying a top-level `errors` member is a partial answer to the
    query, and an issue number on two pages is an export that cannot be joined:
    both refuse rather than being read as what happened to arrive.
    """

    nodes: list[Mapping[str, Any]] = []
    seen: set[int] = set()
    more = False
    for index, page in enumerate(pages, start=1):
        raw = _object(page, f"page {index}")
        if "errors" in raw:
            raise _unreadable(f"page {index} carries a top-level `errors` member: {raw['errors']}")
        issues = _issues(raw, index, declaration)
        more = bool(_object(issues["pageInfo"], f"page {index} `pageInfo`").get("hasNextPage"))
        for found in issues["nodes"]:
            node = _object(found, f"an issue on page {index}")
            number = node.get("number")
            if not isinstance(number, int) or isinstance(number, bool):
                raise _unreadable(f"an issue on page {index} carries no number: {number!r}")
            if number in seen:
                raise _unreadable(f"issue #{number} appears on more than one page")
            seen.add(number)
            _shape(node, number)
            nodes.append(node)
    return nodes, more


# --- the shapes inside one node -----------------------------------------------------


def _connection_nodes(node: Mapping[str, Any], name: str) -> list[Any]:
    found: list[Any] = node[name]["nodes"]
    return found


def _page_info(node: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    found: Mapping[str, Any] = node[name]["pageInfo"]
    return found


def _names(node: Mapping[str, Any], connection: str, key: str) -> tuple[str, ...]:
    """One connection's values for a key, in the order the export wrote them."""

    return tuple(
        found[key]
        for found in _connection_nodes(node, connection)
        if isinstance(found, dict) and isinstance(found.get(key), str)
    )


def _state(node: Mapping[str, Any]) -> str | None:
    """The ticket state a tracker state maps to, or None where the table maps none."""

    raw, reason = node.get("state"), node.get("stateReason")
    for state, reasons, reads in _STATE_ROWS:
        if raw == state and (reasons is None or reason in reasons):
            return reads
    return None


# --- relations ----------------------------------------------------------------------


def _is_foreign_relation(relation: str) -> bool:
    """Whether a `parent` or `blocked-by` id names an issue outside this repository.

    A local id is `#<n>`. Anything this reader qualified — `owner/project#n`
    for another repository, `?#n` where the export named none — resolves to
    nothing local, so a foreign blocker never reads closed and a foreign parent
    never joins a subtree here.
    """

    return bool(relation) and not relation.startswith("#")


def _relation(raw: Any, declaration: Declaration) -> str:
    """One relation node as an id, qualified unless the export shows it to be local.

    A node carrying no `repository` at all is not shown to be local either, and
    is qualified rather than assumed local. The two names are compared with case
    folded: a tracker treats `Owner/Project` and `owner/project` as one repository.
    """

    node = _object(raw, "a `parent` or `blockedBy` node")
    number = node.get("number")
    if not isinstance(number, int) or isinstance(number, bool):
        raise _unreadable(f"a `parent` or `blockedBy` node carries no number: {number!r}")
    named = _field(node.get("repository"), "nameWithOwner")
    if named.casefold() == declaration.repo.casefold():
        return f"#{number}"
    return f"{named or _UNKNOWN_REPOSITORY}#{number}"


def _external_text(kind: str, relation: str, declaration: Declaration) -> str:
    if relation.startswith(f"{_UNKNOWN_REPOSITORY}#"):
        return (
            f"the {kind} {relation} carries no repository in this export, so it is not shown "
            f"to be in {declaration.repo}"
        )
    return f"the {kind} {relation} is in another repository, not {declaration.repo}"


def _total(node: Mapping[str, Any]) -> int:
    summary = node.get("subIssuesSummary")
    total = summary.get("total") if isinstance(summary, dict) else None
    return total if isinstance(total, int) and not isinstance(total, bool) else 0


# --- one issue, read once ------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Issue:
    """One export node read once: what the gate, the relations and the reader need.

    `parent` and `blocked_by` are resolved for every issue and not only for a
    ticket, so a relation the export spells in a way nobody can read refuses
    wherever it hangs; only a ticket's are carried into a `Ticket`.
    """

    node: Mapping[str, Any]
    id: str
    number: int
    state: str
    labels: tuple[str, ...]
    parent: str
    blocked_by: tuple[str, ...]
    is_ticket: bool


def _issue(node: Mapping[str, Any], declaration: Declaration) -> _Issue:
    """The gate over one node: the declared label, and nothing else.

    The label as it stands is the acceptance: no edit before or after it lapses
    it, and who applied it is the tracker's to police (only accounts with triage
    access can label).
    """

    number = node["number"]
    state = _state(node)
    if state is None:
        raise _unreadable(
            f"issue #{number} is in the state {node.get('state')!r} with the reason "
            f"{node.get('stateReason')!r}, which the reader does not map"
        )
    labels = _names(node, "labels", "name")
    parent = node.get("parent")
    return _Issue(
        node=node,
        id=f"#{number}",
        number=number,
        state=state,
        labels=labels,
        parent="" if parent is None else _relation(parent, declaration),
        blocked_by=tuple(
            _relation(raw, declaration) for raw in _connection_nodes(node, "blockedBy")
        ),
        is_ticket=declaration.label in labels,
    )


# --- the hold -----------------------------------------------------------------------


def _hold(
    ticket: str, fields: BlockFields, labels: tuple[str, ...], declaration: Declaration
) -> tuple[str, Message | None]:
    """The effective hold, and the INFO where the two surfaces disagree.

    Each surface is read through the model's one table, by asking it what the block
    alone says and what the labels alone say, so this module never keeps a second
    copy of the effective hold. Only a reader knows whether its store has labels,
    which is why the message is here and not there.

    A block that does not carry `human-only` has no surface to disagree with:
    the missing required key is already an error of its own, and reading it as a
    `no` that contradicts a label would report one defect twice.
    """

    from_block = effective_hold(fields.human_only, (), declaration)
    from_labels = effective_hold("", labels, declaration)
    held = effective_hold(fields.human_only, labels, declaration)
    if from_block == from_labels or _HOLD_KEY not in fields.present:
        return held, None
    return held, message(
        "HOLD_SURFACES_DIFFER",
        ticket,
        f"the block says `human-only: {from_block}` and the labels say `{from_labels}`; "
        f"a hold on either surface holds, so this ticket reads `{held}`",
        "set the block and the labels to the same hold",
    )


# --- one ticket ----------------------------------------------------------------------


def _forbidden_keys(ticket: str, fields: BlockFields) -> list[Message]:
    """The lifecycle keys a `github` block must not carry.

    `parse_block` accepts every block key whatever the store, because the
    block grammar is one grammar; which of them a store's tracker already holds
    natively is this reader's to say.
    """

    return [
        message(
            "KEY_UNKNOWN",
            ticket,
            f"`{key}` is not a key of a `github` ticket block: {_TRACKER_FACTS[key]} holds it",
            "remove the key from the block and set it in the tracker",
        )
        for key in LIFECYCLE_KEYS
        if key in fields.present
    ]


def _truncated_connections(issue: _Issue) -> list[Message]:
    return [
        message(
            "EXPORT_TRUNCATED",
            issue.id,
            f"this ticket's `{name}` connection reports a further page",
            RUN_AGAIN,
        )
        for name in _CONNECTIONS
        if _page_info(issue.node, name).get("hasNextPage")
    ]


def _external_relations(issue: _Issue, children: int, declaration: Declaration) -> list[Message]:
    """The relations this export cannot resolve inside the declared repository.

    A foreign relation is kept and never aliased, and a child the export does
    not hold is never assumed closed: both are reported and neither is guessed.
    """

    kinds = [("parent", issue.parent), *(("blocker", blocker) for blocker in issue.blocked_by)]
    found = [
        message(
            "RELATION_EXTERNAL",
            issue.id,
            _external_text(kind, relation, declaration),
            _ONE_REPOSITORY,
        )
        for kind, relation in kinds
        if _is_foreign_relation(relation)
    ]
    total = _total(issue.node)
    if total > children:
        found.append(
            message(
                "RELATION_EXTERNAL",
                issue.id,
                f"`subIssuesSummary.total` is {total} and this export holds {children} of this "
                "ticket's children, so the rest are not shown here",
                _ONE_REPOSITORY,
            )
        )
    return found


def _brief(body: str, fields: BlockFields) -> str:
    """The issue body outside the block; all of it where no block was read."""

    if fields.begin < 0:
        return body
    return body[: fields.begin] + body[fields.end :]


def _ticket(
    issue: _Issue, declaration: Declaration, children: int
) -> tuple[Ticket, tuple[Message, ...]]:
    """One normalised ticket, and everything the reader has to say about it.

    The block is read from the body alone, and the relations come from the
    export: `blockedBy` and `parent` are the tracker's, which is why a block that
    repeats them, or a status or an assignee the tracker holds, is an error rather
    than a second opinion.
    """

    node = issue.node
    body = node["body"] if isinstance(node.get("body"), str) else ""
    title = node["title"] if isinstance(node.get("title"), str) else ""
    fields, found = parse_block(body)
    held, differ = _hold(issue.id, fields, issue.labels, declaration)
    brief = _brief(body, fields)
    messages = [
        *(replace(item, ticket=issue.id) for item in found),
        *_forbidden_keys(issue.id, fields),
        *_truncated_connections(issue),
        *_external_relations(issue, children, declaration),
        *([differ] if differ is not None else []),
    ]
    return (
        Ticket(
            id=issue.id,
            title=title,
            url=node["url"] if isinstance(node.get("url"), str) else "",
            state=issue.state,
            block_version=fields.version,
            brief=brief,
            reads=fields.reads,
            bounds=fields.bounds,
            human_only=fields.human_only,
            hold=held,
            done_when=fields.done_when,
            blocked_by=issue.blocked_by,
            parent=issue.parent,
            discovered_from=fields.discovered_from,
            content=content_identity(title, brief, fields),
        ),
        tuple(messages),
    )


def _partial_gates(issues: Sequence[_Issue]) -> list[Message]:
    """Every issue the gate excluded on a label set the export did not finish.

    The gate reads the labels this export happens to hold, so an issue outside
    it whose `labels` connection reports a further page may carry the ticket
    label on a page nobody was given: it was excluded on evidence known to be
    incomplete. A ticket's own truncated connections are reported against the
    ticket; this is the one finding about an issue that never became one.
    """

    return [
        message(
            "EXPORT_TRUNCATED",
            issue.id,
            f"issue {issue.id} is not a ticket, and its `labels` connection reports a further "
            "page, so the label this gate looked for may be on a page this export does not hold",
            RUN_AGAIN,
        )
        for issue in issues
        if not issue.is_ticket and _page_info(issue.node, "labels").get("hasNextPage")
    ]


# --- the read -----------------------------------------------------------------------


def read_github_export(source: str | Path, declaration: Declaration) -> ReadResult:
    """Read one pinned export as normalised tickets.

    `source` is the file the caller's export wrote, or `-` for standard input.
    Nothing here reaches a tracker: input that is not the array of pages the
    pinned query produces refuses by name rather than being read as an
    empty repository.

    Issues are returned sorted by number, every list in the order the export
    wrote it, so two reads of one export are equal field for field. Messages
    come in one settled order: what is true of the run, then what is true of
    each issue outside the gate, then each ticket's, all by issue number.
    """

    text, info = _source_text(source)
    nodes, more = _issue_nodes(_pages(text), declaration)
    issues = sorted((_issue(node, declaration) for node in nodes), key=lambda found: found.number)
    children = Counter(found.parent for found in issues if found.parent)
    others = frozenset(found.id for found in issues if not found.is_ticket)
    run: list[Message] = []
    if more:
        run.append(
            message(
                "EXPORT_TRUNCATED",
                "",
                "the last page of this export reports a further page, so it is not the whole "
                "issue list",
                RUN_AGAIN,
            )
        )
    run.extend(_partial_gates(issues))
    tickets: list[Ticket] = []
    messages: list[Message] = []
    for found in issues:
        if not found.is_ticket:
            continue
        built, said = _ticket(found, declaration, children[found.id])
        tickets.append(built)
        messages.extend(said)
    return ReadResult(
        tickets=tuple(tickets),
        others=others,
        ignored=len(others),
        messages=tuple(run + messages),
        input=info,
    )
