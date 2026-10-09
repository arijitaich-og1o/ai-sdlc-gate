# AI SDLC Gate — Organisation Dashboard

_Generated 2026-10-09T01:20:38+00:00 from 163 gate run(s)._

## Organisation snapshot

| Metric | Value |
|---|---|
| Gate runs | 163 |
| Pass rate | 64% |
| Runs flagged (findings at/above threshold) | 59 (36%) |
| Runs blocked | 59 (36%) |
| Skips requested / granted | 4 / 4 |
| Findings waived via skips | 42 |
| Findings per run | 13.29 |
| Runs with local client attestation | 99% |
| Active developers / repositories | 3 / 17 |
| Top finding categories | general, hardcoded-configuration, missing-tests, undocumented-decision, observability-gap |

## Monthly trend

| Month | Runs | Pass rate | Blocked | Skips granted | Blockers | High | Medium |
|---|---|---|---|---|---|---|---|
| 2026-09 | 40 | 72% | 11 | 0 | 13 | 50 | 148 |
| 2026-10 | 123 | 61% | 48 | 4 | 26 | 366 | 837 |

## Developers

| Developer | Runs | Pass rate | Flagged | Blocked | Skips req/granted | Waived findings | Findings/run | Client attested | Top categories | Last seen |
|---|---|---|---|---|---|---|---|---|---|---|
| arijit.aich@og1o.in (@arijitaich-og1o) | 133 | 67% | 44 | 44 | 4/4 | 42 | 13.86 | 99% | general, hardcoded-configuration, missing-tests | 2026-10-09 |
| anitha.bantu@og1o.in (@Anitha9765) | 23 | 56% | 10 | 10 | 0/0 | 0 | 3.83 | 100% | logic-error, undocumented-decision, breaking-api-change | 2026-10-07 |
| pavan.neela@og1o.in (@PavanNeela0011) | 7 | 29% | 5 | 5 | 0/0 | 0 | 33.57 | 100% | hardcoded-configuration, hardcoded-credential, unpinned-action-or-image | 2026-09-30 |

## Repositories

| Repository | Runs | Pass rate | Blocked | Skips granted | Developers | Findings/run | Top categories |
|---|---|---|---|---|---|---|---|
| unknown/unknown | 69 | 86% | 10 | 0 | 1 | 5.03 | debug-statement, missing-tests, logic-error |
| arijitaich-og1o/ai-sdlc-gate | 32 | 69% | 10 | 0 | 1 | 10.38 | missing-negative-tests, undocumented-decision, hardcoded-configuration |
| otto-ec/kraken_samplenator | 15 | 53% | 7 | 0 | 1 | 3.93 | breaking-api-change, logic-error, inconsistent-api-contract |
| arijitaich-og1o/creditlens | 9 | 0% | 9 | 4 | 1 | 62.22 | general, hardcoded-configuration, breaking-api-change |
| OG-DW/sofa_docs | 8 | 62% | 3 | 0 | 1 | 12.25 | general, undocumented-decision, observability-gap |
| OG-DW/sofa_poc_fabro | 6 | 17% | 5 | 0 | 1 | 26.83 | general, hardcoded-configuration, observability-gap |
| otto-ec/kraken_suppressions | 5 | 60% | 2 | 0 | 1 | 4.4 | general, hardcoded-configuration, undocumented-decision |
| OG-DW/sofa_openhands | 3 | 0% | 3 | 0 | 1 | 46.33 | general, hardcoded-configuration, insecure-design |
| otto-ec/flagship_benefits_service | 3 | 0% | 3 | 0 | 1 | 29.33 | missing-tests, hardcoded-credential, hardcoded-configuration |
| otto-ec/flagship_connection_service | 3 | 33% | 2 | 0 | 1 | 45.67 | unpinned-action-or-image, missing-changelog, hardcoded-credential |
| arijitaich-og1o/sofa-terraform-sandbox | 2 | 0% | 2 | 0 | 1 | 90.5 | general, missing-negative-tests, scalability-risk |
| oneo-dice/oggpt-x-backend | 2 | 100% | 0 | 0 | 1 | 7.0 | missing-changelog, capacity-risk, observability-gap |
| otto-ec/kraken_partner_order_api | 2 | 100% | 0 | 0 | 1 | 0.0 | - |
| Anitha9765/psw_internal-proxy_AnithaB | 1 | 0% | 1 | 0 | 1 | 7.0 | general, logic-error, dead-code |
| local/demo | 1 | 0% | 1 | 0 | 1 | 3.0 | undocumented-decision, requirement-mismatch, missing-tests |
| oneo-dice/oggpt-x-infra | 1 | 0% | 1 | 0 | 1 | 8.0 | missing-resilience, undocumented-decision, observability-gap |
| otto-ec/flagship_customer_service | 1 | 100% | 0 | 0 | 1 | 10.0 | hardcoded-configuration, undocumented-decision, data-protection-design-gap |

### Reading this dashboard

- **Flagged** counts runs where at least one finding met the blocking threshold, before any skip was applied.
- **Blocked** counts runs that failed the gate. Flagged but not blocked means the developer used a valid skip.
- **Skips requested / granted**: requests that failed validation (short reason, missing approval) are counted as requested only.
- **Client attested**: share of runs whose commits carried the local gate's attestation; low values indicate the local client is not installed or was bypassed.
- Developers are identified by their verified corporate e-mail when available, otherwise by GitHub login. These numbers are a quality signal, not a performance score on their own.
