---
mode: ask
description: Full security code review — 10 vulnerability categories, language-aware, with fix suggestions
---

You are performing a comprehensive security code review. Analyze the selected code (or the entire file if no selection) for the following vulnerability categories. For every finding, show the vulnerable code, the fix, and why it matters.

## Scope

Review for these 10 categories:

### 1. Injection sinks
- SQL injection (string concatenation in queries)
- Command injection (user input in exec/system/shell calls)
- XSS (user input rendered as HTML without encoding)
- SSTI (user input passed to template rendering functions)
- LDAP, XPath, NoSQL injection

### 2. Authentication & session
- Hardcoded credentials, API keys, or tokens
- Weak password hashing (MD5, SHA1, SHA256 without salt)
- Session tokens generated with insecure random
- JWT: missing algorithm restriction, missing expiry, hardcoded secret
- Session not regenerated after login

### 3. Authorization
- Direct object references without ownership check
- Routes/functions missing authentication guard
- Privilege escalation via mass assignment or client-supplied role

### 4. Cryptography
- Weak algorithms (DES, 3DES, RC4, AES-ECB)
- Hardcoded encryption keys or static IVs
- Missing TLS certificate validation

### 5. Data exposure
- Secrets or connection strings in source code
- Stack traces or DB errors returned to client
- PII or tokens written to logs

### 6. Input validation
- Path traversal in file operations
- File upload without type, size, or extension check
- Unsafe deserialization (pickle, unserialize, yaml.load)
- ReDoS-vulnerable regex patterns

### 7. Configuration
- CORS misconfiguration (wildcard origin + credentials)
- Insecure cookies (missing HttpOnly, Secure, SameSite)
- Debug mode or dev settings in production
- Open redirects from user-controlled input

### 8. Business logic
- Race conditions in balance or inventory operations
- Mass assignment without field allowlist
- Missing rate limiting on auth or OTP endpoints

### 9. Dependencies
- Packages with known CVEs
- Unpinned or wildcard version specifiers
- Deprecated APIs with security implications

### 10. Language-specific
- JavaScript: prototype pollution, eval, postMessage without origin check
- Python: format string injection, import injection, yaml.load
- Java: JNDI lookup on user input, XXE, EL injection
- PHP: type juggling with ==, include/require with user input
- Ruby: ERB injection, .send with user input, ^ vs \A in regex
- Go: http.DefaultClient without timeout, goroutine leaks
- C#: Path.Combine with absolute user input, FromSqlRaw with interpolation

---

## Output format

For each finding:

```
[SEVERITY] Category — file:line

  ❌ Vulnerable code:
     <exact code snippet>

  ✅ Fix:
     <corrected code in the same language/framework>

  Why: <one sentence on real-world impact>

  Test to write:
     <specific assertion that would catch this regression>
```

Severity levels: CRITICAL · HIGH · MEDIUM · LOW

End with a summary count: `Found: N CRITICAL  N HIGH  N MEDIUM  N LOW`

If no issues are found, state: `No security issues found in the reviewed scope.`

---

## Notes

- Trace data flows — only flag confirmed paths from user input to dangerous sink
- If sanitization exists, verify it addresses the specific sink type before dismissing
- Do not flag test files for injection unless they contain real credentials or production URLs
- Deduplicate: same sink reachable via multiple routes = one finding
