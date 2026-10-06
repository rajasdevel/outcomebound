"""`outcomebound explorable`: `new`, `build` and `check`, and the browser runner.

The seam is the command line, run in this process: a source in, a page out, the verdicts and the
exit codes. The browser runner is tested with a fake browser script (POSIX) that prints a canned
document and leaves a helper running, and, where a Chromium-family browser is found, with a
small page that writes the check result itself. None of it depends on the stylesheet's or the
runtime's content, only on their being inlined byte for byte."""

from __future__ import annotations

import json
import os
import re
import stat
import sys
import time
from pathlib import Path

import pytest

from outcomebound_tools import (
    explorable,
    explorable_browser,
    explorable_check,
    explorable_shell,
)

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "templates" / "explorable"
POSIX = pytest.mark.skipif(os.name == "nt", reason="the fake browser is a POSIX script")
KINDS = ("decision", "learning", "interview")


@pytest.fixture(autouse=True)
def _epoch(monkeypatch):
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1790000000")


def run(*arguments: object) -> int:
    return explorable.main([str(item) for item in arguments])


def started(tmp_path: Path, kind: str = "decision", name: str = "page") -> Path:
    source = tmp_path / f"{name}.source.html"
    assert run("new", source, "--kind", kind) == 0
    return source


def built(tmp_path: Path, kind: str = "decision") -> Path:
    source = started(tmp_path, kind)
    assert run("build", source) == 0
    return tmp_path / "page.html"


def header(kind: str = "decision", **more: str) -> str:
    fields = {"kind": kind, "id": "x", "title": "X", **more}
    return f'<script type="application/json" data-explorable>{json.dumps(fields)}</script>\n'


def source_with(tmp_path: Path, text: str, kind: str = "learning") -> Path:
    source = tmp_path / "s.source.html"
    source.write_text(header(kind) + text, encoding="utf-8")
    return source


# new.


@pytest.mark.parametrize("kind", KINDS)
def test_new_writes_a_starter_that_build_accepts_and_check_passes(tmp_path, kind, capsys):
    page = built(tmp_path, kind)

    assert run("check", page) == 0
    out = report(capsys)
    assert "shell: PASS" in out and "hosts: PASS" in out and "parts: PASS" in out
    assert out[out.index("explorable check:") :].startswith("explorable check: UNVERIFIED")
    assert (tmp_path / "briefs.json").exists() is (kind == "decision")


def test_new_fills_the_id_and_title(tmp_path):
    source = tmp_path / "cache-choice.source.html"

    assert run("new", source, "--kind", "learning", "--title", "How a cache works") == 0

    text = source.read_text(encoding="utf-8")
    assert '"id": "cache-choice"' in text and '"title": "How a cache works"' in text


def test_new_never_writes_over_a_file_and_keeps_an_existing_briefs_file(tmp_path, capsys):
    (tmp_path / "briefs.json").write_text("mine", encoding="utf-8")
    source = tmp_path / "page.source.html"
    source.write_text("mine", encoding="utf-8")

    assert run("new", source, "--kind", "decision") == 1
    assert source.read_text(encoding="utf-8") == "mine"
    other = tmp_path / "other.source.html"
    assert run("new", other, "--kind", "decision") == 0
    assert (tmp_path / "briefs.json").read_text(encoding="utf-8") == "mine"
    assert "never writes over" in capsys.readouterr().err


@pytest.mark.parametrize("name", ["page.html", "1.source.html"])
def test_new_refuses_a_name_it_cannot_use_with_exit_2(tmp_path, name):
    assert run("new", tmp_path / name, "--kind", "learning") == 2
    assert not (tmp_path / name).exists()


# build: refusals.

