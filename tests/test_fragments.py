"""A fragment instantiates the kernel with project facts; it never adds a rule.

Everything that exercises the composer builds its own source root from inline
fixtures, so composer behavior is pinned independently of the shipped catalog.
Only the catalog acceptance tests read the `fragments/` tree itself.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from outcomebound_tools.fragments import (
    SKILLS,
    FragmentError,
    byte_cap,
    compose_body,
    detect,
    inline,
    load_all,
    parse_fragment,
    select,
)
from outcomebound_tools.identity import parse_managed_blocks
from outcomebound_tools.mechanisms import MECHANISMS
from tests.portable import engine, needs_symlinks, write

ROOT = Path(__file__).resolve().parent.parent

GOOD = """\
---
id: sample
family: stack
applies: sample projects
detect: ["sample.toml"]
version: 1
---
**Context** — the runtime is the evidence.
**Bounds** — publishing is an irreversible edge.
**Mechanisms** — `spec` when the wire format changes; `broad-suite` on a shared type.
**Completion bar** — the focused suite (test).
**Distinguish** — built ≠ published.
"""

shipped_catalog = pytest.mark.skipif(
    not (ROOT / "fragments").is_dir(),
    reason="no shipped fragments/ tree in this checkout",
)


def _fragment(fragment_id, family="stack", detect_patterns=(), padding=""):
    return (
        "---\n"
        f"id: {fragment_id}\n"
        f"family: {family}\n"
        f"applies: {fragment_id} projects\n"
        f"detect: {json.dumps(list(detect_patterns))}\n"
        "version: 1\n"
        "---\n"
        f"**Context** — the runtime is the evidence.{padding}\n"
        "**Bounds** — publishing is an irreversible edge.\n"
        "**Mechanisms** — `spec` when the wire format changes.\n"
        "**Completion bar** — the focused suite (test).\n"
        "**Distinguish** — built ≠ published.\n"
    )


FIXTURE_FRAGMENTS = {
    "stack/python.md": _fragment("python", detect_patterns=["pyproject.toml"]),
    "stack/node-typescript.md": _fragment("node-typescript", detect_patterns=["package.json"]),
    "stack/ci-release.md": _fragment("ci-release", detect_patterns=[".github/workflows/*.yml"]),
    "stack/yaml-anywhere.md": _fragment("yaml-anywhere", detect_patterns=["*.yml"]),
    "stack/oversized.md": _fragment("oversized", padding=" " + "detail. " * 5000),
    "setup/solo.md": _fragment("solo", family="setup"),
    "setup/team.md": _fragment("team", family="setup"),
}


@pytest.fixture(scope="session")
def source(tmp_path_factory):
    """A source root shaped like an engine checkout, with fixture fragments."""

    root = tmp_path_factory.mktemp("source")
    for relative, text in FIXTURE_FRAGMENTS.items():
        path = root / "fragments" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        write(path, text)
    copied = ("templates/managed-block.agents.md.tmpl", *(f"skills/{s}/SKILL.md" for s in SKILLS))
    for relative in copied:
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, destination)
    return root


def test_a_well_formed_fragment_parses():
    fragment = parse_fragment(GOOD, "sample.md")
    assert fragment.id == "sample"
    assert fragment.family == "stack"
    assert fragment.detect == ("sample.toml",)
    assert fragment.version == 1


def test_unknown_frontmatter_key_is_rejected():
    with pytest.raises(FragmentError, match="unknown frontmatter"):
        parse_fragment(GOOD.replace("version: 1", "version: 1\nowner: nobody"), "x.md")


def test_a_repeated_frontmatter_key_is_rejected():
    with pytest.raises(FragmentError, match="duplicate frontmatter"):
        parse_fragment(GOOD.replace("version: 1", "id: other\nversion: 1"), "x.md")


def test_a_missing_frontmatter_block_is_rejected():
    with pytest.raises(FragmentError, match="frontmatter"):
        parse_fragment(GOOD.split("---\n", 2)[2], "x.md")


def test_a_missing_frontmatter_field_is_rejected():
    with pytest.raises(FragmentError, match="missing"):
        parse_fragment(GOOD.replace("applies: sample projects\n", ""), "x.md")


def test_a_fragment_saved_with_crlf_or_a_byte_order_mark_parses_as_one_saved_with_lf():
    """A `local.md` edited on Windows, or checked out with `core.autocrlf`, holds CRLF, and a
    Windows editor may add a mark. Its fields, body and digest are those of the LF text, so the
    pointers block that inlines it is the same one."""

    plain = parse_fragment(GOOD, "x.md")
    for text in (
        GOOD.replace("\n", "\r\n"),
        "\ufeff" + GOOD,
        "\ufeff" + GOOD.replace("\n", "\r\n"),
    ):
        found = parse_fragment(text, "x.md")
        assert found == plain
        assert "\r" not in found.body


def test_an_unknown_family_is_rejected():
    with pytest.raises(FragmentError, match="family"):
        parse_fragment(GOOD.replace("family: stack", "family: doctrine"), "x.md")


@pytest.mark.parametrize(
    "mutation",
    [
        ("**Distinguish** — built ≠ published.\n", ""),
        ("**Bounds** — publishing is an irreversible edge.\n", ""),
        ("**Context** — the runtime is the evidence.\n", "**Notes** — extra slot.\n"),
        (
            "**Distinguish** — built ≠ published.\n",
            "**Distinguish** — built ≠ published.\n**Notes** — a sixth slot.\n",
        ),
    ],
    ids=["missing-last", "missing-middle", "renamed-slot", "sixth-slot"],
)
def test_missing_extra_or_misordered_slots_are_rejected(mutation):
    broken = GOOD.replace(*mutation)
    with pytest.raises(FragmentError, match="slots"):
        parse_fragment(broken, "x.md")


def test_slots_out_of_order_are_rejected():
    lines = GOOD.splitlines(keepends=True)
    swapped = "".join(lines[:7] + [lines[8], lines[7]] + lines[9:])
    with pytest.raises(FragmentError, match="slots"):
        parse_fragment(swapped, "x.md")


def test_NEGATIVE_CONTROL_a_fragment_cannot_invent_a_mechanism():
    """The whole invariant: a fragment instantiates the kernel, it never adds a rule."""
    broken = GOOD.replace("`spec` when", "`sign-off-matrix` when")
    with pytest.raises(FragmentError, match="sign-off-matrix"):
        parse_fragment(broken, "x.md")


def test_backticks_outside_the_mechanisms_slot_are_free():
    fine = GOOD.replace("the runtime is the evidence", "`pyproject.toml` is a claim")
    assert parse_fragment(fine, "x.md").id == "sample"


def test_a_detect_pattern_may_not_escape_the_target_root():
    for pattern in ("../*.toml", "/etc/hosts", "a/../../b"):
        with pytest.raises(FragmentError, match="detect"):
            parse_fragment(GOOD.replace('["sample.toml"]', json.dumps([pattern])), "x.md")


def test_detect_must_be_a_json_list_of_strings():
    with pytest.raises(FragmentError, match="detect"):
        parse_fragment(GOOD.replace('["sample.toml"]', "sample.toml"), "x.md")
    with pytest.raises(FragmentError, match="detect"):
        parse_fragment(GOOD.replace('["sample.toml"]', "[1]"), "x.md")


@shipped_catalog
def test_every_shipped_fragment_parses_and_names_only_registry_mechanisms():
    catalog = load_all(ROOT)
    assert set(catalog) >= {
        "python",
        "node-typescript",
        "ci-release",
        "multi-agent",
        "db-migrations",
        "solo",
        "team",
        "tickets",
        "workspace",
        "research",
        "commands",
    }
    for fragment in catalog.values():
        assert fragment.family in ("stack", "setup")
        for name in fragment.mechanisms:
            assert name in MECHANISMS
        # Each is reached through a pointer, so each says when its guidance is needed.
        assert fragment.condition, f"{fragment.id} declares no condition"


def test_a_catalog_loads_from_a_source_root(source):
    catalog = load_all(source)
    assert set(catalog) == {Path(name).stem for name in FIXTURE_FRAGMENTS}
    assert catalog["solo"].family == "setup"
    assert catalog["python"].path is not None


def test_a_fragment_in_the_wrong_family_directory_is_rejected(source, tmp_path):
    root = tmp_path / "broken"
    shutil.copytree(source / "fragments", root / "fragments")
    write(root / "fragments/setup/misfiled.md", _fragment("misfiled"))
    with pytest.raises(FragmentError, match="does not match its directory"):
        load_all(root)


def test_a_local_fragment_overrides_a_shipped_id(source, tmp_path):
    local = tmp_path / "local.md"
    write(local, _fragment("python", detect_patterns=["local.toml"]))
    catalog = load_all(source, local=local)
    assert catalog["python"].detect == ("local.toml",)


def test_condition_and_edges_are_optional_and_parsed():
    """A fragment may leave both out; `edges` is a JSON list of acts, `condition` one line."""

    bare = parse_fragment(GOOD, "x.md")
    assert (bare.condition, bare.edges) == ("", ())
    extra = 'condition: before a release\nedges: ["pushing a tag", "publishing"]\nversion: 1'
    full = parse_fragment(GOOD.replace("version: 1", extra), "x.md")
    assert (full.condition, full.edges) == ("before a release", ("pushing a tag", "publishing"))


@pytest.mark.parametrize("edges", ["pushing a tag", "[1]", '[""]', "{}"])
def test_edges_must_be_a_json_list_of_non_empty_strings(edges):
    with pytest.raises(FragmentError, match="edges"):
        parse_fragment(GOOD.replace("version: 1", f"edges: {edges}\nversion: 1"), "x.md")


def test_every_install_carries_the_seven_working_skills_and_no_fragment_adds_one():
    """`SKILLS` is the whole set, each in the engine; a `skills:` key is refused as unknown."""

    assert SKILLS == (
        "using-outcomebound",
        "decision-brief",
        "gather-requirements",
        "tests-worth-keeping",
        "explain-spec",
        "slice-tickets",
        "hand-off-tickets",
    )
    for name in SKILLS:
        assert (ROOT / "skills" / name / "SKILL.md").is_file(), name
    assert not hasattr(load_all(ROOT)["tickets"], "skills")
    with pytest.raises(FragmentError, match="skills"):
        parse_fragment(GOOD.replace("version: 1", 'skills: ["a-b"]\nversion: 1'), "x.md")


def test_the_same_selection_composes_the_same_bytes(source):
    """Determinism across independent loads: same inputs, same body, same hash."""

    first = load_all(source)
    second = load_all(source)
    one = compose_body([first["python"], first["solo"]])
    two = compose_body([second["python"], second["solo"]])
    assert one == two


def test_fragment_order_is_the_order_given(source):
    catalog = load_all(source)
    forward = compose_body([catalog["python"], catalog["solo"]])
    reverse = compose_body([catalog["solo"], catalog["python"]])
    assert forward != reverse
    assert forward.index("python projects") < forward.index("solo projects")
    assert reverse.index("solo projects") < reverse.index("python projects")


def test_detect_proposes_and_never_writes(tmp_path, source):
    write(tmp_path / "pyproject.toml", "[project]\n")
    (tmp_path / "node_modules").mkdir()
    write(tmp_path / "node_modules" / "package.json", "{}")
    before = sorted(p.name for p in tmp_path.iterdir())
    proposed = detect(tmp_path, load_all(source))
    assert "python" in proposed
    assert "node-typescript" not in proposed, "node_modules must not drive detection"
    assert sorted(p.name for p in tmp_path.iterdir()) == before


def test_the_pattern_dot_matches_every_target_without_a_file_to_find(tmp_path, monkeypatch):
    """A glob walk finds nothing here, so only the pattern itself can make the match."""

    always = parse_fragment(GOOD.replace('["sample.toml"]', '["."]'), "x.md")
    other = parse_fragment(GOOD.replace("id: sample", "id: other"), "y.md")
    monkeypatch.setattr(Path, "rglob", lambda self, pattern: iter(()))
    assert detect(tmp_path, {"sample": always, "other": other}) == ["sample"]


def test_detect_skips_hidden_directories_a_pattern_does_not_name(tmp_path, source):
    workflows = tmp_path / ".github" / "workflows"
    workflows.mkdir(parents=True)
    write(workflows / "ci.yml", "on: push\n")
    proposed = detect(tmp_path, load_all(source))
    assert "ci-release" in proposed, "a pattern that names .github may match inside it"
    assert "yaml-anywhere" not in proposed, "a bare glob must not descend into hidden dirs"


@pytest.mark.parametrize(
    ("files", "proposed"),
    [
        ((".github/workflows/ci.yml",), False),
        (("VERSION",), True),
        ((".github/workflows/release.yml",), True),
        ((".github/workflows/publish-package.yaml",), True),
    ],
    ids=["ci-only", "version-file", "release-workflow", "publish-workflow"],
)
def test_ci_release_is_proposed_only_where_the_repository_shows_it_releases(
    tmp_path, files, proposed
):
    """A CI workflow alone is no sign of releasing; the shipped fragment's edges stay out."""

    for name in files:
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        write(tmp_path / name, "x\n")
    assert ("ci-release" in detect(tmp_path, load_all(ROOT))) is proposed


