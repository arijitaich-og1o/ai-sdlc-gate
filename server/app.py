"""AI SDLC Gate review endpoint.

A small, keyless service (deploy on Cloud Run in the EU) that the gate client calls with the developer's Microsoft
work-account token. It verifies the token and enforces @og1o.in server-side, then reviews the change on Vertex AI
and returns only the model's text and token usage. The client holds no cloud credential and never learns the
project, region or model.

Configuration (environment variables):
  ENTRA_TENANT     your Entra tenant GUID (required)
  ENTRA_AUDIENCE   the audience the client's token is issued for (the gate's Entra app id, or the client id used at
                   sign-in) (required)
  ALLOWED_DOMAINS  comma separated, default "og1o.in"
  VERTEX_PROJECT   the GCP project that has the model enabled (required)
  VERTEX_LOCATION  region, default "europe-west1"
  VERTEX_MODELS    comma separated: review model, judge model. Default "claude-sonnet-4-5,claude-sonnet-4-5"
  MAX_OUTPUT_TOKENS default 8000
"""
from __future__ import annotations

import os

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from verify import AuthError, verify_entra_token
from vertex import UpstreamError, call_vertex


class Settings:
    def __init__(self, env: dict | None = None) -> None:
        e = env if env is not None else os.environ
        self.tenant = e.get("ENTRA_TENANT", "")
        self.audience = e.get("ENTRA_AUDIENCE", "")
        self.allowed_domains = [d.strip() for d in e.get("ALLOWED_DOMAINS", "og1o.in").split(",") if d.strip()]
        self.project = e.get("VERTEX_PROJECT", "")
        self.location = e.get("VERTEX_LOCATION", "europe-west1")
        self.models = [m.strip() for m in e.get("VERTEX_MODELS", "claude-sonnet-4-5,claude-sonnet-4-5").split(",") if m.strip()]
        self.max_output_tokens = int(e.get("MAX_OUTPUT_TOKENS", "8000"))

    def model_for(self, role: str) -> str:
        if role == "judge" and len(self.models) > 1:
            return self.models[1]
        return self.models[0]


class ReviewRequest(BaseModel):
    user: str = Field(min_length=1)
    system: str = ""
    role: str = "review"  # the client sends a role, never a model name
    max_tokens: int | None = None


def create_app(settings: Settings | None = None, verify=verify_entra_token, review=call_vertex) -> FastAPI:
    cfg = settings or Settings()
    app = FastAPI(title="AI SDLC Gate endpoint", docs_url=None, redoc_url=None, openapi_url=None)

    def caller(authorization: str = Header(default="")) -> dict:
        if not authorization.lower().startswith("bearer "):
            raise HTTPException(status_code=401, detail="missing bearer token")
        token = authorization.split(" ", 1)[1].strip()
        try:
            return verify(token, cfg.tenant, cfg.audience, cfg.allowed_domains)
        except AuthError:
            # Neutral response: never tell an unauthorized caller why (tenant, domain, audience) they were refused.
            raise HTTPException(status_code=403, detail="not authorized")

    @app.get("/status")
    def status() -> dict:
        return {"ok": True}

    @app.post("/v1/review")
    def do_review(req: ReviewRequest, who: dict = Depends(caller)) -> dict:
        model = cfg.model_for(req.role)
        try:
            data = review(cfg.project, cfg.location, model, req.system, req.user,
                          max_tokens=req.max_tokens or cfg.max_output_tokens)
        except UpstreamError:
            raise HTTPException(status_code=502, detail="the review service is unavailable")
        blocks = data.get("content") or []
        text = "".join(b.get("text", "") for b in blocks if isinstance(b, dict) and b.get("type") == "text")
        usage = data.get("usage") or {}
        return {
            "text": text,
            "usage": {"input_tokens": int(usage.get("input_tokens") or 0), "output_tokens": int(usage.get("output_tokens") or 0)},
            "developer": who["email"],
        }

    return app


app = create_app()
