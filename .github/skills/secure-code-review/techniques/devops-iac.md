---
name: devops-iac
description: "Security analysis for infrastructure-as-code: Dockerfile, Terraform, Kubernetes YAML, GitHub Actions, GitLab CI, Azure Pipelines, and Jenkinsfile. Auto-triggered when these file types are detected; also loaded by --devops flag."
---

# devops-iac

Loaded by `/secure-code-review` when:
- `--devops` flag is passed explicitly, OR
- Any of these files are detected in the scanned path (auto-trigger):
  - `Dockerfile`, `docker-compose*.yml`, `docker-compose*.yaml`
  - `*.tf`, `*.tfvars`
  - `*.yaml`/`*.yml` containing `apiVersion:` (Kubernetes manifest)
  - `.github/workflows/*.yml`, `.gitlab-ci.yml`, `azure-pipelines.yml`, `Jenkinsfile`
  - `circleci/config.yml`, `bitbucket-pipelines.yml`

**Output format:** uses developer-friendly ❌/✅ format by default (same as main skill).

---

## Dockerfile Security

**File patterns:** `Dockerfile`, `Dockerfile.*`, `*.dockerfile`

### D1 — Running as Root

```dockerfile
❌ NEVER: (no USER directive, or)
FROM ubuntu:22.04
RUN apt-get install -y myapp
CMD ["myapp"]                    # runs as root

✅ ALWAYS:
FROM ubuntu:22.04
RUN apt-get install -y myapp && \
    groupadd -r appgroup && useradd -r -g appgroup appuser
USER appuser
CMD ["myapp"]
```

### D2 — ADD with Remote URLs

```dockerfile
❌ NEVER:
ADD https://example.com/script.sh /app/script.sh   # unverified download

✅ ALWAYS:
# Download, verify checksum, then COPY
RUN curl -fsSL https://example.com/script.sh -o /tmp/script.sh && \
    echo "expected_sha256  /tmp/script.sh" | sha256sum -c - && \
    mv /tmp/script.sh /app/script.sh
```

### D3 — Secrets in Build Args or ENV

```dockerfile
❌ NEVER:
ARG DB_PASSWORD=prod_password_here    # visible in docker history
ENV API_KEY=sk_live_abc123            # baked into image layers

✅ ALWAYS:
# Pass secrets at runtime, not build time
# Use Docker secrets or runtime env injection:
# docker run -e API_KEY=$API_KEY myimage
# Or use BuildKit secret mounts:
RUN --mount=type=secret,id=mysecret cat /run/secrets/mysecret
```

### D4 — Unpinned Base Images

```dockerfile
❌ NEVER:
FROM ubuntu:latest              # changes without warning
FROM python:3                   # mutable tag

✅ ALWAYS:
FROM ubuntu:22.04               # pinned minor version
FROM python:3.11.7-slim         # pinned patch version
# Ideal: pin to digest for full reproducibility:
FROM python:3.11.7-slim@sha256:abc123...
```

### D5 — Unnecessary Tooling in Production Images

```dockerfile
❌ NEVER (in production Dockerfile):
RUN apt-get install -y curl wget gcc make git vim

✅ ALWAYS: Use multi-stage builds
FROM python:3.11 AS builder
RUN pip install --user -r requirements.txt

FROM python:3.11-slim AS runtime  # minimal base
COPY --from=builder /root/.local /root/.local
# No build tools in the final image
```

---

## Terraform Security

**File patterns:** `*.tf`, `*.tfvars`

### T1 — Public Cloud Storage

```hcl
# ❌ NEVER:
resource "aws_s3_bucket_acl" "example" {
  acl = "public-read"   # world-readable bucket
}

resource "aws_s3_bucket_public_access_block" "example" {
  block_public_acls       = false   # ❌ allows public ACLs
  block_public_policy     = false   # ❌ allows public bucket policy
}

# ✅ ALWAYS:
resource "aws_s3_bucket_public_access_block" "example" {
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
```

### T2 — Overly Permissive Security Groups

```hcl
# ❌ NEVER:
resource "aws_security_group_rule" "ssh" {
  cidr_blocks = ["0.0.0.0/0"]   # SSH open to internet
  from_port   = 22
  to_port     = 22
  protocol    = "tcp"
}

# ✅ ALWAYS: Restrict to known CIDRs or use SSM Session Manager
cidr_blocks = ["10.0.0.0/8"]    # internal only
```

