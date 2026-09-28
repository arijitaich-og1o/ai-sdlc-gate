"""The shared TLS context trusts the OS store and never silently disables verification."""
from __future__ import annotations

import ssl

from ai_sdlc_gate.httpcfg import ssl_context


def test_ssl_context_verifies_and_is_shared():
    ctx = ssl_context()
    assert isinstance(ctx, ssl.SSLContext)
    # It must always verify certificates and check hostnames — never a permissive context.
    assert ctx.verify_mode == ssl.CERT_REQUIRED
    assert ctx.check_hostname is True
    # Built once and shared across all HTTP clients.
    assert ssl_context() is ctx


def test_a_bad_ca_override_never_disables_verification(monkeypatch):
    monkeypatch.setenv("AI_SDLC_GATE_CA_BUNDLE", "/definitely/not/a/real/ca.pem")
    ssl_context.cache_clear()
    try:
        ctx = ssl_context()
        assert ctx.verify_mode == ssl.CERT_REQUIRED  # missing override is ignored, verification stays on
    finally:
        ssl_context.cache_clear()
