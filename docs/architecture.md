# Architecture

## Components

| Component | Where | Responsibility |
|---|---|---|
| Policy | `gate.config.yaml` | phases, intent→phase mapping, detection rules, thresholds, skip rules, models |
| Skills | `skills/NN-*/SKILL.md` | the review checklist and taxonomy the model applies for one phase |
| Engine | `gate/ai_sdlc_gate/` | change collection, intent detection, pre-checks, model calls, waivers, reports, metrics, arbiter |
| Client | `client/` | the gate as deployed: installers (self-service and managed), global git hooks, shim |
| Reusable workflow | `.github/workflows/ai-sdlc-gate.yml` | gates this repository's own pull requests; optional backstop for others |
| Arbiter | `.github/workflows/skill-challenge.yml` + `judge.py` | resolves skill challenges |
| Metrics store | `metrics` branch (`events/`, `dashboard/`) | append-only events + generated dashboard |
| Identity | `gate/ai_sdlc_gate/identity.py` | Entra device-code sign-in, verified e-mail, commit attestation trailer |

## Engine modules

```
cli.py        argparse entry point: run | intent | validate-skills | precheck | evaluate | challenge | emit-metrics | metrics
config.py     Config (YAML + defaults), severities
changes.py    ChangeSet collection (git range / staged index / paths), exclusions, truncation, chunking, rendering
intent.py     explicit → trailer → branch → paths → default
prechecks.py  deterministic secret / credential / dotenv detection on added lines
skills.py     SKILL.md parsing + directory validation (exactly 8, forbidden instruction patterns)
runner.py     system prompt, per-phase review, waiver application, GateReport
report.py     Markdown rendering (PR comment, step summary)
skip.py       SDLC-Skip / SDLC-Skip-Reason parsing and policy
llm.py        OpenAI-compatible client for the model gateway: retries, fallbacks, JSON extraction; StaticLLM for tests
metrics.py    compact event, repository_dispatch, JSONL ingest with dedupe, dashboard build
evaluate.py   run a skill on trials, match GROUND_TRUTH, recall/precision/clarity
judge.py      arbiter prompt, deterministic guards, apply decision, CREDITS.md
identity.py   Entra ID device-code login, identity storage, AI-SDLC-Gate-Client attestation trailer
ghauth.py     locate the developer's existing GitHub credential for sending metrics
```

## Data flow for one gate run (developer machine)

1. `git commit` triggers the global `commit-msg` hook (`git push` the `pre-push` hook); managed installs route
   through a shim that removes `--no-verify` and hook-path overrides.
2. The hook refreshes skills/policy from this repository (daily) and checks the verified identity.
3. `ai-sdlc-gate run --staged` (or `--base/--head` for pushes) builds a `ChangeSet` (per-file diff + post-change content,
   generated/binary files excluded, large files truncated, change set chunked to the budget).
4. Intent is resolved. Pre-checks run. For each phase in scope the skill body, review context and fenced change
   set are sent to the model gateway with a JSON-only system prompt. Findings are normalised (severity aliases, ids,
   categories) and sorted.
5. Skip trailers are parsed from the commit message. Findings in validly skipped phases are marked `waived` unless
   their category is non-skippable.
6. `GateReport` → Markdown printed to the developer, JSON report → compact metrics event dispatched to this
   repository via `repository_dispatch` with the developer's own GitHub credential.
7. Exit code 0 lets the commit/push proceed (and the `AI-SDLC-Gate-Client` trailer is appended); 1 blocks it;
   2 (engine/LLM error) blocks it too (fail closed).

## Metrics flow

`ai-sdlc-gate emit-metrics --dispatch` → `repository_dispatch(ai-sdlc-gate-result)` → `metrics-ingest.yml` validates the
event, appends it to `events/YYYY/MM.jsonl` (idempotent by UUID) on the `metrics` branch, regenerates
`dashboard/README.md` + `summary.json`, pushes with rebase-retry. `metrics-weekly.yml` snapshots the dashboard
and updates a pinned issue every Monday.

## Skill challenge flow

See [skill-challenge.md](skill-challenge.md).

## Design decisions

- **The installed client is the gate.** It is deployed by IT in a location standard users cannot change and applies
  to every repository and tool on the machine. Attestation trailers and per-developer metrics make any bypass visible.
- **No per-repository files.** Nothing is added to projects; policy and skills are pulled by the clients from this
  repository, so a change lands everywhere within a day.
- **Skips are cheap to request, impossible to hide.** A skip needs a real reason and is stored with the developer,
  phases and reason. Management sees skip rates next to pass rates.
- **Run skipped phases anyway.** Waived findings are still produced and recorded, so a skip never hides a leaked
  secret and the organisation learns what is being waived.
- **Objective scoring for challenges.** Skills compete on planted defects with keyword+file matching before the
  arbiter model gives an opinion, and deterministic guards can override the model.
- **Fail closed.** An unavailable model is a failed check, never a silent pass.
- **No workflow engine.** See [decisions/0001-orchestration-without-temporal.md](decisions/0001-orchestration-without-temporal.md).
