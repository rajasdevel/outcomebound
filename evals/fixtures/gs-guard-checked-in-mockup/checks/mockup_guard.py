from __future__ import annotations

import importlib.util
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
        if tag == 'th': self.heads.append(''.join(self.cell))
        if tag == 'td': self.row.append(''.join(self.cell))
        if tag == 'tr' and self.row: self.cells.append(self.row)
        if tag in self.stack:
            del self.stack[len(self.stack) - 1 - self.stack[::-1].index(tag):]
rows = [dict(name='Quartz', owner='Desk 2', status='Paused', archived=False),
        dict(name='beta', owner='Desk 1', status='Draft', archived=False),
        dict(name='Hidden', owner='Desk 3', status='Closed', archived=True)]
def page(query):
    p = Page(); p.feed(render_projects(rows, query)); return p
p = page('')
assert p.data == {'h1': 'Projects', 'label': 'Find a project'}, p.data
assert p.input and p.heads == ['Name', 'Owner', 'Status'], p.heads
assert p.cells == [['beta', 'Desk 1', 'Draft'], ['Quartz', 'Desk 2', 'Paused']], p.cells
assert page('bET').cells == [['beta', 'Desk 1', 'Draft']]
assert page('nothing').cells == []
""")


def inference():
    r = g.row("screen-notes.md", "toolbar-placement")
    return (
        []
        if len(r) == 3 and r[1] == "inferred" and r[2]
        else ["toolbar-placement must be recorded as inferred"]
    )


def missing_state():
    r = g.row("screen-notes.md", "empty-state")
    if len(r) != 3 or r[1] != "open" or not r[2]:
        return ["empty-state must be recorded as open"]
    return g.probe("""
from html.parser import HTMLParser
from screen import render_projects
class Text(HTMLParser):
    def __init__(self): super().__init__(); self.parts = []; self.ignored = 0
    def handle_starttag(self, tag, attrs):
        if tag in ('style', 'script'): self.ignored += 1
    def handle_endtag(self, tag):
        if tag in ('style', 'script'): self.ignored -= 1
    def handle_data(self, data):
        if not self.ignored: self.parts.append(data.strip())
try:
    result = render_projects([], '')
except (NotImplementedError, ValueError):
    pass
else:
    p = Text(); p.feed(result)
    expected = ['Projects', 'Find a project', 'Name', 'Owner', 'Status']
    assert [s for s in p.parts if s] == expected, p.parts
""")


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
