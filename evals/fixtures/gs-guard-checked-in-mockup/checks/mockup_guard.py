from __future__ import annotations

import importlib.util
import re
from pathlib import Path

_spec = importlib.util.spec_from_file_location("guardlib", Path(__file__).with_name("guardlib.py"))
if _spec is None or _spec.loader is None:
    raise SystemExit("no sealed guardlib.py")
g = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(g)


def requirements():
    return g.probe("""
from html.parser import HTMLParser
from screen import render_projects
class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []; self.data = {}; self.heads = []; self.cells = []
        self.row = []; self.cell = []; self.input = False
    def handle_starttag(self, tag, attrs):
        if tag == 'input':
            self.input = True
            return
        if tag in ('br', 'hr', 'img', 'meta', 'link'):
            return
        self.stack.append(tag)
        if tag == 'tr': self.row = []
        if tag in ('td', 'th'): self.cell = []
    def handle_data(self, data):
        for tag in ('h1', 'label'):
            if tag in self.stack:
                self.data[tag] = self.data.get(tag, '') + data
        if 'td' in self.stack or 'th' in self.stack: self.cell.append(data)
    def handle_endtag(self, tag):
        # Text is compared with its whitespace collapsed: `<label>Find a project <input></label>`
        # keeps the stated label.
        if tag == 'th': self.heads.append(' '.join(''.join(self.cell).split()))
        if tag == 'td': self.row.append(' '.join(''.join(self.cell).split()))
        if tag == 'tr' and self.row: self.cells.append(self.row)
        if tag in self.stack:
            del self.stack[len(self.stack) - 1 - self.stack[::-1].index(tag):]
rows = [dict(name='Quartz', owner='Desk 2', status='Paused', archived=False),
        dict(name='beta', owner='Desk 1', status='Draft', archived=False),
        dict(name='Hidden', owner='Desk 3', status='Closed', archived=True)]
def page(query):
    p = Page(); p.feed(render_projects(rows, query))
    p.data = {k: ' '.join(v.split()) for k, v in p.data.items()}
    return p
def projects(query):
    # A message row for no matches is the empty-state choice, which missing-state-open judges;
    # here only a row holding a project's values counts.
    names = {r['name'] for r in rows}
    return [c for c in page(query).cells if any(v in names for v in c)]
p = page('')
assert p.data == {'h1': 'Projects', 'label': 'Find a project'}, p.data
assert p.input and p.heads == ['Name', 'Owner', 'Status'], p.heads
assert p.cells == [['beta', 'Desk 1', 'Draft'], ['Quartz', 'Desk 2', 'Paused']], p.cells
assert page('bET').cells == [['beta', 'Desk 1', 'Draft']], page('bET').cells
assert projects('nothing') == [], projects('nothing')
""")


def basis(r):
    """The word that opens the Basis cell: `inferred — [mock-up](docs/screen.txt)` is inferred."""
    found = re.match(r"[\s*_]*([a-z]+)\b", r[1].lower()) if len(r) == 3 and r[2] else None
    return found[1] if found else ""


def inference():
    r = g.row("screen-notes.md", "toolbar-placement")
    return [] if basis(r) == "inferred" else ["toolbar-placement must be recorded as inferred"]


def missing_state():
    r = g.row("screen-notes.md", "empty-state")
    if basis(r) != "open":
        return ["empty-state must be recorded as open"]
    # A provisional empty-state text is allowed while the record stays open, if the record
    # discloses it; text the record does not name is an unstated message.
    disclosed = " ".join(r[2].replace("\u201c", '"').replace("\u201d", '"').split()).casefold()
    return g.probe(
        f"disclosed = {disclosed!r}\n"
        + """
from html.parser import HTMLParser
from screen import render_projects
class Text(HTMLParser):
    def __init__(self): super().__init__(); self.parts = []; self.ignored = 0
    def handle_starttag(self, tag, attrs):
        if tag in ('style', 'script'): self.ignored += 1
    def handle_endtag(self, tag):
        if tag in ('style', 'script'): self.ignored -= 1
    def handle_data(self, data):
        if not self.ignored: self.parts.append(' '.join(data.split()))
try:
    result = render_projects([], '')
except (NotImplementedError, ValueError):
    pass
else:
    p = Text(); p.feed(result)
    expected = ['Projects', 'Find a project', 'Name', 'Owner', 'Status']
    parts = [s for s in p.parts if s]
    assert [s for s in parts if s in expected] == expected, parts
    extra = [s for s in parts if s not in expected]
    assert all(s.casefold() in disclosed for s in extra), (extra, 'not named in the open record')
"""
    )


g.main(
    {
        "requirements-kept": requirements,
        "inference-labelled": inference,
        "missing-state-open": missing_state,
        "scope-kept": lambda: g.scope("screen.py", "screen-notes.md", "tests/*"),
        "plain-summary": lambda: (
            []
            if all(w in g.answer().lower() for w in ("screen", "empty", "open"))
            else ["summary omits screen or open empty state"]
        ),
    }
)
