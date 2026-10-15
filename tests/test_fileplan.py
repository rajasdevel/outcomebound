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
from tests.portable import WINDOWS, posix_only


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


def test_a_stale_stage_for_a_later_destination_refuses_before_any_write(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_bytes(b"old-a")
    (tmp_path / "b.md").write_bytes(b"old-b")
    stale = tmp_path / ("b.md" + fileplan.STAGE_SUFFIX)
    stale.write_bytes(b"foreign")

    with pytest.raises(fileplan.WriteError, match="staging file"):
        fileplan.write(
            tmp_path,
            {"a.md": b"new-a", "b.md": b"new-b"},
            {"a.md": b"old-a", "b.md": b"old-b"},
        )

    assert (tmp_path / "a.md").read_bytes() == b"old-a"
    assert (tmp_path / "b.md").read_bytes() == b"old-b"
    assert stale.read_bytes() == b"foreign", "a foreign stage is never removed"
    stale.unlink()
    fileplan.write(tmp_path, {"b.md": b"new-b"}, {"b.md": b"old-b"})
    assert (tmp_path / "b.md").read_bytes() == b"new-b"


def test_an_edit_made_while_the_stage_is_written_is_kept_and_the_write_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "f.md").write_bytes(b"old")
    real = os.fsync

    def fsync(descriptor: int) -> None:
        (tmp_path / "f.md").write_bytes(b"concurrent")
        real(descriptor)

    monkeypatch.setattr(os, "fsync", fsync)

    with pytest.raises(fileplan.WriteError, match="changed after it was read"):
        fileplan.write(tmp_path, {"f.md": b"planned"}, {"f.md": b"old"})

    assert (tmp_path / "f.md").read_bytes() == b"concurrent"
    assert not list(tmp_path.glob("*.outcomebound-stage"))


def test_an_edit_made_while_a_refused_rename_waits_is_kept_and_the_write_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Breaks if a retry after Windows refused the rename for a moment skips the recheck: an
    edit made during the wait would be overwritten."""

    (tmp_path / "f.md").write_bytes(b"old")
    real = os.replace
    tries: list[int] = []

    def replace(source: str | os.PathLike[str], destination: str | os.PathLike[str]) -> None:
        tries.append(1)
        if len(tries) == 1:
            raise PermissionError(13, "in use")
        real(source, destination)

    def wait(seconds: float) -> None:
        (tmp_path / "f.md").write_bytes(b"concurrent edit")

    monkeypatch.setattr("sys.platform", "win32")
    monkeypatch.setattr(fileplan.time, "sleep", wait)
    monkeypatch.setattr(os, "replace", replace)

    with pytest.raises(fileplan.WriteError, match="changed after it was read"):
        fileplan.write(tmp_path, {"f.md": b"planned"}, {"f.md": b"old"})

    assert (tmp_path / "f.md").read_bytes() == b"concurrent edit"
    assert tries == [1]
    assert not list(tmp_path.glob("*.outcomebound-stage"))


@posix_only
def test_a_refused_write_leaves_a_stage_a_changed_folder_link_reaches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Breaks if the cleanup of a refused write follows a folder that became a link while the
    stage was written, and deletes another writer's stage outside the target."""

    root, outside = tmp_path / "root", tmp_path / "outside"
    (root / "docs").mkdir(parents=True)
    outside.mkdir()
    (root / "docs/f.md").write_bytes(b"old")
    foreign = outside / ("f.md" + fileplan.STAGE_SUFFIX)
    foreign.write_bytes(b"foreign stage")
    real = os.fsync

    def fsync(descriptor: int) -> None:
        real(descriptor)
        (root / "docs").rename(root / "moved")
        (root / "docs").symlink_to(outside, target_is_directory=True)

    monkeypatch.setattr(os, "fsync", fsync)

    with pytest.raises(fileplan.WriteError, match="symlink"):
        fileplan.write(root, {"docs/f.md": b"planned"}, {"docs/f.md": b"old"})

    assert foreign.read_bytes() == b"foreign stage"
    assert (root / "moved/f.md").read_bytes() == b"old"


def test_a_stage_another_writer_makes_after_the_rename_is_left(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Breaks if the cleanup after a rename deletes the stage name, which the rename freed and
    another writer may already use."""

    (tmp_path / "f.md").write_bytes(b"old")
    stage = tmp_path / ("f.md" + fileplan.STAGE_SUFFIX)
    real = os.replace

    def replace(source: str | os.PathLike[str], destination: str | os.PathLike[str]) -> None:
        real(source, destination)
        stage.write_bytes(b"another writer's stage")

    monkeypatch.setattr(os, "replace", replace)

    fileplan.write(tmp_path, {"f.md": b"planned"}, {"f.md": b"old"})

    assert (tmp_path / "f.md").read_bytes() == b"planned"
    assert stage.read_bytes() == b"another writer's stage"
