# AI SDLC Gate: delivery quality KPIs

Thirteen KPIs built only from data the gate records. Each gate run produces one metrics event
(`events/YYYY/MM.jsonl` on the `metrics` branch, schema 1, see [../metrics.md](../metrics.md)). The exporter
turns those events into a metadata-only dataset and computes the KPIs; a static dashboard shows them.

```bash
ai-sdlc-gate kpi export --events-dir <metrics-branch>/events --out out/kpi
```

This writes `kpi-runs.csv`, `kpi-runs.json` (one row per gate run), `kpi-triage.csv` (one row per finding label),
`kpi-summary.json` (KPIs overall, per ISO week and per repository) and `kpi-dashboard.html` (one self-contained
file, open it in a browser).

## Ground rules

- **Systems, not people.** Rows carry no developer login or e-mail, no finding titles, no file paths and no
  code. The lowest level is a repository; the dashboard has no per-developer view.
- **No raw cross-team ranking.** Repositories differ in language, risk and maturity. Compare a team with its own
  history (trend), not with another team's number.
- **n/a beats a wrong zero.** A KPI the data cannot support is reported as `null` / "n/a" with the reason, never as 0.
- **Small samples are labelled.** First-time-right shows its branch count and time to green its recovery count.

## The KPIs

"Run" = one gate execution (a local commit/push hook or a CI job). "Branch" = a (repository, ref) pair; runs with
ref `HEAD` or repository `unknown/unknown` cannot be attributed to one and are left out of K2 and K7.

| # | KPI | What it measures | Why management cares | Formula (event fields) | Granularity | Don't misuse |
|---|---|---|---|---|---|---|
| K1 | **Gate pass rate** | Share of runs that passed every required phase | Quality: how often work meets the standard as submitted | runs with `verdict = pass` / runs | repo, week | A high rate after many skips is not quality; read it with K8. |
| K2 | **First-time-right rate** | Share of branches whose first gate run passed | Quality and speed: rework avoided before review | branches whose earliest run has `verdict = pass` / attributable branches | repo, week | Depends on how often teams commit; few branches make it noisy (count shown). |
| K3 | **Blocking findings per run and per 1,000 changed lines** | Blocker + high findings, per run and per changed line | Risk: how much must-fix work the gate catches, independent of change size | per run: Σ(`counts.blocker` + `counts.high`) / runs. Per 1k lines: same sum over runs that report size / Σ(`lines_added` + `lines_removed`) × 1000 | repo, week | Per-run favours small changes; use the per-line form once enough runs report size (share shown). |
| K4 | **Phase fail rate** | Per SDLC phase: share of runs where that phase failed | Where to invest: design, testing, security or docs practice | runs with `phase_results[p].verdict = fail` / runs that checked phase p | phase, repo, week | Phases 6/7 run only for deploy/maintenance changes; small denominators. |
| K5 | **Security-critical run rate** | Share of runs with a secret, hard-coded credential or known-vulnerable dependency finding | Risk: exposure that must never ship (non-waivable in the gate) | runs whose categories include `secret-exposure`, `hardcoded-credential` or `known-vulnerable-dependency` / runs | repo, week | Caught locally means it did *not* ship; a rising rate is a training signal, not a breach count. |
| K6 | **Top finding categories** | Most frequent finding categories and their trend | Where quality is lost (tests, docs, resilience, security) | count of `findings_brief[].category` (older events: `top_categories`) | repo, week | `general` is a catch-all; the brief keeps at most 40 findings per run. |
| K7 | **Median time to green** | Hours from a branch's first blocked run to its next passing run | Speed: cost of a block in elapsed time | median over branches of (`ts` of next pass − `ts` of first fail since last pass) | repo, month | Elapsed, not effort, time: weekends count. Show the recovery count. |
| K8 | **Skip / waiver rate and reasons** | Share of runs with a valid `SDLC-Skip`; waived findings; the reasons | Governance: how often the standard is bypassed, and why | runs with `skip.valid` / runs; Σ `waived_count`; `skip.reason` | repo, week | A justified skip is healthy; read the reasons before judging the rate. `--no-verify` bypasses are a separate stream (server logs, see gaps). |
| K9 | **Unverified finding share** | Share of findings the gate downgraded because their evidence is not in the file | Trust: gate precision; false positives cost developer time | Σ `unverified_count` / Σ `findings_total` | repo, week | An automatic lower bound on false positives, not the full rate (needs human triage, see gaps). Available from 2026-10-05. |
| K10 | **Gate latency p50 / p90** | Review time per run | Speed: the gate's cost in developer waiting time | 50th / 90th percentile of `duration_s` (runs with duration > 0) | repo, week | Includes multiple review passes and model queueing; p90 shows the worst waits. |
| K11 | **Tokens per run** | Model tokens per metered run | Cost: the model bill and its trend | Σ(`llm_usage.prompt_tokens` + `completion_tokens`) / metered runs | repo, month | Runs reporting 0 tokens are excluded (share shown); multiply by the model price for €. |
| K12 | **Estimated time saved per run** | Net developer hours saved by fixing blocking defects before merge instead of after, minus the time spent waiting for the gate | Value: what the gate returns for its cost | (caught blocking findings × precision × (post-merge fix h − pre-merge fix h) − Σ `duration_s`/3600) / runs. See the method below | repo, month | An estimate from stated assumptions, not a measurement; never compare teams by it. |
| K13 | **False-positive rate** | Share of triaged findings developers labelled false positive, overall, per phase and per category | Trust: a noisy gate gets bypassed; this shows where the skills need work | `false-positive` labels / all labels (`triage[]` in events) | phase, category, repo | Labels are a sample of what developers chose to label; shown only from 10 labels per group, with the count. |

