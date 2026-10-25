#!/usr/bin/env python3
"""The checks of v2-rp-report-route, read from the workspace by a script the model cannot edit.

The prompt states a small interface, and every claim reads the page only through it and through
what the page does when it runs: two `<input type="number">` elements with the ids `requests`
(millions of requests a month) and `storage` (GB), for each plan its monthly total in dollars in
the one element `total-<plan>` (the plan's name in lower case), one HTML file with no companion
files, the scripts and styles the report needs kept inline (optional network libraries allowed where
the report works without them), and, where recalculation needs a button, that button with the id
`calculate`. The check guesses no meaning from the page's words, its layout or its controls.

    page        reports/hosting.html is there, is an HTML document, and keeps its scripts and
                styles in itself: a script `src` or a stylesheet `href` that names a file (not a
                network address) fails it
    numbers     the page runs in a headless Chromium-family browser with the network denied (every
                host fails to resolve and every connection goes to an unreachable proxy, loopback
                included) and a content policy that allows inline script and style only, with a
                driver of this check's own put first in the page. Before it drives anything, both
                inputs must be inputs of type number that are shown, enabled and not read-only.
                The driver sets `requests` and `storage` to several values (some below a plan's
                included allowance), dispatching `input` and `change` on each, and clicks the
                element `calculate` after both where the page has one and it is shown and
                enabled. It reads the text of `#total-<plan>` only, and only while the element is
                shown (an element that is hidden, off the screen or clear reads as missing). Holds
                when the page starts at the expected traffic, and, at every value, each total's
                text holds one signed number, written to the cent, equal to the plan's monthly
                cost as this check works it out from the seed's plans (plans.json in this
                folder), never from the page. A missing id, an input a reader cannot use, a
                hidden total, a total that does not change, a negative total or a wrong total
                fails it
    local       the page reaches the network by no act of its own: no navigation away from its
                document (a page that navigates away, or replaces itself, before the driver
                finishes fails), no window opened, no form action or ping to an address, no
                refresh to an address. It does not ask whether the report works: `numbers` runs
                with the network denied, so it grades "works with the network off", and a page
                whose totals need a network library fails there. A load that the denial blocks
                (a chart library, say) is recorded as an `observed:` line and never changes the
                verdict
    scope       nothing differs from the seed but files under reports/ and .agents/

`numbers` and `local` need a browser (`outcomebound_tools.explorable_browser.find_browser`).
Without one, `numbers` prints `unjudged:` with the reason and exits 3; so does `local`,
since it runs the same browser. A page that is missing, that the browser cannot print or that
does not finish its work is a failure. Each mode exits 0 where it holds and 1 naming what does not.
`numbers` also prints
`observed:` lines (the page's rendered text and its controls in every state the driver put it in:
the start, each value, the start again) that never change a verdict: a person reads them beside
the answer for the report item. A text past the cap is cut with the cut marked on its line and in
a line of its own. Nothing here writes to the workspace: the page runs from a copy in a folder of
this check's own, and no other file is copied with it. Limits: a total that takes longer than
about a third of a second to settle, an animated total, a window opened by script and a
navigation that happens only after the driver ends are not seen; a minus sign set apart from its
figure by a space is not read as a sign; a script or style in a file is found by its element or
`@import`, not by a script that creates one.
"""

from __future__ import annotations

import difflib
import fnmatch
import json
import os
import re
import subprocess
import sys
import tempfile
from decimal import ROUND_HALF_UP, Decimal
from html.parser import HTMLParser
from pathlib import Path

TIMEOUT = 90
PAGE = Path("reports/hosting.html")
HERE = Path(__file__).resolve().parent
ALLOWED = ("reports/*", ".agents/*")
NETWORK = re.compile(r"^\s*(?:https?:|ftp:|wss?:|//)", re.IGNORECASE)
LOADING = {"src", "href", "srcset", "action", "formaction", "poster", "data", "background",
           "xlink:href", "ping"}  # fmt: skip
