# Demo codebase (deliberately faulty)

Every directory here is a **sandbox of planted defects** for one SDLC phase. It exists so that skill challenges can be
scored objectively: the current skill and a contributor's candidate are both run against the same content, and the
findings are compared with `GROUND_TRUTH.yaml`.

| Directory | Phase | What is inside |
|---|---|---|
| `01-planning/` | Planning | A project charter with missing owners, metrics, risks and sensitive data |
| `02-requirements/` | Requirements | A PRD with ambiguous, untestable and contradictory requirements |
| `03-design/` | Design | Architecture notes, an OpenAPI spec and a migration with design flaws |
| `04-development/` | Development | A small web service riddled with security and correctness bugs |
| `05-testing/` | Testing | Production code with a weak, flaky and misleading test suite |
| `06-deployment/` | Deployment | Dockerfile, pipeline, Kubernetes and Terraform with insecure settings |
| `07-maintenance/` | Maintenance | Changelog, runbook, dependencies and jobs that are not operable |

## Ground truth format

```yaml
phase: 4
defects:
  - id: sql-injection-search        # stable id, referenced in challenge reports
    title: SQL query built with f-string in search()
    file: 04-development/app.py      # suffix match against the finding's file
    severity: blocker
    keywords: [sql-injection, sql injection, f-string, parameteri]   # any one must appear in the finding
```

A finding matches a defect when its file matches (suffix) **and** at least one keyword appears in the finding's
title, description, category or recommendation (case-insensitive). Findings that match nothing are judged by the
model as legitimate or spurious to compute precision.

## Rules

- **Never** put real credentials, real personal data or real infrastructure identifiers here. Everything must be fake.
- Adding defects is welcome (through a normal PR reviewed by code owners); they should be realistic and unambiguous.
- Do not "fix" the defects. This code is not meant to run.
- The repository's own pre-check scan excludes this directory on purpose.
