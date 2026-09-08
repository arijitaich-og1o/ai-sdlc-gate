"""Where the client keeps the LiteLLM key.

Preferred: the operating system credential store through `keyring` (Windows Credential Manager, macOS Keychain,
Linux Secret Service / KWallet). Nothing readable is left in any folder, and the value is protected by the OS
for the signed-in user. Fallback (headless Linux without a secret service): `~/.sdlc-gate/env` with 0600
permissions, which is explicitly reported as the weaker option.

The base URL is not secret and is kept in `~/.sdlc-gate/config.json`.
"""
from __future__ import annotations

import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path

from .identity import sdlc_home

SERVICE = "sdlc-gate"
ACCOUNT = "litellm-api-key"
DEFAULT_BASE_URL = "https://litellm-dev.dev.aime.osp-fine.de"


@dataclass
class Stored:
    base_url: str
    api_key: str
    backend: str  # keyring | file | env


def _keyring():
    try:
        import keyring  # noqa: WPS433 - optional at runtime
        from keyring.errors import KeyringError  # noqa: F401
    except Exception:  # noqa: BLE001
        return None
    try:
        backend = keyring.get_keyring()
        # The "fail" / "null" backends mean no usable OS store is available.
        name = type(backend).__name__.lower()
        if "fail" in name or "null" in name or "chainer" in name and not getattr(backend, "backends", None):
            return None
    except Exception:  # noqa: BLE001
        return None
    return keyring


def config_path() -> Path:
    return sdlc_home() / "config.json"


def env_path() -> Path:
    return sdlc_home() / "env"


def _write_private(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass


def store(base_url: str, api_key: str, mode: str = "", developer: str = "") -> Stored:
    base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
    _write_private(config_path(), json.dumps({"base_url": base_url, "mode": mode, "developer": developer}, indent=2))
    kr = _keyring()
    if kr is not None:
        try:
            kr.set_password(SERVICE, ACCOUNT, api_key)
            if env_path().exists():
                env_path().unlink()  # never leave a plaintext copy behind
            return Stored(base_url, api_key, "keyring")
        except Exception:  # noqa: BLE001 - fall back to the file
            pass
    _write_private(env_path(), f"export LITELLM_BASE_URL='{base_url}'\nexport LITELLM_API_KEY='{api_key}'\n")
    return Stored(base_url, api_key, "file")


def load() -> Stored | None:
    """Resolve the LiteLLM configuration: environment first, then the OS store, then the legacy env file."""
    env_key = os.environ.get("LITELLM_API_KEY", "").strip()
    env_url = os.environ.get("LITELLM_BASE_URL", "").strip()
    base_url = env_url
    if not base_url and config_path().is_file():
        try:
            base_url = str(json.loads(config_path().read_text(encoding="utf-8")).get("base_url") or "")
        except (OSError, json.JSONDecodeError):
            base_url = ""
    if env_key:
        return Stored(base_url or DEFAULT_BASE_URL, env_key, "env")
    kr = _keyring()
    if kr is not None:
        try:
            key = kr.get_password(SERVICE, ACCOUNT)
        except Exception:  # noqa: BLE001
            key = None
        if key:
            return Stored(base_url or DEFAULT_BASE_URL, key, "keyring")
    if env_path().is_file():
        values: dict[str, str] = {}
        for line in env_path().read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if line.startswith("export "):
                line = line[7:]
            if "=" in line:
                k, v = line.split("=", 1)
                values[k.strip()] = v.strip().strip("'\"")
        if values.get("LITELLM_API_KEY"):
            return Stored(values.get("LITELLM_BASE_URL") or base_url or DEFAULT_BASE_URL, values["LITELLM_API_KEY"], "file")
    return None


def clear() -> None:
    kr = _keyring()
    if kr is not None:
        try:
            kr.delete_password(SERVICE, ACCOUNT)
        except Exception:  # noqa: BLE001
            pass
    for p in (env_path(), config_path()):
        if p.exists():
            p.unlink()
