---
name: dataflow
description: "Data flow tracing methodology for secure-code-review — Quick (single-file), Standard (cross-file single hop), and Thorough (full call chain) depth profiles. Loaded when tracing is needed during Phase 1 analysis."
---

# Phase 2 — Data Flow Tracing

## Quick (single-file only)

Within each file: does user input reach a sink IN THE SAME FILE without sanitization?

```
SF01 [HIGH] SQL Injection — src/controllers/userController.js:47
  Sink: db.query(`SELECT * FROM users WHERE name = '${name}'`)
  Source: req.body.name (same file, line 12)
  Confidence: HIGH (direct, single-file flow)
```

## Standard (cross-file, one hop)

Trace one level of function calls. If controller calls a service with user input, check that service for sinks.

If `--graph` was passed: the G4 phase in `graph-traversal.md` has already computed source→sink paths. Use the on-path file set from Phase G4 — no additional traversal needed; deep-read only those files.
Otherwise: use Read/Grep to trace manually.

```
SF01 [CRITICAL] SQL Injection — src/services/userService.js:47
  Sink: db.query(`SELECT * FROM users WHERE name = '${data.name}'`)
  Data flow:
    req.body.name → userController.create():14
    → userService.save(data):47 (SINK)
  Route: POST /api/users
  Confidence: HIGH (cross-file, one hop)
```

## Thorough (full call chain)

Trace the complete path from HTTP entry point through ALL function calls to the sink.
Read every file in the call chain. Note any sanitization encountered and whether it addresses the specific sink type.

If `--graph` passed: multi-hop paths are already resolved by the G4 traversal phase in `graph-traversal.md`. Read the on-path file set directly — the graph pipeline has already eliminated off-path files.

```
SF01 [CRITICAL] SQL Injection — src/repositories/userRepo.js:23
  Sink: db.query(`SELECT * FROM users WHERE name = '${filters.name}'`)
  Data flow:
    req.body.name → userController.create():14
    → validateInput(data):28 — PASSES (length/type check, NOT SQL-safe)
    → userService.save(validated):45
    → userRepo.findByFilters(filters):23 (SINK)
  Route: POST /api/users
  Framework: Express
  Confidence: HIGH (full chain traced; validateInput does not parameterize SQL)
```

## Sanitization Assessment

When a sanitization function is encountered mid-chain, evaluate:
- Does it address THIS specific sink type? (length check ≠ SQL-safe)
- Is it applied BEFORE the sink or after the source?
- Could it be bypassed? (encoding bypass, second-decode, etc.)

If sanitization is present but insufficient → confidence:MEDIUM, explain gap.
If sanitization status is unknown (code not yet read) → confidence:LOW.