REFUSED = [
    ("a doctype", "<!doctype html>\n<p>x</p>"),
    *[
        (f"the {tag} element", f"<{tag}></{tag}>")
        for tag in (
            "html",
            "head",
            "body",
            "meta",
            "link",
            "base",
            "style",
            "form",
            "iframe",
            "object",
            "embed",
        )
    ],
    *[
        (f"the {attribute} attribute", f'<div {attribute}="https://example.org/x">x</div>')
        for attribute in (
            "src",
            "href",
            "xlink:href",
            "srcset",
            "srcdoc",
            "action",
            "formaction",
            "poster",
            "data",
            "ping",
            "cite",
            "background",
        )
    ],
    ("a javascript: URL", '<a href="javascript:alert(1)">x</a>'),
    ("an obscured javascript: URL", '<a href=" Java\tScript:alert(1)">x</a>'),
    ("a protocol-relative src", '<img src="//example.org/x.png">'),
    ("an http a href", '<a href="http://example.org">x</a>'),
    ("a style url", '<p style="background:url(https://example.org/x.png)">x</p>'),
    ("a hidden style url", '<p style="background:\\75rl(https://example.org/x.png)">x</p>'),
    ("a second header", header("learning")),
    ("a comment", "<!-- note -->"),
    ("a comment that ends at once", '<!--><img src="https://evil.example/a.png">-->'),
    ("a comment that ends at once, with a dash", '<!---><img src="https://evil.example/a.png">-->'),
    ("a bogus comment", "<!x><p>y</p>"),
    ("a CDATA section", "<![CDATA[x]]>"),
    ("a processing instruction", '<?xml version="1.0"?>'),
    ("a comment opener in script text", '<script>var a = "<!--";</script>'),
    ("a comment opener in a script comment", "<script>/*<!--*/</script>"),
    ("a NUL character", "<p>a\x00b</p>"),
    ("an id the shell owns", '<div id="explorable-check-result">{"done":true}</div>'),
    (
        "a fake check result",
        '<script type="application/json" id="explorable-check-result">{"done":true}</script>',
    ),
    ("an id the brief drawing owns", '<div id="brief-D1">x</div>'),
    ("a reserved id in capitals", '<div id="Explorable-reply">x</div>'),
    ("an id that shadows the runtime", '<div id="explorable">x</div>'),
    ("a name that shadows the runtime", '<input name="explorable">'),
    ("a data-explorable attribute", "<div data-explorable>x</div>"),
    ("the head's end tag", "</head>"),
    ("the body's end tag", "</body>"),
    ("the document's end tag", "</html>"),
    ("the main's end tag", "</main>"),
    ("a title", "<title>t</title>"),
    ("a plaintext element", "<plaintext>"),
    ("an xmp element", "<xmp>"),
    ("a noembed element", "<noembed>"),
    ("a noframes element", "<noframes>"),
    ("a script that is never closed", "<script>var a = 1;"),
]


@pytest.mark.parametrize("what, text", REFUSED, ids=[item[0] for item in REFUSED])
def test_build_refuses_what_the_shell_owns_and_every_load(tmp_path, capsys, what, text):
    source = source_with(tmp_path, text + "\n<fieldset data-question='Q1'></fieldset>")

    assert run("build", source) == 1

    err = capsys.readouterr().err
    assert re.search(r"s\.source\.html:\d+: ", err), err
    assert not (tmp_path / "s.html").exists()


@pytest.mark.parametrize(
    "text",
    [
        "<textarea data-input='note'>a &lt;b&gt;</textarea><script>var a = 1; // note\n</script>",
        '<a href="#top">x</a><img src="data:image/gif;base64,R0lGOD">',
        '<p style="background:url(data:image/png;base64,AAAA)">x</p>',
        '<svg><use href="#a"/></svg>',
    ],
)
def test_build_accepts_fragments_and_data_urls(tmp_path, text):
    assert run("build", source_with(tmp_path, text)) == 0


def test_build_names_the_line_of_a_refused_element(tmp_path, capsys):
    source = source_with(tmp_path, "<p>a</p>\n<p>b</p>\n<iframe></iframe>\n")

    run("build", source)

    assert "s.source.html:4: <iframe>" in capsys.readouterr().err


def test_build_gives_a_citation_rel_and_referrerpolicy(tmp_path):
    text = '<p><a href="https://example.org/doc?a=1&amp;b=2" rel="author" class="c">doc</a></p>'
    source = source_with(tmp_path, text)

    assert run("build", source) == 0

    page = (tmp_path / "s.html").read_text(encoding="utf-8")
    assert (
        '<a href="https://example.org/doc?a=1&amp;b=2" class="c" rel="noopener noreferrer" '
        'referrerpolicy="no-referrer">doc</a>'
    ) in page


