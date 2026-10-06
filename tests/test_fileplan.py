"""The safe writer's Windows edges, emulated: a name Windows cannot hold, and a rename that fails
for a moment while another process has the destination open.

The POSIX behaviour of the writer is held by `test_adopt.py`. Nothing here needs Windows, and none
of it shows how a real scanner or editor behaves there: that stays for the Windows CI job and for a
person on a desktop, `UNVERIFIED` here.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from outcomebound_tools import fileplan
from tests.portable import WINDOWS


def test_a_name_windows_cannot_hold_is_refused_before_anything_is_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("sys.platform", "win32")

    with pytest.raises(fileplan.WriteError, match="device name"):
        fileplan.write(
            tmp_path, {"ok.md": b"x", "docs/aux.md": b"y"}, {"ok.md": None, "docs/aux.md": None}
        )

    assert not (tmp_path / "ok.md").exists(), "every destination is checked before the first write"
    with pytest.raises(fileplan.WriteError, match="dot or a space"):
        fileplan.current(tmp_path, "notes.")


@pytest.mark.skipif(
    WINDOWS,
    reason="the name is one a Windows file system cannot hold, so a real write of it here "
    "opens a device; what the writer decides for Windows is the test above",
)
def test_another_platform_writes_a_name_only_windows_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("sys.platform", "linux")
    fileplan.write(tmp_path, {"docs/aux.md": b"y"}, {"docs/aux.md": None})

    assert (tmp_path / "docs/aux.md").read_bytes() == b"y"


def test_a_rename_that_is_refused_for_a_moment_on_windows_is_tried_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "f.md").write_bytes(b"old")
    real = os.replace
    refused: list[int] = []

    def replace(source: str | os.PathLike[str], destination: str | os.PathLike[str]) -> None:
        if len(refused) < 2:
            refused.append(1)
            raise PermissionError(13, "in use")
        real(source, destination)

    monkeypatch.setattr("sys.platform", "win32")
    monkeypatch.setattr(fileplan, "REPLACE_WAIT", 0)
    monkeypatch.setattr(os, "replace", replace)

    fileplan.write(tmp_path, {"f.md": b"new"}, {"f.md": b"old"})

    assert (tmp_path / "f.md").read_bytes() == b"new"
    assert len(refused) == 2
    assert not list(tmp_path.glob("*.outcomebound-stage")), "the stage file is gone"


def test_a_rename_that_stays_refused_on_windows_ends_in_the_error_after_a_few_tries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "f.md").write_bytes(b"old")
    tries: list[int] = []

    def replace(source: object, destination: object) -> None:
        tries.append(1)
        raise PermissionError(13, "read-only")

    monkeypatch.setattr("sys.platform", "win32")
    monkeypatch.setattr(fileplan, "REPLACE_WAIT", 0)
    monkeypatch.setattr(os, "replace", replace)

    with pytest.raises(PermissionError):
        fileplan.write(tmp_path, {"f.md": b"new"}, {"f.md": b"old"})

    assert len(tries) == fileplan.REPLACE_TRIES
    assert (tmp_path / "f.md").read_bytes() == b"old"
    assert not list(tmp_path.glob("*.outcomebound-stage"))


def test_a_refused_rename_is_not_tried_again_on_another_platform(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "f.md").write_bytes(b"old")
    tries: list[int] = []

    def replace(source: object, destination: object) -> None:
        tries.append(1)
        raise PermissionError(13, "read-only")

    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.setattr(os, "replace", replace)

    with pytest.raises(PermissionError):
        fileplan.write(tmp_path, {"f.md": b"new"}, {"f.md": b"old"})

    assert tries == [1]
