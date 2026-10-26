# AI SDLC Gate — Organisation Dashboard

_Generated 2026-10-26T15:31:22+00:00 from 185 gate run(s)._

## Organisation snapshot

| Metric | Value |
|---|---|
| Gate runs | 185 |
| Pass rate | 62% |
| Runs flagged (findings at/above threshold) | 71 (38%) |
| Runs blocked | 71 (38%) |
| Skips requested / granted | 5 / 4 |
| Findings waived via skips | 42 |
| Findings per run | 12.97 |
| Runs with local client attestation | 100% |
| Active developers / repositories | 3 / 21 |
| Top finding categories | general, hardcoded-configuration, undocumented-decision, missing-tests, observability-gap |

## Monthly trend

| Month | Runs | Pass rate | Blocked | Skips granted | Blockers | High | Medium |
|---|---|---|---|---|---|---|---|
| 2026-09 | 40 | 72% | 11 | 0 | 13 | 50 | 148 |
| 2026-10 | 145 | 59% | 60 | 4 | 31 | 413 | 964 |

## Developers

| Developer | Runs | Pass rate | Flagged | Blocked | Skips req/granted | Waived findings | Findings/run | Client attested | Top categories | Last seen |
|---|---|---|---|---|---|---|---|---|---|---|
| arijit.aich@og1o.in (@arijitaich-og1o) | 135 | 66% | 46 | 46 | 4/4 | 42 | 14.24 | 99% | general, hardcoded-configuration, missing-tests | 2026-10-09 |
| anitha.bantu@og1o.in (@Anitha9765) | 30 | 60% | 12 | 12 | 0/0 | 0 | 3.77 | 100% | logic-error, general, undocumented-decision | 2026-10-14 |
| pavan.neela@og1o.in (@PavanNeela0011) | 20 | 35% | 13 | 13 | 1/0 | 0 | 18.2 | 100% | hardcoded-configuration, general, observability-gap | 2026-10-26 |

## Repositories

| Repository | Runs | Pass rate | Blocked | Skips granted | Developers | Findings/run | Top categories |
|---|---|---|---|---|---|---|---|
| unknown/unknown | 69 | 86% | 10 | 0 | 1 | 5.03 | debug-statement, missing-tests, logic-error |
| arijitaich-og1o/ai-sdlc-gate | 32 | 69% | 10 | 0 | 1 | 10.38 | missing-negative-tests, undocumented-decision, hardcoded-configuration |
| otto-ec/kraken_samplenator | 15 | 53% | 7 | 0 | 1 | 3.93 | breaking-api-change, logic-error, inconsistent-api-contract |
| OG-DW/sofa_docs | 9 | 56% | 4 | 0 | 1 | 15.33 | undocumented-decision, observability-gap, requirement-mismatch |
| arijitaich-og1o/creditlens | 9 | 0% | 9 | 4 | 1 | 62.22 | general, hardcoded-configuration, breaking-api-change |
| otto-ec/flagship_customer_service | 7 | 57% | 3 | 0 | 1 | 7.71 | hardcoded-configuration, general, hardcoded-credential |
| OG-DW/sofa_poc_fabro | 6 | 17% | 5 | 0 | 1 | 26.83 | general, hardcoded-configuration, observability-gap |
| otto-ec/kraken_partner_order_api | 5 | 60% | 2 | 0 | 1 | 5.0 | missing-changelog, general, unpinned-action-or-image |
| otto-ec/kraken_suppressions | 5 | 60% | 2 | 0 | 1 | 4.4 | general, hardcoded-configuration, undocumented-decision |
| OG-DW/sofa_openhands | 4 | 0% | 4 | 0 | 1 | 44.5 | hardcoded-configuration, general, insecure-design |
| otto-ec/flagship_api_composer | 4 | 0% | 4 | 0 | 1 | 12.75 | missing-resilience, observability-gap, missing-input-validation-design |
| otto-ec/flagship_benefits_service | 4 | 25% | 3 | 0 | 1 | 22.25 | missing-tests, hardcoded-credential, hardcoded-configuration |
| otto-ec/flagship_connection_service | 4 | 50% | 2 | 0 | 1 | 34.75 | unpinned-action-or-image, missing-changelog, hardcoded-credential |
| arijitaich-og1o/sofa-terraform-sandbox | 2 | 0% | 2 | 0 | 1 | 90.5 | general, missing-negative-tests, scalability-risk |
| oneo-dice/oggpt-x-backend | 2 | 100% | 0 | 0 | 1 | 7.0 | missing-changelog, capacity-risk, observability-gap |
| otto-ec/kraken_github | 2 | 100% | 0 | 0 | 1 | 0.0 | - |
| otto-ec/kraken_voucher_management_ui | 2 | 100% | 0 | 0 | 1 | 0.0 | - |
| Anitha9765/psw_internal-proxy_AnithaB | 1 | 0% | 1 | 0 | 1 | 7.0 | general, logic-error, dead-code |
| local/demo | 1 | 0% | 1 | 0 | 1 | 3.0 | undocumented-decision, requirement-mismatch, missing-tests |
| oneo-dice/oggpt-x-infra | 1 | 0% | 1 | 0 | 1 | 8.0 | missing-resilience, undocumented-decision, observability-gap |
| otto-ec/flagship_ottoup_ui | 1 | 0% | 1 | 0 | 1 | 31.0 | logic-error, missing-negative-tests, hardcoded-configuration |

### Reading this dashboard

- **Flagged** counts runs where at least one finding met the blocking threshold, before any skip was applied.
- **Blocked** counts runs that failed the gate. Flagged but not blocked means the developer used a valid skip.
- **Skips requested / granted**: requests that failed validation (short reason, missing approval) are counted as requested only.
- **Client attested**: share of runs whose commits carried the local gate's attestation; low values indicate the local client is not installed or was bypassed.
- Developers are identified by their verified corporate e-mail when available, otherwise by GitHub login. These numbers are a quality signal, not a performance score on their own.
