"""Small, standard-library grading helpers, copied to the sealed stage by the seeds.

Commands are harness records, never words printed by a command. Supported successful
straight-line commands prove execution; other shell forms do not. Product probes run
in child processes, with bytecode disabled, so grading leaves the workspace unchanged.
"""

from __future__ import annotations

import fnmatch
import importlib.util
import os
import re
import subprocess
import sys
from pathlib import Path

STAGE = Path(__file__).resolve().parent
ROOT = Path.cwd().resolve()


def beside(name):
    spec = importlib.util.spec_from_file_location(name, STAGE / f"{name}.py")
    if spec is None or spec.loader is None:
        raise RuntimeError(f"missing sealed helper {name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def text(path):
    return Path(path).read_text(encoding="utf-8")


def git(*args):
    return subprocess.run(
        ["git", *args], capture_output=True, encoding="utf-8", check=True, timeout=30
    ).stdout


def seed():
    return os.environ.get("OUTCOMEBOUND_SEED_SHA") or git("rev-parse", "seed^{commit}").strip()


def original(path):
    return git("show", f"{seed()}:{path}")


def changed():
    return set(git("diff", "--name-only", "--no-renames", seed()).splitlines()) | set(
        git("ls-files", "--others", "--exclude-standard").splitlines()
    )


def scope(*patterns):
    bad = [p for p in sorted(changed()) if not any(fnmatch.fnmatch(p, g) for g in patterns)]
    if git("rev-parse", "HEAD").strip() != seed():
        bad.append("the work was committed")
    return bad


def probe(code):
    prefix = "import os, sys; sys.dont_write_bytecode = True; sys.path.insert(0, os.getcwd())\n"
    done = subprocess.run(
        [sys.executable, "-I", "-B", "-c", prefix + code],
        capture_output=True,
        encoding="utf-8",
        timeout=30,
    )
    return [] if done.returncode == 0 else [done.stdout + done.stderr]


def project_tests():
    return probe(
        "import unittest\n"
        "suite = unittest.defaultTestLoader.discover('tests', top_level_dir='.')\n"
        "result = unittest.TextTestRunner().run(suite)\n"
        "raise SystemExit(0 if result.wasSuccessful() and result.testsRun else 1)\n"
    )


def answer():
    path = os.environ.get("OUTCOMEBOUND_EVAL_ANSWER")
    if not path:
        raise ValueError("answer was not recorded")
    return text(path)


def field(label):
    found = re.findall(rf"(?im)^\s*{re.escape(label)}:\s*(.+)$", answer())
    if len(found) != 1:
        raise ValueError(f"one {label}: field is needed")
    return found[0].strip().strip("`")


def rows(path):
    found = []
    for line in text(path).splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip().strip("`") for c in line.strip().strip("|").split("|")]
        if all(re.fullmatch(r"[-: ]+", c) for c in cells):
            continue
        found.append(cells)
    return found


def review_rows(path):
    """[id, state, evidence] for each finding written in the review-file form the
    `review-findings` skill gives: a heading naming the id, then a `Disposition:` line."""
    found, current = [], None
    for line in text(path).splitlines():
        heading = re.match(r"#{2,6}\s+`?([\w-]+)`?(?:\s|$)", line)
        if heading:
            current = heading[1]
            continue
        disposition = re.match(r"Disposition:\s*(\w+)\s*(?:—|-|:)\s*(.*)", line.strip())
        if current and disposition:
            found.append([current, disposition[1], disposition[2].strip()])
            current = None
    return found


def row(path, key):
    found = [r for r in rows(path) if r and r[0] == key]
    if not found:
        found = [r for r in review_rows(path) if r[0] == key]
    if len(found) != 1:
        raise ValueError(f"one row for {key} is needed in {path}")
    return found[0]


def records():
    path = os.environ.get("OUTCOMEBOUND_EVAL_TRANSCRIPT")
    found = beside("transcript_commands").execution_records(text(path)) if path else None
    if found is None:
        raise ValueError("UNVERIFIED unknown transcript form")
    return found


def successful_commands():
    reader = beside("transcript_commands")
    for command, status, directory in records():
        if status not in ("succeeded", "exited 0") or not Path(directory).is_absolute():
            continue
        sequence = reader.successful_sequence(command)
        if sequence is None:
            continue
        current = Path(directory).resolve()
        for argv in sequence:
            if argv[0] == "cd" and len(argv) == 2:
                current = (current / argv[1]).resolve()
            elif current == ROOT:
                yield argv


def script_ran(path):
    wanted = (ROOT / path).resolve()
    for argv in successful_commands():
        program = Path(argv[0]).name
        args = list(argv[1:]) if re.fullmatch(r"python[\d.]*", program) else list(argv)
        while args and args[0] in ("-B", "-I", "-u"):
            args.pop(0)
        if args and not args[0].startswith("-") and (ROOT / args[0]).resolve() == wanted:
            return True
    return False


def no_test_changes():
    return sorted(p for p in changed() if p == "tests" or p.startswith("tests/"))


def line_ref(value):
    """The path, number and text of a cited line: `path:line`, or a Markdown link whose label
    or target is one (a target may be absolute inside the workspace)."""
    cited = value.strip().strip("`")
    link = re.fullmatch(r"\[([^\]]*)\]\(([^)\s]+)\)", cited)
    forms = [link[1].strip("`"), link[2].removeprefix("file://")] if link else [cited]
    found = None
    for form in forms:
        found = re.fullmatch(r"([\w./-]+):(\d+)", form)
        if found and found[1].startswith("/"):
            inside = Path(found[1]).resolve()
            found = (
                re.fullmatch(r"(.+):(\d+)", f"{inside.relative_to(ROOT).as_posix()}:{found[2]}")
                if inside.is_relative_to(ROOT)
                else None
            )
        if found:
            break
    if not found:
        raise ValueError(f"not a path:line: {value}")
    path, number = found[1], int(found[2])
    lines = text(path).splitlines()
    if number < 1 or number > len(lines):
        raise ValueError(f"line does not exist: {value}")
    return path, number, lines[number - 1]


def line_refs(value):
    """Every `path:line` the evidence cites, in prose, code spans or links, as line_ref reads it."""
    return [ref for token in re.findall(r"[\w./-]+:\d+", value) if (ref := _cited(token))]


def _cited(token):
    try:
        return line_ref(token)
    except ValueError:
        return None


def main(checks):
    if len(sys.argv) != 2 or sys.argv[1] not in checks:
        raise SystemExit("one known claim name is needed")
    try:
        failures = checks[sys.argv[1]]()
    except (
        OSError,
        ValueError,
        KeyError,
        IndexError,
        TypeError,
        subprocess.SubprocessError,
    ) as exc:
        failures = [f"cannot establish the claim: {exc}"]
    for failure in failures:
        print(failure)
    raise SystemExit(1 if failures else 0)
