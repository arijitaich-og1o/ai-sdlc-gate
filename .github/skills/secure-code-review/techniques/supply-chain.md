---
name: supply-chain
description: "Supply chain security analysis: dependency manifest review, version pinning, typosquatting detection, lifecycle script inspection, and known-compromised package version checking. Loaded by --audit and --supply-chain flags."
---

# supply-chain

Loaded by `/secure-code-review` when `--audit` is passed (always) or when dependency manifest
files are found during standard scanning.

**Purpose:** Identify malicious, compromised, or dangerously unpinned dependencies before
`npm install` / `pip install` / `go mod download` executes them.

---

## Step 1 — Locate and Read Manifests

Find and read ALL of the following that exist in the scanned path:

| Ecosystem | Primary manifest | Lock file |
|---|---|---|
| Node.js | `package.json` | `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml` |
| Python | `requirements.txt`, `Pipfile`, `pyproject.toml` | `Pipfile.lock`, `poetry.lock` |
| Go | `go.mod` | `go.sum` |
| Rust | `Cargo.toml` | `Cargo.lock` |
| Java | `pom.xml`, `build.gradle`, `build.gradle.kts` | (Maven/Gradle resolve at build) |
| PHP | `composer.json` | `composer.lock` |
| Ruby | `Gemfile` | `Gemfile.lock` |
| .NET | `*.csproj`, `packages.config` | (NuGet lock files) |

---

## Step 2 — Version Pinning Audit

Flag any dependency without a pinned, exact version:

| Pattern | Risk | Flag as |
|---|---|---|
| `"lodash": "*"` | Any version including compromised ones | HIGH |
| `"lodash": "latest"` | Resolves to whatever is current at install time | HIGH |
| `"lodash": ">=4.0.0"` | Unbounded upper range | MEDIUM |
| `"lodash": "^4.17.0"` | Allows minor/patch updates (semver caret) | LOW |
| `"lodash": "~4.17.0"` | Allows patch updates only | INFO |
| `"lodash": "4.17.21"` | Exact pin — safe | OK |

**Lock file check:** If `package.json`/`pyproject.toml` exists but NO lock file exists → flag as MEDIUM.
Lock files pin the entire dependency tree including transitive deps.

---

## Step 3 — Typosquatting Detection

Compare every package name against common legitimate packages. Flag close matches:

**High-value targets (commonly typosquatted):**

| Legitimate | Common typosquats to flag |
|---|---|
| `lodash` | `lodahs`, `loadsh`, `lodash-js`, `1odash` |
| `requests` (Python) | `reqests`, `request`, `python-requests`, `requestss` |
| `express` | `expres`, `expresss`, `node-express` |
| `react` | `recat`, `raect`, `react-js` |
| `numpy` | `numply`, `numppy`, `nupy` |
| `boto3` | `bot03`, `boto-3`, `bto3` |
| `urllib3` | `urlib3`, `urllib-3`, `urlib` |
| `setuptools` | `setuptool`, `setup-tools`, `seuptools` |
| `pillow` | `pillo`, `pilow`, `pillow-imaging` |
| `axios` | `axois`, `axio`, `node-axios` |
| `moment` | `mement`, `momentjs`, `moment-js` |
| `webpack` | `webpak`, `web-pack`, `webpackk` |

**Detection heuristic:** Levenshtein distance ≤ 2 from a top-1000 package name + package published <90 days ago = HIGH suspicion.

Also flag: packages with names that add common prefixes/suffixes to well-known packages:
- `python-<legit>`, `<legit>-python`, `node-<legit>`, `<legit>-js`, `<legit>2`

---

## Step 4 — Lifecycle Script Inspection

**Highest risk — run automatically on install.**

For Node.js `package.json`, read `scripts` field. Flag ANY of these that contain network calls, file writes outside the package, or obfuscated code:

```json
{
  "scripts": {
    "preinstall":  "...",   // ← runs BEFORE install
    "install":     "...",   // ← runs during install
    "postinstall": "...",   // ← runs AFTER install
    "prepare":     "...",   // ← runs on npm install and publish
    "preuninstall":"...",   // ← runs on npm uninstall
    "prepack":     "..."    // ← runs before npm publish
  }
}
```

**Legitimate postinstall patterns (do not flag):**
- Compiling native bindings: `node-gyp rebuild`, `node-pre-gyp install`
- Building TypeScript: `tsc`, `rollup`, `esbuild`
- Generating code: `protoc`, `graphql-codegen`
- Copying files within package directory

