# AI SDLC Gate — Organisation Dashboard

_Generated 2026-10-01T02:16:12+00:00 from 42 gate run(s)._

## Organisation snapshot

| Metric | Value |
|---|---|
| Gate runs | 42 |
| Pass rate | 74% |
| Runs flagged (findings at/above threshold) | 11 (26%) |
| Runs blocked | 11 (26%) |
| Skips requested / granted | 0 / 0 |
| Findings waived via skips | 0 |
| Findings per run | 7.45 |
| Runs with local client attestation | 98% |
| Active developers / repositories | 3 / 10 |
| Top finding categories | hardcoded-credential, observability-gap, missing-tests, general, hardcoded-configuration |

## Monthly trend

| Month | Runs | Pass rate | Blocked | Skips granted | Blockers | High | Medium |
|---|---|---|---|---|---|---|---|
| 2026-09 | 40 | 72% | 11 | 0 | 13 | 50 | 148 |
| 2026-10 | 2 | 100% | 0 | 0 | 0 | 0 | 0 |

## Developers

| Developer | Runs | Pass rate | Flagged | Blocked | Skips req/granted | Waived findings | Findings/run | Client attested | Top categories | Last seen |
|---|---|---|---|---|---|---|---|---|---|---|
| arijit.aich@og1o.in (@arijitaich-og1o) | 33 | 88% | 4 | 4 | 0/0 | 0 | 1.94 | 97% | observability-gap, general, undocumented-decision | 2026-10-01 |
| pavan.neela@og1o.in (@PavanNeela0011) | 7 | 29% | 5 | 5 | 0/0 | 0 | 33.57 | 100% | hardcoded-configuration, hardcoded-credential, unpinned-action-or-image | 2026-09-30 |
| anitha.bantu@og1o.in (@Anitha9765) | 2 | 0% | 2 | 2 | 0/0 | 0 | 7.0 | 100% | logic-error, dead-code, missing-tests | 2026-09-30 |

## Repositories

| Repository | Runs | Pass rate | Blocked | Skips granted | Developers | Findings/run | Top categories |
|---|---|---|---|---|---|---|---|
| arijitaich-og1o/ai-sdlc-gate | 23 | 91% | 2 | 0 | 1 | 0.52 | hardcoded-credential, missing-tests, missing-negative-tests |
| unknown/unknown | 4 | 100% | 0 | 0 | 1 | 0.0 | - |
| OG-DW/sofa_docs | 3 | 67% | 1 | 0 | 1 | 10.0 | general, undocumented-decision, observability-gap |
| otto-ec/flagship_benefits_service | 3 | 0% | 3 | 0 | 1 | 29.33 | missing-tests, hardcoded-credential, hardcoded-configuration |
| otto-ec/flagship_connection_service | 3 | 33% | 2 | 0 | 1 | 45.67 | unpinned-action-or-image, missing-changelog, hardcoded-credential |
| oneo-dice/oggpt-x-backend | 2 | 100% | 0 | 0 | 1 | 7.0 | missing-changelog, capacity-risk, observability-gap |
| Anitha9765/psw_internal-proxy_AnithaB | 1 | 0% | 1 | 0 | 1 | 7.0 | general, logic-error, dead-code |
| oneo-dice/oggpt-x-infra | 1 | 0% | 1 | 0 | 1 | 8.0 | missing-resilience, undocumented-decision, observability-gap |
| otto-ec/flagship_customer_service | 1 | 100% | 0 | 0 | 1 | 10.0 | hardcoded-configuration, undocumented-decision, data-protection-design-gap |
| otto-ec/kraken_samplenator | 1 | 0% | 1 | 0 | 1 | 7.0 | gate-manipulation, breaking-api-change, logic-error |

### Reading this dashboard

- **Flagged** counts runs where at least one finding met the blocking threshold, before any skip was applied.
- **Blocked** counts runs that failed the gate. Flagged but not blocked means the developer used a valid skip.
- **Skips requested / granted**: requests that failed validation (short reason, missing approval) are counted as requested only.
- **Client attested**: share of runs whose commits carried the local gate's attestation; low values indicate the local client is not installed or was bypassed.
- Developers are identified by their verified corporate e-mail when available, otherwise by GitHub login. These numbers are a quality signal, not a performance score on their own.
