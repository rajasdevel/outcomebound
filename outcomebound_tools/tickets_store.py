"""Which export a run reads: the `github` store's, given as `--input`, and no other.

What this module decides: that a verb reads the store its project declared
from the export it was handed, and what a verb is told when it was
handed none. The reader itself is `tickets_github`'s.
"""

from __future__ import annotations

from pathlib import Path

from outcomebound_tools.tickets_declaration import Declaration
from outcomebound_tools.tickets_github import read_github_export
from outcomebound_tools.tickets_model import ReadResult
from outcomebound_tools.tickets_report import PlanningError

__all__ = ["read_store"]


def read_store(target: Path, declaration: Declaration, source: str | None) -> ReadResult:
    """Read the declared store from `source`, what `--input` was given.

    The `github` store is read from an export and from nowhere else, so a run
    without one cannot be planned: that is exit 2 and one line, not an empty
    report. `target` is the checkout the run is about, which the export is not.
    """

    del target
    if source is None:
        raise PlanningError(
            "INPUT_REQUIRED",
            f"this project declares the github store ({declaration.repo}), which is read "
            "from an export: run the pinned query, templates/tickets/github-export.graphql, "
            "and pass its output "
            "as --input <file>, or - for standard input",
        )
    return read_github_export(source, declaration)
