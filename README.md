# AI SDLC Gate — Otto Group One.O India

One gate, seven skills, every repository. The SDLC Gate reviews each change a developer commits, pushes or
releases against the seven phases of the software development life cycle, using the organisation's own
LiteLLM endpoint, and blocks the change until findings are fixed or explicitly waived with a recorded
justification. It runs entirely in GitHub Actions from this repository; developers can additionally install
a local hook for fast feedback in any IDE or terminal.

| Phase | Skill | Checks |
|---|---|---|
| 1 | [Planning](skills/01-planning/SKILL.md) | charters, RFCs, roadmaps: scope, owners, metrics, risks, compliance |
| 2 | [Requirements Analysis](skills/02-requirements/SKILL.md) | PRDs, stories, acceptance criteria: testability, consistency, NFRs, privacy |
| 3 | [Design](skills/03-design/SKILL.md) | ADRs, APIs, schemas: contracts, security design, resilience, data protection |
| 4 | [Development](skills/04-development/SKILL.md) | code: vulnerabilities, secrets, correctness, dependencies, standards |
| 5 | [Testing](skills/05-testing/SKILL.md) | tests: coverage of the change, negative/security cases, determinism |
| 6 | [Deployment](skills/06-deployment/SKILL.md) | pipelines, containers, IaC: supply chain, least privilege, rollback |
| 7 | [Maintenance](skills/07-maintenance/SKILL.md) | operability: dependency health, runbooks, changelogs, backups, SLOs |

The repository always holds **exactly these seven skills**. They evolve only through the automated
[skill challenge](docs/skill-challenge.md).

## How a change flows through the gate

```
developer commits / pushes / opens PR
        │
        ▼
 intent detection ─── SDLC-Intent trailer › branch name › changed paths › default
        │              plan→[1,2]  design→[2,3]  commit/pr→[3,4,5]  deploy/release→[3..7]  hotfix→[4..7]
        ▼
 deterministic pre-checks ──── secrets, private keys, .env files  (never skippable)
        │
        ▼
 one LiteLLM review per phase, driven by that phase's SKILL.md
        │
        ▼
 skip trailers applied ──── SDLC-Skip / SDLC-Skip-Reason (recorded; secrets and creds never waived)
        │
        ├──► PR comment + job summary + artifact
        ├──► metrics event → central repo → `metrics` branch → management dashboard
        ▼
 required status check "SDLC Gate" passes or fails
```

Findings at or above the blocking threshold (`high` by default, see [gate.config.yaml](gate.config.yaml))
fail the check. The gate **fails closed**: if LiteLLM cannot be reached, the change does not pass.

## Enforcement model

- **Authoritative:** the reusable workflow [`.github/workflows/sdlc-gate.yml`](.github/workflows/sdlc-gate.yml)
  is called by every repository (a 20-line caller, see [templates/caller-workflow.yml](templates/caller-workflow.yml))
  and required by an organisation ruleset ([templates/org-ruleset.json](templates/org-ruleset.json)). Developers
  cannot edit the engine, the skills or the policy from their own repositories, and cannot merge without the check.
- **Advisory:** the local hooks in [`client/`](client/) run the identical engine on `commit` and `push` so
  findings appear before the code leaves the laptop. They are installed once per machine via `core.hooksPath`
  and therefore work from any IDE (VS Code, IntelliJ, Vim, the terminal) on Windows, WSL, macOS and Linux.
  A developer who bypasses the hook with `--no-verify` still hits the server-side gate.
- **Waivers:** a phase can be skipped only with a justification of at least 40 characters, recorded in the
  metrics. Deployment and maintenance skips require the `sdlc-skip-approved` label from a code owner. Leaked
  secrets, hard-coded credentials, known-vulnerable dependencies and attempts to manipulate the gate can never
  be waived. See [docs/skip-policy.md](docs/skip-policy.md).

## Quick start

**Platform owner (once):** follow [docs/setup-central-repo.md](docs/setup-central-repo.md) to add the three
secrets (`LITELLM_BASE_URL`, `LITELLM_API_KEY`, `SDLC_GATE_TOKEN`), apply the ruleset and enable auto-merge.

**Every repository:** copy [templates/caller-workflow.yml](templates/caller-workflow.yml) to
`.github/workflows/sdlc-gate.yml`. Nothing else. Details in [docs/onboarding-repositories.md](docs/onboarding-repositories.md).

**Every developer (optional, recommended):**

```bash
curl -fsSL https://raw.githubusercontent.com/arijitaich-og1o/ai-sdlc-gate/main/client/install.sh | bash
```

```powershell
irm https://raw.githubusercontent.com/arijitaich-og1o/ai-sdlc-gate/main/client/install.ps1 | iex
```

Details in [docs/onboarding-developers.md](docs/onboarding-developers.md).

**Management:** the dashboard lives on the [`metrics` branch](../../tree/metrics/dashboard) (`dashboard/README.md`,
`dashboard/summary.json`) and is refreshed on every gate run and summarised weekly in a pinned issue. See
[docs/metrics.md](docs/metrics.md).

## Challenging a skill

Any developer who believes a skill can be better opens a pull request that changes `skills/<phase>/SKILL.md`.
The [Skill Challenge](.github/workflows/skill-challenge.yml) workflow runs the current and the proposed skill
against the [demo codebase](demo_codebase/) of planted defects, scores recall/precision/clarity, and asks the
arbiter model to keep, replace or merge. Accepted work is written back to the branch with the contributor
credited in [CREDITS.md](CREDITS.md) and the PR is auto-merged; rejected challenges are closed with the full
comparison. Details in [docs/skill-challenge.md](docs/skill-challenge.md).

## Repository layout

```
.github/workflows/    sdlc-gate.yml (reusable gate), self-gate, validate-repo, skill-challenge, metrics-*
gate/                 Python engine (`sdlc-gate` CLI) + tests
skills/               the seven phase skills (SKILL.md each)
demo_codebase/        planted-defect sandboxes + GROUND_TRUTH.yaml per phase
client/               developer installers and git hooks
templates/            caller workflow and organisation ruleset
scripts/              repository hygiene checks (pinned actions, ground truth)
docs/                 architecture, onboarding, policies, security model
gate.config.yaml      the policy: phases, intents, thresholds, skip rules, models
```

## Local usage

```bash
pip install ./gate
export LITELLM_BASE_URL=https://litellm-dev.dev.aime.osp-fine.de LITELLM_API_KEY=...   # from your password manager
sdlc-gate run --base origin/main --head HEAD             # review your branch
sdlc-gate run --staged --intent commit                    # review what you are about to commit
sdlc-gate intent --base origin/main                       # see which phases would apply
sdlc-gate evaluate --skill skills/04-development/SKILL.md --demo demo_codebase   # score a skill
```

Any chat model exposed by the LiteLLM proxy can be selected in `gate.config.yaml` or with `SDLC_GATE_MODEL` /
`SDLC_JUDGE_MODEL`.

## Security

See [SECURITY.md](SECURITY.md) and [docs/security-model.md](docs/security-model.md). Highlights: actions pinned
to commit SHAs, least-privilege tokens, no `pull_request_target`, untrusted content fenced and never executed,
fail-closed behaviour, non-waivable secret detection, code owners on everything except skills, and the arbiter
guarded by deterministic score checks.
