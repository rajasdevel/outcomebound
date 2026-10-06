import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from outcomebound_tools.declared_tests import PYTEST, UNITTEST
from outcomebound_tools.discovery import DiscoveryError, discover
from tests.portable import needs_symlinks, write

ROOT = Path(__file__).resolve().parent.parent


def test_monorepo_observes_markers_scripts_and_workflow_paths_without_runtime_claims(tmp_path):
    frontend = tmp_path / "frontend"
    backend = tmp_path / "backend"
    workflows = tmp_path / ".github" / "workflows"
    frontend.mkdir()
    backend.mkdir()
    workflows.mkdir(parents=True)
    write(frontend / "package-lock.json", "{}\n")
    write(
        frontend / "package.json",
        json.dumps({"scripts": {"test": "vitest run", "lint": "eslint ."}}),
    )
    write(backend / "go.mod", "module example.invalid/api\n")
    write(workflows / "check.yml", "name: check\n")
    write(tmp_path / "CONTRIBUTING.md", "Use the existing workflow.\n")

    result = discover(tmp_path, roots=["frontend", "backend"])

    assert {(row["kind"], row["root"]) for row in result["observed"]["markers"]} >= {
        ("node", "frontend"),
        ("go", "backend"),
    }
    package = result["observed"]["package_scripts"][0]
    assert package["status"] == "parsed"
    assert package["scripts"] == [
        {
            "name": "lint",
            "command": "eslint .",
            "invocation": "npm run lint",
            "execution_status": "UNVERIFIED",
        },
        {
            "name": "test",
            "command": "vitest run",
            "invocation": "npm test",
            "execution_status": "UNVERIFIED",
        },
    ]
    workflows_observed = {row["path"]: row for row in result["observed"]["workflow_refs"]}
    # CI configuration is not observed; the project's workflow documents are.
    assert sorted(workflows_observed) == ["CONTRIBUTING.md"]
    assert workflows_observed["CONTRIBUTING.md"]["kind"] == "project-workflow"
    assert workflows_observed["CONTRIBUTING.md"]["evidence"].strip()
    components = {row["root"]: row for row in result["inferred"]["components"]}
    assert components["frontend"]["modules"] == ["frontend"]
    assert components["frontend"]["test_options"][0] == "npm test"
    assert components["backend"]["modules"] == ["go"]
    assert components["backend"]["test_options"] == ["go test ./..."]


@needs_symlinks
def test_symlinked_files_and_directories_cannot_escape_the_target(tmp_path):
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.mkdir()
    write(outside / "package.json", json.dumps({"scripts": {"test": "would-leak"}}))
    os.symlink(outside, tmp_path / "linked-component")
    os.symlink(outside / "package.json", tmp_path / "package.json")

    result = discover(tmp_path)

    assert result["observed"]["markers"] == []
    assert result["observed"]["package_scripts"] == []
    assert result["observed"]["skipped"] == [
        {"path": "linked-component", "reason": "symlink"},
        {"path": "package.json", "reason": "symlink"},
    ]
    assert "would-leak" not in json.dumps(result)
    with pytest.raises(DiscoveryError, match="crosses a symlink"):
        discover(tmp_path, roots=["linked-component"])


def test_malformed_package_json_is_evidence_not_a_crash_or_a_guessed_command(tmp_path):
    write(tmp_path / "package.json", '{"scripts": {"test": ')

    result = discover(tmp_path)

    package = result["observed"]["package_scripts"][0]
    assert package == {
        "path": "package.json",
        "status": "malformed",
        "evidence": "package.json is not valid JSON",
        "scripts": [],
    }
    assert any(row["subject"] == "package-scripts:package.json" for row in result["unknown"])
    component = result["inferred"]["components"][0]
    assert component["modules"] == ["frontend"]
    assert component["test_options"] == []


def test_a_package_json_saved_with_a_byte_order_mark_and_crlf_is_parsed(tmp_path):
    """PowerShell 5.1's `Set-Content -Encoding UTF8` writes a mark, and `json.loads` refuses a
    string that starts with one: the file was read as malformed, and no script was observed."""

    document = json.dumps({"scripts": {"test": "vitest run"}}, indent=2)
    (tmp_path / "package.json").write_bytes(
        b"\xef\xbb\xbf" + document.replace("\n", "\r\n").encode("utf-8")
    )

    package = discover(tmp_path)["observed"]["package_scripts"][0]

    assert package["status"] == "parsed"
    assert [row["name"] for row in package["scripts"]] == ["test"]


