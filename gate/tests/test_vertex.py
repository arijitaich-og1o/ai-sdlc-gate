"""Vertex AI (Anthropic Claude) provider: client behaviour, secure storage, and the key-broker round-trip."""
from __future__ import annotations

import importlib.util
import json
import time
from pathlib import Path

import httpx
import pytest

from ai_sdlc_gate import keybroker, secrets_store
from ai_sdlc_gate.config import Config
from ai_sdlc_gate.llm import LLMError, VertexClient, build_client

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# A syntactically valid (throwaway) service-account key: a real RSA private key, not tied to any project.
def _fake_sa() -> dict:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    pem = rsa.generate_private_key(public_exponent=65537, key_size=2048).private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode()
    return {"type": "service_account", "project_id": "ogcs-mjnq-ai-ic-network", "private_key_id": "k1",
            "private_key": pem, "client_email": "gate@ogcs-mjnq-ai-ic-network.iam.gserviceaccount.com", "token_uri": "https://oauth2.googleapis.com/token"}


def _anthropic_ok(body_text: str) -> httpx.Response:
    return httpx.Response(200, json={"content": [{"type": "text", "text": body_text}], "usage": {"input_tokens": 11, "output_tokens": 7}})


def test_vertex_client_calls_rawpredict_and_parses_json():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("authorization")
        seen["body"] = json.loads(request.content)
        # With JSON prefill the model continues after "{"; return the remainder of the object.
        return _anthropic_ok('"summary": "ok", "findings": []}')

    client = VertexClient(
        project="ogcs-mjnq-ai-ic-network", location="us-east5", credentials=_fake_sa(),
        model="claude-opus-4-8", transport=httpx.MockTransport(handler),
        token_fn=lambda: ("tok-123", time.time() + 3600),
    )
    data, resp = client.chat_json("system rules", "review this diff")
    assert data == {"summary": "ok", "findings": []}
    assert seen["url"] == "https://us-east5-aiplatform.googleapis.com/v1/projects/ogcs-mjnq-ai-ic-network/locations/us-east5/publishers/anthropic/models/claude-opus-4-8:rawPredict"
    assert seen["auth"] == "Bearer tok-123"
    assert seen["body"]["anthropic_version"] == "vertex-2023-10-16" and seen["body"]["system"] == "system rules"
    assert seen["body"]["messages"][-1] == {"role": "assistant", "content": "{"}  # JSON prefill
    assert client.total_usage == {"prompt_tokens": 11, "completion_tokens": 7}
    client.close()


def test_vertex_global_location_uses_global_host():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "aiplatform.googleapis.com"
        assert "/locations/global/" in str(request.url)
        return _anthropic_ok('"summary": "", "findings": []}')

    client = VertexClient(project="p", location="global", credentials=_fake_sa(), model="claude-opus-4-8",
                          transport=httpx.MockTransport(handler), token_fn=lambda: ("t", time.time() + 3600))
    client.chat_json("s", "u")
    client.close()


def test_vertex_errors_never_leak_project_model_or_credential():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"error": {"message": "Permission denied on resource project ogcs-mjnq-ai-ic-network"}})

    client = VertexClient(project="ogcs-mjnq-ai-ic-network", location="us-east5", credentials=_fake_sa(),
                          model="claude-opus-4-8", transport=httpx.MockTransport(handler),
                          token_fn=lambda: ("t", time.time() + 3600), max_retries=0)
    with pytest.raises(LLMError) as exc:
        client.chat_json("s", "u")
    msg = str(exc.value)
    assert "claude-opus-4-8" not in msg and "ogcs-mjnq-ai-ic-network" not in msg and "aiplatform" not in msg
    assert "ai-sdlc-gate configure" in msg
    client.close()