# Attributes that send the reader or the page's data away; any other network load is an extra
# that the page may lack if its report still works.
SENDS = {"action", "formaction", "ping"}
CSS_NETWORK = re.compile(r"url\(\s*['\"]?\s*(?:https?:|//)", re.IGNORECASE)
CSS_IMPORT = re.compile(r"@import\s*(?:url\(\s*)?['\"]?\s*([^'\")\s;]+)", re.IGNORECASE)
# Put first in the copy's head: nothing loads from the network, inline script and style run.
POLICY = (
    '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; '
    "script-src 'unsafe-inline' 'unsafe-eval'; style-src 'unsafe-inline'; img-src data: blob:; "
    "font-src data:; form-action 'none'\">"
)
# Browser flags that keep the page off the network: no host resolves, and every connection,
# loopback included, goes to a proxy nothing listens on.
DENY = (
    "--host-resolver-rules=MAP * ~NOTFOUND",
    "--proxy-server=http://127.0.0.1:9",
    "--proxy-bypass-list=<-loopback>",
    "--disable-background-networking",
)
NUMBER = re.compile(r"(?<![\d.])\d{1,3}(?:,\d{3})+(?:\.\d+)?(?![\d])|(?<![\d.,])\d+(?:\.\d+)?")
# A minus sign (hyphen-minus or minus sign) set directly before a figure or before its currency
# symbol, or directly after the symbol: "-$37.30", "$-37.30", "-37.30".
# Accounting notation: a figure, with its currency symbol, between parentheses is negative.
OPENING = re.compile(r"\(\s*(?:US)?\$?\s*$")
CLOSING = re.compile(r"\s*\)")
NEGATIVE = re.compile(r"(?:(?:^|[^\w.])[-\u2212](?:US)?\$?|\$[-\u2212])$")
# The longest page text, in characters, that is kept whole as evidence for the reading.
TEXT_CAP = 50000
CONTROLS_CAP = 6000
RESULT_ID = "ob-grader-result"
# The values the driver tries, as (millions of requests, GB). The first is the expected traffic;
# the others move one of the two alone, or both, and some sit under a plan's included allowance
# (Starter: 1 million and 25 GB; Team: 2 million and 50 GB; Metered: none). Consecutive values
# differ in every plan's total but Team's, so a total that did not follow shows.
SCENARIOS = ((2.4, 80), (0.5, 10), (1.5, 30), (2.4, 10), (0.5, 80), (5, 200), (0, 0))
SETTLE_MS = 300

