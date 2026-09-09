# Enforcement and identity

The gate lives on the developer's machine. It is installed once, by IT on company devices or by the developer
with the installer for their operating system, and from then on every `git commit` and `git push` on that machine
passes through it, from any IDE or terminal.

## How the installed gate enforces

| Mechanism | What it does |
|---|---|
| Global git hooks (`core.hooksPath`) | `commit-msg` reviews the staged change with the intent and skip trailers from the message; `pre-push` reviews the commits new to the remote for each branch. Repository-local hooks still run; the gate chains to them. |
| Fail closed | If the engine, policy or model is unavailable the commit is blocked (set `AI_SDLC_GATE_LOCAL_FAIL_OPEN=1` only for temporary offline work; managed installs ignore it). |
| Verified identity required | The hooks refuse to commit until the developer has signed in once with the Microsoft work account (`ai-sdlc-gate identity login`). |
| Attestation | Every commit that passed gets an `AI-SDLC-Gate-Client: pass v<version> <verified e-mail> <time>` trailer, so the history shows who was gated and when. Commits without it were made outside the gate. |
| Metrics | Every run (pass, fail, skip) is sent to the central repository from the developer's machine with their own GitHub credential and appears on the scoreboard under their verified e-mail. |
| Skills and policy refresh | The client pulls the current skills and `gate.config.yaml` from this repository at most once a day, so a policy change reaches everyone without reinstalling. |

## Managed install (recommended for company devices)

`client/managed/install-managed.ps1` (Windows) and `client/managed/install-managed.sh` (macOS, Linux, WSL) are
run once as administrator by IT (Intune, Jamf, SCCM, Ansible). They install the engine, hooks and policy in a
location standard users cannot modify, set the hooks path in the **system** git configuration, install a `git`
shim that removes `--no-verify` and any attempt to override the hooks path, refresh daily as root/SYSTEM, and
switch the hooks to managed mode (fail closed, identity required). Developers then run only:

```bash
ai-sdlc-gate configure          # one-time: fetches the review configuration from the central repository's secrets
ai-sdlc-gate identity login     # one-time Microsoft sign-in
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
  reusable workflow (`.github/workflows/ai-sdlc-gate.yml`) can be required on selected repositories; that is a
  separate decision and not part of the roll-out.

## Verified identity

### What we need

Every gate run should be attributable to a real person by their corporate e-mail (`firstname.lastname@og1o.in`),
not to whatever `git config user.email` happens to say.

### How it works

1. `ai-sdlc-gate identity login` starts a Microsoft Entra ID **browser sign-in** (authorization code with PKCE and
   a loopback redirect on `localhost`). The developer's browser opens the Microsoft account picker; because Outlook,
   Teams and the browser already share that Microsoft session, the step is one click. Nothing has to be typed. On
   headless machines `--device-code` uses the device-code flow instead. The developer sees exactly what is being
   requested (`openid profile email`) and consents.
2. Microsoft returns an ID token whose `preferred_username` claim is the verified UPN. The engine checks the
   audience, issuer, tenant, expiry and allowed domains, then stores the identity in `~/.ai-sdlc-gate/identity.json`
   (user-only permissions).
3. The verified e-mail and display name are written to the developer's global git identity, so all commits are
   authored with the corporate address.
4. Every gate run appends the `AI-SDLC-Gate-Client` trailer with that e-mail and sends a metrics event carrying it.

Nothing is read from Outlook, Teams or the browser. The gate only receives what Microsoft's identity service
returns after the developer signs in. That is the same mechanism the Azure CLI, GitHub CLI and VS Code use, it
works with MFA and Conditional Access, and it is auditable in Entra sign-in logs.

### Platform set-up

Out of the box the sign-in uses Microsoft's public Azure CLI client id, restricted to `og1o.in` accounts. Tenants
whose Conditional Access policy blocks that application (error **AADSTS53003**) need a dedicated registration, which
is recommended before the roll-out in any case:

1. In Entra ID register an application "AI SDLC Gate client": *Accounts in this organizational directory only*,
   platform **Mobile and desktop applications** with redirect URI `http://localhost`, and *Allow public client flows*
   = Yes. API permissions: Microsoft Graph delegated `openid`, `profile`, `email`, `User.Read` (grant admin consent).
   Exclude nothing; the app needs no roles. Note the **Directory (tenant) ID** and **Application (client) ID**.
2. Put them in `gate.config.yaml`:

   ```yaml
   identity:
     provider: entra
     tenant: <tenant-guid>
     client_id: <application-guid>
     allowed_domains: [og1o.in]
     required: true
   ```

## The review configuration: who sees what

The developer's machine talks to the organisation's model gateway directly, so the machine must hold a usable key.
A developer who is determined enough can extract a key their own processes use; no client-side technique changes
that. The design therefore limits what is exposed and to whom:

| Control | How |
|---|---|
| **Nothing readable on disk** | Endpoint, key and model names are stored as one record in the OS credential store: Windows Credential Manager (DPAPI, bound to the signed-in user), macOS Keychain, Linux Secret Service. `~/.ai-sdlc-gate` contains no configuration at all. Headless Linux without a secret service falls back to a file encrypted with a random key kept in a user-only file, and the client says so. |
| **Not in the repository** | The endpoint and the model names live only in the repository secrets (`LITELLM_BASE_URL`, `LITELLM_API_KEY`, `LITELLM_MODELS`). Policy, skills, workflows and documentation never name them. Developers cannot learn which gateway or which models are used by reading the repository or their own installation folder. |
| **Encrypted in transit** | The broker encrypts the record to an RSA key pair generated on the requesting machine; the artifact expires after one day; only people with access to this repository can request it. |
| **Spend limit and rotation** | The shared key should be a gateway virtual key with a spend limit. Rotate it by updating the secret; clients pick the new value up with `ai-sdlc-gate configure`. Gateway logs attribute usage to the key, not to a person; per-person attribution comes from the gate's own metrics. |
| **Never logged** | The engine never prints the key or the endpoint; error messages are reduced to status codes. |

## Metrics from the client

After each run the hook calls `ai-sdlc-gate emit-metrics --dispatch`, which sends a compact event to this
repository using the developer's existing GitHub credential (the GitHub CLI token or the git credential helper,
the same credential used to push code). The gate never reads or stores that credential. Developers need write access to this repository, which they need anyway
to open skill challenges. Nothing is stored by the gate. If no credential is available the run still completes
and a warning is printed; the attestation trailer remains in the commit.
