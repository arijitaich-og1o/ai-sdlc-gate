# Onboarding a developer

The server-side gate protects every repository whether or not you install anything. Installing the local hooks
gives you the same findings **before** you push, in any IDE, because they hook into git itself.

## Install

Linux, macOS, WSL, Git Bash:

```bash
curl -fsSL https://raw.githubusercontent.com/arijitaich-og1o/ai-sdlc-gate/main/client/install.sh | bash
```

Windows PowerShell:

```powershell
irm https://raw.githubusercontent.com/arijitaich-og1o/ai-sdlc-gate/main/client/install.ps1 | iex
```

The installer asks for your LiteLLM key (get it from the platform team; never commit it), stores it in
`~/.sdlc-gate/env` readable only by you, installs the `sdlc-gate` CLI, syncs the skills and policy to
`~/.sdlc-gate/repo`, and sets `git config --global core.hooksPath ~/.sdlc-gate/hooks`.

Requirements: git and Python 3.10+. Corporate proxies: set `HTTPS_PROXY` in your shell profile.

## What happens on your machine

- `git commit` → the `commit-msg` hook reviews the staged change with the intent and skip trailers from your
  message. Blocked commits print the report; fix or add trailers and commit again.
- `git push` → the `pre-push` hook reviews the commits new to the remote for each branch, with the intent
  derived from the branch name.
- Skills and policy refresh from the central repository at most once a day.
- If the model is unreachable the local hook lets the commit through with a warning (set
  `SDLC_GATE_LOCAL_FAIL_CLOSED=1` to block instead). The server-side gate always fails closed.
- Existing repository-local hooks in `.git/hooks/` still run; the global hooks chain to them.

## Working with findings

Each finding has a severity, category, file:line and a concrete recommendation. Fix `blocker` and `high`
findings; `medium` and below are advisory unless your repository sets a stricter threshold.

If a phase genuinely cannot be satisfied right now, waive it:

```
feat: move payment module

SDLC-Skip: 5
SDLC-Skip-Reason: Tests are being rewritten in PAY-1432; this commit only moves files and adds no logic.
```

Rules are in [skip-policy.md](skip-policy.md). Skips are visible to management.

## IDE notes

- **VS Code / IntelliJ / any IDE:** commits made from the IDE go through git and therefore through the hooks.
  IntelliJ shows hook output in the commit dialog; VS Code shows it in the Git output panel.
- **GUI clients that ship their own git** (GitHub Desktop, SourceTree) respect `core.hooksPath` as well.
- To run a review on demand: `sdlc-gate run --base origin/main --head HEAD` inside the repository.

## Uninstall

```bash
git config --global --unset core.hooksPath && rm -rf ~/.sdlc-gate && pip uninstall sdlc-gate
```
