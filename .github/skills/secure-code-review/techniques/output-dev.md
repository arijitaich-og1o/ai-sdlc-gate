---
name: output-dev
description: "Developer-friendly output format for secure-code-review — ❌ NEVER / ✅ ALWAYS style with fix suggestions, test-to-write, and pre-deployment checklist. Default when any extension flag is set (--dev, --audit, --backdoor, --devops, --diff, --emit-ci) and --report is NOT passed."
---

# Developer-Friendly Output Format

## Per-Finding Format

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[SEVERITY] Finding Class  ·  path/to/file.ext:line
OWASP: A03:2021 Injection  ·  CWE-89
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  ❌ NEVER do this:
     <exact vulnerable code snippet from the file>

  ✅ ALWAYS do this:
     <corrected code snippet — specific to this language/framework>

  Why: <one sentence explaining the real-world impact>

  Test to write:
     <specific test assertion that would catch this regression>

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Suppression (`// scr-ignore:`)

If a line has `// scr-ignore: <reason>` (or `# scr-ignore:` in Python/Ruby) within ±2 lines of the finding:
- Do NOT output the finding in dev format
- Log it in a separate "Accepted Risk" block at the end:
  ```
  ACCEPTED RISK (1)
    src/utils/query.js:47 — sql_injection — "parameterized at call site upstream"
  ```
- Bare `// scr-ignore` without a reason → still flag with: `Suppression missing reason — treated as active finding`

## Example

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[CRITICAL] SQL Injection  ·  src/services/userService.js:47
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
```

## Summary Line (after all findings)

```
Found: N CRITICAL  N HIGH  N MEDIUM  N LOW  (N accepted risk)
```

## Security Score (always append)

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Security Score: C+  (62/100)
  Previous scan:  D   (48/100)  ↑ +14 points

  Breakdown:
    Critical findings:  N  (−20 pts each)
    High findings:      N  (−10 pts each)
    Medium findings:    N  (−3 pts each)
    Accepted risks:     N  (documented)    +2 pts each
    No hardcoded secrets found             +10 pts
    Dependencies up to date                +10 pts

  Grade: A (90–100) · B (75–89) · C (60–74) · D (40–59) · F (<40)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

Save score to `sast-findings/score.json`:
```json
{"date": "2026-08-24", "score": 62, "grade": "C+", "critical": 2, "high": 3, "medium": 4, "low": 1}
```

On next scan, read `score.json` and show trend line. If file does not exist, no trend shown.

## --audit Verdict Block (before checklist, if --audit was passed)

```
═══════════════════════════════════════════════════════
  THIRD-PARTY AUDIT VERDICT: [SAFE TO USE / REVIEW BEFORE USING / DO NOT USE]
═══════════════════════════════════════════════════════
  Scanned: NNN files  |  NNN lines  |  N modules

  [SEVERITY] file:line — description
  ...

  Action: <specific next step>
