# AI SDLC Gate: adoption and impact KPIs

**Measured only.** Every number on the dashboard is counted or timed from one of four data streams. Nothing is
estimated from assumed parameters. A KPI without data shows **"no data yet"** and the command that would
collect it.

```bash
# 1. Gate run events: already collected for every run (events/YYYY/MM.jsonl on the `metrics` branch).
# 2. Git history of each repository (metadata only):
ai-sdlc-gate kpi collect-git --repo-dir <clone> --out git-<repo>.jsonl
# 3. Pull requests of each GitHub repository:
ai-sdlc-gate kpi collect-prs --slug <owner/repo> --out prs-<repo>.jsonl      # add --via-gh to use the gh CLI sign-in
# 4. Developer feedback: `ai-sdlc-gate triage` labels travel inside the gate run events.
# Then:
ai-sdlc-gate kpi export --events-dir <metrics>/events --git git-*.jsonl --prs prs-*.jsonl --teams teams.yaml --out out/kpi
```

`kpi export` writes:
- `kpi-runs.csv` / `kpi-runs.json`: one row per gate run;
- `kpi-triage.csv`: one row per finding label;
- `kpi-summary.json`: every KPI overall, per ISO week, per repository and per team, plus adoption and the
  outcome comparisons;
- `kpi-dashboard.html`: one self-contained page.

## Ground rules

- **Measured, never estimated.** If a stream is missing, the KPI is `null` / "no data yet". There is no default
  value, assumed rate or fallback constant anywhere in the computation; a test enforces this.
- **Systems, not people.** No developer login, e-mail, name, commit message, finding title, file path or code
  is exported. People are counted only through a one-way hash, and **any count of fewer than 5 people is
  suppressed** (works-council rule). There is no per-person view.
- **No ranking.** Compare a team with its own history (trend, before / after adoption), not with other teams.
- **Show the n.** Every rate comes with its sample size: runs, branches, recoveries, labels, commits or PRs.

## Data streams

| Stream | Collected by | Holds | Privacy |
|---|---|---|---|
| Gate run events | every gate run (`emit-metrics`) | verdict, phases, findings by severity and category, skips, duration, tokens, changed lines | no titles, paths or code; developer e-mail only for hashed distinct counts |
| Triage labels | `ai-sdlc-gate triage`, sent with the next run's event | phase, category, severity, label per finding | no title, file, line or note leaves the machine |
| Git history | `kpi collect-git` | per commit: time, author key, merge / revert / fix flags | no name, e-mail, message or code; the author key is a keyed HMAC with a secret kept on the collecting machine (`~/.ai-sdlc-gate/kpi-salt`), so it cannot be reversed by hashing a list of likely addresses |
| Pull requests | `kpi collect-prs` | per closed PR: opened, merged, reviews, changes requested, review comments, revert | no titles or bodies kept, except the revert flag |
| Team map (optional) | a YAML file you maintain | `teams: {<team>: [<owner/repo glob>, ...]}` | none |

Without a team map, a repository's team is its GitHub owner (e.g. `otto-ec`). Runs without a known repository
are `(unattributed)`. If a repository matches several teams in the map, the first team in name order wins;
`kpi export` reports such overlaps, globs without an `owner/` part, and teams that match no repository.
Collect git history and export on the same machine, so people are keyed alike in git and in the gate data.

## The KPIs

### Adoption and usage

| KPI | Formula | Source | Status 2026-10-07 |
|---|---|---|---|
| **Cases** | gate runs, per month and team | events | **157** (Sep 40, Oct 117) |
| **Active repositories** | distinct repositories with ≥ 1 run | events | **15** |
| **Adoption phase per team** | from runs per ISO week, see the phase rule below | events | **0 of 6 operational**: 3 regular, 3 experimental |
| **Gate users** | distinct verified developers (hashed), suppressed below 5 | events | **no data yet**: fewer than 5 verified users per team |
| **Committer coverage** | gate users ∩ committers ÷ committers in the team's gated repositories, both ≥ 5 | events + git | **no data yet**: needs ≥ 5 people on both sides |

**Adoption phase rule** (one definition for every team, set in `kpi.py`):
- A week is **active** for a team when it has **≥ 5 gate runs**.
- **2 consecutive active weeks** = *regular*.
- **4 consecutive active weeks** = *operational*.
- Anything else with runs = *experimental*.

The phase is measured each week, so it can fall back after an inactive week.

