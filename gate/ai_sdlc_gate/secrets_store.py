"""Where the client keeps the model-gateway configuration (endpoint, key, model names).

Everything sensitive is stored as one encrypted record in the operating system credential store through
`keyring`: Windows Credential Manager (DPAPI, bound to the signed-in user), macOS Keychain, Linux Secret
Service / KWallet. Nothing about the gateway, its address or the models used is written to a readable file.

Fallback for headless Linux machines without a secret service: `~/.ai-sdlc-gate/env.enc`, encrypted with a
random key that is itself kept in a user-only file next to it. That only protects against casual reading;
the client reports it as the weaker option.
"""
from __future__ import annotations

import base64
import json
import os
import stat
from dataclasses import dataclass, field
from pathlib import Path

from .identity import sdlc_home

SERVICE = "ai-sdlc-gate"
ACCOUNT = "gateway-config"


@dataclass
class Stored:
    base_url: str = ""
    api_key: str = ""
    models: list[str] = field(default_factory=list)
    backend: str = ""  # keyring | file | env
    mode: str = ""
    # provider selects the review backend: "openai" (an OpenAI-compatible gateway with a bearer key) or "vertex"
    # (Anthropic on Google Vertex AI, authenticated with a service account). `data` holds the provider-specific
    # secret material for vertex ({project, location, credentials:<service-account JSON>}); it is part of the one
    # encrypted record and is never written anywhere in the clear.
    provider: str = "openai"
    data: dict = field(default_factory=dict)

    def is_ready(self) -> bool:
        if self.provider == "vertex":
            return bool(self.data and self.data.get("credentials") and self.data.get("project"))
        return bool(self.base_url and self.api_key)

    def to_json(self) -> str:
        return json.dumps({
            "provider": self.provider, "base_url": self.base_url, "api_key": self.api_key,
            "models": self.models, "mode": self.mode, "data": self.data,
        })

    @classmethod
    def from_json(cls, text: str, backend: str) -> "Stored | None":
        try:
            d = json.loads(text)
        except (TypeError, json.JSONDecodeError):
            return None
        if not isinstance(d, dict):
            return None
        provider = str(d.get("provider") or "openai")
        data = d.get("data") if isinstance(d.get("data"), dict) else {}
        rec = cls(base_url=str(d.get("base_url") or ""), api_key=str(d.get("api_key") or ""),
                  models=[str(m) for m in d.get("models") or []], backend=backend,
                  mode=str(d.get("mode") or ""), provider=provider, data=data)
        return rec if rec.is_ready() else None


def _keyring():
    try:
        import keyring  # noqa: WPS433 - optional at runtime
    except Exception:  # noqa: BLE001
        return None
    try:
        name = type(keyring.get_keyring()).__name__.lower()
        if "fail" in name or "null" in name:
            return None
    except Exception:  # noqa: BLE001
        return None
    return keyring


def _enc_path() -> Path:
    return sdlc_home() / "env.enc"


def _enc_key_path() -> Path:
    return sdlc_home() / ".k"


def _lock_down(path: Path) -> None:
    """Restrict a file/dir to the current user only, on POSIX and Windows."""
    if os.name == "nt":
        try:
            import subprocess

            user = os.environ.get("USERNAME") or ""
            if user:
                # Reset inheritance and grant only the current user full control.
                subprocess.run(
                    ["icacls", str(path), "/inheritance:r", "/grant:r", f"{user}:F"],
                    capture_output=True,
                    check=False,
                )
        except Exception:  # noqa: BLE001
            pass
    else:
        try:
            if path.is_dir():
                os.chmod(path, stat.S_IRWXU)  # 0700
            else:
                os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)  # 0600
        except OSError:
            pass


