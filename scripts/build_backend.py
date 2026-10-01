#!/usr/bin/env python3
"""Build OutcomeBound's wheel and source archive with the standard library alone (PEP 517).

`pyproject.toml` names this module as its build backend, so `uv tool install`, `pipx install`
and `pip install` build from a checkout or a source archive with no build dependency. The wheel
holds the engine package, `outcomebound_tools/`, with the engine's own files under
`outcomebound_tools/_home/`, where `outcomebound_tools.home` finds them, and installs the
launcher, `scripts/outcomebound`, as its one command. A checkout contributes the files Git
tracks; a source archive, every file it holds but dotfiles and bytecode. Builds are
reproducible: entries are sorted and dated from SOURCE_DATE_EPOCH, or 1980-01-01, so a wheel
built from the source archive is the wheel built from the checkout.

Run directly, it builds into dist/: `python3 scripts/build_backend.py [--sdist] [--out DIR]`.
"""

from __future__ import annotations

import argparse
import base64
import csv
import gzip
import hashlib
import io
import os
import re
import subprocess
import sys
import tarfile
import time
import zipfile
from pathlib import Path

NAME = "outcomebound"
SUMMARY = (
    "An operating contract for coding agents, and the engine that installs it into a repository."
)
URL = "https://github.com/rajasdevel/outcomebound"
REQUIRES_PYTHON = ">=3.10"
PACKAGE = "outcomebound_tools"
LAUNCHER = "scripts/outcomebound"
# The engine's own files, shipped under the package's _home/ with the checkout's layout.
HOME = (
    "OutcomeBound.md",
    "VERSION",
    "LICENSE",
    "NOTICE",
    "adapters",
    "docs/model-guidance.md",
    "fragments",
    "schemas",
    "scripts/new-spec.sh",
    "skills",
    "templates",
)
# What a source archive adds to build the wheel again.
SDIST = ("pyproject.toml", "README.md", "scripts/build_backend.py", LAUNCHER)
# A build without these would install a command with no engine behind it.
REQUIRED = (f"{PACKAGE}/__main__.py", f"{PACKAGE}/home.py", "OutcomeBound.md", "VERSION", LAUNCHER)
ROOT = Path(__file__).resolve().parent.parent
FLOOR_EPOCH = 315532800  # 1980-01-01, the earliest date a zip entry holds
PRERELEASE = {"alpha": "a", "a": "a", "beta": "b", "b": "b", "rc": "rc"}


def _version(root: Path) -> str:
    """VERSION as the wheel spells it: X.Y.Z, or X.Y.Z-rc.N (alpha, beta) as X.Y.ZrcN."""

    raw = (root / "VERSION").read_text(encoding="utf-8").strip()
    found = re.fullmatch(r"(\d+\.\d+\.\d+)(?:-(alpha|beta|rc|a|b)\.?(\d+))?", raw)
    if found is None:
        raise ValueError(f"VERSION {raw!r} is neither X.Y.Z nor X.Y.Z-rc.N")
    base, kind, number = found.groups()
    return base if kind is None else f"{base}{PRERELEASE[kind]}{number}"


def _dist(root: Path) -> str:
    return f"{NAME}-{_version(root)}"


def _epoch() -> int:
    return max(int(os.environ.get("SOURCE_DATE_EPOCH") or FLOOR_EPOCH), FLOOR_EPOCH)


def _stamp() -> tuple[int, int, int, int, int, int]:
    stamp = time.gmtime(_epoch())
    return (stamp[0], stamp[1], stamp[2], stamp[3], stamp[4], stamp[5])


def _git_files(root: Path) -> list[str] | None:
    """The files Git tracks, when `root` is the top of its own work tree; else None."""

    def git(*arguments: str) -> bytes:
        done = subprocess.run(["git", *arguments], cwd=root, capture_output=True, check=True)
        return done.stdout

    try:
        top = git("rev-parse", "--show-toplevel").decode("utf-8").strip()
        if Path(top).resolve() != root.resolve():
            return None
        listed = git("ls-files", "-z", "--cached").decode("utf-8")
    except (OSError, subprocess.CalledProcessError, UnicodeDecodeError):
        return None
    return [name for name in listed.split("\0") if name and (root / name).is_file()]


def _shipped(root: Path) -> list[str]:
    """Every file the build may take, as relative POSIX paths, and refuse a tree without the
    engine: the files Git tracks in a checkout, else every file but dotfiles and bytecode. A
    checkout whose Git cannot list them builds nothing, since a walk would take ignored files."""

    names = _git_files(root)
    if names is None and (root / ".git").exists():
        raise RuntimeError(
            f"cannot build from {root}: Git cannot list the files the checkout tracks"
        )
    if names is None:
        names = [
            path.relative_to(root).as_posix()
            for path in root.rglob("*")
            if path.is_file()
            and not any(part.startswith(".") for part in path.relative_to(root).parts)
            and "__pycache__" not in path.parts
            and path.suffix != ".pyc"
        ]
    missing = [name for name in REQUIRED if name not in names]
    if missing:
        raise RuntimeError(f"cannot build from {root}: {', '.join(missing)} not among its files")
    return sorted(set(names))


def _under(names: list[str], prefixes: tuple[str, ...]) -> list[str]:
    return [n for n in names if any(n == p or n.startswith(p + "/") for p in prefixes)]


