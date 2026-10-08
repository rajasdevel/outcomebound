"""Line endings and byte-order marks: one install reads the same on every platform.

Git for Windows checks text files out with CRLF where `core.autocrlf` is true, and a Windows
editor can save a file with CRLF and a UTF-8 byte-order mark. These tests make those files here, by
converting what an install wrote, and assert the outcomes the install route owes: `--check` reads
the CRLF checkout current, an upgrade needs no `--force` and keeps each file's line ending, a block
written into a CRLF host is CRLF, and an engine checked out with CRLF installs the same bytes as
one with LF. Every assertion is about bytes on disk or an exit status.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from outcomebound_tools import adopt, textio
from tests.adopt_helpers import (
    ROOT,
    Capture,
    change_kernel,
    engine_copy,
    manifest,
    repo,
    run,
    snapshot,
    states,
)

OWN = "# Project\n\nOur own rules.\n"
INSTALL = ("--harness", "claude-code", "--fragments", "python")
BARE_LF = re.compile(rb"(?<!\r)\n")


def as_crlf(data: bytes) -> bytes:
    return textio.fold(data).replace(b"\n", b"\r\n")


def checkout_with_crlf(root: Path) -> None:
    """Every file under `root` outside `.git` as `core.autocrlf=true` checks it out."""

    for path in root.rglob("*"):
        if path.is_file() and ".git" not in path.relative_to(root).parts:
            path.write_bytes(as_crlf(path.read_bytes()))


def installed(tmp_path: Path, capsys: Capture, source: Path = ROOT) -> Path:
    target = repo(tmp_path / "t", {"AGENTS.md": OWN, "pyproject.toml": "[project]\n"})
    assert run(capsys, str(target), *INSTALL, source=source)[0] == 0
    return target


def test_a_crlf_checkout_reads_current_and_a_second_install_changes_nothing(
    tmp_path: Path, capsys: Capture
) -> None:
    target = installed(tmp_path, capsys)
    checkout_with_crlf(target)
    before = snapshot(target)

    code, out, _ = run(capsys, str(target), "--check")

    assert code == 0, out
    assert set(states(out).values()) == {"current"}
    assert run(capsys, str(target))[0] == 0
    assert snapshot(target) == before, "nothing was rewritten, and no file changed its line ending"


def test_an_upgrade_of_a_crlf_checkout_needs_no_force_and_keeps_its_line_endings(
    tmp_path: Path, capsys: Capture
) -> None:
    source = engine_copy(tmp_path)
    target = installed(tmp_path, capsys, source)
    checkout_with_crlf(target)
    change_kernel(source, "9.9.9")

    code, out, _ = run(capsys, str(target), "--check", source=source)
    assert code != 0 and states(out)[f"AGENTS.md ({adopt.KERNEL})"] == "stale", out

    code, _, err = run(capsys, str(target), source=source)

    assert code == 0, err
    agents = (target / "AGENTS.md").read_bytes()
    assert b"not least work, now." in agents
    assert not BARE_LF.search(agents), "the rewritten block is CRLF like the file around it"
    assert agents.endswith(as_crlf(OWN.encode()))
    code, out, _ = run(capsys, str(target), "--check", source=source)
    assert code == 0 and set(states(out).values()) == {"current"}


def test_a_block_written_into_a_crlf_host_is_crlf_and_the_hosts_own_text_is_untouched(
    tmp_path: Path, capsys: Capture
) -> None:
    own = as_crlf(OWN.encode())
    target = repo(tmp_path / "t")
    (target / "AGENTS.md").write_bytes(own)

    assert run(capsys, str(target), "--harness", "claude-code")[0] == 0

    written = (target / "AGENTS.md").read_bytes()
    assert not BARE_LF.search(written)
    assert written.endswith(b"\r\n\r\n" + own)
    assert run(capsys, str(target), "--check")[0] == 0
    # The record is the digest of the LF text, the same as an LF host's.
    plain = repo(tmp_path / "p", {"AGENTS.md": OWN})
    assert run(capsys, str(plain), "--harness", "claude-code")[0] == 0
    assert manifest(target)["artifacts"] == manifest(plain)["artifacts"]


def test_a_host_with_a_byte_order_mark_and_crlf_comes_back_byte_for_byte_after_a_removal(
    tmp_path: Path, capsys: Capture
) -> None:
    original = textio.UTF8_BOM + as_crlf(OWN.encode())
    target = repo(tmp_path / "t")
    (target / "AGENTS.md").write_bytes(original)

    assert run(capsys, str(target), "--harness", "claude-code")[0] == 0
    installed_bytes = (target / "AGENTS.md").read_bytes()
    assert installed_bytes.startswith(textio.UTF8_BOM + b"<!-- outcomebound:begin")
    assert installed_bytes.count(textio.UTF8_BOM) == 1
    assert run(capsys, str(target), "--check")[0] == 0

    assert run(capsys, str(target), "--remove")[0] == 0

    assert (target / "AGENTS.md").read_bytes() == original


def test_a_host_with_mixed_line_endings_keeps_every_byte_it_had_through_install_and_removal(
    tmp_path: Path, capsys: Capture
) -> None:
    original = b"# Project\r\n\r\nline one\nline two\r\nline three\r\nlone\rcr\nlast"
    target = repo(tmp_path / "t")
    (target / "AGENTS.md").write_bytes(original)

    assert run(capsys, str(target), "--harness", "claude-code")[0] == 0
    written = (target / "AGENTS.md").read_bytes()
    # The host's own lines are as they were; the block is in the ending most lines use (CRLF).
    assert written.startswith(b"<!-- outcomebound:begin")
    assert b"line one\nline two\r\nline three\r\nlone\rcr\nlast" in written
    assert not BARE_LF.search(written.split(b"line one")[0])
    assert run(capsys, str(target), "--check")[0] == 0

    assert run(capsys, str(target), "--remove")[0] == 0

    assert (target / "AGENTS.md").read_bytes() == original


def test_an_engine_checked_out_with_crlf_installs_the_same_bytes_as_one_with_lf(
    tmp_path: Path, capsys: Capture
) -> None:
    lf = engine_copy(tmp_path / "lf")
    crlf = tmp_path / "crlf"
    shutil.copytree(lf, crlf)
    for path in crlf.rglob("*"):
        if path.is_file():
            path.write_bytes(as_crlf(path.read_bytes()))
    by_lf = installed(tmp_path / "a", capsys, lf)
    by_crlf = installed(tmp_path / "b", capsys, crlf)

    assert snapshot(by_crlf) == snapshot(by_lf)
    assert run(capsys, str(by_crlf), "--check", source=lf)[0] == 0


def test_a_local_fragment_with_crlf_and_a_byte_order_mark_installs_as_one_without(
    tmp_path: Path, capsys: Capture
) -> None:
    template = (ROOT / "templates" / "fragment-local.md").read_bytes()
    arguments = ("--harness", "claude-code", "--fragments", "local")
    results = []
    for name, data in (
        ("lf", template),
        ("crlf", as_crlf(template)),
        ("bom", textio.UTF8_BOM + as_crlf(template)),
    ):
        target = repo(tmp_path / name)
        (target / ".outcomebound/fragments").mkdir(parents=True)
        (target / ".outcomebound/fragments/local.md").write_bytes(data)
        code, _, err = run(capsys, str(target), *arguments)
        assert code == 0, f"{name}: {err}"
        results.append(
            adopt.block_text((target / "AGENTS.md").read_text(encoding="utf-8"), adopt.POINTERS)
        )
    assert results[0] == results[1] == results[2]


def test_a_settings_file_with_a_byte_order_mark_and_crlf_keeps_both_when_the_hook_goes_in(
    tmp_path: Path, capsys: Capture
) -> None:
    """A harness settings file saved by Windows PowerShell 5.1 has a mark; `json.loads` refuses
    text that starts with one, and a rewrite would drop it."""

    target = repo(tmp_path / "t")
    settings = target / ".claude" / "settings.json"
    settings.parent.mkdir()
    original = textio.UTF8_BOM + b'{\r\n  "permissions": {}\r\n}\r\n'
    settings.write_bytes(original)

    arguments = (str(target), "--harness", "claude-code", "--done", ":", "--finish-check")
    code, _, err = run(capsys, *arguments)

    assert code == 0, err
    written = settings.read_bytes()
    assert written.startswith(textio.UTF8_BOM + b"{") and written.count(textio.UTF8_BOM) == 1
    assert not BARE_LF.search(written)
    assert "Stop" in json.loads(textio.decode(written))["hooks"]
    code, out, _ = run(capsys, str(target), "--check")
    assert code == 0 and set(states(out).values()) == {"current"}