@pytest.mark.parametrize(
    "text, fragment",
    [
        ("<p>first</p>\n" + header("learning"), "comes before the header"),
        ("<!-- note -->\n" + header("learning"), "comes before the header"),
        ("<p>no header</p>", "comes before the header"),
        ("", "no header"),
        ('<script type="application/json" data-explorable>{"kind": </script>', "not JSON"),
        (header("poem"), "schema"),
        (header("learning", brief="b.json"), "only a decision's header holds `brief`"),
        (header("decision"), "names its brief document"),
        (header("decision", brief="../b.json"), "inside it"),
        (header("decision", brief="/etc/b.json"), "inside it"),
        (header("decision", brief="gone.json"), "missing"),
        (
            '<script type="application/json" data-explorable>{"kind": "learning", "id": "Bad", '
            '"title": "t"}</script>',
            "schema",
        ),
        (
            '<script type="application/json" data-explorable>{"kind": "learning", "id": "a", '
            '"title": "t", "extra": 1}</script>',
            "schema",
        ),
    ],
)
def test_build_refuses_a_bad_header_or_one_that_is_not_first(tmp_path, capsys, text, fragment):
    source = tmp_path / "s.source.html"
    source.write_text(text, encoding="utf-8")

    assert run("build", source) == 1

    assert fragment in capsys.readouterr().err


def test_build_refuses_a_brief_the_brief_command_would_refuse(tmp_path, capsys):
    source = started(tmp_path)
    briefs = tmp_path / "briefs.json"
    document = json.loads(briefs.read_text(encoding="utf-8"))
    document["briefs"][0]["options"].pop()
    briefs.write_text(json.dumps(document), encoding="utf-8")

    assert run("build", source) == 1

    assert "is refused" in capsys.readouterr().err