Also in the summary for context: run counts, block rate (`blocked`/runs), skip request rate, data coverage shares.

## K12 time saved: the method

**What is estimated.** A blocking finding fixed while the change is still open costs less than the same defect
found after merge, when it needs rediscovery, a new branch and review, and possibly a redeploy. The gate's value is
that difference, summed over the defects it catches, minus what the gate costs developers in waiting time.

```
caught    = blocker + high findings of the FIRST failing run of each blocked streak on a branch
precision = 1 − K13 false-positive rate     (measured, from 10 triage labels up)
          = 0.8                             (assumed, until then)
gross h   = caught × precision × (fix_hours_post_merge − fix_hours_pre_merge)
net h     = gross h − Σ gate run duration (h)
K12       = net h / gate runs
```

- **Counted once per streak.** A finding stays in the report on every run until it is fixed, so summing over
  runs would count one defect several times.
- **Lower bound.** Runs that cannot be attributed to a branch (`HEAD`, unknown repository) are left out.
- **Assumptions, all in `TIME_SAVED_ASSUMPTIONS` in `kpi.py` and shown on the dashboard:**
  - fix before merge: 0.5 h;
  - fix after merge: 2.5 h;
  - assumed precision: 0.8.

  The 5× ratio is deliberately at the low end of the defect-cost escalation reported in the literature. Boehm
  and Basili's "Software Defect Reduction Top 10 List" (IEEE Computer, 2001) puts late fixes at up to 100×
  for large systems and about 5× for small, non-critical ones. NIST's report "The Economic Impacts of
  Inadequate Infrastructure for Software Testing" (2002) gives the same direction. Replace the defaults with
  one.O's own figures when the Measurement workstream has them.

**From estimate to measurement.** Human review time saved, the second half of "time saved per review", can't be
derived from gate data. To measure it, the gate (or the Measurement tool) must collect, per pull request:

| Field | Source |
|---|---|
| `pr_number`, `repo` (already in CI events) | gate event |
| `review_minutes`: first review request to approval | GitHub pull request timeline |
| `human_review_comments`, `review_rounds` | GitHub pull request reviews |
| `lines_added`, `lines_removed` (now emitted by the gate) | gate event |
| `gated`: whether the repository ran the gate on that PR | gate event present for the PR head |

Comparing review minutes per 100 changed lines between gated and comparable ungated pull requests (same team,
same period) gives the measured figure. Until then K12 covers the defect-fix side only.

## K13: how findings get triaged

After a gate run, a developer lists the findings and labels the ones they want to confirm or dispute:

```bash
ai-sdlc-gate triage                                   # numbered list of the last run's findings
ai-sdlc-gate triage 3 --label false-positive --note "framework escapes this"
```

Labels are `accepted`, `false-positive` and `wont-fix`. They are kept in `~/.ai-sdlc-gate/triage.jsonl` and
travel with the next gate run's metrics event, marked sent only after that dispatch succeeds. Only the phase,
category, severity and label leave the machine. The finding's title, file, line and the note never do. The
dashboard shows "insufficient data" until a group has 10 labels.

