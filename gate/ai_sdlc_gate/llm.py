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


def describe_failure(status: int, body: str) -> str:
    """Developer-facing reason for a gateway failure.

    Deliberately never echoes the response body: gateway errors name the model, the key label and the provider,
    none of which may reach a developer's terminal or report. The full body is not logged anywhere either.
    """
    low = (body or "").lower()
    if status == 429 and "budget" in low:
        return "the review service has reached its usage budget; ask the gate administrators to raise it"
    if status == 429:
        return "the review service is rate limited; try again in a minute"
    if status in (401, 403):
        return "the review service rejected this machine's credential; run: ai-sdlc-gate configure"
    if status == 404:
        return "the review service did not recognise the request (configuration out of date); run: ai-sdlc-gate configure"
    if status == 400:
        return "the review service rejected the request"
    if status >= 500:
        return f"the review service is unavailable (HTTP {status})"
    return f"HTTP {status}"


def _is_final(status: int, body: str) -> bool:
    """A 429 caused by an exhausted budget does not recover on retry; stop immediately instead of backing off."""
    return status == 429 and "budget" in (body or "").lower()
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


_BLOCKED_SCHEMES = {"file", "ftp", "gopher", "data", "javascript"}
# Link-local cloud metadata endpoints that must never receive review traffic.
_BLOCKED_HOSTS = {"169.254.169.254", "metadata.google.internal", "100.100.100.200"}


def validate_base_url(url: str) -> str:
    """Reject gateway URLs that are not HTTPS to a routable host (blocks file://, IMDS and scheme smuggling)."""
    from urllib.parse import urlparse

    u = (url or "").strip()
    parsed = urlparse(u)
    if parsed.scheme.lower() in _BLOCKED_SCHEMES:
        raise LLMError(f"gateway base URL scheme '{parsed.scheme}' is not allowed")
    if parsed.scheme.lower() not in ("https", "http"):
        raise LLMError("gateway base URL must be http(s)")
    host = (parsed.hostname or "").lower()
    if not host:
        raise LLMError("gateway base URL has no host")
    if host in _BLOCKED_HOSTS or host.startswith("169.254."):
        raise LLMError("gateway base URL points at a link-local/metadata address, which is not allowed")
    if parsed.scheme.lower() == "http" and host not in ("localhost", "127.0.0.1", "::1"):
        raise LLMError("gateway base URL must use https (http is only allowed for localhost)")
    return u


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
    # Environment overrides are only honoured when they name a model already in the configured set; this stops
    # a CI-set variable from silently substituting an arbitrary (and possibly unreviewed) model.
    known = set(names)
    env_review = os.environ.get("AI_SDLC_GATE_MODEL", "").strip()
    review = env_review if env_review in known else names[0]
    env_judge = os.environ.get("AI_SDLC_JUDGE_MODEL", "").strip()
    judge = env_judge if env_judge in known else (names[1] if len(names) > 1 else names[0])
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
        self.base_url = validate_base_url(base_url).rstrip("/")
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
                "User-Agent": "ai-sdlc-gate/1.0",
            },
            json=payload,
        )

    def _attempt(self, model: str, messages: list[dict[str, str]], json_mode: bool) -> LLMResponse:
        # Errors are labelled by role, never by model name: the model must not be identifiable from the client.
        label = "review model" if model == self.model else "fallback model"
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
                last_error = LLMError(f"could not reach the review service ({exc.__class__.__name__})")
            else:
                if resp.status_code == 400:
                    # Some models behind the gateway reject particular parameters; drop the offending one and retry.
                    body = resp.text
                    if "temperature" in payload and "temperature" in body:
                        payload.pop("temperature", None)
                        continue
                    if "response_format" in payload and ("response_format" in body or "json" in body.lower()):
                        payload.pop("response_format", None)
                        continue
                    if "max_tokens" in payload and "max_tokens" in body:
                        payload["max_completion_tokens"] = payload.pop("max_tokens")
                        continue
                if resp.status_code >= 400 and _is_final(resp.status_code, resp.text):
                    raise LLMError(f"{label}: {describe_failure(resp.status_code, resp.text)}")
                if resp.status_code in RETRY_STATUSES:
                    last_error = LLMError(describe_failure(resp.status_code, resp.text))
                elif resp.status_code >= 400:
                    raise LLMError(f"{label}: {describe_failure(resp.status_code, resp.text)}")
                else:
                    data = resp.json()
                    try:
                        content = data["choices"][0]["message"]["content"]
                    except (KeyError, IndexError, TypeError) as exc:
                        raise LLMError(f"{label}: the review service returned an unexpected response") from exc
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
        raise LLMError(f"{label}: gave up after {self.max_retries + 1} attempts: {last_error}")

    # ------------------------------------------------------------------ public
    def chat(self, system: str, user: str, json_mode: bool = True) -> LLMResponse:
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        errors: list[str] = []
        for model in [self.model, *self.fallback_models]:
            try:
                return self._attempt(model, messages, json_mode)
            except LLMError as exc:
                errors.append(str(exc))
        # One reason is enough for the developer; identical fallback failures would only repeat it.
        unique: list[str] = []
        for e in errors:
            if e not in unique:
                unique.append(e)
        raise LLMError("; ".join(unique))

    def chat_json(self, system: str, user: str) -> tuple[dict[str, Any], LLMResponse]:
        resp = self.chat(system, user, json_mode=True)
        data = extract_json(resp.content)
        if not isinstance(data, dict):
            raise LLMError("Model returned JSON that is not an object")
        return data, resp

    def close(self) -> None:
        self._client.close()


