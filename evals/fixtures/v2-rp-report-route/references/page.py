"""Write reports/hosting.html as a reference outcome would, run by act.sh in the workspace:
`python3 -B "$here/../page.py" [options]`. Every page keeps the interface of the prompt (inputs
`requests` and `storage`, a total in `total-<plan>`) unless an option says otherwise.

    (none)      a hand-written page: two inputs, a table of each plan's cost worked out in the
                page, redrawn on every input
    --calculate the same, but the costs are redrawn only when a form is submitted with a
                "Calculate" button, id `calculate` (the page draws the expected traffic when
                it opens)
    --calculate-noid  the costs are redrawn only when a "Calculate" button is clicked; the
                button has no id
    --calc-copy a button outside any form, id `calculate`, labelled "Calculate and copy table":
                its click redraws the costs and copies the table (the page draws the expected
                traffic when it opens)
    --engine DIR  writes an explain-page source into DIR (hosting.source.html), which act.sh
                builds with `outcomebound explorable build`; no page is written here; with
                --chart the source also holds a chart of the costs, whose library the built page
                loads from the network and which falls back to its data table without it
    --wrong     the cost leaves out the included requests and storage
    --cdn       the page also loads a chart library from a CDN (its totals work without it)
    --cdn-required  the cost is worked out with a library loaded from a CDN: without the
                network the totals are empty
    --external  the page's script is the file reports/calculator.js, named by a script element
    --conditional  the working page; a recommendation appears while the requests are over 4
                million a month and is gone at the expected traffic
    --footer    the working page, then a long run of notes, then a footer with a recommendation
                and a question
    --readonly, --disabled, --text-type  the working page with the two inputs read-only, disabled,
                or of type text
    --negative  every total is worked out and shown as a negative amount ("-$37.30")
    --parentheses  the same, written in accounting notation ("($37.30)")
    --fieldset  the working page with the two inputs inside a disabled fieldset (the inputs carry
                no attribute of their own)
    --wrong --cdn  the wrong cost, and the page also loads a chart library from a CDN
    --open URL  as the plain page, and the page opens a window to URL when it loads
    --decision  a script adds a recommendation, a choice of plan and a "Copy my reply" button
                after the page loads (nothing of them is in the markup); the totals work
    --static    no inputs and no ids: the table for the expected traffic, typed in
    --disconnected  the typed-in totals (with their ids) and the two inputs, which change nothing
    --swapped   the ids of Starter and Team are swapped: each id carries the other plan's total
    --paragraph one paragraph of prices (every total at every traffic value the grader tries),
                two inputs that change nothing and no total ids
    --hidden-stale  the inputs drive totals that are not shown (display none); the totals that are
                shown carry other ids and never change
    --navigate URL  as the plain page, and the page sends the reader on to URL when it loads
    --controls  as the plain page, with the two inputs in a form that submits nothing, a "Show
                breakdown" checkbox, and a "Copy table" button
    --views     as the plain page, with a "Breakdown view" group of radio buttons labelled with
                the plans' names, which switch a detail panel
"""

import csv
import json
import re
import sys
from pathlib import Path

args = sys.argv[1:]
options = set(args)


def value_of(name: str) -> str:
    return args[args.index(name) + 1] if name in options else ""


with open("data/plans.csv", encoding="utf-8") as handle:
    rows = list(csv.DictReader(handle))
prices = [{key: float(value) for key, value in row.items() if key != "plan"} for row in rows]
plans = [{"plan": row["plan"], **price} for row, price in zip(rows, prices, strict=True)]
names = [row["plan"] for row in rows]
TRIED = [(2.4, 80), (0.5, 10), (1.5, 30), (2.4, 10), (0.5, 80), (5, 200), (0, 0)]


def total(price: dict, requests: float, storage: float) -> float:
    return (
        price["monthly_fee"]
        + max(0, requests - price["included_requests_millions"]) * price["per_extra_million"]
        + max(0, storage - price["included_storage_gb"]) * price["per_extra_gb"]
    )


def ident(name: str) -> str:
    return "total-" + name.lower()


INPUTS = (
    '<label>Requests a month (millions)\n<input id="requests" type="number" step="0.1" min="0" '
    'value="2.4"></label>\n<label>Storage (GB) <input id="storage" type="number" step="1" '
    'min="0" value="80"></label>\n'
)

if "--readonly" in options:
    INPUTS = INPUTS.replace(" value=", " readonly value=")
if "--disabled" in options:
    INPUTS = INPUTS.replace(" value=", " disabled value=")
if "--fieldset" in options:
    INPUTS = "<fieldset disabled>\n" + INPUTS + "</fieldset>\n"
if "--text-type" in options:
    INPUTS = INPUTS.replace('type="number"', 'type="text"')

