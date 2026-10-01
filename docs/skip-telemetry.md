# Design note — skip telemetry (`--no-verify` visibility)

## Decision
The gate runs as a local git hook, which `git --no-verify` skips entirely. Because the hook is also what
reports to the dashboard, a bypass left **no trace**. We add **visibility without enforcement**: a `--no-verify`
is **allowed** but **reported**, so skips are tracked live.

- **Server:** `POST /v1/skip` records a skip against the caller's verified Microsoft identity and emits a
  structured log line (`jsonPayload.sdlc_event="skip"`); `/v1/review` emits a `review` line for usage.
- **Client:** `ai-sdlc-gate report-skip` POSTs the skip, **fire-and-forget** (never blocks, slows or fails the
  git command), and first appends a local line to `~/.ai-sdlc-gate/skip-reports.log` so a lost POST is still
  auditable.
- **Trigger:** the managed git shim (and, later, the non-managed shim) detects `--no-verify` on a gated
  subcommand and calls `report-skip` in the background; it then runs the real git with the flag preserved.

## Alternatives considered
- **Block the bypass (strip `--no-verify`)** — the managed shim can do this (enforce mode). Rejected as the
  default here because the requirement is to *allow* `--no-verify` while seeing it.
- **Server-side CI gate as a required check** — the only *tamper-proof* option, but it is enforcement, not the
  requested visibility, and needs a workflow in every repo.
- **GitHub `repository_dispatch` metrics** — heavier (per-repo tokens/workflows); the authenticated endpoint
  already sees every run, so telemetry rides that channel instead.

## Threat model (what this does and does not do)
- **In scope:** casual/accidental bypass by developers who follow the normal setup. These are reported and
  attributed. On an MDM-managed, non-admin machine the shim cannot be removed, so coverage is high.
- **Out of scope:** a determined developer who invokes the real `git` binary directly, edits PATH, or uninstalls
  the gate evades the shim. This is **visibility, not a security control.** The server-side required-status-check
  ruleset is the actual enforcement boundary; the client layer is convenience + observability.
- Uninstalling is itself detectable by absence: a developer who was reporting and goes silent is a dashboard
  signal.

## Failure modes
- **Telemetry loss is best-effort.** If the endpoint is unreachable the POST is dropped silently (by design, so
  git is never delayed); the local `skip-reports.log` preserves the record for later audit. If zero loss is ever
  required, add a durable local queue flushed on reconnect.
- **Data sent:** only `repo`, `ref`, `sha`, the command, and an optional reason — never diff content or secrets.
  The git remote slug is restricted to owner/name characters before use.