def _metadata(root: Path) -> str:
    readme = (root / "README.md").read_text(encoding="utf-8")
    return (
        "Metadata-Version: 2.2\n"
        f"Name: {NAME}\n"
        f"Version: {_version(root)}\n"
        f"Summary: {SUMMARY}\n"
        "Author: Rajas Abhyankar\n"
        "License: Apache-2.0\n"
        f"Project-URL: Repository, {URL}\n"
        f"Requires-Python: {REQUIRES_PYTHON}\n"
        "Classifier: License :: OSI Approved :: Apache Software License\n"
        "Classifier: Programming Language :: Python :: 3\n"
        "Description-Content-Type: text/markdown\n"
        f"\n{readme}"
    )


WHEEL = "Wheel-Version: 1.0\nGenerator: outcomebound build_backend\nRoot-Is-Purelib: true\n"
WHEEL += "Tag: py3-none-any\n"


def _entries(root: Path) -> list[tuple[str, bytes, bool]]:
    """The wheel's files but RECORD: archive path, bytes, and whether it is executable."""

    names = _shipped(root)
    dist = _dist(root)
    entries = [
        (name, (root / name).read_bytes(), False)
        for name in _under(names, (PACKAGE,))
        if name.endswith(".py") and not name.startswith(f"{PACKAGE}/_home/")
    ]
    entries += [
        (f"{PACKAGE}/_home/{name}", (root / name).read_bytes(), os.access(root / name, os.X_OK))
        for name in _under(names, HOME)
    ]
    entries.append((f"{dist}.data/scripts/outcomebound", (root / LAUNCHER).read_bytes(), True))
    info = f"{dist}.dist-info"
    entries += [
        (f"{info}/METADATA", _metadata(root).encode("utf-8"), False),
        (f"{info}/WHEEL", WHEEL.encode("utf-8"), False),
        (f"{info}/LICENSE", (root / "LICENSE").read_bytes(), False),
        (f"{info}/NOTICE", (root / "NOTICE").read_bytes(), False),
    ]
    return entries


def _hash(data: bytes) -> str:
    digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=")
    return f"sha256={digest.decode('ascii')}"


def _record(entries: list[tuple[str, bytes, bool]], record_name: str) -> bytes:
    """RECORD as the wheel format has it: CSV rows of path, hash and size, RECORD's own last."""

    text = io.StringIO()
    rows = csv.writer(text, lineterminator="\n")
    for name, data, _ in entries:
        rows.writerow((name, _hash(data), len(data)))
    rows.writerow((record_name, "", ""))
    return text.getvalue().encode("utf-8")


def _zip_info(name: str, executable: bool) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=_stamp())
    info.external_attr = (0o100755 if executable else 0o100644) << 16
    info.compress_type = zipfile.ZIP_DEFLATED
    return info


def build_wheel(
    wheel_directory: str,
    config_settings: dict[str, object] | None = None,
    metadata_directory: str | None = None,
) -> str:
    """PEP 517: write the wheel into `wheel_directory` and return its file name."""

    entries = _entries(ROOT)
    record_name = f"{_dist(ROOT)}.dist-info/RECORD"
    filename = f"{_dist(ROOT)}-py3-none-any.whl"
    with zipfile.ZipFile(Path(wheel_directory) / filename, "w") as wheel:
        for name, data, executable in [
            *entries,
            (record_name, _record(entries, record_name), False),
        ]:
            wheel.writestr(_zip_info(name, executable), data)
    return filename


def prepare_metadata_for_build_wheel(
    metadata_directory: str, config_settings: dict[str, object] | None = None
) -> str:
    """PEP 517: write the wheel's METADATA and WHEEL, and return the dist-info folder's name."""

    info = Path(metadata_directory) / f"{_dist(ROOT)}.dist-info"
    info.mkdir(parents=True, exist_ok=True)
    (info / "METADATA").write_text(_metadata(ROOT), encoding="utf-8")
    (info / "WHEEL").write_text(WHEEL, encoding="utf-8")
    return info.name


def build_sdist(sdist_directory: str, config_settings: dict[str, object] | None = None) -> str:
    """PEP 517: write the source archive into `sdist_directory` and return its file name."""

    dist = _dist(ROOT)
    names = _under(_shipped(ROOT), (PACKAGE, *HOME, *SDIST))
    names = [n for n in names if not n.startswith(f"{PACKAGE}/_home/")]
    members = [(f"{dist}/PKG-INFO", _metadata(ROOT).encode("utf-8"), False)]
    members += [
        (f"{dist}/{name}", (ROOT / name).read_bytes(), os.access(ROOT / name, os.X_OK))
        for name in names
    ]
    filename = f"{dist}.tar.gz"
    with (
        open(Path(sdist_directory) / filename, "wb") as raw,
        gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as zipped,
        tarfile.open(fileobj=zipped, mode="w", format=tarfile.PAX_FORMAT) as archive,
    ):
        for name, data, executable in sorted(members):
            member = tarfile.TarInfo(name)
            member.size, member.mtime = len(data), _epoch()
            member.mode = 0o755 if executable else 0o644
            archive.addfile(member, io.BytesIO(data))
    return filename


def get_requires_for_build_wheel(config_settings: dict[str, object] | None = None) -> list[str]:
    return []


def get_requires_for_build_sdist(config_settings: dict[str, object] | None = None) -> list[str]:
    return []


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sdist", action="store_true", help="build the source archive as well")
    parser.add_argument("--out", type=Path, default=ROOT / "dist", help="where to write (dist/)")
    args = parser.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    print(args.out / build_wheel(str(args.out)))
    if args.sdist:
        print(args.out / build_sdist(str(args.out)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
