"""Opaque names: nothing the runner gives a call names its fixture, its variant or its arm.

Each test builds real fixtures through `run_one`, with the real Codex or Claude Code harness
driving a stand-in `codex` or `claude` that records what it was given and calls no model: its
argv, its environment, its working directory, the prompt on its stdin, and its own process title
as the system shows it. The test then reads the kept workspace: every file, every Git object and
the Git configuration, remotes and refs. Each surface has a negative control: the same check,
with a label planted in that surface, must fail.

Not covered: files outside the workspace that the model reads on its own (graders, references,
other runs' results), which only denied reads would keep from it. The real CLIs' own session
records (Claude Code's projects folder, Codex's session metadata) are derived here from what the
call was given; that the real CLIs add nothing else that names a label is UNVERIFIED without a
model call.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from evals import native_receipts
from evals.harnesses import claude_code as cc
from evals.harnesses import codex as cx
from tests.eval_helpers import RUN, load
from tests.portable import needs_posix_bash

pytestmark = needs_posix_bash

# Two fixtures per harness: one with a stub on the call's PATH and a Git remote in its seed,
# one with watched paths (a watch log the call must not write).
FIXTURES = ("v2-rs-review-until-clean", "v2-dg-wrong-hypothesis")
ARM_KIND = "current"
ARM_LABEL = "arm-q7zx"
# The stand-in for both CLIs: it records what it was given, in a file named by its pid under
# $STANDIN_RECORDS, and exits as a call that ran no model.
STANDIN = r"""#!/usr/bin/env python3
import json, os, subprocess, sys
from pathlib import Path

if sys.argv[1:2] == ["--version"]:
    print("0.0.0 (stand-in)")
    sys.exit(0)
prompt = sys.stdin.read()
proc = Path("/proc/self/cmdline")
if proc.is_file():
    title = proc.read_bytes().replace(b"\0", b" ").decode("utf-8", "replace").strip()
else:
    title = subprocess.run(["ps", "-o", "args=", "-p", str(os.getpid())],
                           capture_output=True, text=True).stdout.strip()
record = {"argv": sys.argv, "env": dict(os.environ), "cwd": os.getcwd(), "prompt": prompt,
          "title": title}
out = Path(os.environ["STANDIN_RECORDS"], f"{os.getpid()}.json")
out.write_text(json.dumps(record), encoding="utf-8")
"""
# The PATH folders `call_path` makes in the workspace root: the arm's launcher alone, and a
# mirror of a PATH entry less its `outcomebound`. Their names are random and name no label.
LAUNCHERS = re.compile(r"ob-(?:launcher|path)-[A-Za-z0-9_]+")
GIT_COMMANDS = (
    ("config", "--list", "--show-origin"),
    ("remote", "-v"),
    ("for-each-ref", "--format=%(refname) %(objectname)"),
    ("symbolic-ref", "-q", "HEAD"),
    ("log", "--all", "--format=%an <%ae> %cn <%ce>%n%B"),
    ("cat-file", "--batch-all-objects", "--batch"),
)


def labels(fixture: str) -> tuple[str, ...]:
    """What names a run: the fixture, its variant (the name after a `v2-xx-` family prefix)
    and the arm's label."""

    variant = fixture.split("-", 2)[2] if re.match(r"v2-[a-z]{2}-", fixture) else fixture
    return (fixture, variant, ARM_LABEL)


def found(text: str, names: tuple[str, ...]) -> list[str]:
    lowered = text.lower()
    return [name for name in names if name.lower() in lowered]


def _git_dirs(workspace: Path) -> Iterator[Path]:
    for folder, _dirs, _files in os.walk(workspace):
        here = Path(folder)
        if (here / "HEAD").is_file() and (here / "objects").is_dir():
            yield here


