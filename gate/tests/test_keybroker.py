from __future__ import annotations

import io
import json
import zipfile

import httpx
import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from sdlc_gate import keybroker


def _encrypt_for(public_pem: str, payload: dict) -> bytes:
    pub = serialization.load_pem_public_key(public_pem.encode("ascii"))
    return pub.encrypt(json.dumps(payload).encode(), padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None))


def test_keypair_roundtrip():
    private, pem = keybroker.generate_keypair()
    blob = _encrypt_for(pem, {"base_url": "https://llm.example", "api_key": "sk-test-1234567890", "mode": "per-developer", "developer": "priya"})
    cfg = keybroker.decrypt_config(private, blob)
    assert cfg.api_key == "sk-test-1234567890" and cfg.base_url == "https://llm.example" and cfg.mode == "per-developer" and cfg.developer == "priya"
    other, _ = keybroker.generate_keypair()
    with pytest.raises(keybroker.KeyBrokerError):
        keybroker.decrypt_config(other, blob)


def test_fetch_config_end_to_end():
    state: dict = {"public_key": None, "request_id": None, "polls": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        p = request.url.path
        if p.endswith("/actions/workflows/key-broker.yml/dispatches"):
            body = json.loads(request.content)
            state["public_key"] = body["inputs"]["public_key"]
            state["request_id"] = body["inputs"]["request_id"]
            assert body["ref"] == "main"
            return httpx.Response(204)
        if p.endswith("/actions/runs"):
            state["polls"] += 1
            status = "in_progress" if state["polls"] < 2 else "completed"
            return httpx.Response(200, json={"workflow_runs": [
                {"id": 99, "display_title": "key-broker other", "status": "completed", "conclusion": "success"},
                {"id": 42, "display_title": f"key-broker {state['request_id']}", "status": status, "conclusion": "success" if status == "completed" else None, "html_url": "https://x"},
            ]})
        if p.endswith("/actions/runs/42/artifacts"):
            return httpx.Response(200, json={"artifacts": [{"id": 7, "name": f"key-{state['request_id']}"}]})
        if p.endswith("/actions/artifacts/7/zip"):
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w") as zf:
                zf.writestr("config.enc", _encrypt_for(state["public_key"], {"base_url": "https://llm.example", "api_key": "sk-org-key-abcdefgh"}))
            return httpx.Response(200, content=buf.getvalue())
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    messages: list[str] = []
    cfg = keybroker.fetch_config("tok", "org/ai-sdlc-gate", out=messages.append, sleep=lambda s: None, client=client)
    assert cfg.api_key == "sk-org-key-abcdefgh" and cfg.base_url == "https://llm.example"
    assert state["polls"] >= 2 and any("received" in m for m in messages)


def test_fetch_config_reports_missing_workflow_and_failed_run():
    def handler_404(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"message": "Not Found"})

    with pytest.raises(keybroker.KeyBrokerError) as exc:
        keybroker.fetch_config("tok", "org/x", sleep=lambda s: None, client=httpx.Client(transport=httpx.MockTransport(handler_404)))
    assert "not found" in str(exc.value)

    def handler_fail(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/dispatches"):
            return httpx.Response(204)
        rid = json.loads(request.content)["inputs"]["request_id"] if request.content else None
        return httpx.Response(200, json={"workflow_runs": [{"id": 1, "display_title": "key-broker " + "0" * 32, "status": "completed", "conclusion": "failure", "html_url": "u"}]})

    with pytest.raises(keybroker.KeyBrokerError) as exc:
        keybroker.fetch_config("tok", "org/x", sleep=lambda s: None, timeout_s=1, poll_s=0.3, client=httpx.Client(transport=httpx.MockTransport(handler_fail)))
    assert "did not start" in str(exc.value)


def test_secrets_store_roundtrip_with_fake_keyring(tmp_path, monkeypatch):
    from sdlc_gate import secrets_store

    monkeypatch.setenv("SDLC_GATE_HOME", str(tmp_path))
    monkeypatch.delenv("LITELLM_API_KEY", raising=False)
    monkeypatch.delenv("LITELLM_BASE_URL", raising=False)

    class FakeKeyring:
        store: dict = {}

        def set_password(self, service, account, value):
            self.store[(service, account)] = value

        def get_password(self, service, account):
            return self.store.get((service, account))

        def delete_password(self, service, account):
            self.store.pop((service, account), None)

    fake = FakeKeyring()
    monkeypatch.setattr(secrets_store, "_keyring", lambda: fake)
    st = secrets_store.store("https://llm.example/", "sk-personal-key-1234", mode="per-developer", developer="priya")
    assert st.backend == "keyring" and not (tmp_path / "env").exists() and (tmp_path / "config.json").is_file()
    loaded = secrets_store.load()
    assert loaded and loaded.backend == "keyring" and loaded.api_key == "sk-personal-key-1234" and loaded.base_url == "https://llm.example"
    secrets_store.clear()
    assert secrets_store.load() is None

    # Without an OS store the client falls back to a private file and says so.
    monkeypatch.setattr(secrets_store, "_keyring", lambda: None)
    st = secrets_store.store("https://llm.example", "sk-fallback-key-1234")
    assert st.backend == "file" and (tmp_path / "env").is_file()
    assert secrets_store.load().api_key == "sk-fallback-key-1234"

    # The LLM client resolves the key from the store when the environment does not provide one.
    from sdlc_gate.config import Config
    from sdlc_gate.llm import LLMClient

    client = LLMClient.from_config(Config())
    assert client.api_key == "sk-fallback-key-1234" and client.base_url == "https://llm.example"
