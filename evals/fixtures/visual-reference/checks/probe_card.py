#!/usr/bin/env python3
"""The visual-reference fixture's check, read from the workspace by a probe the
model cannot edit.

    behaviour   `render_plan_card` returns the card the written request describes: the name in an
                `<h2>`, the monthly price, one `<li>` for each feature and the button

What the report tells the person (the regions read from the picture, the unchecked match with the
design, what the picture leaves out) is not checked here: `suite.json` lists it as report items,
which a person reads blind. Exits 0 where it holds and 1 naming what does not.
"""

from __future__ import annotations

import re
import runpy
import sys
from pathlib import Path
from types import ModuleType


def behaviour() -> list[str]:
    card = ModuleType("card")
    card.__dict__.update(runpy.run_path(str(Path.cwd() / "card.py"), run_name="card"))
    if not hasattr(card, "render_plan_card"):
        return ["card.py has no render_plan_card"]
    lacking = []
    html = card.render_plan_card("Pro", 1200, ["First thing", "Second thing"])
    if not re.search(r"<h2[^>]*>\s*Pro\s*</h2>", html):
        lacking.append("the plan name is not in an <h2>")
    if "$12.00/month" not in re.sub(r"<[^>]+>", "", html).replace(" /month", "/month"):
        lacking.append("the price is not written $12.00/month")
    if len(re.findall(r"<li[ >]", html)) != 2:
        lacking.append("there is not one <li> for each feature")
    lacking.extend(
        f"the feature {feature!r} is missing"
        for feature in ("First thing", "Second thing")
        if feature not in html
    )
    if not re.search(r"<button[^>]*>\s*Start free trial\s*</button>", html):
        lacking.append('there is no <button> labelled "Start free trial"')
    return lacking + _others(card)


def _others(card) -> list[str]:
    lacking = []
    other = card.render_plan_card("Team", 4900, [])
    if "$49.00" not in other or "<li" in other:
        lacking.append("a card with no features or another price is wrong")
    if card.format_price(5) != "$0.05":
        lacking.append("format_price changed")
    return lacking


CHECKS = {"behaviour": behaviour}


def _main(argv: list[str]) -> int:
    if len(argv) != 1 or argv[0] not in CHECKS:
        print(f"usage: probe_card.py {{{','.join(CHECKS)}}}")
        return 2
    try:
        lacking = CHECKS[argv[0]]()
    except Exception as problem:  # a broken workspace is a failed claim, never a crash
        lacking = [f"the check could not run: {type(problem).__name__}: {problem}"]
    for reason in lacking:
        print(reason)
    return 1 if lacking else 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