def evidence(record: dict[str, Any], root: Path) -> dict[str, Any]:
    """Every surface of one call: its record from the stand-in, the kept workspace's files and
    Git data read with the call's own environment, and the paths of what the call was given
    (workspace, stubs, watch log, cell) below the workspace root."""

    workspace = Path(record["cwd"])
    env = {**record["env"], "GIT_PAGER": "cat", "PAGER": "cat"}
    git: list[str] = []
    for folder in _git_dirs(workspace):
        for words in GIT_COMMANDS:
            done = subprocess.run(
                ["git", "--git-dir", str(folder), *words],
                capture_output=True,
                env=env,
                cwd=workspace,
                timeout=60,
                check=False,
            )
            git.append(done.stdout.decode("utf-8", "replace"))
    # A file under `.git/objects` is compressed: `git cat-file` above reads it.
    files = {
        str(path.relative_to(workspace)): path.read_bytes().decode("utf-8", "replace")
        for folder, _dirs, names in os.walk(workspace)
        for path in (Path(folder, name) for name in names)
        if not (".git" in path.relative_to(workspace).parts and "objects" in path.parts)
    }
    named = [Path(path) for path in _paths_named(record)]
    given = [workspace, *(path for path in named if root in path.parents)]
    return {
        "paths": sorted({str(path) for path in given}),
        # The entries of the workspace root the call is given: its workspace, the call's own
        # files beside it, and the launcher folders of its PATH; a name below a workspace is
        # the seed's, read with the files.
        "entries": sorted({path.relative_to(root).parts[0] for path in given}),
        "env": [f"{key}={value}" for key, value in record["env"].items()],
        "argv": list(record["argv"]),
        "title": record["title"],
        "prompt": record["prompt"],
        "git": git,
        "files": files,
        # Claude Code keeps a session under `projects/<the working directory, each character
        # that is not a letter or digit written as '-'>`; Codex records the working directory.
        "session": re.sub(r"[^A-Za-z0-9]", "-", record["cwd"]),
    }


def _paths_named(record: dict[str, Any]) -> list[str]:
    """Every absolute path the call's argv and environment name."""

    words = [*record["argv"], *record["env"].values()]
    return [
        part
        for word in words
        for part in re.split(r"[\s:\",\[\]{}]+", word)
        if part.startswith("/")
    ]


def leaks(seen: dict[str, Any], names: tuple[str, ...]) -> dict[str, list[str]]:
    """Each surface that names a label, with what it names. A path below the workspace root must
    be an opaque name (`ws-<16 hex>`, with its suffix) and name neither a label nor the arm's
    kind; the other surfaces must not hold a label."""

    strange = [
        part
        for part in seen["entries"]
        if not (RUN.OPAQUE_ENTRY.fullmatch(part) or LAUNCHERS.fullmatch(part))
        or found(part, (*names, ARM_KIND))
    ]
    hits = {
        "paths": strange + [n for path in seen["paths"] for n in found(path, names)],
        "env": [n for line in seen["env"] for n in found(line, names)],
        "argv": [n for word in seen["argv"] for n in found(word, names)],
        "title": found(seen["title"], names),
        "prompt": found(seen["prompt"], names),
        "git": [n for text in seen["git"] for n in found(text, names)],
        "files": [
            f"{path}: {n}" for path, text in seen["files"].items() for n in found(text, names)
        ],
        "session": found(seen["session"], names),
    }
    return {surface: items for surface, items in hits.items() if items}


# --- the runs -----------------------------------------------------------------------------------


@pytest.fixture
def layout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    """A loop-like layout: run folders named after the arm and the fixture (as loop.py names
    them) and a workspace root of their own. The stand-in calls run no sandbox, so the test's
    temporary folder stands for a folder the sandbox does not grant, as a workspace root outside
    the temporary folders is."""

    for module in (native_receipts, cx, cc, RUN):
        monkeypatch.setattr(module, "temporary_write_roots", lambda: (tmp_path / "granted",))
    tools = tmp_path / "tools"
    tools.mkdir()
    for cli in ("codex", "claude"):
        (tools / cli).write_text(STANDIN, encoding="utf-8")
        (tools / cli).chmod(0o755)
    places = {
        "tools": tools,
        "records": tmp_path / "records",
        "results": tmp_path / "results" / "plan",
        "root": tmp_path / "workspaces" / "plan",
        "codex_home": tmp_path / "codex-home",
    }
    for key in ("records", "results", "root", "codex_home"):
        places[key].mkdir(parents=True)
    return places


def _run(harness_name: str, places: dict[str, Path]) -> dict[str, dict[str, Any]]:
    """Run each fixture once under the arm through the named harness, each into a run folder
    named `<arm>-r1-<fixture>` as loop.py names it; each fixture's record from the stand-in."""

    env = {
        **RUN.child_env(),
        "CODEX_HOME": str(places["codex_home"]),
        "STANDIN_RECORDS": str(places["records"]),
    }
    if harness_name == RUN.CLAUDE:
        RUN.set_harness(RUN.CLAUDE)
        harness: Any = cc.ClaudeCodeHarness(lambda: env, RUN._run, 60)
    else:
        harness = cx.CodexHarness(lambda: env, RUN._run, 60)
    try:
        base = RUN.run_arm(ARM_KIND, RUN.NO_ELEMENTS)
        path = RUN.call_path(base, str(places["root"]))
        status = {
            "model": "m-standin",
            "effort": "medium",
            "repetition": 1,
            "workspace_root": str(places["root"]),
            "harness": harness_name,
            "arm": ARM_LABEL,
        }
        records = {}
        for fixture in FIXTURES:
            out = places["results"] / f"{ARM_LABEL}-r1-{fixture}"
            out.mkdir()
            before = set(places["records"].iterdir())
            arm = RUN.fixture_arm(fixture, base)
            RUN.run_one(out, status, fixture, arm, f"{places['tools']}{os.pathsep}{path}", harness)
            (made,) = set(places["records"].iterdir()) - before
            records[fixture] = json.loads(made.read_text(encoding="utf-8"))
            meta = json.loads((out / f"{fixture}.meta.json").read_text(encoding="utf-8"))
            assert (
                Path(meta["fixture_repo"]).name
                == meta["workspace_id"]
                == Path(records[fixture]["cwd"]).name
            ), "the record maps the opaque id to its fixture"
        return records
    finally:
        RUN.set_harness(RUN.HARNESS)


