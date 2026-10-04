"""Shell entry points remain executable after renames and template changes."""

import stat
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_command_scripts_are_executable():
    must_exec = sorted(ROOT.glob("scripts/*.sh")) + [ROOT / "scripts" / "check-no-deps.py"]
    missing = [
        str(p.relative_to(ROOT))
        for p in must_exec
        if not (p.is_file() and p.stat().st_mode & stat.S_IXUSR)
    ]
    assert not missing, f"lost executable bit: {missing}"
