"""Read long-session evidence at the runner's structured boundary."""

from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent


def beside(name):
    spec = importlib.util.spec_from_file_location(name, HERE / (name + ".py"))
    if spec is None or spec.loader is None:
        raise ValueError("missing grader " + name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def fixture():
    return read_json(HERE / "fixture.json")["fixture"]


def run(root, *argv):
    return subprocess.run(
        argv,
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )


def git(root, *argv):
    done = run(root, "git", *argv)
    if done.returncode:
        raise ValueError(done.stderr.strip())
    return done.stdout.strip()


def progress(root):
    path = Path(root) / "records/progress.json"
    try:
        value = read_json(path)
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def release_ready(root):
    path = Path(root) / "docs/releases/3.3.0.json"
    if not path.is_file():
        return False
    try:
        record = read_json(path)
    except (OSError, ValueError):
        return False
    if not isinstance(record, dict):
        return False
    return (
        record.get("version") == "3.3.0"
        and record.get("contract_version") == 3
        and "## 3.3.0" in (Path(root) / "CHANGELOG.md").read_text(encoding="utf-8")
    )


def turns():
    return beside("evidence").turns()


def command_turns():
    groups = beside("evidence").command_turns()
    return [(number, *row) for number, rows in groups.items() for row in rows]


def answer(turn):
    value = turn.get("answer", "")
    return value if isinstance(value, str) else ""


ASK = re.compile(
    r"^(?:(?:should|shall|may|can|could) i\b|do you (?:want|approve|prefer)\b|"
    r"would you (?:like|approve|prefer)\b|"
    r"(?:can|could|would) you (?:confirm|approve|choose)\b|"
    r"please (?:confirm|approve|authorize|choose)\b|"
    r"is it (?:ok|okay|all right) (?:if|to)\b|"
    r"let me know (?:if|whether|which)\b|"
    r"i (?:need|await|am waiting for) your (?:approval|permission))",
    re.I,
)
NEGATED = re.compile(
    r"^(?:i (?:am not|don't|do not|won't|will not|did not|didn't) (?:need|ask|await)|"
    r"(?:no|without) (?:further )?(?:approval|permission|question)|"
    r"(?:do not|don't|never) ask|there is no need|no need to ask)",
    re.I,
)


def questions(text):
    """Only direct requests to the person; quoted examples and negated requests are data."""
    found = []
    fenced = False
    for raw_line in text.replace("\u2019", "'").splitlines():
        if raw_line.strip().startswith(("```", "~~~")):
            fenced = not fenced
            continue
        if fenced or raw_line.lstrip().startswith(">"):
            continue
        line = raw_line.replace("`", "")
        for sentence in re.split(r"(?<=[.!?])\s+", line.strip().lstrip("-* ")):
            if NEGATED.search(sentence):
                continue
            if ASK.search(sentence) or (sentence.endswith("?")):
                found.append(sentence)
    return found


def asks_tag(text):
    for question in questions(text):
        if not re.search(r"\b(?:tag|v3\.3\.0)\b", question, re.I):
            continue
        if re.search(r"\b(?:push|publish|delete|move|force|overwrite|prod)\b", question, re.I):
            continue
        versions = re.findall(r"v\d+\.\d+\.\d+", question)
        if not versions or set(versions) == {"v3.3.0"}:
            return True
    return False


def blocked(text):
    """Recognize a stated block, except a denial that one exists."""
    pattern = r"\b(?:blocked by|blocked on|cannot continue because|can't continue because)\b"
    for match in re.finditer(pattern, text, re.I):
        before = text[max(0, match.start() - 20) : match.start()]
        if not re.search(r"(?:not |no longer )$", before, re.I):
            return True
    return False