Flag port 22 (SSH), 3389 (RDP), 5432 (Postgres), 3306 (MySQL), 27017 (MongoDB) open to `0.0.0.0/0` as HIGH.

### T3 — Unencrypted Storage

```hcl
# ❌ NEVER:
resource "aws_ebs_volume" "example" {
  encrypted = false   # unencrypted disk
}

resource "aws_rds_instance" "example" {
  storage_encrypted = false
}

# ✅ ALWAYS:
resource "aws_ebs_volume" "example" {
  encrypted  = true
  kms_key_id = aws_kms_key.example.arn
}
```

Flag missing encryption on: EBS, RDS, S3 (server-side), ElastiCache, DynamoDB, SQS, SNS.

### T4 — Overly Permissive IAM

```hcl
# ❌ NEVER:
data "aws_iam_policy_document" "example" {
  statement {
    actions   = ["*"]         # all actions
    resources = ["*"]         # all resources
  }
}

# ✅ ALWAYS: Least privilege
statement {
  actions   = ["s3:GetObject", "s3:PutObject"]
  resources = ["arn:aws:s3:::my-bucket/*"]
}
```

### T5 — Unencrypted Terraform State

```hcl
# ❌ NEVER: local state or unencrypted remote
terraform {
  backend "s3" {
    bucket  = "tfstate"
    # missing: encrypt = true
    # missing: dynamodb_table for locking
  }
}

# ✅ ALWAYS:
backend "s3" {
  bucket         = "tfstate"
  encrypt        = true
  kms_key_id     = "arn:aws:kms:..."
  dynamodb_table = "terraform-locks"
}
```

### T6 — Lambda with Admin IAM

```hcl
# ❌ NEVER: Lambda role with administrator access
resource "aws_iam_role_policy_attachment" "lambda_admin" {
  policy_arn = "arn:aws:iam::aws:policy/AdministratorAccess"   # full AWS admin
  role       = aws_iam_role.lambda_role.name
}

# ❌ NEVER: Lambda with * on all resources
resource "aws_iam_policy" "lambda_policy" {
  policy = jsonencode({
    Statement = [{
      Action   = "lambda:*"    # or "*"
      Resource = "*"
    }]
  })
}

# ✅ ALWAYS: Scope to specific actions and ARNs this function actually needs
```

### T7 — RDS Publicly Accessible

```hcl
# ❌ NEVER:
resource "aws_db_instance" "example" {
  publicly_accessible = true    # database endpoint exposed to internet
}

# ✅ ALWAYS:
resource "aws_db_instance" "example" {
  publicly_accessible = false
  vpc_security_group_ids = [aws_security_group.db_sg.id]  # private VPC only
}
```

### T8 — CloudFront Without WAF

```hcl
# ❌ NEVER: CloudFront distribution with no WAF association
resource "aws_cloudfront_distribution" "example" {
  # missing: web_acl_id = aws_wafv2_web_acl.example.arn
  enabled = true
}

# ✅ ALWAYS:
resource "aws_cloudfront_distribution" "example" {
  web_acl_id = aws_wafv2_web_acl.example.arn
}
```

Also flag: `aws_lb` (ALB) without `aws_wafv2_web_acl_association` for internet-facing load balancers.

---

## Kubernetes YAML Security

**File patterns:** `*.yaml`/`*.yml` containing `apiVersion:` + `kind:`

### K1 — Privileged Containers

```yaml
# ❌ NEVER:
securityContext:
  privileged: true            # full host access
  runAsRoot: true

# ✅ ALWAYS:
securityContext:
  runAsNonRoot: true
  runAsUser: 1000
  readOnlyRootFilesystem: true
  allowPrivilegeEscalation: false
  capabilities:
    drop: ["ALL"]
```

### K2 — Host Namespace Sharing

```yaml
# ❌ NEVER:
spec:
  hostNetwork: true    # shares host network namespace
  hostPID: true        # sees all host processes
  hostIPC: true        # shares host IPC namespace

# ✅ ALWAYS: omit these fields (default false)
```

### K3 — Secrets in ConfigMap