### Quality caught before merge

| KPI | Formula | Source | Status 2026-10-07 |
|---|---|---|---|
| **Gate pass rate** | runs with `verdict = pass` ÷ runs | events | **66.2%** |
| **First-time-right** | branches whose first run passed ÷ attributable branches | events | **67.7%** (34 branches) |
| **Block rate** | blocked runs ÷ runs | events | **33.8%** |
| **Blocking findings per run** | Σ(blocker + high) ÷ runs | events | **2.65** |
| **Blocking findings per 1,000 changed lines** | Σ(blocker + high) ÷ Σ(lines added + removed) × 1000, over runs that report size | events | **no data yet**: engines from PR #34 on report changed lines |
| **Security-critical run rate** | runs with a `secret-exposure`, `hardcoded-credential` or `known-vulnerable-dependency` finding ÷ runs | events | **14.7%** |
| **Phase fail rate** | runs where phase p failed ÷ runs that checked phase p | events | Design 18.8%, Development 18.8%, Testing 18.1%, Deployment 53.9%, Maintenance 56.5%, Security 8.1% (measured on the earlier 149 runs; the dashboard shows current values) |
| **Top finding categories** | count of findings per category (run brief, ≤ 40 per run) | events | `general`, `missing-tests`, `hardcoded-configuration` lead |

### Fix cycle (replaces the former estimated "time saved")

A **block** is a streak of failing runs on one branch. It is **resolved** when a later run on that branch passes.
A streak counts the blocker + high findings of its first run once: a finding stays in the report until it is
fixed, so summing over runs would count it repeatedly.

| KPI | Formula | Source | Status 2026-10-07 |
|---|---|---|---|
| **Blocks resolved before merge** | resolved streaks; and their blocking findings | events | **2 of 16** blocked branches; **6** blocking findings fixed |
| **Median fix cycle** | median hours from a streak's first failing run to the next passing run | events | **58.6 h** (2 recoveries: too few to read as a trend) |
| **Fix iterations** | median failing runs per resolved streak | events | **3.5** |

**Why there is no "time saved" figure.** Time saved cannot be measured from these streams without assuming a fix
cost or a defect rate, so it is not reported. Its measured stand-ins are:
- the **fix cycle** above;
- the **pull-request review effect** below: cycle time and review rounds before and after adoption, measured
  per PR.

### Measured outcomes (git history and pull requests)

Cohorts per repository, using the date of its first gate run:
- *gated, before adoption*;
- *gated, after adoption*;
- *never gated*: repositories with history but no gate runs.

Merge commits are excluded.

| KPI | Formula | Source | Status 2026-10-07 |
|---|---|---|---|
| **Revert rate** | commits written by `git revert` ÷ non-merge commits, per cohort | git | 0% before (49 commits) / 0% after (36) / 0% ungated (7); 2 gated + 3 ungated repos, all Arijit's own |
| **Fix-commit rate** | Conventional Commits `fix:` / `hotfix:` / `bugfix:` commits ÷ non-merge commits, per cohort | git | 0% / 0% / 14.3%. Only meaningful for repositories that follow Conventional Commits; `ai-sdlc-gate` uses `area: summary` subjects, so read 0% as "convention not used" |
| **PR cycle time** | median hours opened → merged, per cohort | PRs | 0.04 h before (3 PRs) / 0.0 h after (22 PRs), one repository |
| **Review rounds / changes requested / review comments** | median submitted reviews, share of PRs with a change request, median review comments | PRs | 0 / 0% / 0 in both cohorts: a single-maintainer repository, so no review effect can show yet |
| **Revert PR rate** | PRs titled `Revert …` ÷ merged PRs | PRs | 0% |

These outcome rows need team repositories with real review traffic. See the data-access questions.

### Cost

| KPI | Formula | Source | Status 2026-10-07 |
|---|---|---|---|
| **Tokens per run p50 / p90** | percentiles of prompt + completion tokens, metered runs | events | **29,897 / 884,262**; 35.6 M tokens in total; 74.5% of runs report usage |
| **Run time p50 / p90** | percentiles of `duration_s` | events | **49 s / 279 s** |

### Feedback and governance

