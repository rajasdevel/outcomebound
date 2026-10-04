"""The claims plan a `done-when` name resolves against.

What this module decides: where the one v1 validation plan the declaration names
is read from, which claims it defines, what command, timeout and required paths
each carries, and where a claim would run and whether that directory lies inside
the checkout (answered once, so that `check` and `brief` cannot answer it
differently). A relative `cwd` starts at the plan file's own folder, as
`outcomebound validation` resolves it, so one plan runs in one place for both.
Whether a plan's claims would run in a folder it was not written for is decided
once too, by `placement`, which `check` and `adopt` both read.

What it does not decide: any message, any verdict about a ticket, and what an
undefined claim means — `CLAIM_PLANNED` and `CLAIM_CWD_OUTSIDE` belong to
`check`, which reads these answers. It runs nothing and writes nothing: a claim's
command is the project's own, and the engine only names it.

**No text from a ticket is ever executed.** The only thing a ticket contributes
is a name, looked up in a plan the repository committed.

`CLAIMS_UNREADABLE` covers a plan that is absent, is not JSON, or is not shaped
as a plan -- `claims` that is not a list of objects with unique non-empty names,
a top-level `cwd` or `timeout_seconds` of the wrong type, or a top-level `cwd`
holding a NUL byte.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

from outcomebound_tools import paths
from outcomebound_tools.tickets_declaration import Declaration
from outcomebound_tools.tickets_report import Refusal

__all__ = [
    "ClaimDefinition",
    "ClaimsPlan",
    "Placement",
    "absent_paths",
    "load_claims",
    "placement",
]

UNREADABLE = "CLAIMS_UNREADABLE"


class _Unreadable(Exception):
    """Internal: why this text is not a claims plan, which `load_claims` refuses."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


@dataclass(frozen=True, slots=True)
class ClaimDefinition:
    """One claim of the plan, as `brief` renders it.

    `timeout_seconds` is the timeout in effect: the claim's own where it
    declares one, otherwise the plan's, and None where neither sets one, because
    a claim waits for its command unless the project sets a hang guard.
    `command` is empty where the claim declares none the runner could use. The
    directory it would run in is the plan's `cwd_resolved`, the same for every
    claim, since a validation claim declares none of its own.

    `required_paths` is each path the claim declares it needs, resolved against
    that directory and written relative to the checkout as a POSIX path; a path
    that resolves outside the checkout is None, since no `bounds` entry can
    cover it. Empty where the claim declares none, which says nothing about what
    its command reads.
    """

    name: str
    command: tuple[str, ...]
    timeout_seconds: float | None
    required_paths: tuple[str | None, ...] = ()


@dataclass(frozen=True, slots=True)
class ClaimsPlan:
    """The claims plan at one checkout.

    `cwd_resolved` is the directory the plan's top-level `cwd` resolves to
    against the plan file's folder in the checkout this plan was loaded from, the
    folder `outcomebound validation` starts a relative `cwd` from, and `cwd_inside` is
    whether that directory lies inside the checkout. Both are computed once, in one
    expression, at load: a plan may define no claim at all and still name a
    directory outside the checkout, which `check` must report, so the answer is
    a field rather than something a caller recomputes against a root of its own
    choosing.

    `claims` maps a claim name to its definition, in the order the plan writes
    them.
    """

    path: str
    cwd_resolved: Path
    cwd_inside: bool
    claims: Mapping[str, ClaimDefinition]


# --- the working directory --------------------------------------------------------


def _resolve(root: Path, path: str, raw_cwd: str | None) -> tuple[Path, bool]:
    """The plan's `cwd` against the plan file's folder, and whether it stays inside
    the checkout.

    A relative `cwd` starts where `validation.load_plan` starts it, at the folder
    that holds the plan, so a plan at `.outcomebound/ticket-claims.json` writes
    `"cwd": ".."` to run at the checkout root under both verbs. Both sides are
    resolved with symbolic links followed, because a checkout reached through a
    symlinked directory -- which is what a temporary directory often is --
    otherwise reads as outside its own root. The directory need not exist: a plan
    naming one that is not there still has a resolved name.
    """

    candidate = Path("." if raw_cwd is None else raw_cwd)
    if not candidate.is_absolute():
        candidate = (root / path).parent / candidate
    resolved = candidate.resolve()
    return resolved, resolved.is_relative_to(root.resolve())


def _required(root: Path, cwd: Path, value: object) -> tuple[str | None, ...]:
    """Each declared required path, relative to the checkout, or None outside it.

    Resolved as `validation.run_claim` resolves it: an absolute path as written,
    a relative one against the plan's directory. Entries that are not non-empty
    strings are passed over, because judging a claim is the runner's job.
    """

    if not isinstance(value, list):
        return ()
    base = root.resolve()
    found: list[str | None] = []
    for raw in value:
        if not isinstance(raw, str) or not raw.strip() or "\0" in raw:
            continue
        candidate = Path(raw.strip())
        resolved = Path(os.path.normpath(candidate if candidate.is_absolute() else cwd / candidate))
        found.append(
            resolved.relative_to(base).as_posix() if resolved.is_relative_to(base) else None
        )
    return tuple(found)


# --- reading the plan -------------------------------------------------------------


def _refusal(path: str, detail: str) -> Refusal:
    return Refusal(
        UNREADABLE,
        f"the claims plan {path} could not be read: {detail}; it must be the one "
        "committed v1 validation plan the store declaration names, because a "
        "`done-when` name resolves against it and nothing else",
    )


def _tree_document(root: Path, path: str) -> object:
    """The decoded plan in the working tree. The bounded read refuses a symlink."""

    try:
        raw = paths.read_bounded(root, path)
    except paths.PathError as error:
        raise _Unreadable(str(error)) from error
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise _Unreadable(f"it is not UTF-8 JSON: {error}") from error


