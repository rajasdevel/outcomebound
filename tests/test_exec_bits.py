"""Shell entry points remain executable after renames and template changes."""

import stat
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _recorded_modes() -> dict[str, str]:
    """The mode Git records for each tracked file, `100755` for an executable one. A checkout
    on any platform keeps it, and a Windows file system has no executable bit to read. Empty
    where Git cannot read the tree (no repository, or a folder another user owns)."""

    done = subprocess.run(
        ["git", "ls-files", "-s", "-z"], cwd=ROOT, capture_output=True, text=True, check=False
    )
    modes = {}
    for entry in done.stdout.split("\0") if done.returncode == 0 else ():
        head, _, name = entry.partition("\t")
        if name:
            modes[name] = head.split()[0]
    return modes


def test_command_scripts_are_executable():
    modes = _recorded_modes()
    must_exec = [*sorted(ROOT.glob("scripts/*.sh")), ROOT / "scripts" / "check-no-deps.py"]
    missing = []
    for path in must_exec:
        name = path.relative_to(ROOT).as_posix()
        recorded = modes.get(name)
        if recorded is not None:
            executable = recorded == "100755"
        else:
            executable = path.is_file() and bool(path.stat().st_mode & stat.S_IXUSR)
        if not executable:
            missing.append(name)
    assert not missing, f"lost executable bit: {missing}"
