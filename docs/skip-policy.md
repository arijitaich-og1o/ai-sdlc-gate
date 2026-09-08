# Skip (waiver) policy

A skip lets a change pass a phase whose findings cannot be addressed right now. It never hides anything: the
review still runs, waived findings are shown in the report, and the skip is stored in the organisation metrics
with the developer, repository, phases and reason.

## How to request

Add both trailers to a commit message in the range or to the pull request description:

```
SDLC-Skip: 4, 5
SDLC-Skip-Reason: Legacy module is deleted in LEG-201 next sprint; the flagged code is being removed, not
  changed. Ticket has the risk acceptance from the product owner.
```

- Phases are numbers 1–7 (or `all`). The reason may continue on indented lines.
- The reason must be at least 40 characters (`skip.min_reason_chars`) and should reference a ticket.

## Rules (from `gate.config.yaml`)

| Rule | Default |
|---|---|
| Minimum reason length | 40 characters |
| Phases needing code-owner approval label `sdlc-skip-approved` | 6 (Deployment), 7 (Maintenance) |
| Phases that can never be skipped | none |
| Categories that are never waived, even in a skipped phase | `secret-exposure`, `hardcoded-credential`, `known-vulnerable-dependency`, `gate-manipulation` |
| Deterministic pre-check findings (secrets, private keys, `.env` files) | never waived |

An invalid skip request (short reason, missing label, unknown phase) is reported in the PR comment and the
gate proceeds as if no skip was requested.

## Approval label

For phases 6 and 7 a code owner of the repository adds the `sdlc-skip-approved` label to the pull request after
reading the reason. The label applies to that PR only. Re-running the gate after the label is added applies the
skip. Pushes without a PR cannot use approved skips; open a PR.

## What management sees

Per developer, repository and month: skips requested, skips granted, findings waived, alongside pass/flag/block
rates. A high skip rate is a conversation starter, not a verdict; the reasons are stored so patterns (e.g. a
test framework nobody can run) can be fixed at the root.
