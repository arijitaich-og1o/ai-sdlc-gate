# AI SDLC Gate — Organisation Dashboard

_Generated 2026-09-09T05:11:27+00:00 from 8 gate run(s)._

## Organisation snapshot

| Metric | Value |
|---|---|
| Gate runs | 8 |
| Pass rate | 75% |
| Runs flagged (findings at/above threshold) | 2 (25%) |
| Runs blocked | 2 (25%) |
| Skips requested / granted | 0 / 0 |
| Findings waived via skips | 0 |
| Findings per run | 1.75 |
| Runs with local client attestation | 12% |
| Active developers / repositories | 2 / 3 |
| Top finding categories | hardcoded-credential, missing-negative-tests, hardcoded-configuration, insecure-design, data-protection-design-gap |

## Monthly trend

| Month | Runs | Pass rate | Blocked | Skips granted | Blockers | High | Medium |
|---|---|---|---|---|---|---|---|
| 2026-09 | 8 | 75% | 2 | 0 | 4 | 1 | 5 |

## Developers

| Developer | Runs | Pass rate | Flagged | Blocked | Skips req/granted | Waived findings | Findings/run | Client attested | Top categories | Last seen |
|---|---|---|---|---|---|---|---|---|---|---|
| @arijitaich-og1o | 4 | 100% | 0 | 0 | 0/0 | 0 | 0.5 | 0% | missing-negative-tests | 2026-09-09 |
| arijit.aich@og1o.in (@arijitaich-og1o) | 4 | 50% | 2 | 2 | 0/0 | 0 | 3.0 | 25% | hardcoded-credential, hardcoded-configuration, insecure-design | 2026-09-09 |

## Repositories

| Repository | Runs | Pass rate | Blocked | Skips granted | Developers | Findings/run | Top categories |
|---|---|---|---|---|---|---|---|
| arijitaich-og1o/hook-demo | 4 | 75% | 1 | 0 | 2 | 1.5 | missing-negative-tests, hardcoded-credential, hardcoded-configuration |
| arijitaich-og1o/review-skill | 3 | 67% | 1 | 0 | 1 | 2.67 | insecure-design, data-protection-design-gap, general |
| unknown/unknown | 1 | 100% | 0 | 0 | 1 | 0.0 | - |

### Reading this dashboard

- **Flagged** counts runs where at least one finding met the blocking threshold, before any skip was applied.
- **Blocked** counts runs that failed the gate. Flagged but not blocked means the developer used a valid skip.
- **Skips requested / granted**: requests that failed validation (short reason, missing approval) are counted as requested only.
- **Client attested**: share of runs whose commits carried the local gate's attestation; low values indicate the local client is not installed or was bypassed.
- Developers are identified by their verified corporate e-mail when available, otherwise by GitHub login. These numbers are a quality signal, not a performance score on their own.
