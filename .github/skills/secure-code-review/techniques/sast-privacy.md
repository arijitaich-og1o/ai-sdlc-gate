---
name: sast-privacy
description: "GDPR/data privacy checks — PII in logs, PII to third-party analytics, missing retention/deletion logic, insufficient anonymization, PII in error responses, PII in URLs. Load on --thorough or when privacy-sensitive field names detected."
---

# Data Privacy / GDPR

Loaded on `--thorough` or when PII-related field names detected in models/schemas: `email`, `phone`, `ssn`, `dob`, `address`, `health`, `medical`, `diagnosis`, `salary`, `passport`.

## P1 — PII in Application Logs

```javascript
// ❌ NEVER:
logger.info(`User login: email=${user.email} ip=${req.ip}`)
console.log(req.body)                       // body may contain email, password, CC
logger.debug(`Payment: card=${cardNumber} cvv=${cvv}`)

// ✅ ALWAYS: mask or omit PII
logger.info(`User login: userId=${user.id}`)
logger.debug(`Payment: cardLast4=${card.slice(-4)}`)
```

**Flag:** log calls where arguments include: `email`, `password`, `ssn`, `dob`, `phone`, `address`, `card`, `cvv`, `pan`, `health`, `diagnosis`, `salary`.

## P2 — PII Sent to Third-Party Analytics

```javascript
// ❌ NEVER: PII in analytics events
analytics.track('Signed Up', {
  email: user.email,        // PII to third party without consent
  phone: user.phone,
  dateOfBirth: user.dob
})

// Google Analytics / gtag
gtag('event', 'purchase', { user_email: email })  // violates GA TOS + GDPR

// ✅ ALWAYS: pseudonymous identifiers only
analytics.track('Signed Up', {
  userId: hmacHash(user.id),   // non-reversible pseudonym
  plan: user.plan,
  country: user.country
})
```

**Flag:** calls to `analytics.track`, `gtag`, `mixpanel.track`, `amplitude.track`, `segment.track`, `heap.track` where properties include PII field names.

## P3 — Missing Data Retention / Deletion Logic

```python
# ❌ Flag absence of:
# - No scheduled job deleting records older than retention period
# - User "delete account" that only sets deleted_at=now (soft delete without PII purge)
# - No cascade delete removing associated PII tables

# ✅ Look for:
# - Cron/scheduler purging old records
# - Hard delete or anonymization: user.email = 'deleted@anon'
# - CASCADE DELETE on FKs referencing the users table
```

**Flag:** delete/deactivate routes that only set `deleted_at`, `is_deleted`, `active=False` without removing PII fields or triggering cascade deletion.

## P4 — PII in Error Responses

```python
# ❌ NEVER: user data in error messages returned to client
return jsonify({"error": f"User {user.email} not found"}), 404
return jsonify({"error": str(exception)}), 500  # may include SQL column values with PII
```

## P5 — PII in URLs / Query Parameters

```
❌ NEVER:
GET /users?email=john@example.com       ← PII in server logs, browser history, Referer headers
GET /reset?token=abc&email=user@x.com
GET /report?ssn=123-45-6789

✅ ALWAYS: PII in POST body, never in URL
```

**Flag:** PII field names (`email`, `ssn`, `dob`, `phone`) in route path definitions or `req.query.*` / `request.args.get(...)` extraction.

## P6 — Insufficient Anonymization

```python
# ❌ NEVER: MD5 of email is reversible — email space is small, rainbow tables exist
df['email_anon'] = df['email'].apply(lambda x: hashlib.md5(x.encode()).hexdigest())

# ✅ ALWAYS: HMAC with a secret key
import hmac, hashlib, os
SECRET = os.environ['ANON_KEY']
pseudonym = hmac.new(SECRET.encode(), email.encode(), hashlib.sha256).hexdigest()
```

## P7 — Consent / Legal Basis (INFO — manual verification required)

Flag for manual review (INFO severity):
- User registration without explicit consent checkbox for marketing
- Analytics tracking without cookie consent gate
- Children's data handling (detect `age`, `dob`, `child` fields) without additional safeguards
- Data sharing with third parties not documented in code comments or config