═══════════════════════════════════════════════════════
```

Verdicts:
- **SAFE TO USE** — zero findings after false-positive filter
- **REVIEW BEFORE USING** — HIGH or MEDIUM findings; inspect before running
- **DO NOT USE** — CRITICAL finding confirmed; do not install or execute

## Pre-Deployment Checklist (always append at end)

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  PRE-DEPLOYMENT SECURITY CHECKLIST
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Secrets & Config
  [ ] No hardcoded secrets, keys, or passwords in source
  [ ] All secrets loaded from environment variables
  [ ] .env is in .gitignore and never committed

Authentication
  [ ] Passwords hashed with bcrypt / argon2 / scrypt (NOT md5/sha1)
  [ ] Session tokens: httpOnly + Secure + SameSite=Strict
  [ ] No sensitive data in localStorage or sessionStorage

Input & Data
  [ ] All user input validated server-side before use
  [ ] Parameterized queries everywhere (no string SQL concatenation)
  [ ] File uploads: type, size, and extension validated

Infrastructure (if IaC detected)
  [ ] No public cloud storage buckets or overly open security groups
  [ ] Containers run as non-root user
  [ ] Base images pinned to specific versions (not :latest)

Dependencies
  [ ] No known-vulnerable package versions (npm audit / pip-audit)
  [ ] Dependency versions pinned in lock file and committed

CI/CD
  [ ] GitHub Actions: all third-party actions SHA-pinned
  [ ] Secrets not echoed in pipeline logs

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## --fix Behavior (if --fix was passed)

For every finding with `confidence: HIGH`:
1. Show diff preview before writing:
   ```
   Fix: src/services/userService.js:47
   - db.query(`SELECT * FROM users WHERE name = '${data.name}'`)
   + db.query('SELECT * FROM users WHERE name = $1', [data.name])
   Apply? [y/N]
   ```
2. Without `--yes`: prompt per file, default NO
3. With `--yes`: auto-apply all HIGH-confidence fixes without prompting
4. Write `sast-fixes.log` listing every file changed and what was changed
5. Skip `confidence: MEDIUM` and `confidence: LOW` — never auto-fix uncertain findings
6. Never modify test files unless `--fix-tests` also passed

## --baseline Behavior (if --baseline passed)

- First run: write `sast-findings/.baseline.json` with all current findings (file + finding class + code hash). Print: `Baseline established: N findings recorded.`
- Subsequent runs (baseline file exists): suppress baseline findings from output. Print: `N new findings · N existing findings suppressed (baseline)`
- `--show-all` overrides: shows everything including baseline findings
- `--report` always includes baseline findings under "Pre-existing / Out of Scope" section
- Match by: file path + finding class + code snippet hash (not line number — survives refactors)

## --min-severity Behavior

- `--min-severity critical` → show only CRITICAL
- `--min-severity high` → show CRITICAL + HIGH
- `--min-severity medium` → show CRITICAL + HIGH + MEDIUM (default)
- `--min-severity low` → show all
- Suppressed findings and score still calculated on full set — filter is display-only

## --pr-comment Behavior (if --pr-comment passed)

Requires: `GITHUB_TOKEN` env var set. Detects current branch's open PR via `gh pr view`.

1. Group all findings into a single PR review (not separate comments)
2. Post each finding as an inline comment on the exact line in the diff
3. Add PR-level summary comment with security score at top
4. Findings suppressed via `// scr-ignore:` → no comment posted
5. Print: `Posted N inline comments on PR #123`

## --watch Behavior (if --watch passed)

1. Print: `Watching <N> files. Save any file to scan it.`
2. On file save: rescan only the changed file using `--quick` depth
3. Display findings for that file, clear on next save
4. Stop with Ctrl+C
5. Combine with `--min-severity high` to reduce noise: `--watch --min-severity high`

## --git-history Behavior (if --git-history passed)

1. Run: `git log -p --all` piped through secret pattern matching
2. Scan for: `AKIA*` `sk_live_*` `sk_ant_*` `ghp_*` `-----BEGIN RSA PRIVATE KEY-----` connection strings with passwords `password =` `api_key =`
3. Report: commit hash · author · date · file (even if deleted) · matched pattern
4. Suggest: rotate credential immediately + `git filter-repo` to rewrite history
5. Runs separately from code scan — does not affect security score

## --sarif Behavior (if --sarif passed)

Write `sast-findings/results.sarif` after scan. SARIF 2.1.0 format compatible with GitHub Security tab. Each finding maps to a SARIF `result` with `ruleId` (CWE), `level`, `locations` (file + line), and `message`. Upload in CI:
```yaml
- uses: github/codeql-action/upload-sarif@v3
  with:
    sarif_file: sast-findings/results.sarif
```

## --json Behavior (if --json passed)

Output all findings as a JSON array instead of the ❌/✅ blocks. One object per finding:
```json
[
  {
    "id": "SF01",
    "severity": "CRITICAL",
    "confidence": "HIGH",
    "category": "injection",
    "class": "sql_injection",
    "file": "src/services/userService.js",
    "line": 47,
    "sink": "db.query(sql)",
    "source": "req.body.username",
    "owasp": "A03:2021",
    "cwe": "CWE-89",
    "remediation": "Use parameterized query"
  }
]
```
Still append score JSON to `sast-findings/score.json`. Pre-deployment checklist is suppressed in `--json` mode (machine-readable output only). Security score appears as a trailing JSON object: `{"score": 62, "grade": "C+", ...}`.