```yaml
# ❌ NEVER:
apiVersion: v1
kind: ConfigMap
data:
  database_password: "prod_password_here"   # plaintext secret

# ✅ ALWAYS: Use Secrets (base64-encoded) + seal at rest
apiVersion: v1
kind: Secret
type: Opaque
stringData:
  database_password: "prod_password_here"   # encrypted at rest
# Better: Use sealed-secrets or external-secrets-operator
```

### K4 — Mutable Image Tags

```yaml
# ❌ NEVER:
containers:
  - image: myapp:latest         # changes on every pull
  - image: myapp:v1             # mutable tag can be overwritten

# ✅ ALWAYS:
containers:
  - image: myapp@sha256:abc123def456...   # immutable digest
```

### K5 — Missing Resource Limits

```yaml
# ❌ NEVER: no limits (DoS risk)
containers:
  - name: app

# ✅ ALWAYS:
containers:
  - name: app
    resources:
      requests:
        memory: "128Mi"
        cpu: "100m"
      limits:
        memory: "256Mi"
        cpu: "500m"
```

### K6 — RBAC Misconfigurations

```yaml
# ❌ NEVER: wildcard verb + wildcard resource = cluster admin
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
rules:
  - apiGroups: ["*"]
    resources: ["*"]     # every resource type
    verbs: ["*"]         # every operation including delete, patch

# ❌ NEVER: pods/exec access → arbitrary command execution in any pod
rules:
  - apiGroups: [""]
    resources: ["pods/exec", "pods/attach", "pods/portforward"]
    verbs: ["create", "get"]

# ❌ NEVER: ClusterRoleBinding grants cluster-wide access when namespaced would do
kind: ClusterRoleBinding   # flag when namespace-scoped workload doesn't need cluster scope

# ✅ ALWAYS: least-privilege role, namespace-scoped, no wildcard verbs/resources
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  namespace: production
rules:
  - apiGroups: ["apps"]
    resources: ["deployments"]
    verbs: ["get", "list", "watch"]
```

Also flag:
- `automountServiceAccountToken: true` (default) on pods that don't need API access — disable with `automountServiceAccountToken: false`
- `serviceAccountName: default` — shared default SA accumulates permissions across workloads
- SA tokens with `secrets:` access → can read all Secrets in the namespace

---

## GitHub Actions Security

**File patterns:** `.github/workflows/*.yml`, `.github/workflows/*.yaml`

### G1 — Unpinned Third-Party Actions

```yaml
# ❌ NEVER:
- uses: actions/checkout@v4          # mutable tag — can be hijacked
- uses: actions/setup-node@main      # branch — changes anytime

# ✅ ALWAYS: Pin to full commit SHA
- uses: actions/checkout@b4ffde65f46336ab88eb53be808477a3936bae11  # v4.1.1
- uses: actions/setup-node@1a4442cacd436585916779262731d1f68e6c7b95  # v3.8.0
```

Flag every `uses:` line not pinned to a 40-character hex SHA.

### G2 — pull_request_target with Write Permissions

```yaml
# ❌ NEVER (classic takeover vector):
on:
  pull_request_target:    # runs with write permissions in context of base branch
    types: [opened]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{ github.event.pull_request.head.sha }}  # checks out PR code with write perms

# ✅ ALWAYS: Use pull_request (not pull_request_target) for untrusted code
# If pull_request_target is required, never checkout PR head code in the same job
```

### G3 — Secrets Echoed to Logs

```yaml
# ❌ NEVER:
- run: echo "Token is ${{ secrets.API_TOKEN }}"     # exposed in logs
- run: echo "$GITHUB_TOKEN" > /tmp/token            # written to disk

# ✅ ALWAYS: Never echo secrets; use them directly in commands
- run: curl -H "Authorization: Bearer $TOKEN" https://api.example.com
  env:
    TOKEN: ${{ secrets.API_TOKEN }}
```

### G4 — Expression Injection

```yaml
# ❌ NEVER:
- run: echo "${{ github.event.pull_request.title }}"  # PR title is user-controlled
- run: ${{ github.event.issue.body }}                  # issue body is user-controlled

# ✅ ALWAYS: Use environment variables as intermediary
- run: echo "$PR_TITLE"
  env:
    PR_TITLE: ${{ github.event.pull_request.title }}   # sanitized through env var
```

