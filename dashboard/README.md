# AI SDLC Gate — Organisation Dashboard

_Generated 2026-09-28T12:01:52+00:00 from 23 gate run(s)._

## Organisation snapshot

| Metric | Value |
|---|---|
| Gate runs | 23 |
| Pass rate | 96% |
| Runs flagged (findings at/above threshold) | 1 (4%) |
| Runs blocked | 1 (4%) |
| Skips requested / granted | 0 / 0 |
| Findings waived via skips | 0 |
| Findings per run | 0.65 |
| Runs with local client attestation | 96% |
| Active developers / repositories | 1 / 2 |
| Top finding categories | missing-changelog, capacity-risk, hardcoded-credential, observability-gap, scalability-risk |

## Monthly trend

| Month | Runs | Pass rate | Blocked | Skips granted | Blockers | High | Medium |
|---|---|---|---|---|---|---|---|
| 2026-09 | 23 | 96% | 1 | 0 | 1 | 0 | 3 |

## Developers

| Developer | Runs | Pass rate | Flagged | Blocked | Skips req/granted | Waived findings | Findings/run | Client attested | Top categories | Last seen |
|---|---|---|---|---|---|---|---|---|---|---|
| arijit.aich@og1o.in (@arijitaich-og1o) | 23 | 96% | 1 | 1 | 0/0 | 0 | 0.65 | 96% | missing-changelog, capacity-risk, hardcoded-credential | 2026-09-28 |

## Repositories

| Repository | Runs | Pass rate | Blocked | Skips granted | Developers | Findings/run | Top categories |
|---|---|---|---|---|---|---|---|
| arijitaich-og1o/ai-sdlc-gate | 21 | 95% | 1 | 0 | 1 | 0.05 | hardcoded-credential |
| oneo-dice/oggpt-x-backend | 2 | 100% | 0 | 0 | 1 | 7.0 | missing-changelog, capacity-risk, observability-gap |

### Reading this dashboard

- **Flagged** counts runs where at least one finding met the blocking threshold, before any skip was applied.
- **Blocked** counts runs that failed the gate. Flagged but not blocked means the developer used a valid skip.
- **Skips requested / granted**: requests that failed validation (short reason, missing approval) are counted as requested only.
- **Client attested**: share of runs whose commits carried the local gate's attestation; low values indicate the local client is not installed or was bypassed.
- Developers are identified by their verified corporate e-mail when available, otherwise by GitHub login. These numbers are a quality signal, not a performance score on their own.