# The driver, run in the page after it loads. It writes one JSON element and reads nothing of the
# page but the ids of the interface, and the page's rendered text and controls after every state
# it put the page in.
DRIVER = r"""
<script>
(function () {
  var CONFIG = __CONFIG__;
  var result = {violations: [], opened: [], inputs: {}, initial: null, runs: [], clicks: 0,
                states: [], error: null};
  document.addEventListener("securitypolicyviolation", function (event) {
    result.violations.push(event.violatedDirective + " " + event.blockedURI);
  });
  window.open = function (address) { result.opened.push(String(address)); return null; };
  function tick(ms) { return new Promise(function (done) { setTimeout(done, ms); }); }
  function squash(text) { return String(text || "").replace(/\s+/g, " ").trim(); }
  // Whether an element is drawn where a reader can see it: it and its ancestors are not clear,
  // it is not inside a closed <details>, it has a box (display none has none), its visibility
  // is not hidden, and it is not wholly off the left or the top of the page.
  function shown(el) {
    var summary = el.closest("summary");
    for (var up = el; up && up.nodeType === 1; up = up.parentElement) {
      var style = getComputedStyle(up);
      if (style.opacity === "0") { return false; }
      if (up.tagName === "DETAILS" && !up.open && !(summary && summary.parentElement === up)) {
        return false;
      }
    }
    var own = getComputedStyle(el);
    if (own.visibility === "hidden" || own.visibility === "collapse") { return false; }
    var boxes = Array.prototype.filter.call(el.getClientRects(), function (box) {
      return (box.width > 0 || box.height > 0) &&
        box.right + window.scrollX > 0 && box.bottom + window.scrollY > 0;
    });
    return boxes.length > 0;
  }
  function slug(plan) { return plan.toLowerCase(); }
  function reading(id) {
    var el = document.getElementById(id);
    if (!el) { return {state: "missing", tag: ""}; }
    var tag = el.tagName.toLowerCase();
    if (!shown(el)) { return {state: "hidden", tag: tag}; }
    var field = tag === "input" || tag === "textarea";
    var text = field ? el.value : (el.innerText || el.textContent);
    return {state: "shown", tag: tag, text: squash(text)};
  }
  function totals() {
    var found = {};
    CONFIG.plans.forEach(function (plan) { found[plan] = reading("total-" + slug(plan)); });
    return found;
  }
  function key() {
    return JSON.stringify(totals());
  }
  function setValue(el, value) {
    el.value = String(value);
    el.dispatchEvent(new Event("input", {bubbles: true}));
    el.dispatchEvent(new Event("change", {bubbles: true}));
  }
  // Wait until the totals differ from `before`, up to the settle time, then a moment more.
  async function changed(before) {
    for (var spent = 0; spent < CONFIG.settle; spent += 30) {
      if (key() !== before) { await tick(60); return true; }
      await tick(30);
    }
    return key() !== before;
  }
  // What a reader would meet in an input: whether it is an input, of which type, shown, enabled
  // and editable.
  function describe(el) {
    if (!el) { return null; }
    return {tag: el.tagName.toLowerCase(), type: String(el.type || ""), shown: shown(el),
            disabled: el.matches(":disabled"), readonly: !!el.readOnly};
  }
  function usable(info) {
    return !!info && info.tag === "input" && info.type === "number" && info.shown &&
      !info.disabled && !info.readonly;
  }
  function controls() {
    return Array.prototype.filter.call(document.querySelectorAll(
      "button, input, select, textarea, summary, [role=button], a[href]"), function (el) {
      return el.type !== "hidden" && shown(el);
    }).map(function (el) {
      var push = /^(button|submit|reset)$/.test(el.type || "");
      var label = squash([el.innerText, push ? el.value : "", el.getAttribute("aria-label"),
                          el.getAttribute("placeholder"), el.getAttribute("title")].join(" "));
      var named = Array.prototype.map.call(el.labels || [], function (item) {
        return squash(item.innerText);
      }).join(" ");
      var flags = ["disabled", "readOnly", "checked"].filter(function (name) {
        return name === "disabled" ? el.matches(":disabled") : el[name] === true;
      }).map(function (name) { return name.toLowerCase(); });
      return (el.tagName.toLowerCase() + (el.type ? "[" + el.type + "]" : "") + " " +
              squash(named + " " + label) + (flags.length ? " (" + flags.join(", ") + ")" : ""))
        .trim();
    });
  }
  // The rendered text and the controls now, kept under the name of the state the page is in.
  function snapshot(label) {
    result.states.push({label: label, text: squash(document.body.innerText),
                        controls: controls()});
  }
  async function main() {
    await tick(80);
    var first = document.getElementById("requests"), second = document.getElementById("storage");
    result.inputs.requests = describe(first);
    result.inputs.storage = describe(second);
    result.initial = {totals: totals(), values: [first && first.value, second && second.value]};
    snapshot("the start");
    if (!usable(result.inputs.requests) || !usable(result.inputs.storage)) { return; }
    var last = [Number(first.value), Number(second.value)];
    for (var at = 0; at < CONFIG.scenarios.length; at += 1) {
      var before = key();
      setValue(first, CONFIG.scenarios[at][0]);
      setValue(second, CONFIG.scenarios[at][1]);
      var applied = [Number(first.value), Number(second.value)];
      var same = applied[0] === last[0] && applied[1] === last[1];
      // The page's own way to take the values is the button the prompt names: `calculate`.
      var go = document.getElementById("calculate");
      if (go && !go.matches(":disabled") && shown(go)) { go.click(); result.clicks += 1; }
      if (!same) { await changed(before); }
      last = applied;
      result.runs.push({scenario: at, applied: applied, totals: totals()});
      snapshot(applied[0] + " million requests and " + applied[1] + " GB");
    }
    var back = key();
    setValue(first, result.initial.values[0]);
    setValue(second, result.initial.values[1]);
    await changed(back);
    snapshot("the starting values again");
  }
  function finish() {
    var element = document.createElement("script");
    element.type = "application/json";
    element.id = "__RESULT_ID__";
    element.textContent = JSON.stringify(result).replace(/</g, "\\u003c");
    document.body.appendChild(element);
  }
  window.addEventListener("load", function () {
    main().catch(function (problem) { result.error = String(problem); }).then(finish);
  });
})();
</script>
"""


def git(*arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments], capture_output=True, text=True, timeout=TIMEOUT, encoding="utf-8"
    ).stdout


def seed() -> str:
    return (
        os.environ.get("OUTCOMEBOUND_SEED_SHA")
        or git("rev-parse", "--verify", "refs/tags/seed^{commit}").strip()
    )


def facts() -> dict:
    return json.loads((HERE / "plans.json").read_text(encoding="utf-8"))