class VertexClient:
    """Anthropic Claude on Google Vertex AI, with the same surface as LLMClient.

    Authentication uses a Google service account (delivered by the key broker and kept in the OS credential store,
    never on disk in the clear); the client mints short-lived access tokens from it locally. The endpoint, project,
    region and model name all live inside the encrypted record, so a developer cannot learn which model or gateway
    is used by reading the repository or their installation. Requests use the native Anthropic Messages format on
    the `:rawPredict` endpoint; all output is treated as untrusted data and parsed as JSON by the caller.
    """

    ANTHROPIC_VERSION = "vertex-2023-10-16"
    SCOPES = ("https://www.googleapis.com/auth/cloud-platform",)

    def __init__(
        self,
        project: str,
        location: str,
        credentials: dict,
        model: str,
        fallback_models: list[str] | None = None,
        timeout: float = 180.0,
        max_retries: int = 3,
        temperature: float = 0.0,
        max_output_tokens: int = 8000,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        token_fn: Callable[[], tuple[str, float]] | None = None,
    ) -> None:
        if not project:
            raise LLMError("the review engine is not configured (no project); run: ai-sdlc-gate configure")
        if not credentials:
            raise LLMError("the review engine credential is missing; run: ai-sdlc-gate configure")
        self.project = project
        self.location = (location or "us-east5").strip()
        self.credentials = credentials
        self.model = model
        self.fallback_models = [m for m in (fallback_models or []) if m and m != model]
        self.timeout = timeout
        self.max_retries = max(0, int(max_retries))
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens
        self._sleep = sleep
        self._client = httpx.Client(timeout=httpx.Timeout(timeout), transport=transport)
        self._token_fn = token_fn
        self._tok: str | None = None
        self._tok_exp: float = 0.0
        self.total_usage: dict[str, int] = {"prompt_tokens": 0, "completion_tokens": 0}

    # ------------------------------------------------------------------ factory
    @classmethod
    def from_config(cls, cfg: Config, stored: Any, model: str | None = None, **kwargs: Any) -> "VertexClient":
        review, judge, fallbacks = resolve_models(cfg, getattr(stored, "models", None) or None)
        chosen = judge if model == "judge" else (model or review)
        d = getattr(stored, "data", None) or {}
        llm = cfg.llm
        return cls(
            project=str(d.get("project") or ""),
            location=str(d.get("location") or "us-east5"),
            credentials=d.get("credentials") or {},
            model=chosen,
            fallback_models=fallbacks,
            timeout=float(llm.get("timeout_seconds", 180)),
            max_retries=int(llm.get("max_retries", 3)),
            temperature=float(llm.get("temperature", 0)),
            max_output_tokens=int(llm.get("max_output_tokens", 8000)),
            **kwargs,
        )

    # ------------------------------------------------------------------ auth
    def _mint_token(self) -> tuple[str, float]:
        # google-auth is imported lazily so the package is only needed on machines that use the Vertex provider.
        from google.auth.transport.requests import Request
        from google.oauth2 import service_account

        creds = service_account.Credentials.from_service_account_info(self.credentials, scopes=list(self.SCOPES))
        creds.refresh(Request())
        exp = creds.expiry.timestamp() if getattr(creds, "expiry", None) else time.time() + 3000
        if not creds.token:
            raise LLMError("could not obtain an access token for the review service")
        return creds.token, exp

    def _token(self) -> str:
        now = time.time()
        if self._tok and now < self._tok_exp - 60:
            return self._tok
        try:
            self._tok, self._tok_exp = (self._token_fn or self._mint_token)()
        except LLMError:
            raise
        except Exception as exc:  # noqa: BLE001 - never leak credential internals
            raise LLMError("the review engine credential was rejected; run: ai-sdlc-gate configure") from exc
        return self._tok

    # ------------------------------------------------------------------ helpers
    def _host(self) -> str:
        return "aiplatform.googleapis.com" if self.location == "global" else f"{self.location}-aiplatform.googleapis.com"

    def _url(self, model: str) -> str:
        return (
            f"https://{self._host()}/v1/projects/{self.project}/locations/{self.location}"
            f"/publishers/anthropic/models/{model}:rawPredict"
        )

    def _post(self, model: str, payload: dict[str, Any]) -> httpx.Response:
        return self._client.post(
            self._url(model),
            headers={
                "Authorization": f"Bearer {self._token()}",
                "Content-Type": "application/json; charset=utf-8",
                "User-Agent": "ai-sdlc-gate/1.0",
            },
            json=payload,
        )

    def _attempt(self, model: str, system: str, user: str, json_mode: bool) -> LLMResponse:
        label = "review model" if model == self.model else "fallback model"
        messages: list[dict[str, Any]] = [{"role": "user", "content": user}]
        if json_mode:
            # Prefill the assistant turn with "{" so the model must emit a JSON object (Anthropic has no json mode).
            messages.append({"role": "assistant", "content": "{"})
        payload: dict[str, Any] = {
            "anthropic_version": self.ANTHROPIC_VERSION,
            "max_tokens": self.max_output_tokens,
            "messages": messages,
            "temperature": self.temperature,
        }
        if system:
            payload["system"] = system
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            started = time.monotonic()
            try:
                resp = self._post(model, payload)
            except httpx.HTTPError as exc:
                last_error = LLMError(f"could not reach the review service ({exc.__class__.__name__})")
            else:
                if resp.status_code == 400 and "temperature" in payload and "temperature" in resp.text.lower():
                    payload.pop("temperature", None)
                    continue
                if resp.status_code >= 400 and _is_final(resp.status_code, resp.text):
                    raise LLMError(f"{label}: {describe_failure(resp.status_code, resp.text)}")
                if resp.status_code in RETRY_STATUSES:
                    last_error = LLMError(describe_failure(resp.status_code, resp.text))
                elif resp.status_code >= 400:
                    raise LLMError(f"{label}: {describe_failure(resp.status_code, resp.text)}")
                else:
                    data = resp.json()
                    blocks = data.get("content") or []
                    text = "".join(b.get("text", "") for b in blocks if isinstance(b, dict) and b.get("type") == "text")
                    if json_mode:
                        text = text if text.lstrip().startswith("{") else "{" + text
                    usage = data.get("usage") or {}
                    self.total_usage["prompt_tokens"] += int(usage.get("input_tokens") or 0)
                    self.total_usage["completion_tokens"] += int(usage.get("output_tokens") or 0)
                    return LLMResponse(content=text or "", model=model, usage=usage, latency_s=time.monotonic() - started)
            if attempt < self.max_retries:
                self._sleep(min(30.0, 2.0 ** attempt))
        raise LLMError(f"{label}: gave up after {self.max_retries + 1} attempts: {last_error}")

    # ------------------------------------------------------------------ public
    def chat(self, system: str, user: str, json_mode: bool = True) -> LLMResponse:
        errors: list[str] = []
        for model in [self.model, *self.fallback_models]:
            try:
                return self._attempt(model, system, user, json_mode)
            except LLMError as exc:
                errors.append(str(exc))
        unique: list[str] = []
        for e in errors:
            if e not in unique:
                unique.append(e)
        raise LLMError("; ".join(unique))

    def chat_json(self, system: str, user: str) -> tuple[dict[str, Any], LLMResponse]:
        resp = self.chat(system, user, json_mode=True)
        data = extract_json(resp.content)
        if not isinstance(data, dict):
            raise LLMError("Model returned JSON that is not an object")
        return data, resp

    def close(self) -> None:
        self._client.close()


def build_client(cfg: Config, model: str | None = None, **kwargs: Any) -> Any:
    """Return the review client for the configured provider (Vertex AI or an OpenAI-compatible gateway)."""
    from . import secrets_store  # local import: keyring is optional at import time

    stored = secrets_store.load()
    if stored is not None and stored.provider == "vertex":
        return VertexClient.from_config(cfg, stored, model=model, **kwargs)
    return LLMClient.from_config(cfg, model=model, **kwargs)



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
