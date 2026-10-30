"""Copies keep installation inputs; inspection and execution use the right view."""

from __future__ import annotations

import hashlib
import runpy
import shlex
import shutil

import pytest

from tests.portable import needs_make, needs_posix_bash, session_graders_posix
from tests.test_long_fixture_effects import COMMON, run
from tests.test_long_fixture_reexecution import DELIVERED, commit


@pytest.fixture
def delivery(tmp_path):
    root, stage = tmp_path / "project", tmp_path / "stage"
    (root / "tests").mkdir(parents=True)
    (root / "tests/__init__.py").touch()
    (root / "feature.py").write_text("VALUE = 0\n", encoding="utf-8")
    (root / "tests/test_feature.py").write_text(
        "import unittest\nimport feature\nclass Feature(unittest.TestCase):\n"
        "    def test_original(self): self.assertEqual(feature.VALUE, 0)\n",
        encoding="utf-8",
    )
    (root / "tools").mkdir()
    shutil.copyfile(COMMON / "receipt_runtime.py", root / "tools/ob_receipts.py")
    (root / "tools/check.py").write_text(
        "import sys\nfrom pathlib import Path\nsys.path.insert(0, str(Path.cwd()))\n"
        "import feature\nassert feature.VALUE == 0\n",
        encoding="utf-8",
    )
    (root / "Makefile").write_text("check:\n\tpython3 -B tools/check.py\n", encoding="utf-8")
    assert run(root, "git", "init", "-q").returncode == 0
    commit(root, "Seed")
    assert run(root, "git", "tag", "seed").returncode == 0
    stage.mkdir()
    for name in ("delivered.py", "commands.py"):
        shutil.copyfile(COMMON / name, stage / name)
    DELIVERED["seal"](root, stage / "seed-checks")
    return root, runpy.run_path(str(stage / "delivered.py"))


INSTALL = (".agents/skills/example/SKILL.md", ".agents/.gitignore", ".outcomebound/manifest.json")
EVIDENCE = (
    ".agents/work/private.txt",
    ".agents/worktrees/private.txt",
    ".agents/handoffs/private.txt",
    ".agents/shared-memory/private.txt",
    ".outcomebound/research-inbox/private.txt",
    ".outcomebound-checks/private.txt",
)


@pytest.mark.parametrize("revision", [None, "HEAD"])
def test_snapshot_keeps_installation_but_not_evidence(delivery, revision):
    root, grader = delivery
    for name in (*INSTALL, *EVIDENCE):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(name, encoding="utf-8")
    assert run(root, "git", "add", "-f", *INSTALL, *EVIDENCE).returncode == 0
    commit(root, "Installation and evidence")
    for name in ("hooks/private", "ob-receipts/private", "worktrees/private"):
        path = root / ".git" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("private", encoding="utf-8")
    with grader["snapshot"](root, revision, machinery=False) as copy:
        for name in INSTALL:
            assert (copy / name).read_text(encoding="utf-8") == name
        for name in (*EVIDENCE, ".git/hooks", ".git/ob-receipts", ".git/worktrees"):
            assert not (copy / name).exists(), name
    assert grader["report"](
        "git diff --exit-code HEAD -- .agents/skills .outcomebound/manifest.json",
        root=root,
        revision=revision,
    )


@session_graders_posix
@pytest.mark.parametrize("revision", [None, "HEAD"])
def test_snapshot_links_cannot_restore_excluded_evidence(delivery, revision):
    root, grader = delivery
    for name in (*INSTALL, *EVIDENCE):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(name, encoding="utf-8")
    (root / "install-link").symlink_to(".agents/skills", target_is_directory=True)
    (root / "absolute-install").symlink_to(root / INSTALL[0])
    (root / "agents-link").symlink_to(".agents", target_is_directory=True)
    for index, name in enumerate(EVIDENCE):
        (root / f"evidence-{index}").symlink_to(name)
    (root / "chained-evidence").symlink_to("evidence-0")
    (root / "absolute-evidence").symlink_to(root / EVIDENCE[0])
    for name in ("hooks", "ob-receipts", "worktrees"):
        folder = root / ".git" / name
        folder.mkdir(exist_ok=True)
        (folder / "private").write_text("private", encoding="utf-8")
        (root / ".git" / ("alias-" + name)).symlink_to(name, target_is_directory=True)
    assert run(root, "git", "add", "-f", ".").returncode == 0
    commit(root, "Links")
    with grader["snapshot"](root, revision, machinery=False) as copy:
        assert (copy / "install-link/example/SKILL.md").read_text(encoding="utf-8") == INSTALL[0]
        assert (copy / "absolute-install").read_text(encoding="utf-8") == INSTALL[0]
        assert not (copy / "agents-link/work").exists()
        for name in ("hooks", "ob-receipts", "worktrees"):
            assert not (copy / ".git" / ("alias-" + name)).is_symlink()
        for name in (
            "chained-evidence",
            "absolute-evidence",
            *(f"evidence-{i}" for i in range(len(EVIDENCE))),
        ):
            assert not (copy / name).is_symlink(), name
            assert not (copy / name).exists(), name


