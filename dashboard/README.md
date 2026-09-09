# AI SDLC Gate — Organisation Dashboard

_Generated 2026-09-09T05:23:22+00:00 from 14 gate run(s)._

## Organisation snapshot

| Metric | Value |
|---|---|
| Gate runs | 14 |
| Pass rate | 43% |
| Runs flagged (findings at/above threshold) | 8 (57%) |
| Runs blocked | 8 (57%) |
| Skips requested / granted | 0 / 0 |
| Findings waived via skips | 0 |
| Findings per run | 4.57 |
| Runs with local client attestation | 7% |
| Active developers / repositories | 2 / 3 |
| Top finding categories | hardcoded-credential, data-protection-design-gap, general, credentials-in-tests, insecure-design |

## Monthly trend

| Month | Runs | Pass rate | Blocked | Skips granted | Blockers | High | Medium |
|---|---|---|---|---|---|---|---|
| 2026-09 | 14 | 43% | 8 | 0 | 24 | 9 | 19 |

## Developers

| Developer | Runs | Pass rate | Flagged | Blocked | Skips req/granted | Waived findings | Findings/run | Client attested | Top categories | Last seen |
|---|---|---|---|---|---|---|---|---|---|---|
| arijit.aich@og1o.in (@arijitaich-og1o) | 8 | 25% | 6 | 6 | 0/0 | 0 | 5.38 | 12% | hardcoded-credential, data-protection-design-gap, general | 2026-09-09 |
| @arijitaich-og1o | 6 | 67% | 2 | 2 | 0/0 | 0 | 3.5 | 0% | missing-negative-tests, hardcoded-credential, secret-exposure | 2026-09-09 |

## Repositories

| Repository | Runs | Pass rate | Blocked | Skips granted | Developers | Findings/run | Top categories |
|---|---|---|---|---|---|---|---|
| arijitaich-og1o/review-skill | 7 | 29% | 5 | 0 | 1 | 5.57 | data-protection-design-gap, general, hardcoded-credential |
| arijitaich-og1o/hook-demo | 6 | 50% | 3 | 0 | 2 | 4.17 | hardcoded-credential, hardcoded-configuration, missing-negative-tests |
| unknown/unknown | 1 | 100% | 0 | 0 | 1 | 0.0 | - |

### Reading this dashboard

- **Flagged** counts runs where at least one finding met the blocking threshold, before any skip was applied.
- **Blocked** counts runs that failed the gate. Flagged but not blocked means the developer used a valid skip.
- **Skips requested / granted**: requests that failed validation (short reason, missing approval) are counted as requested only.
- **Client attested**: share of runs whose commits carried the local gate's attestation; low values indicate the local client is not installed or was bypassed.
- Developers are identified by their verified corporate e-mail when available, otherwise by GitHub login. These numbers are a quality signal, not a performance score on their own.
