# SDLC Gate — Organisation Dashboard

_Generated 2026-09-08T23:24:18+00:00 from 3 gate run(s)._

## Organisation snapshot

| Metric | Value |
|---|---|
| Gate runs | 3 |
| Pass rate | 67% |
| Runs flagged (findings at/above threshold) | 1 (33%) |
| Runs blocked | 1 (33%) |
| Skips requested / granted | 0 / 0 |
| Findings waived via skips | 0 |
| Findings per run | 1.67 |
| Runs with local client attestation | 0% |
| Active developers / repositories | 2 / 1 |
| Top finding categories | hardcoded-credential, hardcoded-configuration, missing-negative-tests |

## Monthly trend

| Month | Runs | Pass rate | Blocked | Skips granted | Blockers | High | Medium |
|---|---|---|---|---|---|---|---|
| 2026-09 | 3 | 67% | 1 | 0 | 4 | 0 | 1 |

## Developers

| Developer | Runs | Pass rate | Flagged | Blocked | Skips req/granted | Waived findings | Findings/run | Client attested | Top categories | Last seen |
|---|---|---|---|---|---|---|---|---|---|---|
| @arijitaich-og1o | 2 | 100% | 0 | 0 | 0/0 | 0 | 0.5 | 0% | missing-negative-tests | 2026-09-08 |
| arijit.aich@og1o.in (@arijitaich-og1o) | 1 | 0% | 1 | 1 | 0/0 | 0 | 4.0 | 0% | hardcoded-credential, hardcoded-configuration | 2026-09-08 |

## Repositories

| Repository | Runs | Pass rate | Blocked | Skips granted | Developers | Findings/run | Top categories |
|---|---|---|---|---|---|---|---|
| arijitaich-og1o/hook-demo | 3 | 67% | 1 | 0 | 2 | 1.67 | hardcoded-credential, hardcoded-configuration, missing-negative-tests |

### Reading this dashboard

- **Flagged** counts runs where at least one finding met the blocking threshold, before any skip was applied.
- **Blocked** counts runs that failed the gate. Flagged but not blocked means the developer used a valid skip.
- **Skips requested / granted**: requests that failed validation (short reason, missing approval) are counted as requested only.
- **Client attested**: share of runs whose commits carried the local gate's attestation; low values indicate the local client is not installed or was bypassed.
- Developers are identified by their verified corporate e-mail when available, otherwise by GitHub login. These numbers are a quality signal, not a performance score on their own.
