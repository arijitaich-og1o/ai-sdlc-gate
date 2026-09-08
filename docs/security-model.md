# Security model

## Threats considered

| Threat | Control |
|---|---|
| Developer disables the gate on a managed device | Engine, hooks, policy, shim and PATH entry are administrator-owned; the hooks path is set in the system git configuration and re-forced by the shim on every invocation; `--no-verify` is stripped. |
| Developer bypasses the gate (unmanaged machine, local admin) | Commits lack the `SDLC-Gate-Client` attestation and runs stop appearing in metrics; the scoreboard shows the attested share per developer. |
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

- A sufficiently subtle defect can pass a model review. Skills improve continuously through challenges; the trials
  codebase is the regression suite.
- Repository admins can still push directly if the ruleset is misconfigured; audit ruleset changes.
- The LiteLLM proxy sees the code under review. Keep it inside the organisation's boundary and apply its
  retention policy.

## Hardening checklist for operators

- [ ] Managed client deployed to all company devices; attested share on the scoreboard near 100 %.
- [ ] `identity.required: true` and Entra app configured.
- [ ] Secrets in this repository only; per-developer LiteLLM keys with spend limits.
- [ ] Auto-merge enabled here; squash only.
- [ ] `metrics` branch protected from human pushes (ruleset: only the workflow's token / app may push).
- [ ] Dependabot PRs for actions merged promptly.
- [ ] Rotation calendar for `LITELLM_API_KEY` and `SDLC_GATE_TOKEN`.
