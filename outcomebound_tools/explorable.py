"""`outcomebound explorable ...`: start, build and check an explorable, one HTML page that a
person opens from disk to explore a decision, learn a mechanism or answer questions.

What this module decides: the three subcommands and their options; that `new` writes a starter
source and never writes over a file; that `build` joins a source to the engine's shell, writes
over a page it built (the generator `meta` marks it) and refuses to write over any other file;
that `check` prints one overall verdict first, then the shell, hosts, parts and run verdicts; and
the exits: 0 when nothing fails (an UNVERIFIED is named); 1 for a FAIL or a refusal; 2 when a file
cannot be read or on a usage error.

What it does not decide: whether a page's content is right. It reads the source, the brief
document a decision names and the engine's templates (`build`), or the page and, with
`--browser`, the document the browser prints (`check`); it writes only `new`'s starter and
`build`'s page. Standard library only.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path

from outcomebound_tools import (
    decision_brief,
    decision_brief_html,
    explorable_browser,
    explorable_check,
    explorable_shell,
    explorable_source,
    paths,
    textio,
)
from outcomebound_tools.explorable_source import SOURCE_SUFFIX, SourceRefusal

NAME = "explorable"
DEFAULT_TIMEOUT = 60.0
_GENERATED = re.compile(r'<meta name="generator" content="outcomebound explorable [^"]*">')
_EPILOG = """\
A source is an HTML fragment named <name>.source.html: its first element is the header,
<script type="application/json" data-explorable>{"kind", "id", "title", "brief"}</script>
(schemas/explorable-source.schema.json; `brief`, a decision's only, is the brief document's path
inside the source's folder), then content sections and scripts. It holds no doctype, html, head,
body, meta, link, base, style, form, iframe, object or embed element, and no attribute that loads
or sends (src, href, xlink:href, srcset, srcdoc, action, formaction, poster, data, ping, cite,
background) holds anything but #fragment or a data: URL; an `a` with an https: href is a
citation, and build gives it rel and referrerpolicy. The page is <name>.html beside it.

new      writes the starter source of a kind, and for a decision briefs.json beside it where
         none exists. Never writes over a file.
build    joins the source to the shell. Reads the source, its brief document and the engine's
         templates/explorable/. Writes the page, over a page it built, and over no other file.
check    verdicts: shell (policy, generator, kind, stylesheet, runtime and pins equal the
         engine's; else `next: build again`), hosts, parts (a decision holds a brief; the other
         kinds a data-question), and with --browser run (no script error; each expectation
         passes; each output with no expectation reads UNVERIFIED). The page is run only where
         the first three pass. A pass never says that the page's content is right.

Exits: 0 when nothing fails, any UNVERIFIED named; 1 on a FAIL or a refusal; 2 when a file cannot
be read or on a usage error. Set SOURCE_DATE_EPOCH to make a build repeatable. The browser is
OUTCOMEBOUND_BROWSER, else google-chrome, chromium, chromium-browser, msedge or brave on PATH,
else an install folder; with none, or only Firefox or Safari, the run is UNVERIFIED.
"""


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="outcomebound explorable",
        description="Start, build and check an explorable page.",
        epilog=_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    commands = parser.add_subparsers(dest="command", required=True)
    made = commands.add_parser(
        "new",
        prog="outcomebound explorable new",
        help="write a starter source",
        description="Write a starter source of one kind. Never writes over a file.",
    )
    made.add_argument(
        "source", metavar="SOURCE", help=f"the new source, named <name>{SOURCE_SUFFIX}"
    )
    made.add_argument("--kind", required=True, choices=explorable_source.KINDS)
    made.add_argument("--id", dest="page_id", help="the page's id (default: from the file name)")
    made.add_argument("--title", help="the page's title (default: from the id)")
    built = commands.add_parser(
        "build",
        prog="outcomebound explorable build",
        help="join a source to the shell",
        description="Write <name>.html beside <name>.source.html.",
    )
    built.add_argument("source", metavar="SOURCE", help=f"the source, named <name>{SOURCE_SUFFIX}")
    checked = commands.add_parser(
        "check",
        prog="outcomebound explorable check",
        help="check a built page",
        description="Print the verdicts for a built page. Writes nothing.",
    )
    checked.add_argument("page", metavar="PAGE", help="the built page")
    checked.add_argument("--browser", action="store_true", help="also run the page headless")
    checked.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        metavar="SECONDS",
        help=f"how long the browser may take (default {DEFAULT_TIMEOUT:g})",
    )
    return parser


def _say(text: str) -> None:
    print(f"{NAME}: {text}", file=sys.stderr)


# new.


def _slug(name: str) -> str | None:
    found = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return found if re.fullmatch(r"[a-z][a-z0-9-]*", found) else None


def _starter(kind: str, page_id: str, title: str) -> str:
    text = explorable_shell.template(f"starters/{kind}.source.html")
    found = explorable_source.scan(text, source=True)
    if found.header_end is None or found.header_text is None:
        raise explorable_shell.ShellError(f"the {kind} starter has no header")
    header = json.loads(found.header_text)
    header.update(id=page_id, title=title)
    document = json.dumps(header, ensure_ascii=False).replace("</", "<\\/")
    opening = '<script type="application/json" data-explorable>'
    return f"{opening}\n{document}\n</script>" + text[found.header_end :]


def _write_new(path: Path, text: str) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def _new(options: argparse.Namespace) -> int:
    path = Path(options.source)
    name = explorable_source.page_name(path.name)
    if name is None:
        _say(f"the source's name ends in {SOURCE_SUFFIX}")
        return 2
    page_id = options.page_id or _slug(name[: -len(".html")])
    if not page_id or not re.fullmatch(r"[a-z][a-z0-9-]*", page_id):
        _say("give --id: lowercase letters, digits and hyphens, starting with a letter")
        return 2
    title = options.title or page_id.replace("-", " ").capitalize()
    if not title or re.search(r"[\r\n]", title):
        _say("the title is one line")
        return 2
    try:
        text = _starter(options.kind, page_id, title)
        brief = json.loads(explorable_source.scan(text, source=True).header_text or "{}").get(
            "brief"
        )
        companion = path.parent / brief if brief else None
        if path.exists() or path.is_symlink():
            _say(f"{path} exists; new never writes over a file")
            return 1
        if companion is not None and not (companion.exists() or companion.is_symlink()):
            _write_new(companion, explorable_shell.template("starters/decision.briefs.json"))
            print(f"{NAME}: wrote {companion}")
        _write_new(path, text)
    except (OSError, explorable_shell.ShellError) as error:
        _say(f"cannot write {path}: {error}")
        return 2
    print(f"{NAME}: wrote {path}")
    print(f"next: edit it, then `outcomebound explorable build {path}`")
    return 0


# build.


def _brief(header: dict[str, str], folder: Path) -> tuple[str, list[dict[str, object]]]:
    """The briefs' drawing and configuration; a refusal is a `SourceRefusal`."""

    where = header["brief"]
    try:
        document = paths.resolve_bounded(folder, where)
    except paths.PathError as error:
        raise SourceRefusal([explorable_source.Finding(1, f"brief: {error}")]) from error
    if not document.is_file():
        raise SourceRefusal(
            [explorable_source.Finding(1, f"the brief document {where} is missing")]
        )
    try:
        briefs, order = decision_brief.read_document(document)
    except ValueError as error:
        raise SourceRefusal([explorable_source.Finding(1, f"{where}: {error}")]) from error
    if not briefs:
        raise SourceRefusal([explorable_source.Finding(1, f"{where} holds no brief")])
    return decision_brief_html.render_html(briefs, order), decision_brief_html.config_briefs(briefs)


def _may_replace(target: Path) -> str | None:
    """Why `build` may not write `target`, or None."""

    if target.is_symlink() or (target.exists() and not target.is_file()):
        return f"{target} is not a regular file"
    if not target.exists():
        return None
    try:
        text = textio.read_text(target)
    except (OSError, UnicodeDecodeError):
        return f"{target} exists and is not a page this command built"
    return (
        None if _GENERATED.search(text) else f"{target} exists and is not a page this command built"
    )


def _write_page(target: Path, text: str) -> None:
    handle, name = tempfile.mkstemp(dir=target.parent, prefix=".explorable-", suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
        os.replace(name, target)
    except BaseException:
        Path(name).unlink(missing_ok=True)
        raise


def _build(options: argparse.Namespace) -> int:
    source = Path(options.source)
    name = explorable_source.page_name(source.name)
    if name is None:
        _say(f"the source's name ends in {SOURCE_SUFFIX}")
        return 2
    try:
        text = explorable_source.read_text(source)
    except (OSError, UnicodeDecodeError) as error:
        _say(f"cannot read {source}: {error}")
        return 2
    try:
        parsed = explorable_source.parse_source(text)
        briefs_html = ""
        briefs: list[dict[str, object]] = []
        if parsed.header["kind"] == "decision":
            briefs_html, briefs = _brief(parsed.header, source.resolve().parent)
        page = explorable_shell.build_page(
            parsed.header,
            parsed.content,
            briefs_html,
            briefs,
            explorable_shell.built_time(),
        )
    except SourceRefusal as refused:
        for item in refused.findings:
            _say(f"{source}:{item.line}: {item.text}")
        return 1
    except explorable_shell.ShellError as error:
        _say(str(error))
        return 2
    target = source.parent / name
    why = _may_replace(target)
    if why:
        _say(f"refused: {why}")
        return 1
    try:
        _write_page(target, page)
    except OSError as error:
        _say(f"cannot write {target}: {error}")
        return 2
    print(f"{NAME}: wrote {target}")
    print(f"next: `outcomebound explorable check {target}`")
    return 0


# check.


def _print(page: Path, verdicts: list[explorable_check.Verdict]) -> None:
    print(f"{NAME} check: {explorable_check.overall(verdicts)} {page}")
    for item in verdicts:
        print(f"{item.name}: {item.status} {item.summary}")
        for line in item.details:
            print(f"  {line}")
    print(
        "note: a pass says the page is the engine's shell plus your content, with the parts its "
        "kind needs; it never says the content, the options or an output with no expectation "
        "is right"
    )


def _run_verdict(page: Path, timeout: float) -> explorable_check.Verdict:
    browser, how = explorable_browser.find_browser()
    if browser is None:
        return explorable_check.not_run(how)
    ran = explorable_browser.run_page(browser, page, timeout)
    if ran.document is None:
        return explorable_check.not_run(ran.reason)
    result, reason = explorable_browser.parse_result(ran.document)
    if result is None:
        return explorable_check.no_result(reason)
    return explorable_check.run(result)


def _check(options: argparse.Namespace) -> int:
    page = Path(options.page)
    try:
        text = textio.read_text(page)
    except (OSError, UnicodeDecodeError) as error:
        _say(f"cannot read {page}: {error}")
        return 2
    first, found = explorable_check.shell(text)
    verdicts = [first]
    if found is None:
        verdicts += [
            explorable_check.Verdict(
                "hosts", explorable_check.UNVERIFIED, "needs the shell to match"
            ),
            explorable_check.Verdict(
                "parts", explorable_check.UNVERIFIED, "needs the shell to match"
            ),
        ]
    else:
        kind = html_kind(found)
        verdicts += [explorable_check.hosts(found), explorable_check.parts(kind, found)]
    if not options.browser:
        verdicts.append(explorable_check.not_run("--browser was not given"))
    elif any(item.status != explorable_check.PASS for item in verdicts):
        verdicts.append(explorable_check.not_run("the shell, hosts and parts do not all pass"))
    else:
        verdicts.append(_run_verdict(page, options.timeout))
    _print(page, verdicts)
    return 1 if explorable_check.FAIL in {item.status for item in verdicts} else 0


def html_kind(found: explorable_shell.Parts) -> str:
    """The kind a page that matched the frame holds."""

    return found.values["kind"][0]


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    options = parser.parse_args(argv)
    if options.command == "check" and not options.timeout > 0:
        parser.error("--timeout is a number of seconds above 0")
    if options.command == "new":
        return _new(options)
    if options.command == "build":
        return _build(options)
    return _check(options)


if __name__ == "__main__":
    raise SystemExit(main())
