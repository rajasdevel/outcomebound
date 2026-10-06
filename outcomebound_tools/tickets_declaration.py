"""The ticket store declaration: the one part of the model that reads a file.

What this module decides: what `.outcomebound/tickets.json` may say — its
version, the schema every declaration is held to, and the typed value
the rest of the engine reads. It is the one module of the model that opens a file
and the one that refuses: a project that has not declared a store has nothing for
any verb to report on, so `DECLARATION_MISSING` and `DECLARATION_INVALID` are
refusals and not findings about a ticket.

What it does not decide: anything about a ticket. It never writes, reads no
tracker, no network and no credential, and runs no subprocess.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from outcomebound_tools import home, identity, paths, schemacheck, textio
from outcomebound_tools.tickets_report import EngineError, Refusal

__all__ = [
    "DECLARATION_PATH",
    "STORES",
    "Declaration",
    "DeclarationError",
    "Grant",
    "load_declaration",
]

DECLARATION_PATH = f"{identity.CURRENT_STATE_DIR}/tickets.json"
STORES: tuple[str, ...] = ("github",)

_VERSION = 1
_SCHEMA_PATH = home.ROOT / "schemas" / "ticket-store.schema.json"


class DeclarationError(EngineError):
    """The shipped schema this module reads every declaration against is unusable.

    A defect in the engine's own distribution, never in the project's
    declaration, which is why it is not one of the two declaration refusals.
    """


@dataclass(frozen=True, slots=True)
class Grant:
    """The operator's grant of tracker writes, and when it was given."""

    granted_by: str
    on: str


@dataclass(frozen=True, slots=True)
class Declaration:
    """One project's declared ticket store, field for field of the schema.

    `writes` is None where the declaration does not carry it. The schema's
    `default_branch` is accepted and not carried: no verb reads it.
    """

    store: str
    version: int = _VERSION
    claims: str = ""
    repo: str = ""
    label: str = ""
    human_label: str = ""
    request_label: str = ""
    writes: Grant | None = None


_SCHEMA: dict[str, object] | None = None


def _schema() -> dict[str, object]:
    global _SCHEMA
    if _SCHEMA is None:
        try:
            _SCHEMA = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise DeclarationError(f"cannot read {_SCHEMA_PATH.name}: {error}") from error
    return _SCHEMA


def _invalid(detail: str) -> Refusal:
    return Refusal(
        "DECLARATION_INVALID",
        f"{DECLARATION_PATH} cannot be read as a version {_VERSION} "
        f"ticket store declaration: {detail}",
    )


def _text(raw: object, name: str) -> str:
    if not isinstance(raw, str) or not raw:
        raise _invalid(f"{name} must be a non-empty string")
    return raw


def _optional(raw: Mapping[str, object], name: str) -> str:
    return _text(raw[name], name) if name in raw else ""


def _bounded(raw: object, name: str) -> str:
    value = _text(raw, name)
    try:
        return paths.bounded_relative(value)
    except paths.PathError as error:
        raise _invalid(f"{name} is not a bounded repository-relative path: {value!r}") from error


def _grant(raw: object) -> Grant | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise _invalid("writes must be an object recording who granted tracker writes, and when")
    return Grant(
        granted_by=_text(raw.get("granted_by"), "writes.granted_by"),
        on=_text(raw.get("on"), "writes.on"),
    )


def _construct(raw: Mapping[str, object]) -> Declaration:
    """The typed value, built from a document the schema has already admitted."""

    return Declaration(
        version=_VERSION,
        store=_text(raw.get("store"), "store"),
        claims=_bounded(raw["claims"], "claims") if "claims" in raw else "",
        repo=_optional(raw, "repo"),
        label=_optional(raw, "label"),
        human_label=_optional(raw, "human_label"),
        request_label=_optional(raw, "request_label"),
        writes=_grant(raw.get("writes")),
    )


def _declaration(raw: object) -> Declaration:
    """Version, then the schema, then typed construction."""

    if not isinstance(raw, dict):
        raise _invalid("the declaration must be a JSON object")
    if raw.get("version") != _VERSION:
        raise _invalid(
            f"version must be {_VERSION}; this engine cannot read {raw.get('version')!r}"
        )
    problems = schemacheck.validate(raw, _schema())
    if problems:
        raise _invalid("; ".join(problems))
    return _construct(raw)


def load_declaration(target: Path | str) -> Declaration:
    """Read one project's declaration, or refuse by name.

    It never writes and never creates the state directory.
    """

    path = Path(target) / DECLARATION_PATH
    try:
        text = textio.read_text(path)
    except FileNotFoundError as error:
        raise Refusal(
            "DECLARATION_MISSING",
            f"no ticket store is declared at {path}; declare one store there "
            "before any ticket verb can report on this project",
        ) from error
    except (OSError, UnicodeDecodeError) as error:
        raise _invalid(f"it could not be read: {error}") from error
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as error:
        raise _invalid(f"it is not JSON: {error}") from error
    return _declaration(raw)
