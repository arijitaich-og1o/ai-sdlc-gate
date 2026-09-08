# Onboarding a developer

The gate is installed on your machine and hooks into git itself, so it applies to every repository and every IDE
you use. On company devices IT installs it; otherwise install it yourself.

## Install

- **Windows:** download and double-click [`client/install.cmd`](../client/install.cmd), or in PowerShell:
  `irm https://raw.githubusercontent.com/arijitaich-og1o/ai-sdlc-gate/main/client/install.ps1 | iex`
- **macOS:** download and double-click [`client/install.command`](../client/install.command), or in Terminal:
  `curl -fsSL https://raw.githubusercontent.com/arijitaich-og1o/ai-sdlc-gate/main/client/install.sh | bash`
- **Linux / WSL:** `curl -fsSL https://raw.githubusercontent.com/arijitaich-og1o/ai-sdlc-gate/main/client/install.sh | bash`

The installer installs the `ai-sdlc-gate` CLI, syncs the skills and policy to `~/.ai-sdlc-gate/repo`, sets
`git config --global core.hooksPath ~/.ai-sdlc-gate/hooks`, and then runs two one-time steps:

- `ai-sdlc-gate identity login` — a Microsoft sign-in opens in your browser (usually one click because you are
  already signed in for Outlook/Teams). Your verified corporate e-mail becomes your gate identity and your git
  `user.email`. Nothing is read from Outlook, Teams or the browser; only what Microsoft returns after you sign in.
- `ai-sdlc-gate configure` — obtains the review configuration from the central repository using your existing GitHub
  sign-in and keeps it in your operating system's credential store (Windows Credential Manager, macOS Keychain,
  Linux Secret Service). Nothing to type, nothing readable on disk.

On company-managed devices IT installs the gate system-wide (see [enforcement.md](enforcement.md)); you still run
the two one-time steps above.

Requirements: git, Python 3.10+, and a GitHub sign-in on the machine (GitHub CLI `gh auth login`, or the credential
helper that stores your login when you push). Corporate proxies: set `HTTPS_PROXY` in your shell profile.

## What happens on your machine

- `git commit` → the `commit-msg` hook reviews the staged change with the intent and skip trailers from your
  message. Blocked commits print the report; fix or add trailers and commit again. Passing commits get an
  `AI-SDLC-Gate-Client` trailer that records the local check and your verified e-mail.
- `git push` → the `pre-push` hook reviews the commits new to the remote for each branch, with the intent
  derived from the branch name.
- Skills and policy refresh from the central repository at most once a day.
- If the model is unreachable the commit is blocked (fail closed). For genuinely offline work on a self-installed
  client, `AI_SDLC_GATE_LOCAL_FAIL_OPEN=1` lets commits through with a warning; managed installs ignore it.
- Every run is recorded on the organisation scoreboard using your existing GitHub credential (GitHub CLI or the
  git credential helper). If none is available the run still completes and you see a note.
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

Rules are in [skip-policy.md](skip-policy.md). Skips are visible to management on the scoreboard.

## IDE notes

- **VS Code / IntelliJ / any IDE:** commits made from the IDE go through git and therefore through the hooks.
  IntelliJ shows hook output in the commit dialog; VS Code shows it in the Git output panel.
- **GUI clients that ship their own git** (GitHub Desktop, SourceTree) respect `core.hooksPath` as well.
- To run a review on demand: `ai-sdlc-gate run --base origin/main --head HEAD` inside the repository.

## Uninstall

Windows: run `client/uninstall.ps1`. macOS, Linux, WSL: `bash client/uninstall.sh`. Both remove the hooks, the
installation folder, the package and the credential-store entry.
