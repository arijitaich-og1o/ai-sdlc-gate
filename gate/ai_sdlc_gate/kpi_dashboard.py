"""Static, self-contained KPI dashboard (one HTML file, data embedded, no external scripts).

Untrusted text in the data (repository names, branch names, skip reasons) is embedded as JSON with `</` escaped so
it cannot close the script tag, and the page only ever writes it with textContent, never innerHTML.
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
from typing import Any

_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="__CSP__">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AI SDLC Gate KPIs</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Lexend:wght@400;600;700&family=Source+Sans+3:wght@400;600&display=swap" rel="stylesheet">
<style>
  :root {
    --purple: #434098; --red: #EB001F; --lilac: #EDECFC; --ink: #1d1b3a; --muted: #5d5b7a;
    --line: #d9d7f0; --card: #ffffff; --bg: #f7f7fc; --good: #1f8a4c; --warn: #b26b00;
  }
  * { box-sizing: border-box; }
  body { margin: 0; background: var(--bg); color: var(--ink); font: 15px/1.45 "Source Sans 3", system-ui, sans-serif; }
  header { background: var(--purple); color: #fff; padding: 20px 24px 18px; }
  header h1 { font: 700 22px/1.2 Lexend, system-ui, sans-serif; margin: 0 0 4px; }
  header p { margin: 0; opacity: .85; }
  .bar { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; padding: 12px 24px; background: var(--lilac); border-bottom: 1px solid var(--line); }
  .bar label { font-weight: 600; }
  .bar select { font: inherit; padding: 4px 8px; border: 1px solid var(--line); border-radius: 6px; background: #fff; }
  main { padding: 20px 24px 32px; max-width: 1280px; margin: 0 auto; }
  h2 { font: 600 16px/1.3 Lexend, system-ui, sans-serif; color: var(--purple); margin: 26px 0 10px; }
  .tiles { display: grid; grid-template-columns: repeat(auto-fill, minmax(210px, 1fr)); gap: 12px; }
  .tile { background: var(--card); border: 1px solid var(--line); border-radius: 10px; padding: 14px 16px; border-top: 4px solid var(--purple); }
  .tile .k { font-size: 13px; color: var(--muted); font-weight: 600; }
  .tile .v { font: 700 28px/1.2 Lexend, system-ui, sans-serif; margin: 4px 0; }
  .tile .d { font-size: 13px; color: var(--muted); }
  .tile.na .v { color: var(--muted); font-size: 18px; }
  .grid2 { display: grid; grid-template-columns: repeat(auto-fit, minmax(380px, 1fr)); gap: 16px; }
  .panel { background: var(--card); border: 1px solid var(--line); border-radius: 10px; padding: 14px 16px; overflow-x: auto; }
  .panel h3 { font: 600 14px/1.3 Lexend, system-ui, sans-serif; margin: 0 0 8px; }
  .legend { display: flex; gap: 14px; font-size: 13px; color: var(--muted); margin-bottom: 4px; }
  .legend i { display: inline-block; width: 12px; height: 3px; vertical-align: middle; margin-right: 5px; }
  .legend .sw-purple { background: var(--purple); }
  .legend .sw-red { background: var(--red); }
  .legend .sw-bar { background: var(--lilac); height: 10px; border: 1px solid var(--purple); }
  svg text { font: 12px "Source Sans 3", system-ui, sans-serif; fill: var(--muted); }
  table { border-collapse: collapse; width: 100%; font-size: 14px; }
  th, td { text-align: left; padding: 6px 8px; border-bottom: 1px solid var(--line); vertical-align: top; }
  th { color: var(--muted); font-weight: 600; }
  .note { font-size: 13px; color: var(--muted); }
  .warn { color: var(--warn); }
  footer { max-width: 1280px; margin: 0 auto; padding: 0 24px 32px; font-size: 13px; color: var(--muted); }
  @media (max-width: 520px) { header, .bar, main { padding-left: 16px; padding-right: 16px; } .grid2 { grid-template-columns: 1fr; } }
</style>
</head>
<body>
<header>
  <h1>AI SDLC Gate: delivery quality KPIs</h1>
  <p id="period"></p>
</header>
<div class="bar">
  <label for="scope">Scope</label>
  <select id="scope"></select>
  <span class="note" id="scopenote"></span>
</div>
<main>
  <h2>Quality, speed, risk and cost</h2>
  <div class="tiles" id="tiles"></div>

  <h2>Trends (all repositories, by ISO week)</h2>
  <div class="grid2">
    <div class="panel"><h3>Gate pass rate and block rate</h3><div class="legend"><span><i class="sw-purple"></i>pass rate</span><span><i class="sw-red"></i>block rate</span></div><div id="trendRates"></div></div>
    <div class="panel"><h3>Gate runs and blocking findings per run</h3><div class="legend"><span><i class="sw-bar"></i>runs</span><span><i class="sw-red"></i>blocker + high per run</span></div><div id="trendRuns"></div></div>
  </div>

  <h2>Where quality is lost</h2>
  <div class="grid2">
    <div class="panel"><h3>Fail rate by SDLC phase</h3><div id="phases"></div></div>
    <div class="panel"><h3>Most frequent finding categories</h3><div id="cats"></div></div>
  </div>

  <h2>Value and trust</h2>
  <div class="grid2">
    <div class="panel"><h3>Time saved estimate (net of gate waiting time)</h3><div id="saved"></div></div>
    <div class="panel"><h3>False-positive rate by phase (developer triage)</h3><div id="fpphase"></div></div>
  </div>

  <h2>Exceptions and data quality</h2>
  <div class="grid2">
    <div class="panel"><h3>Skip requests (SDLC-Skip trailers)</h3><div id="skips"></div></div>
    <div class="panel"><h3>Data coverage</h3><div id="coverage"></div></div>
  </div>
</main>
<footer id="footer">
  These KPIs describe the delivery system, not people. Compare a team or repository with its own history; do not
  rank teams or developers against each other. Definitions and formulas: docs/kpi/README.md.
</footer>
<script id="kpi-data" type="application/json">__KPI_DATA__</script>
<script>
(function () {
  "use strict";
  var DATA = JSON.parse(document.getElementById("kpi-data").textContent);
  var S = DATA.summary;
  var NS = "http://www.w3.org/2000/svg";
  var PHASES = {"1": "Planning", "2": "Requirements", "3": "Design", "4": "Development", "5": "Testing", "6": "Deployment", "7": "Maintenance", "8": "Security"};

  function el(tag, attrs, text) {
    var e = document.createElement(tag);
    for (var k in (attrs || {})) e.setAttribute(k, attrs[k]);
    if (text !== undefined && text !== null) e.textContent = String(text);
    return e;
  }
  function svgEl(tag, attrs, text) {
    var e = document.createElementNS(NS, tag);
    for (var k in (attrs || {})) e.setAttribute(k, attrs[k]);
    if (text !== undefined) e.textContent = String(text);
    return e;
  }
  function pct(x) { return x === null || x === undefined ? null : Math.round(x * 1000) / 10 + "%"; }
  function num(x, d) { return x === null || x === undefined ? null : Number(x).toFixed(d === undefined ? 1 : d); }
  function clear(id) { var n = document.getElementById(id); while (n.firstChild) n.removeChild(n.firstChild); return n; }

  var TILES = [
    ["gate_pass_rate", "Gate pass rate", pct, "Runs that passed every required phase."],
    ["first_time_right_rate", "First-time-right", pct, "Branches whose first gate run passed."],
    ["block_rate", "Block rate", pct, "Runs stopped by a high or blocker finding."],
    ["blocking_findings_per_run", "Blocking findings / run", function (x) { return num(x, 2); }, "Blocker + high findings per gate run."],
    ["security_critical_run_rate", "Security-critical runs", pct, "Runs with a secret, credential or vulnerable dependency."],
    ["time_to_green_hours_median", "Median time to green", function (x) { return x === null ? null : num(x, 1) + " h"; }, "From a blocked run to the next passing run on a branch."],
    ["skip_granted_rate", "Skip rate", pct, "Runs with a valid SDLC-Skip waiver."],
    ["unverified_finding_share", "Unverified findings", pct, "Findings without evidence in the file (gate precision signal)."],
    ["gate_latency_s_p50", "Gate latency p50 / p90", null, "Review time per run, seconds."],
    ["tokens_per_run", "Tokens / run", function (x) { return x === null ? null : Math.round(x).toLocaleString("en"); }, "Model tokens per metered run (cost driver)."],
    ["blocking_findings_per_kloc", "Blocking findings / 1k lines", function (x) { return num(x, 2); }, "Blocker + high per 1,000 changed lines (runs that report size)."],
    ["time_saved", "Est. time saved / run", null, "Net developer hours per gate run: defects fixed before merge minus waiting for the gate."],
    ["false_positives", "False-positive rate", null, "Share of triaged findings labelled false positive."]
  ];
  var NA_REASON = {
    first_time_right_rate: "no run with a known repository and branch",
    time_to_green_hours_median: "no blocked branch has turned green yet",
    unverified_finding_share: "no findings in scope",
    tokens_per_run: "no run reported token usage",
    blocking_findings_per_kloc: "no run reports changed lines yet (engines from this release on do)",
    time_saved: "no gate runs in scope"
  };

  function renderTiles(k) {
    var box = clear("tiles");
    TILES.forEach(function (t) {
      var value;
      if (t[0] === "gate_latency_s_p50") {
        value = k.gate_latency_s_p50 === null ? null : num(k.gate_latency_s_p50, 0) + " / " + num(k.gate_latency_s_p90, 0) + " s";
      } else if (t[0] === "time_saved") {
        value = k.time_saved.net_hours_per_run === null ? null : num(k.time_saved.net_hours_per_run, 2) + " h";
      } else if (t[0] === "false_positives") {
        value = pct(k.false_positives.rate);
        if (value === null) NA_REASON.false_positives = "insufficient data (" + k.false_positives.labels + " of " + S.min_triage_labels + " labels needed)";
      } else {
        value = t[2](k[t[0]]);
      }
      var tile = el("div", {"class": "tile" + (value === null ? " na" : "")});
      tile.appendChild(el("div", {"class": "k"}, t[1]));
      tile.appendChild(el("div", {"class": "v"}, value === null ? "n/a" : value));
      var desc = value === null ? "Not available: " + (NA_REASON[t[0]] || "not enough data") : t[3];
      // Small samples are flagged, so a median over two recoveries is not read as a trend.
      if (value !== null && t[0] === "time_to_green_hours_median") desc += " Based on " + k.time_to_green_recoveries + " recover" + (k.time_to_green_recoveries === 1 ? "y." : "ies.");
      if (value !== null && t[0] === "first_time_right_rate") desc += " " + k.first_time_right_branches + " branches.";
      if (value !== null && t[0] === "time_saved") desc += " Estimate; precision " + k.time_saved.precision_source + ".";
      if (value !== null && t[0] === "false_positives") desc += " " + k.false_positives.labels + " labels.";
      tile.appendChild(el("div", {"class": "d"}, desc));
      box.appendChild(tile);
    });
  }

  function lineChart(id, weeks, series, maxY, fmt) {
    var box = clear(id), W = 520, H = 220, L = 44, R = 12, T = 10, B = 34;
    var svg = svgEl("svg", {viewBox: "0 0 " + W + " " + H, width: "100%", role: "img"});
    var n = weeks.length, x = function (i) { return L + (n <= 1 ? (W - L - R) / 2 : i * (W - L - R) / (n - 1)); };
    var y = function (v) { return T + (H - T - B) * (1 - v / maxY); };
    for (var g = 0; g <= 4; g++) {
      var gv = maxY * g / 4;
      svg.appendChild(svgEl("line", {x1: L, x2: W - R, y1: y(gv), y2: y(gv), stroke: "#d9d7f0"}));
      svg.appendChild(svgEl("text", {x: L - 6, y: y(gv) + 4, "text-anchor": "end"}, fmt(gv)));
    }
    weeks.forEach(function (w, i) {
      if (n <= 8 || i % Math.ceil(n / 8) === 0) svg.appendChild(svgEl("text", {x: x(i), y: H - 12, "text-anchor": "middle"}, w.replace(/^\d{4}-/, "")));
    });
    series.forEach(function (s) {
      var pts = [];
      s.values.forEach(function (v, i) { if (v !== null) pts.push([x(i), y(v)]); });
      if (pts.length > 1) svg.appendChild(svgEl("polyline", {points: pts.map(function (p) { return p.join(","); }).join(" "), fill: "none", stroke: s.color, "stroke-width": 2.5}));
      pts.forEach(function (p) { svg.appendChild(svgEl("circle", {cx: p[0], cy: p[1], r: 3.5, fill: s.color})); });
    });
    box.appendChild(svg);
  }

  function barsAndLine(id, weeks, bars, line) {
    var box = clear(id), W = 520, H = 220, L = 44, R = 44, T = 10, B = 34;
    var svg = svgEl("svg", {viewBox: "0 0 " + W + " " + H, width: "100%", role: "img"});
    var n = Math.max(weeks.length, 1), bw = (W - L - R) / n;
    var maxB = Math.max.apply(null, bars.concat([1])), maxL = Math.max.apply(null, line.filter(function (v) { return v !== null; }).concat([1]));
    var yb = function (v) { return T + (H - T - B) * (1 - v / maxB); }, yl = function (v) { return T + (H - T - B) * (1 - v / maxL); };
    svg.appendChild(svgEl("text", {x: L - 6, y: yb(maxB) + 4, "text-anchor": "end"}, maxB));
    svg.appendChild(svgEl("text", {x: W - R + 6, y: yl(maxL) + 4}, maxL.toFixed(1)));
    svg.appendChild(svgEl("line", {x1: L, x2: W - R, y1: yb(0), y2: yb(0), stroke: "#d9d7f0"}));
    weeks.forEach(function (w, i) {
      svg.appendChild(svgEl("rect", {x: L + i * bw + bw * 0.15, y: yb(bars[i]), width: bw * 0.7, height: yb(0) - yb(bars[i]), fill: "#EDECFC", stroke: "#434098"}));
      if (n <= 8 || i % Math.ceil(n / 8) === 0) svg.appendChild(svgEl("text", {x: L + i * bw + bw / 2, y: H - 12, "text-anchor": "middle"}, w.replace(/^\d{4}-/, "")));
    });
    var pts = [];
    line.forEach(function (v, i) { if (v !== null) pts.push([L + i * bw + bw / 2, yl(v)]); });
    if (pts.length > 1) svg.appendChild(svgEl("polyline", {points: pts.map(function (p) { return p.join(","); }).join(" "), fill: "none", stroke: "#EB001F", "stroke-width": 2.5}));
    pts.forEach(function (p) { svg.appendChild(svgEl("circle", {cx: p[0], cy: p[1], r: 3.5, fill: "#EB001F"})); });
    box.appendChild(svg);
  }

  function hbars(id, items, fmt, color) {
    var box = clear(id);
    if (!items.length) { box.appendChild(el("p", {"class": "note"}, "No data in this scope.")); return; }
    var W = 520, rowH = 26, L = 170, R = 60, H = items.length * rowH + 6;
    var max = Math.max.apply(null, items.map(function (it) { return it[1]; }).concat([1e-9]));
    var svg = svgEl("svg", {viewBox: "0 0 " + W + " " + H, width: "100%", role: "img"});
    items.forEach(function (it, i) {
      var y = 3 + i * rowH, w = (W - L - R) * it[1] / max;
      svg.appendChild(svgEl("text", {x: L - 8, y: y + 16, "text-anchor": "end"}, it[0]));
      svg.appendChild(svgEl("rect", {x: L, y: y + 4, width: Math.max(w, 1), height: rowH - 10, rx: 3, fill: color}));
      svg.appendChild(svgEl("text", {x: L + w + 6, y: y + 16}, fmt(it[1])));
    });
    box.appendChild(svg);
  }

  function renderScope(name) {
    var k = name === "__all__" ? S.overall : S.repos[name];
    renderTiles(k);
    document.getElementById("scopenote").textContent = k.runs + " gate runs in scope";
    var phases = Object.keys(k.phase_fail_rate).filter(function (p) { return k.phase_fail_rate[p] !== null; })
      .map(function (p) { return [p + " " + (PHASES[p] || ""), k.phase_fail_rate[p]]; });
    hbars("phases", phases, function (v) { return pct(v); }, "#434098");
    // The JSON is written with sorted keys, so order by count here (ties alphabetically, for a stable picture).
    var cats = Object.keys(k.top_categories).map(function (c) { return [c, k.top_categories[c]]; })
      .sort(function (a, b) { return b[1] - a[1] || (a[0] < b[0] ? -1 : 1); });
    hbars("cats", cats, function (v) { return v; }, "#EB001F");
    renderSaved(k.time_saved);
    renderFp(k.false_positives);
  }

  function table(id, rows, head) {
    var box = clear(id), t = el("table");
    if (head) { var hr = el("tr"); head.forEach(function (h) { hr.appendChild(el("th", {}, h)); }); t.appendChild(hr); }
    rows.forEach(function (r) {
      var tr = el("tr");
      r.forEach(function (c, i) { tr.appendChild(el("td", i === r.length - 1 && r.length > 2 ? {"class": "note"} : {}, c)); });
      t.appendChild(tr);
    });
    box.appendChild(t);
    return box;
  }

  function renderSaved(ts) {
    var a = ts.assumptions;
    var box = table("saved", [
      ["Blocking findings caught (once per blocked streak)", String(ts.caught_blocking_findings), "Lower bound: attributable branches only."],
      ["Precision applied", pct(ts.precision), ts.precision_source],
      ["Fix cost before / after merge", a.fix_hours_pre_merge + " h / " + a.fix_hours_post_merge + " h", "Assumption (5x escalation)."],
      ["Gross hours saved", num(ts.gross_hours, 1) + " h", "caught x precision x (after - before)"],
      ["Developer time waiting for the gate", num(ts.gate_wait_hours, 1) + " h", "Sum of gate run durations."],
      ["Net hours saved", num(ts.net_hours, 1) + " h", "gross - waiting"]
    ]);
    box.appendChild(el("p", {"class": "note"}, "An estimate, not a measurement: human review time saved needs PR review data the gate does not collect yet (see docs/kpi/README.md)."));
  }

  function renderFp(fp) {
    var phases = Object.keys(fp.by_phase);
    if (!phases.length) {
      clear("fpphase").appendChild(el("p", {"class": "note"},
        "Insufficient data: no findings triaged yet. Developers label findings with `ai-sdlc-gate triage`; a rate is shown from " + S.min_triage_labels + " labels per group."));
      return;
    }
    table("fpphase", phases.map(function (p) {
      var g = fp.by_phase[p];
      return [p + " " + (PHASES[p] || ""), g.rate === null ? "insufficient data" : pct(g.rate), g.labels + " labels"];
    }), ["Phase", "False-positive rate", "Sample"]);
  }

  // Header, scope selector, trends.
  var runs = S.overall.runs;
  document.getElementById("period").textContent = runs
    ? "Period " + S.period.from.slice(0, 10) + " to " + S.period.to.slice(0, 10) + "  ·  " + runs + " gate runs  ·  " + Object.keys(S.repos).length + " repositories"
    : "No gate runs in the dataset.";
  var scope = document.getElementById("scope");
  scope.appendChild(el("option", {value: "__all__"}, "All repositories"));
  Object.keys(S.repos).forEach(function (r) { scope.appendChild(el("option", {value: r}, r + " (" + S.repos[r].runs + ")")); });
  scope.addEventListener("change", function () { renderScope(scope.value); });

  var weeks = Object.keys(S.weeks);
  lineChart("trendRates", weeks, [
    {color: "#434098", values: weeks.map(function (w) { return S.weeks[w].gate_pass_rate; })},
    {color: "#EB001F", values: weeks.map(function (w) { return S.weeks[w].block_rate; })}
  ], 1, function (v) { return Math.round(v * 100) + "%"; });
  barsAndLine("trendRuns", weeks, weeks.map(function (w) { return S.weeks[w].runs; }), weeks.map(function (w) { return S.weeks[w].blocking_findings_per_run; }));

  var sk = clear("skips");
  if (!S.skip_reasons.length) {
    sk.appendChild(el("p", {"class": "note"}, "No skip requests in the period."));
  } else {
    var t = el("table"), hr = el("tr");
    ["Date", "Repository", "Phases", "Reason"].forEach(function (h) { hr.appendChild(el("th", {}, h)); });
    t.appendChild(hr);
    S.skip_reasons.slice(-12).reverse().forEach(function (s) {
      var tr = el("tr");
      tr.appendChild(el("td", {}, s.ts.slice(0, 10)));
      tr.appendChild(el("td", {}, s.repo));
      tr.appendChild(el("td", {}, s.phases.join(", ") || "-"));
      tr.appendChild(el("td", {}, s.reason || "(no reason)"));
      t.appendChild(tr);
    });
    sk.appendChild(t);
  }

  var o = S.overall, cov = clear("coverage"), ct = el("table");
  [
    ["Runs attributable to a repository and branch", pct(o.attributable_share), "Needed for first-time-right and time to green."],
    ["Runs reporting token usage", pct(o.token_metered_share), "Needed for the cost KPI."],
    ["Runs reporting changed lines", o.sized_run_share ? pct(o.sized_run_share) : "missing", "Needed to normalise findings per 1,000 changed lines (engines from this release on)."],
    ["Findings triaged by developers", o.false_positives.labels ? String(o.false_positives.labels) + " labels" : "not tracked", "Needed for the false-positive rate; the unverified share is an automatic lower bound."]
  ].forEach(function (r) {
    var tr = el("tr");
    tr.appendChild(el("td", {}, r[0]));
    tr.appendChild(el("td", {"class": (r[1] === "missing" || r[1] === "not tracked") ? "warn" : ""}, r[1] === null ? "n/a" : r[1]));
    tr.appendChild(el("td", {"class": "note"}, r[2]));
    ct.appendChild(tr);
  });
  cov.appendChild(ct);

  renderScope("__all__");
})();
</script>
</body>
</html>
"""


