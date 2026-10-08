"""Deterministic checks for selected OutcomeBound artifacts.

This module validates claims it can actually observe: managed-block structure and
authored content in an explicitly selected spec. It does not infer engineering
quality from length, headings alone, or the presence of a command string.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from collections.abc import Sequence

from outcomebound_tools import textio
from outcomebound_tools.identity import IdentityError, parse_managed_block

HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
FRONTMATTER_RE = re.compile(r"\A---\s*\n.*?\n---\s*\n", re.DOTALL)
TEMPLATE_PLACEHOLDER_RE = re.compile(
    r"<(?:slug|name|one-line outcome|"
    r"observable state this step leaves true|"
    r"only material constraints; delete this row when none|"
    r"when this step needs its own check; otherwise delete this row)>"
    r"|\{\{[^}\n]*\}\}",
    re.IGNORECASE,
)


class ArtifactCheckError(ValueError):
    """The selected artifact is malformed or incomplete."""


def extract_body(block: str, block_id: str | None = None) -> tuple[str, str]:
    try:
        parsed = parse_managed_block(block, block_id)
    except IdentityError as error:
        raise ArtifactCheckError(str(error)) from error
    if not parsed.body.strip():
        raise ArtifactCheckError("managed block body is empty")
    return parsed.body, parsed.block_id


def check_block(block: str, block_id: str | None = None) -> None:
    """Validate one named non-empty managed block.

    Without ``block_id`` the input must carry exactly one block.
    Compactness is maintained in the shipped template and reviewed as
    prompt quality. A universal line/token cutoff would reject useful content
    based on an arbitrary proxy, so this checker deliberately makes no size
    claim.
    """

    extract_body(block, block_id)


def _authored_content(text: str) -> str:
    without_frontmatter = FRONTMATTER_RE.sub("", text, count=1)
    without_comments = HTML_COMMENT_RE.sub("", without_frontmatter)
    without_scaffold_frame = re.sub(
        r"^(?:#{1,6}\s+|>\s?).*$", "", without_comments, flags=re.MULTILINE
    )
    return without_scaffold_frame.strip()


def check_document(text: str) -> list[str]:
    """Report only observable scaffold incompleteness.

    Passing means that known template placeholders are gone and some authored
    content exists. It does not establish decision quality or require a fixed
    section shape.
    """

    problems: list[str] = []
    if TEMPLATE_PLACEHOLDER_RE.search(text):
        problems.append("document still contains an OutcomeBound template placeholder")
    if not re.search(r"\w", _authored_content(text)):
        problems.append("document contains no authored content beyond metadata and headings")
    return problems


def check_spec_file(spec_path: str | os.PathLike[str]) -> list[str]:
    path = os.fspath(spec_path)
    try:
        with open(path, encoding="utf-8") as source:
            text = source.read()
    except (OSError, UnicodeDecodeError) as error:
        return [f"{path}: unreadable spec: {error}"]
    if path.endswith(("design.md", "plan.md")):
        return [f"{path}: {problem}" for problem in check_document(text)]
    return [f"{path}: expected design.md or plan.md"]


def check_spec_dir(specs_dir: str | os.PathLike[str]) -> list[str]:
    """Check every spec under a selected tree, at any depth.

    A directory that holds neither a spec nor further directories is reported:
    silently passing a tree with no checkable artifact would let "no specs" look
    exactly like "every spec is clean".
    """

    root = os.fspath(specs_dir)
    if not os.path.isdir(root):
        return [f"{root}: unreadable specs directory: not a directory"]

    violations: list[str] = []
    found_spec = False
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(
            name for name in dirnames if not name.startswith(("_", ".")) and name != "node_modules"
        )
        kinds = [kind for kind in ("design.md", "plan.md") if kind in filenames]
        if os.path.abspath(dirpath) == os.path.abspath(root):
            continue
        if kinds:
            found_spec = True
            for kind in kinds:
                violations.extend(check_spec_file(os.path.join(dirpath, kind)))
        elif not dirnames:
            violations.append(f"{dirpath}: spec directory has no design.md or plan.md")
    if not found_spec and not violations:
        violations.append(f"{root}: contains no spec with a design.md or plan.md")
    return violations


def _main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python3 -m outcomebound_tools.artifactcheck")
    parser.add_argument("--managed-block", action="store_true", help="check one block on stdin")
    parser.add_argument(
        "--id",
        default="operating-contract",
        help="managed block id to select from stdin (default: operating-contract)",
    )
    parser.add_argument("--spec", action="append", default=[], help="selected design/plan path")
    parser.add_argument("--spec-dir", action="append", default=[], help="selected specs directory")
    args = parser.parse_args(argv)

    problems: list[str] = []
    if args.managed_block:
        try:
            check_block(textio.stdin_text(), args.id)
        except ArtifactCheckError as error:
            problems.append(str(error))
    for path in args.spec:
        problems.extend(check_spec_file(path))
    for directory in args.spec_dir:
        problems.extend(check_spec_dir(directory))
    if not args.managed_block and not args.spec and not args.spec_dir:
        parser.error("select --managed-block, --spec, or --spec-dir")
    for problem in problems:
        sys.stderr.write(f"artifact-check FAIL: {problem}\n")
    if problems:
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
