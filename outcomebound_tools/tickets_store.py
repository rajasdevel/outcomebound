"""Which export a run reads: the `github` store's, given as `--input`, and no other.

What this module decides: that a verb reads the store its project declared
from the export it was handed, what a verb is told when it was handed none,
and the one command that makes that export, which the `export` verb prints.
The reader itself is `tickets_github`'s.

It runs nothing: the engine holds no credential, so the command is printed
for the person or agent who holds one.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from outcomebound_tools import home, paths
from outcomebound_tools.tickets_declaration import Declaration
from outcomebound_tools.tickets_github import read_github_export
from outcomebound_tools.tickets_model import ReadResult
from outcomebound_tools.tickets_report import PlanningError

__all__ = ["QUERY", "export", "export_command", "read_store"]

# The pinned query, as this engine ships it. The command names its absolute path in this install,
# which `gh` reads itself (`-F query=@path`): no shell has to substitute a file's text.
QUERY = home.ROOT / "templates" / "tickets" / "github-export.graphql"


def export_command(declaration: Declaration) -> str:
    """The `gh` command that writes the declared repository's export to `issues.json`.

    It is one command for POSIX shells, PowerShell and Git Bash: the query is read by `gh` from
    its path. PowerShell 5.1 saves `>` output as UTF-16, which `--input` reads.
    """

    owner, _, name = declaration.repo.partition("/")
    return (
        f"gh api graphql --paginate --slurp -F owner={paths.shell_word(owner)} "
        f"-F name={paths.shell_word(name)} "
        f"-F {paths.shell_word(f'query=@{QUERY.resolve().as_posix()}')} "
        "> issues.json"
    )


def export(target: Path, declaration: Declaration, options: argparse.Namespace) -> str:
    """The `export` verb: the pinned query's path, as a shell comment, then the command.

    Two lines, and the whole is a shell script a person can read and run. It
    runs nothing and writes nothing: the export is made under the login of
    whoever runs the command.
    """

    del target, options
    return f"# the pinned query: {QUERY.resolve().as_posix()}\n{export_command(declaration)}\n"


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
            f"from an export: run `{export_command(declaration)}`, then pass the file as "
            "--input issues.json, or - for standard input; `outcomebound tickets export` "
            "prints the same command",
        )
    return read_github_export(source, declaration)
