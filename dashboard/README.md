# AI SDLC Gate — Organisation Dashboard

_Generated 2026-09-09T00:26:56+00:00 from 5 gate run(s)._

## Organisation snapshot

| Metric | Value |
|---|---|
| Gate runs | 5 |
| Pass rate | 80% |
| Runs flagged (findings at/above threshold) | 1 (20%) |
| Runs blocked | 1 (20%) |
| Skips requested / granted | 0 / 0 |
| Findings waived via skips | 0 |
| Findings per run | 1.2 |
| Runs with local client attestation | 0% |
| Active developers / repositories | 2 / 2 |
| Top finding categories | missing-negative-tests, hardcoded-credential, hardcoded-configuration |

## Monthly trend

| Month | Runs | Pass rate | Blocked | Skips granted | Blockers | High | Medium |
|---|---|---|---|---|---|---|---|
| 2026-09 | 5 | 80% | 1 | 0 | 4 | 0 | 2 |

## Developers

| Developer | Runs | Pass rate | Flagged | Blocked | Skips req/granted | Waived findings | Findings/run | Client attested | Top categories | Last seen |
|---|---|---|---|---|---|---|---|---|---|---|
| @arijitaich-og1o | 4 | 100% | 0 | 0 | 0/0 | 0 | 0.5 | 0% | missing-negative-tests | 2026-09-09 |
| arijit.aich@og1o.in (@arijitaich-og1o) | 1 | 0% | 1 | 1 | 0/0 | 0 | 4.0 | 0% | hardcoded-credential, hardcoded-configuration | 2026-09-08 |

## Repositories

| Repository | Runs | Pass rate | Blocked | Skips granted | Developers | Findings/run | Top categories |
|---|---|---|---|---|---|---|---|
| arijitaich-og1o/hook-demo | 4 | 75% | 1 | 0 | 2 | 1.5 | missing-negative-tests, hardcoded-credential, hardcoded-configuration |
| unknown/unknown | 1 | 100% | 0 | 0 | 1 | 0.0 | - |

### Reading this dashboard

- **Flagged** counts runs where at least one finding met the blocking threshold, before any skip was applied.
- **Blocked** counts runs that failed the gate. Flagged but not blocked means the developer used a valid skip.
- **Skips requested / granted**: requests that failed validation (short reason, missing approval) are counted as requested only.
- **Client attested**: share of runs whose commits carried the local gate's attestation; low values indicate the local client is not installed or was bypassed.
- Developers are identified by their verified corporate e-mail when available, otherwise by GitHub login. These numbers are a quality signal, not a performance score on their own.
