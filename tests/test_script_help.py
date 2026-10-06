"""Every scripts/*.sh entry point, and every executable scripts/*.py one, handles -h/--help before any target validation.

A stranger's first move with an unfamiliar CLI is `--help`. A script that took `--help`
for a positional argument (a target directory, a slug, a manifest path) would fail with a
confusing domain error instead of printing usage, so each has the same shape: check for
-h/--help first, print one usage line, exit 0 -- before touching `$1` as anything else.
"""  # noqa: E501 - the summary line is one line, as written

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = sorted((ROOT / "scripts").glob("*.sh"))
PY_SCRIPTS = sorted(path for path in (ROOT / "scripts").glob("*.py") if os.access(path, os.X_OK))


def _bash() -> str | None:
    """The bash the `.sh` scripts need, or None where there is none to run them with. On
    Windows `bash` on PATH can be the WSL stub, so Git for Windows' own is taken (UNVERIFIED
    until the Windows CI job runs it); Alpine has none until it is installed."""

    if os.name != "nt":
        return shutil.which("bash")
    git = shutil.which("git")
    candidate = Path(git).resolve().parent.parent / "bin" / "bash.exe" if git else None
    return str(candidate) if candidate is not None and candidate.is_file() else None


def _run(script: Path, flag: str) -> subprocess.CompletedProcess[str]:
    bash = _bash()
    if bash is None:
        pytest.skip("no bash here to run a .sh script with (the Alpine image has none)")
    return subprocess.run(
        [bash, str(script), flag],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


@pytest.mark.parametrize("script", SCRIPTS, ids=[p.name for p in SCRIPTS])
@pytest.mark.parametrize("flag", ["-h", "--help"])
def test_help_exits_zero_with_usage_and_no_traceback(script, flag):
    result = _run(script, flag)
    combined = result.stdout + result.stderr
    assert result.returncode == 0, (
        f"{script.name} {flag} exited {result.returncode}, expected 0:\n{combined}"
    )
    assert "usage" in combined.lower(), f"{script.name} {flag} printed no usage line:\n{combined}"
    assert "Traceback" not in combined, (
        f"{script.name} {flag} raised a Python traceback:\n{combined}"
    )
    # --help wins even where it would otherwise be consumed as the first positional (a
    # target directory, a slug, a manifest path): no domain-specific error ('target is
    # not a directory', 'slug must be lowercase...') in place of usage.
    for domain_error in ("is not a directory", "must be lowercase", "no such file"):
        assert domain_error not in combined.lower(), (
            f"{script.name} {flag} fell through to target/argument validation:\n{combined}"
        )


@pytest.mark.parametrize("script", PY_SCRIPTS, ids=[p.name for p in PY_SCRIPTS])
@pytest.mark.parametrize("flag", ["-h", "--help"])
def test_every_executable_python_script_answers_help_with_usage(
    script: Path, flag: str, tmp_path: Path
) -> None:
    """An executable script reads `--help` as a request for usage, never as an argument.

    Run from a directory holding nothing, so a script that would read `--help` as a
    path, or check it as a root and find nothing, cannot pass by accident.
    """

    result = subprocess.run(
        [sys.executable, str(script), flag],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    combined = result.stdout + result.stderr
    assert result.returncode == 0, f"{script.name} {flag} exited {result.returncode}:\n{combined}"
    assert "usage:" in result.stdout, f"{script.name} {flag} printed no usage:\n{combined}"
    assert "Traceback" not in combined, f"{script.name} {flag} raised:\n{combined}"