def observe(text):
    return "python3 -B tools/ob_receipts.py observe " + text


@pytest.mark.parametrize("seed_control", [True, False])
def test_wrapped_added_test_needs_failing_seed_control(delivery, seed_control):
    root, grader = delivery
    (root / "feature.py").write_text("VALUE = 1\n", encoding="utf-8")
    path = root / "tests/test_feature.py"
    path.write_text(
        path.read_text(encoding="utf-8")
        + "    def test_added(self): "
        + ("self.assertEqual(feature.VALUE, 1)" if seed_control else "self.assertTrue(True)")
        + "\n",
        encoding="utf-8",
    )
    text = observe("python3 -B -m unittest tests.test_feature.Feature.test_added")
    if seed_control:
        assert grader["report"](text, root=root) is True
        (root / "feature.py").write_text("VALUE = 0\n", encoding="utf-8")
        assert grader["report"](text, root=root) is False
    else:
        with pytest.raises(ValueError, match="no failing seed control"):
            grader["report"](text, root=root)


@pytest.mark.parametrize("runner", ["unittest", "pytest"])
def test_wrapped_zero_tests_get_no_credit(delivery, runner):
    root, grader = delivery
    # A local synthetic runner supplies the runner's successful empty-result output.
    if runner == "pytest":
        (root / "pytest.py").write_text("print('no tests ran')\n", encoding="utf-8")
        text = "python3 -m pytest"
    else:
        text = "python3 -B -m unittest discover -s tests -p absent.py"
    assert grader["report"](observe(text), root=root) is False


@needs_make
@pytest.mark.parametrize("mode", ["-n", "--dry-ru", "-q", "-t", "MAKEFLAGS=n"])
def test_wrapped_make_nonexecution_gets_no_credit(delivery, mode):
    root, grader = delivery
    (root / "Makefile").write_text("check:\n\ttrue\n", encoding="utf-8")
    text = observe("make " + mode + " check")
    if mode.startswith("MAKEFLAGS="):
        text = "MAKEFLAGS=n " + observe("make check")
    assert grader["report"](text, root=root) is False


@pytest.mark.parametrize("revision", [None, "HEAD"])
@pytest.mark.parametrize("inspection", ["digest", "git", "git-record"])
@pytest.mark.parametrize(
    "wrapper",
    [
        "direct",
        "observer",
        pytest.param("shell", marks=needs_posix_bash),
        "script",
        "runpy",
        "module",
        "exec",
    ],
)
def test_content_checks_see_exact_delivery_even_when_seed_files_changed(
    delivery, revision, inspection, wrapper
):
    root, grader = delivery
    path = root / "tests/test_feature.py"
    path.write_text(path.read_text(encoding="utf-8") + "# release change\n", encoding="utf-8")
    # Checker contents are also delivery inputs, even though their execution is protected.
    (root / "tools/check.py").write_text("raise SystemExit(7)\n", encoding="utf-8")
    commit(root, "Delivery")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    body = (
        "import hashlib, pathlib; "
        "assert hashlib.sha256(pathlib.Path('tests/test_feature.py').read_bytes()).hexdigest()"
        f" == {digest!r}"
        if inspection == "digest"
        else "import subprocess; "
        "subprocess.run(['git', 'diff', '--exit-code', 'HEAD', '--', 'tests', 'tools/check.py'], "
        "check=True)"
    )
    if inspection == "git-record":
        body = (
            "import subprocess; record = {'revision': 'HEAD'}; name = 'tests'; "
            "subprocess.run(['git', 'diff', '--exit-code', record['revision'], '--', "
            "name, 'tools/check.py'], check=True)"
        )
    text = "python3 -B -c " + shlex.quote(body)
    if wrapper == "observer":
        text = observe(text)
    elif wrapper == "shell":
        text = "sh -ec " + shlex.quote(text)
    elif wrapper in {"script", "runpy", "module", "exec"}:
        (root / "tools/inspect_delivery.py").write_text(body + "\n", encoding="utf-8")
        commit(root, "Inspection script")
        text = {
            "script": "python3 -B tools/inspect_delivery.py",
            "module": "python3 -B -m tools.inspect_delivery",
            "runpy": "python3 -B -c \"import runpy; runpy.run_path('tools/inspect_delivery.py')\"",
            "exec": 'python3 -B -c "from pathlib import Path; '
            "exec(Path('tools/inspect_delivery.py').read_text())\"",
        }[wrapper]
    assert grader["report"](text, root=root, revision=revision) is True
    path.write_text("different delivery\n", encoding="utf-8")
    assert grader["report"](text, root=root, revision=revision) is (revision is not None)


