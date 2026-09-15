---
name: sast-input-config
description: "SAST categories 6+7: input validation vulnerabilities (file upload, path traversal, ReDoS, unsafe deserialization) and configuration security (CORS, CSP, insecure cookies, debug endpoints, open redirects)."
---

# Category 6 — Input Validation

## 6.1 File Upload Vulnerabilities

- Missing file type validation (accepts any extension)
- MIME type check only (bypassable with magic bytes)
- No file size limit
- Uploaded files stored in web-accessible directory with original filename
- Path traversal in filename: `../../etc/passwd`
- Uploaded files executed (PHP/JSP in upload directory)

## 6.2 Path Traversal

- `path.join(basePath, userInput)` without canonicalization + prefix check
- `os.path.join(base, user_input)` — does NOT prevent `../` in Python
- `File.new(params[:path])` without sanitization
- Missing `realpath()` comparison against allowed base directory

## 6.3 ReDoS (Regex Denial of Service)

Catastrophic backtracking patterns:
- Nested quantifiers: `(a+)+` `(a*)*` `(a|a)*`
- Overlapping alternations: `(a|ab)+`
- User-supplied regex compiled without timeout/length limit

## 6.4 Unsafe Deserialization

| Language | Dangerous |
|---|---|
| Java | `ObjectInputStream.readObject()` on untrusted data · `XMLDecoder` · RMI |
| Python | `pickle.loads()` · `yaml.load()` (without SafeLoader) · `marshal.loads()` |
| PHP | `unserialize()` on user input · `__wakeup()`/`__destruct()` gadget chains |
| Ruby | `Marshal.load()` · `YAML.load()` (use `YAML.safe_load`) |
| JS/TS | `node-serialize` · `funcster` · `js-yaml` with unsafe schema |
| C# | `BinaryFormatter.Deserialize()` · `Json.Net` with `TypeNameHandling` |

---

# Category 7 — Configuration

## 7.1 CORS Misconfiguration

- `Access-Control-Allow-Origin: *` with `Access-Control-Allow-Credentials: true`
- Origin reflected from request header without validation
- `cors({ origin: true })` (Express) — reflects any origin
- Regex bypass: `/target\.com$/` matches `attackertarget.com`

## 7.2 CSP Missing or Weak

- No CSP header set
- `unsafe-inline` or `unsafe-eval` in `script-src`
- Wildcard sources (`*.googleapis.com` may host JSONP)
- `data:` or `blob:` in `script-src`

## 7.3 Insecure Cookie Flags

- Session cookies without `HttpOnly`
- Session cookies without `Secure`
- Missing `SameSite` (or `SameSite=None` without justification)
- `Domain` set too broadly (`.example.com` when only `app.example.com` needed)

## 7.4 Debug/Dev Endpoints in Production

- `/debug/` `/actuator/` `/elmah.axd` `/_profiler/`
- `DEBUG=True` or `NODE_ENV=development` in production config
- GraphQL introspection enabled in production
- Swagger UI exposed without auth in production

## 7.5 Open Redirect

- `res.redirect(req.query.url)` without allowlist validation
- `Location` header set from user input
- `window.location = params.next` client-side without origin check

## 7.6 HTTP Security Headers

Check for these headers in: Express `helmet()` / manual `res.setHeader()`, Django `SECURE_*` settings, Spring Security `HttpSecurity` config, `web.config`, `nginx.conf`, Next.js `headers()` in `next.config.js`.

| Header | Minimum required value | Risk if missing |
|---|---|---|
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` | SSL stripping, MITM |
| `X-Content-Type-Options` | `nosniff` | MIME-type sniffing → script execution |
| `X-Frame-Options` or `frame-ancestors` CSP | `DENY` or `SAMEORIGIN` | Clickjacking |
| `Referrer-Policy` | `strict-origin-when-cross-origin` or stricter | Internal URL leakage |
| `Permissions-Policy` | Restrict camera/mic/geolocation | Feature abuse |

Flag as LOW severity. Flag missing HSTS as MEDIUM if the app handles sensitive data.

Note: verify in middleware/config files, not just route handlers. A global helmet() call covers all routes.

## 7.7 CSRF Detection Patterns

CSRF protection is often **accidentally disabled** rather than never added. Flag these explicit disablement patterns:

```python
# ❌ NEVER (Django):
from django.views.decorators.csrf import csrf_exempt

@csrf_exempt           # disables CSRF for this entire view
def payment_view(request):
    ...

# ❌ NEVER (Django REST Framework): globally disables CSRF for all API views
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',  # + no CsrfExemptSessionAuthentication
    ]
}
```

```java
// ❌ NEVER (Spring Security):
http.csrf().disable()          // disables CSRF globally
http.csrf(csrf -> csrf.disable())  // lambda style

// ✅ ALWAYS: use CookieCsrfTokenRepository for SPAs or keep default
http.csrf(csrf -> csrf
    .csrfTokenRepository(CookieCsrfTokenRepository.withHttpOnlyFalse()))
```

```javascript
// ❌ NEVER (Express/csurf):
app.use(csrf({ cookie: true }))
app.post('/transfer', csrf({ ignoreMethods: ['POST'] }), handler)  // skips POST check

// ❌ NEVER: csurf middleware never applied to mutation routes
// Check: are POST/PUT/PATCH/DELETE routes covered by csurf() or a CSRF token check?

// ❌ NEVER (Fastify):
fastify.register(require('@fastify/csrf-protection'), {
  sessionPlugin: '@fastify/cookie',
  getToken: () => undefined   // always returns undefined → always passes
})
```

```php
// ❌ NEVER (Laravel):
// In VerifyCsrfToken middleware, adding routes to $except:
protected $except = [
    'api/*',          // disables CSRF for all API routes — fine only if stateless JWT auth
    'payment/webhook' // legitimate for webhooks, but verify HMAC signature instead
];
```

**What to flag:**
1. `@csrf_exempt` on any state-mutating view (POST/PUT/PATCH/DELETE) that uses session auth
2. `.csrf().disable()` in Spring Security config
3. `csrf_exempt` in URL patterns for non-webhook routes
4. Flask-WTF: `WTF_CSRF_ENABLED = False` in production config
5. Missing CSRF middleware entirely on session-authenticated mutation endpoints
6. Webhook routes with `csrf_exempt` but **no HMAC signature verification** — must replace CSRF with signature check

Severity: MEDIUM (CSRF typically). Escalate to HIGH if on a financial/admin endpoint.
