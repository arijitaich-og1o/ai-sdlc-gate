---
name: sast-compliance
description: "Compliance overlay — PCI-DSS, HIPAA, SOC2. Tags findings from other modules with applicable requirements. Loaded only with --compliance flag."
---

# Compliance Overlay

Loaded only when `--compliance <standard>` is passed. This module tags findings from other modules — it does not replace them.

**Tag format:** append inline after the finding class line.

---

## PCI-DSS

Activate with `--compliance pci`. Applies when app handles payment card data.

| Req | What to check |
|---|---|
| 2.2 | No hardcoded credentials, no default service accounts |
| 3.4 | PAN stored unencrypted — flag `card_number`, `pan`, `cc_number` fields without encryption |
| 3.5 | Encryption keys co-located with encrypted data |
| 6.3.1 | SQLi, XSS, command injection in payment flows |
| 6.4.1 | Public web app without WAF middleware on payment routes |
| 7.2 | Missing authz checks on payment/cardholder endpoints |
| 8.3.6 | Weak password validation — flag regex allowing <12 chars or no complexity |
| 8.6.1 | Admin routes without MFA enforcement |
| 10.2 | Payment endpoints without access logging |
| 10.3 | Log files writable by app user (log injection risk) |
| 12.3.3 | Deprecated crypto: DES, RC4, AES-ECB |

**Tag:** `[PCI-DSS: Req 6.3.1 — Injection in Payment Flow]`

---

## HIPAA

Activate with `--compliance hipaa`. Applies when app handles health data (PHI).

PHI signals: `diagnosis`, `condition`, `medication`, `icd_code`, `lab_result`, `patient`, `mrn`, `health_record`, `insurance_id`.

| Section | What to check |
|---|---|
| §164.312(a)(2)(i) | Unique user ID — flag shared accounts or no user attribution in audit logs |
| §164.312(a)(2)(iv) | PHI stored or transmitted unencrypted |
| §164.312(b) | PHI access without audit logging |
| §164.312(c)(1) | PHI endpoints without integrity verification (HMAC, signature) |
| §164.312(d) | Missing auth on PHI-accessing endpoints |
| §164.312(e)(1) | Plaintext HTTP for PHI, missing TLS |
| §164.308(a)(1) | Known-vulnerable deps in PHI processing code paths |

**Tag:** `[HIPAA: §164.312(b) — Audit Controls]`

---

## SOC 2

Activate with `--compliance soc2`. Applies to SaaS/cloud service providers.

| Criterion | What to check |
|---|---|
| CC6.1 | Missing auth, broken access control, IDOR |
| CC6.3 | Wildcard permissions, no RBAC enforcement |
| CC6.6 | Missing security headers, weak TLS config |
| CC6.7 | Missing HTTPS enforcement, missing HSTS |
| CC6.8 | npm install scripts, unsigned packages |
| CC7.2 | Missing audit logging on sensitive operations |
| CC8.1 | CI/CD pipelines without approval gates |
| A1.2 | Missing rate limiting, missing K8s resource limits |
| C1.1 | Verbose error messages, PII in logs |
| P3.1 | Missing consent, PII to third parties |

**Tag:** `[SOC2: CC6.1 — Logical Access]`

---

## Compliance Summary Block

Append after the main findings summary:

```
COMPLIANCE SUMMARY (PCI-DSS)
  Req 6.3.1 (Injection):      2 findings  ← FAIL
  Req 3.4   (PAN Storage):    0 findings  ← PASS
  Req 8.3.6 (Password Policy):1 finding   ← FAIL
  Req 10.2  (Audit Logging):  1 finding   ← FAIL
  Overall: NON-COMPLIANT (3 failing requirements)
```
