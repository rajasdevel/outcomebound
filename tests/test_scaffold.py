"""`outcomebound scaffold`: the plan, `--accept`, `--check`, moves and the template manifest.

The seam is the command line, run in this process, on Git repositories under `tmp_path`: the file
set each lifecycle writes into an empty repository, what the plan prints and writes (nothing),
what `--accept` writes and leaves, what `--check` counts, and the report each mode prints with
`--json`. The tables these tests hold are the scaffold design's (docs/specs/scaffold/design.md).
"""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
from pathlib import Path

import pytest

from outcomebound_tools import adopt, fileplan, fragments, instruction_audit, paths, scaffold
from outcomebound_tools.schemacheck import validate
from tests.adopt_helpers import GIT, Capture, repo
from tests.portable import needs_symlinks
from tests.portable import write as write_file

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "templates" / "scaffold"
REPORT_SCHEMA = json.loads((ROOT / "schemas/scaffold-report.schema.json").read_text("utf-8"))
MANIFEST_SCHEMA = json.loads((ROOT / "schemas/scaffold-manifest.schema.json").read_text("utf-8"))

LOCAL = ".outcomebound/fragments/local.md"
CI = ".github/workflows/ci.yml"
BOT = ".github/dependabot.yml"
ROUTE = "CONTRIBUTING.md"
SECURITY = "SECURITY.md"
CHANGELOG = "CHANGELOG.md"
CODEOWNERS = ".github/CODEOWNERS"
PR_TEMPLATE = ".github/pull_request_template.md"
PRESETS = ("prototype", "solo", "team", "organization")
OVERLAYS = ("client", "eu-market", "safety-critical", "audit", "unattended-agents", "ai-product")
ACTS = ("deploy", "publish", "tag", "stored-data")
VISIBILITIES = ("public", "private", "private-free")
REFUSED_ON_PROTOTYPE = ("client", "eu-market", "audit")
# A line each overlay adds to the local fragment, and no preset writes.
OVERLAY_LINE = {
    "client": "Gates — acceptance: owner UNVERIFIED (<<owner:",
    "eu-market": "Regulation (EU) 2024/2847",
    "safety-critical": "This scaffold is not the lifecycle that",
    "audit": "the compensating control is",
    "unattended-agents": "Each agent works on its own branch or worktree",
    "ai-product": "The evaluation tasks and their grader run as part of Done",
}
MARKER = re.compile(r"<<(fill|owner): ([^<>\r\n]+)>>")


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    write_file(path, text)


def run(capsys: Capture, *argv: object, source: Path = ROOT) -> tuple[int, str, str]:
    code = scaffold.main([str(item) for item in argv], source=source)
    out, err = capsys.readouterr()
    return code, out, err


def target(tmp_path: Path, name: str = "t", files: dict[str, str] | None = None) -> Path:
    return repo(tmp_path / name, files)


def tree(root: Path) -> dict[str, bytes]:
    """Every file and link under `root`, `.git` included, by relative path."""

    found: dict[str, bytes] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            found[relative] = b"-> " + os.readlink(path).encode()
        elif path.is_file():
            found[relative] = path.read_bytes()
        elif path.is_dir():
            found[relative + "/"] = b""
    return found


def files_of(root: Path) -> set[str]:
    return {name for name in tree(root) if not name.startswith(".git/") and not name.endswith("/")}


def facts(preset: str, visibility: str | None) -> list[str]:
    return [] if visibility is None else ["--visibility", visibility]


def accept(capsys: Capture, root: Path, lifecycle: str, *more: object) -> str:
    code, out, err = run(capsys, root, "--lifecycle", lifecycle, *more, "--accept")
    assert code == 0, out + err
    return out


def expected_set(preset: str, visibility: str | None, acts: tuple[str, ...] = ()) -> set[str]:
    """The design's table "So a fresh empty repository gets these files", with each act's file."""

    found = {LOCAL}
    if preset == "prototype":
        return found
    found |= {CI, BOT}
    if preset in ("team", "organization") or visibility == "public":
        found.add(SECURITY)
    if preset in ("team", "organization"):
        found.add(ROUTE)
    if {"publish", "tag"} & set(acts):
        found.add(CHANGELOG)
    return found


def adopt_words(out: str) -> list[str]:
    """The `adopt:` line of a plan, as the words after `outcomebound adopt`."""

    line = next(line for line in out.splitlines() if line.startswith("adopt:"))
    words = shlex.split(line[len("adopt:") :])
    assert words[:2] == ["outcomebound", "adopt"]
    return words[2:]


def fill_every_marker(root: Path) -> None:
    """Each value filled as the agent fills it, and each gate owner named as the person names it."""

    for name in files_of(root):
        path = root / name
        text = path.read_text(encoding="utf-8")
        text = re.sub(r"UNVERIFIED \(<<owner: [^<>\n]+>>\)", "Pat Example", text)
        text = MARKER.sub("a value the person gave", text)
        write(path, text)


def json_report(capsys: Capture, *argv: object) -> tuple[int, dict]:
    code, out, _ = run(capsys, *argv, "--json")
    document = json.loads(out)
    assert validate(document, REPORT_SCHEMA) == [], out
    return code, document


# 1. The file set of each preset.

