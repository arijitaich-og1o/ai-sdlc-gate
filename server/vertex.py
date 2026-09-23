"""Call Anthropic Claude on Vertex AI using the service's own runtime identity (no key file).

On Cloud Run / GKE the container runs as a service account; google.auth.default() reads a short-lived token from
the metadata server. There is no downloaded key anywhere. The project, region and model names live only in the
server's configuration and never reach the client.
"""
from __future__ import annotations

from typing import Any

import httpx

_SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]
ANTHROPIC_VERSION = "vertex-2023-10-16"


class UpstreamError(Exception):
    """The model backend failed. The detail is for server logs, not the client."""


def _default_token() -> str:
    # google-auth is imported lazily so unit tests can inject a token instead.
    import google.auth
    from google.auth.transport.requests import Request

    creds, _ = google.auth.default(scopes=_SCOPES)
    if not creds.valid:
        creds.refresh(Request())
    if not creds.token:
        raise UpstreamError("could not obtain a Google access token from the runtime identity")
    return creds.token


def host_for(location: str) -> str:
    return "aiplatform.googleapis.com" if location == "global" else f"{location}-aiplatform.googleapis.com"


def call_vertex(
    project: str,
    location: str,
    model: str,
    system: str,
    user: str,
    max_tokens: int = 8000,
    client: httpx.Client | None = None,
    token_fn: Any | None = None,
) -> dict[str, Any]:
    """POST one review to Vertex rawPredict and return the parsed Anthropic response."""
    url = (
        f"https://{host_for(location)}/v1/projects/{project}/locations/{location}"
        f"/publishers/anthropic/models/{model}:rawPredict"
    )
    body: dict[str, Any] = {
        "anthropic_version": ANTHROPIC_VERSION,
        "max_tokens": int(max_tokens),
        "messages": [{"role": "user", "content": user}],
    }
    if system:
        body["system"] = system
    token = (token_fn or _default_token)()
    http = client or httpx.Client(timeout=httpx.Timeout(180.0))
    try:
        resp = http.post(url, headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}, json=body)
    except httpx.HTTPError as exc:
        raise UpstreamError(f"could not reach the model backend: {exc.__class__.__name__}") from exc
    finally:
        if client is None:
            http.close()
    if resp.status_code >= 400:
        raise UpstreamError(f"model backend returned HTTP {resp.status_code}: {resp.text[:300]}")
    return resp.json()
