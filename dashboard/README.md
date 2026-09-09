# AI SDLC Gate — Organisation Dashboard

_Generated 2026-09-09T05:17:31+00:00 from 11 gate run(s)._

## Organisation snapshot

| Metric | Value |
|---|---|
| Gate runs | 11 |
| Pass rate | 55% |
| Runs flagged (findings at/above threshold) | 5 (46%) |
| Runs blocked | 5 (46%) |
| Skips requested / granted | 0 / 0 |
| Findings waived via skips | 0 |
| Findings per run | 3.82 |
| Runs with local client attestation | 9% |
| Active developers / repositories | 2 / 3 |
| Top finding categories | hardcoded-credential, hardcoded-configuration, insecure-design, data-protection-design-gap, missing-negative-tests |

## Monthly trend

| Month | Runs | Pass rate | Blocked | Skips granted | Blockers | High | Medium |
|---|---|---|---|---|---|---|---|
| 2026-09 | 11 | 55% | 5 | 0 | 22 | 4 | 9 |

## Developers

| Developer | Runs | Pass rate | Flagged | Blocked | Skips req/granted | Waived findings | Findings/run | Client attested | Top categories | Last seen |
|---|---|---|---|---|---|---|---|---|---|---|
| @arijitaich-og1o | 6 | 67% | 2 | 2 | 0/0 | 0 | 3.5 | 0% | missing-negative-tests, hardcoded-credential, secret-exposure | 2026-09-09 |
| arijit.aich@og1o.in (@arijitaich-og1o) | 5 | 40% | 3 | 3 | 0/0 | 0 | 4.2 | 20% | hardcoded-credential, hardcoded-configuration, data-protection-design-gap | 2026-09-09 |

## Repositories

| Repository | Runs | Pass rate | Blocked | Skips granted | Developers | Findings/run | Top categories |
|---|---|---|---|---|---|---|---|
| arijitaich-og1o/hook-demo | 6 | 50% | 3 | 0 | 2 | 4.17 | hardcoded-credential, hardcoded-configuration, missing-negative-tests |
| arijitaich-og1o/review-skill | 4 | 50% | 2 | 0 | 1 | 4.25 | data-protection-design-gap, general, dead-code |
| unknown/unknown | 1 | 100% | 0 | 0 | 1 | 0.0 | - |

### Reading this dashboard

- **Flagged** counts runs where at least one finding met the blocking threshold, before any skip was applied.
- **Blocked** counts runs that failed the gate. Flagged but not blocked means the developer used a valid skip.
- **Skips requested / granted**: requests that failed validation (short reason, missing approval) are counted as requested only.
- **Client attested**: share of runs whose commits carried the local gate's attestation; low values indicate the local client is not installed or was bypassed.
- Developers are identified by their verified corporate e-mail when available, otherwise by GitHub login. These numbers are a quality signal, not a performance score on their own.