**Flag as CRITICAL:**
- Any `curl`, `wget`, `fetch`, `http.get` in lifecycle scripts
- Writing to paths outside `node_modules/<this-package>/`
- `eval` or `exec` of downloaded content
- Reading `process.env` for non-obvious variables then sending them anywhere

**For Python (`setup.py`, `setup.cfg`):**
- `cmdclass` overriding `install` command with network calls
- `subprocess.run()` / `os.system()` in `setup.py` outside of native extension compilation

---

## Step 5 — Known-Compromised Version Database

Check every pinned dependency version against this list. Flag matches as CRITICAL:

### Node.js / npm

| Package | Compromised version(s) | Incident |
|---|---|---|
| `event-stream` | `3.3.6` | Malicious maintainer added Bitcoin wallet stealer |
| `ua-parser-js` | `0.7.29`, `0.7.30`, `0.7.31`, `1.0.1` | Account hijack; crypto miner + credential stealer |
| `colors` | `1.4.1` (and `1.4.2`) | Maintainer sabotage; infinite loop (protest) |
| `faker` | `6.6.6` | Maintainer sabotage; output replaced with `null` |
| `node-ipc` | `10.1.1`, `10.1.2`, `11.1.0` | Geopolitical protest; file deletion payload |
| `es5-ext` | `0.10.63` | Anti-war message on Ukrainian IPs |
| `coa` | `2.0.3`, `2.0.4`, `2.1.3` | Account compromise; malware |
| `rc` | `1.2.9`, `1.3.9`, `2.3.9` | Account compromise; malware |
| `nightmare` | `3.0.2` (npm scope hijack) | Malware via dependency confusion |
| `flatmap-stream` | `0.1.1` | Delivered via event-stream incident |
| `@noblox.js/main` | multiple | Malware targeting Roblox developers |

### Python / PyPI

| Package | Compromised version(s) | Incident |
|---|---|---|
| `ctx` | `0.1.2` | Typosquat of `ctx`; credential exfiltration |
| `pygrata` | `0.1` | Malware; exfiltrates env vars |
| `loglib-modules` | `0.1` | Typosquat of `loglib`; steals credentials |
| `httpx-networkmanager` | `0.1` | Typosquat; malware |
| `noblesse` | `0.1–0.3` | Info stealer targeting Discord/browser tokens |
| `pytagora` | `0.1.3` | Reverse shell |
| `pytagora2` | `0.1.3` | Reverse shell |
| `request-plus` | `0.1.0` | Typosquat of `requests`; malware |
| `importantpackage` | multiple | Dependency confusion PoC / actual malware |
| `setup-tools` | `0.0.1` | Typosquat of `setuptools`; exfil |

### Ruby / RubyGems

| Package | Compromised version(s) | Incident |
|---|---|---|
| `rest-client` | `1.6.13`, `1.6.14`, `1.6.15` | Account compromise; credential stealer |
| `strong_password` | `0.0.7` | Malicious code inserted; exfil |
| `bootstrap-sass` | `3.2.0.3` | Backdoor added |

### General Indicators (flag as HIGH for investigation)

- Package published within the last 30 days with a sudden download spike (>10,000/week)
- Package version that skips many minor versions (e.g., `1.0.0` → `1.9.9` with no intermediate releases)
- Package where the latest version was published by a DIFFERENT npm/PyPI username than all prior versions (possible account takeover)

---

## Step 6 — Dependency Ratio Heuristic

Flag for manual review when:

- Package has <200 lines of own code but declares >30 direct dependencies (shell company package)
- Package's stated functionality (e.g., "string formatting") doesn't justify importing `child_process`, `net`, `http`, `crypto` as dependencies

---

## Output Format

For each finding, use the developer-friendly format:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[CRITICAL] Known Compromised Package  ·  package.json
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  ❌ NEVER use:
     "event-stream": "3.3.6"

  ✅ ALWAYS use:
     "event-stream": "3.3.4"  (last safe version)
     OR remove and use a maintained alternative

  Why: Version 3.3.6 was published by a malicious maintainer
       and contained a Bitcoin wallet stealer targeting
       Copay cryptocurrency wallets (Nov 2018).

  Test to add:
     Add event-stream@3.3.6 to your dependency scanner blocklist.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```