def cost(plan: dict, requests: float, storage: float) -> Decimal:
    """One plan's monthly cost at `requests` million requests and `storage` GB, in dollars to the
    cent, worked out in decimal."""

    def dec(value: float) -> Decimal:
        return Decimal(str(value))

    total = (
        dec(plan["monthly_fee"])
        + max(Decimal(0), dec(requests) - dec(plan["included_requests_millions"]))
        * dec(plan["per_extra_million"])
        + max(Decimal(0), dec(storage) - dec(plan["included_storage_gb"]))
        * dec(plan["per_extra_gb"])
    )
    return total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def element_id(plan: str) -> str:
    return f"total-{plan.lower()}"


def read_total(text: str) -> tuple[Decimal | None, str]:
    """The signed amount an element's text shows, and why it is none: the text must hold one
    number, written to the cent. A minus sign before the figure or its currency symbol, or the
    figure between parentheses (accounting notation), makes it negative; an opening parenthesis
    without its closing one is not read as an amount."""

    text = text or ""
    found = list(NUMBER.finditer(text))
    if not found:
        return None, "shows no number"
    if len(found) > 1:
        return None, f"shows {len(found)} numbers, not the one total"
    figure = found[0].group().replace(",", "")
    if not re.fullmatch(r"\d+\.\d{2}", figure):
        return None, f"shows {found[0].group()}, not a total to the cent"
    amount = Decimal(figure)
    before, after = text[: found[0].start()], text[found[0].end() :]
    if OPENING.search(before):
        if not CLOSING.match(after):
            return None, "shows an opening parenthesis before the figure and no closing one"
        return -amount, ""
    return (-amount if NEGATIVE.search(before) else amount), ""


class _Reader(HTMLParser):
    """The start tags' attributes and the text of each style."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tags: list[tuple[str, dict[str, str]]] = []
        self.styles: list[str] = []
        self._style = False
        self._buffer: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.append((tag, {name.lower(): value or "" for name, value in attrs}))
        if tag == "style":
            self._style, self._buffer = True, []

    def handle_endtag(self, tag: str) -> None:
        if tag == "style" and self._style:
            self.styles.append("".join(self._buffer))
            self._style = False

    def handle_data(self, data: str) -> None:
        if self._style:
            self._buffer.append(data)


def read(text: str) -> _Reader:
    reader = _Reader()
    reader.feed(text)
    reader.close()
    return reader


def _loads(name: str, value: str) -> bool:
    """Whether the attribute `name` with `value` loads from the network."""

    if name == "srcset":
        parts = [part.split()[0] for part in value.split(",") if part.split()]
        return any(NETWORK.match(part) for part in parts)
    return bool(NETWORK.match(value))


def _separate(tag: str, values: dict[str, str]) -> str:
    """The file of this checkout's own that a script or style element names, else nothing: a
    script `src` or a stylesheet `href` that is neither a network address nor inline data."""

    if tag == "script":
        name = "src"
    elif tag == "link" and "stylesheet" in values.get("rel", "").lower().split():
        name = "href"
    else:
        return ""
    value = values.get(name, "").strip()
    if not value or NETWORK.match(value) or value.lower().startswith("data:"):
        return ""
    return f"<{tag} {name}> names the file {value[:100]}"


def markup() -> dict[str, list[str]]:
    """What the page's markup names, in three kinds: `separate`, a script or style kept in a file
    beside the page; `sends`, what sends the reader or the page's data away when it is used (a
    refresh, a form action, a ping); `optional`, any other load from the network, which the page
    may lack if its report still works."""

    reader = read(PAGE.read_text(encoding="utf-8", errors="replace"))
    found: dict[str, list[str]] = {"separate": [], "sends": [], "optional": []}
    for tag, values in reader.tags:
        if separate := _separate(tag, values):
            found["separate"].append(separate)
        for name, value in values.items():
            if name in LOADING and not (tag == "a" and name == "href") and _loads(name, value):
                kind = "sends" if name in SENDS else "optional"
                found[kind].append(f"<{tag} {name}> loads {value[:100]}")
        if tag == "meta" and values.get("http-equiv", "").lower() == "refresh":
            found["sends"].append("a <meta> refresh")
        if CSS_NETWORK.search(values.get("style", "")):
            found["optional"].append(f"a style attribute of <{tag}> loads from the network")
    for body in reader.styles:
        if CSS_NETWORK.search(body):
            found["optional"].append("a style element loads from the network")
        for address in CSS_IMPORT.findall(body):
            kind = "optional" if NETWORK.match(address) else "separate"
            found[kind].append(f"a style element imports {address[:100]}")
    return found


def page() -> list[str]:
    if not PAGE.is_file():
        return [f"{PAGE} is not there"]
    text = PAGE.read_text(encoding="utf-8", errors="replace")
    if not read(text).tags or not re.search(r"<(?:html|body|!doctype)", text, re.I):
        return [f"{PAGE} is not an HTML document"]
    return [
        f"{line}: deliver one HTML file with no companion files, the scripts and styles the "
        "report needs kept inline"
        for line in markup()["separate"]
    ]


def _browser() -> tuple[str | None, str]:
    """The browser, found and tried on a page of this check's own, or None and why not."""

    from outcomebound_tools import explorable_browser

    browser, where = explorable_browser.find_browser()
    if browser is None:
        return None, f"no Chromium-family browser: {where}"
    resolved = Path(browser).resolve()
    if Path.cwd().resolve() in resolved.parents:
        return None, "the only browser found is inside the workspace"
    with tempfile.TemporaryDirectory(prefix="report-check-") as folder:
        own = Path(folder, "own.html")
        own.write_text("<!doctype html><html><body><p id=x>own 12.34</p></body></html>", "utf-8")
        ran = explorable_browser.run_page(str(resolved), own, TIMEOUT, arguments=DENY)
    if ran.document is None or "own 12.34" not in ran.document:
        return None, f"the browser could not print a page of this check's own: {ran.reason}"
    return str(resolved), ""


