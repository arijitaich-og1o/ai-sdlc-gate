# AI SDLC Gate — Organisation Dashboard

_Generated 2026-09-22T03:44:44+00:00 from 36 gate run(s)._

## Organisation snapshot

| Metric | Value |
|---|---|
| Gate runs | 36 |
| Pass rate | 33% |
| Runs flagged (findings at/above threshold) | 17 (47%) |
| Runs blocked | 24 (67%) |
| Skips requested / granted | 3 / 3 |
| Findings waived via skips | 0 |
| Findings per run | 3.69 |
| Runs with local client attestation | 14% |
| Active developers / repositories | 5 / 8 |
| Top finding categories | hardcoded-credential, secret-exposure, data-protection-design-gap, missing-negative-tests, insecure-design |

## Monthly trend

| Month | Runs | Pass rate | Blocked | Skips granted | Blockers | High | Medium |
|---|---|---|---|---|---|---|---|
| 2026-09 | 36 | 33% | 24 | 3 | 43 | 18 | 47 |

## Developers

| Developer | Runs | Pass rate | Flagged | Blocked | Skips req/granted | Waived findings | Findings/run | Client attested | Top categories | Last seen |
|---|---|---|---|---|---|---|---|---|---|---|
| arijit.aich@og1o.in (@arijitaich-og1o) | 21 | 29% | 11 | 15 | 3/3 | 0 | 3.19 | 24% | hardcoded-credential, secret-exposure, data-protection-design-gap | 2026-09-19 |
| @arijitaich-og1o | 10 | 40% | 6 | 6 | 0/0 | 0 | 6.3 | 0% | missing-negative-tests, hardcoded-credential, insecure-design | 2026-09-16 |
| marlene.graefe@og1o.de (@arijitaich-og1o) | 3 | 33% | 0 | 2 | 0/0 | 0 | 0.0 | 0% | - | 2026-09-20 |
| aich@ornakala.com (@arijitaich-og1o) | 1 | 0% | 0 | 1 | 0/0 | 0 | 0.0 | 0% | - | 2026-09-22 |
| felix.theodor@ottogroup.com (@arijitaich-og1o) | 1 | 100% | 0 | 0 | 0/0 | 0 | 3.0 | 0% | authz-design-gap, undocumented-decision, schema-incompatibility | 2026-09-10 |

## Repositories

| Repository | Runs | Pass rate | Blocked | Skips granted | Developers | Findings/run | Top categories |
|---|---|---|---|---|---|---|---|
| OG-DW/sofa_poc_fabro | 9 | 0% | 9 | 3 | 1 | 1.33 | secret-exposure, hardcoded-credential, insecure-design |
| arijitaich-og1o/hook-demo | 8 | 38% | 5 | 0 | 2 | 3.62 | missing-negative-tests, hardcoded-credential, hardcoded-configuration |
| arijitaich-og1o/review-skill | 7 | 29% | 5 | 0 | 1 | 5.57 | data-protection-design-gap, general, hardcoded-credential |
| OG-DW/rmscontextual_api | 5 | 100% | 0 | 0 | 2 | 3.0 | authz-design-gap, undocumented-decision, observability-gap |
| oneo-dice/oggpt-x-backend | 3 | 33% | 2 | 0 | 1 | 0.0 | - |
| arijitaich-og1o/ledger-demo | 2 | 0% | 2 | 0 | 1 | 19.0 | hardcoded-configuration, missing-negative-tests, observability-gap |
| arijitaich-og1o/ai-sdlc-gate | 1 | 0% | 1 | 0 | 1 | 0.0 | - |
| unknown/unknown | 1 | 100% | 0 | 0 | 1 | 0.0 | - |

### Reading this dashboard

- **Flagged** counts runs where at least one finding met the blocking threshold, before any skip was applied.
- **Blocked** counts runs that failed the gate. Flagged but not blocked means the developer used a valid skip.
- **Skips requested / granted**: requests that failed validation (short reason, missing approval) are counted as requested only.
- **Client attested**: share of runs whose commits carried the local gate's attestation; low values indicate the local client is not installed or was bypassed.
- Developers are identified by their verified corporate e-mail when available, otherwise by GitHub login. These numbers are a quality signal, not a performance score on their own.
