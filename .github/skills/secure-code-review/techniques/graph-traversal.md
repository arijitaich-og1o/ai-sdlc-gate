---
name: graph-traversal
description: "GraphRAG-inspired graph-accelerated SAST (--graph flag). Shallow entity extraction → import-graph community detection → hierarchical module summaries → targeted deep-read only on source→sink paths. 40-60% token reduction vs full scan on modular codebases."
---

# Graph-Accelerated SAST (`--graph` mode)

Inspired by Microsoft GraphRAG (arxiv:2404.16130): precompute a code knowledge graph,
detect communities, then deep-read ONLY nodes on user-input → security-sink paths.
Unrelated subtrees are never fully read — this is where the token savings come from.

---

## When to Use

- Codebases with >50 source files (full scan becomes expensive)
- PR reviews where only changed modules need re-analysis (combine with `--diff`)
- Repeat scans (cached graph.json skips re-extraction of unchanged files)

Token savings vs full scan: **40–60%** for codebases with clear module boundaries;
less benefit on monolithic single-file codebases.

---

## Phase G1 — Shallow Entity Extraction

**Goal:** build the call/import graph without reading full file bodies.

For every file in the scanned path (ALL files, not just P0-P1), read only:
- Import/require/from statements (top of file)
- Exported function/class signatures (name + first-line signature only)
- Any line containing `req.body`, `req.query`, `req.params`, `request.form`, `request.json`,
  `event.body` (marks as a **source node**)
- Any line containing `db.query`, `db.exec`, `cursor.execute`, `os.system`, `exec(`,
  `subprocess`, `child_process`, `axios.`, `fetch(`, `http.get` (marks as a **sink node**)

Emit one JSON object per file (hold in memory, not written to disk yet):
```json
{
  "file": "src/services/paymentService.js",
  "imports": ["../db/client", "../utils/validator", "stripe"],
  "exports": ["createCharge", "refund", "getTransaction"],
  "is_source": false,
  "is_sink": true,
  "sink_types": ["db.query", "axios.post"],
  "loc_approx": 340
}
```

Token cost: ~30-60 tokens per file (signatures + imports only). For a 200-file codebase:
~8,000 tokens for extraction vs ~200,000 for full read.

---

## Phase G2 — Community Detection

**Goal:** group files into functional clusters using the import graph. Simulates the
Leiden algorithm using connected-component BFS over the import graph.

### Step 1 — Build adjacency list

From the Phase G1 nodes, create directed edges:
`A imports B` → edge `A → B` (A depends on B)

### Step 2 — Find entry points

Files with **zero reverse imports** (nothing imports them) = entry points.
These are typically route handlers, Lambda handlers, CLI entry points.
Each entry point is the root of a community traversal.

### Step 3 — BFS per entry point

Starting from each entry point, BFS through import edges to cluster co-dependent files.
Files reachable from the same entry point = same community.

Apply split heuristic: if a community has >15 files, re-cluster by inspecting which
files share the most edges within the group (dense subgraph = sub-community).

### Step 4 — Label communities

For each community, determine:
```json
{
  "id": "payments",
  "entry_point": "src/routes/payment.js",
  "files": ["src/routes/payment.js", "src/services/paymentService.js", "src/db/paymentRepo.js"],
  "has_source": true,
  "has_sink": true,
  "sink_types": ["db.query", "axios.post (Stripe)"],
  "priority": "CRITICAL"
}
```

Priority rules:
| has_source | has_sink | Priority |
|---|---|---|
| true | true | **CRITICAL** — data flows from user input to sink |
| true | false | **HIGH** — processes user input (may pass to sink via community boundary) |
| false | true | **MEDIUM** — contains sinks (may receive tainted data from other community) |
| false | false | **SKIP** — no user input, no security-relevant sinks |

---

## Phase G3 — Hierarchical Community Summaries

**Goal:** write a 2-3 sentence summary per community that can be loaded cheaply on
future scans instead of re-running Phase G1+G2.

For each community, write:
```json
{
  "id": "auth",
  "summary": "Handles user login, session creation, JWT issuance, and password reset. Imports bcrypt and jsonwebtoken. Entry via POST /auth/login and POST /auth/reset.",
  "security_signals": ["jwt.sign without exp", "Math.random() in token generation (L89)"],
  "priority": "CRITICAL",
  "file_count": 6,
  "files": [...]
}
```