def test_secrets_store_roundtrip_with_vertex_record(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_SDLC_GATE_HOME", str(tmp_path))
    for var in ("LITELLM_API_KEY", "LITELLM_BASE_URL", "LITELLM_MODELS", "VERTEX_SA_KEY", "VERTEX_PROJECT", "VERTEX_LOCATION", "VERTEX_MODELS"):
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
    sa = _fake_sa()
    st = secrets_store.store(models=["claude-opus-4-8", "claude-opus-4-8"], mode="shared", provider="vertex",
                             data={"project": "ogcs-mjnq-ai-ic-network", "location": "us-east5", "credentials": sa})
    assert st.backend == "keyring" and st.is_ready()
    assert not any(tmp_path.glob("*")), "nothing may be written to disk when the OS store is available"
    loaded = secrets_store.load()
    assert loaded and loaded.provider == "vertex" and loaded.data["project"] == "ogcs-mjnq-ai-ic-network"
    assert loaded.data["credentials"]["client_email"].endswith(".iam.gserviceaccount.com")

    # build_client selects the Vertex client for a stored Vertex record.
    monkeypatch.setattr("ai_sdlc_gate.llm.VertexClient._mint_token", lambda self: ("t", time.time() + 3600))
    client = build_client(Config())
    assert isinstance(client, VertexClient) and client.model == "claude-opus-4-8"
    client.close()


def test_vertex_env_configures_provider(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_SDLC_GATE_HOME", str(tmp_path))
    monkeypatch.setattr(secrets_store, "_keyring", lambda: None)
    monkeypatch.setenv("VERTEX_SA_KEY", json.dumps(_fake_sa()))
    monkeypatch.setenv("VERTEX_PROJECT", "ogcs-mjnq-ai-ic-network")
    monkeypatch.setenv("VERTEX_LOCATION", "europe-west1")
    st = secrets_store.load()
    assert st and st.provider == "vertex" and st.backend == "env" and st.data["location"] == "europe-west1"


def test_broker_payload_and_hybrid_roundtrip():
    payload_mod = _load_script("broker_payload")
    seal_mod = _load_script("broker_seal")

    # Vertex payload from environment-style secrets.
    sa = _fake_sa()
    env = {"VERTEX_SA_KEY": json.dumps(sa), "VERTEX_PROJECT": "ogcs-mjnq-ai-ic-network", "DEVELOPER": "arijitaich-og1o"}
    payload = payload_mod.build(env)
    assert payload["provider"] == "vertex" and payload["data"]["project"] == "ogcs-mjnq-ai-ic-network"
    assert payload["models"] == ["claude-opus-4-8", "claude-opus-4-8"]

    # Seal to a client key pair (hybrid envelope, because a service account is too big for direct RSA), then decrypt.
    private, pub_pem = keybroker.generate_keypair()
    envelope = seal_mod.seal(pub_pem.encode(), json.dumps(payload).encode())
    cfg = keybroker.decrypt_config(private, json.dumps(envelope).encode())
    assert cfg.provider == "vertex" and cfg.data["project"] == "ogcs-mjnq-ai-ic-network"
    assert cfg.data["credentials"]["client_email"] == sa["client_email"]

    # The OpenAI/LiteLLM payload also seals and decrypts through the same envelope.
    litellm = payload_mod.build({"LITELLM_API_KEY": "label: sk-abcdefgh12345678", "LITELLM_BASE_URL": "https://gw.example/", "DEVELOPER": "d"})
    assert litellm["provider"] == "openai" and litellm["api_key"] == "sk-abcdefgh12345678"
    env2 = seal_mod.seal(pub_pem.encode(), json.dumps(litellm).encode())
    cfg2 = keybroker.decrypt_config(private, json.dumps(env2).encode())
    assert cfg2.provider == "openai" and cfg2.base_url == "https://gw.example" and cfg2.api_key == "sk-abcdefgh12345678"


def test_broker_payload_requires_a_backend():
    payload_mod = _load_script("broker_payload")
    with pytest.raises(SystemExit):
        payload_mod.build({"DEVELOPER": "d"})
    with pytest.raises(SystemExit):
        payload_mod.build({"VERTEX_SA_KEY": json.dumps(_fake_sa())})  # project missing
