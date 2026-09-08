"""OpenAI-compatible chat client for the organisation's model gateway proxy.

Design notes
- Only the `/v1/chat/completions` endpoint is used; works with any model model gateway exposes.
- All model output is treated as untrusted data: it is parsed as JSON and validated by
  callers, never executed or interpolated into commands.
- Retries with exponential backoff on 408/409/429/5xx and network errors, then fails over
  to the configured fallback models. Failure is surfaced as `LLMError` so the gate can
  fail closed.
"""
from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable

import httpx

from .config import Config

RETRY_STATUSES = {408, 409, 425, 429, 500, 502, 503, 504}
_KEY_TOKEN = re.compile(r"sk-[A-Za-z0-9_-]{16,}")


def normalize_api_key(raw: str) -> str:
    """Accept a model gateway virtual key pasted together with its display name ("Name: sk-...") and keep only the key."""
    raw = (raw or "").strip()
    if raw.startswith("sk-"):
        return raw
    m = _KEY_TOKEN.search(raw)
    return m.group(0) if m else raw


class LLMError(RuntimeError):
    pass


# Default model for review and arbitration when neither LITELLM_MODELS nor the stored client configuration names one.
_BUILTIN_MODELS = ["claude-opus-4-8", "claude-opus-4-8"]


def resolve_models(cfg: Config, stored_models: list[str] | None = None) -> tuple[str, str, list[str]]:
    """Return (review_model, judge_model, fallback_models) from env, stored configuration, policy, or built-ins."""
    llm = cfg.llm
    env_list = [m.strip() for m in os.environ.get(llm.get("models_env", "LITELLM_MODELS"), "").split(",") if m.strip()]
    names = env_list or list(stored_models or [])
    if not names:
        names = [m for m in (llm.get("review_model"), llm.get("judge_model"), *(llm.get("fallback_models") or [])) if m]
    if not names:
        names = list(_BUILTIN_MODELS)
    review = os.environ.get("SDLC_GATE_MODEL") or names[0]
    judge = os.environ.get("SDLC_JUDGE_MODEL") or (names[1] if len(names) > 1 else names[0])
    fallbacks = [m for m in names[2:] if m not in (review, judge)] if len(names) > 2 else [m for m in names if m not in (review,)]
    return review, judge, fallbacks


@dataclass
class LLMResponse:
    content: str
    model: str
    usage: dict[str, Any] = field(default_factory=dict)
    latency_s: float = 0.0


def extract_json(text: str) -> Any:
    """Parse JSON from a model reply, tolerating code fences and surrounding prose."""
    if text is None:
        raise LLMError("Empty model response")
    s = text.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", s, flags=re.S | re.I)
    if fence:
        s = fence.group(1).strip()
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass
    start = s.find("{")
    end = s.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(s[start : end + 1])
        except json.JSONDecodeError as exc:
            raise LLMError(f"Model returned invalid JSON: {exc}") from exc
    raise LLMError("Model response did not contain a JSON object")


class LLMClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        fallback_models: list[str] | None = None,
        timeout: float = 180.0,
        max_retries: int = 3,
        temperature: float = 0.0,
        max_output_tokens: int = 8000,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not base_url:
            raise LLMError("model gateway base URL is not configured (LITELLM_BASE_URL)")
        if not api_key:
            raise LLMError("model gateway API key is not configured (LITELLM_API_KEY)")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.fallback_models = [m for m in (fallback_models or []) if m and m != model]
        self.timeout = timeout
        self.max_retries = max(0, int(max_retries))
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens
        self._sleep = sleep
        self._client = httpx.Client(timeout=httpx.Timeout(timeout), transport=transport)
        self.total_usage: dict[str, int] = {"prompt_tokens": 0, "completion_tokens": 0}

    # ------------------------------------------------------------------ factory
    @classmethod
    def from_config(cls, cfg: Config, model: str | None = None, **kwargs: Any) -> "LLMClient":
        llm = cfg.llm
        from . import secrets_store  # local import: keyring is optional at import time

        stored = secrets_store.load()
        base_url = os.environ.get(llm.get("base_url_env", "LITELLM_BASE_URL"), "") or (stored.base_url if stored else "")
        api_key = normalize_api_key(os.environ.get(llm.get("api_key_env", "LITELLM_API_KEY"), "") or (stored.api_key if stored else ""))
        review, judge, fallbacks = resolve_models(cfg, stored.models if stored else None)
        chosen = model or review
        if model == "judge":
            chosen = judge
        return cls(
            base_url=base_url,
            api_key=api_key,
            model=chosen,
            fallback_models=fallbacks,
            timeout=float(llm.get("timeout_seconds", 180)),
            max_retries=int(llm.get("max_retries", 3)),
            temperature=float(llm.get("temperature", 0)),
            max_output_tokens=int(llm.get("max_output_tokens", 8000)),
            **kwargs,
        )

    # ------------------------------------------------------------------ helpers
    def _url(self) -> str:
        if self.base_url.endswith("/v1"):
            return f"{self.base_url}/chat/completions"
        return f"{self.base_url}/v1/chat/completions"

    def _post(self, payload: dict[str, Any]) -> httpx.Response:
        return self._client.post(
            self._url(),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "User-Agent": "sdlc-gate/1.0",
            },
            json=payload,
        )

    def _attempt(self, model: str, messages: list[dict[str, str]], json_mode: bool) -> LLMResponse:
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_output_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            started = time.monotonic()
            try:
                resp = self._post(payload)
            except httpx.HTTPError as exc:
                last_error = exc
            else:
                if resp.status_code == 400 and json_mode and "response_format" in payload:
                    # Some models behind the proxy do not accept response_format; retry without it.
                    payload.pop("response_format", None)
                    continue
                if resp.status_code in RETRY_STATUSES:
                    last_error = LLMError(f"{model}: HTTP {resp.status_code}: {resp.text[:300]}")
                elif resp.status_code >= 400:
                    raise LLMError(f"{model}: HTTP {resp.status_code}: {resp.text[:500]}")
                else:
                    data = resp.json()
                    try:
                        content = data["choices"][0]["message"]["content"]
                    except (KeyError, IndexError, TypeError) as exc:
                        raise LLMError(f"{model}: unexpected response shape: {str(data)[:300]}") from exc
                    usage = data.get("usage") or {}
                    self.total_usage["prompt_tokens"] += int(usage.get("prompt_tokens") or 0)
                    self.total_usage["completion_tokens"] += int(usage.get("completion_tokens") or 0)
                    return LLMResponse(
                        content=content or "",
                        model=data.get("model") or model,
                        usage=usage,
                        latency_s=time.monotonic() - started,
                    )
            if attempt < self.max_retries:
                self._sleep(min(30.0, 2.0 ** attempt))
        raise LLMError(f"{model}: exhausted retries: {last_error}")

    # ------------------------------------------------------------------ public
    def chat(self, system: str, user: str, json_mode: bool = True) -> LLMResponse:
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        errors: list[str] = []
        for model in [self.model, *self.fallback_models]:
            try:
                return self._attempt(model, messages, json_mode)
            except LLMError as exc:
                errors.append(str(exc))
        raise LLMError("All models failed: " + " | ".join(errors))

    def chat_json(self, system: str, user: str) -> tuple[dict[str, Any], LLMResponse]:
        resp = self.chat(system, user, json_mode=True)
        data = extract_json(resp.content)
        if not isinstance(data, dict):
            raise LLMError("Model returned JSON that is not an object")
        return data, resp

    def close(self) -> None:
        self._client.close()


class StaticLLM:
    """Deterministic stand-in used by tests and `--offline` dry runs."""

    def __init__(self, responder: Callable[[str, str], dict[str, Any]] | None = None, model: str = "offline") -> None:
        self.responder = responder or (lambda system, user: {"findings": [], "summary": "offline"})
        self.model = model
        self.total_usage = {"prompt_tokens": 0, "completion_tokens": 0}
        self.calls: list[tuple[str, str]] = []

    def chat_json(self, system: str, user: str) -> tuple[dict[str, Any], LLMResponse]:
        self.calls.append((system, user))
        data = self.responder(system, user)
        return data, LLMResponse(content=json.dumps(data), model=self.model)

    def chat(self, system: str, user: str, json_mode: bool = True) -> LLMResponse:
        _, resp = self.chat_json(system, user)
        return resp

    def close(self) -> None:
        return None