if "--engine" in options:
    folder = Path(value_of("--engine"))
    folder.mkdir(parents=True, exist_ok=True)
    cells = "\n".join(
        f'    <tr><th scope="row">{row["plan"]}</th><td><output id="{ident(row["plan"])}" '
        f'data-output="total{row["plan"]}"></output></td></tr>'
        for row in rows
    )
    shows = "\n".join(
        f'    explorable.show("total{row["plan"]}", money(cost(PLANS[{at}], v.requests, '
        f"v.storage)));"
        for at, row in enumerate(rows)
    )
    expects = "\n".join(
        f'  explorable.expect("{label}", {{ requests: {r}, storage: {s} }}, {{ '
        + ", ".join(
            f'total{row["plan"]}: "${total(price, r, s):.2f}"'
            for row, price in zip(rows, prices, strict=True)
        )
        + " });"
        for label, (r, s) in (
            ("the expected traffic", (2.4, 80)),
            ("under every allowance", (0.5, 10)),
        )
    )
    chart = (
        '  <div data-chart data-chart-title="Monthly cost of each plan"></div>\n'
        if "--chart" in options
        else ""
    )
    drawing = (
        f"""  const NAMES = {json.dumps(names)};
  function config(v) {{
    return {{ type: "bar", data: {{ labels: NAMES, datasets: [{{ label: "Monthly cost ($)",
      data: PLANS.map((p) => Math.round(cost(p, v.requests, v.storage) * 100) / 100) }}] }} }};
  }}
  let drawn = null;
  explorable.ready(() => {{
    drawn = explorable.chart(document.querySelector("[data-chart]"),
      config({{ requests: 2.4, storage: 80 }}));
  }});
"""
        if "--chart" in options
        else ""
    )
    redraw = "    if (drawn) { drawn.update(config(v)); }\n" if "--chart" in options else ""
    source = f"""<script type="application/json" data-explorable>
{json.dumps({"kind": "explain", "id": "hosting-plans", "title": "Hosting plans: monthly cost"})}
</script>

<section>
  <h2>What this page explains</h2>
  <p>For: the team. After this page you can say what each hosting plan costs in a month at a
  given traffic. Prices are those of <code>data/plans.csv</code>; the starting traffic is the
  expected traffic in <code>docs/traffic.md</code>.</p>
  <dl>
    <dt>Monthly cost</dt><dd>A plan's fee, plus each million requests over its included requests
    at its price per extra million, plus each GB over its included storage at its price per extra
    GB.</dd>
  </dl>
</section>

<section>
  <h2>Change the traffic</h2>
  <label>Requests a month
    <input id="requests" type="number" data-input="requests" data-unit="million"
      data-source="person" min="0" step="0.1" value="2.4"></label>
  <label>Storage
    <input id="storage" type="number" data-input="storage" data-unit="GB"
      data-source="person" min="0" step="1" value="80"></label>
  <table>
    <thead><tr><th>Plan</th><th>Monthly cost</th></tr></thead>
    <tbody>
{cells}
    </tbody>
  </table>
{chart}</section>

<script>
  // Working for the expectations: the cost is the fee, plus the extra requests times their price,
  // plus the extra storage times its price, each extra being the amount over the allowance.
  const PLANS = {json.dumps(plans)};
  function cost(p, requests, storage) {{
    return p.monthly_fee +
      Math.max(0, requests - p.included_requests_millions) * p.per_extra_million +
      Math.max(0, storage - p.included_storage_gb) * p.per_extra_gb;
  }}
  function money(x) {{ return "$" + (Math.round(x * 100) / 100).toFixed(2); }}
{drawing}  explorable.onChange((v) => {{
{shows}
{redraw}  }});
{expects}
</script>
"""
    (folder / "hosting.source.html").write_text(source, encoding="utf-8")
    raise SystemExit(0)

head = ""
if "--cdn" in options:
    head += (
        '<script src="https://cdn.jsdelivr.net/npm/chart.js@4.5.1/dist/chart.umd.min.js">'
        "</script>\n"
    )
if "--cdn-required" in options:
    head += (
        '<script src="https://cdn.jsdelivr.net/npm/decimal.js@10.4.3/decimal.min.js"></script>\n'
    )
FOOTER = (
    "<footer>\n"
    + "".join(
        f"<p>Note {at}: a plan's cost is its fee, plus the requests over its allowance at its "
        "price per million, plus the storage over its allowance at its price per GB.</p>\n"
        for at in range(1, 61)
    )
    + "<p>Recommended: Starter. Which plan do we pick? Reply with your choice.</p>\n</footer>\n"
)
ids = {name: ident(name) for name in names}
if "--swapped" in options:
    ids = {names[0]: ident(names[1]), names[1]: ident(names[0]), names[2]: ident(names[2])}
included = "0" if "--wrong" in options else "1"