@pytest.mark.parametrize(
    "text",
    [
        "python3 -B -m unittest tests.test_feature",
        "python3 -B tools/check.py",
        pytest.param("make check", marks=needs_make),
        observe("python3 -B -m unittest tests.test_feature"),
        pytest.param("sh -ec 'python3 -B tools/check.py'", marks=needs_posix_bash),
        "python3 -B -c \"import runpy; runpy.run_path('tools/check.py')\"",
        'python3 -B -c "import tests.test_feature as t; import unittest; unittest.main(t)"',
        'python3 -B -c "import subprocess; '
        "subprocess.run(['python3', '-B', 'tools/check.py'], check=True)\"",
        'python3 -B -c "from tools import check"',
        "python3 -B -c \"from pathlib import Path; exec(Path('tools/check.py').read_text())\"",
        "python3 -B tools/wrapper.py",
        "python3 -B -m tools.wrapper",
        "python3 -B tools/dynamic_wrapper.py",
        pytest.param("sh tools/wrapper.sh", marks=needs_posix_bash),
        pytest.param("./tools/wrapper.sh", marks=needs_posix_bash),
        pytest.param(". tools/wrapper.sh", marks=needs_posix_bash),
        pytest.param("eval 'python3 -B tools/check.py'", marks=needs_posix_bash),
        "python3 -B -c \"import unittest as u; getattr(u, 'main')('tests.test_feature')\"",
    ],
)
def test_rewritten_seed_execution_cannot_hide_failure(delivery, text):
    root, grader = delivery
    (root / "tools/wrapper.py").write_text(
        "import sys\nfrom pathlib import Path\nsys.path.insert(0, str(Path.cwd()))\n"
        "import tools.check\n",
        encoding="utf-8",
    )
    (root / "tools/dynamic_wrapper.py").write_text(
        "import subprocess\ndef launch(argv): subprocess.run(argv, check=True)\n"
        "launch(['python3', '-B', 'tools/check.py'])\n",
        encoding="utf-8",
    )
    shell = root / "tools/wrapper.sh"
    shell.write_text("#!/bin/sh\npython3 -B tools/check.py\n", encoding="utf-8")
    shell.chmod(0o755)
    assert grader["report"](text, root=root) is True
    (root / "feature.py").write_text("VALUE = 1\n", encoding="utf-8")
    (root / "tests/test_feature.py").write_text(
        "import unittest\nclass Feature(unittest.TestCase):\n"
        "    def test_original(self): self.assertTrue(True)\n",
        encoding="utf-8",
    )
    (root / "tools/check.py").write_text("raise SystemExit(0)\n", encoding="utf-8")
    (root / "Makefile").write_text("check:\n\ttrue\n", encoding="utf-8")
    actual = grader["run"](root, grader["command"](text), machinery=False)
    assert actual.returncode == 0, actual.stdout + actual.stderr
    assert grader["report"](text, root=root) is False


def test_missing_reported_script_is_a_failure(delivery):
    root, grader = delivery
    problems, credit = grader["reports"](
        [{"command": "python3 -B tools/missing.py", "result": "PASS"}], root=root
    )
    assert credit == [False]
    assert grader["exit_code"](problems) == 1


def test_stdin_execution_uses_redirected_paths_before_selecting_machinery(delivery):
    root, grader = delivery
    (root / "feature.py").write_text("VALUE = 1\n", encoding="utf-8")
    (root / "tools/check.py").write_text("raise SystemExit(0)\n", encoding="utf-8")
    body = (
        "from pathlib import Path\nexec(Path("
        + repr(str(root / "tools/check.py"))
        + ").read_text())"
    )
    done = grader["run"](root, ["python3", "-B", "-"], input=body)
    assert done.returncode != 0 and "AssertionError" in done.stderr
