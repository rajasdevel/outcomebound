"""`outcomebound sources links`: each code has a file that triggers it and a clean file beside it
(the negative control); external links are counted and never broken; the exits, the verdict line,
the JSON report, and that nothing is written."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from outcomebound_tools import sources, sources_links
from outcomebound_tools.schemacheck import validate
from tests.adopt_helpers import repo
from tests.portable import write

HOME = Path(__file__).resolve().parent.parent
ENV = ["-c", "user.name=t", "-c", "user.email=t@example.test"]


def schema() -> dict:
    return json.loads((HOME / "schemas" / "sources-links-report.schema.json").read_text("utf-8"))


@pytest.fixture
def project(tmp_path, monkeypatch):
    root = repo(tmp_path / "p")
    monkeypatch.chdir(root)
    return root


def put(root: Path, name: str, text: str) -> None:
    (root / name).parent.mkdir(parents=True, exist_ok=True)
    write(root / name, text)


def links(capsys, *argv: str) -> tuple[int, str]:
    code = sources.main(["links", *argv])
    return code, capsys.readouterr().out


def codes(capsys, *argv: str) -> list[str]:
    code, out = links(capsys, "--json", *argv)
    document = json.loads(out)
    assert validate(document, schema()) == []
    assert code == (1 if document["broken"] else 0)
    return [f"{b['file']}:{b['line']}:{b['code']}" for b in document["broken"]]


def test_clean_file_passes_and_broken_file_fails_with_file_and_line(project, capsys):
    put(project, "other.md", "# Other\n\n## Part\n")
    put(project, "ok.md", "# Ok\n\nSee [o](other.md#part) and [self](#ok).\n")
    code, out = links(capsys, "ok.md")
    assert code == 0 and out.splitlines()[0].startswith("VERDICT: PASS broken=0")
    put(project, "bad.md", "# Bad\n\ntext\n[gone](nothing.md) and [x](other.md#absent)\n")
    code, out = links(capsys, "bad.md")
    assert code == 1
    assert "bad.md:4: LINK_FILE_MISSING nothing.md" in out
    assert "bad.md:4: LINK_ANCHOR_MISSING other.md#absent" in out
    assert out.splitlines()[0].startswith("VERDICT: FAIL broken=2")


def test_anchors_follow_github_slugs_with_suffixes_setext_and_markup(project, capsys):
    put(
        project,
        "t.md",
        "# Same\n\n## Same\n\n### Same\n\nSetext Title\n------------\n\n"
        "## A [link](x.md) & `code`!\n\n```\n# not a heading\n```\n",
    )
    put(
        project,
        "from.md",
        "[a](t.md#same) [b](t.md#same-1) [c](t.md#same-2) [d](t.md#same-3)\n"
        "[e](t.md#setext-title) [f](t.md#a-link--code) [g](t.md#not-a-heading)\n",
    )
    assert codes(capsys, "from.md") == [
        "from.md:1:LINK_ANCHOR_MISSING",
        "from.md:2:LINK_ANCHOR_MISSING",
    ]


def test_fences_and_code_spans_hide_links_and_external_links_are_never_broken(project, capsys):
    put(
        project,
        "f.md",
        "`[x](missing.md)`\n\n```\n[y](missing.md)\n```\n"
        "[w](https://example.test/x) <https://example.test/y> [m](mailto:a@example.test)\n",
    )
    code, out = links(capsys, "f.md", "--json")
    document = json.loads(out)
    assert code == 0 and document["broken"] == []
    assert [n["code"] for n in document["not_checked"]] == ["external"] * 3
    assert validate(document, schema()) == []


def test_reference_definitions_escapes_titles_and_nested_images(project, capsys):
    put(project, "a b.md", "# T\n")
    put(project, "img.png", "x")
    put(
        project,
        "r.md",
        '[ref]: gone.md\n[![i](img.png)](a%20b.md "title") [<a b.md>](<a b.md#t>)\n'
        "[q](a%20b.md?plain=1#t) [z](/img.png)\n",
    )
    assert codes(capsys, "r.md") == ["r.md:1:LINK_FILE_MISSING"]


def test_link_case_must_match_the_file_name(project, capsys):
    put(project, "Real.md", "# R\n")
    put(project, "c.md", "[a](real.md)\n")
    assert codes(capsys, "c.md") == ["c.md:1:LINK_FILE_MISSING"]


def test_line_references_past_the_end_of_a_file(project, capsys):
    put(project, "src/m.py", "a\nb\nc\n")
    put(
        project,
        "n.md",
        "`src/m.py:3` `src/m.py:2-3,1` `src/m.py:4` `src/m.py:1-9` "
        "[l](src/m.py#L3) [l](src/m.py#L7-L8) `src/gone.py:1` `gone.py:1` "
        "`localhost:8080` `x.com:80`\n",
    )
    assert codes(capsys, "n.md") == [
        "n.md:1:LINE_PAST_END",
        "n.md:1:LINE_PAST_END",
        "n.md:1:LINE_PAST_END",
        "n.md:1:REF_MISSING",
    ]
    _, out = links(capsys, "n.md", "--json")
    assert [n["code"] for n in json.loads(out)["not_checked"]] == ["unresolved_name"]


def test_git_refs_marked_by_a_word_resolve_or_break(project, capsys):
    put(project, "x.txt", "x\n")
    subprocess.run(["git", "add", "."], cwd=project, check=True)
    subprocess.run(["git", *ENV, "commit", "-qm", "m"], cwd=project, check=True)
    subprocess.run(["git", "tag", "v1"], cwd=project, check=True)
    head = (
        subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], cwd=project, capture_output=True, check=True
        )
        .stdout.decode("utf-8")
        .strip()
    )
    put(
        project,
        "g.md",
        f"commit `{head}`, tag `v1`, branch `nowhere`, rev at `deadbeef0000`, "
        "git commit `-s`, branch `<name>`, a bare `deadbee1`, and tag `v<VERSION>`.\n",
    )
    assert codes(capsys, "g.md") == ["g.md:1:REF_UNRESOLVED"] * 3


def test_refs_outside_a_repository_are_not_checked_not_broken(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    put(tmp_path, "g.md", "commit `abc1234`\n")
    code, out = links(capsys, "g.md", "--json")
    document = json.loads(out)
    assert code == 0 and [n["code"] for n in document["not_checked"]] == ["git_unavailable"]


def test_targets_outside_the_root_are_not_read(project, capsys):
    (project.parent / "secret.md").write_text("# S\n", "utf-8")
    put(project, "o.md", "[s](../secret.md#nope) [t](/etc/passwd#x)\n")
    _, out = links(capsys, "o.md", "--json")
    document = json.loads(out)
    assert [n["code"] for n in document["not_checked"]] == ["outside_root"]
    assert [b["code"] for b in document["broken"]] == ["LINK_FILE_MISSING"]


def test_folders_are_walked_and_usage_errors_exit_2(project, capsys):
    put(project, "docs/one.md", "[x](nope.md)\n")
    put(project, "docs/skip.txt", "[x](nope.md)\n")
    assert codes(capsys, "docs") == ["docs/one.md:1:LINK_FILE_MISSING"]
    assert sources.main(["links", "missing-folder"]) == 2
    (project / "empty").mkdir()
    assert sources.main(["links", "empty"]) == 2
    capsys.readouterr()
    with pytest.raises(SystemExit) as stopped:
        sources.main(["links"])
    assert stopped.value.code == 2


def test_the_check_writes_nothing(project, capsys):
    put(project, "w.md", "# W\n[a](nope.md) `commit` `src:1`\n")
    before = {
        p: p.read_bytes() for p in project.rglob("*") if p.is_file() and ".git" not in p.parts
    }
    links(capsys, "w.md")
    after = {p: p.read_bytes() for p in project.rglob("*") if p.is_file() and ".git" not in p.parts}
    assert before == after


def test_anchors_of_counts_a_repeated_slug_from_zero():
    assert sources_links.anchors_of("# A\n## A\n## A\n") == {"a", "a-1", "a-2"}


def test_frontmatter_and_natural_slugs_do_not_shift_duplicate_suffixes(project, capsys):
    put(project, "t.md", "---\nstatus: ratified\n---\n\n# Foo\n\n# Foo 1\n\n# Foo\n")
    put(
        project, "f.md", "[a](t.md#foo) [b](t.md#foo-1) [c](t.md#foo-2) [d](t.md#status-ratified)\n"
    )
    assert codes(capsys, "f.md") == ["f.md:1:LINK_ANCHOR_MISSING"]


def test_heading_entities_and_links_slug_as_rendered(project, capsys):
    put(project, "t.md", "## A &amp; B\n\n## See [the design](x.md)\n\n## Caf\u00e9\n")
    put(project, "f.md", "[a](t.md#a--b) [b](t.md#see-the-design) [c](t.md#caf%C3%A9)\n")
    assert codes(capsys, "f.md") == []


def test_badges_footnotes_comments_and_scheme_like_targets(project, capsys):
    put(project, "m.py", "a\nb\n")
    put(
        project,
        "b.md",
        "[![CI](https://example.test/b.svg)](gone.md)\n[^1]: See the appendix.\n"
        "<!-- [old](gone2.md)\n[old](gone3.md) -->\n[a](m.py:2) [b](m.py:3) [c](m.py?plain=1#L9)\n"
        "[d](m.py#L1C2-L2C4)\n",
    )
    assert codes(capsys, "b.md") == [
        "b.md:1:LINK_FILE_MISSING",
        "b.md:5:LINE_PAST_END",
        "b.md:5:LINE_PAST_END",
    ]


def test_bare_path_line_tokens_need_a_slash_and_a_known_suffix(project, capsys):
    put(project, "src/m.py", "a\n")
    put(project, "n.md", "see src/m.py:5 and m.py:5 and src/Makefile:1 and ghcr.io/o/i:1\n")
    assert codes(capsys, "n.md") == ["n.md:1:LINE_PAST_END", "n.md:1:REF_MISSING"]


def test_symlinks_out_of_root_and_named_files_outside_root(project, capsys):
    outside = project.parent / "outside"
    outside.mkdir()
    (outside / "x.md").write_text("# X\n", "utf-8")
    (project / "out").symlink_to(outside, target_is_directory=True)
    put(project, "s.md", "[a](out/x.md#nope)\n")
    _, out = links(capsys, "s.md", "--json")
    assert [n["code"] for n in json.loads(out)["not_checked"]] == ["outside_root"]
    assert sources.main(["links", str(outside / "x.md")]) == 2


def test_a_ref_name_that_looks_like_an_option_is_never_read(project, capsys):
    put(project, "g.md", "branch `--output=x`\n")
    assert codes(capsys, "g.md") == []
