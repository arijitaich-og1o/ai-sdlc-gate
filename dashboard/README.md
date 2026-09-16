# AI SDLC Gate — Organisation Dashboard

_Generated 2026-09-16T10:14:37+00:00 from 22 gate run(s)._

## Organisation snapshot

| Metric | Value |
|---|---|
| Gate runs | 22 |
| Pass rate | 50% |
| Runs flagged (findings at/above threshold) | 11 (50%) |
| Runs blocked | 11 (50%) |
| Skips requested / granted | 0 / 0 |
| Findings waived via skips | 0 |
| Findings per run | 5.41 |
| Runs with local client attestation | 23% |
| Active developers / repositories | 3 / 5 |
| Top finding categories | hardcoded-credential, data-protection-design-gap, general, authz-design-gap, observability-gap |

## Monthly trend

| Month | Runs | Pass rate | Blocked | Skips granted | Blockers | High | Medium |
|---|---|---|---|---|---|---|---|
| 2026-09 | 22 | 50% | 11 | 0 | 32 | 17 | 45 |

## Developers

| Developer | Runs | Pass rate | Flagged | Blocked | Skips req/granted | Waived findings | Findings/run | Client attested | Top categories | Last seen |
|---|---|---|---|---|---|---|---|---|---|---|
| arijit.aich@og1o.in (@arijitaich-og1o) | 12 | 50% | 6 | 6 | 0/0 | 0 | 4.58 | 42% | hardcoded-credential, data-protection-design-gap, general | 2026-09-10 |
| @arijitaich-og1o | 9 | 44% | 5 | 5 | 0/0 | 0 | 6.78 | 0% | missing-negative-tests, hardcoded-credential, insecure-design | 2026-09-16 |
| felix.theodor@ottogroup.com (@arijitaich-og1o) | 1 | 100% | 0 | 0 | 0/0 | 0 | 3.0 | 0% | authz-design-gap, undocumented-decision, schema-incompatibility | 2026-09-10 |

## Repositories

| Repository | Runs | Pass rate | Blocked | Skips granted | Developers | Findings/run | Top categories |
|---|---|---|---|---|---|---|---|
| arijitaich-og1o/hook-demo | 7 | 43% | 4 | 0 | 2 | 3.86 | hardcoded-credential, missing-negative-tests, hardcoded-configuration |
| arijitaich-og1o/review-skill | 7 | 29% | 5 | 0 | 1 | 5.57 | data-protection-design-gap, general, hardcoded-credential |
| OG-DW/rmscontextual_api | 5 | 100% | 0 | 0 | 2 | 3.0 | authz-design-gap, undocumented-decision, observability-gap |
| arijitaich-og1o/ledger-demo | 2 | 0% | 2 | 0 | 1 | 19.0 | hardcoded-configuration, missing-negative-tests, observability-gap |
| unknown/unknown | 1 | 100% | 0 | 0 | 1 | 0.0 | - |

### Reading this dashboard

- **Flagged** counts runs where at least one finding met the blocking threshold, before any skip was applied.
- **Blocked** counts runs that failed the gate. Flagged but not blocked means the developer used a valid skip.
- **Skips requested / granted**: requests that failed validation (short reason, missing approval) are counted as requested only.
- **Client attested**: share of runs whose commits carried the local gate's attestation; low values indicate the local client is not installed or was bypassed.
- Developers are identified by their verified corporate e-mail when available, otherwise by GitHub login. These numbers are a quality signal, not a performance score on their own.