CASES = [("prototype", None, ())] + [
    (preset, visibility, acts)
    for preset in PRESETS[1:]
    for visibility in VISIBILITIES
    for acts in ((), ("deploy",), ("publish",), ("tag",), ("stored-data",))
]


@pytest.mark.parametrize(("preset", "visibility", "acts"), CASES)
def test_each_preset_writes_exactly_its_file_set_into_an_empty_repository(
    tmp_path: Path, capsys: Capture, preset: str, visibility: str | None, acts: tuple[str, ...]
) -> None:
    root = target(tmp_path)
    more = [*facts(preset, visibility)] + (["--acts", ",".join(acts)] if acts else [])

    accept(capsys, root, preset, *more)

    assert files_of(root) == expected_set(preset, visibility, acts)
    assert not (root / "docs" / "specs").exists()


def test_team_and_organization_get_five_files_on_a_fresh_repository(
    tmp_path: Path, capsys: Capture
) -> None:
    for preset in ("team", "organization"):
        root = target(tmp_path, preset)
        accept(capsys, root, preset, "--visibility", "public")
        assert len(files_of(root)) == 5


# 1a. The first design is offered, never written.


def test_the_first_design_is_offered_and_the_overlay_rows_are_printed_as_a_block(
    tmp_path: Path, capsys: Capture
) -> None:
    root = target(tmp_path)
    lifecycle = "team+eu-market+ai-product"

    code, out, _ = run(capsys, root, "--lifecycle", lifecycle, "--visibility", "public")

    assert code == 0
    offer = [
        line for line in out.splitlines() if line.startswith("offer") and "first design" in line
    ]
    assert len(offer) == 1 and "new-spec.sh" in offer[0] and "<slug>" in offer[0]
    assert "--- block for docs/specs/<slug>/design.md (eu-market, ai-product) ---" in out
    block = out.split("--- block for docs/specs/<slug>/design.md", 1)[1]
    assert "cybersecurity risk assessment" in block and "model provider" in block

    accept(capsys, root, lifecycle, "--visibility", "public")
    assert not (root / "docs").exists()

    write(root / "docs/specs/app/design.md", "# app — design\n")
    code, out, _ = run(capsys, root, "--lifecycle", lifecycle, "--visibility", "public")
    assert re.search(r"^present +docs/specs/app/design\.md", out, re.MULTILINE), out
    assert "--- block for docs/specs/app/design.md (eu-market, ai-product) ---" in out


# 2. Each overlay on each preset that takes it.


@pytest.mark.parametrize("preset", PRESETS)
@pytest.mark.parametrize("overlay", OVERLAYS)
def test_each_overlay_on_each_base_adds_exactly_its_parts(
    tmp_path: Path, capsys: Capture, preset: str, overlay: str
) -> None:
    if preset == "prototype" and overlay in REFUSED_ON_PROTOTYPE:
        pytest.skip("the design refuses this overlay on prototype (test 3)")
    visibility = None if preset == "prototype" else "private"
    base, both = target(tmp_path, "base"), target(tmp_path, "both")

    accept(capsys, base, preset, *facts(preset, visibility))
    accept(capsys, both, f"{preset}+{overlay}", *facts(preset, visibility))

    added = files_of(both) - files_of(base)
    brought = {("client", "solo"): {ROUTE}, ("eu-market", "solo"): {SECURITY}}
    assert added == brought.get((overlay, preset), set())
    assert files_of(base) <= files_of(both)
    local = (both / LOCAL).read_text(encoding="utf-8")
    assert OVERLAY_LINE[overlay] in local
    assert OVERLAY_LINE[overlay] not in (base / LOCAL).read_text(encoding="utf-8")
    parsed = fragments.parse_fragment(local, LOCAL)
    assert ("rewriting published history" in parsed.edges) is (overlay == "eu-market")
    if overlay == "client" and preset != "prototype":
        assert "Acceptance" in (both / ROUTE).read_text(encoding="utf-8")
    if overlay == "eu-market" and preset != "prototype":
        assert "Coordinated vulnerability disclosure" in (both / SECURITY).read_text("utf-8")
    for name in files_of(base) - {LOCAL}:
        if overlay not in ("client", "eu-market"):
            assert (base / name).read_bytes() == (both / name).read_bytes(), name


# 3, 4. Usage errors.


@pytest.mark.parametrize(
    "argv",
    [
        ["--lifecycle", "prototype+client"],
        ["--lifecycle", "prototype+eu-market"],
        ["--lifecycle", "prototype+audit"],
        ["--lifecycle", "prototype", "--acts", "deploy"],
        ["--lifecycle", "team+nothing", "--visibility", "public"],
        ["--lifecycle", "team+audit+audit", "--visibility", "public"],
        ["--lifecycle", "team+solo", "--visibility", "public"],
        ["--lifecycle", "client", "--visibility", "public"],
        ["--lifecycle", "team", "--visibility", "public", "--acts", "launch"],
        ["--lifecycle", "team", "--visibility", "public", "--with", "codeowners"],
        ["--lifecycle", "team", "--visibility", "public", "--accept", "--check"],
        ["--lifecycle", "team", "--visibility", "public", "--from", "team+team"],
    ],
)
def test_an_overlay_a_preset_refuses_is_a_usage_error(
    tmp_path: Path, capsys: Capture, argv: list[str]
) -> None:
    root = target(tmp_path)
    before = tree(root)

    code, out, err = run(capsys, root, *argv)

    assert code == 2, out + err
    assert "usage:" in err and out == ""
    assert tree(root) == before


