"""Verify the caller's Microsoft Entra token and enforce that they are an @og1o.in account.

This runs on every request to the SDLC endpoint, before any model call. It is the server-side gate that a client
cannot bypass: a token that is not from the configured tenant, not for the configured audience, expired, or whose
account is not in an allowed domain is rejected, so no non-og1o.in caller ever reaches the model.
"""
from __future__ import annotations

import re
from typing import Any

import jwt
from jwt import PyJWKClient

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_TENANT_UUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")


class AuthError(Exception):
    """Raised when a token is invalid or the account is not allowed. The message is for logs, never the client."""


def verify_entra_token(
    token: str,
    tenant: str,
    audience: str,
    allowed_domains: list[str],
    authority: str = "https://login.microsoftonline.com",
    jwks_client: Any | None = None,
) -> dict[str, str]:
    """Return {email, name, tid} for a valid @allowed-domain token, else raise AuthError.

    `jwks_client` is injectable for tests; in production the tenant's JWKS is fetched and cached.
    """
    if not _TENANT_UUID.match(tenant or ""):
        raise AuthError("server misconfigured: tenant must be a GUID")
    if not audience:
        raise AuthError("server misconfigured: audience is empty")
    if not allowed_domains:
        raise AuthError("server misconfigured: no allowed domains")

    issuer = f"{authority.rstrip('/')}/{tenant}/v2.0"
    jwks = jwks_client or PyJWKClient(f"{authority.rstrip('/')}/{tenant}/discovery/v2.0/keys")
    try:
        signing_key = jwks.get_signing_key_from_jwt(token).key
        claims = jwt.decode(token, signing_key, algorithms=["RS256"], audience=audience, issuer=issuer)
    except jwt.PyJWTError as exc:
        raise AuthError(f"token verification failed: {exc}") from exc

    tid = str(claims.get("tid") or "")
    if tid.lower() != tenant.lower():
        raise AuthError("token was issued for a different tenant")
    email = str(claims.get("preferred_username") or claims.get("email") or claims.get("upn") or "").strip().lower()
    if not EMAIL_RE.match(email):
        raise AuthError("token carries no usable e-mail")
    domain = email.rsplit("@", 1)[1]
    if domain not in {d.lower().lstrip("@") for d in allowed_domains}:
        raise AuthError(f"{email} is not in an allowed organisation domain")
    return {"email": email, "name": str(claims.get("name") or "").strip(), "tid": tid}
