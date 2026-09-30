# AI SDLC Gate — Organisation Dashboard

_Generated 2026-09-30T06:34:24+00:00 from 30 gate run(s)._

## Organisation snapshot

| Metric | Value |
|---|---|
| Gate runs | 30 |
| Pass rate | 80% |
| Runs flagged (findings at/above threshold) | 6 (20%) |
| Runs blocked | 6 (20%) |
| Skips requested / granted | 0 / 0 |
| Findings waived via skips | 0 |
| Findings per run | 4.4 |
| Runs with local client attestation | 97% |
| Active developers / repositories | 2 / 5 |
| Top finding categories | observability-gap, hardcoded-credential, hardcoded-configuration, undocumented-decision, general |

## Monthly trend

| Month | Runs | Pass rate | Blocked | Skips granted | Blockers | High | Medium |
|---|---|---|---|---|---|---|---|
| 2026-09 | 30 | 80% | 6 | 0 | 1 | 11 | 61 |

## Developers

| Developer | Runs | Pass rate | Flagged | Blocked | Skips req/granted | Waived findings | Findings/run | Client attested | Top categories | Last seen |
|---|---|---|---|---|---|---|---|---|---|---|
| arijit.aich@og1o.in (@arijitaich-og1o) | 26 | 88% | 3 | 3 | 0/0 | 0 | 1.31 | 96% | observability-gap, missing-changelog, capacity-risk | 2026-09-29 |
| pavan.neela@og1o.in (@PavanNeela0011) | 4 | 25% | 3 | 3 | 0/0 | 0 | 24.5 | 100% | hardcoded-configuration, undocumented-decision, hardcoded-credential | 2026-09-30 |

## Repositories

| Repository | Runs | Pass rate | Blocked | Skips granted | Developers | Findings/run | Top categories |
|---|---|---|---|---|---|---|---|
| arijitaich-og1o/ai-sdlc-gate | 23 | 91% | 2 | 0 | 1 | 0.52 | hardcoded-credential, missing-tests, missing-negative-tests |
| otto-ec/flagship_benefits_service | 3 | 0% | 3 | 0 | 1 | 29.33 | missing-tests, hardcoded-credential, hardcoded-configuration |
| oneo-dice/oggpt-x-backend | 2 | 100% | 0 | 0 | 1 | 7.0 | missing-changelog, capacity-risk, observability-gap |
| oneo-dice/oggpt-x-infra | 1 | 0% | 1 | 0 | 1 | 8.0 | missing-resilience, undocumented-decision, observability-gap |
| otto-ec/flagship_customer_service | 1 | 100% | 0 | 0 | 1 | 10.0 | hardcoded-configuration, undocumented-decision, data-protection-design-gap |

### Reading this dashboard

- **Flagged** counts runs where at least one finding met the blocking threshold, before any skip was applied.
- **Blocked** counts runs that failed the gate. Flagged but not blocked means the developer used a valid skip.
- **Skips requested / granted**: requests that failed validation (short reason, missing approval) are counted as requested only.
- **Client attested**: share of runs whose commits carried the local gate's attestation; low values indicate the local client is not installed or was bypassed.
- Developers are identified by their verified corporate e-mail when available, otherwise by GitHub login. These numbers are a quality signal, not a performance score on their own.