def _with_driver(text: str) -> str:
    data = facts()
    config = json.dumps(
        {"plans": [plan["plan"] for plan in data["plans"]], "scenarios": SCENARIOS,
         "settle": SETTLE_MS}
    )  # fmt: skip
    driver = DRIVER.replace("__CONFIG__", config).replace("__RESULT_ID__", RESULT_ID)
    inserted = POLICY + driver
    head = re.search(r"<head\b[^>]*>", text, re.IGNORECASE)
    if head:
        return text[: head.end()] + inserted + text[head.end() :]
    doctype = re.match(r"\s*<!doctype[^>]*>", text, re.IGNORECASE)
    at = doctype.end() if doctype else 0
    return text[:at] + inserted + text[at:]


def _run(browser: str) -> tuple[str | None, dict | None, str]:
    """The printed document of the page run with the driver, the driver's result, and a reason
    where either is missing."""

    from outcomebound_tools import explorable_browser

    with tempfile.TemporaryDirectory(prefix="report-page-") as folder:
        copy = Path(folder, "hosting.html")
        copy.write_text(_with_driver(PAGE.read_text(encoding="utf-8", errors="replace")), "utf-8")
        ran = explorable_browser.run_page(browser, copy, TIMEOUT, fragment="", arguments=DENY)
    if ran.document is None:
        return None, None, f"the page could not be printed after it ran: {ran.reason}"
    found = re.search(rf'<script[^>]*id="{RESULT_ID}"[^>]*>(.*?)</script>', ran.document, re.DOTALL)
    if not found:
        return ran.document, None, (
            "the page did not finish: the grader's own script wrote no result (the page left "
            "its document, replaced it or stopped its scripts)"
        )  # fmt: skip
    try:
        return ran.document, json.loads(found.group(1)), ""
    except ValueError:
        return ran.document, None, "the grader's result could not be read"


def _cut(text: str, cap: int) -> str:
    """The text on one line, whole up to `cap` characters; past that, cut and marked as cut."""

    text = " ".join(str(text).split())
    return (
        text if len(text) <= cap else f"{text[:cap]} [cut: {cap} of {len(text)} characters shown]"
    )


def _changes(start: str, other: str) -> str:
    """How `other` differs from `start`, word by word, each change with the words before it:
    what was replaced, added or removed. Nothing of `other` is left out: with `start` it gives
    the whole of it."""

    old, new = start.split(), other.split()
    found = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(
        None, old, new, autojunk=False
    ).get_opcodes():
        if tag == "equal":
            continue
        before = " ".join(new[max(0, j1 - 4) : j1])
        after = f'after "{before}": ' if before else "at the start: "
        gone, came = " ".join(old[i1:i2]), " ".join(new[j1:j2])
        if tag == "replace":
            found.append(f'{after}"{gone}" became "{came}"')
        elif tag == "insert":
            found.append(f'{after}added "{came}"')
        else:
            found.append(f'{after}removed "{gone}"')
    return "; ".join(found)


