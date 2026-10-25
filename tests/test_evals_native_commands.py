"""Command directories read from a Codex native session, and the digests `--regrade` compares.

All data here is synthetic, in the shape codex-cli 0.162.1 writes: the stream gives a command as
shell-quoted text and no directory; the session gives the argv and a `file://` directory.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

import pytest

from evals.evidence import grading_digest, workspace_digest
from evals.native_commands import directory_of, fill_directories

HERE = "file:///work/space"


def _item(argv: Any, cwd: str = HERE, status: str = "completed", code: int = 0) -> dict:
    item = {
        "type": "CommandExecution",
        "id": "exec-1",
        "command": argv,
        "cwd": cwd,
        "status": status,
        "exit_code": code,
    }
    return {"type": "event_msg", "payload": {"type": "item_completed", "item": item}}


def _transcript(*rows: list[str]) -> str:
    return json.dumps({"format": "outcomebound-command-events-v1", "commands": list(rows)})


def _shell(script: str) -> list[str]:
    return ["/bin/zsh", "-lc", script]


def test_quoting_that_prefers_double_quotes_still_matches_its_argv() -> None:
    """The stream's quoting is not Python's `shlex.quote`; reading it back gives the argv."""

    script = "pwd; rg --files -g 'AGENTS.md' -g '!node_modules'"
    stream = "/bin/zsh -lc \"pwd; rg --files -g 'AGENTS.md' -g '\"'!node_modules'\"'\""
    text, meta = fill_directories(_transcript([stream, "succeeded", ""]), [_item(_shell(script))])
    assert meta["command_cwd_source"] == "native"
    assert json.loads(text)["commands"] == [[stream, "succeeded", "/work/space"]]


def test_calls_that_overlapped_come_in_another_order_and_still_match_by_text() -> None:
    first, second = _shell("make check"), _shell("git status")
    text, meta = fill_directories(
        _transcript(
            ["/bin/zsh -lc 'make check'", "unverified", ""],
            ["/bin/zsh -lc 'git status'", "unverified", ""],
        ),
        [_item(second, "file:///other"), _item(first)],
    )
    assert meta["command_cwd_source"] == "native"
    assert [row[2] for row in json.loads(text)["commands"]] == ["/work/space", "/other"]


def test_NEGATIVE_CONTROL_a_repeated_command_in_two_directories_cannot_be_paired_out_of_order() -> (
    None
):
    row = ["/bin/zsh -lc ls", "succeeded", ""]
    other = ["/bin/zsh -lc pwd", "succeeded", ""]
    session = [
        _item(_shell("ls"), "file:///a"),
        _item(_shell("pwd")),
        _item(_shell("ls"), "file:///b"),
    ]
    text, meta = fill_directories(_transcript(other, row, row), session)
    assert meta["command_cwd_source"].startswith("none: the native commands do not match")
    assert [r[2] for r in json.loads(text)["commands"]] == ["", "", ""]


def test_NEGATIVE_CONTROL_a_repeated_command_in_two_directories_is_refused_in_the_same_order() -> (
    None
):
    """Equal lists are not enough: identical text cannot say which completion is which start."""

    row = ["/bin/sh -c pwd", "unverified", ""]
    session = [_item(["/bin/sh", "-c", "pwd"], "file:///b"), _item(["/bin/sh", "-c", "pwd"])]
    text, meta = fill_directories(_transcript(row, row), session)
    assert meta["command_cwd_source"].startswith("none: the native commands do not match")
    assert [r[2] for r in json.loads(text)["commands"]] == ["", ""]


def test_a_repeated_command_in_one_directory_is_still_filled_in_the_same_order() -> None:
    row = ["/bin/sh -c pwd", "unverified", ""]
    session = [_item(["/bin/sh", "-c", "pwd"]), _item(["/bin/sh", "-c", "pwd"])]
    text, meta = fill_directories(_transcript(row, row), session)
    assert meta["command_cwd_source"] == "native"
    assert [r[2] for r in json.loads(text)["commands"]] == ["/work/space"] * 2


def test_a_success_the_native_record_contradicts_is_unverified_and_both_values_are_listed() -> None:
    stream = "/bin/zsh -lc 'make check'"
    text, meta = fill_directories(
        _transcript([stream, "succeeded", ""]), [_item(_shell("make check"), code=2)]
    )
    assert json.loads(text)["commands"][0] == [stream, "unverified", "/work/space"]
    assert meta["command_native_disagreements"] == [
        {"index": 0, "field": "status", "stream": "succeeded", "native": "exited 2"}
    ]


def test_a_success_in_a_directory_the_native_record_contradicts_is_unverified() -> None:
    stream = "/bin/zsh -lc ls"
    text, meta = fill_directories(
        _transcript([stream, "succeeded", "/elsewhere"]), [_item(_shell("ls"))]
    )
    assert json.loads(text)["commands"][0] == [stream, "unverified", "/elsewhere"]
    assert meta["command_native_disagreements"] == [
        {"index": 0, "field": "cwd", "stream": "/elsewhere", "native": "/work/space"}
    ]


def test_a_failure_stays_a_failure_and_a_success_the_native_record_shares_stays() -> None:
    failed, agreed = "/bin/zsh -lc 'false'", "/bin/zsh -lc true"
    text, meta = fill_directories(
        _transcript([failed, "exited 1", "/elsewhere"], [agreed, "succeeded", ""]),
        [_item(_shell("false"), code=1), _item(_shell("true"))],
    )
    assert [row[1] for row in json.loads(text)["commands"]] == ["exited 1", "succeeded"]
    assert [d["field"] for d in meta["command_native_disagreements"]] == ["cwd"]


@pytest.mark.parametrize(("code", "outcome"), [(0, "succeeded"), (2, "exited 2")])
def test_a_stream_unverified_takes_the_native_outcome_and_both_are_listed(
    code: int, outcome: str
) -> None:
    """Breaks if a command whose exit code the stream lost, and the native session recorded, is
    left unjudged: a suite that passed before a commit would be read as never shown to pass."""

    stream = "/bin/zsh -lc 'make check'"
    text, meta = fill_directories(
        _transcript([stream, "unverified", ""]), [_item(_shell("make check"), code=code)]
    )
    assert json.loads(text)["commands"][0][1] == outcome
    assert meta["command_native_disagreements"] == [
        {"index": 0, "field": "status", "stream": "unverified", "native": outcome}
    ]


def test_a_stream_unverified_in_a_directory_the_native_record_contradicts_stays() -> None:
    stream = "/bin/zsh -lc 'make check'"
    text, _meta = fill_directories(
        _transcript([stream, "unverified", "/elsewhere"]), [_item(_shell("make check"))]
    )
    assert json.loads(text)["commands"][0][1] == "unverified"


@pytest.mark.parametrize(
    ("transcript", "session", "reason"),
    [
        (_transcript(), None, "no native session was read"),
        ("not json", [], "the stream gives no command records"),
        (json.dumps({"commands": None}), [], "the stream gives no command records"),
        (_transcript(["/bin/zsh -lc ls", "succeeded", ""]), [], "the stream has 1 commands"),
        (
            _transcript(["/bin/zsh -lc ls", "succeeded", ""]),
            [_item(_shell("ls"), "https://example.test/x")],
            "a native command has no absolute working directory",
        ),
        (
            _transcript(["/bin/zsh -lc ls", "succeeded", ""]),
            [_item("/bin/zsh -lc ls")],
            "a native command has no argv list",
        ),
        (
            _transcript(["/bin/zsh -lc 'ls", "succeeded", ""]),
            [_item(_shell("ls"))],
            "a stream command is not shell-quoted text",
        ),
    ],
)
def test_NEGATIVE_CONTROL_anything_short_of_an_exact_match_leaves_the_transcript_as_it_came(
    transcript: str, session: list[dict[str, Any]] | None, reason: str
) -> None:
    text, meta = fill_directories(transcript, session)
    assert text == transcript and meta["command_cwd_source"].startswith(f"none: {reason}")


def test_a_directory_is_never_taken_from_the_session_cwd() -> None:
    """The session's own cwd is not a command's directory; an empty one is never filled."""

    session = [
        {"type": "session_meta", "payload": {"cwd": "/session/cwd"}},
        {"type": "turn_context", "payload": {"cwd": "/session/cwd"}},
    ]
    text, meta = fill_directories(_transcript(["/bin/zsh -lc ls", "succeeded", ""]), session)
    assert text.count("/session/cwd") == 0 and meta["command_cwd_source"].startswith("none:")


def test_a_file_uri_becomes_an_absolute_path() -> None:
    assert directory_of("file:///a/b%20c") == "/a/b c"
    assert directory_of("file://localhost/a") == "/a"
    assert directory_of("file:///C:/work/a%20b") == "C:/work/a b"
    assert directory_of("/a") == "/a"
    assert [directory_of(v) for v in ("", "a/b", "file://host/a", "ftp:///a", None)] == [""] * 5


# --- the digests -----------------------------------------------------------------------------


def _git(workdir: Path, *arguments: str) -> None:
    env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
    subprocess.run(["git", *arguments], cwd=workdir, check=True, capture_output=True, env=env)


def test_the_workspace_digest_changes_with_any_edit_and_not_with_a_later_git_status(
    tmp_path: Path,
) -> None:
    env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
    (tmp_path / "a.txt").write_text("one", encoding="utf-8")
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "-c", "user.name=t", "-c", "user.email=t@example.test", "add", ".")
    _git(tmp_path, "-c", "user.name=t", "-c", "user.email=t@example.test", "commit", "-qm", "seed")
    base = workspace_digest(tmp_path, env)
    assert base and base == workspace_digest(tmp_path, env)
    seen: set[str | None] = {base}
    for edit in (
        lambda: (tmp_path / "a.txt").write_text("two", encoding="utf-8"),  # a tracked edit
        lambda: (tmp_path / "new.txt").write_text("x", encoding="utf-8"),  # an untracked file
        lambda: (tmp_path / "new.txt").write_text("y", encoding="utf-8"),  # its content
        lambda: (tmp_path / "a.txt").unlink(),  # a deletion
    ):
        edit()
        seen.add(workspace_digest(tmp_path, env))
    assert len(seen) == 5 and None not in seen


def test_the_workspace_digest_is_none_where_git_cannot_say(tmp_path: Path) -> None:
    assert workspace_digest(tmp_path, {**os.environ, "GIT_DIR": str(tmp_path / "none")}) is None


def test_the_grading_digest_covers_the_fixture_what_it_shares_and_the_graders(
    tmp_path: Path,
) -> None:
    evals = tmp_path / "evals"
    for relative, text in {
        "fixtures/one/setup.sh": '. "$here/../shared/close.sh"\n',
        "fixtures/shared/close.sh": "echo close\n",
        "fixtures/one/probe.py": 'load(HERE.parent / "other/probe.py")\n',
        "fixtures/other/probe.py": "y = 1\n",
        "fixtures/two/setup.sh": "echo unrelated\n",
        "fixtures/core.sh": "echo core\n",
        "graders/g.py": "x = 1\n",
    }.items():
        (evals / relative).parent.mkdir(parents=True, exist_ok=True)
        (evals / relative).write_text(text, encoding="utf-8")
    base = grading_digest(evals, "one")
    assert base == grading_digest(evals, "one") and base != grading_digest(evals, "two")
    for relative in (
        "fixtures/one/setup.sh",
        "fixtures/shared/close.sh",
        "fixtures/other/probe.py",
        "fixtures/core.sh",
        "graders/g.py",
    ):
        path = evals / relative
        before = path.read_text(encoding="utf-8")
        path.write_text(before + "# edited\n", encoding="utf-8")
        assert grading_digest(evals, "one") != base, relative
        path.write_text(before, encoding="utf-8")
    (evals / "fixtures/two/setup.sh").write_text("changed\n", encoding="utf-8")
    assert grading_digest(evals, "one") == base, "an unrelated fixture changed the digest"