@needs_symlinks
@pytest.mark.parametrize("link", ["directory", "file"], ids=["dir-symlink", "file-symlink"])
def test_detect_ignores_evidence_that_resolves_outside_the_target(tmp_path, source, link):
    """Detection reports what is in the target; a link out of it is another tree."""

    outside = tmp_path / "outside"
    outside.mkdir()
    write(outside / "pyproject.toml", "[project]\n")
    target = tmp_path / "target"
    target.mkdir()
    if link == "directory":
        (target / "vendor").symlink_to(outside, target_is_directory=True)
    else:
        (target / "pyproject.toml").symlink_to(outside / "pyproject.toml")
    assert "python" not in detect(target, load_all(source))


def test_byte_cap_ignores_a_non_integer_cap(monkeypatch):
    """`isinstance(True, int)` is True: a boolean must not become a 1-byte cap."""

    from outcomebound_tools import adapters

    row = {
        "skill_install_path": ".x/skills/",
        "pointer_mechanism": "AGENTS.md",
        "command_format": "slash",
        "native_skills": True,
        "mcp": False,
        "verified": False,
    }
    monkeypatch.setitem(adapters._table(), "bool-cap", {**row, "doc_byte_cap": True})
    monkeypatch.setitem(adapters._table(), "text-cap", {**row, "doc_byte_cap": "32768"})
    assert byte_cap("bool-cap") is None
    assert byte_cap("text-cap") is None