def _write_private(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _lock_down(path.parent)
    # Create with no bytes first so the restrictive mode is applied before secret data is written.
    path.write_bytes(b"")
    _lock_down(path)
    path.write_bytes(data)
    _lock_down(path)


def _fernet():
    from cryptography.fernet import Fernet

    kp = _enc_key_path()
    if kp.is_file():
        key = kp.read_bytes().strip()
    else:
        key = Fernet.generate_key()
        _write_private(kp, key)
    return Fernet(key)


def store(base_url: str = "", api_key: str = "", models: list[str] | None = None, mode: str = "",
          provider: str = "openai", data: dict | None = None) -> Stored:
    rec = Stored(base_url=(base_url or "").rstrip("/"), api_key=api_key, models=list(models or []), mode=mode,
                 provider=provider, data=dict(data or {}))
    kr = _keyring()
    if kr is not None:
        try:
            kr.set_password(SERVICE, ACCOUNT, rec.to_json())
            for legacy in (_enc_path(), sdlc_home() / "env", sdlc_home() / "config.json"):
                if legacy.exists():
                    legacy.unlink()  # never leave another copy behind
            rec.backend = "keyring"
            return rec
        except Exception:  # noqa: BLE001 - fall back to the encrypted file
            pass
    # Windows Credential Manager caps a single entry at ~2.5 KB, which a Vertex service-account record exceeds, so the
    # write falls back to the encrypted file. Remove any earlier keyring entry so a stale record cannot shadow this one.
    if kr is not None:
        try:
            kr.delete_password(SERVICE, ACCOUNT)
        except Exception:  # noqa: BLE001
            pass
    _write_private(_enc_path(), _fernet().encrypt(rec.to_json().encode("utf-8")))
    legacy = sdlc_home() / "env"
    if legacy.exists():
        legacy.unlink()
    rec.backend = "file"
    return rec


def load() -> Stored | None:
    """Resolve the gateway configuration: environment first (CI), then the OS store, then the encrypted file."""
    sa = os.environ.get("VERTEX_SA_KEY", "").strip()
    proj = os.environ.get("VERTEX_PROJECT", "").strip()
    if sa and proj:
        try:
            creds = json.loads(sa)
        except json.JSONDecodeError:
            creds = None
        if isinstance(creds, dict):
            vmodels = [m.strip() for m in (os.environ.get("VERTEX_MODELS") or os.environ.get("LITELLM_MODELS") or "").split(",") if m.strip()]
            return Stored(provider="vertex", backend="env", mode="shared", models=vmodels,
                          data={"project": proj, "location": os.environ.get("VERTEX_LOCATION", "").strip() or "us-east5", "credentials": creds})
    env_key = os.environ.get("LITELLM_API_KEY", "").strip()
    env_url = os.environ.get("LITELLM_BASE_URL", "").strip()
    env_models = [m.strip() for m in os.environ.get("LITELLM_MODELS", "").split(",") if m.strip()]
    stored: Stored | None = None
    kr = _keyring()
    if kr is not None:
        try:
            raw = kr.get_password(SERVICE, ACCOUNT)
        except Exception:  # noqa: BLE001
            raw = None
        if raw:
            stored = Stored.from_json(raw, "keyring")
    if stored is None and _enc_path().is_file() and _enc_key_path().is_file():
        try:
            stored = Stored.from_json(_fernet().decrypt(_enc_path().read_bytes()).decode("utf-8"), "file")
        except Exception:  # noqa: BLE001
            stored = None
    if env_key:
        return Stored(base_url=env_url or (stored.base_url if stored else ""), api_key=env_key,
                      models=env_models or (stored.models if stored else []), backend="env")
    if stored is not None:
        if env_url:
            stored.base_url = env_url
        if env_models:
            stored.models = env_models
    return stored


def clear() -> None:
    kr = _keyring()
    if kr is not None:
        try:
            kr.delete_password(SERVICE, ACCOUNT)
        except Exception:  # noqa: BLE001
            pass
    for p in (_enc_path(), _enc_key_path(), sdlc_home() / "env", sdlc_home() / "config.json"):
        if p.exists():
            p.unlink()
