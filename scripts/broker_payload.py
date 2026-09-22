#!/usr/bin/env python3
"""Assemble the review-backend configuration JSON from repository secrets (read from the environment).

Vertex AI is used when VERTEX_SA_KEY is set; otherwise an OpenAI-compatible gateway. The JSON payload is printed
to stdout for the sealing step. Misconfiguration exits non-zero with a `::error::` annotation. No secret is printed
except inside the intended configuration payload on stdout.
"""
from __future__ import annotations

import json
import os
import re
import sys


def fail(msg: str) -> None:
    print(f"::error::{msg}", file=sys.stderr)
    raise SystemExit(1)


def build(env: dict) -> dict:
    developer = env.get("DEVELOPER", "")
    sa_raw = (env.get("VERTEX_SA_KEY") or "").strip()
    if sa_raw:
        project = (env.get("VERTEX_PROJECT") or "").strip()
        if not project:
            fail("VERTEX_SA_KEY is set but the VERTEX_PROJECT secret is not")
        try:
            sa = json.loads(sa_raw)
        except json.JSONDecodeError:
            fail("VERTEX_SA_KEY is not valid JSON (paste the whole service-account key file)")
        if not isinstance(sa, dict) or "private_key" not in sa or "client_email" not in sa:
            fail("VERTEX_SA_KEY does not look like a service-account key (missing private_key/client_email)")
        models = [m.strip() for m in (env.get("VERTEX_MODELS") or "").split(",") if m.strip()] or ["claude-opus-4-8", "claude-opus-4-8"]
        return {
            "provider": "vertex", "mode": "shared", "developer": developer, "models": models,
            "data": {"project": project, "location": (env.get("VERTEX_LOCATION") or "").strip() or "us-east5", "credentials": sa},
        }
    api_key = env.get("LITELLM_API_KEY") or ""
    base_url = (env.get("LITELLM_BASE_URL") or "").strip()
    if not api_key:
        fail("no review backend is configured: set VERTEX_SA_KEY (+ VERTEX_PROJECT) for Vertex AI, or LITELLM_API_KEY and LITELLM_BASE_URL for an OpenAI-compatible gateway")
    if not base_url:
        fail("the LITELLM_BASE_URL secret is not configured")
    m = re.search(r"sk-[A-Za-z0-9_-]{16,}", api_key)
    if not m:
        fail("LITELLM_API_KEY does not contain a gateway key (expected a token starting with 'sk-')")
    key = m.group(0)
    if key != api_key.strip():
        print("::warning::LITELLM_API_KEY contained extra text around the key; only the key token was used.", file=sys.stderr)
    models = [x.strip() for x in (env.get("LITELLM_MODELS") or "").split(",") if x.strip()]
    if not models:
        print("::warning::the LITELLM_MODELS secret is not set; clients will use the engine's built-in model list.", file=sys.stderr)
    return {"provider": "openai", "base_url": base_url.rstrip("/"), "api_key": key, "models": models, "mode": "shared", "developer": developer}


if __name__ == "__main__":
    print(json.dumps(build(dict(os.environ))))
