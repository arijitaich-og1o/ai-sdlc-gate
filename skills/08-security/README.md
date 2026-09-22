# Phase 8 — Security skill

`SKILL.md` in this directory is the review prompt the gate runs for the **Security** phase: a dedicated,
adversarial application-security pass over the change set (source-to-sink dataflow for injection,
authorisation/IDOR, cryptography and data protection, SSRF and file handling, unsafe deserialisation,
secrets, supply-chain and infrastructure-as-code risk). It complements the phase-4 development review, which
weighs correctness and maintainability alongside a lighter security check.

## Source

The detection knowledge in `SKILL.md` is distilled from the **secure-code-review** Claude-native SAST project:

> https://github.com/rohanbadekan0g10/secure-code-review

That project organises its coverage across ~20 technique modules (per-language source/sink tables, GraphQL /
gRPC / WebSocket / LLM / XXE / SSRF / crypto / privacy analysis, supply-chain and dependency review,
DevOps/IaC hardening, backdoor and obfuscation detection, and multi-hop dataflow tracing). Because the gate
engine reads only a single `SKILL.md` body per phase (no runtime, no module loader, and any extra files in a
skill directory are rejected by `validate-skills`), that material is **condensed into this one prompt** rather
than ported file-for-file — the taxonomy, tables and reasoning steps are the portable core.

## Category taxonomy

`SKILL.md` emits the same category vocabulary used by the phase-4 development skill, so the challenge/evaluate
scoring stays consistent across the two security-relevant phases. The planted-defect corpus at
`trials/08-security/` exercises these categories.

## Contributing

Improvements follow the same **Skill Challenge** flow as every other phase: open a PR that edits `SKILL.md`
and bumps its `version`; the workflow scores your version against the current one and keeps, replaces, or
absorbs the better parts. See `docs/skill-challenge.md`.