def test_package_manager_declaration_is_used_and_conflicts_are_unresolved(tmp_path):
    package = tmp_path / "package.json"
    write(package, json.dumps({"packageManager": "pnpm@9.7.0", "scripts": {"test": "vitest run"}}))

    declared = discover(tmp_path)
    evidence = declared["observed"]["package_scripts"][0]
    assert evidence["manager"] == {
        "status": "observed",
        "name": "pnpm",
        "evidence": ["package.json packageManager declares pnpm"],
    }
    assert evidence["scripts"][0]["invocation"] == "pnpm test"

    write(tmp_path / "package-lock.json", "{}\n")
    conflicted = discover(tmp_path)
    evidence = conflicted["observed"]["package_scripts"][0]
    assert evidence["manager"] == {
        "status": "unresolved",
        "candidates": ["npm", "pnpm"],
        "evidence": [
            "package-lock.json indicates npm",
            "package.json packageManager declares pnpm",
        ],
    }
    assert evidence["scripts"][0]["invocation"] is None
    assert any(row["subject"] == "package-manager:package.json" for row in conflicted["unknown"])


def test_depth_pruning_is_reported_as_unknown_completeness(tmp_path):
    deep = tmp_path
    for name in ("one", "two", "three", "four", "five"):
        deep = deep / name
        deep.mkdir()
    write(deep / "go.mod", "module example.invalid/deep\n")

    result = discover(tmp_path)

    assert result["observed"]["markers"] == []
    assert any(row["subject"] == "discovery-completeness" for row in result["unknown"])


