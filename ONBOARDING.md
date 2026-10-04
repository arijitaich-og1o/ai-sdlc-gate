# AI SDLC Gate — Developer Onboarding

An AI code-review gate that runs **on your machine**. Before every push it reviews your changes across the SDLC
phases (design, development, testing, security…) and blocks on serious issues. It signs you in with your
**Microsoft work account** — there are **no API keys** to get, store, or leak, and nothing to set up in the cloud.

## Prerequisites
- **Git** and **Python 3.10+** installed and on PATH.
  - Windows: [Git for Windows](https://git-scm.com/download/win) + [Python](https://www.python.org/downloads/) (tick *Add python.exe to PATH*).
- A **@og1o.in** Microsoft work account.
- **Read access** to the gate repository. If the clone step fails with a permission error, ask the platform owner (Arijit) to grant read access.

## Install

**Windows (PowerShell):**
```powershell
git clone https://github.com/arijitaich-og1o/ai-sdlc-gate "$env:USERPROFILE\.ai-sdlc-gate\repo"; & "$env:USERPROFILE\.ai-sdlc-gate\repo\client\install.ps1"
```

**WSL / macOS / Linux (bash):**
```bash
git clone https://github.com/arijitaich-og1o/ai-sdlc-gate ~/.ai-sdlc-gate/repo && bash ~/.ai-sdlc-gate/repo/client/install.sh
```

The installer will:
1. install the engine into a private environment (no changes to your system Python),
2. wire global git hooks — they run in every terminal and IDE,
3. prompt a **one-time Microsoft sign-in** (a browser opens; choose your `@og1o.in` account),
4. connect to the organisation review endpoint. **No cloud credential is stored on your machine.**

> Using **WSL** for your git work? Install in **both** Windows *and* your WSL distro (run the bash command inside WSL) — they are separate environments.

## Daily use
Work as normal. On `git push`, the gate reviews the changes you're pushing and either **passes** or **blocks** with specific findings to fix. If a phase genuinely can't be satisfied right now, add these trailers to your commit message or PR description and push again:
```
SDLC-Skip: <phase numbers, e.g. 5>
SDLC-Skip-Reason: <at least 40 characters explaining why, with a ticket reference>
```
Secrets, hard-coded credentials and known-vulnerable dependencies can **never** be skipped.

## Corporate network / VPN
Handled automatically — the gate trusts your organisation's TLS-inspection certificate via the operating-system
trust store, so it works on the corporate network out of the box. If you ever see a certificate error, point it at
your corporate CA file: set the environment variable `AI_SDLC_GATE_CA_BUNDLE` to that `.pem` and retry.

## Troubleshooting
| Symptom | Fix |
|---|---|
| `could not clone` / permission denied | You need **read access** to the repo — ask the platform owner. |
| `Python 3.10+ is required` | Install Python and re-open your terminal. |
| Sign-in didn't finish | Run `ai-sdlc-gate identity login` again. |
| `review engine is not set up` | Run `ai-sdlc-gate configure`. |
| Certificate error on a corporate laptop | Set `AI_SDLC_GATE_CA_BUNDLE` to your corporate root CA `.pem`. |

Questions or access requests: contact the platform owner (Arijit).