def test_a_refused_overlay_names_the_reason(tmp_path: Path, capsys: Capture) -> None:
    code, _, err = run(capsys, target(tmp_path), "--lifecycle", "prototype+client")

    assert code == 2
    assert "client" in err and "prototype" in err and "outside user" in err


def test_visibility_is_required_beyond_prototype(tmp_path: Path, capsys: Capture) -> None:
    root = target(tmp_path)

    for preset in PRESETS[1:]:
        code, _, err = run(capsys, root, "--lifecycle", preset)
        assert code == 2 and "--visibility" in err

    code, out, _ = run(capsys, root, "--lifecycle", "prototype")
    assert code == 0 and out.startswith("plan prototype")
    code, _, _ = run(capsys, root, "--lifecycle", "prototype", "--visibility", "public")
    assert code == 0


# 5. The plan writes nothing.


def test_the_plan_writes_nothing(tmp_path: Path, capsys: Capture) -> None:
    root = target(tmp_path, files={"README.md": "# x\n", "notes.md": "<<fill: a value>>\n"})
    subprocess.run([GIT, "add", "-A"], cwd=root, check=True)
    before = tree(root)
    lifecycle = ["--lifecycle", "organization+client+eu-market", "--visibility", "public"]

    for mode in ([], ["--json"], ["--check"], ["--check", "--json"], ["--from", "team"]):
        code, _, _ = run(capsys, root, *lifecycle, *mode)
        assert code in (0, 1)
        assert tree(root) == before, mode


# 6, 7. The printed adopt command, and its drift lines.

ADOPTED = [(preset, "") for preset in PRESETS] + [("team", overlay) for overlay in OVERLAYS]


@pytest.mark.parametrize(("preset", "overlay"), ADOPTED)
def test_the_local_fragment_parses_after_adopt_selects_it(
    tmp_path: Path, capsys: Capture, preset: str, overlay: str
) -> None:
    root = target(tmp_path)
    lifecycle = preset + (f"+{overlay}" if overlay else "")
    out = accept(
        capsys, root, lifecycle, *facts(preset, None if preset == "prototype" else "private")
    )
    code, plan, _ = run(
        capsys,
        root,
        "--lifecycle",
        lifecycle,
        *facts(preset, None if preset == "prototype" else "private"),
    )
    assert code == 0 and "PASS" in out

    code = adopt.main(adopt_words(plan))
    out, err = capsys.readouterr()

    assert code == 0, out + err


@pytest.mark.parametrize(("preset", "overlay"), [*ADOPTED[:4], ("team", "client")])
def test_adopt_check_prints_no_drift_line_for_the_scaffolds_own_selection(
    tmp_path: Path, capsys: Capture, preset: str, overlay: str
) -> None:
    root = target(tmp_path)
    lifecycle = preset + (f"+{overlay}" if overlay else "")
    visibility = facts(preset, None if preset == "prototype" else "public")
    accept(
        capsys,
        root,
        lifecycle,
        *visibility,
        *([] if preset == "prototype" else ["--acts", "deploy,tag"]),
    )
    _, plan, _ = run(
        capsys,
        root,
        "--lifecycle",
        lifecycle,
        *visibility,
        *([] if preset == "prototype" else ["--acts", "deploy,tag"]),
    )
    assert adopt.main(adopt_words(plan)) == 0
    capsys.readouterr()

    adopt.main([str(root), "--check"])
    out, _ = capsys.readouterr()

    assert not [line for line in out.splitlines() if line.startswith("drift")], out


# 8-13. --check.


def test_with_each_marker_filled_check_exits_0_and_no_stale_reference(
    tmp_path: Path, capsys: Capture
) -> None:
    root = target(tmp_path)
    lifecycle = [
        "--lifecycle",
        "organization+client+eu-market+ai-product",
        "--visibility",
        "public",
    ]
    more = ["--acts", "deploy,tag", "--with", "codeowners,pr-template"]
    accept(capsys, root, *lifecycle[1:], *more)
    _, plan, _ = run(capsys, root, *lifecycle, *more)
    assert adopt.main(adopt_words(plan)) == 0
    capsys.readouterr()
    assert run(capsys, root, "--check")[0] == 1

    fill_every_marker(root)

    code, out, _ = run(capsys, root, "--check")
    assert code == 0 and out == "PASS no value left to fill\n"
    report = instruction_audit.check(root, [], None)
    stale = [f for f in report.findings if f.check == "stale-reference" and f.verdict != "PASS"]
    assert stale == [], stale


