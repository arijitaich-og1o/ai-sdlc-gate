# AI SDLC Gate — Organisation Dashboard

_Generated 2026-09-28T11:50:05+00:00 from 9 gate run(s)._

## Organisation snapshot

| Metric | Value |
|---|---|
| Gate runs | 9 |
| Pass rate | 89% |
| Runs flagged (findings at/above threshold) | 1 (11%) |
| Runs blocked | 1 (11%) |
| Skips requested / granted | 0 / 0 |
| Findings waived via skips | 0 |
| Findings per run | 1.67 |
| Runs with local client attestation | 89% |
| Active developers / repositories | 1 / 2 |
| Top finding categories | missing-changelog, capacity-risk, hardcoded-credential, observability-gap, scalability-risk |

## Monthly trend

| Month | Runs | Pass rate | Blocked | Skips granted | Blockers | High | Medium |
|---|---|---|---|---|---|---|---|
| 2026-09 | 9 | 89% | 1 | 0 | 1 | 0 | 3 |

## Developers

| Developer | Runs | Pass rate | Flagged | Blocked | Skips req/granted | Waived findings | Findings/run | Client attested | Top categories | Last seen |
|---|---|---|---|---|---|---|---|---|---|---|
| arijit.aich@og1o.in (@arijitaich-og1o) | 9 | 89% | 1 | 1 | 0/0 | 0 | 1.67 | 89% | missing-changelog, capacity-risk, hardcoded-credential | 2026-09-28 |

## Repositories

| Repository | Runs | Pass rate | Blocked | Skips granted | Developers | Findings/run | Top categories |
|---|---|---|---|---|---|---|---|
| arijitaich-og1o/ai-sdlc-gate | 7 | 86% | 1 | 0 | 1 | 0.14 | hardcoded-credential |
| oneo-dice/oggpt-x-backend | 2 | 100% | 0 | 0 | 1 | 7.0 | missing-changelog, capacity-risk, observability-gap |

### Reading this dashboard

- **Flagged** counts runs where at least one finding met the blocking threshold, before any skip was applied.
- **Blocked** counts runs that failed the gate. Flagged but not blocked means the developer used a valid skip.
- **Skips requested / granted**: requests that failed validation (short reason, missing approval) are counted as requested only.
- **Client attested**: share of runs whose commits carried the local gate's attestation; low values indicate the local client is not installed or was bypassed.
- Developers are identified by their verified corporate e-mail when available, otherwise by GitHub login. These numbers are a quality signal, not a performance score on their own.