## --explain Behavior (if --explain passed)

For every finding in addition to the standard ❌/✅ format, append a 3-sentence attack scenario:
```
  Attack scenario:
    An attacker sends a POST request to /api/users with the username field set to
    "' OR 1=1 --". The query becomes SELECT * FROM users WHERE name = '' OR 1=1 --',
    which returns all rows. The attacker receives the full user table in the response,
    including hashed passwords and PII.
```
Use concrete, realistic payloads. No vague "may allow an attacker to". The scenario should be specific to the code path found.

## --ci Behavior (if --ci passed or CI=true env var detected)

1. After completing the scan, check if any finding has severity CRITICAL or HIGH
2. If yes: exit with status code 1 (causes CI pipeline to fail)
3. If no: exit with status code 0
4. Print before findings:
   ```
   [CI MODE] Scan will exit 1 on any CRITICAL or HIGH finding
   ```
5. Combine with `--min-severity` to adjust threshold: `--ci --min-severity medium` → exit 1 on MEDIUM+
6. Suppressed findings (`// scr-ignore:`) do NOT count toward the exit code — accepted risks don't fail CI
7. `--baseline` findings do NOT count toward exit code — only new findings break the build

## --scope Behavior (if --scope <file> passed)

Read the scope file before scanning. Format (one entry per line):
```
# in-scope hosts / paths / endpoints
app.example.com
/api/v1/*
/admin/**
src/payments/
!src/payments/test/   # exclude (prefix with !)
```

Apply scope as an additional filter on top of auto-excludes:
- Only scan files under in-scope paths
- Skip files matching `!` exclusion lines
- At the start of output, print: `Scope: N files in scope, N excluded`

## --compliance Behavior (if --compliance <framework> passed)

Load `techniques/sast-compliance.md` and tag each finding with the relevant compliance control IDs:
- `--compliance pci` → tag findings with PCI-DSS Requirement numbers (e.g., `PCI Req 6.3.1`)
- `--compliance hipaa` → tag findings with HIPAA §164.312 sections
- `--compliance soc2` → tag findings with SOC 2 CC criterion codes

Add compliance tag inline in the finding header:
```
[CRITICAL] SQL Injection  ·  src/db/query.js:89  ·  PCI Req 6.3.1 · HIPAA §164.312(a)(1)
```

Also append a compliance summary at the end:
```
PCI-DSS Coverage: 4 findings map to requirements 6.3.1, 8.3.6, 10.2, 10.3
```

## --emit-ci Output (if --emit-ci was passed)

After checklist, read and write CI templates:

1. Read `references/ci-templates/github-actions.yml`
2. Write to `<scanned-path>/.github/workflows/security.yml` (create dirs if needed)
3. Read `references/ci-templates/pre-commit-config.yaml`
4. Write to `<scanned-path>/.pre-commit-config.yaml`
5. Read `references/ci-templates/gitlab-ci.yml`
6. Ask user: "Write GitLab CI template? [y/N]" — write to `<scanned-path>/.gitlab-ci-security.yml` if yes
7. Read `references/ci-templates/dependabot.yml`
8. Write to `<scanned-path>/.github/dependabot.yml` (creates/merges with existing)
9. Print:
```
CI configs generated:
  ✓ .github/workflows/security.yml  — GitHub Actions (Gitleaks + Semgrep + Trivy + Checkov, SHA-pinned)
  ✓ .pre-commit-config.yaml         — pre-commit hooks (gitleaks + private-key detection)
  ✓ .github/dependabot.yml          — Dependabot (npm, pip, docker, Actions, Terraform, weekly)
  ✓ .gitlab-ci-security.yml         — GitLab CI security jobs (if requested)

Setup: pip install pre-commit && pre-commit install
Note: These tools are optional. /secure-code-review works without them.
```
