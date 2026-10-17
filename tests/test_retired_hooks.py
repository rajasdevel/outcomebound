"""The finish check is retired in 1.7.0: adopt installs no hook and runs no Done command, takes
out the entries and records that 1.6.0 wrote, and the verb those entries call stays as a stub.

The 1.6.0 entry shapes below are fixture data, copied from what that release wrote for the Done
list `["true"]`, so that these tests need no earlier engine; `tests/test_upgrade_corpus.py` upgrades
real installs of earlier releases. Each test names the break it catches.
"""

from __future__ import annotations

import hashlib
import json
import shlex
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest

from outcomebound_tools import adopt, finish_check, textio
from tests.adopt_helpers import Capture, manifest, repo, run, snapshot, states
from tests.portable import engine

DONE = hashlib.sha256(json.dumps(["true"], separators=(",", ":")).encode()).hexdigest()
SETTINGS = {"claude-code": ".claude/settings.json", "codex": ".codex/hooks.json"}


def stop_entry(row: str) -> dict[str, Any]:
    """The stop entry 1.6.0 wrote: on claude-code a background entry that wakes the model, on
    codex one that returns at once."""

    command = (
        f"outcomebound finish-check --constant-time --harness {row} --done {DONE} --timeout 600"
    )
    if row == "claude-code":
        return {
            "hooks": [{"type": "command", "command": command, "asyncRewake": True, "timeout": 660}]
        }
    return {"hooks": [{"type": "command", "command": command, "timeout": 30}]}


def mark_entry(row: str) -> dict[str, Any]:
    """The turn-start entry 1.6.0 wrote beside the stop entry."""

    command = f"outcomebound finish-check --mark --harness {row} --done {DONE}"
    return {"hooks": [{"type": "command", "command": command, "timeout": 30}]}


def digest(entry: dict[str, Any]) -> str:
    text = json.dumps(entry, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode()).hexdigest()


# A project's own settings: keys out of alphabetical order, its own hooks under both events,
# non-ASCII text written plainly and four-space indentation, each of which a rewrite keeps.
OWN = {"command": "./their-own.sh", "type": "command"}
PROJECT = {
    "zeta": 1,
    "hooks": {
        "Stop": [{"hooks": [OWN]}],
        "UserPromptSubmit": [{"hooks": [{**OWN, "command": "./their-prompt.sh"}]}],
    },
    "alpha": "café",
}


def dump(document: dict[str, Any], indent: int = 4) -> str:
    return json.dumps(document, indent=indent, ensure_ascii=False) + "\n"


