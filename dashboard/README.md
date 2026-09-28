# AI SDLC Gate — Organisation Dashboard

_Generated 2026-09-28T15:42:12+00:00 from 25 gate run(s)._

## Organisation snapshot

| Metric | Value |
|---|---|
| Gate runs | 25 |
| Pass rate | 92% |
| Runs flagged (findings at/above threshold) | 2 (8%) |
| Runs blocked | 2 (8%) |
| Skips requested / granted | 0 / 0 |
| Findings waived via skips | 0 |
| Findings per run | 1.04 |
| Runs with local client attestation | 96% |
| Active developers / repositories | 1 / 2 |
| Top finding categories | missing-changelog, observability-gap, capacity-risk, hardcoded-credential, scalability-risk |

## Monthly trend

| Month | Runs | Pass rate | Blocked | Skips granted | Blockers | High | Medium |
|---|---|---|---|---|---|---|---|
| 2026-09 | 25 | 92% | 2 | 0 | 1 | 1 | 10 |

## Developers

| Developer | Runs | Pass rate | Flagged | Blocked | Skips req/granted | Waived findings | Findings/run | Client attested | Top categories | Last seen |
|---|---|---|---|---|---|---|---|---|---|---|
| arijit.aich@og1o.in (@arijitaich-og1o) | 25 | 92% | 2 | 2 | 0/0 | 0 | 1.04 | 96% | missing-changelog, observability-gap, capacity-risk | 2026-09-28 |

## Repositories

| Repository | Runs | Pass rate | Blocked | Skips granted | Developers | Findings/run | Top categories |
|---|---|---|---|---|---|---|---|
| arijitaich-og1o/ai-sdlc-gate | 23 | 91% | 2 | 0 | 1 | 0.52 | hardcoded-credential, missing-tests, missing-negative-tests |
| oneo-dice/oggpt-x-backend | 2 | 100% | 0 | 0 | 1 | 7.0 | missing-changelog, capacity-risk, observability-gap |

### Reading this dashboard

- **Flagged** counts runs where at least one finding met the blocking threshold, before any skip was applied.
- **Blocked** counts runs that failed the gate. Flagged but not blocked means the developer used a valid skip.
- **Skips requested / granted**: requests that failed validation (short reason, missing approval) are counted as requested only.
- **Client attested**: share of runs whose commits carried the local gate's attestation; low values indicate the local client is not installed or was bypassed.
- Developers are identified by their verified corporate e-mail when available, otherwise by GitHub login. These numbers are a quality signal, not a performance score on their own.