def observed(result: dict) -> list[str]:
    """What the page showed, as lines that never change a verdict: its rendered text and its
    controls in every state the driver put it in (the start, each value, the start again). The
    start's text is whole; a state with other text gives how it differs word by word, so with
    the start the whole of it is there; states with the same text share one line. A text or list
    past the cap is cut, marked in its line and in a line of its own."""

    lines, cut = [], False
    for field, cap in (("text", TEXT_CAP), ("controls", CONTROLS_CAP)):
        seen: dict[str, list[str]] = {}
        for state in result.get("states") or []:
            value = state.get(field)
            joined = (
                "; ".join(value) if isinstance(value, list) else " ".join(str(value or "").split())
            )
            seen.setdefault(joined, []).append(str(state.get("label", "")))
        start = next(iter(seen), "")
        for joined, labels in seen.items():
            if not joined and field == "controls":
                continue
            names = "; ".join(labels)
            if joined == start:
                body, subject = joined, f"page {field} [{names}]"
            else:
                body = _changes(start, joined) if field == "text" else joined
                subject = (
                    f"page {field} [{names}] differs from the start text"
                    if field == "text"
                    else f"page {field} [{names}]"
                )
            shown = _cut(body, cap)
            cut = cut or shown != " ".join(body.split())
            lines.append(f"observed: {subject}: {shown}")
    if cut:
        lines.append(
            "observed: page evidence cut: a text or list of controls above is longer than the "
            "cap and shows only its start"
        )
    if result.get("clicks"):
        lines.append(
            f"observed: #calculate was clicked after the inputs were set ({result['clicks']} times)"
        )
    return lines


def _interface_misses(result: dict) -> list[str]:
    """What of the interface is missing at the start: an input that is not an input, or is not a
    number input, shown, enabled and editable; a total that is missing, hidden or not a total to
    the cent, with the reason."""

    lacking = []
    for name in ("requests", "storage"):
        info = (result.get("inputs") or {}).get(name)
        if not info:
            lacking.append(f"there is no element with the id `{name}`")
        elif info.get("tag") != "input":
            lacking.append(f"the element `{name}` is a <{info.get('tag')}>, not an input")
        else:
            problems = [
                reason
                for reason, found in (
                    (f"of type {info.get('type')}, not number", info.get("type") != "number"),
                    ("not shown", not info.get("shown")),
                    ("disabled", info.get("disabled")),
                    ("read-only", info.get("readonly")),
                )
                if found
            ]
            if problems:
                lacking.append(f"the input `{name}` is {', '.join(problems)}")
    totals = (result.get("initial") or {}).get("totals", {})
    for plan, seen in totals.items():
        label = f"#{element_id(plan)}"
        if seen["state"] == "missing":
            lacking.append(f"there is no element {label}")
        elif seen["state"] == "hidden":
            lacking.append(f"{label} is hidden, so it reads as missing")
    return lacking


def _at_start(result: dict, arithmetic: bool = True) -> list[str]:
    data = facts()
    values = (result.get("initial") or {}).get("values") or []
    wanted = (data["requests_millions"], data["storage_gb"])
    lacking = []
    try:
        started = tuple(float(value) for value in values)
    except (TypeError, ValueError):
        started = ()
    if started != wanted:
        lacking.append(
            f"the inputs should start at {wanted[0]:g} million requests and {wanted[1]:g} GB "
            f"(the expected traffic), not {values}"
        )
    totals = result["initial"]["totals"]
    for plan in data["plans"]:
        lacking += _wrong(totals[plan["plan"]], plan, *wanted, "at the start", arithmetic)
    return lacking


def _wrong(
    seen: dict, plan: dict, requests: float, storage: float, when: str, arithmetic: bool = True
) -> list[str]:
    """Why what the page shows in `#total-<plan>` is not the plan's cost at these values; with
    `arithmetic` false, only why it is not a shown total to the cent."""

    label = f"#{element_id(plan['plan'])}"
    if seen["state"] != "shown":
        return [f"{when}, {label} is {seen['state']}"]
    amount, why = read_total(seen.get("text", ""))
    wanted = cost(plan, requests, storage)
    if amount is None:
        return [f'{when}, {label} {why} ("{seen.get("text", "")[:40]}"), not {wanted}']
    if arithmetic and amount != wanted:
        return [f"{when}, {label} shows {amount}, not {wanted}"]
    return []