def test_check_lists_each_marker_with_its_file_line_and_kind_and_exits_1_with_the_count_printed(
    tmp_path: Path, capsys: Capture
) -> None:
    files = {
        "CONTRIBUTING.md": "# Route\n\nStaging: <<fill: the staging address>>.\n",
        "docs/gates.md": "a\nb\nGates — acceptance: owner UNVERIFIED (<<owner: acceptance>>)\n",
        "ci.yml": 'run: "<<fill: the Done command>>"\n',
    }
    root = target(tmp_path, files=files)

    code, out, _ = run(capsys, root, "--check")

    assert code == 1
    lines = out.splitlines()
    assert lines[0] == "FAIL 3 values left: 2 to fill, 1 gate owner not named"
    assert "CONTRIBUTING.md:3: fill: the staging address" in lines
    assert "ci.yml:1: fill: the Done command" in lines
    owner = [line for line in lines if line.startswith("docs/gates.md:3: owner: acceptance")]
    assert len(owner) == 1 and "next:" in owner[0]
    assert lines[-1].startswith("next: ")

    code, document = json_report(capsys, root, "--check")
    assert code == 1 and document["verdict"] == "FAIL"
    assert {"path": "docs/gates.md", "line": 3, "kind": "owner", "label": "acceptance"} in (
        document["values"]
    )


@pytest.mark.parametrize("count", [0, 1, 2, 256])
def test_check_exits_0_with_no_marker_and_1_with_one_or_many(
    tmp_path: Path, capsys: Capture, count: int
) -> None:
    root = target(tmp_path, files={"notes.md": "".join(f"<<fill: v{n}>>\n" for n in range(count))})

    code, out, _ = run(capsys, root, "--check")

    assert code == (0 if count == 0 else 1)
    if count:
        assert out.splitlines()[0].startswith(f"FAIL {count} value")


@pytest.mark.skipif(
    os.name != "posix" or os.geteuid() == 0,
    reason="mode 000 keeps a file unreadable only for a POSIX user that is not root",
)
def test_check_counts_a_file_it_cannot_read_as_a_value_left(
    tmp_path: Path, capsys: Capture
) -> None:
    """Breaks if a file the check cannot read, which may hold a marker, reads PASS."""

    root = target(tmp_path, files={"SECURITY.md": "Report to <<fill: reporting channel>>.\n"})
    (root / "SECURITY.md").chmod(0)
    try:
        code, out, _ = run(capsys, root, "--check")
    finally:
        (root / "SECURITY.md").chmod(0o644)

    assert code == 1
    assert (
        out.splitlines()[0]
        == "FAIL 1 value left: 0 to fill, 0 gate owners not named, 1 path not read"
    )
    assert "SECURITY.md:0: unread: cannot read SECURITY.md" in out


@pytest.mark.skipif(
    os.name != "posix" or os.geteuid() == 0,
    reason="mode 000 keeps a folder unreadable only for a POSIX user that is not root",
)
def test_check_counts_a_folder_git_cannot_list_as_a_value_left(
    tmp_path: Path, capsys: Capture
) -> None:
    """Breaks if an untracked folder that Git cannot open, which may hold a marker, reads PASS."""

    root = target(tmp_path)
    write(root / "docs" / "s.md", "<<fill: unresolved>>\n")
    (root / "docs").chmod(0)
    try:
        code, out, _ = run(capsys, root, "--check")
    finally:
        (root / "docs").chmod(0o755)

    assert code == 1
    assert "docs:0: unread: cannot list docs/" in out


def test_check_leaves_out_managed_blocks_and_recorded_copies(
    tmp_path: Path, capsys: Capture
) -> None:
    root = target(tmp_path)
    accept(capsys, root, "prototype")
    _, plan, _ = run(capsys, root, "--lifecycle", "prototype")
    assert adopt.main([*adopt_words(plan), "--harness", "claude-code"]) == 0
    capsys.readouterr()
    agents = (root / "AGENTS.md").read_text(encoding="utf-8")
    assert "<<fill:" in agents  # the local fragment is rendered into a managed block
    copy = root / ".outcomebound/fragments/commands.md"
    write(copy, copy.read_text(encoding="utf-8") + "<<fill: in a recorded copy>>\n")
    write(root / "untracked.md", "<<fill: untracked>>\n")
    write(root / "ignored.md", "<<fill: ignored>>\n")
    write(root / ".gitignore", "ignored.md\n")
    expected = (root / LOCAL).read_text(encoding="utf-8").count("<<") + 1

    code, document = json_report(capsys, root, "--check")

    paths_found = {value["path"] for value in document["values"]}
    assert code == 1 and paths_found == {LOCAL, "untracked.md"}
    assert len(document["values"]) == expected


def test_check_reads_crlf_and_a_byte_order_mark(tmp_path: Path, capsys: Capture) -> None:
    root = target(tmp_path)
    (root / "a.md").write_bytes(b"\xef\xbb\xbfline\r\n<<fill: after a mark>>\r\n")

    code, document = json_report(capsys, root, "--check")

    assert code == 1
    assert document["values"] == [
        {"path": "a.md", "line": 2, "kind": "fill", "label": "after a mark"}
    ]


