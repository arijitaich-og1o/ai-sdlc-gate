# AI SDLC Gate — Otto Group One.O India

Every change a developer commits, pushes or releases in the organisation passes through one gate. The gate
reviews the change against the seven phases of the software development life cycle with the organisation's own
LiteLLM models, blocks it until findings are fixed or explicitly waived with a recorded reason, and keeps a
scoreboard so we all know how we are doing. It is installed once on every developer machine, by IT or with a
one-click installer, and from then on every commit and push from any IDE or terminal goes through it. There is
nothing to add to any project.

![Gate runs](https://github.com/arijitaich-og1o/ai-sdlc-gate/blob/metrics/dashboard/badge-runs.svg?raw=true)
![Pass rate](https://github.com/arijitaich-og1o/ai-sdlc-gate/blob/metrics/dashboard/badge-pass-rate.svg?raw=true)
![Blocked](https://github.com/arijitaich-og1o/ai-sdlc-gate/blob/metrics/dashboard/badge-blocked.svg?raw=true)
![Skips granted](https://github.com/arijitaich-og1o/ai-sdlc-gate/blob/metrics/dashboard/badge-skips.svg?raw=true)

<sub>Badges and the scoreboard below are generated from live gate results and appear after the first recorded run.</sub>

## The seven skills

| Phase | Skill | What it looks at |
|---|---|---|
| 1 | [Planning](skills/01-planning/SKILL.md) | charters, RFCs, roadmaps |
| 2 | [Requirements Analysis](skills/02-requirements/SKILL.md) | PRDs, user stories, acceptance criteria |
| 3 | [Design](skills/03-design/SKILL.md) | ADRs, API contracts, schemas, security design |
| 4 | [Development](skills/04-development/SKILL.md) | source code: vulnerabilities, secrets, correctness, standards |
| 5 | [Testing](skills/05-testing/SKILL.md) | test coverage and quality for the change |
| 6 | [Deployment](skills/06-deployment/SKILL.md) | pipelines, containers, infrastructure as code |
| 7 | [Maintenance](skills/07-maintenance/SKILL.md) | dependencies, runbooks, changelogs, backups, SLOs |

Which phases apply depends on what you are doing: planning work is checked against phases 1–2, a normal commit
or pull request against 3–5, a release or deployment against 3–7, a hotfix against 4–7. You can state your
intent explicitly with an `SDLC-Intent:` trailer; otherwise it is inferred from your branch and files.

## Live scoreboard

![SDLC Gate scoreboard](https://github.com/arijitaich-og1o/ai-sdlc-gate/blob/metrics/dashboard/scoreboard.svg?raw=true)

Refreshed after every gate run. Full tables per developer, repository and month:
[dashboard](../../blob/metrics/dashboard/README.md) · [JSON](../../blob/metrics/dashboard/summary.json).
Developers are identified by their verified corporate e-mail. See [docs/metrics.md](docs/metrics.md).

## Install once, then just work

On company devices IT installs the gate for you. On any other machine, download and run the installer for your
operating system:

| OS | Installer |
|---|---|
| Windows | [install.cmd](client/install.cmd) (double-click) or `irm https://raw.githubusercontent.com/arijitaich-og1o/ai-sdlc-gate/main/client/install.ps1 \| iex` |
| macOS | [install.command](client/install.command) (double-click) or `curl -fsSL https://raw.githubusercontent.com/arijitaich-og1o/ai-sdlc-gate/main/client/install.sh \| bash` |
| Linux / WSL | `curl -fsSL https://raw.githubusercontent.com/arijitaich-og1o/ai-sdlc-gate/main/client/install.sh \| bash` |

Requirements: git and Python 3.10+. The installer finishes with two one-time steps (it prompts for them):

```bash
sdlc-gate identity login     # one-click Microsoft sign-in; your corporate e-mail becomes your gate identity
sdlc-gate configure          # store your LiteLLM key (from the platform team)
```

When the gate blocks a change, fix the findings and commit again. If a phase genuinely cannot be satisfied right
now, waive it with a reason. The waiver is recorded and visible to management:

```
SDLC-Skip: 5
SDLC-Skip-Reason: Tests are being rewritten in PAY-1432; this commit only moves files and adds no logic.
```

Leaked secrets, hard-coded credentials and known-vulnerable dependencies can never be waived. Skips of the
deployment and maintenance phases are highlighted separately on the dashboard. Details:
[developer guide](docs/onboarding-developers.md) · [skip policy](docs/skip-policy.md).

## How enforcement works

The gate hooks into git itself on the developer's machine, so it applies to every repository and every tool that
commits or pushes. It fails closed, requires a verified identity, stamps each passing commit with an attestation,
and reports every run to the scoreboard. On company devices IT installs it in managed mode, where standard users
cannot disable it. Details in [docs/enforcement.md](docs/enforcement.md).

**IT roll-out:** push `client/managed/install-managed.ps1` (Windows) or `client/managed/install-managed.sh` (macOS,
Linux) through Intune, Jamf, SCCM or Ansible as administrator. Developers then only sign in once.

## Challenging a skill

Think a skill misses things, or flags too much? Improve it. Open a pull request in this repository that changes
`skills/<phase>/SKILL.md` and bumps its version. The **Skill Challenge** workflow validates your version against the
current one, scores both, and decides to keep the current skill, adopt yours, or absorb the parts of yours that
are better. Adopted work is written to your branch, you are credited in [CREDITS.md](CREDITS.md), and the pull
request merges automatically. Rejected challenges are closed with the scores so you can try again. The repository
always holds exactly seven skills. Read [docs/skill-challenge.md](docs/skill-challenge.md) before your first
challenge.

## Documentation

- [Developer guide](docs/onboarding-developers.md) · [Skip policy](docs/skip-policy.md)
- [Central set-up](docs/setup-central-repo.md)
- [Enforcement and identity](docs/enforcement.md) · [Security](SECURITY.md)
- [Metrics](docs/metrics.md) · [Skill challenge](docs/skill-challenge.md) · [Contributing](CONTRIBUTING.md)