@pytest.mark.parametrize("harness_name", [RUN.HARNESS, RUN.CLAUDE])
def test_no_surface_a_call_is_given_names_its_fixture_variant_or_arm(
    harness_name: str, layout: dict[str, Path]
) -> None:
    """Breaks if the workspace path or a parent, the call's environment, argv or process title,
    the prompt, the workspace's Git data or files, or the session folder the CLI derives from the
    working directory names the fixture, its variant or the arm."""

    records = _run(harness_name, layout)
    for fixture, record in records.items():
        seen = evidence(record, layout["root"])
        assert leaks(seen, labels(fixture)) == {}, fixture
        assert seen["git"] and any(seen["files"]), "the evidence was read"
    stubbed = records[FIXTURES[0]]
    stubs = [p for p in stubbed["env"]["PATH"].split(os.pathsep) if p.endswith(".stubs")]
    assert len(stubs) == 1 and Path(stubs[0]).parent == layout["root"], "stubs beside it"
    assert "remote.origin.url" in "".join(evidence(stubbed, layout["root"])["git"])
    if harness_name == RUN.CLAUDE:
        home = Path(stubbed["env"]["HOME"]).parent
        assert home.parent == layout["root"] and home.name.endswith(".claude-home")
        settings = json.loads(stubbed["argv"][stubbed["argv"].index("--settings") + 1])
        denied = settings["sandbox"]["filesystem"]["denyRead"]
        assert str(layout["results"]) in denied, "the run folders are denied as one folder"
        watched = records[FIXTURES[1]]
        writes = json.loads(watched["argv"][watched["argv"].index("--settings") + 1])
        assert any(p.endswith(".watch.jsonl") for p in writes["sandbox"]["filesystem"]["denyWrite"])


