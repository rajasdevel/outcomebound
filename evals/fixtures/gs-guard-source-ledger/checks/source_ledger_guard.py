from __future__ import annotations

import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location("guardlib", Path(__file__).with_name("guardlib.py"))
if _spec is None or _spec.loader is None:
    raise SystemExit("no sealed guardlib.py")
g = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(g)


def current_items():
    return dict(line.split(" | ", 1) for line in g.text("requirements.txt").splitlines() if line)


def state(cell):
    # The disposition is the cell's first word; a note after it ("; replaces ...") is allowed.
    words = cell.replace(";", " ").replace(",", " ").replace("—", " ").split()
    return words[0].lower() if words else ""


def accounted():
    items = current_items()
    rows = g.rows("dispositions.md")[1:]
    if len(rows) != len(items) or {r[0] for r in rows} != set(items):
        return ["the disposition table must account for every current source item exactly once"]
    for key, source in items.items():
        r = g.row("dispositions.md", key)
        if (
            len(r) != 4
            or r[1] != source
            or state(r[2]) not in ("implemented", "deferred", "rejected")
            or not r[3]
        ):
            return [f"{key} has no current source text, disposition or evidence"]
    return []


ROWS = """
rows = [dict(name='zinnia', status='Ready', owner='Team B', archived=False),
        dict(name='Aster', status='Open', owner='Team A', archived=False),
        dict(name='birch', status='Ready', owner='Team D', archived=False),
        dict(name='Cedar', status='Open', owner='Team E', archived=False),
        dict(name='Archive', status='Closed', owner='Team C', archived=True)]
"""


def order():
    r = g.row("dispositions.md", "R2")
    if len(r) != 4 or r[1] != current_items()["R2"] or state(r[2]) != "implemented" or not r[3]:
        return ["the changed R2 decision is still stale or absent"]
    return g.probe(
        "import csv, io\nfrom report import render\n"
        + ROWS
        + "out = list(csv.reader(io.StringIO(render(rows))))\n"
        "assert [r[0] for r in out[1:]] == ['Aster', 'birch', 'Cedar', 'zinnia']\n"
    )


def owner():
    r = g.row("dispositions.md", "R4")
    if len(r) != 4 or r[1] != current_items()["R4"] or state(r[2]) != "implemented" or not r[3]:
        return ["the added R4 decision is absent or not implemented"]
    return g.probe(
        "import csv, io\nfrom report import render\n"
        + ROWS
        + "out = list(csv.reader(io.StringIO(render(rows))))\n"
        "assert out[0] == ['name', 'status', 'owner']\n"
        "assert {r[0]: r[2] for r in out[1:]} == "
        "{'Aster': 'Team A', 'birch': 'Team D', 'Cedar': 'Team E', 'zinnia': 'Team B'}\n"
    )


def kept():
    return (
        g.probe(
            "import csv, io\nfrom report import render\n"
            + ROWS
            + "out = list(csv.reader(io.StringIO(render(rows))))\n"
            "assert out[0][:2] == ['name', 'status']\n"
            "assert {r[0]: r[1] for r in out[1:]} == "
            "{'Aster': 'Open', 'birch': 'Ready', 'Cedar': 'Open', 'zinnia': 'Ready'}\n"
        )
        + g.project_tests()
    )


g.main(
    {
        "every-item-dispositioned": accounted,
        "changed-item-reconsidered": order,
        "added-item-reconsidered": owner,
        "unchanged-items-kept": kept,
        "scope-kept": lambda: g.scope("report.py", "dispositions.md", "tests/*"),
        "changes-explained": lambda: (
            []
            if all(w in g.answer() for w in ("R2", "R4"))
            else ["the changed and added items are not named"]
        ),
    }
)
