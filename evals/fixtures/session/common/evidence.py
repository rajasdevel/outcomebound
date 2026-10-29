"""Read only protocol v1 evidence; the checker is staged beside this module."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent


def beside(name):
    spec = importlib.util.spec_from_file_location(name, HERE / (name + ".py"))
    if spec is None or spec.loader is None:
        raise ValueError("missing staged module: " + name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def turns(path=None):
    return beside("session_protocol").turns(read(path or os.environ["OB_TURNS"]))


def actions():
    found = beside("session_protocol").actions(read(os.environ["OB_ACTIONS"]))
    if "OB_TURNS" in os.environ:
        expected = [
            {**action, "turn": number}
            for number, turn in enumerate(turns(), 1)
            for action in turn["actions"]
        ]
        if expected != found:
            raise ValueError("per-turn actions disagree with OB_ACTIONS")
    return found


def segments(row):
    return beside("commands").segments(row)


def records(rows=None):
    parser = beside("commands")
    return [
        (part, "succeeded" if part.status == "ok" else "attempted", part.cwd)
        for row in (actions() if rows is None else rows)
        for segment in segments(row)
        for part in parser.processes(segment)
    ]


def successful_parts(row):
    return [part for part, status, _cwd in records([row]) if status == "succeeded"]


def content_tool(row):
    name = row.get("tool", "").rsplit(".", 1)[-1].lower()
    return name in {"read", "notebookread", "grep", "get_file", "read_file", "read_text"} and not (
        name == "grep" and row.get("output_mode") != "content"
    )


def content_segment(part):
    parser = beside("commands")
    argv = parser.program(part)
    name = parser.executes(part)
    if name in {"grep", "rg"}:
        args = iter(argv[1:])
        for arg in args:
            if arg == "--":
                break
            if arg in {
                "--files",
                "--files-with-matches",
                "--files-without-match",
                "--count",
                "--count-matches",
                "--quiet",
            }:
                return False
            if arg in {
                "-e",
                "-f",
                "-g",
                "-A",
                "-B",
                "-C",
                "-m",
                "-t",
                "-T",
                "--regexp",
                "--file",
                "--glob",
                "--context",
            }:
                next(args, None)
            elif arg.startswith("-") and not arg.startswith("--"):
                for flag in arg[1:]:
                    if flag in "efgABCmtT":
                        break
                    if flag in "lLqc":
                        return False
    raw = parser._program(part.argv or ())
    return name in {
        "cat",
        "head",
        "tail",
        "sed",
        "awk",
        "jq",
        "rg",
        "grep",
        "less",
        "more",
    } or bool(raw and Path(raw[0]).name.startswith(("python", "pypy")))


SEARCH_VALUES = {
    "-e",
    "--regexp",
    "-f",
    "--file",
    "-g",
    "--glob",
    "--iglob",
    "-A",
    "--after-context",
    "-B",
    "--before-context",
    "-C",
    "--context",
    "-m",
    "--max-count",
    "-t",
    "--type",
    "-T",
    "--type-not",
    "--include",
    "--exclude",
    "--exclude-dir",
}


def search_option(arg):
    if arg.startswith("--"):
        flag, separator, value = arg.partition("=")
        return flag, value if separator else None
    for index, flag in enumerate(arg[1:], 2):
        if "-" + flag in SEARCH_VALUES:
            return "-" + flag, arg[index:] or None
    return arg, None


def search_files(argv):
    """Separate content operands from patterns in the driver's recorded argv."""
    args = iter(argv[1:])
    operands = []
    explicit, options = False, True
    for arg in args:
        if options and arg == "--":
            options = False
        elif options and arg.startswith("-") and arg != "-":
            flag, value = search_option(arg)
            explicit |= flag in {"-e", "--regexp", "-f", "--file"}
            if flag in SEARCH_VALUES and value is None:
                next(args, None)
        else:
            operands.append(arg)
    return operands if explicit else operands[1:]


def content_paths(part):
    if not content_segment(part):
        return set()
    parser = beside("commands")
    if parser.executes(part) in {"grep", "rg"}:
        return {
            (Path(part.cwd) / name).resolve()
            for name in search_files(parser.program(part))
            if name != "-"
        }
    return {Path(path).resolve() for path in part.reads}


def read_paths(row):
    if row["kind"] == "tool":
        if row.get("status") != "ok" or not content_tool(row):
            return set()
        return {Path(path).resolve() for path in row.get("paths", [])}
    return {path for part in segments(row) if part.status == "ok" for path in content_paths(part)}


def uncertain_reads(row, path):
    parser = beside("commands")
    if (
        row["kind"] == "tool"
        and row.get("status") == "unknown"
        and content_tool(row)
        and str(path) in row.get("paths", [])
    ):
        return [
            parser.Segment(
                None, str(path.parent), "unknown", command="tool " + row["tool"] + " " + str(path)
            )
        ]
    return [
        part
        for part in segments(row)
        if (path in content_paths(part) and part.status == "unknown") or parser.unresolved(part)
    ]


def command_turns():
    actions()
    return {number: records(turn["actions"]) for number, turn in enumerate(turns(), 1)}


def checked_next(result):
    protocol = beside("session_protocol")
    config = read(HERE / "session.json")
    return protocol.next_turn(result, protocol.labels(config["labels"]))
