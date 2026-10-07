# AI SDLC Gate: delivery quality KPIs

Eleven KPIs built only from data the gate already records. Each gate run produces one metrics event
(`events/YYYY/MM.jsonl` on the `metrics` branch, schema 1, see [../metrics.md](../metrics.md)). The exporter
turns those events into a metadata-only dataset and computes the KPIs; a static dashboard shows them.

```bash
ai-sdlc-gate kpi export --events-dir <metrics-branch>/events --out out/kpi
```

This writes `kpi-runs.csv`, `kpi-runs.json` (one row per gate run), `kpi-summary.json` (KPIs overall, per ISO week
and per repository) and `kpi-dashboard.html` (one self-contained file, open it in a browser).

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
| K3 | **Blocking findings per run** | Blocker + high findings per run | Risk: how much must-fix work the gate catches | Σ(`counts.blocker` + `counts.high`) / runs. Target form: per 1,000 changed lines (needs a new field, see gaps) | repo, week | Bigger changes find more; until normalised by size, compare trends only. |
| K4 | **Phase fail rate** | Per SDLC phase: share of runs where that phase failed | Where to invest: design, testing, security or docs practice | runs with `phase_results[p].verdict = fail` / runs that checked phase p | phase, repo, week | Phases 6/7 run only for deploy/maintenance changes; small denominators. |
| K5 | **Security-critical run rate** | Share of runs with a secret, hard-coded credential or known-vulnerable dependency finding | Risk: exposure that must never ship (non-waivable in the gate) | runs whose categories include `secret-exposure`, `hardcoded-credential` or `known-vulnerable-dependency` / runs | repo, week | Caught locally means it did *not* ship; a rising rate is a training signal, not a breach count. |
| K6 | **Top finding categories** | Most frequent finding categories and their trend | Where quality is lost (tests, docs, resilience, security) | count of `findings_brief[].category` (older events: `top_categories`) | repo, week | `general` is a catch-all; the brief keeps at most 40 findings per run. |
| K7 | **Median time to green** | Hours from a branch's first blocked run to its next passing run | Speed: cost of a block in elapsed time | median over branches of (`ts` of next pass − `ts` of first fail since last pass) | repo, month | Elapsed, not effort, time: weekends count. Show the recovery count. |
| K8 | **Skip / waiver rate and reasons** | Share of runs with a valid `SDLC-Skip`; waived findings; the reasons | Governance: how often the standard is bypassed, and why | runs with `skip.valid` / runs; Σ `waived_count`; `skip.reason` | repo, week | A justified skip is healthy; read the reasons before judging the rate. `--no-verify` bypasses are a separate stream (server logs, see gaps). |
| K9 | **Unverified finding share** | Share of findings the gate downgraded because their evidence is not in the file | Trust: gate precision; false positives cost developer time | Σ `unverified_count` / Σ `findings_total` | repo, week | An automatic lower bound on false positives, not the full rate (needs human triage, see gaps). Available from 2026-10-05. |
| K10 | **Gate latency p50 / p90** | Review time per run | Speed: the gate's cost in developer waiting time | 50th / 90th percentile of `duration_s` (runs with duration > 0) | repo, week | Includes multiple review passes and model queueing; p90 shows the worst waits. |
| K11 | **Tokens per run** | Model tokens per metered run | Cost: the model bill and its trend | Σ(`llm_usage.prompt_tokens` + `completion_tokens`) / metered runs | repo, month | Runs reporting 0 tokens are excluded (share shown); multiply by the model price for €. |

Also in the summary for context: run counts, block rate (`blocked`/runs), skip request rate, data coverage shares.

## Data gaps (what the events do not support yet)

Measured on the 149 events of 2026-09-22 to 2026-10-07:

| Gap | Effect | Fix |
|---|---|---|
| No changed-lines field | K3 cannot be normalised per 1,000 lines | Add `lines_added` / `lines_removed` to the event (additive, schema 1 stays valid). |
| 47% of runs unattributable (`ref = HEAD` or repo `unknown/unknown`) | K2 and K7 rest on about half the runs; K7 had only 2 recoveries | Send the branch name and remote slug from the local hooks. |
| 25% of runs report 0 tokens | K11 covers 75% of runs | Return usage from the review endpoint to the client in every case. |
| No human triage of false positives | K9 is a lower bound | A "dispute finding" action that records the verdict. |
| `--no-verify` bypasses are in Cloud Logging, not in events | K8 sees only `SDLC-Skip` waivers | Export `sdlc_event="skip"` log lines into the same dataset. |
| No link to production incidents | "escaped issues" cannot be measured | Join with incident tickets by repository and release (out of scope for the gate). |

## Plugging into the Measurement tool (due 15 Nov)

**Contract.** The Measurement tool consumes `kpi-runs.json` (or `.csv`) and `kpi-summary.json`:

- `kpi-runs.*`: one row per gate run. The columns are listed in `COLUMNS` in `gate/ai_sdlc_gate/kpi.py`, in that
  order. `dataset_version` is 1. Changes are additive only; a removed or renamed column bumps the version.
  List values are `;`-joined in CSV (`phases`, `failed_phases`, `skip_phases`) and `category:count` pairs in
  `categories`. Times are ISO-8601 UTC; `week` is the ISO week (`2026-W41`).
- `kpi-summary.json`: the K1–K11 values `overall`, per `weeks[<iso week>]` and per `repos[<owner/name>]`, with
  `null` where the data cannot support a KPI.

**Delivery, in two steps.**

1. *Now (no new infrastructure):* a scheduled job on the central repository runs `ai-sdlc-gate kpi export` over
   the `metrics` branch and commits the four files to `dashboard/kpi/`. The tool reads them over the GitHub
   API with a read-only token. The dashboard is viewable straight from the branch.
2. *Later (if the tool needs live data or filtering):* `GET /v1/kpi?from=&to=&repo=` on the existing Cloud Run
   endpoint, returning the same rows / summary JSON, authorised with the org's Entra sign-in. Same contract, so
   the tool does not change.

**What the tool should own:** cross-source joins (incidents, DORA metrics, survey data) and the management view
across all AI-in-SDLC tools. The gate dataset stays one source among several, keyed by repository and week.
