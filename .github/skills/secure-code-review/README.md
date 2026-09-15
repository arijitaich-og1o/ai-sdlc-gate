# secure-code-review

> **Universal security code review for engineering teams** — works in Claude Code, GitHub Copilot, Visual Studio, VS Code, and any IDE. No external tools, no installs, no API keys.

[![Version](https://img.shields.io/badge/version-3.0-blue)](./SKILL.md)
[![Works with Claude Code](https://img.shields.io/badge/Claude%20Code-skill-blue)](https://claude.ai/code)
[![Works with GitHub Copilot](https://img.shields.io/badge/GitHub%20Copilot-compatible-green)](https://github.com/features/copilot)
[![VS Code](https://img.shields.io/badge/VS%20Code-tasks%20included-blue)](https://code.visualstudio.com)
[![Visual Studio](https://img.shields.io/badge/Visual%20Studio-Copilot%20compatible-purple)](https://visualstudio.microsoft.com)

---

## What's New in v3.0

- **GraphRAG-mode** (`--graph`) — builds a call graph and deep-reads only source→sink paths; ~60% token reduction on large codebases
- **Android / iOS / Electron** — full Tier 1 detection for mobile and desktop app security (SharedPreferences, Keychain, WebView, nodeIntegration, IPC)
- **Rendering-based SSRF** — wkhtmltopdf, Puppeteer, WeasyPrint, pdfkit patterns that reach cloud metadata
- **Serverless/FaaS** — Lambda event validation, AuthType:NONE, secrets in env vars, overly permissive execution roles
- **CSRF detection** — framework-specific patterns (Django, Spring, Express, Fastify, Laravel, Flask-WTF)
- **Compliance tagging** (`--compliance`) — inline PCI-DSS, HIPAA, and SOC 2 control IDs per finding
- **Machine-readable output** (`--json`, `--explain`, `--ci`) — JSON array, attack scenarios, exit-code-1 CI gate
- **Scope file** (`--scope`) — target specific paths and endpoints per scan
- **4 CI templates** (`--emit-ci`) — GitHub Actions, pre-commit, GitLab CI, Dependabot
- **Project-level config** — `.scr-config.yml` for per-repo defaults

---

## What It Does

`/secure-code-review` is a slash skill for [Claude Code](https://claude.ai/code) that performs deep security analysis on your codebase. Claude reads your source files directly, traces data flows from user input to dangerous sinks, and reports exploitable vulnerabilities — not just pattern matches.

- **10+ vulnerability categories** — injection, auth, authorization, crypto, data exposure, input validation, configuration, business logic, dependencies, language-specific, privacy, SSRF, XXE, GraphQL, WebSocket, gRPC, LLM/AI
- **Universal language support** — auto-detects the language from signal files; no configuration needed
- **Developer-friendly output** — ❌ NEVER / ✅ ALWAYS format with fix suggestions and tests to write
- **Third-party audit** — scan open-source or vendor code for backdoors before adopting it
- **IaC security** — Dockerfile, Terraform, Kubernetes, GitHub Actions, Lambda, RDS, CloudFront (auto-triggered)
- **CI integration** — optionally generates GitHub Actions, GitLab CI, pre-commit, and Dependabot configs

---

## Language Support

| Tier | Languages | Detection |
|---|---|---|
| **Tier 1** (full coverage) | JavaScript, TypeScript, Python, Java, PHP, C#, Go, Ruby, Android (Java/Kotlin), Electron | `package.json`, `pyproject.toml`, `pom.xml`, `composer.json`, `*.csproj`, `go.mod`, `Gemfile`, `AndroidManifest.xml`, `electron` in deps |
| **Tier 2** (core coverage) | Rust, Kotlin, Swift, Scala, iOS/Swift | `Cargo.toml`, `build.gradle.kts`, `Package.swift`, `build.sbt`, `import UIKit`/`import SwiftUI` |
| **Tier 3** (generic) | Any other language | Pattern-based analysis |

---

## Installation

Copy the skill to your Claude Code skills directory:

```bash
# macOS / Linux
git clone https://github.com/<your-org>/secure-code-review \
  ~/.claude/skills/secure-code-review

# Windows (PowerShell)
git clone https://github.com/<your-org>/secure-code-review `
  "$env:USERPROFILE\.claude\skills\secure-code-review"
```

Restart Claude Code — the skill is immediately available as `/secure-code-review`.

> **No further setup required.** Claude Code is the analysis engine. No `npm install`, no `pip install`, no Docker.

---

## Usage

```
/secure-code-review <path> [flags]
```

### All flags

| Flag | Description |
|---|---|
| `--quick` | Scan only auth, config, and entry-point files (fastest) |
| `--thorough` | Full call-chain tracing across all files (most complete) |
| `--dev` | Force developer-friendly ❌/✅ output |
| `--report` | Formal `SF<NN>` output for security teams (includes `sast-findings/` directory) |
| `--audit` | Third-party code evaluation — outputs SAFE / REVIEW / DO NOT USE verdict |
| `--backdoor` | Backdoor and malware scan (6 detection types + entropy analysis) |
| `--devops` | IaC scan (auto-triggered when Dockerfile/Terraform/K8s/CI files detected) |
| `--diff` | Scan only files changed in the current branch (PR review mode) |
| `--fix` | Write high-confidence fixes to disk (diff preview before each write) |
| `--fix --yes` | Auto-apply all high-confidence fixes without prompting |
| `--baseline` | Establish baseline / only show new findings vs last scan |
| `--emit-ci` | Generate GitHub Actions, GitLab CI, pre-commit, and Dependabot configs |
| `--custom-rules <file>` | Append org-specific rules from a markdown file |
| `--language <lang>` | Force language detection (e.g. `--language python`) |
| `--graph` | GraphRAG-mode: build call graph → community detection → deep-read source→sink paths only (~60% token reduction) |
| `--json` | Output findings as JSON array (machine-readable, one object per finding) |
| `--explain` | Add 3-sentence attack-scenario with real payloads to every finding |
| `--ci` | CI mode: exit 1 on any CRITICAL or HIGH finding; auto-detected when `CI=true` |
| `--scope <file>` | Load scope file — one path per line, `!` prefix to exclude |
| `--compliance <f>` | Tag findings with compliance control IDs: `pci`, `hipaa`, `soc2` |
| `--sarif` | Write `sast-findings/results.sarif` (GitHub Security tab compatible) |
| `--pr-comment` | Post findings as inline GitHub PR review comments |
| `--watch` | Rescan on file save — real-time terminal feedback |
| `--git-history` | Scan git log for secrets in deleted files |
| `--min-severity <l>` | Filter output: `critical` `high` `medium` `low` |

### Examples

```bash
# Review your own code before merging
/secure-code-review ~/code/my-app

# Quick pre-commit check on changed files only
/secure-code-review ~/code/my-app --diff --quick

# Large codebase — build call graph, read only source→sink paths
/secure-code-review ~/code/my-app --graph

# Evaluate a third-party library before adding it as a dependency
/secure-code-review ~/vendor/suspect-lib --audit

# Audit open-source code for backdoors
/secure-code-review ~/downloads/npm-package --backdoor

# Full security review with CI configs generated
/secure-code-review ~/code/my-app --thorough --emit-ci

# Scan Terraform + Kubernetes + Lambda infra
/secure-code-review ~/infra --devops

# Machine-readable output for a security pipeline
/secure-code-review ~/code/my-app --json --ci

# Compliance report for PCI audit
/secure-code-review ~/code/my-app --thorough --compliance pci --report

# Formal report for security team review
/secure-code-review ~/code/my-app --report
```

---

## Project-Level Config (`.scr-config.yml`)

Place a `.scr-config.yml` in your project root to set per-repo defaults:

```yaml
# .scr-config.yml
min_severity: high
compliance: pci
emit_ci: false
custom_rules: .security-rules.md
```

Command-line flags override config file values. The skill reads this file automatically at startup.

---

## Output

### Developer-friendly (default)

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[CRITICAL] SQL Injection  ·  src/services/userService.js:47
OWASP: A03:2021 Injection  ·  CWE-89
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  ❌ NEVER do this:
     db.query(`SELECT * FROM users WHERE name = '${data.name}'`)

  ✅ ALWAYS do this:
     db.query('SELECT * FROM users WHERE name = $1', [data.name])

  Why: String interpolation in SQL lets an attacker inject arbitrary SQL
       commands, accessing or deleting any data in the database.

  Test to write:
     Pass name = "'; DROP TABLE users; --" and assert the query
     executes safely (returns 0 rows, does not throw or modify data).

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Found: 2 CRITICAL  3 HIGH  4 MEDIUM  1 LOW
Security Score: C+  (62/100)
```

### Third-party audit (`--audit`)

```
═══════════════════════════════════════════════════════
  THIRD-PARTY AUDIT VERDICT: DO NOT USE
═══════════════════════════════════════════════════════
  Scanned: 247 files  |  8,340 lines  |  3 modules

  [CRITICAL] postinstall.js:14 — outbound HTTP during npm install
  [HIGH]     src/utils/crypto.js:89 — base64-encoded eval payload
  [MEDIUM]   package.json — event-stream@3.3.6 (known compromised)

  Action: Do not install or execute. Inspect flagged files and
          consider an alternative package.
═══════════════════════════════════════════════════════
```

### GraphRAG-mode summary (`--graph`)

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  GRAPH-ACCELERATED SCAN
  Communities detected: 12  |  CRITICAL: 3  |  HIGH: 2  |  SKIP: 7
  Files deep-read: 28 / 87 total  (68% skipped)
  Graph cached: sast-findings/graph.json
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## What It Detects

### Security vulnerabilities

| # | Category | Examples |
|---|---|---|
| 1 | Injection | SQLi, XSS, command injection, SSTI, LDAP, NoSQL, CRLF |
| 2 | Authentication & session | Hardcoded creds, weak hashing, session fixation, JWT flaws, timing attacks |
| 3 | Authorization | IDOR, missing access control, privilege escalation, CSRF |
| 4 | Cryptography | Weak algorithms, hardcoded keys/IVs, missing cert validation, ECB mode |
| 5 | Data exposure | Secrets in source (17 service patterns), verbose errors, sensitive logging |
| 6 | Input validation | Path traversal, file upload bypass, ReDoS, unsafe deserialization |
| 7 | Configuration | CORS/CSP misconfig, insecure cookies, open redirects, debug endpoints |
| 8 | Business logic | Race conditions, mass assignment, API pagination, type coercion, missing rate limits |
| 9 | Dependencies | Known CVEs, unpinned versions, deprecated APIs |
| 10 | Language-specific | Prototype pollution (JS), JNDI (Java), type juggling (PHP), ERB injection (Ruby), pickle (Python) |
| 11 | SSRF | Direct URL fetch, DNS rebinding, cloud metadata (169.254.169.254), **rendering-based** (wkhtmltopdf, Puppeteer, WeasyPrint, pdfkit) |
| 12 | XXE | DTD injection, external entity, billion-laughs |
| 13 | GraphQL | Introspection enabled, batch query DoS, broken field-level auth |
| 14 | WebSocket | Missing auth on upgrade, message injection, origin validation |
| 15 | gRPC | Unauthenticated reflection, insecure channel |
| 16 | LLM/AI | Prompt injection, training data exfiltration, insecure agent tools |
| 17 | Privacy | PII in logs, unencrypted PII storage, missing consent |

### Mobile & desktop app security

| Platform | Key checks |
|---|---|
| **Android** | SharedPreferences `MODE_WORLD_READABLE`, WebView `addJavascriptInterface` (CRITICAL on Android <4.2), `setAllowUniversalAccessFromFileURLs`, exported components without `android:permission`, cleartext traffic, missing `network_security_config.xml` |
| **iOS/Swift** | `UserDefaults` for tokens, `kSecAttrAccessibleAlways`, WKWebView `evaluateJavaScript(userInput)`, `NSAllowsArbitraryLoads:true`, LAContext fallback bypass |
| **Electron** | `nodeIntegration:true` (XSS→RCE), `contextIsolation:false`, `webSecurity:false`, IPC without allowlist, remote module, protocol path traversal, unsigned autoupdater |

### Backdoor & malware detection (`--backdoor` / `--audit`)

| Type | What Claude looks for |
|---|---|
| Obfuscated execution | `eval`, `base64_decode`, `fromCharCode`, dynamic imports, hex strings used as code |
| Hidden network callbacks | Hardcoded IPs/domains, unexpected `fetch`/HTTP in utility code, DNS in lifecycle scripts |
| Rogue credentials | Backdoor accounts, hardcoded API keys, secondary auth paths |
| Supply chain tampering | Malicious `postinstall`/`preinstall`, known-compromised package versions |
| CI/CD poisoning | Unpinned GitHub Actions, `pull_request_target` with write access, secrets in logs |
| Timing bombs | Date-gated logic, kill-switch APIs, hidden environment flags |
| High-entropy strings | Shannon entropy >4.5 on strings >20 chars = possible embedded payload |

### Secrets — 17-service pattern table

| Service | Pattern |
|---|---|
| AWS Access Key | `AKIA[0-9A-Z]{16}` |
| Stripe Live | `sk_live_[0-9a-zA-Z]{24,}` |
| GitHub Token | `ghp_[0-9a-zA-Z]{36}` |
| Slack Token | `xoxb-[0-9]{11}-[0-9]{11}-[0-9a-zA-Z]{24}` |
| Firebase | `AIza[0-9A-Za-z_-]{35}` |
| GCP Service Account | `"type": "service_account"` in JSON |
| Private Key | `-----BEGIN (RSA\|EC\|OPENSSH) PRIVATE KEY-----` |
| JWT (hardcoded) | `eyJ[A-Za-z0-9_-]+\.eyJ...` |
| DB URL with password | `(postgres\|mysql\|mongodb)://[^:]+:[^@]+@` |
| Generic high-entropy | String >20 chars, Shannon entropy >4.5 |

### IaC security (`--devops`, auto on Dockerfile/Terraform/K8s/CI files)

| Platform | Key checks |
|---|---|
| Dockerfile | Root user, remote `ADD`, secrets in `ARG`/`ENV`, unpinned base images |
| Terraform | Public S3, open security groups, unencrypted storage, `Action: "*"` IAM, RDS publicly accessible, CloudFront without WAF, Lambda admin IAM |
| Kubernetes | Privileged containers, host namespaces, secrets in ConfigMap, mutable tags, **RBAC wildcard verbs/resources** |
| GitHub Actions | Unpinned actions (SHA required), `pull_request_target`, expression injection |
| Serverless/FaaS | Missing event source validation, Lambda URL `AuthType:NONE`, secrets in env vars, overly permissive execution role, missing timeout/reservedConcurrency |

---

## How It Works

This skill uses a **tiered token-optimized architecture**. The router (`SKILL.md`) loads in ~800 tokens and pulls in only the modules needed for each scan.

```
SKILL.md (router, ~80 lines)            ← always loaded
techniques/
  sast-injection.md                     ← all scans
  sast-auth-authz.md                    ← all scans
  sast-crypto-data.md                   ← standard + thorough
  sast-input-config.md                  ← standard + thorough
  sast-ssrf.md                          ← standard + thorough
  sast-logic-deps.md                    ← thorough only
  sast-lang-specific.md                 ← Tier 1 language detected
  sast-llm.md                           ← LLM deps detected
  sast-graphql.md                       ← GraphQL deps detected
  sast-websocket.md                     ← WebSocket detected
  sast-privacy.md                       ← --thorough or PII fields
  sast-xxe.md                           ← XML parsing detected
  sast-grpc.md                          ← gRPC deps detected
  sast-compliance.md                    ← --compliance flag
  backdoor-detection.md                 ← --backdoor / --audit
  devops-iac.md                         ← auto on IaC files / --devops
  supply-chain.md                       ← --audit
  dataflow.md                           ← tracing methodology
  graph-traversal.md                    ← --graph (GraphRAG pipeline)
  output-dev.md                         ← developer output format
references/
  route-mapping.md                      ← --thorough / DAST correlation
  output-report.md                      ← --report
  ci-templates/
    github-actions.yml                  ← written by --emit-ci
    pre-commit-config.yaml              ← written by --emit-ci
    gitlab-ci.yml                       ← written by --emit-ci
    dependabot.yml                      ← written by --emit-ci
```

**Subagent orchestration:** When multiple modules apply, they run as parallel fork subagents — wall-clock equals the slowest single module, not the sum of all. A two-stage false-positive filter agent always runs last to remove noise and assign confidence levels.

---

## GraphRAG Mode (`--graph`)

For large codebases, `--graph` builds a code knowledge graph before scanning — then reads only the files on source→sink paths. Everything else is skipped.

| Phase | What happens | Tokens (200-file codebase) |
|---|---|---|
| G1 Shallow extraction | Import graph + security signal scan (all files) | ~10,000 |
| G2 Community detection | BFS clusters + CRITICAL/HIGH/MEDIUM/SKIP labels | ~2,000 |
| G3 Hierarchical summaries | 2-sentence summaries cached to `sast-findings/graph.json` | ~1,000 |
| G4 Path traversal | Source→sink path per CRITICAL community | ~1,000 |
| G5 Targeted deep-read | Full analysis on on-path files only | ~56,000 |
| **Total (graph mode)** | | **~69,000** |
| Standard scan | Full read of all 200 files | ~180,000 |
| **Savings** | | **~62%** |

Repeat scans are even cheaper — `graph.json` is cached and only changed files are re-derived.

---

## CI Integration (`--emit-ci`)

Running `--emit-ci` writes four ready-to-use configs to your project:

**`.github/workflows/security.yml`** — GitHub Actions (SHA-pinned):
- [Gitleaks](https://github.com/gitleaks/gitleaks) — secrets in git history
- [Semgrep](https://github.com/semgrep/semgrep) — SAST with OWASP Top 10 rules
- [Trivy](https://github.com/aquasecurity/trivy) — dependency CVEs + IaC misconfigs
- [Checkov](https://github.com/bridgecrewio/checkov) — IaC policy enforcement

**`.pre-commit-config.yaml`** — pre-commit hooks:
- Gitleaks — catches secrets before commit
- detect-private-key — blocks accidentally committed keys
- Hadolint — Dockerfile linting

**`.gitlab-ci-security.yml`** — GitLab CI security jobs (prompted before writing)

**`.github/dependabot.yml`** — Dependabot for npm, pip, Docker, Actions, Terraform (weekly)

> These tools run in CI/CD. The `/secure-code-review` skill itself never calls them — Claude is the analysis engine.

---

## Compliance Tagging (`--compliance`)

Tag every finding with the relevant control IDs inline:

```
[CRITICAL] SQL Injection  ·  src/db/query.js:89  ·  PCI Req 6.3.1 · HIPAA §164.312(a)(1)
```

Supported frameworks:
- `--compliance pci` → PCI-DSS Requirement numbers
- `--compliance hipaa` → HIPAA §164.312 sections
- `--compliance soc2` → SOC 2 CC criterion codes

A compliance summary is appended at the end of each scan showing which controls have findings.

---

## Extending with Custom Rules

Create a markdown file with org-specific rules and pass it with `--custom-rules`:

```markdown
# My Org Security Rules

## Rule: No MD5 for any purpose
Any use of MD5 (even non-security) is banned by org policy. Flag all occurrences.

## Rule: Internal API calls must use mTLS
Any HTTP call to *.internal.example.com must use the mTLS client from pkg/mtls.
```

```bash
/secure-code-review ~/code/my-app --custom-rules ./security-rules.md
```

---

## Pre-Deployment Checklist

Every review appends a checklist covering secrets, authentication, input validation, infrastructure, dependencies, and CI/CD — a final gate before any code ships.

---

## Universal Setup — Works in Every IDE

### Claude Code (CLI · Desktop · VS Code Extension · Web)

The full skill with all flags. Best experience — deep data-flow tracing, GraphRAG graph mode, parallel subagents, backdoor detection.

```bash
# Install
git clone https://github.com/<your-org>/secure-code-review \
  ~/.claude/skills/secure-code-review   # macOS/Linux

git clone https://github.com/<your-org>/secure-code-review `
  "$env:USERPROFILE\.claude\skills\secure-code-review"   # Windows

# Use
/secure-code-review ~/code/my-app
/secure-code-review ~/code/my-app --graph        # large codebase, fast
/secure-code-review ~/code/my-app --audit        # third-party evaluation
```

Restart Claude Code — `/secure-code-review` appears immediately.

---

### GitHub Copilot (VS Code · Visual Studio · JetBrains · github.com)

Two files to copy into each project repo:

**1. Security awareness on every Copilot suggestion** — copy to `.github/copilot-instructions.md`:

```bash
cp templates/copilot-instructions.md .github/copilot-instructions.md
```

Once added, Copilot will automatically:
- Flag injection sinks as you type
- Suggest parameterized queries instead of string SQL
- Warn on hardcoded secrets and weak crypto
- Enforce `HttpOnly`/`Secure` on cookie suggestions

**2. Full security review on demand** — copy to `.github/prompts/security-review.prompt.md`:

```bash
mkdir -p .github/prompts
cp templates/security-review.prompt.md .github/prompts/security-review.prompt.md
```

Then in Copilot Chat (VS Code or Visual Studio), type:

```
#security-review
```

Or reference specific files:

```
#security-review review #file:src/controllers/userController.js
#security-review check this for SQL injection #selection
```

Copilot will run all 10 vulnerability categories with ❌/✅ fix suggestions.

---

### VS Code Tasks (Claude Code Extension)

If your team uses the Claude Code VS Code extension, the `.vscode/tasks.json` included in this repo adds four commands to the VS Code Task Runner:

| Task | How to run |
|---|---|
| Security Review — Full | `Ctrl+Shift+P` → Tasks: Run Task → Security Review — Full |
| Security Review — Quick | Tasks: Run Task → Security Review — Quick |
| Security Review — Changed Files Only | Tasks: Run Task → Security Review — Changed Files Only |
| Security Review — Audit Third-Party Code | Tasks: Run Task → Security Review — Audit Third-Party Code |

Copy `.vscode/tasks.json` to your project repo to enable these tasks.

---

### Org-Wide Rollout Checklist

To deploy across your organization:

```
For every project repo:
  [ ] Copy templates/copilot-instructions.md → .github/copilot-instructions.md
  [ ] Copy templates/security-review.prompt.md → .github/prompts/security-review.prompt.md
  [ ] Copy .vscode/tasks.json → .vscode/tasks.json  (if using VS Code)

For developers who want deep analysis:
  [ ] Install Claude Code: https://claude.ai/code
  [ ] Clone this repo to ~/.claude/skills/secure-code-review
  [ ] Done — /secure-code-review is available immediately
```

---

## Requirements

| Tool | Requirement |
|---|---|
| Claude Code | [Claude Code](https://claude.ai/code) + Claude account (free or Pro) |
| GitHub Copilot | GitHub Copilot subscription + VS Code, Visual Studio, or JetBrains |
| VS Code Tasks | Claude Code VS Code extension |

---

## Architecture Decisions

| Decision | Choice | Reason |
|---|---|---|
| External tools | None required | Works on any machine without setup |
| Language detection | Signal-file based | No config needed; covers monorepos |
| Output format | Developer-friendly default | Engineers fix issues faster with ❌/✅ + tests |
| Token optimization | Tiered modules + GraphRAG | 91% reduction (tiered) or 62% reduction (graph) vs monolithic |
| False positives | Two-stage LLM filter | Reduces noise before results reach the developer |
| Graph traversal | Import-graph BFS + community detection | Scales to 500+ file codebases without reading everything |

---

## License

MIT — see [LICENSE](./LICENSE)
