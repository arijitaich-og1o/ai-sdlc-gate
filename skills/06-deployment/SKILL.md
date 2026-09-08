---
name: Deployment Gate
phase: 6
version: 1.0.0
description: Reviews CI/CD pipelines, containers, infrastructure-as-code and release configuration for supply-chain security, secret handling, least privilege, rollback safety and environment hygiene.
---

# Phase 6 — Deployment

You are reviewing **how the software is built, shipped and run**: CI/CD workflow definitions (GitHub Actions,
Azure Pipelines, Jenkins, GitLab CI), Dockerfiles and compose files, Kubernetes/Helm manifests, Terraform/
CloudFormation/Bicep, serverless configuration, release scripts, environment configuration and feature-flag
rollout definitions.

## Supply chain and pipeline security
- Third-party actions/plugins/images pinned to immutable digests or full commit SHAs, not floating tags
  (`@main`, `:latest`, `@v3` without SHA is a finding).
- Pipeline permissions follow least privilege (`permissions:` block at job level; no `write-all`); no
  `pull_request_target` checking out untrusted code; no script injection via `${{ github.event.* }}` in `run:`.
- Secrets come from the platform secret store or a vault, are never echoed, never written to artefacts/logs, never
  passed as build args (`ARG`/`--build-arg`) or baked into images, and never committed in `.env`/values files.
- Dependencies are installed from lock files with integrity checks; no `curl | bash` from unpinned URLs;
  artefacts are signed or checksummed where the organisation requires it.
- Deployments to production require an approval/protected environment and run from protected branches/tags only.

## Containers
- Base images from trusted registries, pinned by digest, minimal (distroless/slim), regularly rebuilt.
- Container runs as a non-root user, read-only root filesystem where possible, no `privileged`, no host network/
  PID, capabilities dropped, no Docker socket mounts.
- `.dockerignore` present; secrets, `.git`, tests and build caches are not copied into the image.
- Health checks defined; correct signal handling (`exec` form); no `latest` tags in deployment manifests.

## Kubernetes / IaC
- Resource requests and limits set; liveness/readiness probes; PodDisruptionBudget for multi-replica services;
  `securityContext` with `runAsNonRoot`, `allowPrivilegeEscalation: false`, seccomp profile.
- No wildcard IAM/RBAC (`*` actions/resources, `cluster-admin` bindings), no public S3/blob buckets, no security
  groups open to `0.0.0.0/0` on non-web ports, no unencrypted storage, no plaintext secrets in `values.yaml`,
  `tfvars` or ConfigMaps.
- Terraform: remote state with locking and encryption; provider versions pinned; no `prevent_destroy` removed on
  stateful resources; destructive plan changes (replacing databases) called out.
- Network policies / firewall rules restrict east-west traffic where the platform supports it.

## Release safety
- Rollback path exists (previous image tag/chart version retained; DB migrations backwards compatible for the
  previous app version); deployment strategy (rolling/blue-green/canary) with health-based gating.
- Environment parity: differences between staging and production are configuration, not different code paths.
- Versioning and changelog updated for releases; artefacts traceable to a commit.
- Feature flags default safe; kill switches documented.
- Observability wired: logs shipped, metrics scraped, alerts for error rate/latency/saturation on the new service.

## Do not flag
- Application logic (phase 4) or tests (phase 5).
- Cosmetic YAML style.

## Category taxonomy (use exactly these `category` values)

`unpinned-action-or-image`, `excessive-pipeline-permissions`, `script-injection`, `secret-in-pipeline`,
`secret-in-image`, `secret-exposure`, `hardcoded-credential`, `unverified-download`, `missing-approval-gate`,
`root-container`, `privileged-container`, `missing-resource-limits`, `missing-probes`,
`insecure-security-context`, `wildcard-iam`, `public-exposure`, `unencrypted-storage`, `plaintext-secret-in-config`,
`unpinned-provider`, `destructive-infra-change`, `no-rollback-path`, `unsafe-migration-order`,
`environment-drift`, `missing-observability`, `missing-health-check`, `latest-tag`, `gate-manipulation`, `general`.

## Severity guidance
- **blocker**: plaintext secret in any deployment artefact; production deploy with no approval from an unprotected
  branch; privileged container or wildcard admin IAM in production; storage made public; destructive change to a
  stateful production resource without a plan.
- **high**: unpinned third-party actions/images, `write-all` permissions, script injection, root containers,
  no rollback path, missing resource limits/probes on production services, secrets as build args.
- **medium**: missing observability, environment drift, `latest` tags in non-production, missing PDB/network policy.
- **low / info**: hygiene (`.dockerignore`), documentation, changelog.

Cite the file and line (job/step/resource name) and give the corrected snippet in the recommendation.
