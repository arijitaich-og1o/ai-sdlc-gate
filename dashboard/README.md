# AI SDLC Gate — Organisation Dashboard

_Generated 2026-10-06T04:01:22+00:00 from 136 gate run(s)._

## Organisation snapshot

| Metric | Value |
|---|---|
| Gate runs | 136 |
| Pass rate | 71% |
| Runs flagged (findings at/above threshold) | 39 (29%) |
| Runs blocked | 39 (29%) |
| Skips requested / granted | 1 / 1 |
| Findings waived via skips | 19 |
| Findings per run | 8.15 |
| Runs with local client attestation | 99% |
| Active developers / repositories | 3 / 13 |
| Top finding categories | general, hardcoded-configuration, missing-tests, undocumented-decision, observability-gap |

## Monthly trend

| Month | Runs | Pass rate | Blocked | Skips granted | Blockers | High | Medium |
|---|---|---|---|---|---|---|---|
| 2026-09 | 40 | 72% | 11 | 0 | 13 | 50 | 148 |
| 2026-10 | 96 | 71% | 28 | 1 | 24 | 180 | 340 |

## Developers

| Developer | Runs | Pass rate | Flagged | Blocked | Skips req/granted | Waived findings | Findings/run | Client attested | Top categories | Last seen |
|---|---|---|---|---|---|---|---|---|---|---|
| arijit.aich@og1o.in (@arijitaich-og1o) | 115 | 77% | 26 | 26 | 1/1 | 19 | 7.03 | 99% | general, observability-gap, missing-tests | 2026-10-06 |
| anitha.bantu@og1o.in (@Anitha9765) | 14 | 43% | 8 | 8 | 0/0 | 0 | 4.71 | 100% | logic-error, breaking-api-change, missing-contract-tests | 2026-10-05 |
| pavan.neela@og1o.in (@PavanNeela0011) | 7 | 29% | 5 | 5 | 0/0 | 0 | 33.57 | 100% | hardcoded-configuration, hardcoded-credential, unpinned-action-or-image | 2026-09-30 |

## Repositories

| Repository | Runs | Pass rate | Blocked | Skips granted | Developers | Findings/run | Top categories |
|---|---|---|---|---|---|---|---|
| unknown/unknown | 68 | 87% | 9 | 0 | 1 | 1.31 | debug-statement, missing-tests, missing-documentation |
| arijitaich-og1o/ai-sdlc-gate | 24 | 92% | 2 | 0 | 1 | 1.83 | missing-tests, missing-negative-tests, observability-gap |
| otto-ec/kraken_samplenator | 13 | 46% | 7 | 0 | 1 | 4.54 | breaking-api-change, logic-error, inconsistent-api-contract |
| OG-DW/sofa_docs | 8 | 62% | 3 | 0 | 1 | 12.25 | general, undocumented-decision, observability-gap |
| OG-DW/sofa_poc_fabro | 6 | 17% | 5 | 0 | 1 | 26.83 | general, hardcoded-configuration, observability-gap |
| arijitaich-og1o/creditlens | 4 | 0% | 4 | 1 | 1 | 53.25 | general, authz-design-gap, data-protection-design-gap |
| otto-ec/flagship_benefits_service | 3 | 0% | 3 | 0 | 1 | 29.33 | missing-tests, hardcoded-credential, hardcoded-configuration |
| otto-ec/flagship_connection_service | 3 | 33% | 2 | 0 | 1 | 45.67 | unpinned-action-or-image, missing-changelog, hardcoded-credential |
| arijitaich-og1o/sofa-terraform-sandbox | 2 | 0% | 2 | 0 | 1 | 90.5 | general, missing-negative-tests, scalability-risk |
| oneo-dice/oggpt-x-backend | 2 | 100% | 0 | 0 | 1 | 7.0 | missing-changelog, capacity-risk, observability-gap |
| Anitha9765/psw_internal-proxy_AnithaB | 1 | 0% | 1 | 0 | 1 | 7.0 | general, logic-error, dead-code |
| oneo-dice/oggpt-x-infra | 1 | 0% | 1 | 0 | 1 | 8.0 | missing-resilience, undocumented-decision, observability-gap |
| otto-ec/flagship_customer_service | 1 | 100% | 0 | 0 | 1 | 10.0 | hardcoded-configuration, undocumented-decision, data-protection-design-gap |

### Reading this dashboard

- **Flagged** counts runs where at least one finding met the blocking threshold, before any skip was applied.
- **Blocked** counts runs that failed the gate. Flagged but not blocked means the developer used a valid skip.
- **Skips requested / granted**: requests that failed validation (short reason, missing approval) are counted as requested only.
- **Client attested**: share of runs whose commits carried the local gate's attestation; low values indicate the local client is not installed or was bypassed.
- Developers are identified by their verified corporate e-mail when available, otherwise by GitHub login. These numbers are a quality signal, not a performance score on their own.