def judge(result: dict, arithmetic: bool = True) -> list[str]:
    """What does not hold for a driver result. With `arithmetic` false, the amounts are not
    compared with the plans' costs: only whether the report works (usable inputs, a shown total
    to the cent for every plan, totals that follow the inputs)."""

    lacking = []
    if result.get("error"):
        lacking.append(f"the grader's script stopped: {result['error']}")
    interface = _interface_misses(result)
    if interface:
        return lacking + interface
    lacking += _at_start(result, arithmetic)
    data = facts()
    vectors = set()
    for run in result["runs"]:
        requests, storage = run["applied"]
        shown = []
        for plan in data["plans"]:
            seen = run["totals"][plan["plan"]]
            lacking += _wrong(
                seen,
                plan,
                requests,
                storage,
                f"at {requests:g} million requests and {storage:g} GB",
                arithmetic,
            )
            shown.append(seen.get("text", ""))
        vectors.add(tuple(shown))
    if len(result["runs"]) < len(SCENARIOS):
        lacking.append("the inputs could not be driven to every value")
    elif len(vectors) < 3:
        lacking.append(
            "the totals did not change as the inputs changed (if recalculation needs a button, "
            "it needs the id `calculate`)"
        )
    return list(dict.fromkeys(lacking))


def numbers() -> tuple[list[str], bool, list[str]]:
    """What does not hold, whether the check could judge at all, and what it observed."""

    if not PAGE.is_file():
        return [f"{PAGE} is not there"], True, []
    browser, why = _browser()
    if browser is None:
        return [why], False, []
    _document, result, reason = _run(browser)
    if result is None:
        return [reason], True, []
    return judge(result)[:8], True, observed(result)


def local() -> tuple[list[str], bool, list[str]]:
    """What does not hold, whether the check could judge at all, and what it observed: the page
    reaches the network by no act of its own. It makes no navigation away from its document, no
    `window.open`, no form action or ping to an address, no `<meta>` refresh to an address; the
    markup and the browser run's effects show these. Whether the report works is not asked here:
    `numbers` runs with the network denied and judges that, so a broken report passes this claim.
    A load the network would have served is only recorded as an `observed:` line."""

    if not PAGE.is_file():
        return [], True, []
    named = markup()
    lacking = list(named["sends"])
    browser, why = _browser()
    if browser is None:
        return (lacking, True, []) if lacking else ([why], False, [])
    document, result, _reason = _run(browser)
    if result is None:
        if document is not None:
            lacking.append(
                "the page did not keep its own document while it ran: it sent the reader away "
                "or replaced itself"
            )
        return lacking, True, []
    network = re.compile(r"(?:https?|wss?|ftp):|//", re.IGNORECASE)
    blocked = [line[:120] for line in result.get("violations", []) if network.search(line)]
    lacking += [f"the page opened a window: {line[:100]}" for line in result.get("opened", [])]
    loads = list(dict.fromkeys(named["optional"] + blocked))
    return lacking, True, [f"observed: load from the network not made: {line}" for line in loads]


def scope() -> list[str]:
    found = set(git("diff", "--name-only", seed()).splitlines())
    found |= set(git("diff", "--name-only", "--cached", seed()).splitlines())
    found |= set(git("diff", "--name-only", seed(), "HEAD").splitlines())
    found |= set(git("ls-files", "--others", "--exclude-standard").splitlines())
    return [
        f"changed outside the task: {path}"
        for path in sorted(found - {""})
        if not any(fnmatch.fnmatch(path, pattern) for pattern in ALLOWED)
    ]


def main(argv: list[str]) -> int:
    modes = {"page": page, "scope": scope}
    if len(argv) != 1 or argv[0] not in (*modes, "numbers", "local"):
        print(__doc__)
        return 2
    lines: list[str] = []
    if argv[0] in ("numbers", "local"):
        lacking, judged, lines = numbers() if argv[0] == "numbers" else local()
        if not judged:
            print(f"unjudged: {lacking[0]}")
            return 3
    else:
        lacking = modes[argv[0]]()
    for line in lacking:
        print(line)
    if not lacking:
        print(f"{argv[0]}: holds")
    for line in lines:
        print(line)
    return 1 if lacking else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
