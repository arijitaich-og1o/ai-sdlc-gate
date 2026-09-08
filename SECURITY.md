# Security

## Reporting

Report vulnerabilities in the gate itself (engine, workflows, hooks, policy) privately to the code owners listed
in `.github/CODEOWNERS`. Do not open a public issue for a bypass. Include the workflow run URL or the exact
command and input that reproduces the problem.

## What the gate protects

- **Integrity of enforcement.** Policy (`gate.config.yaml`), engine (`gate/`), workflows and benchmark can
  only change through code-owner-reviewed pull requests. Skills change only through the arbiter workflow, which
  itself is code-owned.
- **Secrets.** The LiteLLM admin key and the shared key exist only as GitHub secrets. Developers receive
  individual, budget-capped, model-restricted, expiring keys through the key broker, encrypted to their machine
  and kept in the OS credential store. The engine never logs keys.
- **Untrusted input.** Diffs, commit messages, PR bodies and candidate skills are data. They are fenced in
  explicit delimiters, the model is instructed to treat them as untrusted, model output is parsed as JSON and
  validated, and nothing from the model or the input is ever executed or interpolated into a shell.
- **Supply chain.** All third-party actions are pinned to full commit SHAs, verified by
  `scripts/check_pinned_actions.py` on every pull request. Dependabot keeps pins current. No
  `pull_request_target`, no `write-all`, every job declares least-privilege permissions.
- **Fail closed.** If the model, the proxy or the engine fails, the commit is blocked.

## Known limits

- On unmanaged machines, or with local administrator rights, the client can be removed. Such commits carry no
  attestation and vanish from the metrics, which is visible per developer.
- Fork pull requests to this repository do not receive secrets and therefore fail the self gate; work from branches.
- A model review is probabilistic. Deterministic pre-checks cover the highest-impact class (leaked secrets);
  everything else is best effort and improves through skill challenges.
- Metrics attribute runs to the GitHub account that triggered them, which for pushes is the pusher.

## Rotation

Rotate `LITELLM_API_KEY` and `SDLC_GATE_TOKEN` on a schedule and immediately if they appear anywhere outside
GitHub secrets. Keys are read at run time, so rotation needs no code change.