def test_a_yaml_merge_key_a_here_document_and_a_quoted_marker_are_no_marker(
    tmp_path: Path, capsys: Capture
) -> None:
    files = {
        "a.yml": "base: &b\n  x: 1\nother:\n  <<: *b\n",
        "b.sh": "cat <<EOF\nhello\nEOF\ncat <<'NOTE'\nx\nNOTE\n",
        "c.md": "Write `<<fill: LABEL>>` for a value.\n\n```text\n<<owner: GATE>>\n```\n",
        "d.md": "<<fill:no space>> <<fill: >> <<other: x>>\n",
    }
    root = target(tmp_path, files=files)

    code, out, _ = run(capsys, root, "--check")

    assert (code, out) == (0, "PASS no value left to fill\n")
    lifecycle = ["--lifecycle", "team+eu-market+ai-product+client", "--visibility", "public"]
    printed = [run(capsys, root, *lifecycle)[1], run(capsys, root, *lifecycle, "--accept")[1]]
    write(root / "SECURITY.md", "# Security\n")
    printed.append(run(capsys, root, *lifecycle, "--from", "solo")[1])
    for text in printed:
        assert scaffold.markers_in(text) == [], text


# 14-17a. Presence and the never-overwrite rule.

ELSEWHERE = {
    ".github/CONTRIBUTING.md": ROUTE,
    "docs/CONTRIBUTING.md": ROUTE,
    ".github/workflows/build.yaml": CI,
    ".gitlab-ci.yml": CI,
    ".github/dependabot.yaml": BOT,
    "renovate.json": BOT,
    "renovate.json5": BOT,
    ".github/renovate.json": BOT,
    ".renovaterc": BOT,
    ".renovaterc.json": BOT,
    ".github/SECURITY.md": SECURITY,
    "docs/SECURITY.md": SECURITY,
    "CHANGES.md": CHANGELOG,
    "HISTORY.md": CHANGELOG,
    "CODEOWNERS": CODEOWNERS,
    "docs/CODEOWNERS": CODEOWNERS,
    "pull_request_template.md": PR_TEMPLATE,
    "docs/PULL_REQUEST_TEMPLATE.md": PR_TEMPLATE,
    ".github/PULL_REQUEST_TEMPLATE/feature.md": PR_TEMPLATE,
}


@pytest.mark.parametrize("found", sorted(ELSEWHERE))
def test_accept_leaves_every_present_file_byte_for_byte(
    tmp_path: Path, capsys: Capture, found: str
) -> None:
    root = target(tmp_path)
    (root / found).parent.mkdir(parents=True, exist_ok=True)
    (root / found).write_bytes(b"# Theirs\r\nkept as it is\r\n")
    write(root / LOCAL, "their own local fragment\n")
    before = {found: (root / found).read_bytes(), LOCAL: (root / LOCAL).read_bytes()}
    lifecycle = "organization+client+eu-market"
    more = ["--visibility", "public", "--acts", "tag", "--with", "codeowners,pr-template"]

    out = accept(capsys, root, lifecycle, *more)

    assert {name: (root / name).read_bytes() for name in before} == before
    planned = ELSEWHERE[found]
    if found.casefold() != planned.casefold():
        assert not (root / planned).exists(), out
    assert re.search(rf"^present +{re.escape(LOCAL)}", out, re.MULTILINE)


def test_a_route_named_by_a_streams_line_reads_present(tmp_path: Path, capsys: Capture) -> None:
    local = "x\nStreams — main: route in `docs/route.md`; takes every change.\n"
    named = target(tmp_path, "named", {LOCAL: local, "docs/route.md": "# Route\n"})
    missing = target(tmp_path, "missing", {LOCAL: local})

    out = accept(capsys, named, "team", "--visibility", "private")
    assert not (named / ROUTE).exists()
    assert re.search(r"^present +CONTRIBUTING\.md .*docs/route\.md", out, re.MULTILINE), out

    accept(capsys, missing, "team", "--visibility", "private")
    assert (missing / ROUTE).is_file()


def test_accept_twice_writes_nothing_the_second_time(tmp_path: Path, capsys: Capture) -> None:
    root = target(tmp_path)
    lifecycle = ["organization+client", "--visibility", "public", "--acts", "deploy,tag"]
    accept(capsys, root, *lifecycle)
    before = tree(root)

    out = accept(capsys, root, *lifecycle)

    assert tree(root) == before
    assert out.startswith("PASS nothing to write")