def hooked(
    tmp_path: Path, capsys: Capture, row: str, seeded: bool, edit: str | None = None
) -> tuple[Path, str | None]:
    """A project that 1.6.0 installed with `--finish-check` for `row`: this engine's install
    without a hook, then the two entries in the row's settings document and the two `hook`
    records in the manifest. Returns the project and the project's own settings text before the
    entries (None where the document did not exist and 1.6.0 created it). `edit` is appended to
    the stop entry's command, as a person's change."""

    target = repo(tmp_path / "t")
    assert run(capsys, str(target), "--harness", row, "--done", "true")[0] == 0
    path = SETTINGS[row]
    stop, mark = stop_entry(row), mark_entry(row)
    own = dump(PROJECT) if seeded else None
    document = json.loads(own) if own else {}
    if edit:
        stop["hooks"][0]["command"] += edit
    document.setdefault("hooks", {}).setdefault("Stop", []).append(stop)
    document["hooks"].setdefault("UserPromptSubmit", []).append(mark)
    (target / path).parent.mkdir(parents=True, exist_ok=True)
    (target / path).write_text(dump(document, 4 if seeded else 2), encoding="utf-8")
    records = manifest(target)
    kept_stop = stop_entry(row)
    records["artifacts"] += [
        {
            "kind": "hook",
            "path": path,
            "id": "finish-check",
            "harness": row,
            "timeout": 600,
            "created": not seeded,
            "sha256": digest(kept_stop),
        },
        {
            "kind": "hook",
            "path": path,
            "id": "finish-check-mark",
            "harness": row,
            "created": not seeded,
            "sha256": digest(mark),
        },
    ]
    (target / adopt.MANIFEST).write_text(
        json.dumps(records, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return target, own


def hook_records(target: Path) -> list[dict[str, Any]]:
    return [r for r in manifest(target)["artifacts"] if r["kind"] == "hook"]


@pytest.mark.parametrize("seeded", [True, False], ids=["project-settings", "created-by-adopt"])
@pytest.mark.parametrize("row", sorted(SETTINGS))
def test_an_install_takes_out_only_the_entries_and_records_1_6_0_wrote(
    tmp_path: Path, capsys: Capture, row: str, seeded: bool
) -> None:
    """Breaks if a re-install leaves an entry or a record, removes a hook or a key the project
    owns, changes a byte of the project's settings besides the two entries (their order,
    indentation and non-ASCII text included), or leaves behind a settings document that adopt
    created and that now holds nothing."""

    target, own = hooked(tmp_path, capsys, row, seeded)
    path = target / SETTINGS[row]

    code, out, err = run(capsys, str(target))

    assert code == 0, err
    assert hook_records(target) == []
    if seeded:
        assert path.read_text(encoding="utf-8") == own
    else:
        assert not path.exists()
    removed = [line for line in out.splitlines() if "retired in 1.7.0, so its" in line]
    assert len(removed) == 2 and all(line.startswith("note") for line in removed), out
    code, out, _ = run(capsys, str(target), "--check")
    assert code == 0 and set(states(out).values()) == {"current"}, out
    code, out, _ = run(capsys, str(target))
    assert code == 0 and "nothing to change" in out


def test_remove_takes_out_the_entries_1_6_0_wrote_and_nothing_else_of_the_project(
    tmp_path: Path, capsys: Capture
) -> None:
    """Breaks if `--remove` leaves a finish-check entry behind, or touches the project's own
    hooks and keys."""

    target, own = hooked(tmp_path, capsys, "claude-code", seeded=True)

    code, _, err = run(capsys, str(target), "--remove")

    assert code == 0, err
    assert (target / SETTINGS["claude-code"]).read_text(encoding="utf-8") == own
    assert not (target / adopt.MANIFEST).exists()


def test_a_settings_file_keeps_its_byte_order_mark_and_line_endings_when_the_entries_go(
    tmp_path: Path, capsys: Capture
) -> None:
    """A settings file saved by Windows PowerShell 5.1 has a mark and CRLF; `json.loads` refuses
    text that starts with one, and a rewrite would drop both."""

    target, _ = hooked(tmp_path, capsys, "claude-code", seeded=True)
    path = target / SETTINGS["claude-code"]
    plain = {"permissions": {}, "hooks": {"Stop": [stop_entry("claude-code")]}}
    plain["hooks"]["UserPromptSubmit"] = [mark_entry("claude-code")]
    text = json.dumps(plain, indent=2).replace("\n", "\r\n") + "\r\n"
    path.write_bytes(textio.UTF8_BOM + text.encode())

    code, _, err = run(capsys, str(target))

    assert code == 0, err
    written = path.read_bytes()
    assert written.startswith(textio.UTF8_BOM + b"{") and written.count(textio.UTF8_BOM) == 1
    assert b"\n" not in written.replace(b"\r\n", b"")
    assert json.loads(textio.decode(written)) == {"permissions": {}}


@pytest.mark.parametrize("row", sorted(SETTINGS))
def test_check_reads_a_1_6_0_install_as_not_current_and_names_the_entries_it_would_remove(
    tmp_path: Path, capsys: Capture, row: str
) -> None:
    """Breaks if `--check` reads the hook records current, or names no entry: the upgrade is
    `adopt .`, and the person reads here what it will take out."""

    target, _ = hooked(tmp_path, capsys, row, seeded=True)
    before = snapshot(target)

    code, out, _ = run(capsys, str(target), "--check")

    assert code == 2 and snapshot(target) == before
    lines = [line for line in out.splitlines() if "finish-check" in line and "stale" in line]
    assert len(lines) == 2, out
    assert any("the Stop entry `outcomebound finish-check --constant-time" in x for x in lines)
    assert any("the UserPromptSubmit entry `outcomebound finish-check --mark" in x for x in lines)
    assert all("retired in 1.7.0" in line for line in lines)
    assert "next: outcomebound adopt " in out and "--force" not in out


def test_a_hand_edited_entry_is_kept_and_refused_without_force_and_removed_with_it(
    tmp_path: Path, capsys: Capture
) -> None:
    """Breaks if an entry that no longer has the digest the record holds is removed without
    `--force`, which would delete the person's change, or kept with it."""

    target, own = hooked(tmp_path, capsys, "codex", seeded=True, edit=" --extra")
    path = target / SETTINGS["codex"]
    before = snapshot(target)

    code, out, _ = run(capsys, str(target), "--check")
    assert code == 2 and any(v == "edited" for v in states(out).values()), out

    code, _, err = run(capsys, str(target))
    assert code == 1
    assert ".codex/hooks.json (finish-check) differs from what adopt wrote" in err
    assert "restore it, or pass --force" in err
    assert snapshot(target) == before

    code, out, err = run(capsys, str(target), "--force")
    assert code == 0, err
    assert hook_records(target) == []
    assert path.read_text(encoding="utf-8") == own
    assert "edited   .codex/hooks.json (finish-check): overridden by --force" in out


def test_a_record_whose_entry_is_gone_is_dropped_without_reading_the_settings_file(
    tmp_path: Path, capsys: Capture
) -> None:
    """Breaks if a settings document with comments, which adopt cannot rewrite, stops an upgrade
    after the person took the entries out by hand."""

    target, _ = hooked(tmp_path, capsys, "claude-code", seeded=True)
    path = target / SETTINGS["claude-code"]
    path.write_text('{\n  // the person\'s own\n  "model": "x"\n}\n', encoding="utf-8")

    code, _, err = run(capsys, str(target))

    assert code == 0, err
    assert hook_records(target) == []
    assert path.read_text(encoding="utf-8").startswith("{\n  // the person's own")
    assert run(capsys, str(target), "--check")[0] == 0


def test_a_settings_file_with_comments_that_still_holds_an_entry_is_refused_by_name(
    tmp_path: Path, capsys: Capture
) -> None:
    """Breaks if adopt rewrites a document it cannot rewrite without changing more than its
    whitespace, or refuses without saying what the person does."""

    target, _ = hooked(tmp_path, capsys, "claude-code", seeded=True)
    path = target / SETTINGS["claude-code"]
    text = path.read_text(encoding="utf-8")
    path.write_text("// ours\n" + text, encoding="utf-8")
    before = snapshot(target)

    code, _, err = run(capsys, str(target))

    assert code == 1 and snapshot(target) == before
    assert "adopt refuses a document with comments" in err
    assert "remove OutcomeBound's finish-check entry from it by hand" in err


CLAUDE_STOP = stop_entry("claude-code")["hooks"][0]["command"]
CLAUDE_MARK = mark_entry("claude-code")["hooks"][0]["command"]
CODEX_STOP = stop_entry("codex")["hooks"][0]["command"]
CODEX_MARK = mark_entry("codex")["hooks"][0]["command"]


@pytest.mark.parametrize(
    ("command", "printed"),
    [(CLAUDE_STOP, ""), (CLAUDE_MARK, ""), (CODEX_STOP, "{}\n"), (CODEX_MARK, "")],
    ids=["claude-code-stop", "claude-code-turn-start", "codex-stop", "codex-turn-start"],
)
def test_the_retired_verb_answers_each_entry_1_6_0_wrote_with_what_a_no_op_prints(
    tmp_path: Path, command: str, printed: str
) -> None:
    """Breaks if a harness that still runs an old entry, between `pip install -U` and the next
    `adopt`, is held, shown an error, made to wait, or told something: claude-code reads no
    output as nothing to report, and codex reads its stop's output as JSON, so `{}` is what
    1.6.0 printed when it held nothing."""

    words = shlex.split(command)
    assert words[:2] == ["outcomebound", "finish-check"]
    stdin = json.dumps({"cwd": str(tmp_path), "session_id": "s", "stop_hook_active": False})
    before = snapshot(tmp_path)

    result = subprocess.run(
        engine(*words[1:]),
        input=stdin,
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=60,
    )

    assert (result.returncode, result.stdout, result.stderr) == (0, printed, "")
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize(
    "words",
    [
        shlex.split(CLAUDE_STOP)[2:],
        shlex.split(CODEX_STOP)[2:],
        shlex.split(CODEX_MARK)[2:],
        ["--run", "--input", "{}", "--harness", "codex"],
        ["--status"],
        ["--harness=codex", "--bogus", "x"],
        [],
    ],
    ids=["claude-stop", "codex-stop", "codex-mark", "codex-run", "status", "unknown-flag", "none"],
)
def test_the_retired_verb_accepts_any_arguments_and_returns_at_once(
    words: list[str], capsys: Capture
) -> None:
    """Breaks if the stub parses its arguments (an unknown one would fail with a usage error),
    reads its input, or takes more than a moment."""

    started = time.monotonic()
    code = finish_check.main(words)
    elapsed = time.monotonic() - started

    out, err = capsys.readouterr()
    assert code == 0 and err == "" and elapsed < 1
    assert out in ("", "{}\n")


def test_a_closed_standard_output_cannot_make_the_retired_verb_fail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Breaks if a harness that has closed its end of the pipe turns the stub's exit into an
    error: the codex stop is the one call that prints."""

    class Closed:
        def write(self, text: str) -> int:
            raise BrokenPipeError

        def flush(self) -> None:
            raise BrokenPipeError

        def fileno(self) -> int:
            raise OSError("closed")

    monkeypatch.setattr(sys, "stdout", Closed())

    assert finish_check.main(["--harness", "codex", "--done", DONE]) == 0


RETIRED = [
    ("--finish-check",),
    ("--no-finish-check",),
    ("--finish-timeout", "900"),
    ("--verify",),
    ("--done-skip", "make test", "docs/**"),
]


@pytest.mark.parametrize("flag", RETIRED, ids=[f[0] for f in RETIRED])
def test_each_retired_flag_prints_one_note_and_installs_no_hook_and_runs_no_done(
    tmp_path: Path, capsys: Capture, flag: tuple[str, ...]
) -> None:
    """Breaks if a flag that a script still passes is refused, installs an entry, runs the Done
    commands (the marker file), changes the Done fact, or prints its note twice or not at all."""

    target = repo(tmp_path / "t")
    done = f"{shlex.quote(Path(sys.executable).as_posix())} -c \"open('ran.marker', 'w')\""

    code, out, err = run(capsys, str(target), "--harness", "claude-code", "--done", done, *flag)

    assert code == 0, err
    notes = [
        line for line in out.splitlines() if "retired in 1.7.0; adopt installs no hook" in line
    ]
    assert len(notes) == 1 and notes[0].startswith(f"note     {flag[0]}:"), out
    assert "runs no Done command" in notes[0]
    assert hook_records(target) == []
    assert not (target / ".claude/settings.json").exists()
    assert not (target / "ran.marker").exists() and not list(target.rglob("ran.marker"))
    agents = (target / "AGENTS.md").read_text(encoding="utf-8")
    assert "is not run when" not in agents
    assert run(capsys, str(target), "--check")[0] == 0


@pytest.mark.parametrize("flag", RETIRED, ids=[f[0] for f in RETIRED])
def test_a_retired_flag_is_hidden_from_help_and_refused_beside_check(
    tmp_path: Path, capsys: Capture, flag: tuple[str, ...]
) -> None:
    """Breaks if `--help` still offers a flag that does nothing, or if `--check` takes it."""

    target = repo(tmp_path / "t")
    with pytest.raises(SystemExit) as stopped:
        adopt.main(["--help"])
    assert stopped.value.code == 0
    helped = capsys.readouterr().out
    assert flag[0] not in helped
    with pytest.raises(SystemExit):
        adopt.main([str(target), "--check", *flag])
    assert "apply to an install" in capsys.readouterr().err


def test_the_stop_entry_is_still_the_shape_the_migration_looks_for() -> None:
    """Breaks if the helpers that find an entry (`marked`, `canonical`) drift from the shapes
    above, which are the only record of what 1.6.0 wrote."""

    for row in SETTINGS:
        assert finish_check.marked(stop_entry(row)) and not finish_check.marked(
            stop_entry(row), True
        )
        assert finish_check.marked(mark_entry(row), True)
        assert (
            finish_check.canonical(mark_entry(row))
            == json.dumps(mark_entry(row), sort_keys=True, separators=(",", ":")).encode()
        )
    assert not finish_check.marked({"hooks": [{"type": "command", "command": "./their-own.sh"}]})
