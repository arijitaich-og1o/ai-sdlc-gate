"""Obtain the LiteLLM configuration from the central repository's GitHub secrets.

GitHub secrets are only readable inside a workflow run, so the client asks a workflow to hand them over:

1. generate an RSA-3072 key pair in memory;
2. trigger `key-broker.yml` (workflow_dispatch) with a random request id and the public key, using the
   developer's own GitHub credential;
3. wait for the run named `key-broker <request id>` to finish and download its artifact;
4. decrypt with the private key and store the configuration in `~/.sdlc-gate/env` (user-only permissions).

The plaintext key exists only on the runner and on the requesting machine. Anyone able to trigger the workflow
must have write access to the repository, which is the same access needed to open a skill challenge.
"""
from __future__ import annotations

import io
import json
import secrets
import time
import zipfile
from dataclasses import dataclass
from typing import Any, Callable

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

WORKFLOW_FILE = "key-broker.yml"


class KeyBrokerError(RuntimeError):
    pass


@dataclass
class LiteLLMConfig:
    base_url: str
    api_key: str


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "sdlc-gate/1.0",
    }


def generate_keypair() -> tuple[rsa.RSAPrivateKey, str]:
    private = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    pem = private.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode("ascii")
    return private, pem


def decrypt_config(private: rsa.RSAPrivateKey, blob: bytes) -> LiteLLMConfig:
    try:
        plain = private.decrypt(blob, padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None))
        data = json.loads(plain.decode("utf-8"))
    except (ValueError, json.JSONDecodeError) as exc:
        raise KeyBrokerError("could not decrypt the configuration returned by the key broker") from exc
    key = str(data.get("api_key") or "").strip()
    if not key:
        raise KeyBrokerError("key broker returned an empty API key")
    return LiteLLMConfig(base_url=str(data.get("base_url") or "").strip(), api_key=key)


def fetch_config(
    token: str,
    repo: str,
    ref: str = "main",
    api_base: str = "https://api.github.com",
    timeout_s: int = 300,
    poll_s: float = 5.0,
    out: Callable[[str], None] = lambda m: None,
    sleep: Callable[[float], None] = time.sleep,
    client: httpx.Client | None = None,
) -> LiteLLMConfig:
    http = client or httpx.Client(timeout=60, follow_redirects=True)
    hdr = _headers(token)
    request_id = secrets.token_hex(16)
    private, public_pem = generate_keypair()
    try:
        resp = http.post(
            f"{api_base}/repos/{repo}/actions/workflows/{WORKFLOW_FILE}/dispatches",
            headers=hdr,
            json={"ref": ref, "inputs": {"request_id": request_id, "public_key": public_pem}},
        )
        if resp.status_code == 404:
            raise KeyBrokerError(f"key broker workflow not found in {repo}@{ref}, or your GitHub credential has no access to that repository")
        if resp.status_code not in (204, 200):
            raise KeyBrokerError(f"could not start the key broker: HTTP {resp.status_code}: {resp.text[:200]}")
        out(f"requested the LiteLLM configuration from {repo} (request {request_id[:8]}...)")

        deadline = time.monotonic() + timeout_s
        run: dict[str, Any] | None = None
        while time.monotonic() < deadline:
            sleep(poll_s)
            runs = http.get(f"{api_base}/repos/{repo}/actions/runs", headers=hdr, params={"event": "workflow_dispatch", "per_page": 30}).json()
            for r in runs.get("workflow_runs") or []:
                if request_id in str(r.get("display_title") or r.get("name") or ""):
                    run = r
                    break
            if run and run.get("status") == "completed":
                break
            if run and run.get("status") != "completed":
                out(f"waiting for the key broker run ({run.get('status')})")
        if run is None:
            raise KeyBrokerError("the key broker run did not start in time (check Actions permissions on the repository)")
        if run.get("conclusion") != "success":
            raise KeyBrokerError(f"key broker run finished with {run.get('conclusion')}: {run.get('html_url')}")

        arts = http.get(f"{api_base}/repos/{repo}/actions/runs/{run['id']}/artifacts", headers=hdr).json()
        art = next((a for a in arts.get("artifacts") or [] if a.get("name") == f"key-{request_id}"), None)
        if art is None:
            raise KeyBrokerError("key broker run produced no artifact")
        zbytes = http.get(f"{api_base}/repos/{repo}/actions/artifacts/{art['id']}/zip", headers=hdr).content
        try:
            with zipfile.ZipFile(io.BytesIO(zbytes)) as zf:
                blob = zf.read("config.enc")
        except (zipfile.BadZipFile, KeyError) as exc:
            raise KeyBrokerError("key broker artifact is malformed") from exc
        cfg = decrypt_config(private, blob)
        out("LiteLLM configuration received and decrypted")
        return cfg
    finally:
        if client is None:
            http.close()
