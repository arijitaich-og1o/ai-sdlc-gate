# Onboarding a repository

1. Copy [templates/caller-workflow.yml](../templates/caller-workflow.yml) to `.github/workflows/sdlc-gate.yml`.
2. Make sure the organisation secrets `LITELLM_BASE_URL`, `LITELLM_API_KEY` and `SDLC_GATE_TOKEN` are shared
   with the repository (`secrets: inherit` forwards them).
3. If the organisation ruleset is not active for the repository, add a branch protection rule requiring the
   status check **`SDLC Gate / SDLC Gate`**.
4. Open a pull request. The gate comments with its report and blocks or passes.

## Options

```yaml
    uses: arijitaich-og1o/ai-sdlc-gate/.github/workflows/sdlc-gate.yml@main
    with:
      gate-ref: v1.0.0   # pin the policy/skills version this repository follows (default: main)
      intent: deploy     # force the phase set for this workflow (default: auto-detect)
      fail-on: medium    # stricter threshold for this repository (default from gate.config.yaml: high)
```

You may run the gate several times with different intents, for example a second job with `intent: deploy`
that only triggers on `release/**` branches.

## How the intent is detected when not forced

1. `SDLC-Intent: <intent>` trailer in any commit message in the range, or in the PR description.
2. Branch name: `release/*`, `deploy/*` → deploy; `hotfix/*` → hotfix; `rfc/*`, `plan/*` → plan; `adr/*`,
   `design/*` → design; `maintenance/*`, `dependabot/*` → maintenance.
3. Changed paths: Dockerfiles, Terraform, Helm/Kubernetes, workflow files → deploy; `docs/adr/**`, OpenAPI,
   protobuf, migrations → design; `docs/planning/**`, charters → plan; changelogs, runbooks, dependency
   manifests → maintenance. When code files are also present the default commit phases (3, 4, 5) are always
   included.
4. Otherwise `commit` → phases 3, 4, 5.

## Repository-specific exclusions

Generated code and fixtures can be excluded organisation-wide in `gate.config.yaml` (`gate.exclude_globs`) via a
code-owner PR to this repository. Lock files, minified assets and binaries are always excluded.

## Costs and timing

Each phase is one model call per ~400 KB chunk of change. A typical PR completes in one to three minutes.
Very large changes are chunked automatically; extremely large single files are truncated with a note.