@needs_symlinks
def test_accept_refuses_a_link_a_git_path_and_a_file_that_appeared_after_the_plan(
    tmp_path: Path, capsys: Capture, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A linked .github/: the plan reads its paths refused and does not raise; --accept writes none.
    linked = target(tmp_path, "linked")
    (tmp_path / "elsewhere").mkdir()
    (linked / ".github").symlink_to(tmp_path / "elsewhere", target_is_directory=True)
    lifecycle = ["--lifecycle", "solo", "--visibility", "private"]
    code, out, _ = run(capsys, linked, *lifecycle)
    assert code == 0
    assert re.search(rf"^refused +{re.escape(CI)} .*symlink", out, re.MULTILINE), out
    code, out, _ = run(capsys, linked, *lifecycle, "--accept")
    assert code == 1 and out.startswith("FAIL")
    assert not (linked / LOCAL).exists() and os.listdir(tmp_path / "elsewhere") == []

    # A manifest whose path is inside .git: refused, nothing written.
    source = tmp_path / "engine"
    shutil.copytree(ROOT / "templates" / "scaffold", source / "templates" / "scaffold")
    shutil.copytree(ROOT / "schemas", source / "schemas")
    manifest = json.loads((source / "templates/scaffold/scaffold.json").read_text("utf-8"))
    for item in manifest["files"]:
        if item["path"] == LOCAL:
            item["path"] = ".git/hooks/local.md"
    write(source / "templates/scaffold/scaffold.json", json.dumps(manifest))
    inside = target(tmp_path, "inside")
    code, out, _ = run(capsys, inside, "--lifecycle", "prototype", "--accept", source=source)
    assert code == 1 and not (inside / ".git/hooks/local.md").exists()

    # A file that appears after the plan read the target is never overwritten.
    late = target(tmp_path, "late")
    real_write = fileplan.write

    def appear_first(root, changes, expected):
        write(Path(root) / SECURITY, "theirs\n")
        return real_write(root, changes, expected)

    monkeypatch.setattr(fileplan, "write", appear_first)
    code, out, _ = run(capsys, late, "--lifecycle", "team", "--visibility", "public", "--accept")
    assert code == 1 and out.startswith("FAIL")
    assert (late / SECURITY).read_text(encoding="utf-8") == "theirs\n"


def test_a_file_that_appears_after_the_last_recheck_is_not_overwritten(tmp_path: Path) -> None:
    """The exclusive create of a destination expected absent: a writer that lands in the instant
    between the recheck and the move keeps its bytes."""

    destination = tmp_path / "SECURITY.md"

    def lands() -> None:
        destination.write_text("theirs\n", encoding="utf-8")

    with pytest.raises(fileplan.WriteError):
        fileplan._replace(destination, b"ours\n", lands, create=True)

    assert destination.read_text(encoding="utf-8") == "theirs\n"
    assert [path.name for path in tmp_path.iterdir()] == ["SECURITY.md"]


def test_presence_and_accept_fold_case(tmp_path: Path, capsys: Capture) -> None:
    root = target(tmp_path, files={"security.md": "theirs\n", "Contributing.md": "theirs\n"})

    out = accept(capsys, root, "team", "--visibility", "public")

    assert re.search(r"^present +SECURITY\.md .*security\.md", out, re.MULTILINE), out
    assert re.search(r"^present +CONTRIBUTING\.md .*Contributing\.md", out, re.MULTILINE), out
    names = {path.name for path in root.iterdir()}
    assert "SECURITY.md" not in names and "CONTRIBUTING.md" not in names

    twin = target(tmp_path, "twin", {".GitHub/notes.txt": "theirs\n"})
    code, out, _ = run(capsys, twin, "--lifecycle", "solo", "--visibility", "private")
    assert code == 0 and re.search(rf"^refused +{re.escape(CI)} ", out, re.MULTILINE), out
    code, out, _ = run(capsys, twin, "--lifecycle", "solo", "--visibility", "private", "--accept")
    assert code == 1 and not (twin / LOCAL).exists()
    assert sorted(os.listdir(twin)) == [".GitHub", ".git"]


def test_a_rerun_asks_to_add_nothing_the_files_already_hold_filled_or_not(
    tmp_path: Path, capsys: Capture
) -> None:
    """Breaks if a re-run after --accept prints a block of parts the files already hold, which an
    agent would add a second time; a file that lacks a part still gets its block."""

    flags = ("--lifecycle", "solo+client", "--visibility", "private", "--acts", "deploy")
    root = target(tmp_path)
    accept(capsys, root, *flags[1:])
    local = root / LOCAL
    write(
        local,
        re.sub(r"<<fill: [^<>]+>>", "filled by the person", local.read_text(encoding="utf-8")),
    )

    code, out, _ = run(capsys, root, *flags, "--accept")

    assert code == 0 and "--- block for" not in out and "add it on the person's yes" not in out

    write(root / "CONTRIBUTING.md", "# Contributing\n")
    out = run(capsys, root, *flags)[1]

    assert "--- block for CONTRIBUTING.md (client) ---" in out and "## The client route" in out
    assert f"--- block for {LOCAL}" not in out


# 18, 19. Moves.


def test_a_move_from_prototype_to_team_lists_exactly_the_parts_the_prototype_lacks(
    tmp_path: Path, capsys: Capture
) -> None:
    root = target(tmp_path)
    accept(capsys, root, "prototype")
    before = tree(root)

    code, out, _ = run(
        capsys, root, "--lifecycle", "team", "--visibility", "public", "--from", "prototype"
    )

    assert code == 0 and tree(root) == before
    written = set(re.findall(r"^write +(\S+)", out, re.MULTILINE))
    assert written == expected_set("team", "public") - {LOCAL}
    assert re.search(rf"^present +{re.escape(LOCAL)}", out, re.MULTILINE)
    assert "fragments no longer selected: explore" in out
    block = out.split(f"--- block for {LOCAL}", 1)[1]
    assert "replaced in Context: Exposure — who can be hurt: the owner and" in block
    assert "replaced in Bounds: Leave when — the first outside user" in block
    assert "add to Context:" in block and "Streams — main: route in `CONTRIBUTING.md`" in block
    assert "--fragments local,team,commands" in out


def test_a_move_back_lists_the_parts_no_longer_required_and_deletes_nothing(
    tmp_path: Path, capsys: Capture
) -> None:
    root = target(tmp_path)
    accept(capsys, root, "team+eu-market", "--visibility", "public")
    write(root / "docs/specs/app/design.md", "# app — design\n")
    before = tree(root)

    code, out, _ = run(
        capsys, root, "--lifecycle", "solo", "--visibility", "private", "--from", "team+eu-market"
    )
    accepted = run(
        capsys,
        root,
        "--lifecycle",
        "solo",
        "--visibility",
        "private",
        "--from",
        "team+eu-market",
        "--accept",
    )

    assert code == 0 and accepted[0] == 0 and tree(root) == before
    lines = {line.split()[2]: line for line in out.splitlines() if line.startswith("not required")}
    assert "what to retire" in lines[ROUTE]
    assert "what still holds" in lines[SECURITY]
    assert "what still holds" in lines["docs/specs/app/design.md"]

    code, out, _ = run(
        capsys, root, "--lifecycle", "team", "--visibility", "public", "--from", "team+eu-market"
    )
    parts = [line for line in out.splitlines() if line.startswith("not required")]
    assert any(SECURITY in line and "eu-market" in line for line in parts), out
    assert tree(root) == before


# 20-22. Facts.


def test_private_free_marks_each_platform_guard_not_enforced_and_offers_no_codeowners(
    tmp_path: Path, capsys: Capture
) -> None:
    root = target(tmp_path)

    code, document = json_report(
        capsys, root, "--lifecycle", "organization", "--visibility", "private-free"
    )

    assert code == 0
    status = {act["id"]: act["status"] for act in document["platform_acts"]}
    for guard in ("branch-rule", "required-review", "code-owner-review"):
        assert status[guard].startswith("not enforced"), status
    assert "gitleaks" in status["secret-scan"]
    assert not [item for item in document["files"] if item["path"] == CODEOWNERS]
    code, _, err = run(
        capsys,
        root,
        "--lifecycle",
        "organization",
        "--visibility",
        "private-free",
        "--with",
        "codeowners",
    )
    assert code == 2 and "private-free" in err


def test_other_host_writes_nothing_under_github_and_reads_the_acts_unverified(
    tmp_path: Path, capsys: Capture
) -> None:
    root = target(tmp_path)
    lifecycle = ["--lifecycle", "team", "--visibility", "public", "--host", "other"]

    code, document = json_report(capsys, root, *lifecycle)
    accept(capsys, root, *lifecycle[1:])

    assert code == 0 and not (root / ".github").exists()
    status = {act["id"]: act["status"] for act in document["platform_acts"]}
    assert status["branch-rule"].startswith("UNVERIFIED")
    assert status["required-review"].startswith("UNVERIFIED")
    offers = [item for item in document["files"] if item["state"] == "offer"]
    assert sum("templates/ci/" in item.get("offer", "") for item in offers) == 2


@pytest.mark.parametrize(
    ("act", "fragment", "edge", "changelog"),
    [
        ("deploy", "deploy,runtime", "a deploy to production", False),
        ("publish", "ci-release", None, True),
        ("tag", None, "pushing a tag", True),
        ("stored-data", "db-migrations", "a change to stored production data", False),
    ],
)
def test_each_act_adds_its_fragments_edges_and_files(
    tmp_path: Path,
    capsys: Capture,
    act: str,
    fragment: str | None,
    edge: str | None,
    changelog: bool,
) -> None:
    root = target(tmp_path)
    lifecycle = ["--lifecycle", "team", "--visibility", "public", "--acts", act]

    _, plan, _ = run(capsys, root, *lifecycle)
    accept(capsys, root, *lifecycle[1:])

    words = adopt_words(plan)
    selected = words[words.index("--fragments") + 1].split(",")
    assert selected[:2] == ["local", "team"] and selected[-1] == "commands"
    assert set(selected[2:-1]) == set(fragment.split(",") if fragment else [])
    parsed = fragments.parse_fragment((root / LOCAL).read_text(encoding="utf-8"), LOCAL)
    assert list(parsed.edges) == ([edge] if edge else [])
    assert (root / CHANGELOG).is_file() is changelog


# 23-29. Reports, the manifest, the templates, printed paths, ownership, the work tree.


def test_json_validates_against_the_report_schema_in_each_mode(
    tmp_path: Path, capsys: Capture
) -> None:
    root = target(tmp_path, files={"SECURITY.md": "theirs\n"})
    lifecycle = ["--lifecycle", "organization+client", "--visibility", "public"]

    assert json_report(capsys, root, *lifecycle)[1]["verdict"] == "PLAN"
    assert json_report(capsys, root, *lifecycle, "--from", "team")[1]["from"] == "team"
    assert json_report(capsys, root, *lifecycle, "--accept")[1]["verdict"] == "PASS"
    assert json_report(capsys, root, "--check")[1]["verdict"] == "FAIL"
    assert "lifecycle" not in json_report(capsys, root, "--check")[1]


def test_the_manifest_validates_and_maps_each_source_to_a_part_and_each_part_to_a_source() -> None:
    manifest = json.loads((TEMPLATES / "scaffold.json").read_text(encoding="utf-8"))
    assert validate(manifest, MANIFEST_SCHEMA) == []

    named = {item["head"] for item in manifest["files"] if "head" in item}
    named |= {part["source"] for item in manifest["files"] for part in item["parts"]}
    shipped = {
        path.relative_to(TEMPLATES).as_posix()
        for path in TEMPLATES.rglob("*")
        if path.is_file() and path.name != "scaffold.json"
    }
    assert named == shipped
    ids = [item["id"] for item in manifest["lifecycles"]]
    assert ids == [*PRESETS, *OVERLAYS]
    assert [item["id"] for item in manifest["acts"]] == list(ACTS)
    selectable = {*PRESETS, *OVERLAYS, *ACTS}
    for item in manifest["files"]:
        for part in item["parts"]:
            assert set(part["for"]) <= selectable, part
    for act in manifest["platform_acts"]:
        assert set(act["for"]) <= selectable, act


def test_template_sources_have_no_dot_segment_and_no_name_windows_refuses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sources = [path.relative_to(TEMPLATES).as_posix() for path in TEMPLATES.rglob("*")]
    monkeypatch.setattr(paths, "on_windows", lambda: True)

    for source in sources:
        assert not any(part.startswith(".") for part in source.split("/")), source
        assert paths.windows_refusal(source) is None, source
    manifest = json.loads((TEMPLATES / "scaffold.json").read_text(encoding="utf-8"))
    for item in manifest["files"]:
        if "<" not in item["path"]:
            assert paths.windows_refusal(item["path"]) is None, item["path"]


def test_every_marker_in_a_template_is_one_of_the_two_kinds_on_one_line() -> None:
    manifest = json.loads((TEMPLATES / "scaffold.json").read_text(encoding="utf-8"))
    for path in sorted(TEMPLATES.rglob("*")):
        if not path.is_file() or path.name == "scaffold.json":
            continue
        name = path.relative_to(TEMPLATES).as_posix()
        text = path.read_text(encoding="utf-8")
        for number, line in enumerate(text.splitlines(), start=1):
            opened = line.count("<<")
            found = MARKER.findall(line)
            assert opened == len(found), f"{name}:{number}: {line}"
            for kind, label in found:
                if kind == "owner":
                    assert f"owner UNVERIFIED (<<owner: {label}>>)" in line, f"{name}:{number}"
        assert scaffold.markers_in(text) == [
            (number, kind, label)
            for number, line in enumerate(text.splitlines(), start=1)
            for kind, label in MARKER.findall(line)
        ], f"{name}: a marker inside a code span or a fence"
    local = next(item for item in manifest["files"] if item["path"] == LOCAL)
    head = (TEMPLATES / local["head"]).read_text(encoding="utf-8")
    assert head.startswith("---\n") and "<<" not in head.split("\n---\n", 1)[0]


def test_printed_paths_are_posix_and_printed_commands_are_quoted(
    tmp_path: Path, capsys: Capture, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = target(tmp_path, "a folder")

    code, out, _ = run(capsys, root, "--lifecycle", "team", "--visibility", "public")
    _, document = json_report(capsys, root, "--lifecycle", "team", "--visibility", "public")

    assert code == 0 and "\\" not in out
    assert adopt_words(out)[0] == root.as_posix()
    assert document["adopt"].startswith(f"outcomebound adopt {shlex.quote(root.as_posix())} ")
    assert all("\\" not in item["path"] for item in document["files"])

    monkeypatch.setattr(paths, "on_windows", lambda: True)
    _, out, _ = run(capsys, root, "--lifecycle", "team", "--visibility", "public")
    line = next(line for line in out.splitlines() if line.startswith("adopt:"))
    assert f"'{root.as_posix()}'" in line


def test_scaffold_writes_no_manifest_record_and_adopt_remove_leaves_its_files(
    tmp_path: Path, capsys: Capture
) -> None:
    root = target(tmp_path)
    accept(capsys, root, "team", "--visibility", "public")
    assert not (root / adopt.MANIFEST).exists()
    written = {name: (root / name).read_bytes() for name in files_of(root)}
    _, plan, _ = run(capsys, root, "--lifecycle", "team", "--visibility", "public")
    assert adopt.main(adopt_words(plan)) == 0
    capsys.readouterr()
    recorded = json.loads((root / adopt.MANIFEST).read_text(encoding="utf-8"))
    assert not {record["path"] for record in recorded["artifacts"]} & set(written)

    assert adopt.main([str(root), "--remove"]) == 0
    capsys.readouterr()

    assert {name: (root / name).read_bytes() for name in written} == written


def test_outside_a_git_work_tree_the_verb_refuses_and_names_git_init(
    tmp_path: Path, capsys: Capture
) -> None:
    folder = tmp_path / "plain"
    folder.mkdir()

    for mode in ([], ["--accept"], ["--check"]):
        code, out, err = run(capsys, folder, "--lifecycle", "prototype", *mode)
        assert code == 1 and out == ""
        assert "git init" in err
    assert list(folder.iterdir()) == []


def test_the_templates_that_cannot_be_read_refuse_with_exit_1(
    tmp_path: Path, capsys: Capture
) -> None:
    root = target(tmp_path)

    code, out, err = run(capsys, root, "--lifecycle", "prototype", source=tmp_path / "no-engine")

    assert code == 1 and out == "" and "scaffold.json" in err