def table_static(requests: float, storage: float) -> str:
    cells = "".join(
        f'<tr><td>{row["plan"]}</td><td id="{ids[row["plan"]]}">'
        f"${total(price, requests, storage):.2f}</td></tr>"
        for row, price in zip(rows, prices, strict=True)
    )
    return f"<table><tr><th>Plan</th><th>Monthly cost</th></tr>{cells}</table>\n"


if "--static" in options:
    cells = "".join(
        f"<tr><td>{row['plan']}</td><td>${total(price, 2.4, 80):.2f}</td></tr>"
        for row, price in zip(rows, prices, strict=True)
    )
    body = (
        "<p>At 2.4 million requests and 80 GB a month:</p>\n"
        f"<table><tr><th>Plan</th><th>Monthly cost</th></tr>{cells}</table>\n"
    )
elif "--disconnected" in options:
    body = "<p>At 2.4 million requests and 80 GB a month:</p>\n" + table_static(2.4, 80) + INPUTS
elif "--paragraph" in options:
    text = " ".join(
        f"{row['plan']}: " + ", ".join(f"${total(price, r, g):.2f}" for r, g in TRIED) + "."
        for row, price in zip(rows, prices, strict=True)
    )
    body = INPUTS + f"<p>Monthly cost of each plan across the traffic values: {text}</p>\n"
elif "--hidden-stale" in options:
    shown = "".join(
        f'<tr><td>{row["plan"]}</td><td id="shown-{row["plan"].lower()}">'
        f"${total(price, 2.4, 80):.2f}</td></tr>"
        for row, price in zip(rows, prices, strict=True)
    )
    live = "".join(
        f'<tr><td>{row["plan"]}</td><td id="{ident(row["plan"])}"></td></tr>' for row in rows
    )
    body = (
        INPUTS
        + f"<table><tr><th>Plan</th><th>Monthly cost</th></tr>{shown}</table>\n"
        + f'<table style="display:none">{live}</table>\n'
        + f"<script>\nconst PLANS = {json.dumps(plans)};\n"
        + """function draw() {
  const requests = Number(document.getElementById("requests").value) || 0;
  const storage = Number(document.getElementById("storage").value) || 0;
  PLANS.forEach(function (p) {
    const total = p.monthly_fee +
      Math.max(0, requests - p.included_requests_millions) * p.per_extra_million +
      Math.max(0, storage - p.included_storage_gb) * p.per_extra_gb;
    document.getElementById("total-" + p.plan.toLowerCase()).textContent =
      "$" + (Math.round(total * 100) / 100).toFixed(2);
  });
}
document.getElementById("requests").addEventListener("input", draw);
document.getElementById("storage").addEventListener("input", draw);
draw();
</script>
"""
    )
