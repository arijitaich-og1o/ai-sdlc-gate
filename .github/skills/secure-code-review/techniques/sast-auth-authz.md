---
name: sast-auth-authz
description: "SAST categories 2+3: authentication & session vulnerabilities (hardcoded creds, weak hashing, session fixation, JWT flaws, insecure token generation) and authorization issues (missing access control, privilege escalation, horizontal access control)."
---

# Category 2 — Authentication & Session

## 2.1 Hardcoded Credentials

Grep for:
```
password = "..." passwd = "..." secret = "..." api_key = "..."
apiKey = "..." API_KEY = "..." token = "eyJ..." AWS_SECRET_ACCESS_KEY
AKIA[0-9A-Z]{16} sk_live_* sk_test_* private_key = "..."
```
Exclude: test files, example configs, docs. Flag ONLY if in production code paths.

## 2.2 Weak Password Hashing

| Dangerous | Safe |
|---|---|
| `MD5` `SHA1` `SHA256` (unsalted) for passwords | `bcrypt` `argon2` `scrypt` `PBKDF2` |
| `hashlib.md5(password)` | `bcrypt.hashpw(password, bcrypt.gensalt())` |
| Custom hash functions | Framework defaults (Django `make_password`, bcrypt gem) |

## 2.3 Missing Auth on Routes

Compare route definitions against middleware/guard application:
- Routes without auth middleware that handle sensitive operations (CRUD, admin, user data)
- Controllers missing `@Authenticated` / `login_required` / `[Authorize]` decorators
- API endpoints without token validation

## 2.4 Session Fixation

- Session ID not regenerated after login (`req.session.regenerate()` missing post-auth)
- Session token set before authentication completes
- Session ID accepted from URL parameters or POST body

## 2.5 JWT Vulnerabilities

- `algorithms: ["none"]` or no algorithm restriction in `jwt.verify()`
- Missing `exp` claim validation
- Secret key hardcoded or weak (short string, common word)
- `jwt.decode()` without `verify=True` (Python PyJWT)
- Symmetric secret used where asymmetric expected

## 2.6 JWT Algorithm Confusion (RS256 → HS256)

When server uses RS256 (asymmetric), attacker creates a token with `"alg":"HS256"` signed using the server's **public key** as the HMAC secret. If the library accepts whatever algorithm the token header claims, the token passes.

```javascript
// ❌ NEVER: algorithm taken from token header
jwt.verify(token, publicKey)
jwt.verify(token, publicKey, { algorithms: ['HS256', 'RS256'] })  // accepts both

// ✅ ALWAYS: pin to expected algorithm only
jwt.verify(token, publicKey, { algorithms: ['RS256'] })
```

```python
# ❌ NEVER: no algorithms pin
jwt.decode(token, public_key, options={"verify_signature": True})
# ❌ NEVER: disables expiry check — common copy-paste from Stack Overflow
jwt.decode(token, key, algorithms=['HS256'], options={"verify_exp": False})

# ✅ ALWAYS:
jwt.decode(token, public_key, algorithms=["RS256"])
```

Severity: CRITICAL — arbitrary JWT claims → full auth bypass.

## 2.7 Missing JWT Claims Validation

```javascript
// ❌ NEVER: no issuer/audience check — accepts tokens from any service
jwt.verify(token, secret)

// ✅ ALWAYS: validate all relevant claims
jwt.verify(token, secret, {
  algorithms: ['HS256'],
  issuer: 'https://auth.myapp.com',
  audience: 'myapp-api'
})
```

Flag:
- `jwt.sign()` / `jwt.encode()` without `expiresIn` / `exp` — forever-valid tokens
- `jwt.verify()` without `issuer` and `audience` on multi-service deployments
- `options={"verify_exp": False}` — disables expiry check entirely
- Access tokens with `exp` > 24 hours (flag as MEDIUM)

## 2.8 OAuth 2.0 / OIDC Vulnerabilities

```javascript
// ❌ NEVER: missing state param — CSRF on OAuth flow
app.get('/oauth/callback', (req, res) => {
  const code = req.query.code
  // no state validation → CSRF: attacker tricks victim into binding attacker's account
  exchangeCode(code)
})

// ✅ ALWAYS: verify state matches session value
if (req.query.state !== req.session.oauthState) {
  return res.status(403).send('CSRF detected')
}
```

**What to flag:**
- OAuth callback without `state` parameter validation
- `redirect_uri` not validated against a registered allowlist (open redirect → token theft)
- `response_type=token` (implicit flow) — access token in URL fragment, logged in server logs
- `id_token` accepted without signature verification (`jwks_uri` fetch + algorithm pin)
- PKCE (`code_challenge`) missing on public clients (mobile/SPA) — authorization code interception
- Client secret hardcoded in client-side JS or mobile app binary

## 2.9 Insecure Token Generation

- `Math.random()` / `random.random()` / `rand()` for security tokens
- UUID v1 (time-based, predictable) for session tokens
- Sequential/predictable token patterns
- Missing `crypto.randomBytes()` / `secrets.token_hex()` / `SecureRandom`

---

# Category 3 — Authorization

## 3.1 Missing Access Control (IDOR)

For every route performing data access:
- Does it verify the requesting user owns/has access to the resource?
- Pattern: `db.find(req.params.id)` WITHOUT `WHERE user_id = currentUser.id`
- Direct object reference: user ID, order ID, document ID from request used in query without ownership check

## 3.2 Privilege Escalation

- Role checks using client-supplied values: `if (req.body.role === 'admin')`
- Mass assignment allowing role elevation: `User.update(req.body)` including role field
- Admin endpoints protected only by client-side checks (frontend route guards without backend enforcement)

## 3.3 Horizontal Access Control

- Shared resource access without tenant/org scoping
- Multi-tenant app using single DB without `tenant_id` filtering on queries
- API endpoints returning data across tenant boundaries