def test_cli_emits_json_and_does_not_change_the_target(tmp_path):
    write(tmp_path / "pyproject.toml", "[project]\nname='sample'\n")
    before = sorted(path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*"))

    result = subprocess.run(
        [sys.executable, "-m", "outcomebound_tools.discovery", str(tmp_path)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert set(payload) == {"format_version", "result", "observations"}
    assert payload["format_version"] == 1 and payload["result"] == "PASS"
    after = sorted(path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*"))
    assert after == before


@needs_symlinks
def test_harness_directories_are_observed_and_recommended_not_chosen(tmp_path):
    """Markers are observations; the harness stays an open decision.

    Discovery records which recognized harness directories exist. It never picks
    one: a shared directory names two candidates, and a bare `.agents/` names none.
    """

    from outcomebound_tools.discovery import HARNESS_MARKER_CANDIDATES, harness_markers

    empty = tmp_path / "empty"
    empty.mkdir()
    assert discover(empty)["observed"]["harness_markers"] == []

    bare = tmp_path / "bare-agents"
    (bare / ".agents").mkdir(parents=True)
    assert discover(bare)["observed"]["harness_markers"] == []

    shared = tmp_path / "shared"
    (shared / ".agents/skills").mkdir(parents=True)
    assert discover(shared)["observed"]["harness_markers"] == [".agents/skills/"]
    assert HARNESS_MARKER_CANDIDATES[".agents/skills/"] == ("amp", "codex")

    unique = tmp_path / "unique"
    (unique / ".codex").mkdir(parents=True)
    observations = discover(unique)["observed"]["harness_markers"]
    assert observations == [".codex/"]
    assert HARNESS_MARKER_CANDIDATES[".codex/"] == ("codex",)

    several = tmp_path / "several"
    for name in (".claude", ".codex", ".cursor", ".gemini", ".agents/skills"):
        (several / name).mkdir(parents=True)
    markers = discover(several)["observed"]["harness_markers"]
    assert (
        markers
        == sorted(set(markers))
        == [
            ".agents/skills/",
            ".claude/",
            ".codex/",
            ".cursor/",
            ".gemini/",
        ]
    )
    # Observed twice is one observation, and one call is already deduplicated.
    assert harness_markers(several) == markers == harness_markers(several)

    # A file named like a marker is not a directory, and a symlinked directory
    # is never followed — either would credit a harness nothing established.
    files = tmp_path / "files"
    files.mkdir()
    write(files / ".claude", "not a directory")
    outside = tmp_path / "outside"
    (outside / "skills").mkdir(parents=True)
    (files / ".codex").symlink_to(outside, target_is_directory=True)
    (files / ".agents").mkdir()
    (files / ".agents/skills").symlink_to(outside / "skills", target_is_directory=True)
    assert discover(files)["observed"]["harness_markers"] == []

    # Nothing about the harness decision is closed by any of this.
    assert {row["subject"] for row in discover(several)["unknown"]} >= {"harness"}


def test_every_recognized_marker_maps_to_known_harness_candidates():
    """Each recognized marker names only harnesses the table knows; discovery chooses none."""

    from outcomebound_tools import adapters
    from outcomebound_tools.discovery import HARNESS_MARKER_CANDIDATES

    assert sorted(HARNESS_MARKER_CANDIDATES) == [
        ".agents/skills/",
        ".claude/",
        ".codex/",
        ".cursor/",
        ".gemini/",
    ]
    known = set(adapters.harness_names())
    for marker, candidates in HARNESS_MARKER_CANDIDATES.items():
        assert candidates == tuple(sorted(candidates)) and candidates
        assert set(candidates) <= known, marker


# --- check candidates ------------------------------------------------------------------


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    write(path, text)


def test_check_candidates_are_allowlisted_and_require_explicit_confirmation(tmp_path):
    """Only allowlisted names become candidates, and a name proves nothing.

    `test` here runs a deployment. The allowlist decides which observed scripts
    are OFFERED; it never decides what they do, so every candidate carries the
    unverified-effects label and none of them is confirmed.
    """

    from outcomebound_tools.discovery import CANDIDATE_LABEL

    target = tmp_path / "scripts"
    (target / ".git").mkdir(parents=True)
    _write(target / "package-lock.json", "{}\n")
    _write(
        target / "package.json",
        json.dumps(
            {
                "scripts": {
                    "test": "deploy-to-production",
                    "test:unit": "vitest run",
                    "lint": "eslint .",
                    "lint:css": "stylelint .",
                    "typecheck": "tsc --noEmit",
                    "check": "npm run lint && npm run test",
                    "verify": "node verify.mjs",
                    "format:check": "prettier --check .",
                    "build": "vite build",
                    "dev": "vite",
                    "start": "node server.mjs",
                    "serve": "http-server",
                    "release": "npm publish",
                }
            }
        ),
    )

    observations = discover(target)
    component = observations["inferred"]["components"][0]

    assert component["test_options"] == [
        "npm test",
        "npm run check",
        "npm run typecheck",
        "npm run lint",
        "npm run format:check",
        "npm run lint:css",
        "npm run test:unit",
        "npm run verify",
    ]
    assert [row["command"] for row in component["check_candidates"]] == component["test_options"]
    assert {row["label"] for row in component["check_candidates"]} == {CANDIDATE_LABEL}
    assert all(row["confirmed"] is False for row in component["check_candidates"])

    # Excluded names stay observations, never candidates.
    observed = {row["name"] for row in observations["observed"]["package_scripts"][0]["scripts"]}
    assert {"build", "dev", "start", "serve", "release"} <= observed
    assert not any(
        name in candidate["command"]
        for candidate in component["check_candidates"]
        for name in ("build", "dev", "start", "serve", "release")
    )

    # `npm test` is the first candidate and it deploys. The label is the only
    # claim made about it; nothing here says the allowlist makes it harmless.
    assert component["check_candidates"][0]["command"] == "npm test"
    assert "unverified" in CANDIDATE_LABEL


# --- the test runner the project declares ---------------------------------------------

PYPROJECT = '[project]\nname = "x"\n'


def _write_files(target: Path, files: dict[str, str]) -> None:
    for relative, text in files.items():
        path = target / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        write(path, text)


def _test_options(target: Path, root: str = ".") -> list[str]:
    components = discover(target)["inferred"]["components"]
    options: list[str] = next(row for row in components if row["root"] == root)["test_options"]
    return options


PYTEST_SIGNALS = {
    "pytest-ini": {"pytest.ini": "[pytest]\naddopts = -q\n"},
    "pyproject-ini-options": {
        "pyproject.toml": PYPROJECT + '[tool.pytest.ini_options]\naddopts = "-q"\n'
    },
    "setup-cfg": {"setup.cfg": "[tool:pytest]\naddopts = -q\n"},
    "tox-ini-pytest": {"tox.ini": "[pytest]\naddopts = -q\n"},
    "conftest-root": {"conftest.py": ""},
    "conftest-tests": {"tests/conftest.py": ""},
    "optional-dependencies": {
        "pyproject.toml": PYPROJECT
        + '[project.optional-dependencies]\ntest = ["pytest>=8", "pytest-cov"]\n'
    },
    "dependency-groups": {
        "pyproject.toml": PYPROJECT
        + "[dependency-groups]\ndev = [\"pytest[testing]; python_version >= '3.10'\"]\n"
    },
    "poetry-group": {
        "pyproject.toml": PYPROJECT + '[tool.poetry.group.dev.dependencies]\npytest = "^8.0"\n'
    },
    "requirements-dev": {"requirements-dev.txt": "ruff==0.6.9\npytest>=8  # the runner\n"},
    "oversized-setup-cfg": {"setup.cfg": "[tool:pytest]\n" + "# padding\n" * 120_000},
}


@pytest.mark.parametrize("signal", sorted(PYTEST_SIGNALS))
def test_a_python_root_offers_pytest_from_each_declared_signal(tmp_path: Path, signal: str) -> None:
    """pytest configured anywhere the project declares it is offered before any fallback."""

    _write_files(tmp_path, {"pyproject.toml": PYPROJECT, **PYTEST_SIGNALS[signal]})
    (tmp_path / "tests").mkdir(exist_ok=True)

    options = _test_options(tmp_path)

    if signal == "oversized-setup-cfg":
        # A file over the read limit gives no signal, and raises nothing.
        assert options == [UNITTEST]
    else:
        assert options[0] == PYTEST
        assert UNITTEST not in options


def test_a_pytest_plugin_alone_is_not_a_pytest_signal(tmp_path: Path) -> None:
    """`pytest-cov` names a plugin, not the runner; the fallback stands."""

    _write_files(
        tmp_path,
        {"pyproject.toml": PYPROJECT + '[project.optional-dependencies]\ntest = ["pytest-cov"]\n'},
    )
    (tmp_path / "tests").mkdir()

    assert _test_options(tmp_path) == [UNITTEST]


@pytest.mark.parametrize(
    ("files", "offered"),
    [
        ({"tox.ini": "[flake8]\nmax-line-length = 100\n"}, False),
        ({"tox.ini": "[tox]\nenvlist = py312\n"}, True),
        ({"tox.ini": "[testenv:lint]\ncommands = ruff check .\n"}, True),
        ({"pyproject.toml": PYPROJECT + '[tool.tox]\nenv_list = ["3.12"]\n'}, True),
    ],
)
def test_tox_is_offered_only_for_a_config_that_declares_an_environment(
    tmp_path: Path, files: dict[str, str], offered: bool
) -> None:
    """A lint-only `tox.ini` declares no environment to run, so it offers no `tox`."""

    _write_files(tmp_path, {"pyproject.toml": PYPROJECT, **files})

    assert ("tox" in _test_options(tmp_path)) is offered


@needs_symlinks
def test_unittest_is_offered_only_where_a_tests_directory_exists(tmp_path: Path) -> None:
    """The unittest fallback names `-s tests`; it is offered only where that directory is."""

    target = tmp_path / "project"
    _write_files(target, {"pyproject.toml": PYPROJECT})
    assert _test_options(target) == []

    (target / "tests").mkdir()
    assert _test_options(target) == [UNITTEST]

    (target / "tests").rmdir()
    (tmp_path / "elsewhere").mkdir()
    (target / "tests").symlink_to(tmp_path / "elsewhere", target_is_directory=True)
    assert _test_options(target) == []


def test_a_make_or_just_test_target_is_offered_after_the_stack_runners(tmp_path: Path) -> None:
    """A declared `make test` or `just test` follows the stack's own runners, never a variable."""

    def options(name: str, files: dict[str, str], *, tests: bool = True) -> list[str]:
        target = tmp_path / name
        _write_files(target, files)
        if tests:
            (target / "tests").mkdir(exist_ok=True)
        return _test_options(target)

    python = {"pyproject.toml": PYPROJECT}
    assert options("plain", {**python, "Makefile": "test:\n\tpython3 -m unittest\n"}) == [
        UNITTEST,
        "make test",
    ]
    assert options("listed", {**python, "Makefile": "lint test:\n\ttrue\n"}) == [
        UNITTEST,
        "make test",
    ]
    assert options("variable", {**python, "Makefile": "test := 1\n.PHONY: test\n"}) == [UNITTEST]
    assert options("just", {**python, "justfile": "test *args:\n    pytest {{args}}\n"}) == [
        UNITTEST,
        "just test",
    ]
    go = {"go.mod": "module example.com/x\n\ngo 1.22\n", "Makefile": "test:\n\tgo test ./...\n"}
    assert options("go", go, tests=False) == ["go test ./...", "make test"]
    observed = {
        "pyproject.toml": PYPROJECT + '[tool.pytest.ini_options]\naddopts = "-q"\n',
        "conftest.py": "",
        "Makefile": ".PHONY: test\ntest:\n\tpython3 -m pytest\n",
    }
    assert options("observed", observed) == [PYTEST, "make test"]


def test_a_workspace_member_reads_the_lockfile_of_its_workspace(tmp_path: Path) -> None:
    """A member's scripts run through the workspace's manager, named by its lockfile above."""

    _write_files(
        tmp_path,
        {
            "package.json": json.dumps({"name": "root", "workspaces": ["packages/*"]}),
            "pnpm-lock.yaml": "lockfileVersion: '9.0'\n",
            "packages/web/package.json": json.dumps(
                {"name": "web", "scripts": {"test": "vitest run"}}
            ),
            "packages/api/package.json": json.dumps(
                {"name": "api", "scripts": {"test": "node --test"}}
            ),
            "packages/api/yarn.lock": "# yarn lockfile v1\n",
        },
    )

    observations = discover(tmp_path)

    packages = {row["path"]: row for row in observations["observed"]["package_scripts"]}
    web = packages["packages/web/package.json"]["manager"]
    assert web["name"] == "pnpm"
    assert web["evidence"] == ["pnpm-lock.yaml in an enclosing directory indicates pnpm"]
    assert _test_options(tmp_path, "packages/web") == ["pnpm test"]
    # A member with its own lockfile is named by that lockfile, not the workspace's.
    api = packages["packages/api/package.json"]["manager"]
    assert (api["name"], api["evidence"]) == ("yarn", ["yarn.lock indicates yarn"])
    assert _test_options(tmp_path, "packages/api") == ["yarn test"]


def test_a_go_work_root_without_a_module_offers_no_go_test(tmp_path: Path) -> None:
    """`go test ./...` at a `go.work` root with no module matches no package."""

    _write_files(
        tmp_path,
        {
            "go.work": "go 1.22\n\nuse ./svc\n",
            "svc/go.mod": "module example.com/svc\n\ngo 1.22\n",
        },
    )
    assert _test_options(tmp_path) == []
    assert _test_options(tmp_path, "svc") == ["go test ./..."]

    # Beside a module, the workspace root is that module's root too.
    write(tmp_path / "go.mod", "module example.com/top\n\ngo 1.22\n")
    assert _test_options(tmp_path) == ["go test ./..."]


def test_discovery_document_roundtrips_against_its_schema(tmp_path):
    """The ephemeral document has a versioned envelope and a shipped schema."""

    from outcomebound_tools.discovery import validate_document

    for name, marker, expected in (
        ("bare", ".agents", []),
        ("shared", ".agents/skills", [".agents/skills/"]),
        ("unique", ".codex", [".codex/"]),
    ):
        target = tmp_path / name
        (target / marker).mkdir(parents=True)
        write(target / "pyproject.toml", "[project]\nname = 'greeting'\n")
        write(target / "CONTRIBUTING.md", "Keep changes in scope.\n")
        document = {"format_version": 1, "result": "PASS", "observations": discover(target)}
        markers = document["observations"]["observed"]["harness_markers"]
        assert markers == expected == sorted(set(markers))
        assert validate_document(json.loads(json.dumps(document))) == document

    # The document is ephemeral: emitting it writes nothing into the target.
    before = sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*"))
    discover(tmp_path / "bare")
    assert sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*")) == before


# --- markers a directory listing carries -------------------------------------------


def _sample_project(root):
    """A python component at the root, with its scripts under `scripts/`."""

    root.mkdir(parents=True, exist_ok=True)
    write(root / "pyproject.toml", "[project]\nname='sample'\n")
    package = root / "sample"
    package.mkdir()
    write(package / "__init__.py", "")
    scripts = root / "scripts"
    scripts.mkdir()
    entry = scripts / "run.sh"
    write(entry, "#!/bin/sh\necho run\n")
    entry.chmod(0o755)
    library = scripts / "helpers.sh"
    write(library, "#!/bin/sh\n# library\n")
    library.chmod(0o755)
    plain = scripts / "notexec.sh"
    write(plain, "#!/bin/sh\necho plain\n")
    plain.chmod(0o644)
    return root


def test_markers_are_observed_from_the_filesystem_only(tmp_path):
    """Every marker kind is read from paths alone: no command runs and nothing is written.

    A shell marker qualifies a root the project already has — here the target
    root — rather than making `scripts/` a component of its own.
    """

    target = _sample_project(tmp_path / "project")
    write(target / "composer.json", "{}\n")
    write(target / "Cargo.toml", "[package]\n")
    (target / "migrations").mkdir()
    before = sorted(path.relative_to(target).as_posix() for path in target.rglob("*"))

    observations = discover(target)
    components = {row["root"]: row for row in observations["inferred"]["components"]}

    kinds = {row["kind"] for row in observations["observed"]["markers"]}
    assert {"python", "shell", "php", "rust", "sql"} <= kinds
    # `scripts/` is not a root any other marker infers, so it is not a component.
    assert set(components) == {"."}
    assert components["."]["modules"] == ["python"]
    assert sorted(path.relative_to(target).as_posix() for path in target.rglob("*")) == before


def test_shell_markers_only_qualify_roots_other_markers_infer(tmp_path):
    """A script far below the target, or in a directory nothing else names, infers nothing."""

    target = tmp_path / "project"
    (target / "vendor" / "tools" / "deep").mkdir(parents=True)
    write(target / "vendor" / "tools" / "deep" / "build.sh", "#!/bin/sh\n")
    api = target / "services" / "api"
    api.mkdir(parents=True)
    write(api / "go.mod", "module example.invalid/api\n")
    write(api / "run.sh", "#!/bin/sh\n")

    components = {row["root"]: row for row in discover(target)["inferred"]["components"]}

    # `vendor/tools/deep` names no component, and its script is four segments
    # below the target root, so it qualifies nothing.
    assert set(components) == {"services/api"}
    kinds = {row["kind"] for row in discover(target)["observed"]["markers"]}
    assert kinds == {"go", "shell"}


def test_a_script_qualifies_only_its_nearest_root(tmp_path):
    """A script belongs to one component: the nearest candidate root above it."""

    target = tmp_path / "project"
    api = target / "api"
    api.mkdir(parents=True)
    write(api / "go.mod", "module example.invalid/api\n")
    write(api / "run.sh", "#!/bin/sh\n")

    observations = discover(target)
    shell = [row for row in observations["observed"]["markers"] if row["kind"] == "shell"]

    assert [row["root"] for row in observations["inferred"]["components"]] == ["api"]
    assert [(row["root"], row["path"]) for row in shell] == [("api", "api/run.sh")]

    bin_dir = target / "bin"
    bin_dir.mkdir()
    write(bin_dir / "x.sh", "#!/bin/sh\n")

    observations = discover(target)
    shell = [row for row in observations["observed"]["markers"] if row["kind"] == "shell"]

    assert [row["root"] for row in observations["inferred"]["components"]] == [".", "api"]
    # `markers` is sorted by path, so `api/run.sh` precedes `bin/x.sh`.
    assert [(row["root"], row["path"]) for row in shell] == [
        ("api", "api/run.sh"),
        (".", "bin/x.sh"),
    ]


def test_shell_script_collection_reports_its_own_limit(tmp_path):
    """Scripts are a bounded population; stopping at the cap is said out loud."""

    from outcomebound_tools.discovery import MAX_SHELL_SCRIPTS

    target = tmp_path / "project"
    scripts = target / "scripts"
    scripts.mkdir(parents=True)
    write(target / "pyproject.toml", "[project]\nname='x'\n")
    for index in range(MAX_SHELL_SCRIPTS + 1):
        write(scripts / f"s{index:04d}.sh", "#!/bin/sh\n")

    limits = discover(target)["limits"]

    assert any(
        f"shell-script collection stopped at the {MAX_SHELL_SCRIPTS}-file limit" in row
        for row in limits
    ), limits


@needs_symlinks
def test_a_symlinked_script_directory_is_skipped(tmp_path):
    """A symlinked `scripts/` is recorded as skipped and walked by nothing."""

    outside = tmp_path / "outside"
    outside.mkdir()
    escape = outside / "escape.sh"
    write(escape, "#!/bin/sh\necho escape\n")
    escape.chmod(0o755)
    target = tmp_path / "project"
    app = target / "app"
    app.mkdir(parents=True)
    write(app / "pyproject.toml", "[project]\nname='app'\n")
    (app / "scripts").symlink_to(outside, target_is_directory=True)

    observations = discover(target)

    assert {"app/scripts"} == {
        row["path"] for row in observations["observed"]["skipped"] if row["reason"] == "symlink"
    }


def test_discovery_executes_nothing(tmp_path):
    """A script or package command that writes when run is observed, never invoked."""

    target = _sample_project(tmp_path / "project")
    marker = tmp_path / "ran.txt"
    saboteur = target / "scripts" / "sabotage.sh"
    write(saboteur, f"#!/bin/sh\ntouch {marker}\n")
    saboteur.chmod(0o755)
    write(target / "package.json", json.dumps({"scripts": {"test": f"touch {marker}"}}))

    observations = discover(target)

    assert not marker.exists()
    assert all(
        row["execution_status"] == "UNVERIFIED"
        for package in observations["observed"]["package_scripts"]
        for row in package["scripts"]
    )


def test_discovery_names_a_harness_root_the_project_tracks_and_fills(tmp_path: Path) -> None:
    """A `.agents/skills/` the project keeps its own skills in is an observation."""

    import subprocess

    target = tmp_path / "project"
    (target / ".agents" / "skills" / "release-notes").mkdir(parents=True)
    write(target / ".agents/skills/release-notes/SKILL.md", "---\nname: release-notes\n---\n")
    write(target / "pyproject.toml", "[project]\nname = 'sample'\n")
    subprocess.run(["git", "-C", str(target), "init", "-q"], check=True)
    untracked = discover(target)
    assert untracked["observed"]["project_skill_roots"] == []
    subprocess.run(["git", "-C", str(target), "add", "."], check=True)

    observations = discover(target)

    assert observations["observed"]["project_skill_roots"] == [
        {"path": ".agents/skills", "tracked": True, "skills": ["release-notes"]}
    ]


def test_what_git_ignores_and_nested_repositories_are_not_entered(tmp_path: Path) -> None:
    """In a Git work tree an ignored folder is never walked, so it cannot use up the entry
    limit, and a nested repository's metadata is never read as this project's."""

    target = tmp_path / "project"
    target.mkdir()
    subprocess.run(["git", "init", "-q", str(target)], check=True)
    write(target / ".gitignore", "out/\n*.local.json\n")
    (target / "out" / "big").mkdir(parents=True)
    write(target / "out" / "pyproject.toml", "[project]\n")
    write(target / "package.local.json", "{}\n")
    nested = target / "vendor-src" / "tool"
    nested.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(nested)], check=True)
    write(nested / "package.json", json.dumps({"scripts": {"test": "jest"}}))
    write(target / "go.mod", "module example.invalid/p\n")

    result = discover(target)

    paths = {row["path"] for row in result["observed"]["markers"]}
    assert paths == {"go.mod"}
    assert result["observed"]["package_scripts"] == []
    assert "what Git ignores was not entered" in result["limits"]
    assert "nested repositories were not entered" in result["limits"]


def test_outside_git_the_report_says_no_gitignore_was_applied(tmp_path: Path) -> None:
    target = tmp_path / "plain"
    (target / "out").mkdir(parents=True)
    write(target / ".gitignore", "out/\n")
    write(target / "out" / "go.mod", "module example.invalid/p\n")

    result = discover(target)

    assert {row["path"] for row in result["observed"]["markers"]} == {"out/go.mod"}
    assert any("no .gitignore was applied" in row for row in result["limits"])


def test_a_git_listing_that_is_not_utf8_still_shows_a_tracked_skill_root(tmp_path, monkeypatch):
    """Git's output was decoded with the ANSI code page on Windows, and a byte that page leaves
    undefined (0x81) raised inside `subprocess.run`. A child that prints such a byte stands in
    for Git."""

    from outcomebound_tools import harness_roots

    (tmp_path / ".claude/skills/own").mkdir(parents=True)
    real = subprocess.run

    def child(argv, **options):
        code = "import sys; sys.stdout.buffer.write(b'.claude/skills/own/\\x81.md\\n')"
        return real([sys.executable, "-c", code], **options)

    monkeypatch.setattr(harness_roots.subprocess, "run", child)

    found = harness_roots.project_skill_roots(tmp_path, [".claude/skills"])

    assert found == [{"path": ".claude/skills", "tracked": True, "skills": ["own"]}]