Save to `sast-findings/graph.json` after Phase G3 completes:
```json
{
  "generated": "<ISO timestamp>",
  "scanned_path": "<path>",
  "total_files": 200,
  "communities": [...],
  "skipped_files": 87,
  "skip_reason": "no source/sink path"
}
```

**On subsequent `--graph` runs:** load `graph.json` → compare file modification times →
re-derive only files newer than `generated` timestamp → merge into existing graph.
This makes repeat scans ~80% cheaper (graph derivation cost amortized).

---

## Phase G4 — Source→Sink Path Traversal

**Goal:** within CRITICAL and HIGH communities, trace exact data-flow paths using the
call graph — load only files on the path.

For each CRITICAL community:
1. Find the source files (is_source=true) and sink files (is_sink=true) within the community
2. Trace through the import graph: source file → which of its imports eventually reach a sink?
3. This defines the **on-path file set** — only these files get full deep-read

Example traversal log:
```
source: src/routes/payment.js  (req.body → amount)
  → imports src/services/paymentService.js
      → imports src/db/paymentRepo.js  [SINK: db.query]
  → imports src/utils/validator.js     [no sink — skip]

On-path files: payment.js, paymentService.js, paymentRepo.js  (3 of 8 community files)
Skipped: validator.js, logger.js, constants.js, types.js, helpers.js
```

This narrows the deep-read from the full community to only the 3 files that actually
form the data-flow path.

---

## Phase G5 — Targeted Deep Analysis

**CRITICAL priority communities (has_source + has_sink):**
- Deep-read all on-path files from Phase G4
- Run full SAST categories: injection, auth, SSRF, crypto, logic
- Data-flow field in each finding includes graph path: `[req.body@route:14 → service:28 → db.query@repo:67]`

**HIGH priority communities (has_source, no local sink):**
- Deep-read source files + any files they directly import
- Check for: data passed to cross-community boundary functions, sensitive data stored in globals,
  input validation logic (may protect CRITICAL communities downstream)

**MEDIUM priority communities (has_sink, no local source):**
- Shallow check of sink files only: look for hardcoded credentials in connection strings,
  insecure SQL patterns, unsafe deserialization
- Do NOT fully trace data flow (source is in another community — covered by that community's scan)

**SKIP communities:**
- Read only first 30 lines of each file
- Check for: hardcoded secrets (pattern match only — no data flow tracing)
- This ensures we catch `API_KEY = "sk_live_..."` even in utility files

---

## Output Additions (graph mode)

Prepend to the standard finding output:
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  GRAPH-ACCELERATED SCAN
  Communities detected: 12  |  CRITICAL: 3  |  HIGH: 2  |  SKIP: 7
  Files deep-read: 28 / 87 total  (68% skipped)
  Graph cached: sast-findings/graph.json
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

Add graph path to each finding's data-flow:
```
  Data flow (graph path):
    req.body.amount [src/routes/payment.js:34]
    → createCharge() [src/services/paymentService.js:89]
    → db.query(sql) [src/db/paymentRepo.js:12]  ← SINK
```

---

## Token Budget (reference)

| Phase | What runs | Approx tokens (200-file codebase) |
|---|---|---|
| G1 Extraction | Shallow read all 200 files | ~10,000 |
| G2-G3 Community detection | Reasoning only, no more file reads | ~2,000 |
| G4 Path traversal | Reasoning on graph JSON | ~1,000 |
| G5 Deep read (CRITICAL/HIGH only) | Full read of 28 files | ~56,000 |
| **Total (graph mode)** | | **~69,000** |
| Standard scan (no graph) | Full read of all 200 files | ~180,000 |
| **Savings** | | **~62%** |

Savings scale with codebase modularity — a well-structured codebase with clear
separation between auth, data, and utility layers yields the highest savings.

---

## Limitations

- **Monolithic files**: a single 5,000-line file with all routes, business logic, and DB calls
  forms one community with no skip opportunity. Graph mode = same cost as standard mode.
- **Dynamic imports**: `require(dynamicVar)` creates edges Claude cannot statically trace.
  Flag these as confidence:LOW and include the file in MEDIUM-priority manual review.
- **Indirect data flow via globals**: global state mutations (e.g., `app.locals.user = req.user`)
  are cross-file data flows not captured by import edges. Treat files that write to app-level
  globals as pseudo-source nodes.
- **Polyglot codebases**: graph traversal follows import semantics of the primary language.
  Secondary-language files (e.g., Python scripts in a JS repo) are treated as isolated nodes.
