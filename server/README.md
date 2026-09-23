# AI SDLC Gate review endpoint

A small, keyless service that the gate client calls with the developer's Microsoft work-account token. It verifies
that token and enforces `@og1o.in` **server-side** before any model call, then reviews the change on Vertex AI and
returns only the model's text and token usage.

Why it exists:

- **The client stores no cloud credential** — only its Microsoft sign-in. No service-account key to distribute,
  store, rotate or leak.
- **`@og1o.in` is enforced where it cannot be bypassed.** Every request's token is checked for the right tenant,
  audience and e-mail domain; anything else gets `403` and never reaches the model.
- **The model, project and region stay hidden** from developers — they only ever see this endpoint's URL.
- **EU residency**: deploy in an EU region and the model runs there too; the code never leaves the EU.

## What it exposes

- `POST /v1/review` — body `{ "system": "...", "user": "...", "role": "review|judge", "max_tokens": 8000 }`,
  header `Authorization: Bearer <entra-token>`. Returns `{ "text": "...", "usage": {...}, "developer": "..." }`.
  The client sends a **role**, never a model name.
- `GET /healthz` — liveness.

## One-time setup

Set these in your GCP project (the one that has the Claude model enabled), replacing the placeholders:

```bash
PROJECT=ogcs-mjnq-ai-ic-network
REGION=europe-west1
TENANT=8794e153-c3bd-4479-8bea-61aeaf167d5a          # your Entra tenant GUID
AUDIENCE=<the Entra app id the client's token is issued for>

# 1) A keyless runtime service account that may call Vertex AI, nothing else.
gcloud iam service-accounts create ai-sdlc-endpoint --project "$PROJECT" \
  --display-name "AI SDLC Gate endpoint (Vertex caller)"
gcloud projects add-iam-policy-binding "$PROJECT" \
  --member "serviceAccount:ai-sdlc-endpoint@$PROJECT.iam.gserviceaccount.com" \
  --role roles/aiplatform.user --condition=None

# 2) Enable the services.
gcloud services enable run.googleapis.com aiplatform.googleapis.com --project "$PROJECT"

# 3) Build and deploy to Cloud Run in the EU, running AS that service account (no key file).
gcloud run deploy ai-sdlc-endpoint --project "$PROJECT" --region "$REGION" \
  --source server \
  --service-account "ai-sdlc-endpoint@$PROJECT.iam.gserviceaccount.com" \
  --allow-unauthenticated \
  --set-env-vars "ENTRA_TENANT=$TENANT,ENTRA_AUDIENCE=$AUDIENCE,ALLOWED_DOMAINS=og1o.in,VERTEX_PROJECT=$PROJECT,VERTEX_LOCATION=$REGION,VERTEX_MODELS=claude-sonnet-4-5,claude-sonnet-4-5"
```

Notes:

- `--allow-unauthenticated` lets developer machines reach the URL; the service does its **own** auth (the Entra
  token check), so it is not open — an unauthenticated or non-`og1o.in` request gets `403`. If you prefer, put it
  behind an internal load balancer or IAP instead and drop the flag.
- `ENTRA_AUDIENCE` is the audience the client's token carries. With the dedicated "AI SDLC Gate" Entra app this is
  that app's application id; until then it is the client id used at sign-in.
- Give clients the resulting URL with `ai-sdlc-gate configure --endpoint-url https://ai-sdlc-endpoint-....run.app`.

## Local run / tests

```bash
pip install -r server/requirements.txt
ENTRA_TENANT=... ENTRA_AUDIENCE=... VERTEX_PROJECT=... uvicorn app:app --port 8080   # from the server/ dir
pytest server/tests
```
