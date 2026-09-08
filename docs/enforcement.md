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
sdlc-gate configure          # one-time: fetches the LiteLLM configuration from the central repository's secrets
sdlc-gate identity login     # one-time Microsoft sign-in
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

## LiteLLM keys: who holds what

The developer's machine calls LiteLLM directly, so it must hold a usable key. A developer can always extract a key
that their own processes use; no client-side trick changes that. What the design controls is the blast radius:

| Control | How |
|---|---|
| **Individual keys** | The key broker mints a *per-developer* LiteLLM virtual key with `LITELLM_ADMIN_KEY` (a secret that never leaves the workflow). The key is tagged with the developer's GitHub login and `sdlc-gate`. |
| **Spend cap** | `llm.developer_keys.max_budget_usd` per `budget_duration` (default 25 USD / 30 days). LiteLLM refuses calls beyond it. |
| **Model allow-list** | Only the gate's review, judge and fallback models. The key is useless for anything else. |
| **Rate limit and expiry** | `rpm_limit` (default 60) and `duration` (default 90 days). Clients re-run `sdlc-gate configure` when a key stops working. |
| **Revocation** | One developer's key can be deleted in LiteLLM (`/key/delete`, or the UI, filter by tag `sdlc-gate`) without affecting anyone else. |
| **Attribution** | LiteLLM spend logs show the alias `sdlc-gate/<login>/<request>`, so misuse is traceable to a person. |
| **No plaintext on disk** | The client stores the key in the OS credential store: Windows Credential Manager, macOS Keychain, Linux Secret Service. There is nothing to read in `~/.sdlc-gate`. On headless Linux without a secret service it falls back to a user-only `env` file and says so. |
| **Transport** | The broker encrypts the key to an RSA key pair generated by the requesting client; the artifact is deleted after one day. |

Without `LITELLM_ADMIN_KEY` the broker falls back to handing out the shared `LITELLM_API_KEY` and warns in every run.
That is acceptable for a pilot with a spend-limited key, not for the organisation-wide roll-out.

Obtaining the admin key: in LiteLLM, create a key with the `proxy_admin` role (or use the master key) and store it as
the `LITELLM_ADMIN_KEY` secret of this repository only.

## Metrics from the client

After each run the hook calls `sdlc-gate emit-metrics --dispatch`, which sends a compact event to this
repository using the developer's existing GitHub credential (the GitHub CLI token or the git credential helper,
the same credential used to push code). The gate never reads or stores that credential. Developers need write access to this repository, which they need anyway
to open skill challenges. Nothing is stored by the gate. If no credential is available the run still completes
and a warning is printed; the attestation trailer remains in the commit.