def test_build_reads_a_brief_inside_the_sources_folder_only(tmp_path, capsys):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "b.json").write_text(
        (TEMPLATES / "starters" / "decision.briefs.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    source = tmp_path / "docs" / "s.source.html"
    source.write_text(header("decision", brief="b.json"), encoding="utf-8")

    assert run("build", source) == 0


def test_a_missing_source_and_a_wrong_name_are_exit_2(tmp_path):
    assert run("build", tmp_path / "none.source.html") == 2
    assert run("build", tmp_path / "page.html") == 2


# build: the page.


def test_the_pages_first_head_element_is_the_policy_unchanged(tmp_path):
    page = built(tmp_path).read_text(encoding="utf-8")

    head = page.split("<head>\n", 1)[1]
    pins = json.loads((TEMPLATES / "libraries.json").read_text(encoding="utf-8"))
    paths = " ".join(
        f"https://cdn.jsdelivr.net/npm/{p['package']}@{p['version']}/" for p in pins.values()
    )
    assert head.startswith(
        '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; script-src '
        f"'unsafe-inline' {paths}; style-src 'unsafe-inline'; img-src data: blob:; font-src "
        "data:; form-action 'none'; base-uri 'none'\">"
    )


def test_every_library_reference_is_a_pin(tmp_path):
    page = built(tmp_path).read_text(encoding="utf-8")
    pins = json.loads((TEMPLATES / "libraries.json").read_text(encoding="utf-8"))
    config = json.loads(
        re.search(r'id="explorable-config">(.*?)</script>', page, re.DOTALL).group(1)
    )

    assert config["libraries"] == {
        name: {k: v for k, v in pin.items() if k not in ("package", "version")}
        for name, pin in pins.items()
    }
    for url in re.findall(r"https://cdn\.jsdelivr\.net/\S+?(?=[\"'\s<])", page):
        assert any(
            url.startswith(f"https://cdn.jsdelivr.net/npm/{p['package']}@{p['version']}/")
            for p in pins.values()
        )


def test_the_stylesheet_and_runtime_are_inlined_byte_for_byte(tmp_path):
    page = built(tmp_path).read_text(encoding="utf-8")

    assert f"<style>{(TEMPLATES / 'explorable.css').read_text(encoding='utf-8')}</style>" in page
    assert f"<script>{(TEMPLATES / 'explorable.js').read_text(encoding='utf-8')}</script>" in page


def test_the_page_follows_the_shells_order(tmp_path):
    page = built(tmp_path).read_text(encoding="utf-8")

    marks = [
        '<meta http-equiv="Content-Security-Policy"',
        "<style>",
        'id="explorable-config"',
        'class="xp-header"',
        'id="explorable-network"',
        'id="explorable-briefs"',
        'id="explorable-reply"',
    ]
    places = [page.index(mark) for mark in marks]
    assert places == sorted(places)
    assert '<meta name="explorable-kind" content="decision">' in page
    assert "Built 2026-09-20T" in page or re.search(r"Built \d{4}-\d\d-\d\dT", page)


def test_brief_text_with_html_characters_is_escaped_in_the_page(tmp_path):
    source = started(tmp_path)
    briefs = tmp_path / "briefs.json"
    document = json.loads(briefs.read_text(encoding="utf-8"))
    document["briefs"][0]["heading"] = "Use <script>alert(1)</script> here?"
    briefs.write_text(json.dumps(document), encoding="utf-8")
    assert run("build", source) == 0

    page = (tmp_path / "page.html").read_text(encoding="utf-8")

    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page
    config = re.search(r'id="explorable-config">(.*?)</script>', page, re.DOTALL).group(1)
    assert "</script" not in config


def test_a_title_with_markup_is_escaped_and_check_still_passes(tmp_path):
    source = tmp_path / "t.source.html"
    source.write_text(
        '<script type="application/json" data-explorable>{"kind": "interview", "id": "t", '
        '"title": "A <b>\\"b\\"</b> & <\\/script> c"}</script>\n<fieldset data-question="Q1">'
        "</fieldset>",
        encoding="utf-8",
    )

    assert run("build", source) == 0
    assert "<b>" not in (tmp_path / "t.html").read_text(encoding="utf-8").split("<style>")[0]
    assert run("check", tmp_path / "t.html") == 0


def test_two_builds_with_one_epoch_are_equal_and_another_epoch_differs(tmp_path, monkeypatch):
    source = started(tmp_path)
    assert run("build", source) == 0
    first = (tmp_path / "page.html").read_bytes()
    assert run("build", source) == 0
    assert (tmp_path / "page.html").read_bytes() == first
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1790000001")
    assert run("build", source) == 0
    assert (tmp_path / "page.html").read_bytes() != first


def test_a_bad_epoch_is_exit_2(tmp_path, monkeypatch):
    source = started(tmp_path)
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "soon")

    assert run("build", source) == 2


def test_build_writes_over_its_own_page_and_refuses_any_other_file(tmp_path, capsys):
    source = started(tmp_path)
    page = tmp_path / "page.html"
    assert run("build", source) == 0
    page.write_text(page.read_text(encoding="utf-8") + "<!-- edited -->", encoding="utf-8")

    assert run("build", source) == 0
    assert "edited" not in page.read_text(encoding="utf-8")

    page.write_text("<p>mine</p>", encoding="utf-8")
    assert run("build", source) == 1
    assert page.read_text(encoding="utf-8") == "<p>mine</p>"
    assert "not a page this command built" in capsys.readouterr().err


# check.


def change(page: Path, old: str, new: str) -> None:
    text = page.read_text(encoding="utf-8")
    assert old in text
    page.write_text(text.replace(old, new, 1), encoding="utf-8")


def report(capsys) -> str:
    """The check's output: what it printed from its first line."""

    out = capsys.readouterr().out
    return out[out.index("explorable check:") :] if "explorable check:" in out else out


def verdicts(capsys) -> dict[str, str]:
    out = report(capsys)
    return {
        line.split(":")[0]: line.split(" ")[1] for line in out.splitlines()[1:] if line[:1] != " "
    } | {"overall": out.split("\n", 1)[0].split(" ")[2]}


def test_a_built_page_passes_with_the_run_named_unverified(tmp_path, capsys):
    page = built(tmp_path)

    assert run("check", page) == 0

    assert verdicts(capsys) == {
        "overall": "UNVERIFIED",
        "shell": "PASS",
        "hosts": "PASS",
        "parts": "PASS",
        "run": "UNVERIFIED",
        "note": "a",
    }


@pytest.mark.parametrize(
    "old, new, fragment",
    [
        ("default-src 'none'", "default-src *", "Content-Security-Policy"),
        ("chart.js@4.5.1/", "chart.js@4.5.2/", "Content-Security-Policy"),
        ('"global": "Chart"', '"global": "Evil"', "library pins"),
        ("<style>", "<style>/* x */", "stylesheet"),
        ('<script type="application/json" id="explorable-config">', "<script>", "frame"),
        (
            '<meta name="explorable-kind" content="decision">',
            '<meta name="explorable-kind" content="learning">',
            "kind",
        ),
        (
            '<meta name="generator" content="outcomebound explorable',
            '<meta name="generator" content="x',
            "frame",
        ),
        ('<main class="xp-main">', '<main class="xp-main" onclick="x()">', "frame"),
    ],
)
def test_check_fails_a_page_whose_shell_was_changed(tmp_path, capsys, old, new, fragment):
    page = built(tmp_path)
    change(page, old, new)

    assert run("check", page) == 1

    out = report(capsys)
    assert out.startswith("explorable check: FAIL")
    assert "shell: FAIL" in out and "next: build again" in out
    assert fragment in out


def test_check_fails_a_changed_runtime(tmp_path, capsys):
    page = built(tmp_path)
    change(page, "placeholder until the runtime milestone lands: the runtime script", "x")

    assert run("check", page) == 1

    assert "the runtime differs" in capsys.readouterr().out


def test_a_page_built_by_another_engine_fails_the_shell_and_says_to_build_again(
    tmp_path, capsys, monkeypatch
):
    page = built(tmp_path)
    monkeypatch.setattr(explorable_shell, "policy", lambda pins=None: "default-src 'none'")

    assert run("check", page) == 1

    assert "next: build again" in capsys.readouterr().out


@pytest.mark.parametrize(
    "kind, old, fragment",
    [
        ("decision", 'data-brief="D1"', "holds a brief"),
        ("learning", "data-question", "data-question"),
        ("interview", "data-question", "data-question"),
    ],
)
def test_check_fails_a_page_without_the_parts_its_kind_needs(tmp_path, capsys, kind, old, fragment):
    page = built(tmp_path, kind)
    text = page.read_text(encoding="utf-8").replace(old, "data-other")
    page.write_text(text, encoding="utf-8")

    assert run("check", page) == 1

    assert "parts: FAIL" in capsys.readouterr().out


def test_check_fails_a_hosts_defect_a_build_could_not_see(tmp_path, capsys):
    page = built(tmp_path, "learning")
    change(page, "<fieldset", '<img src="https://example.org/t.png"><fieldset')

    assert run("check", page) == 1

    out = report(capsys)
    assert "hosts: FAIL" in out and "src=" in out


def test_check_fails_a_script_string_that_names_an_address(tmp_path, capsys):
    source = source_with(
        tmp_path,
        "<fieldset data-question='Q1'></fieldset>\n<script>fetch('https://example.org/a');</script>",
    )
    assert run("build", source) == 0

    assert run("check", tmp_path / "s.html") == 1

    assert "could name an address" in capsys.readouterr().out


def test_check_fails_a_citation_without_what_build_adds(tmp_path, capsys):
    source = source_with(
        tmp_path, "<fieldset data-question='Q1'></fieldset><a href='https://example.org'>x</a>"
    )
    assert run("build", source) == 0
    page = tmp_path / "s.html"
    assert run("check", page) == 0
    change(page, ' rel="noopener noreferrer"', "")

    assert run("check", page) == 1

    assert "lacks rel" in capsys.readouterr().out


def test_check_exits_2_for_a_page_it_cannot_read_and_for_a_usage_error(tmp_path):
    assert run("check", tmp_path / "none.html") == 2
    with pytest.raises(SystemExit) as caught:
        run("check", tmp_path / "x.html", "--timeout", "0")
    assert caught.value.code == 2


def test_a_page_that_fails_is_not_run(tmp_path, capsys, monkeypatch):
    page = built(tmp_path)
    change(page, "default-src 'none'", "default-src *")
    monkeypatch.setenv("OUTCOMEBOUND_BROWSER", str(tmp_path / "never"))

    assert run("check", page, "--browser") == 1

    assert "not run: the shell, hosts and parts do not all pass" in capsys.readouterr().out


# The browser: discovery, with a fake environment.


def fake_files(*present: str):
    return lambda path: path in present


def test_the_named_browser_comes_first_and_must_be_a_file(tmp_path):
    chosen = tmp_path / "mine"
    chosen.write_text("", encoding="utf-8")

    found, _ = explorable_browser.find_browser(
        {"OUTCOMEBOUND_BROWSER": str(chosen), "PATH": ""}, platform="linux"
    )
    assert found == str(chosen)
    none, why = explorable_browser.find_browser(
        {"OUTCOMEBOUND_BROWSER": str(tmp_path / "gone"), "PATH": ""}, platform="linux"
    )
    assert none is None and "not a file" in why


@POSIX
def test_programs_on_path_are_tried_in_the_documented_order(tmp_path):
    for name in ("brave", "chromium"):
        program = tmp_path / name
        program.write_text("#!/bin/sh\n", encoding="utf-8")
        program.chmod(program.stat().st_mode | stat.S_IXUSR)

    found, how = explorable_browser.find_browser({"PATH": str(tmp_path)}, platform="linux")

    assert found == str(tmp_path / "chromium") and "chromium" in how


def test_install_folders_are_read_on_macos_and_windows():
    mac = explorable_browser.MACOS_PATHS[1]
    found, _ = explorable_browser.find_browser(
        {"PATH": ""}, platform="darwin", is_file=fake_files(mac)
    )
    assert found == mac
    edge = os.path.join("C:\\Programs", r"Microsoft\Edge\Application\msedge.exe")
    found, _ = explorable_browser.find_browser(
        {"PATH": "", "PROGRAMFILES": "C:\\Programs"}, platform="win32", is_file=fake_files(edge)
    )
    assert found == edge


def test_no_browser_is_a_reason_not_an_error():
    found, why = explorable_browser.find_browser({"PATH": ""}, platform="linux")

    assert found is None and "Firefox" in why


# The browser: result parsing.

RESULT = {
    "done": True,
    "errors": [],
    "expectations": [{"label": "a", "pass": True, "expected": {"o": "30"}, "shown": {"o": "30"}}],
    "outputs": {"names": ["o"], "covered": ["o"], "uncovered": []},
    "libraries": {"chart": "unused", "mermaid": "failed"},
    "diagrams": {"drawn": 0, "failed": 0},
}


def document(result: object) -> str:
    return (
        '<html><body><script type="application/json" id="explorable-check-result">'
        f"{json.dumps(result)}</script></body></html>"
    )


def test_a_result_in_the_printed_document_is_read():
    found, reason = explorable_browser.parse_result(document(RESULT))

    assert found == RESULT and reason == ""


@pytest.mark.parametrize(
    "text, fragment",
    [
        ("<html></html>", "no check result"),
        ('<script id="explorable-check-result">{', "not JSON"),
        ('<script id="explorable-check-result">{</script>', "not JSON"),
        (document({"done": False}), "not complete"),
        (document([1]), "not complete"),
    ],
)
def test_a_missing_or_malformed_result_is_named(text, fragment):
    found, reason = explorable_browser.parse_result(text)

    assert found is None and fragment in reason


def test_the_verdict_of_a_result():
    assert explorable_check.run(RESULT).status == "PASS"
    failed = {**RESULT, "errors": ["boom"]}
    assert explorable_check.run(failed).status == "FAIL"
    wrong = {**RESULT, "expectations": [{**RESULT["expectations"][0], "pass": False}]}
    assert explorable_check.run(wrong).status == "FAIL"
    open_output = {**RESULT, "outputs": {"names": ["o", "p"], "covered": ["o"], "uncovered": ["p"]}}
    verdict = explorable_check.run(open_output)
    assert verdict.status == "UNVERIFIED" and "output p: UNVERIFIED" in verdict.details[0]
    assert "mermaid failed" in explorable_check.run(RESULT).details[0]


# The browser: a fake browser that prints a document and leaves a helper running.

FAKE = """#!{python}
import os, subprocess, sys, time
folder = os.environ["FAKE_DIR"]
profile = [a for a in sys.argv if a.startswith("--user-data-dir=")][0].split("=", 1)[1]
open(folder + "/profile", "w").write(profile)
open(folder + "/args", "w").write("\\n".join(sys.argv[1:]))
helper = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
open(folder + "/helper", "w").write(str(helper.pid))
if os.environ.get("FAKE_MODE", "document") == "document":
    sys.stdout.write(open(folder + "/document.html").read())
    sys.stdout.flush()
if os.environ.get("FAKE_MODE") == "exit":
    sys.exit(0)
time.sleep(120)
"""


@pytest.fixture
def fake(tmp_path, monkeypatch):
    folder = tmp_path / "fake"
    folder.mkdir()
    program = folder / "browser"
    program.write_text(FAKE.format(python=sys.executable), encoding="utf-8")
    program.chmod(0o755)
    monkeypatch.setenv("FAKE_DIR", str(folder))
    monkeypatch.setenv("OUTCOMEBOUND_BROWSER", str(program))
    return folder, program


def gone(pid: int) -> bool:
    for _ in range(50):
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        time.sleep(0.1)
    return False


@POSIX
def test_the_runner_reads_to_the_end_of_the_document_then_stops_the_whole_group(fake, tmp_path):
    folder, program = fake
    (folder / "document.html").write_text(document(RESULT), encoding="utf-8")
    page = tmp_path / "p.html"
    page.write_text("x", encoding="utf-8")

    ran = explorable_browser.run_page(str(program), page, 30)

    assert ran.document is not None and "explorable-check-result" in ran.document
    assert gone(int((folder / "helper").read_text(encoding="utf-8")))
    assert not Path((folder / "profile").read_text(encoding="utf-8")).exists()
    args = (folder / "args").read_text(encoding="utf-8").splitlines()
    assert "--headless=new" in args and "--dump-dom" in args
    assert args[-1] == page.resolve().as_uri() + "#explorable-check"


@POSIX
def test_a_browser_that_prints_nothing_reads_as_the_limit(fake, tmp_path, monkeypatch):
    folder, program = fake
    monkeypatch.setenv("FAKE_MODE", "silent")
    page = tmp_path / "p.html"
    page.write_text("x", encoding="utf-8")

    ran = explorable_browser.run_page(str(program), page, 1)

    assert ran.document is None and "1 s limit" in ran.reason
    assert gone(int((folder / "helper").read_text(encoding="utf-8")))


@POSIX
def test_a_browser_that_exits_without_a_document_reads_as_that(fake, tmp_path, monkeypatch):
    _, program = fake
    monkeypatch.setenv("FAKE_MODE", "exit")
    page = tmp_path / "p.html"
    page.write_text("x", encoding="utf-8")

    ran = explorable_browser.run_page(str(program), page, 30)

    assert ran.document is None and "without printing" in ran.reason


# check --browser through the command line, with the fake browser.


@POSIX
@pytest.mark.parametrize(
    "result, code, overall, run_line",
    [
        (RESULT, 0, "PASS", "run: PASS"),
        ({**RESULT, "errors": ["x is not defined"]}, 1, "FAIL", "run: FAIL"),
        (
            {**RESULT, "outputs": {"names": ["o", "p"], "covered": ["o"], "uncovered": ["p"]}},
            0,
            "UNVERIFIED",
            "run: UNVERIFIED",
        ),
    ],
)
def test_check_browser_reports_the_run(fake, tmp_path, capsys, result, code, overall, run_line):
    folder, _ = fake
    (folder / "document.html").write_text(document(result), encoding="utf-8")
    page = built(tmp_path)

    assert run("check", page, "--browser") == code

    out = report(capsys)
    assert out.startswith(f"explorable check: {overall}") and run_line in out


@POSIX
def test_check_browser_fails_a_page_that_wrote_no_result(fake, tmp_path, capsys):
    folder, _ = fake
    (folder / "document.html").write_text("<html></html>", encoding="utf-8")

    assert run("check", built(tmp_path), "--browser") == 1

    assert "the page wrote no check result" in capsys.readouterr().out


@POSIX
def test_check_browser_with_a_silent_browser_is_unverified_and_names_the_limit(
    fake, tmp_path, capsys, monkeypatch
):
    monkeypatch.setenv("FAKE_MODE", "silent")

    assert run("check", built(tmp_path), "--browser", "--timeout", "1") == 0

    assert "run: UNVERIFIED not run: the browser printed no document within the 1 s limit" in (
        capsys.readouterr().out
    )


def test_check_browser_with_no_browser_is_unverified(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("OUTCOMEBOUND_BROWSER", raising=False)
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.setattr(explorable_browser, "MACOS_PATHS", ())
    monkeypatch.setattr(sys, "platform", "linux")

    assert run("check", built(tmp_path), "--browser") == 0

    assert "run: UNVERIFIED not run: no Chromium-family browser" in capsys.readouterr().out


# A real browser, where one is found.

HAND_MADE = """<!doctype html><html><body><script>
var s = document.createElement('script');
s.type = 'application/json'; s.id = 'explorable-check-result';
s.textContent = JSON.stringify({done: true, errors: [], expectations: [],
  outputs: {names: [], covered: [], uncovered: []}, libraries: {},
  diagrams: {drawn: 0, failed: 0}});
document.body.appendChild(s);
</script></body></html>
"""


def test_a_real_browser_prints_the_result_a_page_writes(tmp_path):
    browser, _ = explorable_browser.find_browser()
    if browser is None:
        pytest.skip("no Chromium-family browser on this machine")
    page = tmp_path / "hand.html"
    page.write_text(HAND_MADE, encoding="utf-8")

    ran = explorable_browser.run_page(browser, page, 90)

    assert ran.document is not None, ran.reason
    result, reason = explorable_browser.parse_result(ran.document)
    assert result is not None and result["done"] is True, reason


# Parser differentials, the reserved names, and what `check` finds in a page.


def test_a_header_after_other_content_is_reported_once(tmp_path, capsys):
    source = tmp_path / "s.source.html"
    source.write_text("<p>first</p>\n" + header("learning"), encoding="utf-8")

    assert run("build", source) == 1

    err = capsys.readouterr().err
    assert "comes before the header" in err and "second header" not in err


def test_a_second_header_after_the_first_is_still_refused(tmp_path, capsys):
    source = source_with(tmp_path, header("learning"))

    assert run("build", source) == 1

    assert "a second header" in capsys.readouterr().err


def test_a_refused_comment_names_its_line(tmp_path, capsys):
    source = source_with(tmp_path, "<p>a</p>\n<p>b</p>\n<!--><img src=x>-->\n")

    run("build", source)

    assert "s.source.html:4: `<!`" in capsys.readouterr().err


@pytest.mark.parametrize(
    "put",
    [
        '<div id="explorable-check-result">{"done": true}</div>',
        '<script type="application/json" id="explorable-check-result">{"done":true}</script>',
        "<div data-explorable></div>",
        '<div id="explorable"></div>',
    ],
)
def test_check_fails_reserved_names_in_a_page_edited_after_the_build(tmp_path, capsys, put):
    page = built(tmp_path, "learning")
    change(page, "<fieldset", put + "<fieldset")

    assert run("check", page) == 1

    assert "hosts: FAIL" in capsys.readouterr().out


def test_check_fails_a_comment_in_a_page_edited_after_the_build(tmp_path, capsys):
    page = built(tmp_path, "learning")
    change(page, "<fieldset", "<!--><img src=x>--><fieldset")

    assert run("check", page) == 1

    assert "hosts: FAIL" in capsys.readouterr().out


def test_check_fails_markup_that_could_end_or_hide_the_configuration(tmp_path, capsys):
    page = built(tmp_path, "learning")
    change(page, '"briefs": []', '"briefs": ["<!--"]')

    assert run("check", page) == 1

    assert "the configuration holds markup" in capsys.readouterr().out


def test_the_brief_drawings_own_names_do_not_fail_the_hosts_verdict(tmp_path, capsys):
    page = built(tmp_path)

    assert run("check", page) == 0

    assert "hosts: PASS" in capsys.readouterr().out


def test_a_page_with_a_second_result_element_is_not_read(tmp_path):
    fake = (
        '<div id="explorable-check-result">{"done": true}</div>'
        '<script>var s = "<script id=\\"explorable-check-result\\">";</script>'
    )
    one = document(RESULT)

    assert explorable_browser.parse_result(one.replace("<body>", "<body>" + fake))[0] is None
    found, reason = explorable_browser.parse_result(
        one.replace("<body>", "<body>" + fake.split("<script>")[0])
    )
    assert found is None and "2 elements" in reason
    inert = '<script>var s = "<script id=\\"explorable-check-result\\">";</script>'
    assert explorable_browser.parse_result(one.replace("<body>", "<body>" + inert))[0] == RESULT


@POSIX
def test_check_browser_fails_a_page_whose_document_holds_two_results(fake, tmp_path, capsys):
    folder, _ = fake
    two = document(RESULT).replace("</body>", '<p id="explorable-check-result"></p></body>')
    (folder / "document.html").write_text(two, encoding="utf-8")

    assert run("check", built(tmp_path), "--browser") == 1

    assert "2 elements" in report(capsys)
