"""TLS trust for the gate's outbound HTTP calls.

Developer machines commonly sit behind a corporate TLS-inspection proxy that re-signs HTTPS with the
organisation's own root CA. That root is installed in the operating system trust store (by IT), but Python's
`httpx` verifies against its bundled `certifi` store by default, which does not contain it -- so every call
(the review endpoint, Microsoft sign-in, the key broker, metrics) fails with
`CERTIFICATE_VERIFY_FAILED: self-signed certificate in certificate chain`.

`ssl_context()` returns a context that trusts the OS store instead (Windows cert store, macOS keychain, or the
system bundle on Linux), so the gate works behind such a proxy with no per-machine configuration. An explicit CA
bundle can still be forced with AI_SDLC_GATE_CA_BUNDLE / SSL_CERT_FILE / REQUESTS_CA_BUNDLE, for the rarer case
where the CA is shipped as a file rather than installed in the store.
"""
from __future__ import annotations

import functools
import os
import ssl

_CA_ENV_VARS = ("AI_SDLC_GATE_CA_BUNDLE", "SSL_CERT_FILE", "REQUESTS_CA_BUNDLE")


@functools.lru_cache(maxsize=1)
def ssl_context() -> ssl.SSLContext:
    """A verifying TLS context that trusts the operating system's certificate store (shared, built once)."""
    ctx = ssl.create_default_context()  # loads the OS trust store on Windows, macOS and Linux
    for var in _CA_ENV_VARS:
        path = os.environ.get(var)
        if path and os.path.isfile(path):
            try:
                ctx.load_verify_locations(cafile=path)
            except ssl.SSLError:
                pass  # a malformed override must not disable TLS verification
    return ctx