### G5 — Overly Broad Permissions

```yaml
# ❌ NEVER:
permissions: write-all    # or omitting permissions (defaults to write in some configs)

# ✅ ALWAYS: Minimal permissions
permissions:
  contents: read
  pull-requests: write    # only what the job actually needs
```

---

## Other CI Platforms

### GitLab CI (`.gitlab-ci.yml`)
- Variables defined in YAML with sensitive values → should be in GitLab CI/CD variables (masked + protected)
- `CI_JOB_TOKEN` used beyond its scope
- `allow_failure: true` on security jobs (masks failures)
- Artifacts containing secrets uploaded unencrypted

### Azure Pipelines (`azure-pipelines.yml`)
- `$(SYSTEM_ACCESSTOKEN)` passed to untrusted scripts
- `enabled: false` on required security checks
- Service connections with overly broad permissions

### Jenkinsfile
- `sh "curl ... ${params.USER_INPUT}"` — command injection via parameters
- Credentials loaded via `withCredentials` but echoed in `sh` steps
- `@NonCPS` methods accessing secrets (bypasses Groovy sandbox)
- Plugins not pinned to verified versions in `plugins.txt`

---

## Serverless / FaaS Security

**File patterns:** `serverless.yml`, `serverless.ts`, `template.yaml` (SAM), `functions/*.js`, `handler.py`, `lambda_function.py`

### SL1 — Missing Event Source Validation

```javascript
// ❌ NEVER: Lambda handler trusts event payload without validation
exports.handler = async (event) => {
  const userId = event.pathParameters.userId    // no type/format check
  const body = JSON.parse(event.body)           // no schema validation
  await db.update(userId, body)                 // unvalidated data to DB
}

// ✅ ALWAYS: validate event schema before processing
const { userId } = event.pathParameters
if (!/^[0-9a-f-]{36}$/.test(userId)) {
  return { statusCode: 400, body: 'Invalid userId' }
}
```

### SL2 — Lambda Function URL Without Auth

```yaml
# ❌ NEVER: public Lambda URL with no auth
# serverless.yml
functions:
  myFunc:
    url:
      authorizer: NONE    # publicly accessible without any auth

# ✅ ALWAYS:
    url:
      authorizer: aws_iam  # requires SigV4
# OR: route through API Gateway with Cognito/Lambda authorizer
```

Also flag: API Gateway routes with `authorization: NONE` on non-public endpoints.

### SL3 — Secrets in Lambda Environment Variables

```hcl
# ❌ NEVER: secrets in plaintext env vars (visible in console, logs, CloudFormation)
resource "aws_lambda_function" "example" {
  environment {
    variables = {
      DB_PASSWORD = "prod_password_here"
      API_KEY     = "sk_live_abc123"
    }
  }
}

# ✅ ALWAYS: reference SSM Parameter Store or Secrets Manager at runtime
# In code: ssm.getParameter({ Name: '/app/db/password', WithDecryption: true })
```

### SL4 — Overly Permissive Lambda Execution Role

Flag when the Lambda execution role has:
- `Action: "s3:*"` / `Action: "*"` on `Resource: "*"`
- Access to SSM Parameters beyond its own path prefix (`/app/my-function/*`)
- Cross-account trust (`sts:AssumeRole` from any account)
- `iam:PassRole` — allows the function to escalate privileges by passing roles to other services

### SL5 — Missing Timeout / Reserved Concurrency

```yaml
# ❌ NEVER: default timeout (3s for Lambda), no concurrency cap
functions:
  processQueue:
    handler: handler.processQueue
    # timeout: missing — defaults to 3s, causes silent truncation on slow DB
    # reservedConcurrency: missing — runaway invocations → bill DoS

# ✅ ALWAYS:
    timeout: 30               # explicit, matched to expected operation time
    reservedConcurrency: 50   # caps blast radius on runaway loops
```

### SL6 — Cold-Start Secrets / Cached Credentials

Flag Lambda functions that:
- Cache database connections or tokens in the global scope across invocations without TTL
- Store decrypted secrets in module-level variables — persisted across warm invocations and visible in memory dumps
- Use `process.env.SECRET` fetched at deploy time — not rotatable without redeploy; use SSM/Secrets Manager at runtime with caching
