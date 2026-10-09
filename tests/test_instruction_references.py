"""`outcomebound instructions check`, its `stale-reference` check.

A path, a Make target or a package script that project-owned instruction text names and the
target no longer holds is reported as a review hit that never changes the result. Every target
below is inert data under `tmp_path`: the check reads makefiles and `package.json` files as text
and must never run what they hold.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from outcomebound_tools import instruction_audit
from outcomebound_tools.instruction_audit import (
    CHECKS,
    AuditError,
    Finding,
    Report,
    check,
    main,
    report_document,
    stale_references,
)
from outcomebound_tools.schemacheck import validate
from tests.portable import home_environment, needs_symlinks, write

ROOT = Path(__file__).resolve().parent.parent
REPORT_SCHEMA = json.loads(
    (ROOT / "schemas/instruction-audit-report.schema.json").read_text(encoding="utf-8")
)
BEGIN = "<!-- outcomebound:begin id=operating-contract v=1 -->"
END = "<!-- outcomebound:end id=operating-contract -->"


@pytest.fixture(autouse=True)
def _a_person_with_no_rulings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for name, value in home_environment(tmp_path / "person").items():
        monkeypatch.setenv(name, value)


def _target(root: Path, files: dict[str, str]) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    for relative, text in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        write(path, text)
    return root


def _git(root: Path, *arguments: str) -> None:
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=t",
            "-c",
            "user.email=t@example.invalid",
            "-c",
            "commit.gpgsign=false",
            "-c",
            "maintenance.auto=false",
            "-c",
            "gc.auto=0",
            *arguments,
        ],
        cwd=root,
        check=True,
        capture_output=True,
    )


def _repository(root: Path, files: dict[str, str]) -> Path:
    _target(root, files)
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "first")
    return root


def _references(report: Report) -> list[Finding]:
    return [f for f in report.findings if f.check == "stale-reference" and f.verdict != "PASS"]


def _spans(report: Report) -> list[str]:
    """The text each reported reference quotes, in report order."""

    quoted = [re.search(r': "(.*)"$', f.fact) for f in _references(report)]
    return [match.group(1) for match in quoted if match]


def _flagged(root: Path, harness: str = "codex") -> list[str]:
    return _spans(check(root, [harness]))


# --- what is reported, and that it never changes the result ----------------------------


def test_a_path_a_target_and_a_script_the_target_lacks_are_reported_without_changing_the_result(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _target(
        tmp_path / "t",
        {
            "AGENTS.md": (
                "# Rules\n\n"
                "Read `docs/gone.md` and `docs/ok.md`.\n"
                "Run `make deploy`, `make test`, `make lint`.\n"
                "Then `npm run lint` and `npm run build`.\n"
            ),
            "docs/ok.md": "ok\n",
            "Makefile": ".PHONY: lint\ntest:\n\t@echo test\n",
            "package.json": json.dumps({"scripts": {"build": "x"}}),
        },
    )
    report = check(root, ["codex"])

    assert _spans(report) == ["docs/gone.md", "make deploy", "npm run lint"]
    assert [(f.line, f.family, f.kind, f.verdict, f.decides) for f in _references(report)] == [
        (3, "references", "review", "UNVERIFIED", False),
        (4, "references", "review", "UNVERIFIED", False),
        (5, "references", "review", "UNVERIFIED", False),
    ]
    assert {(f.rule, f.severity, f.id) for f in _references(report)} == {
        ("S14", "Agreement (S14)", "")
    }
    assert report.counts["references"] == {"PASS": 0, "FAIL": 0, "UNVERIFIED": 3}
    assert report.result == "PASS"
    assert main(["check", str(root), "--harness", "codex"]) == 0
    assert main(["check", str(root), "--harness", "codex", "--strict"]) == 0
    out = capsys.readouterr().out
    assert out.count("(does not change the result)") >= 3
    assert "stale-reference AGENTS.md:3 UNVERIFIED: a path the target holds neither beside" in out
    assert validate(report_document(report), REPORT_SCHEMA) == []


def test_a_file_with_no_stale_reference_reads_pass(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _target(tmp_path / "t", {"AGENTS.md": "Read `docs/ok.md`.\n", "docs/ok.md": "ok\n"})
    report = check(root, ["codex"])
    assert _references(report) == []
    assert report.counts["references"] == {"PASS": 1, "FAIL": 0, "UNVERIFIED": 0}
    main(["check", str(root), "--harness", "codex", "--verbose"])
    assert "stale-reference AGENTS.md:0 PASS: nothing matched" in capsys.readouterr().out


def test_the_check_is_the_third_family_by_severity() -> None:
    assert CHECKS["stale-reference"] == ("references", "review", "S14")
    assert instruction_audit.FAMILIES == ("security", "references", "loading")
    assert REPORT_SCHEMA["properties"]["counts"]["required"] == [
        "security",
        "references",
        "loading",
    ]


def test_a_reference_has_no_ruling_id_and_a_repeat_on_one_line_counts_once(
    tmp_path: Path,
) -> None:
    root = _target(
        tmp_path / "t", {"AGENTS.md": "`docs/gone.md` and `docs/gone.md`\n", "docs/ok.md": "ok\n"}
    )
    [hit] = _references(check(root, ["codex"]))
    assert (hit.id, hit.ruled, hit.decides) == ("", "", False)


# --- what is a concrete relative path ---------------------------------------------------

NOT_PATHS = [
    "origin/main",
    "@scope/pkg",
    "owner/repo",
    "docs/<name>.md",
    "docs/*.md",
    "docs/{a,b}.md",
    "$HOME/docs/gone.md",
    "~" + "/docs/gone.md",  # written apart so the public-text check sees no home path
    "/docs/gone.md",
    "https://example.invalid/docs/gone.md",
    "C:/docs/gone.md",
    "-docs/gone.md",
    "docs\\gone.md",
    "docs/gone file.md",
    "1.5.0",
    "v1.2",
    "gone.md",
    "legacy/gone.md",
    ".git/config",
    "pytest -q",
    "docs",
]


@pytest.mark.parametrize("span", NOT_PATHS)
def test_a_name_that_is_no_concrete_path_the_target_lacks_is_no_reference(
    tmp_path: Path, span: str
) -> None:
    root = _target(
        tmp_path / "t", {"AGENTS.md": f"Mentions `{span}` here.\n", "docs/ok.md": "ok\n"}
    )
    assert _flagged(root) == []


@pytest.mark.parametrize(
    "span",
    ["docs/ok.md", "./docs/ok.md", "docs/", "docs/ok.md:12", "docs/ok.md::test_it", "docs/ok.md#a"],
)
def test_a_path_the_target_holds_is_no_reference(tmp_path: Path, span: str) -> None:
    root = _target(
        tmp_path / "t", {"AGENTS.md": f"Mentions `{span}` here.\n", "docs/ok.md": "ok\n"}
    )
    assert _flagged(root) == []


@pytest.mark.parametrize(
    "span", ["docs/gone.md", "./docs/gone.md", "docs/gone/", "docs/gone.md:12", "docs/gone.md#a"]
)
def test_a_concrete_path_the_target_lacks_is_a_reference_with_its_location_quoted(
    tmp_path: Path, span: str
) -> None:
    root = _target(
        tmp_path / "t", {"AGENTS.md": f"Mentions `{span}` here.\n", "docs/ok.md": "ok\n"}
    )
    assert _flagged(root) == [span]


def test_a_path_in_git_s_own_folder_is_no_reference(tmp_path: Path) -> None:
    """`.git` may be a file, as in a linked work tree, and holds no `config` there."""

    files = {"AGENTS.md": "See `.git/config` and `.git/info/exclude`.\n", ".git": "gitdir: x\n"}
    assert _flagged(_target(tmp_path / "t", files)) == []


def test_a_path_is_looked_for_beside_the_file_and_at_the_root(tmp_path: Path) -> None:
    root = _target(
        tmp_path / "t",
        {
            "AGENTS.md": "ok\n",
            "top.md": "ok\n",
            "pkg/AGENTS.md": (
                "Beside `notes.md`, at the root `top.md`, from the root `pkg/notes.md`,\n"
                "gone `pkg/gone.md`, gone beside `sub/old.md`, up `../top.md`, up and gone "
                "`../gone.md`.\n"
            ),
            "pkg/notes.md": "ok\n",
            "pkg/sub/keep.md": "ok\n",
        },
    )
    assert _flagged(root) == ["pkg/gone.md", "sub/old.md", "../gone.md"]


def test_a_fenced_block_is_no_reference_and_a_span_that_wraps_reports_its_first_line(
    tmp_path: Path,
) -> None:
    text = "Intro\n\n```text\n`docs/gone.md`\n```\n\nSee `docs/\ngone.md`, wrapped.\n"
    root = _target(tmp_path / "t", {"AGENTS.md": text, "docs/ok.md": "ok\n"})
    # A wrapped span reads with a space where the line broke, so it holds whitespace: no path.
    assert _flagged(root) == []
    text = "Intro\n\n```text\n`docs/gone.md`\n```\n\nThen `docs/gone.md`.\n"
    root = _target(tmp_path / "u", {"AGENTS.md": text, "docs/ok.md": "ok\n"})
    [hit] = _references(check(root, ["codex"]))
    assert hit.line == 7


def test_a_git_ignored_path_is_no_reference_and_one_git_does_not_ignore_is(
    tmp_path: Path,
) -> None:
    files = {
        "AGENTS.md": "Bundle `dist/bundle.js`, log `logs/run.log`, copy `build/out.js`.\n",
        ".gitignore": "dist/\n*.log\n",
        "dist/other.txt": "built\n",
        "logs/keep.txt": "kept\n",
        "build/keep.txt": "kept\n",
    }
    root = _repository(tmp_path / "git", files)
    assert (root / "dist/other.txt").exists()
    assert _flagged(root) == ["build/out.js"]
    # Where Git does not list the target, no ignore rule applies to it.
    bare = _target(tmp_path / "bare", files)
    assert _flagged(bare) == ["dist/bundle.js", "logs/run.log", "build/out.js"]


def test_a_path_that_resolves_outside_the_target_is_skipped(tmp_path: Path) -> None:
    root = _target(
        tmp_path / "t",
        {"AGENTS.md": "Up `../elsewhere/x.md`.\n", "docs/ok.md": "ok\n"},
    )
    (tmp_path / "elsewhere").mkdir()
    assert _flagged(root) == []


@needs_symlinks
def test_a_path_through_a_link_out_of_the_target_is_skipped(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    root = _target(tmp_path / "t", {"AGENTS.md": "See `vendor/missing.md`.\n"})
    (root / "vendor").symlink_to(outside, target_is_directory=True)
    assert _flagged(root) == []


# --- Make targets --------------------------------------------------------------------


def _make(tmp_path: Path, makefile: str, *spans: str, name: str = "Makefile") -> Path:
    text = "".join(f"Run `{span}`.\n" for span in spans)
    return _target(tmp_path / "t", {"AGENTS.md": text, name: makefile})


def test_a_make_target_is_defined_by_a_rule_line_or_a_phony_entry(tmp_path: Path) -> None:
    makefile = (
        "CC = gcc\n"
        "VAR := x\n"
        "export OTHER ::= y\n"
        "# comment: not a rule\n"
        ".PHONY: lint \\\n    docs\n"
        ".SUFFIXES:\n"
        "build test: deps\n\t@echo $@\n"
        "all:: ; @echo all\n"
        "ifeq ($(OS),a:b)\n"
        "cond:\n"
        "endif\n"
    )
    root = _make(
        tmp_path,
        makefile,
        "make build",
        "make test",
        "make lint",
        "make docs",
        "make all",
        "make cond",
        "make CC",
        "make VAR",
        "make SUFFIXES",
        "make nope",
    )
    assert _flagged(root) == ["make CC", "make VAR", "make SUFFIXES", "make nope"]


def test_flags_and_variable_words_are_left_out_of_a_make_command(tmp_path: Path) -> None:
    root = _make(
        tmp_path,
        "test:\n\t@echo\n",
        "make -j4 CC=gcc test",
        "make -k -j 4 test",
        "make -o old.txt test",
        "make test && make nope",
        "make test; echo done",
        "make <target>",
        "make [target]",
        "make $(TARGET)",
        "make",
        "make gone-target",
    )
    assert _flagged(root) == ["make gone-target"]


def test_the_nearest_makefile_upward_is_the_one_looked_in(tmp_path: Path) -> None:
    root = _target(
        tmp_path / "t",
        {
            "AGENTS.md": "Run `make shared`, `make local`.\n",
            "Makefile": "shared:\nroot-only:\n",
            "sub/AGENTS.md": "Run `make local`, `make shared`, `make root-only`.\n",
            "sub/Makefile": "local:\n",
            "deep/er/AGENTS.md": "Run `make shared`, `make local`.\n",
        },
    )
    report = check(root, ["codex"])
    assert [(f.path, s) for f, s in zip(_references(report), _spans(report), strict=True)] == [
        ("AGENTS.md", "make local"),
        ("deep/er/AGENTS.md", "make local"),
        ("sub/AGENTS.md", "make shared"),
        ("sub/AGENTS.md", "make root-only"),
    ]


def test_a_gnumakefile_wins_over_a_makefile(tmp_path: Path) -> None:
    root = _make(tmp_path, "plain:\n", "make gnu", "make plain")
    write(root / "GNUmakefile", "gnu:\n")
    assert _flagged(root) == ["make plain"]


def test_a_make_target_with_no_makefile_at_or_above_is_a_reference(tmp_path: Path) -> None:
    root = _target(tmp_path / "t", {"AGENTS.md": "Run `make test`.\n"})
    report = check(root, ["codex"])
    assert _spans(report) == ["make test"]
    assert "no makefile is at or above this file" in _references(report)[0].fact


@pytest.mark.parametrize(
    "makefile",
    [
        "include other.mk\n",
        "-include other.mk\n",
        "%.o: %.c\n",
        "$(BIN): main.c\n",
        ".PHONY: $(X)\n",
    ],
)
def test_a_makefile_that_can_define_more_than_it_shows_leaves_an_undefined_target_unsettled(
    tmp_path: Path, makefile: str
) -> None:
    root = _make(tmp_path, f"known:\n{makefile}", "make known", "make unknown")
    report = check(root, ["codex"])
    [hit] = _references(report)
    assert (hit.decides, hit.verdict) == (False, "UNVERIFIED")
    assert "does not show" in hit.fact
    assert stale_references(root, ["codex"]) == []


@pytest.mark.parametrize(
    "span",
    ["make -C sub test", "make -f other.mk test", "make --directory=sub test", "make -Csub test"],
)
def test_a_make_command_naming_another_makefile_or_folder_reads_unsettled(
    tmp_path: Path, span: str
) -> None:
    root = _make(tmp_path, "known:\n", span)
    [hit] = _references(check(root, ["codex"]))
    assert "names a makefile or folder" in hit.fact
    assert stale_references(root, ["codex"]) == []


def test_a_makefile_that_cannot_be_read_leaves_its_targets_unsettled(tmp_path: Path) -> None:
    root = _target(tmp_path / "t", {"AGENTS.md": "Run `make test`.\n"})
    (root / "Makefile").mkdir()
    [hit] = _references(check(root, ["codex"]))
    assert "was not read" in hit.fact
    assert stale_references(root, ["codex"]) == []


@needs_symlinks
def test_a_makefile_that_links_out_of_the_target_is_not_read(tmp_path: Path) -> None:
    outside = tmp_path / "outside.mk"
    write(outside, "evil:\n")
    root = _target(tmp_path / "t", {"AGENTS.md": "Run `make evil`.\n"})
    (root / "Makefile").symlink_to(outside)
    [hit] = _references(check(root, ["codex"]))
    assert "was not read" in hit.fact


# --- package scripts -----------------------------------------------------------------


def test_the_nearest_package_json_upward_is_the_one_looked_in(tmp_path: Path) -> None:
    root = _target(
        tmp_path / "t",
        {
            "AGENTS.md": "Run `npm run build`, `pnpm run dev`, `yarn run test:unit`.\n",
            "package.json": json.dumps({"scripts": {"build": "x", "test:unit": "y"}}),
            "app/AGENTS.md": "Run `npm run dev`, `pnpm run build`, `yarn run dev`.\n",
            "app/package.json": json.dumps({"scripts": {"dev": "z"}}),
            "app/src/AGENTS.md": "Run `npm run dev`.\n",
        },
    )
    report = check(root, ["codex"])
    assert [(f.path, s) for f, s in zip(_references(report), _spans(report), strict=True)] == [
        ("AGENTS.md", "pnpm run dev"),
        ("app/AGENTS.md", "pnpm run build"),
    ]


def test_a_yarn_name_package_json_lacks_is_unsettled_since_yarn_runs_binaries_too(
    tmp_path: Path,
) -> None:
    root = _target(
        tmp_path / "t",
        {
            "AGENTS.md": "Run `yarn run eslint`, `npm run eslint`.\n",
            "package.json": json.dumps({"scripts": {"build": "x"}}),
        },
    )
    [yarn, npm] = _references(check(root, ["codex"]))
    assert "yarn run also runs a dependency's binary" in yarn.fact
    assert "does not define" in npm.fact
    assert [f.fact for f in stale_references(root, ["codex"])] == [npm.fact]


def test_a_script_command_that_names_no_script_is_no_reference(tmp_path: Path) -> None:
    spans = [
        "npm run",
        "npm run <script>",
        "npm run -w app build",
        "npm run $SCRIPT",
        "npm run build:*",
        "npm run build -- --watch",
        "npm run build && npm test",
        "npm install",
        "npm run-script gone",
        "yarn test",
    ]
    text = "".join(f"Run `{span}`.\n" for span in spans)
    root = _target(
        tmp_path / "t",
        {"AGENTS.md": text, "package.json": json.dumps({"scripts": {"build": "x"}})},
    )
    assert _flagged(root) == []


def test_a_script_with_no_package_json_at_or_above_is_a_reference(tmp_path: Path) -> None:
    root = _target(tmp_path / "t", {"AGENTS.md": "Run `npm run build`.\n"})
    report = check(root, ["codex"])
    assert _spans(report) == ["npm run build"]
    assert "no package.json is at or above this file" in _references(report)[0].fact


@pytest.mark.parametrize("content", ["{not json", "[1, 2]", "42"])
def test_a_package_json_that_is_no_json_object_leaves_its_scripts_unsettled(
    tmp_path: Path, content: str
) -> None:
    root = _target(tmp_path / "t", {"AGENTS.md": "Run `npm run build`.\n", "package.json": content})
    [hit] = _references(check(root, ["codex"]))
    assert "was not read as JSON" in hit.fact
    assert stale_references(root, ["codex"]) == []


def test_a_package_json_with_no_scripts_holds_no_script(tmp_path: Path) -> None:
    root = _target(
        tmp_path / "t",
        {"AGENTS.md": "Run `npm run build`.\n", "package.json": json.dumps({"name": "x"})},
    )
    assert _flagged(root) == ["npm run build"]


# --- whose text is read --------------------------------------------------------------


def test_the_text_of_a_managed_block_is_left_out_and_lines_are_kept(tmp_path: Path) -> None:
    block = f"{BEGIN}\nNamed in the block: `docs/gone.md`, `make nope`.\n{END}\n"
    text = f"# Mine\n\n{block}\nMine: `docs/gone2.md`.\n"
    root = _target(tmp_path / "t", {"AGENTS.md": text, "docs/ok.md": "ok\n"})
    [hit] = _references(check(root, ["codex"]))
    assert (hit.line, _spans(check(root, ["codex"]))) == (7, ["docs/gone2.md"])


def test_a_file_whose_managed_blocks_cannot_be_told_apart_is_not_read_for_references(
    tmp_path: Path,
) -> None:
    text = f"{BEGIN}\nopen block with `docs/gone.md`\n"
    root = _target(tmp_path / "t", {"AGENTS.md": text, "docs/ok.md": "ok\n"})
    [hit] = _references(check(root, ["codex"]))
    assert (hit.path, hit.line, hit.decides) == ("AGENTS.md", 0, False)
    assert "cannot be told apart" in hit.fact
    assert stale_references(root, ["codex"]) == []


def test_the_skill_copies_the_manifest_records_are_left_out_and_the_projects_own_are_read(
    tmp_path: Path,
) -> None:
    copy = ".claude/skills/shipped/SKILL.md"
    own = ".claude/skills/mine/SKILL.md"
    manifest = {
        "format_version": 2,
        "artifacts": [
            {"kind": "skill", "path": copy, "id": "shipped", "harnesses": ["claude-code"]},
            {"kind": "fragment", "path": ".claude/rules/frag.md", "id": "frag"},
        ],
    }
    root = _target(
        tmp_path / "t",
        {
            copy: "Read `docs/gone.md`.\n",
            own: "Read `docs/gone.md`.\n",
            ".claude/rules/frag.md": "Read `docs/gone.md`.\n",
            ".claude/rules/mine.md": "Read `docs/gone.md`.\n",
            ".outcomebound/manifest.json": json.dumps(manifest),
            "docs/ok.md": "ok\n",
        },
    )
    paths = [f.path for f in _references(check(root, ["claude-code"]))]
    assert paths == [".claude/rules/mine.md", own]


def test_the_agents_notes_are_left_out(tmp_path: Path) -> None:
    root = _target(
        tmp_path / "t",
        {
            "AGENTS.md": "ok\n",
            ".agents/handoffs/n.md": "Read `docs/gone.md`.\n",
            ".agents/shared-memory/m.md": "Run `make nope`.\n",
            "docs/ok.md": "ok\n",
        },
    )
    report = check(root, ["codex"])
    assert not any(
        f.path.startswith(".agents/") for f in report.findings if f.family == "references"
    )
    assert any(f.path.startswith(".agents/") for f in report.findings if f.family == "security")


def test_the_projects_own_local_fragment_is_read_from_the_root(tmp_path: Path) -> None:
    root = _target(
        tmp_path / "t",
        {
            "AGENTS.md": "ok\n",
            ".outcomebound/fragments/local.md": "Read `docs/gone.md` and `docs/ok.md`.\n",
            "docs/ok.md": "ok\n",
        },
    )
    [hit] = _references(check(root, ["codex"]))
    assert (hit.path, hit.line) == (".outcomebound/fragments/local.md", 1)


def test_only_markdown_in_scope_is_read(tmp_path: Path) -> None:
    root = _target(
        tmp_path / "t",
        {
            "AGENTS.md": "ok\n",
            ".cursor/rules/r.mdc": "Read `docs/gone.md`.\n",
            ".claude/settings.json": json.dumps({"note": "`docs/gone.md`"}),
            "docs/notes.md": "Read `docs/gone.md`.\n",
            "docs/ok.md": "ok\n",
        },
    )
    paths = [f.path for f in _references(check(root, ["cursor", "claude-code"]))]
    assert paths == [".cursor/rules/r.mdc"]


def test_a_file_that_is_not_utf8_is_not_read_for_references(tmp_path: Path) -> None:
    root = _target(tmp_path / "t", {"docs/ok.md": "ok\n"})
    (root / "AGENTS.md").write_bytes(b"Read `docs/gone.md` \xff\xfe.\n")
    report = check(root, ["codex"])
    assert [f for f in report.findings if f.family == "references"] == []


# --- stale_references, for adopt's install report -----------------------------------------


def test_stale_references_returns_the_findings_check_reports_for_what_the_target_lacks(
    tmp_path: Path,
) -> None:
    root = _target(
        tmp_path / "t",
        {
            "AGENTS.md": "Read `docs/gone.md`, run `make nope`, `make -C x y`, `npm run gone`.\n",
            "docs/ok.md": "ok\n",
            "Makefile": "test:\n",
            "package.json": json.dumps({"scripts": {}}),
        },
    )
    found = stale_references(root)
    report = check(root)
    assert [(f.path, f.line, f.check, f.decides) for f in found] == [
        ("AGENTS.md", 1, "stale-reference", False)
    ] * 3
    settled = [f for f in _references(report) if "names a makefile or folder" not in f.fact]
    assert found == settled
    assert _spans(replace(report, findings=tuple(found))) == [
        "docs/gone.md",
        "make nope",
        "npm run gone",
    ]


def test_stale_references_is_empty_for_a_clean_target_and_refuses_a_missing_one(
    tmp_path: Path,
) -> None:
    root = _target(tmp_path / "t", {"AGENTS.md": "Read `docs/ok.md`.\n", "docs/ok.md": "ok\n"})
    assert stale_references(root) == []
    with pytest.raises(AuditError, match="is not a directory"):
        stale_references(tmp_path / "missing")


# --- the limits the check keeps ----------------------------------------------------------


def test_a_quoted_span_is_escaped_so_no_file_steers_the_terminal(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    span = f"docs/g{chr(0xF6)}ne.md"
    root = _target(tmp_path / "t", {"AGENTS.md": f"Read `{span}`.\n", "docs/ok.md": "ok\n"})
    # The security gate fails on non-ASCII in a code span; the reference is quoted escaped
    # and adds nothing to the exit.
    assert main(["check", str(root), "--harness", "codex"]) == 1
    out = capsys.readouterr().out
    assert "stale-reference AGENTS.md:1 UNVERIFIED" in out and "docs/g\\u00f6ne.md" in out
    assert chr(0xF6) not in out


@pytest.mark.parametrize("control", ["\x00", "\x1b", "\x7f"])
def test_a_control_character_in_a_span_makes_it_no_path_and_stops_nothing(
    tmp_path: Path, control: str
) -> None:
    root = _repository(
        tmp_path / "t", {"AGENTS.md": f"Read `docs/a{control}b.md`.\n", "docs/ok.md": "ok\n"}
    )
    assert _flagged(root) == []


def test_nothing_the_target_holds_is_run_and_nothing_is_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    marker = tmp_path / "ran"
    files = {
        "AGENTS.md": "Run `make evil`, `make nope`, `npm run evil`, `npm run nope`.\n",
        "Makefile": f"$(shell touch {marker.as_posix()})\nevil:\n\ttouch {marker.as_posix()}\n",
        "package.json": json.dumps({"scripts": {"evil": f"touch {marker.as_posix()}"}}),
    }
    root = _repository(tmp_path / "t", files)
    before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file() and ".git" not in p.parts}
    started: list[str] = []
    real = subprocess.Popen

    def only_git(args: Any, *rest: Any, **options: Any) -> Any:
        argv = [str(a) for a in (args if isinstance(args, (list, tuple)) else [args])]
        started.append(Path(argv[0]).stem)
        if Path(argv[0]).stem != "git":
            raise AssertionError(f"started a process other than git: {argv}")
        return real(args, *rest, **options)

    monkeypatch.setattr(subprocess, "Popen", only_git)
    assert _flagged(root) == ["make nope", "npm run nope"]
    assert set(started) == {"git"}
    assert not marker.exists()
    assert before == {p: p.read_bytes() for p in before}
    assert {p for p in root.rglob("*") if p.is_file() and ".git" not in p.parts} == set(before)


def test_a_label_and_another_projects_path_are_no_reference(tmp_path: Path) -> None:
    """Breaks if a slash-separated label, or a path another project owns, is read as a stale
    reference of this one: both were false hits on real projects' instruction files."""

    text = (
        "| `proof/test` | tests and proof helpers |\n"
        "Acme's `docs/specs/product/` decides the contract.\n"
        "The types are owned in the Acme repository at `docs/specs/instance/contracts.md`.\n"
        "This repository's `docs/gone.md` was removed.\n"
        "Read `docs/missing/` first.\n"
    )
    root = _target(tmp_path / "t", {"AGENTS.md": text, "proof/keep.txt": "x\n", "docs/a.md": "a\n"})
    assert _flagged(root) == ["docs/gone.md", "docs/missing/"]