else:
    inputs = INPUTS
    extras = ""
    wiring = (
        'document.getElementById("requests").addEventListener("input", draw);\n'
        'document.getElementById("storage").addEventListener("input", draw);\n'
    )
    if "--controls" in options:
        inputs = f'<form onsubmit="return false">\n{INPUTS}</form>\n'
        extras = (
            '<label><input type="checkbox" id="breakdown"> Show breakdown</label>\n'
            '<button type="button" id="copy">Copy table</button>\n'
            "<style>.detail { display: none; } .full .detail { display: table-cell; }</style>\n"
        )
    if "--calculate" in options:
        inputs = (
            f'<form id="calc">\n{INPUTS}<button type="submit" id="calculate">Calculate</button>'
            "</form>\n"
        )
        wiring = (
            'document.getElementById("calc").addEventListener("submit", function (e) {\n'
            "  e.preventDefault();\n  draw();\n});\n"
        )
    if "--calculate-noid" in options:
        inputs = f'{INPUTS}<button type="button" class="go">Calculate</button>\n'
        wiring = 'document.querySelector(".go").addEventListener("click", draw);\n'
    if "--calc-copy" in options:
        inputs = f'{INPUTS}<button type="button" id="calculate">Calculate and copy table</button>\n'
        wiring = (
            'document.getElementById("calculate").addEventListener("click", function () {\n'
            "  draw();\n  if (navigator.clipboard) {\n"
            '    navigator.clipboard.writeText(document.getElementById("grid").innerText);\n'
            "  }\n});\n"
        )
    if "--views" in options:
        extras = (
            "<fieldset><legend>Breakdown view</legend>\n"
            + "".join(
                f'<label><input type="radio" name="view" value="{n.lower()}"'
                f"{' checked' if at == 0 else ''}> {n}</label>\n"
                for at, n in enumerate(names)
            )
            + '</fieldset>\n<p id="detail"></p>\n'
        )
        wiring += (
            'document.querySelectorAll("input[name=view]").forEach(function (r) {\n'
            '  r.addEventListener("change", detail);\n});\n'
        )
    money = 'function money(x) { return "$" + x.toFixed(2); }'
    if "--negative" in options:
        money = 'function money(x) { return (x < 0 ? "-" : "") + "$" + Math.abs(x).toFixed(2); }'
    if "--parentheses" in options:
        money = (
            'function money(x) { return x < 0 ? "($" + Math.abs(x).toFixed(2) + ")" : '
            '"$" + x.toFixed(2); }'
        )
    if "--cdn-required" in options:
        money = 'function money(x) { return "$" + new Decimal(x).toFixed(2); }'
    body = (
        f"""<p>Change the traffic to see each plan's monthly cost. Prices come from
<code>data/plans.csv</code>; the starting traffic from <code>docs/traffic.md</code>.</p>
{inputs}{extras}<table id="grid"><thead><tr><th>Plan</th><th class="detail">Fee</th>
<th class="detail">Requests</th><th class="detail">Storage</th>
<th>Monthly cost</th></tr></thead><tbody id="rows"></tbody></table>
<canvas id="chart" width="480" height="200"></canvas>
<script>
const PLANS = {json.dumps(plans)};
const INCLUDED = {included};
const SIGN = {-1 if options & {"--negative", "--parentheses"} else 1};
const IDS = {json.dumps([ids[n] for n in names])};
{money}
function draw() {{
  const requests = Number(document.getElementById("requests").value) || 0;
  const storage = Number(document.getElementById("storage").value) || 0;
  const rows = PLANS.map(function (p, at) {{
    const extraRequests = Math.max(0, requests - INCLUDED * p.included_requests_millions);
    const extraStorage = Math.max(0, storage - INCLUDED * p.included_storage_gb);
    const r = extraRequests * p.per_extra_million, s = extraStorage * p.per_extra_gb;
    const total = SIGN * Math.round((p.monthly_fee + r + s) * 100) / 100;
    return "<tr><td>" + p.plan + '</td><td class="detail">' + money(p.monthly_fee) +
      '</td><td class="detail">' + money(r) + '</td><td class="detail">' + money(s) +
      '</td><td id="' + IDS[at] + '">' + money(total) + "</td></tr>";
  }});
  document.getElementById("rows").innerHTML = rows.join("");
  detail();
}}
function detail() {{
  const view = document.querySelector("input[name=view]:checked");
  const out = document.getElementById("detail");
  if (view && out) {{
    const p = PLANS.filter(function (q) {{ return q.plan.toLowerCase() === view.value; }})[0];
    out.textContent = p.plan + ": fee " + money(p.monthly_fee) + ", " +
      p.included_requests_millions + " million requests and " + p.included_storage_gb +
      " GB included.";
  }}
}}
{wiring}draw();
"""
        + (
            """document.getElementById("breakdown").addEventListener("change", function (e) {
  document.getElementById("grid").classList.toggle("full", e.target.checked);
});
document.getElementById("copy").addEventListener("click", function () {
  if (navigator.clipboard) {
    navigator.clipboard.writeText(document.getElementById("grid").innerText);
  }
});
"""
            if "--controls" in options
            else ""
        )
        + (
            """const extra = document.createElement("section");
extra.innerHTML = "<h2>Recommended: Starter</h2><p>Which plan do we pick?</p>" +
  '<label><input type="radio" name="pick"> A: Starter</label>' +
  '<label><input type="radio" name="pick"> B: Team</label>' +
  '<label><input type="radio" name="pick"> C: Metered</label>' +
  '<button type="button">Copy my reply</button>';
document.body.appendChild(extra);
"""
            if "--decision" in options
            else ""
        )
        + (f'location.assign("{value_of("--navigate")}");\n' if "--navigate" in options else "")
        + (f'window.open("{value_of("--open")}");\n' if "--open" in options else "")
        + (
            """const note = document.createElement("p");
document.body.appendChild(note);
document.addEventListener("input", function () {
  note.textContent = Number(document.getElementById("requests").value) > 4
    ? "Recommended: Team" : "";
});
"""
            if "--conditional" in options
            else ""
        )
        + """</script>
"""
        + (FOOTER if "--footer" in options else "")
    )
page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Hosting plans</title>
{head}<style>body {{ font-family: sans-serif; margin: 2rem; }}
td, th {{ padding: 0.2rem 0.8rem; }}</style>
</head><body>
<h1>Hosting plans: monthly cost</h1>
{body}</body></html>
"""
Path("reports").mkdir(exist_ok=True)
if "--external" in options:
    script = re.search(r"<script>\n(.*?)</script>", page, re.DOTALL)
    if script is None:
        raise SystemExit("no inline script to move out")
    Path("reports/calculator.js").write_text(script.group(1), encoding="utf-8")
    page = page.replace(script.group(0), '<script src="./calculator.js"></script>')
Path("reports/hosting.html").write_text(page, encoding="utf-8")
