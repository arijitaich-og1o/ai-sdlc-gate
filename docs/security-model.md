# Security model

## Threats considered

| Threat | Control |
|---|---|
| Developer disables or edits the gate in their repository | Engine, skills and policy are fetched from this repository at run time; the caller is 20 lines; the check is required by an organisation ruleset with no bypass actors. Required-workflow rulesets (Enterprise) enforce even without a caller. |
| Developer bypasses local hooks | Local hooks are advisory. Server-side check is authoritative. |
| Developer edits skills to weaken them | Skills change only via the arbiter, which requires objective improvement on planted defects; skill text with instruction-smuggling patterns fails validation; CODEOWNERS covers the arbiter itself. |
| Prompt injection in diffs, commit messages, PR bodies or candidate skills | All such content is fenced in explicit tags and the system prompt declares it untrusted; the model is told to report manipulation attempts as `gate-manipulation` (non-waivable). Output is JSON-parsed and normalised; nothing is executed. Untrusted values are passed to shell steps through environment variables, never interpolated. |
| Skip abuse | Minimum reason length, code-owner label for deployment/maintenance, non-waivable categories, every skip recorded with reason and shown to management. |
| Leaked secrets in code | Deterministic pre-checks (independent of the model) block on common key formats, private keys and dotenv files; never waivable. |
| Compromised third-party action | All actions pinned to full commit SHAs; `check_pinned_actions.py` enforces on every PR; Dependabot proposes updates. |
| Token theft from workflows | Least-privilege `permissions` per job; `persist-credentials: false` on checkouts; `pull_request_target` banned; secrets never echoed; report comments use the ephemeral job token. `SDLC_GATE_TOKEN` is scoped to this repository only. |
| Forged metrics | Ingest validates schema, UUID, repository slug, login format, size; events are written only by this repository's workflow with its own token; the `metrics` branch is machine-written and can be protected. |
| Model outage used to slip changes through | Fail closed: any engine or model error is a failed check. |
| Cost or denial-of-service via huge diffs | Exclusions for generated files, per-file truncation, chunking to a fixed budget, 30-minute job timeout, retries with backoff and fallbacks. |
| Fork PRs exfiltrating secrets | Fork PRs receive no secrets and fail; the arbiter refuses forks explicitly. |

## Residual risks

- A sufficiently subtle defect can pass a model review. Skills improve continuously through challenges; the demo
  codebase is the regression suite.
- Repository admins can still push directly if the ruleset is misconfigured; audit ruleset changes.
- The LiteLLM proxy sees the code under review. Keep it inside the organisation's boundary and apply its
  retention policy.

## Hardening checklist for operators

- [ ] Organisation ruleset active with `SDLC Gate / SDLC Gate` required and empty bypass list.
- [ ] Secrets are organisation secrets with repository allow-lists; `SDLC_GATE_TOKEN` scoped to this repository.
- [ ] Auto-merge enabled here; squash only.
- [ ] `metrics` branch protected from human pushes (ruleset: only the workflow's token / app may push).
- [ ] Dependabot PRs for actions merged promptly.
- [ ] Rotation calendar for `LITELLM_API_KEY` and `SDLC_GATE_TOKEN`.
