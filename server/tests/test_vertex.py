"""call_vertex builds the Vertex request: the reused system prompt is a prompt-cache breakpoint."""
from __future__ import annotations

import json

import httpx

from vertex import call_vertex


def test_system_prompt_is_marked_as_a_cache_breakpoint():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("authorization")
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"content": [{"type": "text", "text": "ok"}],
                                         "usage": {"input_tokens": 5, "output_tokens": 2}})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    out = call_vertex("proj", "europe-west1", "claude-haiku-4-5", "SYSTEM RULES", "the diff",
                      max_tokens=100, client=client, token_fn=lambda: "tok")
    client.close()

    body = seen["body"]
    # The system prompt is sent as a structured block carrying an ephemeral cache breakpoint, so repeat calls
    # with the same prefix read from cache instead of re-billing the full prompt.
    assert body["system"] == [{"type": "text", "text": "SYSTEM RULES", "cache_control": {"type": "ephemeral"}}]
    assert body["messages"] == [{"role": "user", "content": "the diff"}]
    assert body["max_tokens"] == 100
    assert seen["auth"] == "Bearer tok"
    assert seen["url"] == ("https://europe-west1-aiplatform.googleapis.com/v1/projects/proj/locations/"
                           "europe-west1/publishers/anthropic/models/claude-haiku-4-5:rawPredict")
    assert out["usage"]["input_tokens"] == 5


def test_empty_system_sends_no_system_field():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"content": [], "usage": {}})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    call_vertex("p", "europe-west1", "m", "", "u", client=client, token_fn=lambda: "t")
    client.close()
    # No system prompt -> no system field at all (nothing to cache).
    assert "system" not in seen["body"]
