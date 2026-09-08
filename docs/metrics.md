# Metrics

## Where

Branch `metrics` of this repository:

```
events/YYYY/MM.jsonl     one event per gate run (append-only, deduplicated by id)
dashboard/README.md      organisation snapshot, monthly trend, per developer, per repository
dashboard/summary.json   the same numbers for BI tools
dashboard/weekly/        Monday snapshots
```

A pinned issue **"SDLC Gate — Weekly Report"** mirrors the dashboard every Monday 09:00 IST.

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

`Flagged − Blocked` is the number of runs that passed only because of a skip.

## Interpreting per-developer numbers

They describe the interaction between one account and the gate over time. Use them to find where standards are
unclear, where tooling is missing, or where coaching helps. Combine with the skip reasons before drawing
conclusions; a developer working on a legacy module will be flagged more often than one on a green-field service.

## Access

Anyone with read access to this repository can read the `metrics` branch. To restrict management data,
make the repository internal and grant read access to leads only; callers still work because they use the
`SDLC_GATE_TOKEN` to reach the repository.

## Exporting

```bash
git fetch origin metrics && git show origin/metrics:dashboard/summary.json > summary.json
```

or read `events/*.jsonl` directly into your BI tool.
