#!/usr/bin/env python3
"""Build the examplectl documentation site: each content/<page>.md becomes site/<page>.html.

    python3 build.py              write site/
    python3 build.py --out DIR    write DIR instead
    python3 build.py --check      build to a temporary folder; fail if site/ differs from it
                                  or a page links to a page that does not exist

A page may include a snippet with {{> name}} (content/_snippets/name.md) and use a value from
content/_data.json with {{key}}. The Markdown is a small subset: headings, paragraphs, bullet
lists, fenced code, inline code and links.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import tempfile
from pathlib import Path
from string import Template

ROOT = Path(__file__).resolve().parent
CONTENT = ROOT / "content"
SITE = ROOT / "site"
TEMPLATE = ROOT / "templates" / "page.html"
INCLUDE = re.compile(r"\{\{>\s*([\w-]+)\s*\}\}")
VALUE = re.compile(r"\{\{\s*(\w+)\s*\}\}")
LINK = re.compile(r'href="([^"#]+\.html)"')
NAV = (
    ("index", "Home"),
    ("install", "Install"),
    ("quickstart", "Quickstart"),
    ("faq", "FAQ"),
    ("migrating-from-2", "Migrating from 2.x"),
    ("changelog", "Changelog"),
)


def expand(text: str, data: dict[str, str]) -> str:
    """The page with its snippets included and its values filled in."""

    def snippet(found: re.Match[str]) -> str:
        path = CONTENT / "_snippets" / f"{found[1]}.md"
        return path.read_text(encoding="utf-8").strip("\n")

    return VALUE.sub(lambda found: str(data[found[1]]), INCLUDE.sub(snippet, text))


def inline(text: str) -> str:
    text = html.escape(text, quote=False)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    return re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)


def blocks(markdown: str) -> list[list[str]]:
    """The page's blocks: runs of lines split by blank lines, a fenced block kept whole."""

    found: list[list[str]] = []
    current: list[str] = []
    fenced = False
    for line in markdown.splitlines():
        if line.startswith("```"):
            fenced = not fenced
        if not line.strip() and not fenced:
            if current:
                found.append(current)
            current = []
            continue
        current.append(line)
    if current:
        found.append(current)
    return found


def render_block(lines: list[str]) -> str:
    first = lines[0]
    if first.startswith("```"):
        code = "\n".join(html.escape(line, quote=False) for line in lines[1:-1])
        return f"<pre><code>{code}</code></pre>"
    heading = re.match(r"(#{1,3}) (.*)", first)
    if heading and len(lines) == 1:
        level = len(heading[1])
        return f"<h{level}>{inline(heading[2])}</h{level}>"
    if all(line.startswith("- ") for line in lines):
        items = "".join(f"<li>{inline(line[2:])}</li>" for line in lines)
        return f"<ul>{items}</ul>"
    return f"<p>{inline(' '.join(lines))}</p>"


def page(name: str, data: dict[str, str]) -> str:
    markdown = expand((CONTENT / f"{name}.md").read_text(encoding="utf-8"), data)
    title = next(
        (line[2:] for line in markdown.splitlines() if line.startswith("# ")), name.title()
    )
    nav = " | ".join(f'<a href="{target}.html">{label}</a>' for target, label in NAV)
    body = "\n".join(render_block(lines) for lines in blocks(markdown))
    template = Template(TEMPLATE.read_text(encoding="utf-8"))
    return template.substitute(title=html.escape(title), nav=nav, body=body)


def build(out: Path) -> list[Path]:
    """Write every page into `out`; the paths written."""

    data = json.loads((CONTENT / "_data.json").read_text(encoding="utf-8"))
    out.mkdir(parents=True, exist_ok=True)
    written = []
    for source in sorted(CONTENT.glob("*.md")):
        target = out / f"{source.stem}.html"
        target.write_text(page(source.stem, data), encoding="utf-8")
        written.append(target)
    return written


def problems(built: Path) -> list[str]:
    """How site/ differs from a fresh build in `built`, and each broken link."""

    fresh = {path.name: path.read_bytes() for path in built.glob("*.html")}
    served = {path.name: path.read_bytes() for path in SITE.glob("*.html")} if SITE.is_dir() else {}
    found = [f"site/{name} is not built from content/" for name in sorted(set(served) - set(fresh))]
    found += [f"site/{name} is missing" for name in sorted(set(fresh) - set(served))]
    found += [
        f"site/{name} is out of date: run `make build`"
        for name in sorted(set(fresh) & set(served))
        if fresh[name] != served[name]
    ]
    for name, text in sorted(fresh.items()):
        for target in LINK.findall(text.decode("utf-8")):
            if target not in fresh:
                found.append(f"{name} links to {target}, which does not exist")
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the examplectl documentation site.")
    parser.add_argument("--out", type=Path, help="write the site here instead of site/")
    parser.add_argument("--check", action="store_true", help="check that site/ is current")
    args = parser.parse_args(argv)
    if args.check:
        with tempfile.TemporaryDirectory() as scratch:
            build(Path(scratch))
            found = problems(Path(scratch))
        for problem in found:
            print(problem, file=sys.stderr)
        print("site check: FAIL" if found else "site check: PASS")
        return 1 if found else 0
    written = build(args.out or SITE)
    print(f"built {len(written)} pages into {args.out or 'site'}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
