# Metrics

## Where

Branch `metrics` of this repository:

```
events/YYYY/MM.jsonl     one event per gate run (append-only, deduplicated by id)
dashboard/README.md      organisation snapshot, monthly trend, per developer, per repository
dashboard/summary.json   the same numbers for BI tools
dashboard/scoreboard.svg live scoreboard embedded in the main README
dashboard/badge-*.svg    badges embedded in the main README
dashboard/weekly/        Monday snapshots
```

A pinned issue **"AI SDLC Gate — Weekly Report"** mirrors the dashboard every Monday 09:00 IST.

Events are sent from developer machines by the installed gate after every commit and push, using the developer's own
GitHub credential; this repository's own pull requests are recorded by the Self Gate workflow.

## Event contents

Compact by design (≤ 60 KB, no full findings text): repository, actor, ref, sha, PR number, run URL, intent and
how it was detected, phases, verdict, whether the run was flagged (any finding at/above threshold before skips)
and blocked, counts per severity, waived count, skip request (phases, validity, reason ≤ 500 chars), per-phase
verdicts and skill versions, top categories, up to 40 finding briefs (phase, severity, category, title, file),
token usage and duration.

## Definitions

| Metric | Meaning |
|---|---|
| Runs | gate executions (one per push/PR update) |
| Pass rate | runs with verdict pass ÷ runs |
| Flagged | runs where at least one finding met the blocking threshold, regardless of skips |
| Blocked | runs that failed the gate |
| Skips requested / granted | skip trailers seen / skip trailers that met the policy |
| Waived findings | findings neutralised by granted skips |
| Findings per run | total findings (all severities) ÷ runs |
| Top categories | most frequent finding categories |
| Client attested | share of runs whose commits carry the gate's `AI-SDLC-Gate-Client` trailer |

`Flagged − Blocked` is the number of runs that passed only because of a skip.

## Identity

Developers are keyed by their **verified corporate e-mail** (from the Entra sign-in carried in the attestation
trailer); runs without an attestation fall back to the GitHub login. The README scoreboard and the dashboard
tables use the same key, so a person appears once even when they use several GitHub accounts or machines.

## Interpreting per-developer numbers

They describe the interaction between one account and the gate over time. Use them to find where standards are
unclear, where tooling is missing, or where coaching helps. Combine with the skip reasons before drawing
conclusions; a developer working on a legacy module will be flagged more often than one on a green-field service.

## Access

Anyone with read access to this repository can read the `metrics` branch. To restrict management data,
make the repository internal and grant read access to leads only; callers still work because they use the
`AI_SDLC_GATE_TOKEN` to reach the repository.

## Exporting

```bash
git fetch origin metrics && git show origin/metrics:dashboard/summary.json > summary.json
```

or read `events/*.jsonl` directly into your BI tool.
