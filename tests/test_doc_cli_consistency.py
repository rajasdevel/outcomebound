"""Every command the documents give runs where its reader runs it: a launcher verb that exists,
a script that exists, and never the engine's module form in text OutcomeBound ships."""

import os
import re
import shlex
from collections.abc import Iterator
from pathlib import Path

from outcomebound_tools.__main__ import VERBS

ROOT = Path(__file__).resolve().parent.parent
# `python3 -m outcomebound_tools.<module>` runs only inside this checkout; with the checkout on
# PYTHONPATH it lets a project's own files shadow the engine. The launcher runs from anywhere.
MODULE_FORM = re.compile(r"\bpython3?\s+-m\s+outcomebound_tools\b")
# `outcomebound <verb>` where a command starts: a line, a code span, `$(`, or a pipe.
LAUNCHER_VERB = re.compile(r"(?:^|[\s(`|;&])outcomebound ([a-z_-]+)", re.MULTILINE)


def _active_docs() -> Iterator[Path]:
    yield ROOT / "AGENTS.md"
    yield ROOT / "README.md"
    yield ROOT / "OutcomeBound.md"
    yield from ROOT.glob("skills/**/*.md")
    # A selected fragment is composed into an adopting project's AGENTS.md.
    yield from ROOT.glob("fragments/**/*.md")
    yield from ROOT.glob("templates/**/*.md")


# What OutcomeBound ships to an adopting project's agent: the contract, the README, the kernel
# and the other templates, the skills, the fragments, the guides and the schemas. This
# repository's own AGENTS.md and its designs run inside the checkout and are not read.
SHIPPED_TEXT = (
    "OutcomeBound.md",
    "README.md",
    "skills/**/*",
    "fragments/**/*",
    "templates/**/*",
    "docs/*.md",
    "schemas/*.json",
)


def test_no_shipped_text_gives_the_engines_module_form():
    paths = sorted({path for pattern in SHIPPED_TEXT for path in ROOT.glob(pattern)})
    assert any(path.name == "managed-block.agents.md.tmpl" for path in paths)
    found = [
        f"{path.relative_to(ROOT).as_posix()}:{number}"
        for path in paths
        if path.is_file()
        for number, line in enumerate(
            path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1
        )
        if MODULE_FORM.search(line)
    ]
    assert not found, f"give `outcomebound <verb>` instead of the module form: {found}"


def test_every_advertised_launcher_verb_exists():
    verbs = {"home", *VERBS}
    advertised: dict[str, str] = {}
    for path in _active_docs():
        if path.is_file():
            for verb in LAUNCHER_VERB.findall(path.read_text(encoding="utf-8")):
                advertised.setdefault(verb, path.relative_to(ROOT).as_posix())
    assert advertised
    unknown = {verb: where for verb, where in advertised.items() if verb not in verbs}
    assert not unknown, f"documented `outcomebound` verbs the launcher does not have: {unknown}"


SCRIPT_INVOKE = re.compile(
    r"(?:bash |\$\(OB_ENGINE\) |\./)?(scripts/[a-z0-9_-]+\.(?:sh|py)|scripts/outcomebound\b)"
)


def test_every_documented_script_exists_and_is_executable():
    referenced = set()
    for path in _active_docs():
        if path.is_file():
            referenced.update(SCRIPT_INVOKE.findall(path.read_text(encoding="utf-8")))
    assert referenced, "no scripts are documented anywhere"
    broken = [
        name
        for name in sorted(referenced)
        if not (ROOT / name).is_file() or not os.access(ROOT / name, os.X_OK)
    ]
    assert not broken, f"documented scripts missing or not executable: {broken}"


# The tests above hold `python3 -m` forms to the engine's CLIs, which leaves
# `python3 -c 'import outcomebound_tools…'` — an instruction that binds a reader to an
# internal function no CLI promises to keep. Shipped instruction text reaches the engine
# through a CLI; a `-c` program that imports it stands only where no CLI reports the same
# thing, named here with why.
PYTHON_C_ALLOWED: dict[tuple[str, str], str] = {}
PYTHON_C = re.compile(r"\bpython3?\s+-c\s+")
ENGINE_IMPORT = re.compile(r"\boutcomebound_tools\b(?:\.(\w+))?")
SHIPPED_INSTRUCTIONS = ("skills/**/*.md", "fragments/**/*.md")


def _c_programs(text: str) -> Iterator[tuple[int, str]]:
    """(line, program) for each `python3 -c` in a text, the program read as one shell word."""

    for match in PYTHON_C.finditer(text):
        rest = text[match.end() :]
        lexer = shlex.shlex(rest, posix=True)
        lexer.whitespace_split = True
        lexer.commenters = ""
        try:
            program = lexer.get_token() or ""
        except ValueError:
            program = rest.split("\n", 1)[0]
        yield text.count("\n", 0, match.start()) + 1, program


def python_c_engine_imports(root: Path) -> tuple[list[str], set[tuple[str, str]]]:
    """The `python3 -c` engine imports under `root` not allowed, and the allowed ones seen."""

    offenders, allowed = [], set()
    paths = sorted(path for pattern in SHIPPED_INSTRUCTIONS for path in root.glob(pattern))
    for path in paths:
        relative = path.relative_to(root).as_posix()
        for line, program in _c_programs(path.read_text(encoding="utf-8")):
            for module in ENGINE_IMPORT.findall(program):
                key = (relative, module or "outcomebound_tools")
                if key in PYTHON_C_ALLOWED:
                    allowed.add(key)
                else:
                    offenders.append(f"{relative}:{line} runs `python3 -c` into {key[1]}")
    return offenders, allowed


def test_no_shipped_instruction_runs_python_c_into_the_engine() -> None:
    offenders, allowed = python_c_engine_imports(ROOT)
    assert not offenders, (
        "name the engine's launcher verb (`outcomebound <verb>`) instead, or allow "
        f"the entry in PYTHON_C_ALLOWED with the reason no CLI covers it: {offenders}"
    )
    stale = set(PYTHON_C_ALLOWED) - allowed
    assert not stale, f"PYTHON_C_ALLOWED names a `python3 -c` that is gone: {sorted(stale)}"