| KPI | Formula | Source | Status 2026-10-07 |
|---|---|---|---|
| **Positive feedback** | `accepted` ÷ (`accepted` + `false-positive`), from 10 labels | triage | **no data yet** (0 labels) |
| **False-positive rate** | `false-positive` ÷ all labels, per phase and category, from 10 labels per group | triage | **no data yet** |
| **Label coverage** | labels ÷ findings | triage + events | 0% |
| **Unverified finding share** | findings the gate downgraded (evidence not in the file, or self-declared sound) ÷ findings | events | **3.8%** |
| **Skip rate and reasons** | runs with a valid `SDLC-Skip` ÷ runs; the reasons | events | **2.5%** (4 skips) |

## Which slide KPIs we can fill now

The reference slide is Resolve AI's customer slide for MSCI.

- **Filled now with measured numbers:**
  - cases (total and by month, stacked by team);
  - adoption curve and phase per team;
  - active repositories;
  - issues caught before merge (blocks, security-critical runs, blocking findings resolved) and fix cycle;
  - cost per run;
  - pass / block / first-time-right rates.
- **Need data collection first:**
  - **Gate users and committer coverage:** needs ≥ 5 verified users per team, plus git history of the teams'
    repositories.
  - **Positive feedback %:** needs developers to label findings with `ai-sdlc-gate triage`.
  - **Time saved / review effect:** needs pull-request data from team repositories with real reviews.
  - **Quality outcome:** needs git history of team repositories.
  - **Findings per 1k lines:** needs engines from PR #34 on.
- **Not measurable from the gate's streams:** "alerts eliminated" has no counterpart. Incidents avoided would
  need a join with incident tickets, which is out of the gate's scope.

## Data gaps and fixes

| Gap | Cause (measured) | Fix |
|---|---|---|
| 45% of runs unattributable | All 69 `unknown/unknown` runs come from **one** developer machine. The hooks parsed only `github.com` remotes, so other or missing remotes arrived empty, and raw Azure DevOps / GitLab URLs were rejected by the metrics store (those runs were lost). The branch read `HEAD` on unborn branches and during rebases. | Fixed in the engine: the slug is derived from GitHub, GitLab, Bitbucket and Azure DevOps remotes, else `local/<folder>`; the branch comes from `symbolic-ref` and rebase state. Applies to new runs; old events stay as they are. |
| Changed lines only from PR #34 on | older engines | fills as developers update the gate |
| 25% of runs report 0 tokens | the review endpoint does not return usage in every case | return usage from the endpoint |
| No triage labels | the mechanism is new | developers use `ai-sdlc-gate triage`; a PR-comment convention would cover CI runs |
| Git / PR data only for Arijit's repositories | collected with his own access only | team repositories need the owners' OK (see below) |
| `--no-verify` bypasses are in Cloud Logging | separate stream | export `sdlc_event="skip"` log lines into the dataset |

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
| **Delivery & Automation** | adoption phase, cases, pass rate, first-time-right, blocks resolved, fix cycle, run time |
| **Risk & Responsible AI** | security-critical run rate, skip / waiver governance, unverified share, false-positive rate |

India runs every change through the gate, so all output is standardized; these KPIs show it.

## Plugging into the Measurement tool (due 15 Nov)

**Contract.** The Measurement tool consumes:

- **`kpi-runs.json` / `.csv`**: one row per gate run.
  - The columns are `COLUMNS` in `gate/ai_sdlc_gate/kpi.py`, in that order; `team` was appended in this release.
  - `dataset_version` is 1. Changes are additive only; a removed or renamed column bumps the version.
  - List values are `;`-joined in CSV, and categories are written as `category:count` pairs.
  - Times are ISO-8601 UTC; `week` is the ISO week.
- **`kpi-triage.csv`**: one row per finding label.
- **`kpi-summary.json`**: `overall`, `weeks`, `repos` and `teams` KPIs, plus `adoption`, `cases_by_month`,
  `users`, `quality_outcome`, `review_effect`, `sources` and `rules`. `null` means no data.

**Delivery, in two steps.**

1. *Now (no new infrastructure):* a scheduled job on the central repository runs the collectors and
   `ai-sdlc-gate kpi export`, and commits the files to `dashboard/kpi/`. The tool reads them over the GitHub
   API with a read-only token.
2. *Later (if the tool needs live data or filtering):* `GET /v1/kpi?from=&to=&team=` on the existing Cloud Run
   endpoint, returning the same JSON, authorised with the org's Entra sign-in.

**What the tool should own:** cross-source joins (incidents, DORA metrics, survey data) and the management view
across all AI-in-SDLC tools.
