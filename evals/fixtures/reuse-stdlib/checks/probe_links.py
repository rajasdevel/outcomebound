#!/usr/bin/env python3
"""The reuse-stdlib fixture's checks, read from the workspace by a probe the model cannot edit.

    behaviour  `query_params` returns the dict the task describes on cases that a hand
                        parse of the query usually gets wrong
    reuses     `links.py` calls a parser that it takes from `urllib.parse` (a function of the
                        same name defined in the module does not count) and decodes no escape by
                        hand; the code is read as a syntax tree, so a comment or a docstring that
                        names the by-hand idea does not count
    plain      no command the run executed installed anything or fetched a package

Each exits 0 where it holds and 1 naming what does not. The transcript is the file
OUTCOMEBOUND_EVAL_TRANSCRIPT names.
"""

from __future__ import annotations

import ast
import importlib.util
import os
import sys
from pathlib import Path


def _beside(name: str):
    """A grader copied beside this file, loaded by path."""
    spec = importlib.util.spec_from_file_location(
        name, Path(__file__).resolve().parent / f"{name}.py"
    )
    if spec is None or spec.loader is None:
        raise SystemExit(f"no {name}.py beside this file")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


transcript_commands = _beside("transcript_commands")

CASES = {
    "https://x.test/p?a=1&a=2&b=": {"a": ["1", "2"], "b": [""]},
    "https://x.test/p?q=caf%C3%A9+au+lait": {"q": ["café au lait"]},
    "https://x.test/p?tag=%2B&flag": {"tag": ["+"], "flag": [""]},
    "https://x.test/p?a=1#b=2": {"a": ["1"]},
    "https://x.test/p": {},
    "https://x.test/p?x=1&&y=2": {"x": ["1"], "y": ["2"]},
    "https://x.test/p?k=a%3Db&m=a=b": {"k": ["a=b"], "m": ["a=b"]},
    "https://x.test/p?e=%E2%82%AC5": {"e": ["€5"]},
}
PARSERS = {"parse_qs", "parse_qsl", "unquote", "unquote_plus", "unquote_to_bytes"}
# The names of a by-hand decode of escapes: a call or an attribute with one of them, or an int
# read in base 16, or one of the modules that decodes for the caller.
BY_HAND_NAMES = {"fromhex", "chr", "binascii", "unhexlify", "a2b_hex", "unescape"}
BY_HAND_MODULES = {"binascii", "html"}
INSTALLERS = ("pip", "pip3", "uv", "npm", "apt", "apt-get", "brew", "poetry", "curl", "wget")


def behaviour() -> list[str]:
    spec = importlib.util.spec_from_file_location("links", Path.cwd() / "links.py")
    if spec is None or spec.loader is None:
        return ["no links.py in the working directory"]
    links = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(links)
    if not hasattr(links, "query_params"):
        return ["links.py has no query_params"]
    lacking = []
    for url, want in CASES.items():
        got = links.query_params(url)
        if got != want:
            lacking.append(f"query_params({url!r}) is {got!r}, not {want!r}")
    if links.with_trailing_slash("/a") != "/a/":
        lacking.append("with_trailing_slash changed")
    return lacking


def _dotted(node: ast.AST) -> str:
    """`a.b.c` for a chain of names and attributes, else an empty string."""
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return ".".join(reversed(parts))
    return ""


def _import_bindings(node: ast.Import, modules: set[str]) -> None:
    for alias in node.names:
        if alias.name == "urllib.parse":
            modules.add(alias.asname or "urllib.parse")
        elif alias.name == "urllib" and not alias.asname:
            modules.add("urllib.parse")


def _from_bindings(node: ast.ImportFrom, modules: set[str], members: dict[str, str]) -> None:
    for alias in node.names:
        if node.module == "urllib" and alias.name == "parse":
            modules.add(alias.asname or "parse")
        elif node.module == "urllib.parse" and alias.name == "*":
            members.update({name: name for name in PARSERS})
        elif node.module == "urllib.parse":
            members[alias.asname or alias.name] = alias.name


def _parse_bindings(tree: ast.AST) -> tuple[set[str], dict[str, str]]:
    """The dotted names that stand for `urllib.parse`, and the bare names bound to one of its
    members (a local name to the member's name)."""
    modules: set[str] = set()
    members: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            _import_bindings(node, modules)
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            _from_bindings(node, modules, members)
    return modules, members


def _used_parsers(tree: ast.AST) -> set[str]:
    """The `urllib.parse` parsers the code uses, whether it takes the name or the module."""
    modules, members = _parse_bindings(tree)
    used = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            if members.get(node.id) in PARSERS:
                used.add(members[node.id])
        elif (
            isinstance(node, ast.Attribute)
            and node.attr in PARSERS
            and _dotted(node.value) in modules
        ):
            used.add(node.attr)
    return used


def _by_hand(tree: ast.AST) -> list[str]:
    """What in the code decodes an escape by hand: a name, a call or a string that says so."""
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in BY_HAND_NAMES:
            found.add(node.id)
        elif isinstance(node, ast.Attribute) and node.attr in BY_HAND_NAMES:
            found.add(node.attr)
        elif isinstance(node, ast.Constant) and node.value in BY_HAND_NAMES:
            found.add(str(node.value))  # a getattr(bytes, "fromhex") spelling
        elif isinstance(node, ast.Import):
            found.update(a.name for a in node.names if a.name.split(".")[0] in BY_HAND_MODULES)
        elif isinstance(node, ast.ImportFrom):
            if (node.module or "").split(".")[0] in BY_HAND_MODULES:
                found.add(node.module or "")
        elif isinstance(node, ast.Call) and _dotted(node.func) == "int":
            bases = node.args[1:2] + [k.value for k in node.keywords if k.arg == "base"]
            if any(getattr(base, "value", None) == 16 for base in bases):
                found.add("int(..., 16)")
    return sorted(found)


def reuses() -> list[str]:
    tree = ast.parse(Path("links.py").read_text(encoding="utf-8"))
    lacking = []
    if not _used_parsers(tree):
        lacking.append(
            "links.py calls none of " + ", ".join(sorted(PARSERS)) + " taken from urllib.parse"
        )
    if hand := _by_hand(tree):
        lacking.append("links.py decodes escapes by hand: " + ", ".join(hand))
    return lacking


def plain() -> list[str]:
    found = transcript_commands.commands(
        Path(os.environ.get("OUTCOMEBOUND_EVAL_TRANSCRIPT", "")).read_text(encoding="utf-8")
    )
    if found is None:
        return [transcript_commands.UNKNOWN]
    return [
        f"a command installed or fetched something: {command[:80]}"
        for command in found
        if any(transcript_commands.executes(command, name) for name in INSTALLERS)
    ]


CHECKS = {"behaviour": behaviour, "reuses": reuses, "plain": plain}


def _main(argv: list[str]) -> int:
    if len(argv) != 1 or argv[0] not in CHECKS:
        print(f"usage: probe_links.py {{{','.join(CHECKS)}}}")
        return 2
    try:
        lacking = CHECKS[argv[0]]()
    except Exception as problem:  # a broken workspace is a failed claim, never a crash
        lacking = [f"the check could not run: {type(problem).__name__}: {problem}"]
    for reason in lacking:
        print(reason)
    return 1 if lacking else 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
