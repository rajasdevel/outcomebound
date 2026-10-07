/* OutcomeBound explorable runtime. One plain script: no build step, no framework.
   It defines window.explorable. It loads only the two libraries that the page's config pins,
   and only when a chart or a diagram asks for one. Page code registers with ready and onChange;
   it never navigates, opens a window or loads anything. */
(function () {
  "use strict";

  var TOKEN_NAMES = ["bg", "surface", "text", "muted", "border", "accent", "acctext", "grid",
    "added", "removed", "changed", "warn", "recbg"];
  var KINDS = ["k1", "k2", "k3", "k4", "k5", "k6"];
  var DASHES = [[], [6, 4], [2, 3], [8, 3, 2, 3], [1, 4], [12, 4]];
  var POINTS = ["circle", "rect", "triangle", "rectRot", "star", "cross"];
  var DIFFS = { added: "+", removed: "−", changed: "~" };
  var UNKNOWN = "I don't know";

  // ---- Errors are recorded from the first moment, so that check mode can report them.
  var errors = [];
  function note(message) { errors.push(String(message)); }
  window.addEventListener("error", function (e) {
    note((e && e.message) || "script error");
  });
  window.addEventListener("unhandledrejection", function (e) {
    var r = e && e.reason;
    note("unhandled rejection: " + ((r && r.message) || r));
  });
  document.addEventListener("securitypolicyviolation", function (e) {
    note("policy violation: " + e.violatedDirective + " " + e.blockedURI);
  });

  // ---- State
  var cfg = null;
  var started = false;
  var checkMode = false;
  var readyFns = [];
  var changeFns = [];
  var expectations = [];
  var themeFns = [];
  var inputs = [];          // {name, el, type, defaults, metaEl, noteEl, badgeEl, valueEl}
  var inputByName = {};
  var defaultValues = {};
  var shown = {};           // output name -> {text, state, opts}
  var questions = [];
  var briefChoices = [];
  var diagrams = [];
  var charts = [];
  var libs = { chart: "unused", mermaid: "unused" };
  var libPromises = {};
  var lastSig = null;
  var lastResults = [];
  var idCounter = 0;
  var noteEl = null;
  var replyEl = null;
  var statusEl = null;
  var storageKey = null;
  var restoring = false;
  var renderQueue = Promise.resolve();
  var counts = { drawn: 0, failed: 0 };
  var failedMessages = [];
  var pendingDraws = 0;
  var mq = window.matchMedia ? window.matchMedia("(prefers-color-scheme: dark)") : null;
  var motionQuery = window.matchMedia ? window.matchMedia("(prefers-reduced-motion: reduce)") : null;

  function uid(prefix) { idCounter += 1; return "xp-" + prefix + idCounter; }
  function reducedMotion() { return !!(motionQuery && motionQuery.matches); }
  function currentScheme() { return mq && mq.matches ? "dark" : "light"; }
  function $(sel, root) { return (root || document).querySelector(sel); }
  function $$(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }
  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  function guard(label, fn) {
    try { return fn(); } catch (err) { note(label + ": " + (err && err.message ? err.message : err)); }
    return undefined;
  }
  function readConfig() {
    var node = document.getElementById("explorable-config");
    try { cfg = node ? JSON.parse(node.textContent) : {}; } catch (err) { cfg = {}; note("config: " + err.message); }
    cfg.libraries = cfg.libraries || {};
    cfg.briefs = cfg.briefs || [];
  }
  readConfig();
  checkMode = /(^|[#&])explorable-check($|&)/.test(String(location.hash || ""));

  // ---- Theme
  function tokensFor(scheme) {
    var prefix = scheme === "dark" ? "--xp-d-" : "--xp-l-";
    var style = getComputedStyle(document.documentElement);
    function get(name) { return style.getPropertyValue(prefix + name).trim(); }
    var t = { scheme: scheme, k: {}, font: getComputedStyle(document.body).fontFamily };
    TOKEN_NAMES.forEach(function (n) { t[n] = get(n); });
    KINDS.forEach(function (k) {
      t.k[k] = { fill: get(k + "-fill"), stroke: get(k + "-stroke"), text: get(k + "-text") };
    });
    return t;
  }
  function theme() { return tokensFor(currentScheme()); }
  function onTheme(fn) { if (typeof fn === "function") themeFns.push(fn); }

  // ---- Formatting
  function plain(n, digits) {
    var d = digits == null ? 3 : digits;
    if (n === 0) return "0";
    var r = Number(Number(n).toPrecision(Math.max(1, d)));
    return r.toLocaleString("en-US", { useGrouping: false, maximumFractionDigits: 20 });
  }
  function isNum(v) { return typeof v === "number" && isFinite(v); }
  function withUnit(text, unit) { return unit ? text + " " + unit : text; }
  function unknownText(waits) {
    if (!waits || !waits.length) return "Unknown";
    var words = waits.map(function (w) { return inputByName[w] ? inputByName[w].label : w; });
    return "Unknown until you set: " + words.join(", ");
  }
  function emptyInputs() {
    var v = values();
    return inputs.filter(function (i) { return v[i.name] === null; }).map(function (i) { return i.label; });
  }
  function describe(value, opts) {
    opts = opts || {};
    if (Array.isArray(value)) {
      if (value.length === 2 && isNum(value[0]) && isNum(value[1])) {
        var lo = Math.min(value[0], value[1]);
        var hi = Math.max(value[0], value[1]);
        return { state: "range", text: withUnit(plain(lo, opts.digits) + " to " + plain(hi, opts.digits), opts.unit) };
      }
      return { state: "unknown", text: unknownText(opts.waits && opts.waits.length ? opts.waits : emptyInputs()) };
    }
    if (value === null || value === undefined || (typeof value === "number" && !isFinite(value))) {
      return { state: "unknown", text: unknownText(opts.waits && opts.waits.length ? opts.waits : emptyInputs()) };
    }
    if (typeof value === "number") return { state: "value", text: withUnit(plain(value, opts.digits), opts.unit) };
    if (typeof value === "boolean") return { state: "value", text: value ? "Yes" : "No" };
    return { state: "value", text: String(value) };
  }

  // ---- Inputs
  function inputKind(node) {
    if (node.tagName === "FIELDSET") return "radios";
    if (node.tagName === "SELECT") return "select";
    var t = (node.getAttribute("type") || "text").toLowerCase();
    if (t === "checkbox") return "checkbox";
    if (t === "range" || t === "number") return "number";
    return "text";
  }
  function readInput(rec) {
    var node = rec.el;
    switch (rec.type) {
      case "checkbox": return !!node.checked;
      case "radios":
        var r = $("input[type=radio]:checked", node);
        return r ? r.value : null;
      case "select": return node.value === "" ? null : node.value;
      case "number":
        if (node.value === "") return null;
        var n = Number(node.value);
        return isFinite(n) ? n : null;
      default: return node.value === "" ? null : node.value;
    }
  }
  function writeInput(rec, v) {
    var node = rec.el;
    switch (rec.type) {
      case "checkbox": node.checked = !!v; break;
      case "radios":
        $$("input[type=radio]", node).forEach(function (r) { r.checked = v != null && r.value === String(v); });
        break;
      case "select": node.value = v == null ? "" : String(v); break;
      default: node.value = v == null ? "" : String(v);
    }
  }
  function values() {
    var out = {};
    inputs.forEach(function (rec) { out[rec.name] = readInput(rec); });
    return out;
  }
  function defaults() { return JSON.parse(JSON.stringify(defaultValues)); }
  function rawText(v) {
    if (v === null || v === undefined) return "unknown";
    if (typeof v === "boolean") return v ? "yes" : "no";
    return String(v);
  }
  // The words a person sees for an input: its label's own text, or a fieldset's legend.
  function labelText(node, holder) {
    if (node.tagName === "FIELDSET") {
      var legend = node.querySelector("legend");
      return legend ? legend.textContent.replace(/\s+/g, " ").trim() : "";
    }
    if (holder === node) return node.getAttribute("aria-label") || "";
    var words = [];
    Array.prototype.forEach.call(holder.childNodes, function (child) {
      if (child.nodeType === 3) words.push(child.textContent);
    });
    return words.join(" ").replace(/\s+/g, " ").trim();
  }
  function decorateInputs() {
    $$("[data-input]").forEach(function (node) {
      var name = node.getAttribute("data-input");
      if (!/^[A-Za-z][A-Za-z0-9_]*$/.test(name || "")) { note("input name " + JSON.stringify(name) + " is not allowed"); return; }
      if (inputByName[name]) { note("input name " + name + " is used twice"); return; }
      var rec = { name: name, el: node, type: inputKind(node), unit: node.getAttribute("data-unit") || "" };
      var holder = node.closest("label") || node;
      rec.label = labelText(node, holder) || name;
      var row = el("div", "xp-input-row");
      holder.parentNode.insertBefore(row, holder);
      row.appendChild(holder);
      var meta = el("div", "xp-meta");
      rec.valueEl = el("span", "xp-input-value");
      var source = node.getAttribute("data-source");
      rec.source = source === "checked" || source === "assumed" || source === "person" ? source : "none";
      rec.badgeEl = el("span", "xp-badge");
      meta.appendChild(rec.valueEl);
      meta.appendChild(rec.badgeEl);
      row.appendChild(meta);
      var describedBy = [];
      if (node.getAttribute("data-note")) {
        rec.noteEl = el("p", "xp-input-note", node.getAttribute("data-note"));
        rec.noteEl.id = uid("note");
        describedBy.push(rec.noteEl.id);
        row.appendChild(rec.noteEl);
      }
      meta.id = uid("meta");
      describedBy.push(meta.id);
      if (node.tagName !== "FIELDSET") {
        node.setAttribute("aria-describedby", ((node.getAttribute("aria-describedby") || "") + " " + describedBy.join(" ")).trim());
      }
      rec.row = row;
      inputs.push(rec);
      inputByName[name] = rec;
    });
    inputs.forEach(function (rec) { defaultValues[rec.name] = readInput(rec); });
  }
  function refreshInputMeta() {
    inputs.forEach(function (rec) {
      var v = readInput(rec);
      var moved = rawText(v) !== rawText(defaultValues[rec.name]);
      var src = moved ? "person" : rec.source;
      rec.badgeEl.setAttribute("data-source", src);
      rec.badgeEl.textContent = src === "checked" ? "Checked" : src === "assumed" ? "Assumed"
        : src === "person" ? "Your value" : "No source";
      var text = v === null ? "unknown" : typeof v === "boolean" ? (v ? "yes" : "no") : String(v);
      rec.valueEl.textContent = v === null ? text : (typeof v === "boolean" ? text : withUnit(text, rec.unit));
      if (rec.type === "number" && rec.el.getAttribute("type") === "range") {
        rec.el.setAttribute("aria-valuetext", rec.valueEl.textContent);
      }
      if (rec.row) rec.row.classList.toggle("xp-moved", moved);
    });
  }

  // ---- Change handling
  function runHandlers() {
    var v = values();
    changeFns.forEach(function (fn) { guard("onChange", function () { fn(v); }); });
  }
  function sig() { return JSON.stringify(values()); }
  function inputEvent(e) {
    var t = e.target;
    if (!t || !t.closest) return;
    var holder = t.closest("[data-input]");
    if (holder && inputByName[holder.getAttribute("data-input")]) {
      var s = sig();
      if (s !== lastSig) { lastSig = s; runHandlers(); }
    }
    refreshAll();
  }
  function refreshAll() {
    refreshInputMeta();
    updateQuestions();
    updateReply();
    save();
  }

  function show(name, value, opts) {
    var node = $('[data-output="' + String(name).replace(/"/g, "") + '"]');
    var d = describe(value, opts);
    shown[name] = { text: d.text, state: d.state, opts: opts || {} };
    if (!node) return;
    node.textContent = d.text;
    node.setAttribute("data-state", d.state);
    if (!node.hasAttribute("aria-live")) node.setAttribute("aria-live", "polite");
    if (!node.hasAttribute("aria-atomic")) node.setAttribute("aria-atomic", "true");
  }

  // ---- Threshold
  var THRESHOLD_STEPS = 10000;
  function threshold(inputName, chooser) {
    var rec = inputByName[inputName];
    if (!rec || rec.type !== "number" || typeof chooser !== "function") return null;
    var min = parseFloat(rec.el.getAttribute("min"));
    var max = parseFloat(rec.el.getAttribute("max"));
    var step = parseFloat(rec.el.getAttribute("step"));
    var now = readInput(rec);
    if (!isFinite(min) || !isFinite(max) || now === null) return null;
    if (!isFinite(step) || step <= 0) step = 1;
    // A fine step over a wide range would hold the page in its change handler: scan at most
    // THRESHOLD_STEPS points across the range, the input's own step where that is coarser.
    step = Math.max(step, (max - min) / THRESHOLD_STEPS);
    var base = values();
    function letterAt(x) {
      var v = Object.assign({}, base);
      v[inputName] = x;
      try { return chooser(v); } catch (err) { return undefined; }
    }
    function clean(x) { return Math.round(x * 1e9) / 1e9; }
    var here = letterAt(now);
    function scan(dir) {
      for (var k = 1; ; k += 1) {
        var x = clean(now + dir * k * step);
        if (x > max || x < min) return null;
        var l = letterAt(x);
        if (l !== undefined && l !== null && l !== here) return { value: x, letter: l };
      }
    }
    var up = scan(1);
    var down = scan(-1);
    if (up && down) return Math.abs(up.value - now) <= Math.abs(down.value - now) ? up : down;
    return up || down || null;
  }

  // ---- Expectations
  function expect(label, given, wanted) {
    expectations.push({ label: String(label), inputs: given || {}, outputs: wanted || {} });
  }
  function runExpectations() {
    var results = [];
    expectations.forEach(function (ex) {
      var res = { label: ex.label, pass: true, expected: {}, shown: {} };
      try {
        inputs.forEach(function (rec) { writeInput(rec, defaultValues[rec.name]); });
        Object.keys(ex.inputs).forEach(function (n) {
          if (!inputByName[n]) throw new Error("no input named " + n);
          writeInput(inputByName[n], ex.inputs[n]);
        });
        lastSig = sig();
        runHandlers();
        Object.keys(ex.outputs).forEach(function (n) {
          var s = shown[n];
          var want = ex.outputs[n];
          var exp = describe(want, s ? s.opts : {});
          if (want === null) exp.text = "unknown";
          res.expected[n] = want === null ? "unknown" : exp.text;
          if (!s) { res.shown[n] = null; res.pass = false; return; }
          res.shown[n] = s.state === "unknown" ? "unknown" : s.text;
          var ok = want === null ? s.state === "unknown" : s.state !== "unknown" && s.text === exp.text;
          if (!ok) res.pass = false;
        });
      } catch (err) {
        res.pass = false;
        res.error = err && err.message ? err.message : String(err);
      }
      results.push(res);
    });
    inputs.forEach(function (rec) { writeInput(rec, defaultValues[rec.name]); });
    lastSig = sig();
    runHandlers();
    return results;
  }
  function checkResult(results) {
    var names = $$("[data-output]").map(function (n) { return n.getAttribute("data-output"); })
      .filter(function (n, i, a) { return a.indexOf(n) === i; });
    var covered = {};
    expectations.forEach(function (ex) { Object.keys(ex.outputs).forEach(function (n) { covered[n] = true; }); });
    var body = {
      done: true,
      errors: errors.slice(),
      expectations: results,
      outputs: {
        names: names,
        covered: names.filter(function (n) { return covered[n]; }),
        uncovered: names.filter(function (n) { return !covered[n]; })
      },
      libraries: { chart: libPublic("chart"), mermaid: libPublic("mermaid") },
      diagrams: { drawn: counts.drawn, failed: counts.failed, messages: failedMessages.slice(0, 5) }
    };
    return JSON.stringify(body).replace(/</g, "\\u003c");
  }
  function libPublic(name) { return libs[name] === "loading" ? "pending" : libs[name]; }
  var resultNode = null;
  function writeCheck() {
    if (!resultNode) {
      resultNode = document.createElement("script");
      resultNode.type = "application/json";
      resultNode.id = "explorable-check-result";
      document.body.appendChild(resultNode);
    }
    resultNode.textContent = checkResult(lastResults);
  }
  // ---- Libraries
  function networkBanner() {
    var failed = [];
    if (libs.chart === "failed") failed.push("charts show their data tables");
    if (libs.mermaid === "failed") failed.push("diagrams show their source text");
    var banner = document.getElementById("explorable-network");
    if (!banner) return;
    if (failed.length) {
      banner.textContent = "A library did not load, so " + failed.join(" and ") + ". Everything else works. Check the connection and open the page again.";
      banner.hidden = false;
    }
  }
  function loadChart() {
    if (libPromises.chart) return libPromises.chart;
    var lib = cfg.libraries.chart;
    libPromises.chart = new Promise(function (resolve) {
      if (window.Chart) { libs.chart = "loaded"; resolve(window.Chart); return; }
      if (!lib || !lib.url) { libs.chart = "failed"; resolve(null); return; }
      libs.chart = "loading";
      var s = document.createElement("script");
      var timer = setTimeout(function () { finish(false); }, 20000);
      function finish(ok) {
        clearTimeout(timer);
        libs.chart = ok && window[lib.global || "Chart"] ? "loaded" : "failed";
        if (libs.chart === "failed") networkBanner();
        resolve(libs.chart === "loaded" ? window[lib.global || "Chart"] : null);
      }
      s.onload = function () { finish(true); };
      s.onerror = function () { finish(false); };
      s.src = lib.url;
      if (lib.integrity) s.integrity = lib.integrity;
      s.crossOrigin = "anonymous";
      document.head.appendChild(s);
    });
    return libPromises.chart;
  }
  function loadMermaid() {
    if (libPromises.mermaid) return libPromises.mermaid;
    var lib = cfg.libraries.mermaid;
    libs.mermaid = "loading";
    libPromises.mermaid = new Promise(function (resolve) {
      if (!lib || !lib.url) { libs.mermaid = "failed"; networkBanner(); resolve(null); return; }
      var timer = setTimeout(function () { fail(); }, 20000);
      var done = false;
      function fail() {
        if (done) return;
        done = true;
        clearTimeout(timer);
        libs.mermaid = "failed";
        networkBanner();
        resolve(null);
      }
      // The URL comes from the page's own config, and the policy limits it to the pinned path.
      import(lib.url).then(function (mod) {
        if (done) return;
        done = true;
        clearTimeout(timer);
        libs.mermaid = "loaded";
        resolve(mod.default || mod);
      }, fail);
    });
    return libPromises.mermaid;
  }

  // ---- Diagrams
  function flowchart(source) { return /^\s*(flowchart|graph)\b/.test(source); }
  function prepareSource(source, t) {
    if (!flowchart(source)) return source;
    var lines = [];
    function def(name, fill, stroke, text, width, dash) {
      if (new RegExp("classDef\\s+" + name + "\\b").test(source)) return;
      lines.push("classDef " + name + " fill:" + fill + ",stroke:" + stroke + ",color:" + text +
        ",stroke-width:" + width + "px" + (dash.length ? ",stroke-dasharray:" + dash.join(" ") : ""));
    }
    KINDS.forEach(function (k, i) {
      def(k, t.k[k].fill, t.k[k].stroke, t.k[k].text, i === 3 ? 4 : 2, DASHES[i]);
    });
    def("added", t.surface, t.added, t.text, 4, []);
    def("removed", t.surface, t.removed, t.text, 3, [4, 3]);
    def("changed", t.surface, t.changed, t.text, 4, [8, 3, 2, 3]);
    return source.replace(/\s+$/, "") + "\n" + lines.join("\n") + "\n";
  }
  function mermaidConfig(t) {
    return {
      startOnLoad: false,
      securityLevel: "strict",
      theme: "base",
      fontFamily: t.font || "system-ui, sans-serif",
      flowchart: { useMaxWidth: false, htmlLabels: true },
      sequence: { useMaxWidth: false },
      gantt: { useMaxWidth: false },
      themeVariables: {
        darkMode: t.scheme === "dark",
        background: t.bg,
        primaryColor: t.surface,
        primaryTextColor: t.text,
        primaryBorderColor: t.muted,
        secondaryColor: t.surface,
        tertiaryColor: t.bg,
        lineColor: t.muted,
        textColor: t.text,
        mainBkg: t.surface,
        nodeBorder: t.muted,
        clusterBkg: t.bg,
        clusterBorder: t.border,
        edgeLabelBackground: t.bg,
        noteBkgColor: t.surface,
        noteTextColor: t.text,
        actorBkg: t.surface,
        actorBorder: t.muted,
        actorTextColor: t.text,
        signalColor: t.text,
        signalTextColor: t.text
      }
    };
  }
  function badgeNodes(svgRoot, t) {
    // A shape beside the colour: a small mark on each node that is added, removed or changed.
    // Returns false when the drawing has no layout yet (a hidden tab or step), so a later call retries.
    var complete = true;
    Object.keys(DIFFS).forEach(function (cls) {
      $$("g.node." + cls, svgRoot).forEach(function (g) {
        if (g.querySelector(".xp-diff-mark")) return;
        guard("diagram mark", function () {
          var box = g.getBBox();
          if (!box.width && !box.height) { complete = false; return; }
          var ns = g.namespaceURI;
          var mark = document.createElementNS(ns, "g");
          mark.setAttribute("class", "xp-diff-mark");
          var c = document.createElementNS(ns, "circle");
          c.setAttribute("cx", String(box.x + box.width));
          c.setAttribute("cy", String(box.y));
          c.setAttribute("r", "10");
          c.setAttribute("fill", t.bg);
          c.setAttribute("stroke", t[cls]);
          c.setAttribute("stroke-width", "2");
          var tx = document.createElementNS(ns, "text");
          tx.setAttribute("x", String(box.x + box.width));
          tx.setAttribute("y", String(box.y + 5));
          tx.setAttribute("text-anchor", "middle");
          tx.setAttribute("font-size", "15");
          tx.setAttribute("font-weight", "700");
          tx.setAttribute("fill", t.text);
          tx.textContent = DIFFS[cls];
          mark.appendChild(c);
          mark.appendChild(tx);
          g.appendChild(mark);
        });
      });
    });
    return complete;
  }
  function markDiagram(d) {
    if (d.marked || !d.tokens) return;
    var a = badgeNodes(d.screen, d.tokens.main);
    var b = d.tokens.light ? badgeNodes(d.print, d.tokens.light) : true;
    d.marked = a && b;
  }
  function markAll() { diagrams.forEach(markDiagram); }
  function describeDiagram(d) {
    var title = d.pre.getAttribute("data-diagram-title") || "";
    var desc = d.pre.getAttribute("data-diagram-desc") || "";
    return (title && desc) ? title + ". " + desc : title || desc || "Diagram";
  }
  function setupDiagram(pre) {
    var d = { pre: pre, source: pre.textContent, fallback: null, wrap: el("div", "xp-diagram"), failed: false, n: 0 };
    var next = pre.nextElementSibling;
    if (next && next.hasAttribute("data-diagram-fallback")) d.fallback = next;
    d.wrap.setAttribute("role", "img");
    d.status = el("p", "xp-diagram-status", "Drawing the diagram");
    d.screen = el("div", "xp-diagram-screen");
    d.print = el("div", "xp-diagram-print");
    d.print.setAttribute("aria-hidden", "true");
    d.wrap.appendChild(d.status);
    d.wrap.appendChild(d.screen);
    d.wrap.appendChild(d.print);
    pre.parentNode.insertBefore(d.wrap, pre);
    pre.hidden = true;
    if (d.fallback) d.fallback.hidden = true;
    d.wrap.setAttribute("aria-label", describeDiagram(d));
    return d;
  }
  function showDiagramFallback(d, message) {
    d.wrap.classList.add("xp-diagram-fail");
    d.screen.textContent = "";
    d.print.textContent = "";
    d.print.classList.remove("xp-has-print");
    var src = d.fallback || d.pre;
    d.status.textContent = message;
    d.status.hidden = false;
    var copy = el("pre", null, src.textContent);
    d.screen.appendChild(copy);
    d.wrap.removeAttribute("role");
  }
  function renderOne(d, mm) {
    var scheme = currentScheme();
    var variants = scheme === "dark" ? ["light", "dark"] : ["light"];
    d.n += 1;
    var chain = Promise.resolve();
    var results = {};
    variants.forEach(function (variant) {
      chain = chain.then(function () {
        var t = tokensFor(variant);
        mm.initialize(mermaidConfig(t));
        var id = "xp-m" + (idCounter += 1);
        return mm.render(id, prepareSource(d.source, t)).then(function (out) {
          var tmp = el("div");
          tmp.innerHTML = out.svg;
          results[variant] = { node: tmp, tokens: t };
        }, function (err) {
          var leftover = document.getElementById("d" + id);
          if (leftover) leftover.remove();
          throw err;
        });
      });
    });
    return chain.then(function () {
      d.screen.textContent = "";
      d.print.textContent = "";
      d.wrap.classList.remove("xp-diagram-fail");
      var main = results[scheme];
      while (main.node.firstChild) d.screen.appendChild(main.node.firstChild);
      d.tokens = { main: main.tokens, light: null };
      d.marked = false;
      if (scheme === "dark" && results.light) {
        while (results.light.node.firstChild) d.print.appendChild(results.light.node.firstChild);
        d.screen.classList.add("xp-has-print");
        d.tokens.light = results.light.tokens;
      } else {
        d.screen.classList.remove("xp-has-print");
      }
      markDiagram(d);
      d.status.hidden = true;
      d.wrap.setAttribute("role", "img");
      return true;
    });
  }
  function drawDiagram(d) {
    pendingDraws += 1;
    renderQueue = renderQueue.then(function () {
      return loadMermaid().then(function (mm) {
        if (!mm) { throw new Error("The diagram library did not load. The source is shown instead."); }
        return renderOne(d, mm);
      });
    }).then(function () {
      if (d.failed) { d.failed = false; counts.failed -= 1; }
      if (!d.counted) { d.counted = true; counts.drawn += 1; }
    }, function (err) {
      var msg = String(err && err.message ? err.message : err).split("\n")[0];
      if (!d.failed) { d.failed = true; counts.failed += 1; }
      if (d.counted) { d.counted = false; counts.drawn -= 1; }
      if (failedMessages.indexOf(msg) < 0) failedMessages.push(msg);
      showDiagramFallback(d, /library did not load/.test(msg) ? msg : "This diagram could not be drawn, so its source is shown instead.");
    }).then(function () {
      pendingDraws -= 1;
      if (checkMode && resultNode) writeCheck();
    });
    return renderQueue;
  }
  function diagram(target, source) {
    var node = typeof target === "string" ? $(target) : target;
    if (!node) { note("diagram: no target"); return; }
    var pre = node.matches && node.matches("pre[data-diagram]") ? node : $("pre[data-diagram]", node);
    var d = null;
    diagrams.forEach(function (x) { if (x.pre === pre || x.wrap === node || x.wrap.contains(node)) d = x; });
    if (!d && pre) { d = setupDiagram(pre); diagrams.push(d); }
    if (!d) {
      pre = el("pre");
      pre.setAttribute("data-diagram", "");
      pre.textContent = source || "";
      node.appendChild(pre);
      d = setupDiagram(pre);
      diagrams.push(d);
    }
    if (typeof source === "string") d.source = source;
    return drawDiagram(d);
  }

  // ---- Charts
  function chartDefaults(Chart, t) {
    Chart.defaults.color = t.text;
    Chart.defaults.borderColor = t.grid;
    Chart.defaults.font.family = t.font;
    Chart.defaults.plugins.legend.labels.usePointStyle = true;
    Chart.defaults.plugins.legend.labels.color = t.text;
  }
  function themedConfig(cfgIn, t) {
    var out = Object.assign({}, cfgIn);
    var data = Object.assign({}, cfgIn.data || {});
    data.datasets = (data.datasets || []).map(function (ds, i) {
      var k = KINDS[i % KINDS.length];
      var type = ds.type || cfgIn.type || "line";
      var base = { borderColor: t.k[k].stroke, backgroundColor: t.k[k].fill, borderWidth: 2 };
      if (type === "line" || type === "scatter") {
        base.borderDash = DASHES[i % DASHES.length];
        base.pointStyle = POINTS[i % POINTS.length];
        base.pointRadius = 4;
        base.pointBackgroundColor = t.k[k].stroke;
        base.backgroundColor = t.k[k].stroke;
      }
      return Object.assign(base, ds);
    });
    out.data = data;
    var options = Object.assign({ responsive: true, maintainAspectRatio: false, animation: false }, cfgIn.options || {});
    out.options = options;
    return out;
  }
  function pointLabel(p) { return p && typeof p === "object" && !Array.isArray(p) ? p.x : p; }
  function pointValue(p) {
    if (p && typeof p === "object" && !Array.isArray(p)) return p.y;
    return p;
  }
  function buildChartTable(c) {
    var data = (c.config && c.config.data) || {};
    var sets = data.datasets || [];
    var table = el("table");
    var title = c.node.getAttribute("data-chart-title") || "Chart";
    table.appendChild(el("caption", null, title + ", as a table"));
    var head = el("tr");
    var xTitle = guardTitle(c.config);
    head.appendChild(el("th", null, xTitle));
    sets.forEach(function (ds, i) { head.appendChild(el("th", null, ds.label || ("Series " + (i + 1)))); });
    var thead = el("thead");
    thead.appendChild(head);
    table.appendChild(thead);
    var tbody = el("tbody");
    var labels = data.labels;
    var rows = [];
    if (labels && labels.length) {
      labels.forEach(function (lab, i) {
        rows.push({ label: lab, cells: sets.map(function (ds) { return pointValue((ds.data || [])[i]); }) });
      });
    } else {
      // Points with their own x values: one row for each x, with the series that have it.
      var byX = {};
      sets.forEach(function (ds, si) {
        (ds.data || []).forEach(function (p) {
          var key = String(pointLabel(p));
          if (!byX[key]) { byX[key] = { label: pointLabel(p), cells: sets.map(function () { return ""; }) }; rows.push(byX[key]); }
          byX[key].cells[si] = pointValue(p);
        });
      });
      if (rows.every(function (r) { return isNum(r.label); })) rows.sort(function (a, b) { return a.label - b.label; });
    }
    rows.forEach(function (r) {
      var tr = el("tr");
      tr.appendChild(el("th", null, r.label == null ? "" : String(r.label)));
      r.cells.forEach(function (v) { tr.appendChild(el("td", null, v == null ? "" : String(v))); });
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    var wrap = el("div", "xp-table-wrap xp-chart-table");
    wrap.appendChild(table);
    return wrap;
  }
  function guardTitle(config) {
    var s = config && config.options && config.options.scales && config.options.scales.x;
    var t = s && s.title && s.title.text;
    return t ? String(t) : ((config && config.data && config.data.labels) ? "Label" : "x");
  }
  function drawChart(c, schemeOverride) {
    return loadChart().then(function (Chart) {
      if (!Chart) {
        c.node.classList.add("xp-chart-failed");
        c.node.classList.remove("xp-chart-drawn");
        c.canvas.setAttribute("aria-hidden", "true");
        return;
      }
      var t = tokensFor(schemeOverride || currentScheme());
      chartDefaults(Chart, t);
      if (c.inst) { c.inst.destroy(); c.inst = null; }
      guard("chart", function () {
        c.inst = new Chart(c.canvas, themedConfig(c.config, t));
        c.node.classList.add("xp-chart-drawn");
        c.node.classList.remove("xp-chart-failed");
        c.canvas.setAttribute("aria-hidden", "true");
      });
    });
  }
  function chart(target, config) {
    var node = typeof target === "string" ? $(target) : target;
    if (!node) { note("chart: no target"); return null; }
    var existing = null;
    charts.forEach(function (x) { if (x.node === node) existing = x; });
    var c = existing;
    if (!c) {
      c = { node: node, config: config };
      node.textContent = "";
      node.classList.add("xp-chart");
      if (!node.hasAttribute("data-chart")) node.setAttribute("data-chart", "");
      var holder = el("div", "xp-chart-canvas");
      c.canvas = document.createElement("canvas");
      c.canvas.setAttribute("role", "img");
      c.canvas.setAttribute("aria-label", node.getAttribute("data-chart-title") || "Chart");
      holder.appendChild(c.canvas);
      node.appendChild(holder);
      c.tableHolder = el("div");
      node.appendChild(c.tableHolder);
      charts.push(c);
    }
    c.config = config;
    c.tableHolder.textContent = "";
    c.tableHolder.appendChild(buildChartTable(c));
    drawChart(c);
    return {
      update: function (next) {
        c.config = next || c.config;
        c.tableHolder.textContent = "";
        c.tableHolder.appendChild(buildChartTable(c));
        return drawChart(c);
      }
    };
  }

  // ---- Timeline
  function niceStep(span, target) {
    var raw = span / target;
    var pow = Math.pow(10, Math.floor(Math.log10(raw)));
    var f = raw / pow;
    var m = f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10;
    return m * pow;
  }
  function timeline(target, spec) {
    var node = typeof target === "string" ? $(target) : target;
    if (!node) { note("timeline: no target"); return; }
    spec = spec || {};
    var lanes = spec.lanes || [];
    var lo = Infinity;
    var hi = -Infinity;
    lanes.forEach(function (l) {
      (l.bars || []).forEach(function (b) { lo = Math.min(lo, b.start); hi = Math.max(hi, b.end); });
      (l.marks || []).forEach(function (m) { lo = Math.min(lo, m.at); hi = Math.max(hi, m.at); });
    });
    node.textContent = "";
    node.classList.add("xp-timeline");
    if (!node.hasAttribute("data-timeline")) node.setAttribute("data-timeline", "");
    if (!isFinite(lo) || !isFinite(hi)) return;
    if (lo > 0 && lo < (hi - lo)) lo = 0;
    if (hi === lo) hi = lo + 1;
    var step = niceStep(hi - lo, 6);
    var start = Math.floor(lo / step) * step;
    var end = Math.ceil(hi / step) * step;
    var span = end - start;
    function pct(x) { return ((x - start) / span * 100).toFixed(3) + "%"; }
    var root = el("div", "xp-tl");
    root.setAttribute("role", "group");
    root.setAttribute("aria-label", node.getAttribute("data-timeline-title") || "Timeline");
    lanes.forEach(function (lane) {
      var row = el("div", "xp-tl-lane");
      row.appendChild(el("div", "xp-tl-label", lane.label || ""));
      var track = el("div", "xp-tl-track");
      track.setAttribute("role", "list");
      (lane.bars || []).forEach(function (b) {
        var bar = el("div", "xp-bar", b.label || "");
        bar.setAttribute("role", "listitem");
        if (b.kind) bar.setAttribute("data-kind", b.kind);
        bar.style.left = pct(b.start);
        bar.style.width = ((b.end - b.start) / span * 100).toFixed(3) + "%";
        var text = (b.label || "") + ": " + plain(b.start, 6) + " to " + plain(b.end, 6) + (spec.unit ? " " + spec.unit : "");
        bar.title = text;
        bar.setAttribute("aria-label", text);
        track.appendChild(bar);
      });
      (lane.marks || []).forEach(function (m) {
        var pin = el("div", "xp-tl-mark");
        pin.setAttribute("role", "listitem");
        pin.style.left = pct(m.at);
        if ((m.at - start) / span > 0.65) pin.classList.add("xp-flip");
        pin.appendChild(el("span", null, m.label || ""));
        var text = (m.label || "") + " at " + plain(m.at, 6) + (spec.unit ? " " + spec.unit : "");
        pin.setAttribute("aria-label", text);
        pin.title = text;
        track.appendChild(pin);
      });
      row.appendChild(track);
      root.appendChild(row);
    });
    var axis = el("div", "xp-tl-axis");
    axis.appendChild(el("div"));
    var ticks = el("div", "xp-tl-ticks");
    ticks.setAttribute("aria-hidden", "true");
    for (var x = start; x <= end + step / 1000; x += step) {
      var tick = el("span", null, plain(Math.round(x * 1e9) / 1e9, 6));
      tick.style.left = pct(x);
      ticks.appendChild(tick);
    }
    axis.appendChild(ticks);
    if (spec.unit) axis.appendChild(el("div", "xp-tl-unit", spec.unit));
    root.appendChild(axis);
    node.appendChild(root);
  }

  // ---- Tabs
  function setupTabs() {
    $$("[data-tabs]").forEach(function (box) {
      var panels = $$(":scope > [data-tab]", box);
      if (!panels.length) return;
      var list = el("div", "xp-tablist");
      list.setAttribute("role", "tablist");
      var tabs = panels.map(function (p, i) {
        var b = el("button", "xp-tab", p.getAttribute("data-tab"));
        b.type = "button";
        b.id = uid("tab");
        b.setAttribute("role", "tab");
        p.id = p.id || uid("panel");
        b.setAttribute("aria-controls", p.id);
        p.setAttribute("role", "tabpanel");
        p.setAttribute("aria-labelledby", b.id);
        p.classList.add("xp-tabpanel");
        p.insertBefore(el("h3", "xp-tab-title", p.getAttribute("data-tab")), p.firstChild);
        list.appendChild(b);
        return b;
      });
      box.insertBefore(list, box.firstChild);
      function select(i, focus) {
        tabs.forEach(function (b, j) {
          var on = i === j;
          b.setAttribute("aria-selected", on ? "true" : "false");
          b.tabIndex = on ? 0 : -1;
          panels[j].hidden = !on;
        });
        markAll();
        if (focus) tabs[i].focus();
      }
      tabs.forEach(function (b, i) {
        b.addEventListener("click", function () { select(i, false); });
        b.addEventListener("keydown", function (e) {
          var to = -1;
          if (e.key === "ArrowRight" || e.key === "ArrowDown") to = (i + 1) % tabs.length;
          else if (e.key === "ArrowLeft" || e.key === "ArrowUp") to = (i - 1 + tabs.length) % tabs.length;
          else if (e.key === "Home") to = 0;
          else if (e.key === "End") to = tabs.length - 1;
          if (to >= 0) { e.preventDefault(); select(to, true); }
        });
      });
      select(0, false);
    });
  }

  // ---- Steps
  function setupSteps() {
    $$("[data-steps]").forEach(function (box) {
      var figs = $$(":scope > [data-step]", box);
      if (!figs.length) return;
      box.classList.add("xp-steps");
      var at = 0;
      var timer = null;
      var controls = el("div", "xp-step-controls");
      var prev = el("button", "xp-btn", "Previous");
      var next = el("button", "xp-btn", "Next");
      var play = el("button", "xp-btn", "Play");
      var status = el("span", "xp-step-status");
      status.setAttribute("role", "status");
      [prev, next, play].forEach(function (b) { b.type = "button"; });
      controls.appendChild(prev);
      controls.appendChild(next);
      if (!reducedMotion()) controls.appendChild(play);
      controls.appendChild(status);
      box.appendChild(controls);
      box.setAttribute("tabindex", "0");
      box.setAttribute("role", "group");
      if (!box.getAttribute("aria-label")) box.setAttribute("aria-label", "Steps");
      function stop() {
        if (timer) { clearInterval(timer); timer = null; }
        play.textContent = "Play";
      }
      function go(i, fade) {
        at = Math.max(0, Math.min(figs.length - 1, i));
        figs.forEach(function (f, j) {
          f.hidden = j !== at;
          f.classList.remove("xp-step-fade");
        });
        if (fade && !reducedMotion()) figs[at].classList.add("xp-step-fade");
        prev.disabled = at === 0;
        next.disabled = at === figs.length - 1;
        status.textContent = "Step " + (at + 1) + " of " + figs.length;
        markAll();
        if (at === figs.length - 1) stop();
      }
      prev.addEventListener("click", function () { stop(); go(at - 1, true); });
      next.addEventListener("click", function () { stop(); go(at + 1, true); });
      play.addEventListener("click", function () {
        if (timer) { stop(); return; }
        if (reducedMotion()) return;
        if (at === figs.length - 1) go(0, true);
        play.textContent = "Pause";
        timer = setInterval(function () { go(at + 1, true); }, 2500);
      });
      box.addEventListener("keydown", function (e) {
        if (e.target !== box) return;
        if (e.key === "ArrowRight") { e.preventDefault(); stop(); go(at + 1, true); }
        else if (e.key === "ArrowLeft") { e.preventDefault(); stop(); go(at - 1, true); }
      });
      go(0, false);
    });
  }

  // ---- Legend
  function setupLegends() {
    $$("[data-legend] > li").forEach(function (li) {
      var kind = li.getAttribute("data-kind");
      if (!kind || $(".xp-swatch", li)) return;
      var sw = el("span", "xp-swatch");
      sw.setAttribute("aria-hidden", "true");
      li.insertBefore(sw, li.firstChild);
    });
  }

  // ---- Tables
  function wrapTables() {
    $$(".xp-main table").forEach(function (t) {
      if (t.parentNode && t.parentNode.classList.contains("xp-table-wrap")) return;
      var wrap = el("div", "xp-table-wrap");
      t.parentNode.insertBefore(wrap, t);
      wrap.appendChild(t);
    });
  }

  // ---- Questions
  function radioLabel(r) {
    var l = r.closest("label");
    if (!l) return "";
    var c = l.cloneNode(true);
    $$("input,.xp-rec", c).forEach(function (x) { x.remove(); });
    return c.textContent.trim();
  }
  function setupQuestions() {
    $$("fieldset[data-question]").forEach(function (fs) {
      var q = { id: fs.getAttribute("data-question"), el: fs, kind: fs.getAttribute("data-kind") || "text",
        answer: fs.getAttribute("data-answer"), tolerance: fs.getAttribute("data-tolerance"),
        recommended: fs.getAttribute("data-recommended"), revealed: false };
      var explain = $("[data-explain]", fs);
      var name = uid("q");
      if (q.kind === "choice") {
        var radios = $$("input[type=radio]", fs);
        radios.forEach(function (r) { r.name = name; r.checked = false; r.removeAttribute("checked"); });
        radios.forEach(function (r) {
          if (q.recommended && r.value === q.recommended) {
            var l = r.closest("label");
            if (l) { l.appendChild(el("span", "xp-rec", "Recommended")); }
          }
          var l2 = r.closest("label");
          if (l2) l2.classList.add("xp-q-option");
        });
        var dk = el("label", "xp-q-option");
        q.dk = el("input");
        q.dk.type = "radio";
        q.dk.name = name;
        q.dk.value = UNKNOWN;
        dk.appendChild(q.dk);
        dk.appendChild(document.createTextNode(UNKNOWN));
        fs.appendChild(dk);
        q.field = null;
        q.radios = radios;
      } else {
        q.field = $("input, textarea", fs);
        if (!q.field) {
          q.field = q.kind === "predict" ? el("input") : el("textarea");
          if (q.kind === "predict") q.field.type = "number";
          else q.field.rows = 3;
          fs.appendChild(q.field);
        }
        if (q.field.tagName === "INPUT" && !q.field.type) q.field.type = "text";
        q.field.setAttribute("aria-label", q.field.getAttribute("aria-label") || (($("legend", fs) || {}).textContent || "Answer").trim());
        var dkl = el("label", "xp-q-option");
        q.dk = el("input");
        q.dk.type = "checkbox";
        dkl.appendChild(q.dk);
        dkl.appendChild(document.createTextNode(UNKNOWN));
        fs.appendChild(dkl);
        q.dk.addEventListener("change", function () {
          q.field.disabled = q.dk.checked;
          if (q.dk.checked) q.field.value = "";
        });
      }
      q.explain = explain;
      if (explain) explain.hidden = true;
      var reveals = !!(explain || q.answer != null);
      q.feedback = el("p", "xp-feedback");
      q.feedback.hidden = true;
      q.feedback.setAttribute("role", "status");
      if (reveals) {
        if (q.kind !== "choice") {
          var actions = el("div", "xp-q-actions");
          q.reveal = el("button", "xp-btn", "Reveal the answer");
          q.reveal.type = "button";
          q.reveal.addEventListener("click", function () { q.revealed = true; updateQuestions(); save(); });
          actions.appendChild(q.reveal);
          fs.appendChild(actions);
        }
        fs.appendChild(q.feedback);
        if (explain) fs.appendChild(explain);
      }
      q.reveals = reveals;
      questions.push(q);
    });
  }
  function questionAnswer(q) {
    if (q.kind === "choice") {
      if (q.dk.checked) return UNKNOWN;
      var r = q.radios.filter(function (x) { return x.checked; })[0];
      if (!r) return null;
      var label = radioLabel(r);
      return /^[A-Za-z]$/.test(r.value) && label ? r.value + " " + label.replace(/^[A-Za-z]\s+/, "") : r.value;
    }
    if (q.dk.checked) return UNKNOWN;
    var v = (q.field.value || "").replace(/\s*\n\s*/g, " ").trim();
    return v === "" ? null : v;
  }
  function updateQuestions() {
    questions.forEach(function (q) {
      var a = questionAnswer(q);
      if (q.kind === "choice" && q.reveals && a !== null) q.revealed = true;
      if (!q.reveals) return;
      if (q.reveal) q.reveal.disabled = a === null;
      var show1 = q.revealed && a !== null;
      if (q.explain) q.explain.hidden = !show1;
      q.feedback.hidden = !show1;
      if (!show1) return;
      if (q.answer == null) { q.feedback.textContent = "Answer recorded."; q.feedback.removeAttribute("data-result"); return; }
      var match = false;
      if (a !== UNKNOWN) {
        if (q.kind === "predict") {
          var x = Number(String(a));
          var y = Number(q.answer);
          var tol = q.tolerance == null ? 0 : Number(q.tolerance);
          match = isFinite(x) && isFinite(y) && Math.abs(x - y) <= (isFinite(tol) ? tol : 0);
        } else if (q.kind === "choice") {
          var r = q.radios.filter(function (z) { return z.checked; })[0];
          match = !!r && r.value === q.answer;
        } else {
          match = String(a).toLowerCase() === String(q.answer).trim().toLowerCase();
        }
      }
      q.feedback.setAttribute("data-result", match ? "match" : "differs");
      q.feedback.textContent = match ? "Your answer matches: " + q.answer + "." : "The answer is " + q.answer + ".";
    });
  }

  // ---- Reply
  function oneLine(s) { return String(s).replace(/\s*[\r\n]+\s*/g, " ").trim(); }
  function buildReply() {
    var lines = ["explorable " + (cfg.id || "page") + " built " + (cfg.built || "unknown")];
    briefChoices.forEach(function (b) {
      var r = $$("input[type=radio]", b.el).filter(function (x) { return x.checked; })[0];
      if (!r) lines.push("choice " + b.id + ": none");
      else {
        var opt = b.options.filter(function (o) { return o.letter === r.value; })[0];
        lines.push("choice " + b.id + ": " + r.value + (opt && opt.way ? " " + oneLine(opt.way) : ""));
      }
    });
    var v = values();
    inputs.forEach(function (rec) {
      if (rawText(v[rec.name]) === rawText(defaultValues[rec.name])) return;
      lines.push("input " + rec.name + ": " + rawText(defaultValues[rec.name]) + " -> " + withUnit(rawText(v[rec.name]), rec.unit));
    });
    questions.forEach(function (q) {
      var a = questionAnswer(q);
      lines.push("answer " + q.id + ": " + (a === null ? "none" : oneLine(a)));
    });
    if (noteEl && noteEl.value.trim()) {
      noteEl.value.split(/\r?\n/).forEach(function (l) { if (l.trim()) lines.push("note: " + l.trim()); });
    }
    return lines.join("\n");
  }
  function updateReply() {
    if (replyEl) replyEl.textContent = buildReply();
  }
  function copyText(text) {
    function fallback() {
      var ta = document.createElement("textarea");
      ta.value = text;
      ta.setAttribute("readonly", "");
      ta.className = "xp-sr";
      document.body.appendChild(ta);
      ta.select();
      var ok = false;
      try { ok = document.execCommand("copy"); } catch (err) { ok = false; }
      ta.remove();
      if (!ok) {
        try {
          var range = document.createRange();
          range.selectNodeContents(replyEl);
          var sel = window.getSelection();
          sel.removeAllRanges();
          sel.addRange(range);
        } catch (err2) { /* nothing more to try */ }
      }
      return ok;
    }
    var p = null;
    try { p = navigator.clipboard && navigator.clipboard.writeText ? navigator.clipboard.writeText(text) : null; } catch (err) { p = null; }
    if (p && p.then) {
      return p.then(function () { return true; }, function () { return fallback(); });
    }
    return Promise.resolve(fallback());
  }
  function setupReply() {
    var section = document.getElementById("explorable-reply");
    if (!section) return;
    var body = el("div", "xp-reply-body");
    body.appendChild(el("p", null, "Copy this reply and paste it back to the agent. Nothing leaves this page on its own."));
    (cfg.briefs || []).forEach(function (b) {
      var fs = el("fieldset", "xp-choice");
      fs.setAttribute("data-choice", b.id);
      fs.appendChild(el("legend", null, "Your choice for " + b.id + (b.heading ? ": " + b.heading : "")));
      var gname = uid("choice");
      (b.options || []).forEach(function (o) {
        var label = el("label");
        var r = el("input");
        r.type = "radio";
        r.name = gname;
        r.value = o.letter;
        label.appendChild(r);
        label.appendChild(el("span", "xp-letter", o.letter));
        label.appendChild(document.createTextNode(" " + (o.way || "")));
        if (b.recommend && b.recommend === o.letter) label.appendChild(el("span", "xp-rec", "Recommended"));
        fs.appendChild(label);
      });
      body.appendChild(fs);
      briefChoices.push({ id: b.id, el: fs, options: b.options || [] });
    });
    var nl = el("label", "xp-note-label", "Note for the agent (optional)");
    noteEl = el("textarea");
    noteEl.rows = 3;
    nl.appendChild(noteEl);
    body.appendChild(nl);
    replyEl = el("pre", "xp-reply-text");
    replyEl.tabIndex = 0;
    replyEl.setAttribute("aria-label", "Reply text");
    body.appendChild(replyEl);
    var actions = el("div", "xp-actions");
    var copy = el("button", "xp-btn xp-primary", "Copy reply");
    copy.type = "button";
    var restore = el("button", "xp-btn", "Restore the agent’s values");
    restore.type = "button";
    var forget = el("button", "xp-btn", "Forget what I entered");
    forget.type = "button";
    statusEl = el("span", "xp-copy-status");
    statusEl.setAttribute("role", "status");
    actions.appendChild(copy);
    actions.appendChild(restore);
    actions.appendChild(forget);
    actions.appendChild(statusEl);
    body.appendChild(actions);
    section.appendChild(body);
    copy.addEventListener("click", function () {
      copyText(replyEl.textContent).then(function (ok) {
        statusEl.textContent = ok ? "Copied." : "Copy did not work. The reply text is selected: press Ctrl+C or Cmd+C.";
      });
    });
    restore.addEventListener("click", function () {
      inputs.forEach(function (rec) { writeInput(rec, defaultValues[rec.name]); });
      lastSig = sig();
      runHandlers();
      refreshAll();
      statusEl.textContent = "The agent’s values are back.";
    });
    // Chrome lets every page opened from disk read one shared local storage, so a person can
    // clear what they entered once the reply is copied.
    forget.addEventListener("click", function () {
      restoring = true;
      inputs.forEach(function (rec) { writeInput(rec, defaultValues[rec.name]); });
      briefChoices.forEach(function (b) {
        $$("input[type=radio]", b.el).forEach(function (r) { r.checked = false; });
      });
      questions.forEach(function (q) {
        if (q.dk) q.dk.checked = false;
        if (q.radios) q.radios.forEach(function (r) { r.checked = false; });
        if (q.field) { q.field.value = ""; q.field.disabled = false; }
        q.revealed = false;
      });
      if (noteEl) noteEl.value = "";
      restoring = false;
      lastSig = sig();
      runHandlers();
      refreshAll();
      if (storageKey) {
        try { localStorage.removeItem(storageKey); } catch (err) { /* storage may be refused */ }
      }
      statusEl.textContent = "What you entered is gone from this page and from the browser’s storage.";
    });
    section.addEventListener("input", refreshAll);
    section.addEventListener("change", refreshAll);
  }

  // ---- Saved state
  function snapshot() {
    var st = { inputs: {}, choices: {}, answers: {}, revealed: {}, note: noteEl ? noteEl.value : "" };
    inputs.forEach(function (rec) { st.inputs[rec.name] = readInput(rec); });
    briefChoices.forEach(function (b) {
      var r = $$("input[type=radio]", b.el).filter(function (x) { return x.checked; })[0];
      st.choices[b.id] = r ? r.value : null;
    });
    questions.forEach(function (q) {
      st.answers[q.id] = q.kind === "choice"
        ? (q.dk.checked ? UNKNOWN : (q.radios.filter(function (x) { return x.checked; })[0] || {}).value || null)
        : { v: q.field.value, dk: q.dk.checked };
      st.revealed[q.id] = q.revealed;
    });
    return st;
  }
  function save() {
    if (restoring || checkMode || !storageKey) return;
    try { localStorage.setItem(storageKey, JSON.stringify(snapshot())); } catch (err) { /* storage may be refused */ }
  }
  function restore() {
    if (checkMode || !storageKey) return;
    var st = null;
    try { st = JSON.parse(localStorage.getItem(storageKey) || "null"); } catch (err) { st = null; }
    if (!st || typeof st !== "object") return;
    restoring = true;
    guard("restore", function () {
      inputs.forEach(function (rec) {
        if (st.inputs && Object.prototype.hasOwnProperty.call(st.inputs, rec.name)) writeInput(rec, st.inputs[rec.name]);
      });
      briefChoices.forEach(function (b) {
        var want = st.choices ? st.choices[b.id] : null;
        $$("input[type=radio]", b.el).forEach(function (r) { r.checked = want != null && r.value === want; });
      });
      questions.forEach(function (q) {
        var a = st.answers ? st.answers[q.id] : null;
        if (a == null) return;
        if (q.kind === "choice") {
          q.dk.checked = a === UNKNOWN;
          q.radios.forEach(function (r) { r.checked = a !== UNKNOWN && r.value === a; });
        } else if (typeof a === "object") {
          q.field.value = a.v || "";
          q.dk.checked = !!a.dk;
          q.field.disabled = !!a.dk;
        }
        if (st.revealed && st.revealed[q.id]) q.revealed = true;
      });
      if (noteEl && typeof st.note === "string") noteEl.value = st.note;
    });
    restoring = false;
  }

  // ---- Theme changes and print
  function redrawAll() {
    diagrams.forEach(function (d) { if (!d.failed || libs.mermaid === "loaded") drawDiagram(d); });
    charts.forEach(function (c) { if (libs.chart === "loaded") drawChart(c); });
  }
  function onScheme() {
    redrawAll();
    themeFns.forEach(function (fn) { guard("onTheme", function () { fn(theme()); }); });
  }
  function beforePrint() {
    if (currentScheme() !== "dark") return;
    charts.forEach(function (c) {
      if (libs.chart !== "loaded" || !c.inst) return;
      guard("print", function () {
        var Chart = window[(cfg.libraries.chart || {}).global || "Chart"];
        var t = tokensFor("light");
        chartDefaults(Chart, t);
        c.inst.destroy();
        c.inst = new Chart(c.canvas, themedConfig(c.config, t));
      });
    });
  }
  function afterPrint() {
    if (currentScheme() !== "dark") return;
    charts.forEach(function (c) { if (libs.chart === "loaded") drawChart(c); });
  }

  // ---- Start
  function whenStarted(fn) {
    if (started) fn(); else readyFns.push(fn);
  }
  function ready(fn) { if (typeof fn === "function") { if (started) guard("ready", fn); else readyFns.push(fn); } }
  function onChange(fn) {
    if (typeof fn !== "function") return;
    changeFns.push(fn);
    if (started) guard("onChange", function () { fn(values()); });
  }

  function start() {
    guard("start", function () {
      $$("pre[data-diagram]").forEach(function (pre) { diagrams.push(setupDiagram(pre)); });
      decorateInputs();
      setupTabs();
      setupSteps();
      setupLegends();
      setupQuestions();
      wrapTables();
      setupReply();
      storageKey = "explorable:" + (cfg.id || "page") + ":" + (cfg.built || "");
      restore();
    });
    started = true;
    var queued = readyFns;
    readyFns = [];
    queued.forEach(function (fn) { guard("ready", fn); });
    lastSig = sig();
    runHandlers();
    refreshAll();
    diagrams.forEach(function (d) { drawDiagram(d); });
    if (mq) {
      if (mq.addEventListener) mq.addEventListener("change", onScheme);
      else if (mq.addListener) mq.addListener(onScheme);
    }
    document.addEventListener("input", inputEvent);
    document.addEventListener("change", inputEvent);
    window.addEventListener("beforeprint", beforePrint);
    window.addEventListener("afterprint", afterPrint);
    if (checkMode) {
      var results = runExpectations();
      lastResults = results;
      refreshAll();
      writeCheck();
      // Library and diagram states may still change after this; the node is refreshed when they do.
      var tries = 0;
      var poll = setInterval(function () {
        tries += 1;
        writeCheck();
        if ((pendingDraws === 0 && libs.chart !== "loading" && libs.mermaid !== "loading") || tries > 120) clearInterval(poll);
      }, 250);
    }
  }

  window.explorable = {
    ready: ready,
    onChange: onChange,
    values: values,
    defaults: defaults,
    show: show,
    chart: function (t, c) { var h = null; var wrap = { update: function (n) { return h ? h.update(n) : undefined; } }; whenStarted(function () { h = chart(t, c); }); return wrap; },
    diagram: function (t, s) { whenStarted(function () { diagram(t, s); }); },
    timeline: function (t, s) { whenStarted(function () { timeline(t, s); }); },
    threshold: threshold,
    expect: expect,
    theme: theme,
    onTheme: onTheme
  };

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
})();