def _command(value: object) -> tuple[str, ...]:
    """The claim's argv, or empty where it declares none the runner could use."""

    if not isinstance(value, list) or not all(isinstance(word, str) for word in value):
        return ()
    return tuple(value)


def _number(value: object) -> float | None:
    """`value` as a float where the JSON wrote a number, else None. `True` is not one."""

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _timeout(claim_value: object, plan_value: object) -> float | None:
    """The timeout in effect: the claim's, else the plan's, else None, which is none."""

    for value in (claim_value, plan_value):
        number = _number(value)
        if number is not None:
            return number
    return None


def _definitions(
    raw_claims: list[object], plan_timeout: object, root: Path, cwd: Path
) -> Mapping[str, ClaimDefinition]:
    """The plan's claims, in written order, over one namespace of unique names.

    Names are stripped as `validation.parse_plan` strips them, so a name looked
    up here is the name the runner would run.
    """

    definitions: dict[str, ClaimDefinition] = {}
    for index, item in enumerate(raw_claims):
        if not isinstance(item, dict):
            raise _Unreadable(f"claims[{index}] is not an object")
        written = item.get("name")
        if not isinstance(written, str) or not written.strip():
            raise _Unreadable(f"claims[{index}] has no name")
        name = written.strip()
        if name in definitions:
            raise _Unreadable(
                f"claims[{index}] repeats the claim name {name!r}; the plan is one namespace"
            )
        definitions[name] = ClaimDefinition(
            name=name,
            command=_command(item.get("command")),
            timeout_seconds=_timeout(item.get("timeout_seconds"), plan_timeout),
            required_paths=_required(root, cwd, item.get("required_paths")),
        )
    return MappingProxyType(definitions)


def _plan(root: Path, path: str, document: object) -> ClaimsPlan:
    """The typed plan, or `_Unreadable` naming what is wrong with the document.

    The two top-level values are type-checked because containment and every
    timeout are computed from them; a claim is read for its name, command and
    timeout and required paths alone, because judging a claim is `validation.parse_plan`'s job
    wherever the plan is actually run.
    """

    if not isinstance(document, dict):
        raise _Unreadable("the plan is not a JSON object")
    raw_cwd = document.get("cwd")
    if raw_cwd is not None and not isinstance(raw_cwd, str):
        raise _Unreadable("the top-level cwd must be a string")
    if raw_cwd is not None and "\0" in raw_cwd:
        raise _Unreadable("the top-level cwd contains a NUL byte, which no path can hold")
    raw_timeout = document.get("timeout_seconds")
    if raw_timeout is not None and _number(raw_timeout) is None:
        raise _Unreadable("the top-level timeout_seconds must be a number")
    raw_claims = document.get("claims")
    if not isinstance(raw_claims, list):
        raise _Unreadable("claims must be a list of claim objects")
    cwd, inside = _resolve(root, path, raw_cwd)
    return ClaimsPlan(
        path=path,
        cwd_resolved=cwd,
        cwd_inside=inside,
        claims=_definitions(raw_claims, raw_timeout, root, cwd),
    )


def absent_paths(plan: ClaimsPlan, target: Path | str) -> dict[str, tuple[str, ...]]:
    """Each claim's declared required paths that the checkout does not hold, by claim name.

    The paths are already resolved from the plan's working directory, as `validation`
    resolves them, so a plan whose relative `cwd` was written for the checkout root,
    and now starts at the plan file's folder, names paths that are not there. A path
    outside the checkout is the bounds check's to report, not this one's.
    """

    root = Path(target).resolve()
    found = {
        name: tuple(path for path in item.required_paths if path and not (root / path).exists())
        for name, item in plan.claims.items()
    }
    return {name: paths for name, paths in found.items() if paths}


@dataclass(frozen=True, slots=True)
class Placement:
    """Whether a plan's claims would run in a folder the plan was not written for.

    Since a relative `cwd` started at the plan file's folder, a plan written for the
    checkout root runs its claims elsewhere, and two signs show it. `absent` is the
    first: each claim's declared required paths that the checkout does not hold, as
    `absent_paths` finds them. `at_plan_folder` is the second, for a plan whose claims
    declare no paths: the working directory is the plan file's own folder while that
    folder is not the checkout root, which is what a plan below the root reads with
    no `cwd` at all or with `"cwd": "."`. `to_root` is the relative `cwd` that runs
    the claims at the checkout root instead, `..` from `.outcomebound/`.
    """

    at_plan_folder: bool
    absent: Mapping[str, tuple[str, ...]]
    to_root: str

    @property
    def misplaced(self) -> bool:
        """Whether either sign is present."""

        return self.at_plan_folder or bool(self.absent)


def placement(plan: ClaimsPlan, target: Path | str) -> Placement:
    """The one answer to whether `plan`'s claims would run in the wrong folder.

    `check` warns on it and `adopt` reports it at each install and upgrade, so the
    two cannot disagree on which plan needs a new `cwd` or on what to write there.
    """

    root = Path(target).resolve()
    folder = (root / plan.path).parent.resolve()
    return Placement(
        at_plan_folder=plan.cwd_resolved == folder and folder != root,
        absent=MappingProxyType(absent_paths(plan, root)),
        to_root=Path(os.path.relpath(root, folder)).as_posix(),
    )


def load_claims(target: Path | str, declaration: Declaration) -> ClaimsPlan:
    """The claims plan in the working tree, or `CLAIMS_UNREADABLE`."""

    root = Path(target)
    path = declaration.claims
    try:
        return _plan(root, path, _tree_document(root, path))
    except _Unreadable as error:
        raise _refusal(path, error.detail) from error
