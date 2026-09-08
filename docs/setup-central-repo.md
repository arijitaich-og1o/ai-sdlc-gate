# Setting up the central repository (platform owner, once)

## 1. Secrets

Create these as **organisation secrets** shared with all repositories (Settings → Secrets and variables →
Actions → New organization secret), or per repository if preferred:

| Secret | Value |
|---|---|
| `LITELLM_BASE_URL` | `https://litellm-dev.dev.aime.osp-fine.de` |
| `LITELLM_API_KEY` | the LiteLLM virtual key for this gate (create a dedicated key with a spend limit) |
| `SDLC_GATE_TOKEN` | a fine-grained personal access token or GitHub App token for **all repositories of the organisation** with **Contents: read**, **Pull requests: read & write**, **Commit statuses: read & write**, **Metadata: read**, and additionally **Contents: read & write** on `arijitaich-og1o/ai-sdlc-gate` (metrics branch, arbiter pushes) |

`SDLC_GATE_TOKEN` powers the organisation gate: it lists repositories and pull requests, checks out the code under
review, posts the `SDLC Gate` commit status and PR comments, records metrics, and lets the arbiter push resolution
commits. A GitHub App installation token is preferred over a personal token for auditability.

Never put these values in files. The engine reads them from the environment at run time.

## 2. Repository settings for this repository

- **Branches → main**: protect via ruleset (below).
- **General → Pull Requests**: enable *Allow auto-merge* and *Allow squash merging*; disable merge commits.
- **Actions → General**: *Allow all actions and reusable workflows* is fine because callers pin by SHA; set
  *Workflow permissions* to *Read repository contents and packages permissions* (workflows declare what they need).
- **Labels**: create `sdlc-skip-approved`, `challenge:accepted`, `challenge:rejected`, `metrics`.

## 3. Rulesets

Import [templates/org-ruleset.json](../templates/org-ruleset.json) as an **organisation ruleset**
(Organisation → Settings → Repository → Rulesets → New branch ruleset → Import). Adjust:

- `repository_id` under the `workflows` rule to this repository's numeric id
  (`gh api repos/arijitaich-og1o/ai-sdlc-gate --jq .id`). This makes GitHub itself require
  `.github/workflows/sdlc-gate.yml` to pass on every repository, even one that has not added the caller.
  Note: the `workflows` rule (GitHub Enterprise) is optional. On any plan the `required_status_checks` rule plus the
  organisation gate in this repository is sufficient and needs nothing in the target repositories.
- The required status check context is `SDLC Gate` (the commit status posted by the organisation gate). Repositories
  that also use the optional caller produce a check named `gate / SDLC Gate`; the organisation gate recognises it
  and skips the duplicate review.
- Keep `bypass_actors` empty. If an emergency bypass role is needed, add a single admin team and audit its use.

For this repository additionally require the checks `Validate Repository / Validate (3.10)`,
`Validate Repository / Validate (3.12)` and `Skill Challenge / Arbitrate` (the last one only fires on skill PRs).

## 4. Identity provider

Register a public client application in Microsoft Entra ID ("SDLC Gate client", *Allow public client flows* on),
and put its tenant id and client id into `gate.config.yaml` under `identity:` (see
[enforcement.md](enforcement.md)). Set `identity.required: true` once developers have had a week to sign in.

## 5. Managed client roll-out

Deploy `client/managed/install-managed.ps1` (Windows) / `install-managed.sh` (macOS, Linux, WSL) through
Intune / Jamf / Ansible as administrator. Standard users then cannot disable or bypass the local gate.

## 6. First run

1. Push this repository. `Validate Repository` and `Self Gate` run on `main`; `Organisation Gate` starts on its
   five-minute schedule (trigger it once manually from the Actions tab to verify the token).
   Set `org_gate.owners` in `gate.config.yaml` to the organisation(s) to cover.
2. Trigger `Metrics Weekly Report` manually once (Actions → workflow_dispatch) to confirm the token works; the
   `metrics` branch is created on the first ingested event.
3. In any repository open a PR containing a fake `AKIA…` string and confirm the `SDLC Gate` status turns red within
   five minutes, then a PR with `SDLC-Skip` trailers to confirm waivers and metrics.

## 7. Operating

- Bump the gate version with a tag (`vX.Y.Z`) after meaningful policy or engine changes; repositories that pin
  `gate-ref` upgrade deliberately, others follow `main`.
- Watch LiteLLM spend for the gate key; a typical PR costs a few thousand tokens per phase.
- Review `dashboard/README.md` on the `metrics` branch; the weekly issue mirrors it.
- Rotate the two secrets on a schedule (see SECURITY.md).
