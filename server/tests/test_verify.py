"""Token verification enforces tenant, audience, expiry and the @og1o.in domain."""
from __future__ import annotations

import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

import verify as v

TENANT = "8794e153-c3bd-4479-8bea-61aeaf167d5a"
AUD = "api://ai-sdlc-gate"
ISS = f"https://login.microsoftonline.com/{TENANT}/v2.0"
_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


class _JWKS:
    """Stand-in for PyJWKClient that returns our test signing key."""

    class _K:
        key = _KEY.public_key()

    def get_signing_key_from_jwt(self, token):
        return self._K()


def _token(**over) -> str:
    now = int(time.time())
    claims = {
        "iss": ISS, "aud": AUD, "tid": TENANT, "iat": now, "exp": now + 600,
        "preferred_username": "priya.r@og1o.in", "name": "Priya R",
    }
    claims.update(over)
    return jwt.encode(claims, _KEY, algorithm="RS256")


def _verify(token):
    return v.verify_entra_token(token, TENANT, AUD, ["og1o.in"], jwks_client=_JWKS())


def test_valid_og1o_token_is_accepted():
    who = _verify(_token())
    assert who["email"] == "priya.r@og1o.in" and who["name"] == "Priya R" and who["tid"] == TENANT


def test_non_og1o_domain_is_rejected():
    with pytest.raises(v.AuthError) as e:
        _verify(_token(preferred_username="mallory@gmail.com"))
    assert "allowed organisation domain" in str(e.value)


def test_wrong_tenant_in_tid_is_rejected():
    with pytest.raises(v.AuthError):
        _verify(_token(tid="00000000-0000-0000-0000-000000000000"))


def test_wrong_audience_is_rejected():
    with pytest.raises(v.AuthError):
        _verify(_token(aud="some-other-app"))


def test_expired_token_is_rejected():
    with pytest.raises(v.AuthError):
        _verify(_token(exp=int(time.time()) - 10))


def test_wrong_issuer_is_rejected():
    with pytest.raises(v.AuthError):
        _verify(_token(iss="https://login.microsoftonline.com/evil/v2.0"))


def test_token_without_email_is_rejected():
    with pytest.raises(v.AuthError):
        _verify(_token(preferred_username="", email="", upn=""))


def test_server_misconfiguration_is_flagged():
    with pytest.raises(v.AuthError):
        v.verify_entra_token(_token(), "not-a-guid", AUD, ["og1o.in"], jwks_client=_JWKS())
