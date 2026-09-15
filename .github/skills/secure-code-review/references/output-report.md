---
name: output-report
description: "Formal SF<NN> security-team output format for secure-code-review — finding files, index.json schema, and console summary box. Loaded when --report flag is passed or when invoked by /engage-sast."
---

# Phase 5 — Formal SF\<NN\> Output (Security Team Format)

Loaded when `--report` is passed or invoked by `/engage-sast`.

## 5a — Finding Files

Write each finding to `sast-findings/SF<NN>-<class>.md`:

````markdown
# SF01 — SQL Injection

**Severity:** CRITICAL  
**Confidence:** HIGH  
**Category:** 1. Injection Sinks  
**Class:** 1.1 SQL Injection  

## Location

- **File:** src/repositories/userRepo.js
- **Line:** 23
- **Function:** findByFilters()
- **Route:** POST /api/users

## Data Flow

```
req.body.name (user input)
  → userController.create() [userController.js:14]
  → validateInput(data) [validate.js:28] — PASSES (no SQL sanitization)
  → userService.save(validated) [userService.js:45]
  → userRepo.findByFilters(filters) [userRepo.js:23] — SINK
```

## Vulnerable Code

```javascript
async findByFilters(filters) {
  const sql = `SELECT * FROM users WHERE name = '${filters.name}'`;
  return db.query(sql);
}
```

## Remediation

```javascript
async findByFilters(filters) {
  return db.query('SELECT * FROM users WHERE name = $1', [filters.name]);
}
```

## DAST Correlation Target

Test `POST /api/users` parameter `name` for SQL injection.
Priority: HIGH — code-confirmed sink.
````

## 5b — Index File

Write `sast-findings/index.json`:

```json
{
  "scan_metadata": {
    "tool": "secure-code-review (Claude-native SAST)",
    "depth": "standard",
    "source_path": "/path/to/code",
    "language": "TypeScript",
    "framework": "Next.js 14",
    "files_scanned": 342,
    "files_total": 847,
    "priority_tiers_covered": ["P0", "P1", "P2"]
  },
  "summary": {
    "total": 15,
    "by_severity": {"CRITICAL": 2, "HIGH": 5, "MEDIUM": 4, "LOW": 3, "INFO": 1},
    "by_category": {"injection": 4, "auth_session": 3, "authorization": 2, "crypto": 1,
                    "data_exposure": 2, "input_validation": 1, "configuration": 1, "business_logic": 1},
    "by_confidence": {"HIGH": 8, "MEDIUM": 5, "LOW": 2}
  },
  "findings": [
    {
      "id": "SF01", "class": "sql_injection", "severity": "CRITICAL",
      "confidence": "HIGH", "file": "src/repositories/userRepo.js",
      "line": 23, "route": "POST /api/users", "dast_target": true
    }
  ],
  "route_map": {},
  "coverage": {
    "categories_scanned": [1,2,3,4,5,6,7,8,9,10],
    "files_by_priority": {"P0": 12, "P1": 45, "P2": 285}
  }
}
```

## 5c — Console Summary

```
╔══════════════════════════════════════════════════════════╗
║  SECURE CODE REVIEW COMPLETE                            ║
╠══════════════════════════════════════════════════════════╣
║  Language:    TypeScript (Next.js 14)                   ║
║  Depth:       Standard (P0-P2)                          ║
║  Files:       342 scanned / 847 total                   ║
╠══════════════════════════════════════════════════════════╣
║  CRITICAL:    2    HIGH:    5    MEDIUM:    4            ║
║  LOW:         3    INFO:    1    TOTAL:    15            ║
╠══════════════════════════════════════════════════════════╣
║  DAST targets generated: 11                             ║
║  Findings:   sast-findings/                             ║
║  Index:      sast-findings/index.json                   ║
╚══════════════════════════════════════════════════════════╝

Top findings:
  SF01 [CRITICAL] SQL Injection — POST /api/users — userRepo.js:23
  SF02 [CRITICAL] Command Injection — POST /api/export — exportService.js:67
  SF03 [HIGH] Broken Access Control — GET /api/users/:id — userController.js:34

Next steps:
  • Run /engage-sast <name> --correlate    to map against DAST findings
  • Run /engage-hunt <name>                DAST targets auto-injected
```
