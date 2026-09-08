# Enforcement and identity

The gate lives on the developer's machine. It is installed once, by IT on company devices or by the developer
with the installer for their operating system, and from then on every `git commit` and `git push` on that machine
passes through it, from any IDE or terminal.

## How the installed gate enforces

| Mechanism | What it does |
|---|---|
| Global git hooks (`core.hooksPath`) | `commit-msg` reviews the staged change with the intent and skip trailers from the message; `pre-push` reviews the commits new to the remote for each branch. Repository-local hooks still run; the gate chains to them. |
| Fail closed | If the engine, policy or model is unavailable the commit is blocked (set `SDLC_GATE_LOCAL_FAIL_OPEN=1` only for temporary offline work; managed installs ignore it). |
| Verified identity required | The hooks refuse to commit until the developer has signed in once with the Microsoft work account (`sdlc-gate identity login`). |
| Attestation | Every commit that passed gets an `SDLC-Gate-Client: pass v<version> <verified e-mail> <time>` trailer, so the history shows who was gated and when. Commits without it were made outside the gate. |
| Metrics | Every run (pass, fail, skip) is sent to the central repository from the developer's machine with their own GitHub credential and appears on the scoreboard under their verified e-mail. |
| Skills and policy refresh | The client pulls the current skills and `gate.config.yaml` from this repository at most once a day, so a policy change reaches everyone without reinstalling. |

## Managed install (recommended for company devices)

`client/managed/install-managed.ps1` (Windows) and `client/managed/install-managed.sh` (macOS, Linux, WSL) are
run once as administrator by IT (Intune, Jamf, SCCM, Ansible). They install the engine, hooks and policy in a
location standard users cannot modify, set the hooks path in the **system** git configuration, install a `git`
shim that removes `--no-verify` and any attempt to override the hooks path, refresh daily as root/SYSTEM, and
switch the hooks to managed mode (fail closed, identity required). Developers then run only:

```bash
sdlc-gate identity login     # one-time Microsoft sign-in
sdlc-gate configure          # one-time: store the LiteLLM key from the platform team
```

## Self-service install (any machine)

`client/install.cmd` (Windows), `client/install.command` (macOS) or `client/install.sh` (Linux, WSL) install the
same gate for the current user and run the two one-time steps interactively.

## What this does and does not guarantee

- A standard user on a managed device cannot disable the gate: the files, the git configuration, the shim and
  the PATH entry are administrator-owned.
- A local administrator, or a developer on an unmanaged personal machine, can uninstall it. Their commits will
  then carry no attestation trailer and their runs will stop appearing in the metrics, which is visible to
  management per developer on the scoreboard ("client attested" share).
- Anything that is not a git commit or push on a gated machine (web edits on GitHub, a CI bot, a container
  without the client) is not reviewed. If the organisation later wants a server-side backstop, this repository's
  reusable workflow (`.github/workflows/sdlc-gate.yml`) can be required on selected repositories; that is a
  separate decision and not part of the roll-out.

## Verified identity

### What we need

Every gate run should be attributable to a real person by their corporate e-mail (`firstname.lastname@og1o.in`),
not to whatever `git config user.email` happens to say.

### How it works

1. `sdlc-gate identity login` starts a Microsoft Entra ID **device-code sign-in**. The developer's browser opens
   the Microsoft sign-in page; because Outlook, Teams and the browser already share that Microsoft session, the
   step is normally one click ("Continue as arijit.aich@og1o.in"). The developer sees exactly what is being
   requested (`openid profile email`) and consents.
2. Microsoft returns an ID token whose `preferred_username` claim is the verified UPN. The engine checks the
   audience, issuer, tenant, expiry and allowed domains, then stores the identity in `~/.sdlc-gate/identity.json`
   (user-only permissions).
3. The verified e-mail and display name are written to the developer's global git identity, so all commits are
   authored with the corporate address.
4. Every gate run appends the `SDLC-Gate-Client` trailer with that e-mail and sends a metrics event carrying it.

Nothing is read from Outlook, Teams or the browser. The gate only receives what Microsoft's identity service
returns after the developer signs in. That is the same mechanism the Azure CLI, GitHub CLI and VS Code use, it
works with MFA and Conditional Access, and it is auditable in Entra sign-in logs.

### Platform set-up

1. In Entra ID register an application "SDLC Gate client" (public client / native). Enable *Allow public client
   flows*. Note the **Directory (tenant) ID** and **Application (client) ID**.
2. Put them in `gate.config.yaml`:

   ```yaml
   identity:
     provider: entra
     tenant: <tenant-guid>
     client_id: <application-guid>
     allowed_domains: [og1o.in]
     required: true
   ```

## Metrics from the client

After each run the hook calls `sdlc-gate emit-metrics --dispatch`, which sends a compact event to this
repository using the developer's existing GitHub credential (the GitHub CLI token or the git credential helper,
the same credential used to push code). Developers need write access to this repository, which they need anyway
to open skill challenges. Nothing is stored by the gate. If no credential is available the run still completes
and a warning is printed; the attestation trailer remains in the commit.
