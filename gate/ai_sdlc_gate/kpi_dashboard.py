"""Static, self-contained KPI dashboard (one HTML file, data embedded, no external scripts).

Laid out like an adoption-and-impact slide: usage tiles, per-team adoption curves, cases by month, then quality,
measured outcomes, feedback and data coverage. Every number comes from kpi-summary.json; a KPI without data shows
"no data yet" with the command that would collect it, never an estimate.

Untrusted text in the data (team and repository names, branch names, skip reasons) is embedded as JSON with every
`<` escaped so it cannot close the script tag, and the page only ever writes it with textContent and setAttribute.
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
    --line: #d9d7f0; --card: #ffffff; --bg: #f7f7fc; --warn: #b26b00;
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
  .tiles { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 12px; margin-bottom: 16px; }
  .tile { background: var(--card); border: 1px solid var(--line); border-radius: 10px; padding: 14px 16px; border-top: 4px solid var(--purple); }
  .tile.accent { border-top-color: var(--red); }
  .tile .k { font-size: 13px; color: var(--muted); font-weight: 600; }
  .tile .v { font: 700 28px/1.2 Lexend, system-ui, sans-serif; margin: 4px 0; }
  .tile .d { font-size: 13px; color: var(--muted); }
  .tile.na .v { color: var(--muted); font-size: 17px; }
  .grid2 { display: grid; grid-template-columns: repeat(auto-fit, minmax(380px, 1fr)); gap: 16px; }
  .panel { background: var(--card); border: 1px solid var(--line); border-radius: 10px; padding: 14px 16px; overflow-x: auto; }
  .panel h3 { font: 600 14px/1.3 Lexend, system-ui, sans-serif; margin: 0 0 8px; }
  .legend { display: flex; flex-wrap: wrap; gap: 6px 14px; font-size: 13px; color: var(--muted); margin-bottom: 4px; }
  svg text { font: 12px "Source Sans 3", system-ui, sans-serif; fill: var(--muted); }
  table { border-collapse: collapse; width: 100%; font-size: 14px; }
  th, td { text-align: left; padding: 6px 8px; border-bottom: 1px solid var(--line); vertical-align: top; }
  th { color: var(--muted); font-weight: 600; }
  .note { font-size: 13px; color: var(--muted); }
  footer { max-width: 1280px; margin: 0 auto; padding: 0 24px 32px; font-size: 13px; color: var(--muted); }
  @media (max-width: 520px) { header, .bar, main, footer { padding-left: 16px; padding-right: 16px; } .grid2 { grid-template-columns: 1fr; } }
</style>
</head>
<body>
<header>
  <h1>AI SDLC Gate: adoption and impact</h1>
  <p id="period"></p>
</header>
<div class="bar">
  <label for="scope">Scope</label>
  <select id="scope"></select>
  <span class="note" id="scopenote"></span>
</div>
<main>
  <h2>Adoption and usage</h2>
  <div class="tiles" id="usage"></div>
  <div class="grid2">
    <div class="panel"><h3>Adoption curve per team (gate runs per week)</h3><div class="legend" id="adoptionLegend"></div><div id="adoption"></div><p class="note" id="phaseRule"></p></div>
    <div class="panel"><h3>Cases by month (gate runs, stacked by team)</h3><div class="legend" id="casesLegend"></div><div id="cases"></div></div>
  </div>

  <h2>Quality caught before merge</h2>
  <div class="tiles" id="quality"></div>
  <div class="grid2">
    <div class="panel"><h3>Fail rate by SDLC phase</h3><div id="phases"></div></div>
    <div class="panel"><h3>Most frequent finding categories</h3><div id="cats"></div></div>
  </div>

  <h2>Measured outcomes (git history and pull requests)</h2>
  <div class="grid2">
    <div class="panel"><h3>Reverts and fix commits: gated repositories before / after adoption, and ungated</h3><div id="quality_outcome"></div></div>
    <div class="panel"><h3>Pull request review: before / after adoption, and ungated</h3><div id="review_effect"></div></div>
  </div>

  <h2>Feedback and exceptions</h2>
  <div class="grid2">
    <div class="panel"><h3>Developer feedback on findings (triage labels)</h3><div id="feedback"></div></div>
    <div class="panel"><h3>Skip requests (SDLC-Skip trailers)</h3><div id="skips"></div></div>
  </div>

  <h2>Data coverage</h2>
  <div class="panel"><div id="coverage"></div></div>
</main>
<footer>
  Every number is measured from the gate's run events, developer triage labels, git history and pull requests; none is
  estimated. These KPIs describe the delivery system, not people: no individual is shown, counts of fewer than
  <span id="mingroup"></span> people are suppressed, and teams are compared with their own history, not ranked.
  Definitions and formulas: docs/kpi/README.md.
</footer>
<script id="kpi-data" type="application/json">__KPI_DATA__</script>
<script>
(function () {
  "use strict";
  var S = JSON.parse(document.getElementById("kpi-data").textContent).summary;
  var NS = "http://www.w3.org/2000/svg";
  var PHASES = {"1": "Planning", "2": "Requirements", "3": "Design", "4": "Development", "5": "Testing", "6": "Deployment", "7": "Maintenance", "8": "Security"};
  var PALETTE = ["#434098", "#EB001F", "#8E8BD0", "#F28B99", "#2B2966", "#B8B6E8", "#7A0010", "#5D5B7A"];
  var TEAMS = Object.keys(S.teams);
  var UNATTRIBUTED = "(unattributed)";
  var COLOR = {};
  // Real teams get the palette in order; runs without a known repository get neutral grey, never a team colour.
  TEAMS.filter(function (t) { return t !== UNATTRIBUTED; }).forEach(function (t, i) { COLOR[t] = PALETTE[i % PALETTE.length]; });
  COLOR[UNATTRIBUTED] = "#a9a7bd";

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
  function clear(id) { var n = document.getElementById(id); while (n.firstChild) n.removeChild(n.firstChild); return n; }
  function isNum(x) { return x !== null && x !== undefined && !isNaN(x); }
  function pct(x) { return isNum(x) ? Math.round(x * 1000) / 10 + "%" : null; }
  function num(x, d) { return isNum(x) ? Number(x).toFixed(d === undefined ? 1 : d) : null; }
  function int(x) { return isNum(x) ? Math.round(x).toLocaleString("en") : null; }

  // A legend swatch is a small SVG square: hash-pinned styles allow no style attributes.
  function swatch(color) {
    var s = svgEl("svg", {width: 12, height: 10, viewBox: "0 0 12 10"});
    s.appendChild(svgEl("rect", {width: 12, height: 10, rx: 2, fill: color}));
    return s;
  }

  // A tile shows a measured value, or "no data yet" and what would collect it.
  function tiles(id, specs) {
    var box = clear(id);
    specs.forEach(function (s) {
      var v = s.value;
      var t = el("div", {"class": "tile" + (v === null ? " na" : "") + (s.accent ? " accent" : "")});
      t.appendChild(el("div", {"class": "k"}, s.label));
      t.appendChild(el("div", {"class": "v"}, v === null ? "no data yet" : v));
      t.appendChild(el("div", {"class": "d"}, v === null ? s.missing : s.desc));
      box.appendChild(t);
    });
  }

  function legend(id, teams) {
    var box = clear(id);
    teams.forEach(function (t) {
      var s = el("span");
      s.appendChild(swatch(COLOR[t] || "#5D5B7A"));
      s.appendChild(document.createTextNode(" " + t));
      box.appendChild(s);
    });
  }

  function adoptionChart() {
    var box = clear("adoption"), W = 560, H = 240, L = 40, R = 96, T = 10, B = 34;
    var teams = Object.keys(S.adoption);
    legend("adoptionLegend", teams);
    if (!teams.length) { box.appendChild(el("p", {"class": "note"}, "No gate runs yet.")); return; }
    var weeks = {};
    teams.forEach(function (t) { S.adoption[t].weeks.forEach(function (w) { weeks[w.week] = true; }); });
    weeks = Object.keys(weeks).sort();
    var max = Math.max(1, S.rules.active_week_runs);
    teams.forEach(function (t) { S.adoption[t].weeks.forEach(function (w) { max = Math.max(max, w.runs); }); });
    var n = weeks.length, x = function (i) { return L + (n <= 1 ? (W - L - R) / 2 : i * (W - L - R) / (n - 1)); };
    var y = function (v) { return T + (H - T - B) * (1 - v / max); };
    var svg = svgEl("svg", {viewBox: "0 0 " + W + " " + H, width: "100%", role: "img"});
    [0, max / 2, max].forEach(function (g) {
      svg.appendChild(svgEl("line", {x1: L, x2: W - R, y1: y(g), y2: y(g), stroke: "#d9d7f0"}));
      svg.appendChild(svgEl("text", {x: L - 6, y: y(g) + 4, "text-anchor": "end"}, Math.round(g)));
    });
    svg.appendChild(svgEl("line", {x1: L, x2: W - R, y1: y(S.rules.active_week_runs), y2: y(S.rules.active_week_runs), stroke: "#b26b00", "stroke-dasharray": "4 4"}));
    weeks.forEach(function (w, i) { if (n <= 8 || i % Math.ceil(n / 8) === 0) svg.appendChild(svgEl("text", {x: x(i), y: H - 12, "text-anchor": "middle"}, w.replace(/^\d{4}-/, ""))); });
    var labels = [];
    teams.forEach(function (t) {
      var pts = S.adoption[t].weeks.map(function (w) { return [x(weeks.indexOf(w.week)), y(w.runs)]; });
      if (pts.length > 1) svg.appendChild(svgEl("polyline", {points: pts.map(function (p) { return p.join(","); }).join(" "), fill: "none", stroke: COLOR[t], "stroke-width": 2.5}));
      pts.forEach(function (p) { svg.appendChild(svgEl("circle", {cx: p[0], cy: p[1], r: 3, fill: COLOR[t]})); });
      var last = pts[pts.length - 1];
      labels.push({x: last[0] + 6, y: last[1] + 4, text: S.adoption[t].phase, color: COLOR[t]});
    });
    // Lines often end close together: push the end labels apart so each stays readable.
    labels.sort(function (a, b) { return a.y - b.y; });
    for (var li = 1; li < labels.length; li++) {
      if (labels[li].y - labels[li - 1].y < 13) labels[li].y = labels[li - 1].y + 13;
    }
    labels.forEach(function (l) { svg.appendChild(svgEl("text", {x: l.x, y: l.y, fill: l.color}, l.text)); });
    box.appendChild(svg);
    document.getElementById("phaseRule").textContent = "Phase per team from its runs per week (dashed line: " + S.rules.active_week_runs +
      " runs, an active week). " + S.rules.regular_streak_weeks + " consecutive active weeks = regular, " + S.rules.operational_streak_weeks +
      " = operational, otherwise experimental.";
  }

  function casesChart() {
    var box = clear("cases"), W = 560, H = 240, L = 40, R = 12, T = 18, B = 34;
    var months = Object.keys(S.cases_by_month);
    var teams = {};
    months.forEach(function (m) { Object.keys(S.cases_by_month[m]).forEach(function (t) { teams[t] = true; }); });
    teams = Object.keys(teams).sort();
    legend("casesLegend", teams);
    if (!months.length) { box.appendChild(el("p", {"class": "note"}, "No gate runs yet.")); return; }
    var totals = months.map(function (m) { return teams.reduce(function (a, t) { return a + (S.cases_by_month[m][t] || 0); }, 0); });
    var max = Math.max.apply(null, totals.concat([1])), bw = (W - L - R) / months.length;
    var y = function (v) { return T + (H - T - B) * (1 - v / max); };
    var svg = svgEl("svg", {viewBox: "0 0 " + W + " " + H, width: "100%", role: "img"});
    svg.appendChild(svgEl("line", {x1: L, x2: W - R, y1: y(0), y2: y(0), stroke: "#d9d7f0"}));
    months.forEach(function (m, i) {
      var acc = 0, x0 = L + i * bw + bw * 0.2;
      teams.forEach(function (t) {
        var v = S.cases_by_month[m][t] || 0;
        if (!v) return;
        svg.appendChild(svgEl("rect", {x: x0, y: y(acc + v), width: bw * 0.6, height: y(acc) - y(acc + v), fill: COLOR[t] || "#5D5B7A"}));
        acc += v;
      });
      svg.appendChild(svgEl("text", {x: x0 + bw * 0.3, y: y(acc) - 4, "text-anchor": "middle"}, acc));
      svg.appendChild(svgEl("text", {x: x0 + bw * 0.3, y: H - 12, "text-anchor": "middle"}, m));
    });
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

  function table(id, head, rows, emptyText) {
    var box = clear(id);
    if (!rows.length) { box.appendChild(el("p", {"class": "note"}, emptyText)); return box; }
    var t = el("table"), hr = el("tr");
    head.forEach(function (h) { hr.appendChild(el("th", {}, h)); });
    t.appendChild(hr);
    rows.forEach(function (r) { var tr = el("tr"); r.forEach(function (c) { tr.appendChild(el("td", {}, c === null ? "n/a" : c)); }); t.appendChild(tr); });
    box.appendChild(t);
    return box;
  }

  var COHORT = {gated_before: "Gated repos, before adoption", gated_after: "Gated repos, after adoption", ungated: "Repos never gated"};

  function render(scope) {
    var k = scope === "__all__" ? S.overall : S.teams[scope];
    var u = scope === "__all__" ? {gate_users: S.users.total_gate_users, coverage: null} : (S.users.by_team[scope] || {gate_users: null, coverage: null});
    var teamsAll = Object.keys(S.adoption);
    var operational = teamsAll.filter(function (t) { return S.adoption[t].phase === "operational"; }).length;
    document.getElementById("scopenote").textContent = k.runs + " gate runs in scope";
    tiles("usage", [
      {label: "Cases (gate runs)", value: int(k.runs), desc: "Commits and pushes reviewed by the gate."},
      {label: "Active repositories", value: int(k.active_repos), desc: "Repositories with at least one gate run."},
      {label: scope === "__all__" ? "Teams operational" : "Adoption phase", value: scope === "__all__" ? operational + " of " + teamsAll.length : ((S.adoption[scope] || {}).phase || null),
       desc: "By the adoption rule under the curve.", missing: "No runs for this team."},
      {label: "Gate users", value: int(u.gate_users), desc: "Distinct verified developers" + (isNum(u.coverage) ? "; " + pct(u.coverage) + " of committers in gated repos." : "."),
       missing: "Fewer than " + S.rules.min_group + " people (suppressed), or no verified sign-ins."},
      {label: "Blocks resolved before merge", value: int(k.blocks_resolved), accent: true,
       desc: int(k.blocking_findings_resolved) + " blocking findings fixed; " + int(k.blocks) + " blocked branches in total.", missing: "No blocked branch has turned green yet."},
      {label: "Median fix cycle", value: isNum(k.time_to_green_hours_median) ? num(k.time_to_green_hours_median, 1) + " h" : null, accent: true,
       desc: "Block to next passing run, median " + num(k.fix_iterations_median, 0) + " blocked run(s); " + k.time_to_green_recoveries + " recoveries.",
       missing: "No blocked branch has turned green yet."},
      {label: "Positive feedback", value: pct(k.feedback.positive_share), desc: k.feedback.labels + " labels; " + (pct(k.feedback.label_coverage) || "0%") + " of findings labelled.",
       missing: k.feedback.labels + " of " + S.rules.min_triage_labels + " labels needed; developers label with `ai-sdlc-gate triage`."},
      {label: "Tokens per run p50 / p90", value: isNum(k.tokens_p50) ? int(k.tokens_p50) + " / " + int(k.tokens_p90) : null,
       desc: int(k.tokens_total) + " tokens in scope; " + pct(k.token_metered_share) + " of runs report usage.", missing: "No run reported token usage."},
      {label: "Run time p50 / p90", value: isNum(k.gate_latency_s_p50) ? num(k.gate_latency_s_p50, 0) + " / " + num(k.gate_latency_s_p90, 0) + " s" : null,
       desc: "Time a developer waits for the gate.", missing: "No run reported its duration."}
    ]);
    tiles("quality", [
      {label: "Gate pass rate", value: pct(k.gate_pass_rate), desc: "Runs that passed every required phase."},
      {label: "First-time-right", value: pct(k.first_time_right_rate), desc: "Branches whose first run passed; " + k.first_time_right_branches + " branches.",
       missing: "No run with a known repository and branch."},
      {label: "Block rate", value: pct(k.block_rate), desc: "Runs stopped by a high or blocker finding."},
      {label: "Blocking findings per run", value: num(k.blocking_findings_per_run, 2), desc: "Blocker + high per gate run."},
      {label: "Blocking findings per 1k lines", value: num(k.blocking_findings_per_kloc, 2), desc: "Over runs that report changed lines.",
       missing: "Runs report changed lines from gate engines released with PR #34 on."},
      {label: "Security-critical runs", value: pct(k.security_critical_run_rate), accent: true, desc: "Secret, credential or vulnerable dependency caught."}
    ]);
    hbars("phases", Object.keys(k.phase_fail_rate).filter(function (p) { return isNum(k.phase_fail_rate[p]); })
      .map(function (p) { return [p + " " + (PHASES[p] || ""), k.phase_fail_rate[p]]; }), pct, "#434098");
    // The JSON is written with sorted keys, so order by count here (ties alphabetically, for a stable picture).
    hbars("cats", Object.keys(k.top_categories).map(function (c) { return [c, k.top_categories[c]]; })
      .sort(function (a, b) { return b[1] - a[1] || (a[0] < b[0] ? -1 : 1); }), function (v) { return v; }, "#EB001F");
    var fb = k.feedback;
    table("feedback", ["Phase", "False-positive rate", "Labels"], Object.keys(fb.by_phase).map(function (p) {
      return [p + " " + (PHASES[p] || ""), fb.by_phase[p].rate === null ? "insufficient data" : pct(fb.by_phase[p].rate), String(fb.by_phase[p].labels)];
    }), "No data yet: no findings labelled. Developers label findings with `ai-sdlc-gate triage <n> --label accepted|false-positive|wont-fix`; a rate is shown from " +
      S.rules.min_triage_labels + " labels per group.");
  }

  var src = S.sources;
  document.getElementById("period").textContent = S.overall.runs
    ? "Period " + S.period.from.slice(0, 10) + " to " + S.period.to.slice(0, 10) + "  ·  " + src.gate_runs + " gate runs  ·  " + src.git_commits +
      " commits from " + src.git_repos + " repos  ·  " + src.pull_requests + " pull requests"
    : "No gate runs in the dataset.";
  document.getElementById("mingroup").textContent = S.rules.min_group;
  var scope = document.getElementById("scope");
  scope.appendChild(el("option", {value: "__all__"}, "All teams"));
  TEAMS.forEach(function (t) { scope.appendChild(el("option", {value: t}, t + " (" + S.teams[t].runs + ")")); });
  scope.addEventListener("change", function () { render(scope.value); });
  adoptionChart();
  casesChart();

  table("quality_outcome", ["Cohort", "Commits", "Repos", "Revert rate", "Fix-commit rate"],
    S.quality_outcome ? Object.keys(S.quality_outcome).map(function (c) { var q = S.quality_outcome[c];
      return [COHORT[c] || c, int(q.commits), int(q.repos), pct(q.revert_rate), pct(q.fix_commit_rate)]; }) : [],
    "No data yet: collect each repository's history with `ai-sdlc-gate kpi collect-git --repo-dir <clone> --out <file>` and pass it to `kpi export --git`.");
  table("review_effect", ["Cohort", "PRs", "Cycle h (median)", "Reviews (median)", "Changes requested", "Review comments (median)", "Revert PRs"],
    S.review_effect ? Object.keys(S.review_effect).map(function (c) { var r = S.review_effect[c];
      return [COHORT[c] || c, int(r.prs), num(r.cycle_hours_median, 1), num(r.reviews_median, 0), pct(r.changes_requested_share), num(r.review_comments_median, 0), pct(r.revert_pr_rate)]; }) : [],
    "No data yet: collect pull requests with `ai-sdlc-gate kpi collect-prs --slug <owner/repo> --out <file>` and pass them to `kpi export --prs`.");

  table("skips", ["Date", "Repository", "Phases", "Reason"], S.skip_reasons.slice(-12).reverse().map(function (s) {
    return [s.ts.slice(0, 10), s.repo, s.phases.join(", ") || "-", s.reason || "(no reason)"];
  }), "No skip requests in the period.");

  var o = S.overall;
  table("coverage", ["Stream", "Status", "Needed for"], [
    ["Gate run events", src.gate_runs + " runs", "every run-based KPI"],
    ["Runs attributable to a repository and branch", pct(o.attributable_share), "first-time-right, fix cycle, blocks resolved (newer engines attribute every run)"],
    ["Team map", src.team_map ? "provided" : "not provided: teams are GitHub owners", "exact team attribution (`kpi export --teams`)"],
    ["Runs reporting changed lines", pct(o.sized_run_share), "findings per 1k lines"],
    ["Runs reporting tokens", pct(o.token_metered_share), "cost"],
    ["Triage labels", o.feedback.labels + " (" + (pct(o.feedback.label_coverage) || "0%") + " of findings)", "feedback and false-positive rate"],
    ["Git history", src.git_commits ? src.git_commits + " commits, " + src.git_repos + " repos" : "no data yet", "revert and fix-commit rates, committer coverage"],
    ["Pull requests", src.pull_requests ? src.pull_requests + " PRs, " + src.pr_repos + " repos" : "no data yet", "review cycle time and rounds"]
  ], "");

  render("__all__");
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
    # Escaping contract, tested by test_dashboard_embeds_data_safely_and_has_no_external_scripts and
    # test_hostile_repo_names_and_comment_closers_stay_data (gate/tests/test_kpi.py): every `<` in the JSON
    # payload is replaced by its six-character JSON unicode escape (backslash, u, 003c). JSON.parse reads it back
    # as `<`, but the HTML parser never sees a `<` inside the data block, so neither `</script` nor `<!--` can occur
    # there (and `-->` means nothing without a preceding `<!--`). The page writes data only through textContent and
    # setAttribute, and the Content-Security-Policy pins its one script by hash.
    payload = payload.replace("<", "\\u003c")
    return _TEMPLATE.replace("__CSP__", content_security_policy()).replace("__KPI_DATA__", payload)
