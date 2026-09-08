# Setting up the central repository (platform owner, once)

## 1. Secrets

Create these as **organisation secrets** shared with all repositories (Settings → Secrets and variables →
Actions → New organization secret), or per repository if preferred:

| Secret | Value |
|---|---|
| `LITELLM_BASE_URL` | `https://litellm-dev.dev.aime.osp-fine.de` |
| `LITELLM_API_KEY` | the LiteLLM virtual key for this gate (create a dedicated key with a spend limit) |
| `SDLC_GATE_TOKEN` | a fine-grained personal access token or GitHub App token with **Contents: read & write** and **Pull requests: read & write** on `arijitaich-og1o/ai-sdlc-gate` only |

`SDLC_GATE_TOKEN` is used for three things: recording metrics (`repository_dispatch` into this repository),
reading this repository from callers if it is private, and letting the arbiter push resolution commits that
re-trigger checks. A GitHub App installation token is preferred over a personal token for auditability.

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
  Note: *required workflows* rulesets require GitHub Enterprise; on Team plans use the
  `required_status_checks` rule plus the caller template in every repository.
- The required status check context is `SDLC Gate / SDLC Gate` (workflow name / job name).
- Keep `bypass_actors` empty. If an emergency bypass role is needed, add a single admin team and audit its use.

For this repository additionally require the checks `Validate Repository / Validate (3.10)`,
`Validate Repository / Validate (3.12)` and `Skill Challenge / Arbitrate` (the last one only fires on skill PRs).

## 4. First run

1. Push this repository. `Validate Repository` and `Self Gate` run on `main`.
2. Trigger `Metrics Weekly Report` manually once (Actions → workflow_dispatch) to confirm the token works; the
   `metrics` branch is created on the first ingested event.
3. Onboard one pilot repository with the caller template and open a PR containing a fake `AKIA…` string to
   confirm blocking, then a PR with `SDLC-Skip` trailers to confirm waivers and metrics.

## 5. Operating

- Bump the gate version with a tag (`vX.Y.Z`) after meaningful policy or engine changes; repositories that pin
  `gate-ref` upgrade deliberately, others follow `main`.
- Watch LiteLLM spend for the gate key; a typical PR costs a few thousand tokens per phase.
- Review `dashboard/README.md` on the `metrics` branch; the weekly issue mirrors it.
- Rotate the two secrets on a schedule (see SECURITY.md).
