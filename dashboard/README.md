# AI SDLC Gate — Organisation Dashboard

_Generated 2026-09-09T05:12:31+00:00 from 9 gate run(s)._

## Organisation snapshot

| Metric | Value |
|---|---|
| Gate runs | 9 |
| Pass rate | 67% |
| Runs flagged (findings at/above threshold) | 3 (33%) |
| Runs blocked | 3 (33%) |
| Skips requested / granted | 0 / 0 |
| Findings waived via skips | 0 |
| Findings per run | 2.56 |
| Runs with local client attestation | 11% |
| Active developers / repositories | 2 / 3 |
| Top finding categories | hardcoded-credential, hardcoded-configuration, missing-negative-tests, data-protection-design-gap, general |

## Monthly trend

| Month | Runs | Pass rate | Blocked | Skips granted | Blockers | High | Medium |
|---|---|---|---|---|---|---|---|
| 2026-09 | 9 | 67% | 3 | 0 | 4 | 3 | 9 |

## Developers

| Developer | Runs | Pass rate | Flagged | Blocked | Skips req/granted | Waived findings | Findings/run | Client attested | Top categories | Last seen |
|---|---|---|---|---|---|---|---|---|---|---|
| arijit.aich@og1o.in (@arijitaich-og1o) | 5 | 40% | 3 | 3 | 0/0 | 0 | 4.2 | 20% | hardcoded-credential, hardcoded-configuration, data-protection-design-gap | 2026-09-09 |
| @arijitaich-og1o | 4 | 100% | 0 | 0 | 0/0 | 0 | 0.5 | 0% | missing-negative-tests | 2026-09-09 |

## Repositories

| Repository | Runs | Pass rate | Blocked | Skips granted | Developers | Findings/run | Top categories |
|---|---|---|---|---|---|---|---|
| arijitaich-og1o/hook-demo | 4 | 75% | 1 | 0 | 2 | 1.5 | missing-negative-tests, hardcoded-credential, hardcoded-configuration |
| arijitaich-og1o/review-skill | 4 | 50% | 2 | 0 | 1 | 4.25 | data-protection-design-gap, general, dead-code |
| unknown/unknown | 1 | 100% | 0 | 0 | 1 | 0.0 | - |

### Reading this dashboard

- **Flagged** counts runs where at least one finding met the blocking threshold, before any skip was applied.
- **Blocked** counts runs that failed the gate. Flagged but not blocked means the developer used a valid skip.
- **Skips requested / granted**: requests that failed validation (short reason, missing approval) are counted as requested only.
- **Client attested**: share of runs whose commits carried the local gate's attestation; low values indicate the local client is not installed or was bypassed.
- Developers are identified by their verified corporate e-mail when available, otherwise by GitHub login. These numbers are a quality signal, not a performance score on their own.
