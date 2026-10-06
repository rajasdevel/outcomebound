"""The starter page of each kind runs in a Chromium-family browser, headless, from disk.

Each test drives the CLI the design fixes: `explorable new`, `build` and `check --browser`, with
exit codes 0 (nothing fails), 1 (a FAIL) and 2 (the page cannot be read). The tests need no
network: a library that does not load shows its fallback, which is not a script error. They are
skipped, with the reason, where no browser is found.
"""

import html
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from outcomebound_tools import explorable_browser

ROOT = Path(__file__).resolve().parent.parent
KINDS = ("decision", "learning", "interview")
LINE = re.compile(
    r"^(?:explorable [a-z][a-z0-9-]* built \S+"
    r"|choice [A-Za-z][A-Za-z0-9-]*: (?:none|[A-Z]( .+)?)"
    r"|input [A-Za-z][A-Za-z0-9_]*: \S+ -> .+"
    r"|answer \S+: .+"
    r"|note: .+)$"
)
TIME_LIMIT = 90

BROWSER, WHERE = explorable_browser.find_browser()
needs_browser = pytest.mark.skipif(BROWSER is None, reason=WHERE)


def cli(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ, SOURCE_DATE_EPOCH="1790000000", PYTHONPATH=str(ROOT))
    return subprocess.run(
        [sys.executable, "-m", "outcomebound_tools", "explorable", *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=TIME_LIMIT * 2,
        check=False,
    )


def make_page(kind: str, folder: Path, edit=None) -> tuple[Path, Path]:
    """`new` then `build` for one kind; `edit` may change the source text between them."""

    source = folder / f"{kind}-page.source.html"
    made = cli(
        "new",
        str(source),
        "--kind",
        kind,
        "--id",
        f"{kind}-page",
        "--title",
        "Test page",
        cwd=folder,
    )
    assert made.returncode == 0, made.stdout + made.stderr
    if edit is not None:
        source.write_text(edit(source.read_text(encoding="utf-8")), encoding="utf-8")
    built = cli("build", str(source), cwd=folder)
    assert built.returncode == 0, built.stdout + built.stderr
    return source, folder / f"{kind}-page.html"


def dump_dom(page: Path) -> str:
    """The document the engine's own runner reads after the page has run with the check fragment."""

    assert BROWSER is not None
    run = explorable_browser.run_page(BROWSER, page, TIME_LIMIT)
    assert run.document is not None, run.reason
    return run.document


def result_of(dom: str) -> dict:
    result, reason = explorable_browser.parse_result(dom)
    assert result is not None, reason
    return result


def reply_of(dom: str) -> list[str]:
    found = re.search(r'<pre class="xp-reply-text"[^>]*>(.*?)</pre>', dom, re.S)
    assert found, "the page has no reply text"
    return html.unescape(found.group(1)).splitlines()


@needs_browser
@pytest.mark.parametrize("kind", KINDS)
def test_starter_page_runs_and_its_expectations_pass(kind: str, tmp_path: Path) -> None:
    _, page = make_page(kind, tmp_path)
    checked = cli("check", str(page), "--browser", cwd=tmp_path)
    assert checked.returncode == 0, checked.stdout + checked.stderr
    result = result_of(dump_dom(page))
    assert result["done"] is True
    assert result["errors"] == []
    assert all(item["pass"] for item in result["expectations"])
    if kind != "interview":
        assert result["expectations"], "a starter with outputs states its expectations"
    assert result["outputs"]["uncovered"] == []


@needs_browser
@pytest.mark.parametrize("kind", KINDS)
def test_reply_matches_the_grammar(kind: str, tmp_path: Path) -> None:
    _, page = make_page(kind, tmp_path)
    lines = reply_of(dump_dom(page))
    assert lines[0].startswith(f"explorable {kind}-page built ")
    assert all(LINE.match(line) for line in lines), lines
    if kind == "decision":
        assert any(line.startswith("choice ") for line in lines)
    else:
        assert any(line.startswith("answer ") for line in lines)


@needs_browser
def test_a_wrong_expectation_fails(tmp_path: Path) -> None:
    def wrong(text: str) -> str:
        return text.replace("{ dbLoad: 12 }", "{ dbLoad: 13 }")

    _, page = make_page("learning", tmp_path, wrong)
    checked = cli("check", str(page), "--browser", cwd=tmp_path)
    assert checked.returncode == 1, checked.stdout + checked.stderr
    assert "FAIL" in checked.stdout


@needs_browser
def test_an_output_with_no_expectation_reads_unverified(tmp_path: Path) -> None:
    def add_output(text: str) -> str:
        extra = (
            '<p><output data-output="extra"></output></p>\n'
            '<script>explorable.onChange(() => explorable.show("extra", 7));</script>\n'
        )
        return text + extra

    _, page = make_page("learning", tmp_path, add_output)
    checked = cli("check", str(page), "--browser", cwd=tmp_path)
    assert checked.returncode == 0, checked.stdout + checked.stderr
    assert "UNVERIFIED" in checked.stdout and "extra" in checked.stdout
    assert "extra" in result_of(dump_dom(page))["outputs"]["uncovered"]


def test_NEGATIVE_CONTROL_the_reply_grammar_refuses_a_stray_line() -> None:
    assert LINE.match("input hit: unknown -> 80 %")
    assert LINE.match("choice D1: B drop it now")
    assert not LINE.match("my own line")