def test_byte_cap_reads_the_harness_table():
    table = json.loads((ROOT / "adapters/harnesses.json").read_text(encoding="utf-8"))
    assert byte_cap("codex") == table["codex"]["doc_byte_cap"]
    assert byte_cap("claude-code") is None
    assert byte_cap("some-future-agent") is None
    assert byte_cap(None) is None


def test_byte_cap_refuses_a_row_it_cannot_read_as_a_fragment_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A row the table carries but cannot describe is not an unknown harness.

    `adapters.row` refuses an empty row; the fragments CLI catches only
    `FragmentError`, so that refusal reaches it translated, never as a traceback.
    """

    from outcomebound_tools import adapters

    monkeypatch.setitem(adapters._table(), "empty-row", {})
    with pytest.raises(FragmentError, match="unknown harness 'empty-row'"):
        byte_cap("empty-row")


def _cli(*args, cwd=ROOT):
    """The verb as a person runs it: `engine()` starts it through `outcomebound`, which makes
    standard output UTF-8 where the console's code page could not hold the text."""

    return subprocess.run(
        engine("fragments", *args), capture_output=True, text=True, encoding="utf-8", cwd=cwd
    )


def _oversized_local(tmp_path):
    local = tmp_path / "local.md"
    write(local, _fragment("local", family="setup", padding=" " + "detail. " * 5000))
    return local


