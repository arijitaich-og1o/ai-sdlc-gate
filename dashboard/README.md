# AI SDLC Gate — Organisation Dashboard

_Generated 2026-09-09T05:09:35+00:00 from 7 gate run(s)._

## Organisation snapshot

| Metric | Value |
|---|---|
| Gate runs | 7 |
| Pass rate | 86% |
| Runs flagged (findings at/above threshold) | 1 (14%) |
| Runs blocked | 1 (14%) |
| Skips requested / granted | 0 / 0 |
| Findings waived via skips | 0 |
| Findings per run | 0.86 |
| Runs with local client attestation | 14% |
| Active developers / repositories | 2 / 3 |
| Top finding categories | missing-negative-tests, hardcoded-credential, hardcoded-configuration |

## Monthly trend

| Month | Runs | Pass rate | Blocked | Skips granted | Blockers | High | Medium |
|---|---|---|---|---|---|---|---|
| 2026-09 | 7 | 86% | 1 | 0 | 4 | 0 | 2 |

## Developers

| Developer | Runs | Pass rate | Flagged | Blocked | Skips req/granted | Waived findings | Findings/run | Client attested | Top categories | Last seen |
|---|---|---|---|---|---|---|---|---|---|---|
| @arijitaich-og1o | 4 | 100% | 0 | 0 | 0/0 | 0 | 0.5 | 0% | missing-negative-tests | 2026-09-09 |
| arijit.aich@og1o.in (@arijitaich-og1o) | 3 | 67% | 1 | 1 | 0/0 | 0 | 1.33 | 33% | hardcoded-credential, hardcoded-configuration | 2026-09-09 |

## Repositories

| Repository | Runs | Pass rate | Blocked | Skips granted | Developers | Findings/run | Top categories |
|---|---|---|---|---|---|---|---|
| arijitaich-og1o/hook-demo | 4 | 75% | 1 | 0 | 2 | 1.5 | missing-negative-tests, hardcoded-credential, hardcoded-configuration |
| arijitaich-og1o/review-skill | 2 | 100% | 0 | 0 | 1 | 0.0 | - |
| unknown/unknown | 1 | 100% | 0 | 0 | 1 | 0.0 | - |

### Reading this dashboard

- **Flagged** counts runs where at least one finding met the blocking threshold, before any skip was applied.
- **Blocked** counts runs that failed the gate. Flagged but not blocked means the developer used a valid skip.
- **Skips requested / granted**: requests that failed validation (short reason, missing approval) are counted as requested only.
- **Client attested**: share of runs whose commits carried the local gate's attestation; low values indicate the local client is not installed or was bypassed.
- Developers are identified by their verified corporate e-mail when available, otherwise by GitHub login. These numbers are a quality signal, not a performance score on their own.