## Data gaps (what the events do not support yet)

Measured on the 149 events of 2026-09-22 to 2026-10-07:

| Gap | Effect | Fix |
|---|---|---|
| Changed lines only from this release on | K3 per 1,000 lines covers new runs only (share shown) | Done: events now carry `lines_added` / `lines_removed` (additive, schema 1 stays valid). Fills as developers update. |
| 47% of runs unattributable (`ref = HEAD` or repo `unknown/unknown`) | K2 and K7 rest on about half the runs; K7 had only 2 recoveries | Send the branch name and remote slug from the local hooks. |
| 25% of runs report 0 tokens | K11 covers 75% of runs | Return usage from the review endpoint to the client in every case. |
| No triage labels yet | K13 shows "insufficient data"; K12 uses the assumed precision | Done: `ai-sdlc-gate triage` records labels. Needs developers to use it; consider a PR-comment convention (`/gate fp <n>`) for CI runs. |
| No pull request review data | K12 covers the defect-fix side only | Collect review minutes and rounds per PR (see the K12 method). |
| `--no-verify` bypasses are in Cloud Logging, not in events | K8 sees only `SDLC-Skip` waivers | Export `sdlc_event="skip"` log lines into the same dataset. |
| No link to production incidents | "escaped issues" cannot be measured | Join with incident tickets by repository and release (out of scope for the gate). |

## Why it matters

**AI Standardization: "AI in Software Development" (Vincent Tietz et al.).** The gate is a working test of a
standardization method:

- Every change leaving India is checked against the standard guidelines (prompts, code, documentation,
  security) before it is committed or pushed.
- That makes the gate both the **enforcement point** and the **measurement point** for the standards: #4
  workflows, #5 prompt standards and #6 governance.
- These KPIs feed the Measurement workstream's KPI framework. The stakeholder package is due end of October /
  early November. Arijit's task, with Kaweh Kazemi and Thorsten Madlener, is to review the internal KPI tool,
  integrate it with the gate and benchmark alternatives.

**AI IC Initiative: AI Transformation @ International Commerce (India lead: Arijit Aich).** The gate's KPIs are
India's evidence for two maturity-matrix dimensions:

| Maturity dimension | Gate KPIs that evidence it |
|---|---|
| **Delivery & Automation** | pass rate, first-time-right, time to green, latency, estimated time saved |
| **Risk & Responsible AI** | security-critical run rate, skip / waiver governance, false-positive rate |

India runs every change through the gate, so all output is standardized; these KPIs show it.

## Plugging into the Measurement tool (due 15 Nov)

**Contract.** The Measurement tool consumes `kpi-runs.json` (or `.csv`) and `kpi-summary.json`:

- `kpi-runs.*`: one row per gate run. The columns are listed in `COLUMNS` in `gate/ai_sdlc_gate/kpi.py`, in that
  order. `dataset_version` is 1. Changes are additive only; a removed or renamed column bumps the version.
  List values are `;`-joined in CSV (`phases`, `failed_phases`, `skip_phases`) and `category:count` pairs in
  `categories`. Times are ISO-8601 UTC; `week` is the ISO week (`2026-W41`).
- `kpi-triage.csv`: one row per finding label (`run_id, ts, week, repo, phase, category, severity, label`).
- `kpi-summary.json`: the K1–K13 values `overall`, per `weeks[<iso week>]` and per `repos[<owner/name>]`, with
  `null` where the data cannot support a KPI. K12 includes its inputs and assumptions.

**Delivery, in two steps.**

1. *Now (no new infrastructure):* a scheduled job on the central repository runs `ai-sdlc-gate kpi export` over
   the `metrics` branch and commits the four files to `dashboard/kpi/`. The tool reads them over the GitHub
   API with a read-only token. The dashboard is viewable straight from the branch.
2. *Later (if the tool needs live data or filtering):* `GET /v1/kpi?from=&to=&repo=` on the existing Cloud Run
   endpoint, returning the same rows / summary JSON, authorised with the org's Entra sign-in. Same contract, so
   the tool does not change.

**What the tool should own:** cross-source joins (incidents, DORA metrics, survey data) and the management view
across all AI-in-SDLC tools. The gate dataset stays one source among several, keyed by repository and week.
