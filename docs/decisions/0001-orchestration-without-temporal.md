# ADR 0001 — Orchestrate with GitHub Actions, not Temporal

**Status:** accepted · **Date:** 2026-09-09

## Context

Temporal is a durable-execution platform: workflows written in code run on worker fleets, survive process and
infrastructure failures, and get retries, timers, signals and long-lived state for free. It is excellent for
multi-step business processes that run for hours to months and must never lose their place.

The SDLC Gate has these properties:

- each run is short (one to a few minutes), stateless and idempotent (re-run the check, get the same result);
- the run must happen exactly where GitHub decides whether a merge is allowed, because a required status check
  is the only non-bypassable control we have;
- retries, timeouts and concurrency control are already provided by Actions (`timeout-minutes`, retry logic in
  the engine, `concurrency:` groups);
- the only multi-step process (the skill challenge) is also minutes long and its only "human step" is a PR
  review that GitHub already models.

## Decision

Run everything as GitHub Actions workflows from this repository. Do not introduce Temporal.

## Consequences

- No servers, workers or databases to operate; the whole system is this repository plus GitHub.
- Metrics use an append-only branch instead of a database. If reporting needs grow (ad-hoc queries, SLAs on
  freshness), export the JSONL to a warehouse rather than adding a workflow engine.
- We accept Actions' limits: 6-hour job cap, 64 KB `repository_dispatch` payloads, eventual consistency of the
  metrics branch under high concurrency (handled by rebase-retry).

## When to revisit

Temporal (or an equivalent) would earn its place if any of these become true:

1. the gate must run outside GitHub (Azure DevOps, GitLab, on-prem SCM) with one orchestrator across all of them;
2. a review needs to pause for hours or days for a human decision *outside* a pull request (e.g. a security
   team sign-off in a separate tool) and resume exactly where it stopped;
3. we need per-organisation rate limiting and queuing of model calls across hundreds of concurrent runs that
   Actions' concurrency groups cannot express;
4. the challenge arbiter evolves into a long-running tournament with many stages and partial results.

Until then, an orchestrator would add operational surface without adding enforcement.