def test_compose_cli_renders_the_facts_and_pointers_blocks_adopt_writes(source, tmp_path):
    result = _cli(
        "compose", "--source", str(source), "--target", str(tmp_path), "--fragments", "python"
    )
    assert result.returncode == 0, result.stderr
    blocks = parse_managed_blocks(result.stdout)
    assert list(blocks) == ["project-facts", "guidance-pointers"]
    assert blocks["guidance-pointers"].body.splitlines()[0] == (
        "- for python projects: read .outcomebound/fragments/python.md"
    )
    assert "the runtime is the evidence" not in result.stdout
    assert "fragments=1 words=" in result.stderr and "bytes=" in result.stderr


def test_compose_cli_warns_when_a_harness_byte_cap_is_exceeded(source, tmp_path):
    arguments = ("compose", "--source", str(source), "--target", str(tmp_path))
    local = str(_oversized_local(tmp_path))
    result = _cli(*arguments, "--harness", "codex", "--local", local, "--fragments", "local")
    assert result.returncode == 0, result.stderr
    cap = json.loads((ROOT / "adapters/harnesses.json").read_text(encoding="utf-8"))["codex"][
        "doc_byte_cap"
    ]
    composed = len(result.stdout.encode("utf-8"))
    assert composed > cap
    assert "doc_byte_cap" in result.stderr


def test_compose_cli_is_silent_below_the_cap_and_for_a_harness_without_one(source, tmp_path):
    arguments = ("compose", "--source", str(source), "--target", str(tmp_path))
    under = _cli(*arguments, "--harness", "codex", "--fragments", "python")
    assert under.returncode == 0 and "doc_byte_cap" not in under.stderr
    local = str(_oversized_local(tmp_path))
    uncapped = _cli(
        *arguments, "--harness", "claude-code", "--local", local, "--fragments", "local"
    )
    assert uncapped.returncode == 0 and "doc_byte_cap" not in uncapped.stderr
    assert len(uncapped.stdout.encode("utf-8")) > 32768


def _sentinels_outside_fences(text):
    in_fence, found = False, []
    for line in text.splitlines():
        if line.lstrip().startswith(("```", "~~~")):
            in_fence = not in_fence
        elif not in_fence and "<!-- outcomebound:" in line:
            found.append(line)
    return found


