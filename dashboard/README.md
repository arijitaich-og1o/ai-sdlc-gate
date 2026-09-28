# AI SDLC Gate — Organisation Dashboard

_Generated 2026-09-28T06:58:43+00:00 from 2 gate run(s)._

## Organisation snapshot

| Metric | Value |
|---|---|
| Gate runs | 2 |
| Pass rate | 50% |
| Runs flagged (findings at/above threshold) | 1 (50%) |
| Runs blocked | 1 (50%) |
| Skips requested / granted | 0 / 0 |
| Findings waived via skips | 0 |
| Findings per run | 3.0 |
| Runs with local client attestation | 50% |
| Active developers / repositories | 1 / 2 |
| Top finding categories | hardcoded-credential, missing-changelog, observability-gap, scalability-risk, capacity-risk |

## Monthly trend

| Month | Runs | Pass rate | Blocked | Skips granted | Blockers | High | Medium |
|---|---|---|---|---|---|---|---|
| 2026-09 | 2 | 50% | 1 | 0 | 1 | 0 | 1 |

## Developers

| Developer | Runs | Pass rate | Flagged | Blocked | Skips req/granted | Waived findings | Findings/run | Client attested | Top categories | Last seen |
|---|---|---|---|---|---|---|---|---|---|---|
| arijit.aich@og1o.in (@arijitaich-og1o) | 2 | 50% | 1 | 1 | 0/0 | 0 | 3.0 | 50% | hardcoded-credential, missing-changelog, observability-gap | 2026-09-28 |

## Repositories

| Repository | Runs | Pass rate | Blocked | Skips granted | Developers | Findings/run | Top categories |
|---|---|---|---|---|---|---|---|
| arijitaich-og1o/ai-sdlc-gate | 1 | 0% | 1 | 0 | 1 | 1.0 | hardcoded-credential |
| oneo-dice/oggpt-x-backend | 1 | 100% | 0 | 0 | 1 | 5.0 | missing-changelog, observability-gap, scalability-risk |

### Reading this dashboard

- **Flagged** counts runs where at least one finding met the blocking threshold, before any skip was applied.
- **Blocked** counts runs that failed the gate. Flagged but not blocked means the developer used a valid skip.
- **Skips requested / granted**: requests that failed validation (short reason, missing approval) are counted as requested only.
- **Client attested**: share of runs whose commits carried the local gate's attestation; low values indicate the local client is not installed or was bypassed.
- Developers are identified by their verified corporate e-mail when available, otherwise by GitHub login. These numbers are a quality signal, not a performance score on their own.
