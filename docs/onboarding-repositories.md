# Repositories

**There is nothing to do.** Every repository under the configured owners (`org_gate.owners` in `gate.config.yaml`) is
gated by the [Organisation Gate](../.github/workflows/org-gate.yml) workflow in this repository:

1. every few minutes it lists open pull requests and recent pushes to the default and long-lived branches;
2. commits without an `SDLC Gate` status are checked out here and reviewed;
3. the verdict is posted as a commit status (`pending` → `success` / `failure` / `error`), the report is commented on the
   pull request, and the run is recorded in the metrics;
4. the organisation ruleset requires the `SDLC Gate` status, so nothing merges without it.

New repositories are covered as soon as they exist. Archived repositories are ignored. Draft pull requests are gated
when they leave draft.

## Latency

Results appear within about five minutes of a push (GitHub's shortest schedule). Developers who installed the local
client already saw the findings before pushing, so the central result is a confirmation rather than a surprise.

## Optional fast path

A repository may additionally call the reusable workflow ([templates/caller-workflow.yml](../templates/caller-workflow.yml))
to get results seconds after a push instead of minutes. The organisation gate detects that check and does not run a
second review for the same commit. This is a convenience, not a requirement, and removing the file does not remove
the gate.

## Intent detection

1. `SDLC-Intent: <intent>` trailer in a commit message in the range, or in the PR description.
2. Branch name: `release/*`, `deploy/*` → deploy; `hotfix/*` → hotfix; `rfc/*`, `plan/*` → plan; `adr/*`, `design/*` →
   design; `maintenance/*`, `dependabot/*` → maintenance.
3. Changed paths: Dockerfiles, Terraform, Helm/Kubernetes, workflow files → deploy; `docs/adr/**`, OpenAPI, protobuf,
   migrations → design; `docs/planning/**`, charters → plan; changelogs, runbooks, dependency manifests → maintenance.
   When code files are also present the default commit phases (3, 4, 5) are always included.
4. Otherwise `commit` → phases 3, 4, 5.

## Exclusions

Generated code and fixtures can be excluded organisation-wide in `gate.config.yaml` (`gate.exclude_globs`) through a
code-owner pull request to this repository. Lock files, minified assets and binaries are always excluded.
