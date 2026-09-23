"""The endpoint: 403 for a non-og1o caller, a normal review for a valid one, and the model name never leaves."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import app as appmod
from verify import AuthError


def _settings():
    return appmod.Settings({
        "ENTRA_TENANT": "8794e153-c3bd-4479-8bea-61aeaf167d5a",
        "ENTRA_AUDIENCE": "api://ai-sdlc-gate",
        "ALLOWED_DOMAINS": "og1o.in",
        "VERTEX_PROJECT": "ogcs-mjnq-ai-ic-network",
        "VERTEX_LOCATION": "europe-west1",
        "VERTEX_MODELS": "claude-sonnet-4-5,claude-sonnet-4-5-judge",
    })


def _client(verify, review):
    return TestClient(appmod.create_app(_settings(), verify=verify, review=review))


def _fake_review_capture(box):
    def review(project, location, model, system, user, max_tokens=8000):
        box.update(project=project, location=location, model=model, system=system, user=user)
        return {"content": [{"type": "text", "text": '{"summary": "ok", "findings": []}'}],
                "usage": {"input_tokens": 12, "output_tokens": 8}}
    return review


def test_valid_og1o_caller_gets_a_review():
    box: dict = {}
    c = _client(lambda *a, **k: {"email": "priya.r@og1o.in", "name": "Priya", "tid": "t"}, _fake_review_capture(box))
    r = c.post("/v1/review", json={"system": "rules", "user": "review this", "role": "review"},
               headers={"Authorization": "Bearer good-token"})
    assert r.status_code == 200
    body = r.json()
    assert body["text"] == '{"summary": "ok", "findings": []}'
    assert body["usage"] == {"input_tokens": 12, "output_tokens": 8}
    assert body["developer"] == "priya.r@og1o.in"
    # The server picked the model and region; the client sent only a role.
    assert box["model"] == "claude-sonnet-4-5" and box["location"] == "europe-west1"
    # The model name is never returned to the client.
    assert "claude" not in r.text


def test_judge_role_selects_the_second_model():
    box: dict = {}
    c = _client(lambda *a, **k: {"email": "a@og1o.in", "name": "", "tid": "t"}, _fake_review_capture(box))
    c.post("/v1/review", json={"user": "x", "role": "judge"}, headers={"Authorization": "Bearer t"})
    assert box["model"] == "claude-sonnet-4-5-judge"


def test_non_og1o_caller_is_forbidden_and_no_model_call_happens():
    calls = {"n": 0}

    def review(*a, **k):
        calls["n"] += 1
        return {}

    def verify(*a, **k):
        raise AuthError("mallory@gmail.com is not in an allowed organisation domain")

    c = _client(verify, review)
    r = c.post("/v1/review", json={"user": "x"}, headers={"Authorization": "Bearer other-tenant-token"})
    assert r.status_code == 403
    assert calls["n"] == 0, "the model must never be called for an unauthorized request"
    # The refusal reveals nothing about why (tenant/domain/audience).
    assert "og1o" not in r.text and "domain" not in r.text and "tenant" not in r.text


def test_missing_bearer_is_401():
    c = _client(lambda *a, **k: {"email": "a@og1o.in"}, _fake_review_capture({}))
    assert c.post("/v1/review", json={"user": "x"}).status_code == 401


def test_upstream_failure_is_502_not_a_leak():
    from vertex import UpstreamError

    def review(*a, **k):
        raise UpstreamError("model backend returned HTTP 429: quota exceeded for project ogcs-...")

    c = _client(lambda *a, **k: {"email": "a@og1o.in"}, review)
    r = c.post("/v1/review", json={"user": "x"}, headers={"Authorization": "Bearer t"})
    assert r.status_code == 502 and "ogcs" not in r.text and "quota" not in r.text


def test_status():
    c = _client(lambda *a, **k: {"email": "a@og1o.in"}, _fake_review_capture({}))
    assert c.get("/status").json() == {"ok": True}
