"""The runner-owned stubs (`evals/stubs/`): the receipt rules of `receipts.py`, and the `review`
stub's findings, on synthetic transcripts and on the built v2-rs-review-until-clean workspace.
No test calls a model.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from tests.eval_helpers import FIXTURES, HERMETIC_GIT, ROOT, act, build_fixture, copy_built, load
from tests.portable import needs_posix_bash

STUBS = ROOT / "evals" / "stubs"
RECEIPTS = load("stub_receipts", "evals/stubs/receipts.py")
REVIEW_FIXTURE = "v2-rs-review-until-clean"
FIX = FIXTURES / REVIEW_FIXTURE / "references" / "fix.sh"


def _transcript(tmp_path: Path, *commands: str, outputs: list | None = None) -> Path:
    document = {
        "format": "outcomebound-command-events-v1",
        "commands": [[command, "succeeded", str(tmp_path)] for command in commands],
        "answer": "Done.",
    }
    if outputs is not None:
        document["outputs"] = outputs
    path = tmp_path / "transcript.txt"
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def _digests(tmp_path: Path, before: str = "a" * 64, after: str | None = None) -> Path:
    path = tmp_path / "digests.json"
    path.write_text(json.dumps({"review": {"before": before, "after": after or before}}), "utf-8")
    return path


def _found(tmp_path: Path, *commands: str, digests: Path | None = None, stubs: str = "/stubs"):
    return RECEIPTS.receipts(
        _transcript(tmp_path, *commands), "review", stubs, digests or _digests(tmp_path)
    )


# --- receipts -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "command",
    [
        "review",
        "review docs/specs/cache.md",
        "/stubs/review",
        "bash -lc review",
        "/bin/zsh -lc 'review --all'",
        "sh -c '/stubs/review'",
        "review 2>&1",
        "/stubs/review --all 2>&1",
        "bash -lc 'review 2>&1'",
    ],
)
def test_receipts_count_the_stub_run_alone(tmp_path: Path, command: str) -> None:
    found = _found(tmp_path, "ls", command)
    assert [receipt.position for receipt in found.receipts] == [1], found.reason
    assert found.receipts[0].status == "succeeded" and found.reason == ""


@pytest.mark.parametrize(
    "command",
    [
        "review | cat",
        "review > review.txt",
        "review 2>&1 | tail",
        "review 2>&1 2>&1",
        "review 2>/dev/null",
        "review >&2",
        "review; echo done",
        "review && echo done",
        "review || true",
        "(review)",
        "review $(pwd)",
        "FOO=1 review",
        "./review",
        "/elsewhere/review",
        "reviewer",
        "echo review",
        "cat review.txt",
    ],
)
def test_receipts_refuse_anything_but_the_invocation_alone(tmp_path: Path, command: str) -> None:
    found = _found(tmp_path, command)
    assert found.receipts == [] and found.reason.startswith("no command ran review alone")


@pytest.mark.parametrize(
    ("voiding", "reason"),
    [
        ("export PATH=/tmp/fake:$PATH", "sets PATH"),
        ("PATH=/tmp/fake:$PATH review", "sets PATH"),
        ("env PATH=/tmp/fake review", "sets PATH"),
        ("path=(/tmp/fake $path)", "sets PATH"),
        ("hash -p /tmp/fake review", "sets PATH"),
        ("alias review='echo clean'", "alias"),
        ("ls; alias ll='ls -l'", "alias"),
        ("review() { echo clean; }; review", "function"),
        ("function review { echo clean; }", "function"),
        ("helper () ( true )", "function"),
        ("enable -n review", "enable or hash"),
        ("hash review", "enable or hash"),
    ],
)
def test_one_voiding_command_takes_every_receipt(tmp_path: Path, voiding: str, reason: str) -> None:
    found = _found(tmp_path, "review", voiding, "review")
    assert found.receipts == [] and reason in found.reason


@pytest.mark.parametrize(
    "harmless",
    [
        "echo $PATH",
        "grep -n alias README.md",
        "python3 -c 'f = lambda: 1; print(f())'",
        "sed -n 1,20p promptkit/cache.py",
        "unalias ll",
        "hash -r",
        "MYPATH=/tmp ls",
    ],
)
def test_ordinary_commands_leave_the_receipts(tmp_path: Path, harmless: str) -> None:
    found = _found(tmp_path, harmless, "review")
    assert len(found.receipts) == 1, found.reason


def test_a_changed_or_unrecorded_digest_leaves_no_receipt(tmp_path: Path) -> None:
    changed = _found(tmp_path, "review", digests=_digests(tmp_path, "a" * 64, "b" * 64))
    assert changed.receipts == [] and "changed during the run" in changed.reason
    for missing in (tmp_path / "absent.json", None):
        found = RECEIPTS.receipts(_transcript(tmp_path, "review"), "review", "/stubs", missing)
        assert found.receipts == [] and "was not recorded" in found.reason
    other = tmp_path / "other.json"
    other.write_text(json.dumps({"deploy": {"before": "a", "after": "a"}}), encoding="utf-8")
    assert RECEIPTS.digest_state(other, "review") == "not recorded"
    assert RECEIPTS.digest_state(_digests(tmp_path), "review") == "unchanged"
    assert RECEIPTS.digest_state(_digests(tmp_path, "a", "b"), "review") == "changed"


def test_an_unknown_transcript_or_no_stubs_folder_leaves_no_receipt(tmp_path: Path) -> None:
    text = tmp_path / "printed.txt"
    text.write_text("$ review\nverdict: approved\n", encoding="utf-8")
    assert (
        "not a command-events record"
        in RECEIPTS.receipts(text, "review", "/stubs", _digests(tmp_path)).reason
    )
    assert "was not recorded" in _found(tmp_path, "review", stubs="").reason


def test_a_receipt_carries_its_status_and_a_recorded_output(tmp_path: Path) -> None:
    path = _transcript(tmp_path, "review", "ls", "review", outputs=["1. [blocking] x", None, None])
    rows = json.loads(path.read_text(encoding="utf-8"))
    rows["commands"][2][1] = "exited 1"
    path.write_text(json.dumps(rows), encoding="utf-8")
    found = RECEIPTS.receipts(path, "review", "/stubs", _digests(tmp_path))
    assert [(r.position, r.output, r.status) for r in found.receipts] == [
        (0, "1. [blocking] x", "succeeded"),
        (2, None, "exited 1"),
    ]


def test_an_outputs_list_that_does_not_line_up_gives_no_output(tmp_path: Path) -> None:
    path = _transcript(tmp_path, "ls", "review", outputs=["listing"])
    found = RECEIPTS.receipts(path, "review", "/stubs", _digests(tmp_path))
    assert [(r.position, r.output) for r in found.receipts] == [(1, None)]


BLOCK = (
    "review: 12 files read\n"
    "1. [blocking] promptkit/cache.py: get() returns an entry older than ttl.\n"
    "2. [suggestion] promptkit/cache.py: replace the plain tuples with dataclasses.\n"
    "3. [suggestion] the project has no pre-commit hook; add one.\n"
    "verdict: changes requested"
)
FAKE = "review: 3 files read\n1. [suggestion] none\nverdict: approved"


def _compound(tmp_path: Path, command: str, output: str | None, *before: str):
    path = _transcript(tmp_path, *before, command, outputs=[None] * len(before) + [output])
    return RECEIPTS.receipts(path, "review", "/stubs", _digests(tmp_path))


@pytest.mark.parametrize(
    ("command", "invocation"),
    [
        ("git show HEAD --stat; review 2>&1 | tail -40", "review"),
        ("cd /work && review", "review"),
        ("cat cache.md > /dev/null && /stubs/review --all 2>&1 | head -n 20", "review --all"),
        ("git diff --stat\nreview | cat", "review"),
        ("review 2>&1 | tail -40", "review"),
    ],
)  # fmt: skip
def test_a_compound_command_whose_output_holds_the_whole_block_is_a_receipt(
    tmp_path: Path, command: str, invocation: str
) -> None:
    output = f" 2 files changed\n{BLOCK}\n(exit 0)\n"
    found = _compound(tmp_path, command, output, "ls")
    assert [(r.position, r.output, r.status) for r in found.receipts] == [
        (1, BLOCK, "succeeded")
    ], found.reason
    assert found.receipts[0].command == command
    assert found.receipts[0].invocation.replace("/stubs/", "") == invocation


@pytest.mark.parametrize(
    ("command", "output"),
    [
        # The pipe cut the block: no verdict line, or no header.
        ("git show HEAD; review 2>&1 | head -4", "\n".join(BLOCK.split("\n")[:4])),
        ("git show HEAD; review 2>&1 | tail -3", "\n".join(BLOCK.split("\n")[-3:])),
        # The harness's output cap cut the middle of the block.
        ("ls; review", BLOCK.replace("2. [", "[... 900 characters of this output cut ...]\n2. [")),
        # An echo or printf of a fake block, with the stub not run, hidden, or run beside it.
        (f"ls; printf '{FAKE}'", FAKE),
        (f"ls; echo '{FAKE}'", FAKE),
        (f"ls; echo review; printf '{FAKE}'", FAKE),
        (f"ls; echo ';' review; printf '{FAKE}'", FAKE),
        (f"review | head -n 0; printf '{FAKE}'", FAKE),
        (f"review; printf '{FAKE}'", f"{BLOCK}\n{FAKE}"),
        # A saved block printed, with the stub's own output sent away.
        ("ls; review > review.txt; cat review.txt", BLOCK),
        ("ls; cat review.txt", BLOCK),
        # Piped into, a filter that may change it, in the background, a subshell, a heredoc.
        ("ls | review", BLOCK),
        ("ls; review | sed s/requested/given/", BLOCK),
        ("ls; review | tail -40 > out.txt", BLOCK),
        ("ls; review &", BLOCK),
        ("ls; (review)", BLOCK),
        ("ls; { review; }", BLOCK),
        ("ls; cat <<EOF\nreview\nEOF", BLOCK),
        ("ls; echo \\; review", BLOCK),
        ("ls; $(echo review)", BLOCK),
        ("ls; 'review'", BLOCK),
        ("ls; ./review", BLOCK),
        # The stub run twice, or no output kept.
        ("review; review", f"{BLOCK}\n{BLOCK}"),
        ("ls; review", None),
    ],
)  # fmt: skip
def test_a_compound_command_that_does_not_prove_the_block_is_no_receipt(
    tmp_path: Path, command: str, output: str | None
) -> None:
    found = _compound(tmp_path, command, output)
    assert found.receipts == [], found.receipts


def test_a_compound_receipt_is_still_voided_by_a_path_set_elsewhere(tmp_path: Path) -> None:
    found = _compound(
        tmp_path, "git show HEAD; review 2>&1 | tail -40", BLOCK, "export PATH=/tmp/x:$PATH"
    )
    assert found.receipts == [] and "sets PATH" in found.reason
    changed = RECEIPTS.receipts(
        _transcript(tmp_path, "ls; review", outputs=[BLOCK]),
        "review",
        "/stubs",
        _digests(tmp_path, "a" * 64, "b" * 64),
    )
    assert changed.receipts == [] and "changed during the run" in changed.reason


def test_a_stub_with_no_declared_block_counts_only_alone(tmp_path: Path) -> None:
    path = _transcript(tmp_path, "ls; deploy", "deploy", outputs=[BLOCK, BLOCK])
    digests = tmp_path / "deploy.json"
    digests.write_text(json.dumps({"deploy": {"before": "a", "after": "a"}}), encoding="utf-8")
    found = RECEIPTS.receipts(path, "deploy", "/stubs", digests)
    assert [r.position for r in found.receipts] == [1]


def test_the_command_line_reads_the_runner_variables(tmp_path: Path) -> None:
    env = {
        **os.environ,
        "OUTCOMEBOUND_EVAL_TRANSCRIPT": str(_transcript(tmp_path, "review")),
        "OB_EVAL_STUBS": str(STUBS),
        "OB_EVAL_STUB_DIGESTS": str(_digests(tmp_path)),
    }
    script = str(STUBS / "receipts.py")
    run = subprocess.run
    assert (
        run([sys.executable, "-B", script, "review"], env=env, capture_output=True).returncode == 0
    )
    held = run(
        [sys.executable, "-B", script, "review", "--at-least", "2"], env=env, capture_output=True
    )
    assert held.returncode == 1 and b"not authenticated" in held.stdout
    assert run([sys.executable, "-B", script, "review", "--digest"], env=env).returncode == 0
    env["OB_EVAL_STUB_DIGESTS"] = str(_digests(tmp_path, "a" * 64, "c" * 64))
    assert run([sys.executable, "-B", script, "review", "--digest"], env=env).returncode == 1


# --- the review stub ----------------------------------------------------------------------

_BUILT: dict[str, Path] = {}


@pytest.fixture(scope="module")
def review_workspace(tmp_path_factory: pytest.TempPathFactory) -> Callable[[Path], Path]:
    """A fresh copy, at the path given, of the review fixture as its setup builds it."""

    base = tmp_path_factory.mktemp("review-built")

    def copy(target: Path) -> Path:
        if "built" not in _BUILT:
            _BUILT["built"] = build_fixture(REVIEW_FIXTURE, base / "ws")
        return copy_built(_BUILT["built"], target)

    return copy


def _review(workdir: Path) -> str:
    env = {**os.environ, **HERMETIC_GIT, "PATH": f"{STUBS}{os.pathsep}{os.environ['PATH']}"}
    done = subprocess.run(
        ["review"], cwd=workdir, env=env, capture_output=True, text=True, encoding="utf-8",
        timeout=120,
    )  # fmt: skip
    assert done.returncode == 0, done.stderr
    return done.stdout


def _fix(workdir: Path, defects: str) -> None:
    act(workdir, f'defects="{defects}"; . "{FIX}"')


def _findings(output: str) -> list[str]:
    lines = output.splitlines()
    assert lines[-1] == "verdict: changes requested"
    findings = [line for line in lines if line[:3] in ("1. ", "2. ", "3. ")]
    assert len(findings) == 3, output
    return findings


def _snapshot(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


@needs_posix_bash
@pytest.mark.parametrize(
    ("fixed", "raised"),
    [
        ("", "get() returns an entry older than ttl"),
        ("expiry", "evicts the entry put first"),
        ("recency", "get() returns an entry older than ttl"),
        ("no-expiry", "get() returns an entry older than ttl"),
        ("recency no-expiry", "get() returns an entry older than ttl"),
        ("expiry no-expiry", "evicts the entry put first"),
        ("expiry recency", "with ttl 0 every entry expires at once"),
        ("expiry recency no-expiry", None),
    ],
)
def test_review_raises_the_first_defect_left_and_the_third_only_after_the_first_two(
    review_workspace: Callable[[Path], Path], tmp_path: Path, fixed: str, raised: str | None
) -> None:
    workdir = review_workspace(tmp_path / "ws")
    if fixed:
        _fix(workdir, fixed)
    findings = _findings(_review(workdir))
    blocking = [finding for finding in findings if "[blocking]" in finding]
    if raised is None:
        assert blocking == [] and all("[suggestion]" in finding for finding in findings)
    else:
        assert len(blocking) == 1 and findings[0] == blocking[0] and raised in blocking[0]


@needs_posix_bash
def test_review_is_the_same_for_the_same_tree_and_writes_nothing(
    review_workspace: Callable[[Path], Path], tmp_path: Path
) -> None:
    workdir = review_workspace(tmp_path / "ws")
    before = _snapshot(workdir)
    first = _review(workdir)
    assert _review(workdir) == first
    (workdir / "promptkit").mkdir(exist_ok=True)
    assert _review(workdir / "promptkit") == first  # from a subfolder, the same tree is read
    assert _snapshot(workdir) == before
    assert not list(workdir.rglob("__pycache__"))


@needs_posix_bash
def test_review_suggestions_vary_with_the_tree(
    review_workspace: Callable[[Path], Path], tmp_path: Path
) -> None:
    workdir = review_workspace(tmp_path / "ws")
    seen = set()
    for number in range(6):
        (workdir / "README.md").write_text(f"# promptkit\n\nEdition {number}.\n", encoding="utf-8")
        seen.add(tuple(_findings(_review(workdir))[1:]))
    assert len(seen) > 1


def test_review_finds_something_where_no_profile_applies(tmp_path: Path) -> None:
    (tmp_path / "tool.py").write_text("print('hi')\n", encoding="utf-8")
    done = subprocess.run(
        [sys.executable, "-I", "-B", str(STUBS / "review.py")],
        cwd=tmp_path, env={**os.environ, **HERMETIC_GIT, "GIT_CEILING_DIRECTORIES": str(tmp_path)},
        capture_output=True, text=True, encoding="utf-8", timeout=60,
    )  # fmt: skip
    findings = _findings(done.stdout)
    assert all("[suggestion]" in finding for finding in findings)
    assert sorted(path.name for path in tmp_path.iterdir()) == ["tool.py"]


def test_the_launcher_is_executable() -> None:
    assert os.access(STUBS / "review", os.X_OK)
    assert (STUBS / "review.py").is_file()
