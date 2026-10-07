#!/usr/bin/env python3
"""The reuse-stdlib fixture's checks, read from the workspace by a probe the model cannot edit.

    behaviour  `query_params` returns the dict the task describes on cases that a hand
                        parse of the query usually gets wrong
    reuses     `links.py` uses `urllib.parse` for the parsing and decodes no escape by
                        hand
    plain      no command the run executed installed anything or fetched a package

Each exits 0 where it holds and 1 naming what does not. The transcript is the file
OUTCOMEBOUND_EVAL_TRANSCRIPT names.
"""

from __future__ import annotations

import ast
import importlib.util
import os
import re
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
BY_HAND = re.compile(r"fromhex|\bchr\(|int\([^)]*,\s*16\s*\)|\bbinascii\b|\bhtml\.unescape")
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


def reuses() -> list[str]:
    source = Path("links.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    used = {
        node.attr if isinstance(node, ast.Attribute) else node.id
        for node in ast.walk(tree)
        if isinstance(node, (ast.Attribute, ast.Name))
    }
    lacking = []
    if not used & PARSERS:
        lacking.append("links.py calls none of " + ", ".join(sorted(PARSERS)))
    if BY_HAND.search(source):
        lacking.append("links.py decodes escapes by hand")
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
