# Architecture

## Components

| Component | Where | Responsibility |
|---|---|---|
| Policy | `gate.config.yaml` | phases, intent→phase mapping, detection rules, thresholds, skip rules, models |
| Skills | `skills/NN-*/SKILL.md` | the review checklist and taxonomy the model applies for one phase |
| Engine | `gate/sdlc_gate/` | change collection, intent detection, pre-checks, model calls, waivers, reports, metrics, arbiter |
| Organisation gate | `.github/workflows/org-gate.yml` + `orggate.py` | discovers ungated PR heads/pushes org-wide, reviews them, posts the `SDLC Gate` commit status |
| Reusable gate | `.github/workflows/sdlc-gate.yml` | optional fast path a repository may call directly |
| Arbiter | `.github/workflows/skill-challenge.yml` + `judge.py` | resolves skill challenges |
| Metrics store | `metrics` branch (`events/`, `dashboard/`) | append-only events + generated dashboard |
| Client | `client/` | per-user and managed (admin) installers, global git hooks |
| Identity | `gate/sdlc_gate/identity.py` | Entra device-code sign-in, verified e-mail, commit attestation trailer |

## Engine modules

```
cli.py        argparse entry point: run | intent | validate-skills | precheck | evaluate | challenge | emit-metrics | metrics
config.py     Config (YAML + defaults), severities
changes.py    ChangeSet collection (git range / staged index / paths), exclusions, truncation, chunking, rendering
intent.py     explicit → trailer → branch → paths → default
prechecks.py  deterministic secret / credential / dotenv detection on added lines
skills.py     SKILL.md parsing + directory validation (exactly 7, forbidden instruction patterns)
runner.py     system prompt, per-phase review, waiver application, GateReport
report.py     Markdown rendering (PR comment, step summary)
skip.py       SDLC-Skip / SDLC-Skip-Reason parsing and policy
llm.py        OpenAI-compatible client for LiteLLM: retries, fallbacks, JSON extraction; StaticLLM for tests
metrics.py    compact event, repository_dispatch, JSONL ingest with dedupe, dashboard build
evaluate.py   run a skill on trials, match GROUND_TRUTH, recall/precision/clarity
judge.py      arbiter prompt, deterministic guards, apply decision, CREDITS.md
identity.py   Entra ID device-code login, identity storage, SDLC-Gate-Client attestation trailer
orggate.py    GitHub API client, org-wide discovery of ungated commits, commit status posting
```

## Data flow for one gate run

1. The caller workflow (in the developer's repository) invokes the reusable workflow with the org secrets.
2. The reusable workflow checks out the change and, separately, this repository at `gate-ref`.
3. `sdlc-gate run --base <sha> --head <sha>` builds a `ChangeSet` (per-file diff + post-change content,
   generated/binary files excluded, large files truncated, change set chunked to the budget).
4. Intent is resolved. Pre-checks run. For each phase in scope the skill body, review context and fenced change
   set are sent to LiteLLM with a JSON-only system prompt. Findings are normalised (severity aliases, ids,
   categories) and sorted.
5. Skip trailers are parsed from commit messages and the PR body; approved-label state comes from the workflow.
   Findings in validly skipped phases are marked `waived` unless their category is non-skippable.
6. `GateReport` → Markdown (PR comment upsert, job summary), JSON artifact, compact metrics event dispatched to
   this repository via `repository_dispatch` with the org token.
7. Exit code 0/1 decides the required status check. Exit 2 (engine/LLM error) is also a failure.

## Metrics flow

`sdlc-gate emit-metrics --dispatch` → `repository_dispatch(sdlc-gate-result)` → `metrics-ingest.yml` validates the
event, appends it to `events/YYYY/MM.jsonl` (idempotent by UUID) on the `metrics` branch, regenerates
`dashboard/README.md` + `summary.json`, pushes with rebase-retry. `metrics-weekly.yml` snapshots the dashboard
and updates a pinned issue every Monday.

## Skill challenge flow

See [skill-challenge.md](skill-challenge.md).

## Design decisions

- **Server-side authority, local convenience.** Git hooks cannot be made tamper-proof on a developer machine;
  GitHub rulesets can. Both use the same engine so results agree.
- **Central discovery instead of per-repository files.** The organisation gate finds and reviews changes from
  here, so adoption is not a developer decision and a policy change lands everywhere at once. The reusable
  workflow remains as an optional fast path.
- **Skips are cheap to request, impossible to hide.** A skip needs a real reason and is stored with the developer,
  phases and reason. Management sees skip rates next to pass rates.
- **Run skipped phases anyway.** Waived findings are still produced and recorded, so a skip never hides a leaked
  secret and the organisation learns what is being waived.
- **Objective scoring for challenges.** Skills compete on planted defects with keyword+file matching before the
  arbiter model gives an opinion, and deterministic guards can override the model.
- **Fail closed.** An unavailable model is a failed check, never a silent pass.
- **No workflow engine.** See [decisions/0001-orchestration-without-temporal.md](decisions/0001-orchestration-without-temporal.md).
