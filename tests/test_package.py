"""The package that `uv tool install`, `pipx install` or `pip install` builds from this checkout.

Built through pip from the checkout, as an adopter's install builds it, and installed offline into
a fresh virtual environment, the `outcomebound` command it provides (a console entry point: an
`.exe` on Windows) adopts a repository byte for byte as this checkout's launcher does, carries
every file the shipped skills name under `outcomebound home`, and runs isolated from the caller's
directory and PYTHONPATH; a wheel rebuilt from the source archive is the same wheel, and the
backend refuses a tree without the engine.
"""

from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import sysconfig
import tarfile
import zipfile
from pathlib import Path
from types import ModuleType

import pytest

from tests.test_outcomebound_launcher import engine

ROOT = Path(__file__).resolve().parent.parent
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
DIST = f"outcomebound-{VERSION}"
HOME_MENTION = re.compile(r"\$\(outcomebound home\)/([^\s`\"')]+)")


def backend(source: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "build_backend", source / "scripts" / "build_backend.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    out = tmp_path_factory.mktemp("dist")
    module = backend(ROOT)
    return out / module.build_wheel(str(out)), out / module.build_sdist(str(out))


def scripts_folder(environment: Path) -> Path:
    """`bin/` of a virtual environment, or `Scripts\\` on Windows."""

    scheme = "nt" if os.name == "nt" else "posix_prefix"  # not a distribution's own default
    return Path(sysconfig.get_path("scripts", scheme, vars={"base": str(environment)}))


@pytest.fixture(scope="module")
def installed(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The `outcomebound` command a fresh environment gets when pip builds and installs this
    checkout offline, through the build backend `pyproject.toml` names."""

    environment = tmp_path_factory.mktemp("venv")
    made = subprocess.run(
        [sys.executable, "-m", "venv", str(environment)],
        capture_output=True,
        text=True,
        check=False,
    )
    if made.returncode != 0:
        pytest.skip(f"UNVERIFIED: this Python makes no virtual environment with pip: {made.stderr}")
    scripts = scripts_folder(environment)
    python = scripts / ("python.exe" if os.name == "nt" else "python")
    pip = [str(python), "-m", "pip", "install", "--no-index", "--no-deps"]
    done = subprocess.run(
        [*pip, "--quiet", str(ROOT)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, done.stderr
    return scripts / ("outcomebound.exe" if os.name == "nt" else "outcomebound")


def run(
    command: Path, *arguments: str, cwd: Path, **environment: str
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(command), *arguments],
        cwd=cwd,
        env={**os.environ, **environment},
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def repository(path: Path) -> Path:
    path.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    (path / "README.md").write_text("# Project\n", encoding="utf-8")
    (path / "pyproject.toml").write_text("[project]\nname = 'project'\n", encoding="utf-8")
    return path


def tree(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file() and ".git" not in path.relative_to(root).parts
    }


def test_the_wheel_holds_the_engine_its_files_and_the_entry_point_and_nothing_else(
    built: tuple[Path, Path],
) -> None:
    with zipfile.ZipFile(built[0]) as wheel:
        names = wheel.namelist()
        record = wheel.read(f"{DIST}.dist-info/RECORD").decode("utf-8").splitlines()
        entry_points = wheel.read(f"{DIST}.dist-info/entry_points.txt").decode("utf-8")
        hop = wheel.read("_outcomebound_launch.py")
        for line in record:
            name, digest, size = line.rsplit(",", 2)
            if digest:
                data = wheel.read(name)
                expected = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=")
                assert (digest, int(size)) == (f"sha256={expected.decode()}", len(data)), name

    assert entry_points == "[console_scripts]\noutcomebound = _outcomebound_launch:main\n"
    assert hop == (ROOT / "outcomebound_tools" / "launcher.py").read_bytes()
    assert "outcomebound_tools/launcher.py" not in names  # the hop ships at the top level only
    assert "outcomebound_tools/__main__.py" in names
    assert "outcomebound_tools/_home/skills/using-outcomebound/SKILL.md" in names
    assert "outcomebound_tools/_home/templates/managed-block.agents.md.tmpl" in names
    assert {line.rsplit(",", 2)[0] for line in record} == set(names)
    tops = {name.split("/")[0] for name in names}
    assert tops == {"outcomebound_tools", "_outcomebound_launch.py", f"{DIST}.dist-info"}
    assert not [name for name in names if "__pycache__" in name or name.endswith(".pyc")]


def test_the_installed_command_adopts_exactly_as_the_checkout_does(
    installed: Path, tmp_path: Path
) -> None:
    """Breaks if the package leaves out a file adopt reads, or reads it from elsewhere."""

    words: tuple[str, ...] = ("--harness", "claude-code,codex", "--fragments")
    words += ("python,tickets,workspace", "--done", "make test")
    by_package = repository(tmp_path / "package")
    by_checkout = repository(tmp_path / "checkout")

    first = run(installed, "adopt", str(by_package), *words, cwd=tmp_path)
    second = engine("adopt", str(by_checkout), *words, cwd=tmp_path)
    checked = run(installed, "adopt", str(by_package), "--check", cwd=tmp_path)

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    assert tree(by_package) == tree(by_checkout)
    assert checked.returncode == 0, checked.stdout + checked.stderr


@pytest.mark.parametrize(
    ("row", "settings"),
    [("claude-code", ".claude/settings.json"), ("codex", ".codex/hooks.json")],
)
def test_the_installed_hooks_run_done_without_development_tools(
    installed: Path, tmp_path: Path, row: str, settings: str
) -> None:
    """The saved entries run the installed wheel on a path with spaces, hold a new failure,
    and retry an unavailable project tool. POSIX PATH holds only OutcomeBound and real Git;
    native Windows also needs Git's own folders for its executable and POSIX shell."""

    found = shutil.which("git")
    assert found is not None, "this package test needs real Git"
    git = Path(found).resolve()
    tools = tmp_path / "hook tools"
    tools.mkdir()
    if os.name == "nt":
        # Copy the installed entry point, which embeds its environment's Python path. Keep
        # Git in its install: relocating its executable can separate it from its DLLs.
        shutil.copy2(installed, tools / installed.name)
        shells = [
            parent / relative / "sh.exe"
            for parent in git.parents[:3]
            for relative in ("bin", "usr/bin")
        ]
        shell = next((candidate for candidate in shells if candidate.is_file()), None)
        assert shell is not None, "native Windows finish hooks need Git for Windows' sh.exe"
        entries = [tools, git.parent, shell.parent]
    else:
        shell = Path("/bin/sh")
        assert shell.is_file(), "POSIX finish hooks need /bin/sh"
        (tools / installed.name).symlink_to(installed)
        (tools / "git").symlink_to(git)
        entries = [tools]
    restricted = os.pathsep.join(map(str, entries))
    if os.name != "nt":
        for absent in ("uv", "pipx", "make", "sg", "rg", "ps", "curl", "node", "docker"):
            assert shutil.which(absent, path=restricted) is None
    environment = {key: value for key, value in os.environ.items() if key.upper() != "PATH"}
    environment["PATH"] = restricted

    project = repository(tmp_path / "project with spaces")
    state = project / "check state.txt"
    state.write_text("accepted\n", encoding="utf-8")
    counter = tmp_path / "done invocations.txt"  # outside the tree the hook checks
    checker = project / "done check.py"
    checker.write_text(
        "from pathlib import Path\n"
        "import subprocess\n"
        "import sys\n"
        "with Path(sys.argv[1]).open('a', encoding='utf-8') as count:\n"
        "    count.write('run\\n')\n"
        "state = Path('check state.txt').read_text(encoding='utf-8').strip()\n"
        "if state == 'unsupported':\n"
        "    print('synthetic-project-check-tool is unavailable')\n"
        "    raise SystemExit(127)\n"
        "if state == 'missing':\n"
        "    result = subprocess.run([sys.argv[2], '-c', 'synthetic-project-check-tool'])\n"
        "    raise SystemExit(result.returncode)\n"
        "if state != 'accepted':\n"
        "    print('project check failed: expected accepted, got ' + state)\n"
        "    raise SystemExit(3)\n",
        encoding="utf-8",
    )
    python = installed.parent / ("python.exe" if os.name == "nt" else "python")
    done = " ".join(shlex.quote(path.as_posix()) for path in (python, checker, counter, shell))
    adopted = run(
        installed,
        "adopt",
        str(project),
        "--harness",
        row,
        "--done",
        done,
        "--finish-check",
        cwd=tmp_path,
        PATH=restricted,
    )
    assert adopted.returncode == 0, adopted.stdout + adopted.stderr
    assert "PASS     finish-check:" in adopted.stdout
    subprocess.run([str(git), "-C", str(project), "add", "."], check=True)
    subprocess.run(
        [
            str(git),
            "-C",
            str(project),
            "-c",
            "user.name=Package test",
            "-c",
            "user.email=package-test@example.com",
            "commit",
            "-qm",
            "Initial project",
        ],
        check=True,
    )
    hooks = json.loads((project / settings).read_text(encoding="utf-8"))["hooks"]

    def fire(event: str) -> dict[str, str]:
        command = hooks[event][0]["hooks"][0]["command"]
        result = subprocess.run(
            [str(shell), "-c", command],
            cwd=project,
            env=environment,
            input=json.dumps(
                {
                    "cwd": str(project),
                    "session_id": "package-test",
                    "hook_event_name": event,
                    "stop_hook_active": False,
                }
            ),
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
            timeout=30,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        if event == "UserPromptSubmit":
            assert result.stdout == ""  # marking a turn is silent
            return {}
        return json.loads(result.stdout)

    def runs() -> int:
        return len(counter.read_text(encoding="utf-8").splitlines())

    measured = runs()
    assert measured == 1
    assert fire("UserPromptSubmit") == {}
    unchanged = fire("Stop")
    assert unchanged["systemMessage"].startswith("finish-check: the tree is the one this turn")
    assert runs() == measured

    assert fire("UserPromptSubmit") == {}
    (project / "README.md").write_text("# Changed project\n", encoding="utf-8")
    passed = fire("Stop")
    assert list(passed) == ["systemMessage"]
    assert passed["systemMessage"].startswith("finish-check PASS: ")
    assert runs() == measured + 1
    assert fire("Stop") == {} and runs() == measured + 1

    assert fire("UserPromptSubmit") == {}
    state.write_text("rejected\n", encoding="utf-8")
    failed = fire("Stop")
    assert failed["decision"] == "block" and "systemMessage" not in failed
    assert failed["reason"].startswith("finish-check FAIL: ")
    assert "exit 3" in failed["reason"]
    assert "project check failed: expected accepted, got rejected" in failed["reason"]
    assert runs() == measured + 2

    state.write_text("unsupported\n", encoding="utf-8")
    unsupported = fire("Stop")
    assert unsupported["decision"] == "block"
    assert "exit 127" in unsupported["reason"]
    assert "synthetic-project-check-tool is unavailable" in unsupported["reason"]
    assert runs() == measured + 3

    state.write_text("missing\n", encoding="utf-8")
    for expected in (measured + 4, measured + 5):
        unavailable = fire("Stop")
        assert list(unavailable) == ["systemMessage"]
        assert unavailable["systemMessage"].startswith("finish-check UNVERIFIED: ")
        assert "could not run in the hook's environment" in unavailable["systemMessage"]
        assert "synthetic-project-check-tool" in unavailable["systemMessage"]
        assert runs() == expected  # same tree, no cached success or environmental refusal


def test_home_holds_every_file_the_shipped_skills_name(installed: Path, tmp_path: Path) -> None:
    home = Path(run(installed, "home", cwd=tmp_path).stdout.strip())
    named = {"OutcomeBound.md"}
    for skill in (ROOT / "skills").rglob("*.md"):
        named |= set(HOME_MENTION.findall(skill.read_text(encoding="utf-8")))

    assert home.name == "_home" and home.is_dir()
    assert len(named) > 2
    assert sorted(name for name in named if not (home / name).exists()) == []


def test_an_engine_in_the_callers_directory_or_path_is_never_run(
    installed: Path, tmp_path: Path
) -> None:
    decoy = tmp_path / "outcomebound_tools"
    decoy.mkdir()
    for name in ("__init__", "__main__", "home"):
        (decoy / f"{name}.py").write_text("raise SystemExit(99)\n", encoding="utf-8")

    done = run(installed, "home", cwd=tmp_path, PYTHONPATH=str(tmp_path))

    assert done.returncode == 0, done.stderr
    assert Path(done.stdout.strip()).name == "_home"


def test_the_install_makes_one_command_and_it_passes_the_engines_exit_code_on(
    installed: Path, tmp_path: Path
) -> None:
    """One `outcomebound` in the scripts folder, not a launcher script beside an `.exe`; and a
    word the engine cannot run exits 1, so that a stop hook does not hold the turn."""

    beside = [path.name for path in installed.parent.iterdir() if path.stem == "outcomebound"]
    unknown = run(installed, "frobnicate", cwd=tmp_path)
    plain = run(installed, "home", cwd=tmp_path)

    assert beside == [installed.name]
    assert unknown.returncode == 1 and "verbs: home" in unknown.stderr
    assert plain.returncode == 0 and plain.stdout.endswith("_home\n")


def test_the_wheel_marks_the_scripts_it_ships_executable_by_their_first_line(
    built: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Never by the build machine's file system: a Windows build sees every file as executable,
    and a wheel built there must be the wheel built anywhere. Checked against Git's own mode."""

    tracked = subprocess.run(
        ["git", "ls-files", "-s", "-z"], cwd=ROOT, capture_output=True, text=True, check=False
    )
    if tracked.returncode != 0:
        pytest.skip("UNVERIFIED: this tree is not a Git checkout, so Git's modes are unknown")
    modes = {
        entry.split("\t", 1)[1]: entry.split(" ", 1)[0] == "100755"
        for entry in tracked.stdout.split("\0")
        if entry
    }
    monkeypatch.setattr(os, "access", lambda *args, **kwargs: True)  # Windows: every file is

    entries = backend(ROOT)._entries(ROOT)

    home = "outcomebound_tools/_home/"
    shipped = {name[len(home) :]: executable for name, _, executable in entries if home in name}
    assert shipped["scripts/new-spec.sh"] is True
    assert shipped["OutcomeBound.md"] is False
    assert shipped == {name: modes[name] for name in shipped}


def test_a_wheel_built_from_the_source_archive_is_the_same_wheel(
    built: tuple[Path, Path], tmp_path: Path
) -> None:
    with tarfile.open(built[1]) as archive:
        for member in archive.getmembers():
            target = tmp_path / member.name
            assert target.resolve().is_relative_to(tmp_path.resolve()), member.name
            data = archive.extractfile(member)
            assert member.isfile() and data is not None, member.name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data.read())
            target.chmod(member.mode)
    source = tmp_path / DIST
    out = tmp_path / "out"
    out.mkdir()

    rebuilt = out / backend(source).build_wheel(str(out))

    assert (source / "PKG-INFO").is_file()
    assert rebuilt.name == built[0].name
    assert rebuilt.read_bytes() == built[0].read_bytes()


def test_a_tree_without_the_engine_builds_nothing(tmp_path: Path) -> None:
    """A build from the wrong folder would install a command with no engine behind it."""

    (tmp_path / "VERSION").write_text(f"{VERSION}\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match=r"outcomebound_tools/__main__\.py"):
        backend(ROOT)._shipped(tmp_path)


def test_a_checkout_whose_git_cannot_list_its_files_builds_nothing(tmp_path: Path) -> None:
    """A walk in its place would ship files the checkout ignores."""

    for name in backend(ROOT).REQUIRED:
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_text("x\n", encoding="utf-8")
    (tmp_path / "skills").mkdir()
    (tmp_path / "skills" / "private-notes.txt").write_text("ignored\n", encoding="utf-8")
    (tmp_path / ".git").mkdir()

    with pytest.raises(RuntimeError, match="Git cannot list"):
        backend(ROOT)._shipped(tmp_path)


@pytest.mark.parametrize(
    ("version", "wheel"),
    [("1.2.0", "1.2.0"), ("1.2.0-rc.1", "1.2.0rc1"), ("1.2.0-beta.2", "1.2.0b2")],
)
def test_the_wheel_spells_a_release_as_pip_reads_it(
    tmp_path: Path, version: str, wheel: str
) -> None:
    (tmp_path / "VERSION").write_text(f"{version}\n", encoding="utf-8")

    assert backend(ROOT)._version(tmp_path) == wheel