def _sha256(text: str) -> str:
    return "'sha256-" + base64.b64encode(hashlib.sha256(text.encode("utf-8")).digest()).decode("ascii") + "'"


def content_security_policy(template: str = _TEMPLATE) -> str:
    """Defence in depth on top of the escaping: the page may run only its own inline script and stylesheet (pinned
    by hash, so no 'unsafe-inline'), load fonts from Google Fonts and nothing else; no network calls, no forms, no
    <base>. The JSON data block is not executed, so it needs no allowance. Hashes come from the template itself,
    so they cannot go stale when the page changes."""
    style = re.search(r"<style>(.*?)</style>", template, re.S).group(1)
    script = re.search(r"<script>(.*?)</script>", template, re.S).group(1)
    return "; ".join([
        "default-src 'none'",
        f"script-src {_sha256(script)}",
        f"style-src {_sha256(style)} https://fonts.googleapis.com",
        "font-src https://fonts.gstatic.com",
        "img-src 'none'",
        "connect-src 'none'",
        "base-uri 'none'",
        "form-action 'none'",
    ])


def render_dashboard(summary: dict[str, Any], rows: list[dict[str, Any]] | None = None) -> str:
    """The dashboard HTML with `summary` embedded. Rows are not embedded: the page needs only the aggregates."""
    payload = json.dumps({"summary": summary}, sort_keys=True, separators=(",", ":"))
    # Inside <script>, only `</script` (closes the element) and `<!--` (switches the parser into its escaped state,
    # which is also the only state where `-->` means anything) are dangerous, and both start with `<`. In this JSON
    # a `<` can only occur inside a string, so every one is replaced by its six-character JSON unicode escape: the
    # same character to JSON.parse, but no markup to the HTML parser. Untrusted text therefore cannot leave the
    # data block, and the page writes it only through textContent and setAttribute (never as markup).
    payload = payload.replace("<", "\\u003c")
    return _TEMPLATE.replace("__CSP__", content_security_policy()).replace("__KPI_DATA__", payload)