def test_inline_mode_emits_kernel_skills_and_fragments_with_no_sentinels(source):
    """Each skill an install carries follows the kernel, so the kernel's pointer to the
    decision-brief skill resolves inside the blob."""

    result = _cli("compose", "--source", str(source), "--fragments", "python", "--inline")
    assert result.returncode == 0, result.stderr
    assert not _sentinels_outside_fences(result.stdout)
    assert "**OutcomeBound**" in result.stdout and "four inputs" in result.stdout
    assert "`decision-brief` skill" in result.stdout
    for heading in ("# Using OutcomeBound", "# Decision brief"):
        assert heading in result.stdout, heading
    for name in SKILLS:
        assert f"name: {name}" not in result.stdout, "skill frontmatter must be stripped"
    assert "**Distinguish**" in result.stdout


def test_inline_mode_keeps_the_sentinels_of_the_slice_tickets_example(source):
    """The filled ticket block is a format the tickets check reads, so an inline reader
    needs its begin and end lines."""

    result = _cli("compose", "--source", str(source), "--fragments", "python", "--inline")
    assert result.returncode == 0, result.stderr
    assert "<!-- outcomebound:begin id=ticket v=1 -->" in result.stdout
    assert "<!-- outcomebound:end id=ticket -->" in result.stdout


def test_unknown_fragment_id_fails_closed(source):
    result = _cli("compose", "--source", str(source), "--fragments", "python,not-a-fragment")
    assert result.returncode == 2
    assert "not-a-fragment" in result.stderr
    assert result.stdout == ""


def test_selecting_nothing_fails_closed(source):
    result = _cli("compose", "--source", str(source), "--fragments", "")
    assert result.returncode == 2
    assert "no fragments" in result.stderr
    assert result.stdout == ""


def test_detect_cli_proposes_without_writing(tmp_path, source):
    write(tmp_path / "pyproject.toml", "[project]\n")
    result = _cli("detect", "--target", str(tmp_path), "--source", str(source))
    assert result.returncode == 0, result.stderr
    assert result.stdout.split() == ["python"]
    assert "nothing was written" in result.stderr
    assert sorted(p.name for p in tmp_path.iterdir()) == ["pyproject.toml"]


def test_cli_help_works():
    result = _cli("--help")
    assert result.returncode == 0
    assert "compose" in result.stdout and "detect" in result.stdout


def test_a_malformed_fragment_in_the_source_root_is_a_typed_cli_failure(tmp_path):
    root = tmp_path / "broken"
    (root / "fragments/stack").mkdir(parents=True)
    write(root / "fragments/stack/bad.md", "no frontmatter here\n")
    result = _cli("compose", "--source", str(root), "--fragments", "bad")
    assert result.returncode == 2
    assert "Traceback" not in result.stderr
    assert "frontmatter" in result.stderr


def test_inline_is_a_library_call_too(source):
    catalog = load_all(source)
    text = inline(source, [catalog["python"]])
    assert not _sentinels_outside_fences(text)
    assert text.endswith("\n")


def test_a_duplicate_fragment_id_is_rejected_rather_than_silently_deduped(source):
    """A repeated id is a typo, and a silent dedupe answers a question nobody asked."""

    with pytest.raises(FragmentError, match="duplicate fragment id.*python"):
        select(load_all(source), ["python", "solo", "python"])


def _local(edges: str = "[]", mechanisms: str = "`review` when a change is risky.") -> str:
    return (
        "---\nid: local\nfamily: setup\napplies: this repository\n"
        f"edges: {edges}\ndetect: []\nversion: 1\n---\n"
        "**Context** — c.\n**Bounds** — b.\n"
        f"**Mechanisms** — {mechanisms}\n"
        "**Completion bar** — d.\n**Distinguish** — e.\n"
    )


@pytest.mark.parametrize(
    "edge", ["pushing a tag; deleting a branch", "pushing a tag\\ndeleting a branch"]
)
def test_an_edge_the_facts_line_would_split_is_refused(edge: str) -> None:
    """The facts line joins edges with '; ' on one line, so an edge holding either reads as
    two edges."""

    with pytest.raises(FragmentError, match="edge"):
        parse_fragment(_local(f'["{edge}"]'))
    assert parse_fragment(_local('["pushing a tag, then a release"]')).edges == (
        "pushing a tag, then a release",
    )


def test_a_backticked_command_on_the_mechanisms_line_is_refused_with_the_rule() -> None:
    with pytest.raises(FragmentError, match="only mechanism ids take backticks"):
        parse_fragment(_local(mechanisms="`review` before `make deploy`."))
