# Enforcement and identity

## The honest model: three layers

| Layer | What it does | Can a developer bypass it? |
|---|---|---|
| **1. Organisation gate + ruleset** ([org-gate.yml](../.github/workflows/org-gate.yml), [org-ruleset.json](../templates/org-ruleset.json)) | This repository discovers every open pull request and push across the organisation, reviews it here and posts the `SDLC Gate` commit status. The ruleset requires that status with no bypass actors. Nothing lives in the target repositories, so there is nothing to delete or edit. | **No.** Not by editing files, not by removing workflows (there are none to remove), not by force-pushing. This is the guarantee. |
| **2. Managed client** (`client/managed/`) | Installed by IT as administrator: system-level `core.hooksPath`, a `git` shim that strips `--no-verify` and hook-path overrides, root/Administrator-owned hooks, daily refresh, fail-closed mode, identity required. | Not without administrator rights. Standard users cannot edit the config, hooks, shim or PATH entry. Local administrators can. |
| **3. Attestation + metrics** | The local hook stamps every commit with `SDLC-Gate-Client: pass v1.0.0 <verified e-mail> <time>`. The server-side gate records whether a commit carries a valid attestation and who made it. | Bypassing layer 2 leaves commits without an attestation, which shows up per developer on the scoreboard. Forging the trailer is possible but is itself a policy violation that the gate flags as `gate-manipulation` when detected. |

### Why not "the kernel"

A kernel module cannot understand git; git hooks are a userland convention and any process with the user's
privileges can invoke git in a way that ignores them (a different git binary, a container, a different machine).
The only place where every path converges and where the developer has no privileges is the server: GitHub
accepts the merge or it does not. That is why layer 1 exists and why it is the only layer described as
non-bypassable. Layers 2 and 3 make bypass inconvenient and visible, which is what client-side controls can
realistically do.

## Verified identity

### What we need

Every gate run should be attributable to a real person by their corporate e-mail (`firstname.lastname@og1o.in`),
not to whatever `git config user.email` says or to a GitHub handle that may not map to a person.

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
4. Every local gate run appends the `SDLC-Gate-Client` trailer with that e-mail. The server-side gate records
   `developer_email` and `client_attested` in the metrics event; the dashboard and README scoreboard group by it.
5. In managed mode (`sdlc-gate.managed=true` in the system gitconfig) the hooks refuse to run a commit until an
   identity exists and fail closed if the model is unreachable.

Nothing is read from Outlook, Teams or the browser. The gate does not touch other applications' sessions or
data; it only receives what Microsoft's identity service returns after the developer signs in. That is the
same mechanism the Azure CLI, GitHub CLI and VS Code use, it works with MFA and Conditional Access, and it is
auditable in Entra sign-in logs.

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
     required: true      # local hooks refuse commits without a verified identity (managed mode always requires it)
   ```

3. Optionally enforce that GitHub accounts are SSO-linked (GitHub Enterprise SAML) so `actor` and
   `developer_email` can be cross-checked.

## Rolling out the managed client

- **Windows** (Intune/SCCM, runs as SYSTEM or Administrator):
  `powershell -ExecutionPolicy Bypass -File install-managed.ps1`
- **macOS** (Jamf, as root): `sudo bash install-managed.sh`
- **Linux / WSL** (Ansible, as root): `sudo bash install-managed.sh`

After installation every developer runs, once:

```bash
sdlc-gate identity login          # Entra sign-in, sets git user.email to the verified address
sdlc-gate configure               # stores the developer's LiteLLM key in ~/.sdlc-gate/env (0600)
```

The per-user installer (`client/install.sh` / `install.ps1`) does the same without administrator rights and is
suitable for contractors' unmanaged machines; there the server-side gate is the only enforcement.

## What the scoreboard shows about bypass

`Client attested` per developer: the share of their gate runs whose commits carried a valid local attestation.
A developer at 0 % has removed or never installed the local gate. That is not a failure of the gate (the server
still enforced), but it is a conversation.
