#!/usr/bin/env python3
"""Attribute what each kept eval run spent to what put it in the model's context. No model call.

`python3 evals/attribute.py DIR [DIR ...] [--json]` reads each run directory that `evals/run.py`
wrote (`<fixture>.meta.json` and the `<fixture>.native.jsonl` copy of Codex's own session) and
reports, grouped by arm and by fixture and arm:

- the median model calls and the median input, cached input, uncached input, output and
  reasoning tokens, summed per run from each model call's `last_token_usage`;
- the catalog each run saw before its first user message: the characters of the developer
  messages, the entries of the skill list and the plugin namespaces among them. A group whose
  runs saw different skill lists is flagged;
- what each kind of tool call cost. The first call's input is the preamble, re-sent by every
  call. In a session, model call i issues tool calls, their output is logged, then call i's
  token count; that output enters call i+1. So the input increase from call i to call i+1 is
  charged to the tool calls call i issued: first the visible output of call i (output less
  reasoning tokens) to `model-output`, then the rest split among the tool calls in proportion to
  their output characters. A chunk that enters call j of N (0-based) is re-sent by N - j calls
  and costs its size times N - j;
- each OutcomeBound file read: in how many runs, its median direct cost (output characters / 4
  times the later calls that re-send it), and the failed required claims of the runs that read
  it beside the runs of the same group that did not;
- the slow-suite launches of each run, and the suite runs its workspace's
  `.runs/integration.log` recorded as completed, or UNVERIFIED where that cannot be read.

A tool call is one shell command string as the model issued it, or one `tools.*` call inside a
script of Codex's `exec` tool. A compound command (joined with `&&`, `;`, `|` or newlines) is
one tool call and takes one class: the first class, in `CLASSES` order, that any of its parts
matches.
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, NamedTuple

# Direct script execution also needs the repository package path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evals.native_receipts import parse_records
from outcomebound_tools.fragments import SKILLS

REPO = Path(__file__).resolve().parent.parent
FIXTURES = REPO / "evals" / "fixtures"
REPLICA = FIXTURES / "replica"
UNVERIFIED = "UNVERIFIED"
CHARS_PER_TOKEN = 4
PREAMBLE = "preamble"
MODEL_OUTPUT = "model-output"
CLASSES = (
    "guidance-read",
    "suite-run",
    "poll",
    "checks",
    "git",
    "env",
    "write",
    "read",
    "other",
)
NOTE = (
    "A tool call is one shell command string, or one tools.* call inside an exec script; a "
    "compound command is one tool call and takes one class, the first that any part matches."
)

GUIDANCE_PATH = re.compile(
    r"\.outcomebound/[\w./-]*|\.agents/skills/(?:" + "|".join(SKILLS) + r")(?:/[\w./-]*)?"
)
FILE_READ = re.compile(
    r"\.outcomebound/fragments/[\w.-]+|\.agents/skills/(?:" + "|".join(SKILLS) + r")/[\w./-]+"
)
SKILL_ENTRY = re.compile(r"^- ([\w.-]+(?::[\w.-]+)*): .*\(file: ", re.MULTILINE)
INNER_CALL = re.compile(r"tools\.(\w+)\(")
CMD_FIELD = re.compile(r'"?cmd"?\s*:\s*(?:"((?:[^"\\]|\\.)*)"|`([^`]*)`)')
CHARS_FIELD = re.compile(r'"?chars"?\s*:\s*"((?:[^"\\]|\\.)*)"')
PATCH_FILE = re.compile(r"\*\*\* (?:Update|Add|Delete) File: (\S+)")
HEREDOC = re.compile(r"<<-?\s*['\"]?(\w+)['\"]?")
SCRIPT_HEADER = re.compile(r"^Script \w+")
SEPARATORS = {"&&", "||", ";", "|", "&", "(", ")", ";;", "|&", "{", "}", "!"}
WRAPPERS = {"env", "time", "nohup", "nice", "command", "exec", "stdbuf"}
SHELLS = {"bash", "sh", "zsh", "dash"}
PYTHON = re.compile(r"^python[\d.]*$")
READERS = {
    "cat",
    "sed",
    "head",
    "tail",
    "rg",
    "grep",
    "ls",
    "find",
    "nl",
    "wc",
    "awk",
    "less",
    "jq",
    "tree",
    "stat",
    "file",
    "du",
    "df",
    "diff",
    "pwd",
    "echo",
    "printf",
    "sort",
    "uniq",
    "cut",
}
WRITERS = {"tee", "cp", "mv", "rm", "touch", "patch", "mkdir", "ln", "chmod"}
CHECK_TARGET = re.compile(r"check|lint|unit|test|gates|capacity")
CHECK_TOOLS = {"pytest", "ruff", "mypy", "flake8", "pyflakes", "black", "shellcheck"}
CHECK_MODULES = {"unittest", "pytest", "py_compile", "compileall", "ruff", "mypy", "doctest"}
CHECK_SCRIPT = re.compile(r"(^|/)(tests?|gates)/|lint|check|(^|/)test_[\w]*\.py$")


class Suite(NamedTuple):
    """How a replica base runs its slow suite: the Make targets that run it, the runner scripts
    that execute it, and the folder it lives in."""

    targets: frozenset[str]
    scripts: frozenset[str]
    folder: str


class ToolCall(NamedTuple):
    """One tool call a model call issued: its tool, its command text, the characters of its
    output, and its class."""

    call_id: str
    tool: str
    command: str
    output_chars: int
    cls: str


class ModelCall(NamedTuple):
    """One model call: its token counts and the tool calls it issued."""

    input: int
    cached: int
    output: int
    reasoning: int
    tools: tuple[ToolCall, ...]


class Catalog(NamedTuple):
    """What a run saw before its first user message."""

    developer_chars: int
    skills: tuple[str, ...]
    namespaces: tuple[str, ...]


def suite_from_sources(texts: list[str]) -> Suite:
    """The slow suite as the replica bases' Makefiles define it: the runner each
    `test-integration` recipe executes, and each target that depends on `test-integration`."""

    scripts, targets = set(), {"test-integration"}
    for text in texts:
        scripts.update(re.findall(r"test-integration:[^\n]*\n\s*\$\(PYTHON\)(?: -\w)* (\S+)", text))
        targets.update(re.findall(r"^([\w-]+):[^\n=]*\btest-integration\b", text, re.MULTILINE))
    return Suite(frozenset(targets), frozenset(scripts), "tests/integration")


def replica_suite(root: Path = REPLICA) -> Suite:
    """The slow suite of every replica base under `root`, read from the files that write their
    Makefiles."""

    paths = sorted(root.rglob("*")) if root.is_dir() else []
    texts = [
        path.read_text(encoding="utf-8", errors="replace")
        for path in paths
        if path.is_file() and (path.suffix in (".sh", ".py") or path.name == "Makefile")
    ]
    return suite_from_sources(texts)


SUITE = replica_suite()


def _js_string(text: str) -> str:
    try:
        return str(json.loads(f'"{text}"'))
    except ValueError:
        return text


def _inner_calls(script: str) -> list[tuple[str, str]]:
    """Each `tools.<name>(` call in an exec script, with the text up to the next one."""

    starts = list(INNER_CALL.finditer(script))
    return [
        (
            match.group(1),
            script[match.start() : (starts[n + 1].start() if n + 1 < len(starts) else None)],
        )
        for n, match in enumerate(starts)
    ]


def _described(tool: str, text: str) -> tuple[str, str]:
    """The tool name and the command text of one inner call or function call."""

    if tool == "exec_command":
        found = CMD_FIELD.search(text)
        if found:
            literal = found.group(1)
            return tool, _js_string(literal) if literal is not None else found.group(2)
        return tool, text[:300]
    if tool == "write_stdin":
        chars = CHARS_FIELD.search(text)
        return tool, _js_string(chars.group(1)) if chars else text[:300]
    if tool == "apply_patch":
        files = PATCH_FILE.findall(text.replace("\\n", "\n"))
        return tool, "apply_patch " + " ".join(files)
    return tool, text[:300]


def issued(payload: dict[str, Any]) -> list[tuple[str, str]]:
    """The tool calls one native tool-call record holds, as (tool, command) pairs: each
    `tools.*` call of an exec script, or the one function call."""

    if payload.get("type") == "custom_tool_call":
        text = payload.get("input") or ""
        inner = _inner_calls(text) if payload.get("name") == "exec" else []
        if inner:
            return [_described(tool, part) for tool, part in inner]
        return [_described(str(payload.get("name") or "custom"), text)]
    name = str(payload.get("name") or "function")
    arguments = payload.get("arguments") or ""
    try:
        document = json.loads(arguments)
    except ValueError:
        document = None
    if isinstance(document, dict) and name in ("exec_command", "shell"):
        command = document.get("cmd") or document.get("command") or ""
        return [("exec_command", " ".join(command) if isinstance(command, list) else str(command))]
    if isinstance(document, dict) and name == "write_stdin":
        return [(name, str(document.get("chars") or ""))]
    return [_described(name, arguments)]


def output_parts(output: Any, count: int) -> list[int]:
    """The output characters of each of `count` tool calls that one output record answers.

    An exec script's output is a header item, then one item per call where the counts agree;
    the header is shared equally. Where they do not agree, the whole is shared equally."""

    if isinstance(output, list):
        texts = [
            str(item.get("text", "")) if isinstance(item, dict) else str(item) for item in output
        ]
    else:
        texts = [output if isinstance(output, str) else json.dumps(output)]
    header = texts[0] if texts and SCRIPT_HEADER.match(texts[0]) and len(texts) > 1 else None
    body = texts[1:] if header is not None else texts
    shared = len(header) if header is not None else 0
    if len(body) == count:
        return [len(text) + shared // count for text in body]
    total = sum(len(text) for text in texts)
    return [total // count] * count


def _segments(command: str) -> list[list[str]]:
    """The simple commands of a shell command, each as its words, with wrappers and variable
    assignments taken off the front; `bash -c TEXT` is read as TEXT."""

    found: list[list[str]] = []
    for line in _without_heredocs(command):
        lexer = shlex.shlex(line, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        try:
            words = list(lexer)
        except ValueError:
            words = line.split()
        current: list[str] = []
        for word in [*words, ";"]:
            if word in SEPARATORS:
                if current:
                    found.extend(_unwrapped(current))
                current = []
            else:
                current.append(word)
    return found


def _without_heredocs(command: str) -> list[str]:
    """The lines of a shell command less the bodies of its here-documents, which are data."""

    kept, end = [], None
    for line in command.splitlines():
        if end is not None:
            end = None if line.strip() == end else end
            continue
        kept.append(line)
        marker = HEREDOC.search(line)
        end = marker.group(1) if marker else None
    return kept


def _unwrapped(words: list[str]) -> list[list[str]]:
    while words:
        head = words[0]
        if re.match(r"^\w+=", head) or head in WRAPPERS:
            words = words[1:]
        elif head == "timeout":
            words = words[1:]
            while words and words[0].startswith("-"):
                words = words[2:] if words[0] in ("-k", "-s") else words[1:]
            words = words[1:]
        else:
            break
    if words and Path(words[0]).name in SHELLS:
        for n, word in enumerate(words[1:-1], start=1):
            if word.startswith("-") and "c" in word:
                return _segments(words[n + 1])
    return [words] if words else []


def _program(words: list[str]) -> str:
    return Path(words[0]).name if words else ""


def _make_targets(words: list[str]) -> list[str]:
    targets, skip = [], False
    for word in words[1:]:
        if skip:
            skip = False
        elif word in ("-C", "-f", "-j", "-o", "-W", "-I"):
            skip = True
        elif word.startswith("-") or "=" in word or word in (">", ">>", ">&", "<"):
            continue
        else:
            targets.append(word)
    return targets


def _python_target(words: list[str]) -> tuple[str, str, list[str]]:
    """What a python command runs: ("module", name, args), ("script", path, args), or
    ("code", "", [])."""

    rest = words[1:]
    while rest:
        word = rest[0]
        if word == "-m" and len(rest) > 1:
            return "module", rest[1], rest[2:]
        if word == "-c":
            return "code", "", []
        if word in ("-X", "-W"):
            rest = rest[2:]
        elif word.startswith("-") and word != "-":
            rest = rest[1:]
        else:
            return "script", word, rest[1:]
    return "code", "", []


def _clean(path: str) -> str:
    return path[2:] if path.startswith("./") else path


def _runs_suite(words: list[str], suite: Suite) -> bool:
    program = _program(words)
    if program in ("make", "gmake"):
        return any(target in suite.targets for target in _make_targets(words))
    folder = suite.folder.rstrip("/")

    def names_folder(args: list[str]) -> bool:
        return any(_clean(arg).rstrip("/") == folder for arg in args)

    if PYTHON.match(program):
        kind, name, args = _python_target(words)
        if kind == "module":
            return name in ("unittest", "pytest") and names_folder(args)
        return kind == "script" and any(_clean(name).endswith(s) for s in suite.scripts)
    if program == "pytest":
        return names_folder(words[1:])
    return any(_clean(words[0]).endswith(script) for script in suite.scripts)


def _is_check(words: list[str]) -> bool:
    program = _program(words)
    if program in ("make", "gmake"):
        return any(CHECK_TARGET.search(target) for target in _make_targets(words))
    if program in CHECK_TOOLS:
        return True
    if PYTHON.match(program):
        kind, name, _args = _python_target(words)
        if kind == "module":
            return name.split(".")[0] in CHECK_MODULES
        return kind == "script" and bool(CHECK_SCRIPT.search(_clean(name)))
    return False


def _is_write(words: list[str]) -> bool:
    program = _program(words)
    if program in WRITERS:
        return True
    if program in ("sed", "perl") and any(word.startswith("-i") for word in words[1:]):
        return True
    for n, word in enumerate(words[:-1]):
        if word in (">", ">>") and words[n + 1] != "/dev/null":
            return True
    return False


def _runs_envctl(words: list[str]) -> bool:
    if PYTHON.match(_program(words)):
        kind, name, _args = _python_target(words)
        return kind == "script" and Path(name).name == "envctl"
    return _program(words) == "envctl"


def _shell_class(command: str, suite: Suite) -> str:
    segments = _segments(command)
    rules = (
        ("guidance-read", lambda s: _program(s) == "outcomebound"),
        ("suite-run", lambda s: _runs_suite(s, suite)),
        ("checks", _is_check),
        ("git", lambda s: _program(s) == "git"),
        ("env", _runs_envctl),
        ("write", _is_write),
        ("read", lambda s: _program(s) in READERS),
    )
    for name, rule in rules:
        if name == "guidance-read" and GUIDANCE_PATH.search(command):
            return name
        if name == "env" and ".envs/" in command:
            return name
        if any(rule(segment) for segment in segments):
            return name
    return "other"


def classify(tool: str, command: str, suite: Suite = SUITE) -> str:
    """The class of one tool call; the first class in `CLASSES` order that any part of its
    command matches."""

    if tool == "apply_patch":
        return "write"
    if tool in ("wait", "sleep") or (tool == "write_stdin" and command == ""):
        return "poll"
    return _shell_class(command, suite) if tool == "exec_command" else "other"


def _developer_text(payload: dict[str, Any]) -> str:
    return "".join(
        str(part.get("text", "")) for part in payload.get("content") or [] if isinstance(part, dict)
    )


def session(records: list[dict[str, Any]], suite: Suite = SUITE) -> tuple[list[ModelCall], Catalog]:
    """Each model call of a native session with the tool calls it issued, and the catalog the
    session saw before its first user message.

    A `token_count` event whose running total repeats the one before it is the same call
    reported again and is skipped."""

    calls: list[ModelCall] = []
    pending: list[dict[str, Any]] = []
    by_id: dict[str, list[dict[str, Any]]] = {}
    developer, before_user, last_total = "", True, None
    for record in records:
        kind = record.get("type")
        payload: dict[str, Any] = (
            record["payload"] if isinstance(record.get("payload"), dict) else {}
        )
        item = payload.get("type")
        if kind == "response_item" and item == "message":
            if payload.get("role") == "user":
                before_user = False
            elif payload.get("role") == "developer" and before_user:
                developer += _developer_text(payload)
        elif kind == "response_item" and item in ("custom_tool_call", "function_call"):
            made: list[dict[str, Any]] = [
                {
                    "call_id": str(payload.get("call_id", "")),
                    "tool": tool,
                    "command": command,
                    "chars": 0,
                }
                for tool, command in issued(payload)
            ]
            pending.extend(made)
            by_id[str(payload.get("call_id", ""))] = made
        elif kind == "response_item" and item in (
            "custom_tool_call_output",
            "function_call_output",
        ):
            made = by_id.get(str(payload.get("call_id", "")), [])
            sizes = output_parts(payload.get("output"), len(made)) if made else []
            for entry, size in zip(made, sizes, strict=True):
                entry["chars"] += size
        elif kind == "event_msg" and item == "token_count":
            info: dict[str, Any] = payload["info"] if isinstance(payload.get("info"), dict) else {}
            last, total = info.get("last_token_usage"), info.get("total_token_usage")
            if not isinstance(last, dict) or not last.get("input_tokens") or total == last_total:
                continue
            last_total = total
            tools = tuple(
                ToolCall(
                    e["call_id"],
                    e["tool"],
                    e["command"],
                    e["chars"],
                    classify(e["tool"], e["command"], suite),
                )
                for e in pending
            )
            calls.append(
                ModelCall(
                    int(last.get("input_tokens", 0)),
                    int(last.get("cached_input_tokens", 0)),
                    int(last.get("output_tokens", 0)),
                    int(last.get("reasoning_output_tokens", 0)),
                    tools,
                )
            )
            pending = []
    skills = tuple(sorted(SKILL_ENTRY.findall(developer)))
    namespaces = tuple(sorted({name.split(":", 1)[0] for name in skills if ":" in name}))
    return calls, Catalog(len(developer), skills, namespaces)


def attribution(calls: list[ModelCall]) -> tuple[dict[str, float], list[float]]:
    """Input tokens charged to each class over the run, and the charge of each tool call in
    order of issue, lag-corrected: the increase from call i to call i+1 belongs to call i.

    Of each increase, call i's visible output (output less reasoning) goes to `model-output`
    first; the rest is split among call i's tool calls by output characters (equally where none
    has output), or goes to `model-output` where call i issued none. A chunk entering call j of
    N costs its size times N - j. A decrease (the context was shortened) charges nothing."""

    cost: defaultdict[str, float] = defaultdict(float)
    per_tool: list[float] = []
    count = len(calls)
    if not count:
        return cost, per_tool
    cost[PREAMBLE] = calls[0].input * count
    for i, call in enumerate(calls):
        tools = call.tools
        if i + 1 >= count:
            per_tool.extend(0.0 for _ in tools)
            continue
        weight = count - (i + 1)
        rise = max(0, calls[i + 1].input - call.input)
        own = min(rise, max(0, call.output - call.reasoning)) if tools else rise
        cost[MODEL_OUTPUT] += own * weight
        rest = rise - own
        sizes = [tool.output_chars for tool in tools]
        whole = sum(sizes)
        for tool, size in zip(tools, sizes, strict=True):
            part = rest * (size / whole if whole else 1 / len(tools))
            cost[tool.cls] += part * weight
            per_tool.append(part * weight)
    return cost, per_tool


def guidance_reads(calls: list[ModelCall]) -> dict[str, float]:
    """The direct cost of each OutcomeBound file a run read: its share of the reading call's
    output characters (shared equally among the files one command names) / 4, times the later
    calls that re-send it."""

    found: dict[str, float] = defaultdict(float)
    count = len(calls)
    for i, call in enumerate(calls):
        for tool in call.tools:
            if tool.cls != "guidance-read":
                continue
            files = sorted(set(FILE_READ.findall(tool.command)))
            for name in files:
                share = tool.output_chars / len(files) / CHARS_PER_TOKEN
                found[name] += share * max(0, count - (i + 1))
    return dict(found)


def required_claims(fixture: str, fixtures: Path = FIXTURES) -> frozenset[str] | None:
    """The names of the fixture's required claims, or None where its plan cannot be read."""

    try:
        plan = json.loads((fixtures / fixture / "post.plan.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return frozenset(c["name"] for c in plan.get("claims", []) if c.get("required"))


def _suite_logged(workspace: Path) -> bool:
    for script in SUITE.scripts:
        path = workspace / script
        if path.is_file() and "integration.log" in path.read_text(
            encoding="utf-8", errors="replace"
        ):
            return True
    return False


def completed_suites(workspace: str | None) -> int | str:
    """Suite runs recorded as completed in the workspace's `.runs/integration.log` files (the
    workspace's own and any worktree's within it), or UNVERIFIED with the reason."""

    if not workspace or not Path(workspace).is_dir():
        return f"{UNVERIFIED} (workspace not kept)"
    root = Path(workspace)
    logs = [path for path in root.rglob("integration.log") if path.parent.name == ".runs"]
    if not logs:
        if _suite_logged(root):
            return 0
        return f"{UNVERIFIED} (this suite keeps no log)"
    done = 0
    for log in logs:
        for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            done += isinstance(entry, dict) and entry.get("kind") == "suite"
    return done


def read_run(
    meta_path: Path, suite: Suite = SUITE, fixtures: Path = FIXTURES
) -> dict[str, Any] | None:
    """One run's analysis from its meta file and the native session beside it, or None where
    the session is missing or holds no model call."""

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    native = meta_path.with_name(meta_path.name.replace(".meta.json", ".native.jsonl"))
    if not native.is_file():
        return None
    calls, catalog = session(parse_records(native.read_bytes()), suite)
    if not calls:
        return None
    cost, per_tool = attribution(calls)
    required = required_claims(str(meta.get("fixture")), fixtures)
    claims = meta.get("claims") or {}
    failed = (
        None
        if required is None
        else sum(1 for k, v in claims.items() if v == "FAIL" and k in required)
    )
    tools = [tool for call in calls for tool in call.tools]
    return {
        "directory": str(meta_path.parent),
        "fixture": meta.get("fixture"),
        "arm": meta.get("arm"),
        "verdict": meta.get("verdict"),
        "calls": len(calls),
        "input": sum(c.input for c in calls),
        "cached": sum(c.cached for c in calls),
        "uncached": sum(c.input - c.cached for c in calls),
        "output": sum(c.output for c in calls),
        "reasoning": sum(c.reasoning for c in calls),
        "catalog": catalog._asdict(),
        "cost": dict(cost),
        "guidance": guidance_reads(calls),
        "failed_required": failed,
        "suite_launches": sum(1 for tool in tools if tool.cls == "suite-run"),
        "suite_completed": completed_suites(meta.get("fixture_repo")),
        "model_calls": [
            {
                "input": c.input,
                "cached": c.cached,
                "output": c.output,
                "reasoning": c.reasoning,
                "tools": [
                    {
                        "tool": t.tool,
                        "command": t.command,
                        "output_chars": t.output_chars,
                        "class": t.cls,
                    }
                    for t in c.tools
                ],
            }
            for c in calls
        ],
        "tool_charges": [round(value, 1) for value in per_tool],
    }


def read_runs(directories: list[Path]) -> tuple[list[dict[str, Any]], list[str]]:
    """Every readable run under the directories, and a note for each meta file left out."""

    runs, skipped = [], []
    for directory in directories:
        for meta_path in sorted(directory.glob("*.meta.json")):
            run = read_run(meta_path)
            if run is None:
                skipped.append(f"{meta_path}: no native session with a model call")
            else:
                runs.append(run)
    return runs, skipped


TOKEN_KEYS = ("input", "cached", "uncached", "output", "reasoning")


def summarize(runs: list[dict[str, Any]]) -> dict[str, Any]:
    """The report of one group of runs."""

    median = {key: statistics.median(run[key] for run in runs) for key in ("calls", *TOKEN_KEYS)}
    skill_lists = {tuple(run["catalog"]["skills"]) for run in runs}
    chars = [run["catalog"]["developer_chars"] for run in runs]
    catalog = {
        "developer_chars": [min(chars), max(chars)],
        "skill_entries": sorted({len(skills) for skills in skill_lists}),
        "namespaces": sorted({ns for run in runs for ns in run["catalog"]["namespaces"]}),
        "differ": len(skill_lists) > 1,
    }
    cost: defaultdict[str, float] = defaultdict(float)
    for run in runs:
        for name, value in run["cost"].items():
            cost[name] += value
    whole = sum(cost.values()) or 1
    shares = {
        name: {"tokens": round(value), "share": round(value / whole, 4)}
        for name, value in sorted(cost.items(), key=lambda pair: -pair[1])
    }
    guidance: dict[str, Any] = {}
    for name in sorted({name for run in runs for name in run["guidance"]}):
        read = [run for run in runs if name in run["guidance"]]
        unread = [run for run in runs if name not in run["guidance"]]
        guidance[name] = {
            "runs_read": len(read),
            "median_direct_cost": round(statistics.median(run["guidance"][name] for run in read)),
            "failed_required_read": _failed(read),
            "failed_required_unread": _failed(unread),
        }
    return {
        "runs": len(runs),
        "median": median,
        "catalog": catalog,
        "attribution": shares,
        "guidance": guidance,
        "suite": [
            {
                "fixture": run["fixture"],
                "directory": run["directory"],
                "launches": run["suite_launches"],
                "completed": run["suite_completed"],
            }
            for run in runs
        ],
    }


def _failed(runs: list[dict[str, Any]]) -> dict[str, Any]:
    """Failed required claims per run over the runs whose fixture plan could be read."""

    known = [run["failed_required"] for run in runs if run["failed_required"] is not None]
    return {
        "runs": len(runs),
        "per_run": round(sum(known) / len(known), 2) if known else None,
        "unknown": len(runs) - len(known),
    }


def report(runs: list[dict[str, Any]], skipped: list[str]) -> dict[str, Any]:
    """The whole report: by arm, by fixture and arm, and the runs."""

    by_arm: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_pair: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for run in runs:
        by_arm[str(run["arm"])].append(run)
        by_pair[f"{run['fixture']} x {run['arm']}"].append(run)
    return {
        "note": NOTE,
        "arms": {arm: summarize(group) for arm, group in sorted(by_arm.items())},
        "fixture_arms": {key: summarize(group) for key, group in sorted(by_pair.items())},
        "runs": runs,
        "skipped": skipped,
    }


def _failed_text(item: dict[str, Any]) -> str:
    if not item["runs"]:
        return "no runs"
    per_run = UNVERIFIED if item["per_run"] is None else f"{item['per_run']:.2f}"
    unknown = f", {item['unknown']} unknown" if item["unknown"] else ""
    return f"{per_run} over {item['runs']} runs{unknown}"


def _group_lines(title: str, group: dict[str, Any]) -> list[str]:
    median, catalog = group["median"], group["catalog"]
    low, high = catalog["developer_chars"]
    lines = [
        f"== {title}: {group['runs']} runs",
        "  median   calls {calls:>5g}   input {input:>9g}   cached {cached:>9g}   "
        "uncached {uncached:>8g}   output {output:>7g}   reasoning {reasoning:>7g}".format(
            **median
        ),
        f"  catalog  developer chars {low}-{high}"
        f"   skill entries {', '.join(map(str, catalog['skill_entries']))}"
        f"   namespaces {', '.join(catalog['namespaces']) or 'none'}"
        + ("   FLAG: runs saw different skill lists" if catalog["differ"] else ""),
        "  attribution (input tokens, summed over runs)",
    ]
    for name, item in group["attribution"].items():
        lines.append(f"    {name:<14} {item['tokens']:>12}  {100 * item['share']:5.1f}%")
    if group["guidance"]:
        lines.append(
            "  OutcomeBound files read (runs, median direct cost, failed required claims per run)"
        )
        for name, item in group["guidance"].items():
            lines.append(
                f"    {name:<58} {item['runs_read']:>3}  {item['median_direct_cost']:>8}"
                f"  read {_failed_text(item['failed_required_read'])};"
                f" not read {_failed_text(item['failed_required_unread'])}"
            )
    launches = [str(entry["launches"]) for entry in group["suite"]]
    done = [str(entry["completed"]) for entry in group["suite"]]
    lines.append(f"  suite launches per run  {', '.join(launches)}")
    lines.append(f"  suites completed        {', '.join(done)}")
    return lines


def text(document: dict[str, Any]) -> str:
    """The report as plain aligned text."""

    lines = [document["note"], ""]
    lines.append("BY ARM")
    for arm, group in document["arms"].items():
        lines.extend(_group_lines(f"arm {arm}", group))
    lines.extend(["", "BY FIXTURE AND ARM"])
    for key, group in document["fixture_arms"].items():
        lines.extend(_group_lines(key, group))
    if document["skipped"]:
        lines.extend(["", "LEFT OUT", *(f"  {item}" for item in document["skipped"])])
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="evals/attribute.py",
        description=(
            "Attribute each kept run's tokens to what put them in the model's context, from its "
            "native session; no model call. See the module docstring."
        ),
    )
    parser.add_argument(
        "directories", nargs="+", metavar="DIR", help="a run directory of evals/run.py"
    )
    parser.add_argument("--json", action="store_true", help="print the report as one JSON document")
    args = parser.parse_args(argv)
    directories = [Path(item) for item in args.directories]
    missing = [str(path) for path in directories if not path.is_dir()]
    if missing:
        parser.error(f"no directory {', '.join(missing)}")
    runs, skipped = read_runs(directories)
    if not runs:
        sys.stderr.write("attribute: no run with a native session and a model call\n")
        return 1
    document = report(runs, skipped)
    sys.stdout.write(json.dumps(document, indent=1) + "\n" if args.json else text(document))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
