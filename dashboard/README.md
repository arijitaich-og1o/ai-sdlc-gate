# AI SDLC Gate — Organisation Dashboard

_Generated 2026-10-07T17:35:36+00:00 from 160 gate run(s)._

## Organisation snapshot

| Metric | Value |
|---|---|
| Gate runs | 160 |
| Pass rate | 65% |
| Runs flagged (findings at/above threshold) | 56 (35%) |
| Runs blocked | 56 (35%) |
| Skips requested / granted | 4 / 4 |
| Findings waived via skips | 42 |
| Findings per run | 13.12 |
| Runs with local client attestation | 99% |
| Active developers / repositories | 3 / 16 |
| Top finding categories | general, hardcoded-configuration, missing-tests, undocumented-decision, observability-gap |

## Monthly trend

| Month | Runs | Pass rate | Blocked | Skips granted | Blockers | High | Medium |
|---|---|---|---|---|---|---|---|
| 2026-09 | 40 | 72% | 11 | 0 | 13 | 50 | 148 |
| 2026-10 | 120 | 62% | 45 | 4 | 26 | 353 | 796 |

## Developers

| Developer | Runs | Pass rate | Flagged | Blocked | Skips req/granted | Waived findings | Findings/run | Client attested | Top categories | Last seen |
|---|---|---|---|---|---|---|---|---|---|---|
| arijit.aich@og1o.in (@arijitaich-og1o) | 130 | 68% | 41 | 41 | 4/4 | 42 | 13.66 | 99% | general, hardcoded-configuration, missing-tests | 2026-10-07 |
| anitha.bantu@og1o.in (@Anitha9765) | 23 | 56% | 10 | 10 | 0/0 | 0 | 3.83 | 100% | logic-error, undocumented-decision, breaking-api-change | 2026-10-07 |
| pavan.neela@og1o.in (@PavanNeela0011) | 7 | 29% | 5 | 5 | 0/0 | 0 | 33.57 | 100% | hardcoded-configuration, hardcoded-credential, unpinned-action-or-image | 2026-09-30 |

## Repositories

| Repository | Runs | Pass rate | Blocked | Skips granted | Developers | Findings/run | Top categories |
|---|---|---|---|---|---|---|---|
| unknown/unknown | 69 | 86% | 10 | 0 | 1 | 5.03 | debug-statement, missing-tests, logic-error |
| arijitaich-og1o/ai-sdlc-gate | 31 | 71% | 9 | 0 | 1 | 9.84 | missing-negative-tests, undocumented-decision, missing-tests |
| otto-ec/kraken_samplenator | 15 | 53% | 7 | 0 | 1 | 3.93 | breaking-api-change, logic-error, inconsistent-api-contract |
| arijitaich-og1o/creditlens | 9 | 0% | 9 | 4 | 1 | 62.22 | general, hardcoded-configuration, breaking-api-change |
| OG-DW/sofa_docs | 8 | 62% | 3 | 0 | 1 | 12.25 | general, undocumented-decision, observability-gap |
| OG-DW/sofa_poc_fabro | 6 | 17% | 5 | 0 | 1 | 26.83 | general, hardcoded-configuration, observability-gap |
| otto-ec/kraken_suppressions | 5 | 60% | 2 | 0 | 1 | 4.4 | general, hardcoded-configuration, undocumented-decision |
| otto-ec/flagship_benefits_service | 3 | 0% | 3 | 0 | 1 | 29.33 | missing-tests, hardcoded-credential, hardcoded-configuration |
| otto-ec/flagship_connection_service | 3 | 33% | 2 | 0 | 1 | 45.67 | unpinned-action-or-image, missing-changelog, hardcoded-credential |
| OG-DW/sofa_openhands | 2 | 0% | 2 | 0 | 1 | 51.0 | general, unpinned-dependency, hardcoded-configuration |
| arijitaich-og1o/sofa-terraform-sandbox | 2 | 0% | 2 | 0 | 1 | 90.5 | general, missing-negative-tests, scalability-risk |
| oneo-dice/oggpt-x-backend | 2 | 100% | 0 | 0 | 1 | 7.0 | missing-changelog, capacity-risk, observability-gap |
| otto-ec/kraken_partner_order_api | 2 | 100% | 0 | 0 | 1 | 0.0 | - |
| Anitha9765/psw_internal-proxy_AnithaB | 1 | 0% | 1 | 0 | 1 | 7.0 | general, logic-error, dead-code |
| oneo-dice/oggpt-x-infra | 1 | 0% | 1 | 0 | 1 | 8.0 | missing-resilience, undocumented-decision, observability-gap |
| otto-ec/flagship_customer_service | 1 | 100% | 0 | 0 | 1 | 10.0 | hardcoded-configuration, undocumented-decision, data-protection-design-gap |

### Reading this dashboard

- **Flagged** counts runs where at least one finding met the blocking threshold, before any skip was applied.
- **Blocked** counts runs that failed the gate. Flagged but not blocked means the developer used a valid skip.
- **Skips requested / granted**: requests that failed validation (short reason, missing approval) are counted as requested only.
- **Client attested**: share of runs whose commits carried the local gate's attestation; low values indicate the local client is not installed or was bypassed.
- Developers are identified by their verified corporate e-mail when available, otherwise by GitHub login. These numbers are a quality signal, not a performance score on their own.
