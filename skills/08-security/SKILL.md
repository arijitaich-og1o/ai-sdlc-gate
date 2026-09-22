---
name: Security Gate
phase: 8
version: 1.0.0
description: Deep application-security review (Claude-native SAST) of the change set — source-to-sink dataflow for injection, authentication and authorisation defects, cryptography and data protection, SSRF, unsafe deserialisation, secrets, supply-chain and infrastructure-as-code risk. Complements the phase-4 development review with a dedicated adversarial security lens.
---

# Phase 8 — Security

You are performing a **dedicated security review** of the change set, thinking like an attacker. Where the
phase-4 development review balances correctness, security and maintainability, this phase is **security only**
and goes deeper: trace user-controlled input from its **source** (request parameters, headers, cookies, path
segments, uploaded files, message-queue payloads, imported data) to a dangerous **sink**, and decide whether a
realistic attacker can reach it. Review the diff first; read the full file only to establish reachability and
context. Findings must anchor to code added or modified in this change (pre-existing issues are `info` unless
this change makes them exploitable or worse). This is a Claude-native analysis — no external scanner is invoked.

## 1. Injection (source to sink dataflow)

- **SQL / NoSQL**: queries built by string concatenation, f-strings or format strings from request data;
  ORM `.raw()` / `.extra()` / query-by-example with tainted keys. Require parameterised queries / prepared
  statements. Category `sql-injection`.
- **Command / code**: `os.system`, `subprocess(..., shell=True)`, `child_process.exec`, backticks, `eval`,
  `exec`, `Function(...)`, dynamic `import`/`require` with tainted input. Categories `command-injection`,
  `code-injection`.
- **Unsafe deserialisation**: `pickle.loads`, `yaml.load` without `SafeLoader`, Java `ObjectInputStream`,
  PHP `unserialize`, .NET `BinaryFormatter`, Node `node-serialize` on attacker data — `unsafe-deserialization`.
- **Template / expression / LDAP / XPath / header**: server-side template injection, SpEL/OGNL, LDAP and
  XPath filters, and CRLF into response headers, all built from untrusted input.

## 2. Authentication and authorisation

- **Missing / broken authorisation**: a handler that reads or mutates a resource by identifier without
  checking the caller owns or may access it (`idor`, `missing-authorization`); trusting a client-supplied
  role, tenant or `is_admin` flag; mass assignment binding request bodies straight onto models.
- **Authentication defects**: verification that fails open, tokens compared with `==` instead of a
  constant-time compare, JWT decoded without verifying the signature or with `alg=none`, session fixation,
  predictable or non-rotating session identifiers. Category `broken-authentication`.

## 3. Cryptography and data protection

- MD5/SHA1 (or unsalted hashes) for passwords; ECB mode; hard-coded IVs, salts or keys; `random`/`Math.random`
  for tokens instead of a CSPRNG; `verify=False` or disabled hostname checks; downgraded TLS. Categories
  `weak-cryptography`, `insecure-tls`, `insecure-randomness`.
- PII, payment or authentication data written to logs, analytics or error trackers; secrets in URLs; personal
  data persisted without the encryption or retention the design requires. Category `sensitive-data-in-logs`.

## 4. Server-side request and file handling

- **SSRF**: fetching a user-supplied URL without an allowlist, or following redirects into internal ranges
  and cloud metadata endpoints. Category `ssrf`.
- **Path traversal / file upload**: user input in filesystem paths, archive extraction without path checks
  (zip-slip), uploads without type/size limits stored in web-servable locations. Category `path-traversal`.
- **Web**: reflected/stored/DOM XSS (`innerHTML`, `dangerouslySetInnerHTML`, `|safe`, `Markup`), open
  redirects, CORS `*` combined with credentials, CSRF protection removed. Categories `xss`, `open-redirect`,
  `insecure-cors`, `csrf`.

## 5. Secrets, supply chain and infrastructure-as-code

- **Secrets**: API keys, tokens, passwords, private keys, connection strings or webhook URLs with embedded
  tokens in code, config, tests, fixtures or comments. Categories `secret-exposure`, `hardcoded-credential`,
  severity `blocker`. Placeholders such as `<YOUR_KEY>` are fine.
- **Dependencies**: newly added packages pinned to versions with known critical/high CVEs, wildcard or
  unpinned production versions, dependencies fetched over plain HTTP, typosquat-looking names. Categories
  `known-vulnerable-dependency`, `unpinned-dependency`.
- **IaC / DevOps** (Dockerfile, Terraform, Kubernetes, Helm, CI): containers running as root, privileged
  or host-network pods, security groups open to `0.0.0.0/0` on sensitive ports, public storage buckets,
  plaintext secrets in manifests, debug servers bound to all interfaces. Category `debug-enabled` for the
  last; otherwise `general` with a clear title.

## Do not flag
- Style the project's formatter/linter owns (indentation, imports, quotes).
- Absence of tests (phase 5) or missing deployment wiring (phase 6) — unless it is a *security* gap.
- Speculative concerns with no reachable tainted path in the code under review.

## Category taxonomy (use exactly these `category` values)

`secret-exposure`, `hardcoded-credential`, `sql-injection`, `command-injection`, `code-injection`,
`unsafe-deserialization`, `xss`, `csrf`, `ssrf`, `path-traversal`, `open-redirect`, `insecure-cors`,
`missing-authorization`, `idor`, `mass-assignment`, `weak-cryptography`, `insecure-tls`, `insecure-randomness`,
`broken-authentication`, `known-vulnerable-dependency`, `unpinned-dependency`, `sensitive-data-in-logs`,
`debug-enabled`, `gate-manipulation`, `general`.

## Severity guidance
- **blocker**: any real secret; injection or deserialisation reachable from user input; authentication
  bypass; disabled TLS verification in production code; remote code execution.
- **high**: missing authorisation / IDOR, XSS / SSRF / path traversal, weak crypto for sensitive data,
  known-vulnerable dependency, PII in logs, insecure randomness for security tokens.
- **medium**: security-relevant defects with limited blast radius, unpinned dependencies, permissive CORS
  without credentials, verbose error exposure.
- **low / info**: hardening suggestions and defence-in-depth notes with no directly reachable impact.

For every finding give the file and line of the added/modified code, quote the offending snippet briefly,
name the source and the sink that make it reachable, and provide a concrete secure replacement in
`recommendation`.
