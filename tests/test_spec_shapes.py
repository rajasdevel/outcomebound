"""A selected spec can have any useful shape; checks detect scaffold residue only."""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _check(path):
    return subprocess.run(
        [sys.executable, "-m", "outcomebound_tools.artifactcheck", "--spec", str(path)],
        capture_output=True,
        text=True,
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
    )


def test_freeform_material_design_passes_without_prescribed_headings(tmp_path):
    design = tmp_path / "design.md"
    design.write_text(
        "# Import boundary\n\nKeep the existing parser and repair delimiter detection at "
        "the record boundary. Complete semicolon records must remain intact; run the focused "
        "record regression.\n",
        encoding="utf-8",
    )
    assert _check(design).returncode == 0


def test_generic_type_is_not_mistaken_for_template_residue(tmp_path):
    design = tmp_path / "design.md"
    design.write_text(
        "# Typed boundary\n\nKeep the existing `Result<T>` contract.\n", encoding="utf-8"
    )
    assert _check(design).returncode == 0


def test_known_placeholder_or_heading_only_scaffold_fails(tmp_path):
    design = tmp_path / "design.md"
    design.write_text("# <slug> — design\n\n## Outcome\n\n<!-- observable result -->\n")
    result = _check(design)
    assert result.returncode == 1
    assert "placeholder" in result.stderr and "no authored content" in result.stderr


def test_plan_is_not_required_to_use_checkbox_or_step_shape(tmp_path):
    plan = tmp_path / "plan.md"
    plan.write_text(
        "# Migration sequence\n\nFirst preserve the legacy state. Then emit the current "
        "manifest and verify idempotence.\n",
        encoding="utf-8",
    )
    assert _check(plan).returncode == 0


def test_missing_target_returns_a_clean_failure(tmp_path):
    result = _check(tmp_path / "missing-design.md")
    assert result.returncode == 1
    assert "unreadable spec" in result.stderr
    assert "Traceback" not in result.stderr


def test_new_spec_defaults_to_design_only_and_scaffold_is_incomplete(tmp_path):
    (tmp_path / "docs/specs").mkdir(parents=True)
    result = subprocess.run(
        ["bash", str(ROOT / "scripts/new-spec.sh"), "shape-probe"],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env={**os.environ, "OUTCOMEBOUND_HOME": str(ROOT)},
    )
    assert result.returncode == 0, result.stderr
    design = tmp_path / "docs/specs/shape-probe/design.md"
    assert design.is_file()
    assert not design.with_name("plan.md").exists()
    assert _check(design).returncode == 1


def test_new_spec_adds_plan_only_when_selected(tmp_path):
    (tmp_path / "docs/specs").mkdir(parents=True)
    result = subprocess.run(
        ["bash", str(ROOT / "scripts/new-spec.sh"), "planned", "--with-plan"],
        capture_output=True,
        text=True,
        cwd=tmp_path,
    )
    assert result.returncode == 0, result.stderr
    spec = tmp_path / "docs/specs/planned"
    assert (spec / "design.md").is_file() and (spec / "plan.md").is_file()


def _check_dir(path):
    return subprocess.run(
        [sys.executable, "-m", "outcomebound_tools.artifactcheck", "--spec-dir", str(path)],
        capture_output=True,
        text=True,
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": str(ROOT)},
    )


def test_nested_spec_directories_are_checked(tmp_path):
    nested = tmp_path / "area" / "nested-spec"
    nested.mkdir(parents=True)
    (nested / "design.md").write_text("# <slug> — design\n", encoding="utf-8")
    result = _check_dir(tmp_path)
    assert result.returncode == 1
    assert "nested-spec/design.md" in result.stderr


def test_spec_directory_without_design_or_plan_is_reported(tmp_path):
    (tmp_path / "empty-spec").mkdir()
    result = _check_dir(tmp_path)
    assert result.returncode == 1
    assert "no design.md or plan.md" in result.stderr


