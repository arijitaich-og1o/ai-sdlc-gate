# Setting up the central repository (platform owner, once)

## 1. Secrets (this repository only)

| Secret | Used by | Value |
|---|---|---|
| `LITELLM_BASE_URL` | self gate, skill challenge | `https://litellm-dev.dev.aime.osp-fine.de` |
| `LITELLM_API_KEY` | self gate, skill challenge | a dedicated LiteLLM virtual key with a spend limit |
| `SDLC_GATE_TOKEN` | skill challenge (pushing resolution commits so checks re-run) | fine-grained PAT or GitHub App token with **Contents: read & write** and **Pull requests: read & write** on this repository |

Developers' machines never receive these. Each developer stores their **own** LiteLLM key with `sdlc-gate configure`
(issue one virtual key per developer or per team in LiteLLM so spend is attributable), and metrics are sent with the
developer's own GitHub credential.

## 2. Repository settings

- Protect `main`: require a pull request, one code-owner review, and the checks `Validate Repository / Validate (3.10)`,
  `Validate Repository / Validate (3.12)`, `Self Gate / SDLC Gate` and `Skill Challenge / Arbitrate`. No bypass actors.
- Give all developers **write** access (needed to open skill challenges and to record metrics via `repository_dispatch`);
  the branch protection prevents direct pushes to `main`.
- Enable *Allow auto-merge* and *Allow squash merging*; disable merge commits.
- Labels: `challenge:accepted`, `challenge:rejected`, `metrics`.
- Protect the `metrics` branch from human pushes (ruleset: only the Actions token may push).

## 3. Identity provider

Register a public client application in Microsoft Entra ID ("SDLC Gate client", *Allow public client flows* on) and put
its tenant id and client id into `gate.config.yaml` under `identity:` (see [enforcement.md](enforcement.md)).

## 4. Client roll-out

- **Company devices:** deploy `client/managed/install-managed.ps1` (Windows) / `client/managed/install-managed.sh`
  (macOS, Linux, WSL) as administrator through Intune, Jamf, SCCM or Ansible. The script is idempotent and safe to
  re-run; it also installs a daily refresh so policy and skill changes propagate without redeploying.
- **Other machines:** point developers at the installers in the README.
- Tell developers to run `sdlc-gate identity login` and `sdlc-gate configure` once.

## 5. First run

1. Push this repository; `Validate Repository` and `Self Gate` run on `main`.
2. Install the client on one machine, sign in, and commit a file containing a fake `AKIA…` string in any repository:
   the commit must be blocked. Commit a change with `SDLC-Skip` trailers: it must pass with the skip recorded, and the
   scoreboard on the `metrics` branch must show the run within a minute.
3. Trigger `Metrics Weekly Report` manually once to create the weekly issue.

## 6. Operating

- Tag releases (`vX.Y.Z`); clients follow `main` by default and can be pinned to a tag with `SDLC_GATE_REF` at install.
- Watch LiteLLM spend per developer key; a typical commit costs a few thousand tokens per phase.
- Review `dashboard/README.md` on the `metrics` branch; the weekly issue mirrors it. Low "client attested" shares point
  at machines where the gate is missing.
- Rotate the LiteLLM keys and `SDLC_GATE_TOKEN` on a schedule (see SECURITY.md).