@pytest.mark.parametrize("harness_name", [RUN.HARNESS, RUN.CLAUDE])
def test_NEGATIVE_CONTROL_a_label_planted_in_each_surface_is_caught(
    harness_name: str, layout: dict[str, Path]
) -> None:
    """Breaks if the check above cannot see a label in one of its surfaces."""

    fixture = FIXTURES[0]
    record = _run(harness_name, layout)[fixture]
    names = labels(fixture)
    clean = evidence(record, layout["root"])
    assert leaks(clean, names) == {}
    workspace = Path(record["cwd"])

    planted: dict[str, dict[str, Any]] = {
        "env": {**record, "env": {**record["env"], "OB_CELL": fixture}},
        "argv": {**record, "argv": [*record["argv"], "--label", ARM_LABEL]},
        "title": {**record, "title": f"{record['title']} {names[1]}"},
        "prompt": {**record, "prompt": record["prompt"] + f"\nYou are in {fixture}.\n"},
    }
    for surface, changed in planted.items():
        assert surface in leaks(evidence(changed, layout["root"]), names), surface

    # The path: a workspace named after its fixture, as the runner named it before.
    named = layout["root"] / f"{fixture}-r1"
    named.mkdir()
    seen = evidence({**record, "cwd": str(named)}, layout["root"])
    assert {"paths", "session"} <= set(leaks(seen, names))
    # A parent named after the arm's kind, which the label check alone would not see.
    kind = layout["root"] / ARM_KIND / "ws-0123456789abcdef"
    kind.mkdir(parents=True)
    assert "paths" in leaks(evidence({**record, "cwd": str(kind)}, layout["root"]), names)

    # Git: a remote, a branch, a commit message and an author, each planted in a copy of the
    # workspace (an object, once written, stays readable).
    git_env = {**record["env"], "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
    commit = ["commit", "-q", "--allow-empty"]
    for words in (
        ["remote", "add", "planted", f"https://example.invalid/{fixture}.git"],
        ["branch", f"{names[1]}-work"],
        ["-c", "user.name=plain", "-c", "user.email=p@example.invalid", *commit, "-m", fixture],
        ["-c", f"user.name={ARM_LABEL}", "-c", "user.email=p@example.invalid", *commit, "-m", "x"],
    ):
        copy = layout["root"] / RUN.opaque_id(layout["root"])
        shutil.copytree(workspace, copy, symlinks=True)
        moved = {**record, "cwd": str(copy)}
        assert "git" not in leaks(evidence(moved, layout["root"]), names), words
        subprocess.run(["git", "-C", str(copy), *words], env=git_env, check=True, timeout=60)
        assert "git" in leaks(evidence(moved, layout["root"]), names), words

    # A file anywhere in the workspace.
    (workspace / "docs").mkdir(exist_ok=True)
    (workspace / "docs" / "note.md").write_text(f"Fixture: {fixture}\n", encoding="utf-8")
    assert "files" in leaks(evidence(record, layout["root"]), names)


def test_each_run_gets_a_new_id_and_the_record_maps_it(tmp_path: Path) -> None:
    """Breaks if an id is derived from what it hides, or two runs share one."""

    ids = {RUN.opaque_id(tmp_path) for _ in range(200)}
    assert len(ids) == 200 and all(RUN.OPAQUE.fullmatch(ident) for ident in ids)
    out = tmp_path / "out"
    out.mkdir()
    root = tmp_path / "root"
    root.mkdir()
    first, place = RUN.call_place(root, out, FIXTURES[0])
    second, _ = RUN.call_place(root, out, FIXTURES[0])
    assert first != second
    assert place.workspace == root / first and place.keep == out / f"{FIXTURES[0]}.native.jsonl"


def test_without_a_root_outside_the_temporary_folders_the_call_files_go_in_the_run_folder(
    tmp_path: Path,
) -> None:
    """The fallback: with no root, or one in a temporary folder the sandbox lets the model write,
    the call's own files keep the opaque id but go in the run folder."""

    out = tmp_path / "out"
    ident, place = RUN.call_place(None, out, FIXTURES[1])
    assert place.workspace is not None and place.workspace.name == ident
    assert place.stubs == out / f"{ident}.stubs" and place.cell == out / f"{ident}.claude-home"
    assert RUN.beside_workspaces(None) is False
    assert RUN.beside_workspaces(Path(RUN.tempfile.gettempdir()) / "root") is False


def test_a_grader_reads_a_citation_under_an_opaque_workspace_from_its_kept_copy(
    tmp_path: Path,
) -> None:
    """Breaks if a grader that maps an answer's absolute paths into the tree it grades (a rescore
    grades a copy at another path) stops knowing the workspace's opaque name."""

    cited = load("cited_check", "evals/fixtures/dirty-review/checks/cited.py")
    (tmp_path / "parser.py").write_text("one\ntwo\n", encoding="utf-8")
    text = "See /work/ws-0123456789abcdef/parser.py:2 and /work/ob-fixture-ab12/parser.py:1."
    assert cited.problems(text, tmp_path) == (2, [])
    assert cited.problems("See /work/plain/parser.py:2.", tmp_path)[1], "a path elsewhere"


def test_loop_starts_a_cell_with_no_fixture_or_arm_in_the_runner_s_process_title(
    tmp_path: Path,
) -> None:
    """Breaks if loop.py puts a cell's fixture or arm back on run.py's command line, which a
    call's `ps` can show, or if run.py stops reading its options from the file."""

    loop = load("opaque_loop", "evals/loop.py")
    script = tmp_path / "show.py"
    script.write_text(
        "import sys\nfrom pathlib import Path\n"
        "print(sys.argv[1:])\nprint(Path(sys.argv[1][1:]).read_text(encoding='utf-8'))\n",
        encoding="utf-8",
    )
    log = tmp_path / "results" / "plan" / f"{ARM_LABEL}-r1-{FIXTURES[0]}.log"
    words = ("--fixtures", FIXTURES[0], "--arm", ARM_KIND, "--arm-label", ARM_LABEL)
    assert loop.run_cell((sys.executable, str(script), *words), log, tmp_path) == 0
    title, listing = log.read_text(encoding="utf-8").split("\n", 1)
    (argument,) = json.loads(title.replace("'", '"'))
    assert argument.startswith("@") and not found(argument, labels(FIXTURES[0]))
    assert listing.split() == list(words)
    assert not list(log.parent.glob(".run-args-*")), "the file goes when run.py exits"
    options = tmp_path / "options"
    options.write_text("".join(f"{word}\n" for word in words), encoding="utf-8")
    _, parsed = RUN._arguments([f"@{options}"])
    assert (parsed.fixtures, parsed.arm, parsed.arm_label) == (FIXTURES[0], ARM_KIND, ARM_LABEL)