def test_specs_tree_with_no_spec_at_all_is_reported(tmp_path):
    result = _check_dir(tmp_path)
    assert result.returncode == 1
    assert "contains no spec" in result.stderr


def test_prose_tbd_and_todo_are_not_template_residue(tmp_path):
    design = tmp_path / "design.md"
    design.write_text(
        "# Import boundary\n\nThe upstream owner marks unsupported dialects TBD in their "
        "tracker; we treat a TODO comment in vendored code as evidence of an unfinished "
        "upstream migration and keep the existing parser.\n",
        encoding="utf-8",
    )
    assert _check(design).returncode == 0, _check(design).stderr


def test_unrendered_mustache_slot_is_still_template_residue(tmp_path):
    design = tmp_path / "design.md"
    design.write_text("# Boundary\n\nUse the {{repo_name}} parser.\n", encoding="utf-8")
    result = _check(design)
    assert result.returncode == 1
    assert "placeholder" in result.stderr


def test_node_modules_and_hidden_dirs_are_excluded_from_the_walk(tmp_path):
    clean = tmp_path / "clean"
    (clean / "real-spec").mkdir(parents=True)
    (clean / "real-spec" / "design.md").write_text(
        "# Import boundary\n\nKeep the existing parser and repair delimiter detection.\n",
        encoding="utf-8",
    )
    (clean / "node_modules" / "some-pkg" / "empty").mkdir(parents=True)
    (clean / ".hidden" / "sub" / "empty").mkdir(parents=True)
    clean_result = _check_dir(clean)
    assert clean_result.returncode == 0, clean_result.stderr
    assert clean_result.stderr == ""

    with_visible_empty = tmp_path / "with-visible-empty"
    (with_visible_empty / "real-spec").mkdir(parents=True)
    (with_visible_empty / "real-spec" / "design.md").write_text(
        "# Import boundary\n\nKeep the existing parser and repair delimiter detection.\n",
        encoding="utf-8",
    )
    (with_visible_empty / "node_modules" / "some-pkg" / "empty").mkdir(parents=True)
    (with_visible_empty / ".hidden" / "sub" / "empty").mkdir(parents=True)
    (with_visible_empty / "visible-empty").mkdir()
    visible_result = _check_dir(with_visible_empty)
    assert visible_result.returncode == 1
    assert "/node_modules/" not in visible_result.stderr
    assert "/.hidden/" not in visible_result.stderr
    assert "visible-empty" in visible_result.stderr


def test_new_spec_accepts_a_dotted_slug_and_an_explicit_target(tmp_path):
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    result = subprocess.run(
        [
            "bash",
            str(ROOT / "scripts/new-spec.sh"),
            "payments-api-v2.1",
            "--with-plan",
            str(elsewhere),
        ],
        capture_output=True,
        text=True,
        cwd=tmp_path,
    )
    assert result.returncode == 0, result.stderr
    spec = elsewhere / "docs/specs/payments-api-v2.1"
    assert (spec / "design.md").is_file() and (spec / "plan.md").is_file()
    assert not (tmp_path / "docs").exists()


def test_new_spec_still_rejects_an_unknown_option(tmp_path):
    result = subprocess.run(
        ["bash", str(ROOT / "scripts/new-spec.sh"), "probe", "--with-notes"],
        capture_output=True,
        text=True,
        cwd=tmp_path,
    )
    assert result.returncode == 1
    assert "unknown option" in result.stderr
    assert not (tmp_path / "docs").exists()


def test_new_spec_rejects_more_than_one_target(tmp_path):
    result = subprocess.run(
        ["bash", str(ROOT / "scripts/new-spec.sh"), "probe", str(tmp_path), str(tmp_path / "b")],
        capture_output=True,
        text=True,
        cwd=tmp_path,
    )
    assert result.returncode == 1
    assert "one target" in result.stderr
    assert not (tmp_path / "docs").exists()
