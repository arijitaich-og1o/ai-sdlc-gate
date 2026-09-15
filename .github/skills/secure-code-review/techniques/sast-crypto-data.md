---
name: sast-crypto-data
description: "SAST categories 4+5: cryptography vulnerabilities (weak algorithms, hardcoded keys/IVs, insecure random, missing cert validation) and sensitive data exposure (secrets in source, verbose errors, sensitive logging, PII in comments)."
---

# Category 4 — Cryptography

## 4.1 Weak Algorithms

| Dangerous | Why |
|---|---|
| DES, 3DES, RC4, Blowfish | Broken or deprecated |
| AES-ECB mode | Deterministic, pattern-preserving |
| RSA < 2048 bits | Factorable |
| SHA1 for signatures | Collision attacks |
| MD5 for anything security-related | Broken |

## 4.2 Hardcoded Keys and IVs

- Encryption keys as string literals in source
- Static IVs/nonces (IV reuse = catastrophic for AES-GCM/CTR)
- Key derivation from predictable seeds (timestamp, PID, hostname)

## 4.3 Insecure Random

Flag when non-CSPRNG functions generate values for: reset tokens, session IDs, OTPs, CSRF tokens, API keys, invite codes, verification codes.

| Language | Insecure | Safe |
|---|---|---|
| JS/TS | `Math.random()` | `crypto.randomBytes(32).toString('hex')` |
| Python | `random.random()` `random.randint()` | `secrets.token_hex(32)` `secrets.randbelow(n)` |
| PHP | `rand()` `mt_rand()` | `random_bytes(32)` `bin2hex(random_bytes(16))` |
| Ruby | `rand()` `Random.new` | `SecureRandom.hex(32)` |
| Java | `new Random()` | `new SecureRandom()` |
| Go | `math/rand` package | `crypto/rand` package |

Severity: HIGH — token prediction → account takeover, OTP bypass.

## 4.4 Missing Certificate Validation

- `rejectUnauthorized: false` (Node.js)
- `verify=False` (Python requests)
- `InsecureSkipVerify: true` (Go)
- Custom `TrustManager` accepting all certs (Java) — empty `checkServerTrusted()` body
- `CURLOPT_SSL_VERIFYPEER => false` (PHP)
- `NODE_TLS_REJECT_UNAUTHORIZED=0` in env/config — disables cert verification for entire process

## 4.5 Timing-Safe Comparison

Using `==` to compare secrets allows timing-based attacks: response time reveals how many bytes matched, enabling byte-by-byte recovery.

```python
# ❌ NEVER: short-circuits on first mismatch
if request.headers['X-Hub-Signature'] == compute_hmac(payload):
    process_webhook()

# ✅ ALWAYS:
import hmac
if hmac.compare_digest(request.headers['X-Hub-Signature'], compute_hmac(payload)):
    process_webhook()
```

```javascript
// ❌ NEVER:
if (req.headers['x-signature'] === expectedSig) { ... }

// ✅ ALWAYS:
const crypto = require('crypto')
if (crypto.timingSafeEqual(Buffer.from(req.headers['x-signature']), Buffer.from(expectedSig))) { ... }
```

**Flag:** `==` / `===` / `.equals()` where one operand is a HMAC, signature, API key, webhook secret, or token. Especially in webhook handlers, signature verification, API auth middleware. Severity: HIGH (HMAC bypass → webhook spoofing, auth bypass).

---

# Category 5 — Sensitive Data Exposure

## 5.1 Secrets in Source

Pattern match these formats anywhere in source (excluding test fixtures and example configs):

| Service | Pattern |
|---|---|
| AWS Access Key | `AKIA[0-9A-Z]{16}` |
| AWS Secret | 40-char base64 near `aws_secret` or `AWS_SECRET` |
| Stripe Live | `sk_live_[0-9a-zA-Z]{24,}` |
| Stripe Test | `sk_test_[0-9a-zA-Z]{24,}` |
| GitHub Token | `ghp_[0-9a-zA-Z]{36}` `github_pat_` |
| Slack Token | `xoxb-[0-9]{11}-[0-9]{11}-[0-9a-zA-Z]{24}` `xoxp-` |
| Twilio | `SK[0-9a-f]{32}` near `twilio` |
| SendGrid | `SG\.[0-9a-zA-Z._-]{66}` |
| Firebase | `AIza[0-9A-Za-z_-]{35}` |
| GCP Service Account | `"type": "service_account"` in JSON |
| Azure Connection | `DefaultEndpointsProtocol=https` with `AccountKey=` |
| NPM Token | `npm_[0-9a-zA-Z]{36}` |
| Docker Hub | `dckr_pat_[0-9a-zA-Z_-]{27}` |
| Private Key | `-----BEGIN (RSA\|EC\|OPENSSH) PRIVATE KEY-----` |
| JWT (hardcoded) | `eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+` |
| DB URL with password | `(postgres\|mysql\|mongodb)://[^:]+:[^@]+@` |
| Generic high-entropy | String >20 chars, Shannon entropy >4.5, not UUID/hash/URL format |

Also flag:
- OAuth client secrets / webhook signing secrets in source
- Encryption keys in non-config files
- Hardcoded credentials in connection string literals

## 5.2 Verbose Error Messages

- Stack traces returned to client in production (`err.stack` in error handler response)
- Database error messages exposed (table names, column names, query structure)
- `DEBUG = True` in production config
- `display_errors = On` (PHP)

## 5.3 Sensitive Data in Logs

- `console.log(req.body)` on auth/payment endpoints
- `logger.info(f"Login: {username}:{password}")`
- PII (email, SSN, CC number) logged without masking
- Session tokens or API keys written to log files

## 5.4 Sensitive Data in Comments

- TODO/FIXME referencing credentials, internal URLs, or security workarounds
- Commented-out code containing secrets or backdoors
- Production hostnames, internal IP addresses in developer notes
