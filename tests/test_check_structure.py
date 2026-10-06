"""`scripts/check-structure.py`, the floor's `structure` gate, finds each kind of rot it names,
so its PASS on this repository is not a check that looked at nothing."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from tests.portable import posix_only

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts/check-structure.py"
GIT = shutil.which("git") or "git"


def tracked(path: Path, files: dict[str, str], executable: tuple[str, ...] = ()) -> Path:
    """A Git repository at `path` tracking `files`, ignored ones included."""

    path.mkdir()
    subprocess.run([GIT, "init", "-q", str(path)], check=True)
    for name, text in files.items():
        (path / name).parent.mkdir(parents=True, exist_ok=True)
        (path / name).write_bytes(text.encode("utf-8"))
    for name in executable:
        (path / name).chmod(0o755)
    subprocess.run([GIT, "-C", str(path), "add", "-f", "."], check=True)
    # The recorded mode is what Git hands every platform; `chmod` alone does nothing on Windows.
    for name in executable:
        subprocess.run([GIT, "-C", str(path), "update-index", "--chmod=+x", name], check=True)
    return path


def check(root: Path) -> tuple[int, list[str]]:
    done = subprocess.run(
        [sys.executable, str(SCRIPT), str(root)], capture_output=True, text=True, check=False
    )
    return done.returncode, done.stdout.splitlines()


def test_each_kind_of_rot_is_found_and_what_exists_is_not(tmp_path: Path) -> None:
    helps = "scripts/helps.sh"
    clean = {
        "Makefile": "test:\n\ttrue\n",
        helps: "#!/bin/sh\nexit 0\n",
        "README.md": f"Run `{helps}` or `make test`.\n\n```sh\n./{helps}\n```\n",
    }
    rotten = {
        **clean,
        ".gitignore": "notes/\n",
        "notes/today.md": "# today\n",
        "pkg/__pycache__/m.pyc": "",
        "merged.txt": "one\n" + "<" * 7 + " ours\n",
        "docs/use.md": "WIP: half done\n\n"
        "Run `scripts/gone.sh`, `python3 -m outcomebound_tools.gone`, `make gone` or\n"
        "`outcomebound gone`.\n",
    }

    code, lines = check(tracked(tmp_path / "rotten", rotten))

    assert code == 1
    assert lines[0].startswith("structure: 8 problems; the first: ")
    for expected in (
        "tracked: notes/today.md",
        "tracked: pkg/__pycache__/m.pyc",
        "merged.txt:2: an in-progress marker",
        "docs/use.md:1: an in-progress marker",
        "docs/use.md:3: names `scripts/gone.sh`",
        "docs/use.md:3: names `python3 -m outcomebound_tools.gone`",
        "docs/use.md:3: names `make gone`",
        "docs/use.md:4: names `outcomebound gone`",
    ):
        assert sum(expected in line for line in lines[1:]) == 1, expected
    assert not [line for line in lines if "README.md" in line or "helps.sh" in line]

    assert check(tracked(tmp_path / "clean", clean)) == (
        0,
        ["structure: no problem in 3 tracked files"],
    )


@posix_only
def test_an_executable_that_fails_its_help_is_found(tmp_path: Path) -> None:
    """The script runs each tracked executable itself, which a platform that cannot run a
    shebang file (Windows) cannot do, so the check is POSIX-only."""

    fails = "scripts/fails.sh"
    helps = "scripts/helps.sh"
    files = {
        "Makefile": "test:\n\ttrue\n",
        helps: "#!/bin/sh\nexit 0\n",
        fails: "#!/bin/sh\nexit 3\n",
    }

    code, lines = check(tracked(tmp_path / "failing", files, (helps, fails)))

    assert code == 1
    assert lines[0].startswith("structure: 1 problem")
    assert [line for line in lines[1:] if f"{fails} --help exited 3" in line]
    assert not [line for line in lines if "helps.sh" in line]


def test_a_draft_spec_may_name_what_it_proposes_and_a_ratified_one_may_not(tmp_path: Path) -> None:
    proposes = "Run `scripts/new.sh` or `make new`.\n"
    files = {
        "Makefile": "test:\n\ttrue\n",
        "docs/specs/idea/design.md": f"---\nname: idea\nstatus: draft\n---\n\n{proposes}",
        "docs/specs/idea/plan.md": proposes,
        "docs/specs/done/design.md": f"---\nname: done\nstatus: ratified\n---\n\n{proposes}",
        "docs/specs/idea/notes.md": "WIP: still a marker\n",
    }

    code, lines = check(tracked(tmp_path / "specs", files))

    assert code == 1
    assert sorted(line.split(":")[0] for line in lines[1:]) == [
        "docs/specs/done/design.md",
        "docs/specs/done/design.md",
        "docs/specs/idea/notes.md",
    ]
