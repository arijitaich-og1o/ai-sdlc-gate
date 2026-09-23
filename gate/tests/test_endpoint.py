"""The endpoint provider: the client sends its Microsoft token and a role, holds no cloud credential."""
from __future__ import annotations

import json
import time

import httpx
import pytest

from ai_sdlc_gate import identity as identity_mod
from ai_sdlc_gate import secrets_store
from ai_sdlc_gate.config import Config
from ai_sdlc_gate.llm import EndpointClient, LLMError, build_client


def test_endpoint_client_posts_token_and_role_and_parses_text():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("authorization")
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"text": '{"summary": "ok", "findings": []}', "usage": {"input_tokens": 10, "output_tokens": 4}, "developer": "a@og1o.in"})

    c = EndpointClient("https://sdlc.example", token_provider=lambda: "entra-tok", role="review", transport=httpx.MockTransport(handler))
    data, resp = c.chat_json("system rules", "review this diff")
    assert data == {"summary": "ok", "findings": []}
    assert seen["url"] == "https://sdlc.example/v1/review"
    assert seen["auth"] == "Bearer entra-tok"
    assert seen["body"] == {"system": "system rules", "user": "review this diff", "role": "review", "max_tokens": 8000}
    assert c.total_usage == {"prompt_tokens": 10, "completion_tokens": 4}
    c.close()


def test_endpoint_client_forbidden_gives_a_clear_sign_in_message():
    c = EndpointClient("https://sdlc.example", token_provider=lambda: "t", transport=httpx.MockTransport(lambda r: httpx.Response(403, json={"detail": "not authorized"})), max_retries=0)
    with pytest.raises(LLMError) as exc:
        c.chat_json("s", "u")
    assert "og1o.in" in str(exc.value)
    c.close()


def test_endpoint_client_never_needs_a_model_name():
    # judge role selects nothing on the client; the server maps role -> model.
    seen = {}
    c = EndpointClient("https://sdlc.example", token_provider=lambda: "t", role="judge",
                       transport=httpx.MockTransport(lambda r: (seen.update(body=json.loads(r.content)), httpx.Response(200, json={"text": "{}", "usage": {}}))[1]))
    c.chat_json("s", "u")
    assert seen["body"]["role"] == "judge"
    c.close()


def test_build_client_selects_the_endpoint_provider(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_SDLC_GATE_HOME", str(tmp_path))
    for var in ("LITELLM_API_KEY", "VERTEX_SA_KEY"):
        monkeypatch.delenv(var, raising=False)

    class FakeKeyring:
        store: dict = {}

        def set_password(self, s, a, v):
            self.store[(s, a)] = v

        def get_password(self, s, a):
            return self.store.get((s, a))

        def delete_password(self, s, a):
            self.store.pop((s, a), None)

    monkeypatch.setattr(secrets_store, "_keyring", lambda: FakeKeyring())
    st = secrets_store.store(models=[], mode="endpoint", provider="endpoint", data={"endpoint_url": "https://sdlc.example"})
    assert st.is_ready() and st.provider == "endpoint"
    loaded = secrets_store.load()
    assert loaded and loaded.provider == "endpoint" and loaded.data["endpoint_url"] == "https://sdlc.example"

    client = build_client(Config(), token_provider=lambda: "t")
    assert isinstance(client, EndpointClient) and client.role == "review"
    client.close()


def test_endpoint_token_refreshes_silently_from_the_stored_refresh_token(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_SDLC_GATE_HOME", str(tmp_path))
    monkeypatch.setattr(secrets_store, "_keyring", lambda: None)  # use the encrypted-file fallback
    secrets_store.set_blob(identity_mod.REFRESH_ACCOUNT, "rt-0")

    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        form = dict(x.split("=", 1) for x in request.content.decode().split("&"))
        assert form["grant_type"] == "refresh_token" and form["refresh_token"] == "rt-0"
        return httpx.Response(200, json={"id_token": "fresh-id-token", "refresh_token": "rt-1"})

    cfg = Config()
    cfg.data.setdefault("identity", {}).update({"tenant": "8794e153-c3bd-4479-8bea-61aeaf167d5a", "client_id": "cid", "authority": "https://login.microsoftonline.com"})
    tok = identity_mod.endpoint_token(cfg, client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert tok == "fresh-id-token" and calls["n"] == 1
    # the rotated refresh token is persisted for next time
    assert secrets_store.get_blob(identity_mod.REFRESH_ACCOUNT) == "rt-1"
