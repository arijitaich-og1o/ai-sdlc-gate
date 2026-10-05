# AI SDLC Gate — Organisation Dashboard

_Generated 2026-10-05T11:41:53+00:00 from 131 gate run(s)._

## Organisation snapshot

| Metric | Value |
|---|---|
| Gate runs | 131 |
| Pass rate | 73% |
| Runs flagged (findings at/above threshold) | 35 (27%) |
| Runs blocked | 35 (27%) |
| Skips requested / granted | 0 / 0 |
| Findings waived via skips | 0 |
| Findings per run | 6.84 |
| Runs with local client attestation | 99% |
| Active developers / repositories | 3 / 12 |
| Top finding categories | hardcoded-configuration, undocumented-decision, general, missing-tests, observability-gap |

## Monthly trend

| Month | Runs | Pass rate | Blocked | Skips granted | Blockers | High | Medium |
|---|---|---|---|---|---|---|---|
| 2026-09 | 40 | 72% | 11 | 0 | 13 | 50 | 148 |
| 2026-10 | 91 | 74% | 24 | 0 | 9 | 131 | 253 |

## Developers

| Developer | Runs | Pass rate | Flagged | Blocked | Skips req/granted | Waived findings | Findings/run | Client attested | Top categories | Last seen |
|---|---|---|---|---|---|---|---|---|---|---|
| arijit.aich@og1o.in (@arijitaich-og1o) | 111 | 80% | 22 | 22 | 0/0 | 0 | 5.36 | 99% | general, observability-gap, undocumented-decision | 2026-10-05 |
| anitha.bantu@og1o.in (@Anitha9765) | 13 | 38% | 8 | 8 | 0/0 | 0 | 5.08 | 100% | logic-error, breaking-api-change, missing-contract-tests | 2026-10-05 |
| pavan.neela@og1o.in (@PavanNeela0011) | 7 | 29% | 5 | 5 | 0/0 | 0 | 33.57 | 100% | hardcoded-configuration, hardcoded-credential, unpinned-action-or-image | 2026-09-30 |

## Repositories

| Repository | Runs | Pass rate | Blocked | Skips granted | Developers | Findings/run | Top categories |
|---|---|---|---|---|---|---|---|
| unknown/unknown | 68 | 87% | 9 | 0 | 1 | 1.31 | debug-statement, missing-tests, missing-documentation |
| arijitaich-og1o/ai-sdlc-gate | 24 | 92% | 2 | 0 | 1 | 1.83 | missing-tests, missing-negative-tests, observability-gap |
| otto-ec/kraken_samplenator | 12 | 42% | 7 | 0 | 1 | 4.92 | breaking-api-change, logic-error, inconsistent-api-contract |
| OG-DW/sofa_docs | 8 | 62% | 3 | 0 | 1 | 12.25 | general, undocumented-decision, observability-gap |
| OG-DW/sofa_poc_fabro | 6 | 17% | 5 | 0 | 1 | 26.83 | general, hardcoded-configuration, observability-gap |
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
