"""Verified developer identity through Microsoft Entra ID (Azure AD).

The developer signs in once with the OAuth 2.0 device-code flow. The browser that opens is normally already
signed in to the organisation's Microsoft account (Outlook / Teams on the web use the same session), so the
step is a single confirmation click; nothing is read from Outlook, Teams or the browser itself. The ID token
returned by Microsoft carries the verified corporate e-mail (UPN), which is:

- stored locally in `~/.sdlc-gate/identity.json` (user-only permissions),
- written to the developer's global git identity (`user.email`, `user.name`) so every commit is authored with
  the verified address,
- attached by the local hooks as a `SDLC-Gate-Client` trailer so the server-side gate and the metrics can
  attribute each run to a verified person.

Set-up (platform team): register a public client application in Entra ID, enable "Allow public client flows",
and put its tenant id and client id in `gate.config.yaml` under `identity:`.
"""
from __future__ import annotations

import base64
import json
import os
import re
import stat
import subprocess
import time
import webbrowser
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import httpx

DEFAULT_AUTHORITY = "https://login.microsoftonline.com"
SCOPES = "openid profile email"
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class IdentityError(RuntimeError):
    pass


@dataclass
class Identity:
    email: str
    name: str
    oid: str
    tid: str
    method: str = "entra"
    issued_at: str = ""
    expires_at: str = ""

    @property
    def expired(self) -> bool:
        if not self.expires_at:
            return False
        try:
            return datetime.fromisoformat(self.expires_at) < datetime.now(timezone.utc)
        except ValueError:
            return True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def sdlc_home() -> Path:
    return Path(os.environ.get("SDLC_GATE_HOME") or (Path.home() / ".sdlc-gate"))


def identity_path(home: Path | None = None) -> Path:
    return (home or sdlc_home()) / "identity.json"


def load_identity(home: Path | None = None) -> Identity | None:
    path = identity_path(home)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        ident = Identity(**{k: data.get(k, "") for k in Identity.__dataclass_fields__})
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    if not EMAIL_RE.match(ident.email or ""):
        return None
    return ident


def save_identity(identity: Identity, home: Path | None = None) -> Path:
    path = identity_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(identity.to_dict(), indent=2), encoding="utf-8")
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass
    return path


def clear_identity(home: Path | None = None) -> bool:
    path = identity_path(home)
    if path.exists():
        path.unlink()
        return True
    return False


def decode_jwt_claims(token: str) -> dict[str, Any]:
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload.encode("ascii")))
    except (IndexError, ValueError, json.JSONDecodeError) as exc:
        raise IdentityError("token from the identity provider could not be decoded") from exc


def _validate_claims(claims: dict[str, Any], tenant: str, client_id: str, authority: str, allowed_domains: list[str]) -> Identity:
    now = time.time()
    if claims.get("aud") != client_id:
        raise IdentityError("token audience does not match the configured client id")
    exp = claims.get("exp")
    if not isinstance(exp, (int, float)) or exp < now:
        raise IdentityError("token is expired")
    iss = str(claims.get("iss") or "")
    if not iss.startswith(authority.rstrip("/") + "/"):
        raise IdentityError("token issuer is not the configured authority")
    tid = str(claims.get("tid") or "")
    if re.match(r"^[0-9a-fA-F-]{36}$", tenant) and tid.lower() != tenant.lower():
        raise IdentityError("token was issued for a different tenant")
    email = str(claims.get("preferred_username") or claims.get("email") or claims.get("upn") or "").strip().lower()
    if not EMAIL_RE.match(email):
        raise IdentityError("token does not carry a usable e-mail address")
    domain = email.rsplit("@", 1)[1]
    if allowed_domains and domain not in {d.lower().lstrip("@") for d in allowed_domains}:
        raise IdentityError(f"{email} is not in an allowed organisation domain ({', '.join(allowed_domains)})")
    return Identity(
        email=email,
        name=str(claims.get("name") or "").strip(),
        oid=str(claims.get("oid") or ""),
        tid=tid,
        issued_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        expires_at=datetime.fromtimestamp(float(exp), tz=timezone.utc).isoformat(timespec="seconds"),
    )


def device_code_login(
    tenant: str,
    client_id: str,
    allowed_domains: list[str] | None = None,
    authority: str = DEFAULT_AUTHORITY,
    out: Callable[[str], None] = print,
    sleep: Callable[[float], None] = time.sleep,
    open_browser: bool = True,
    client: httpx.Client | None = None,
    max_wait_seconds: int = 900,
) -> Identity:
    if not tenant or not client_id:
        raise IdentityError("identity.tenant and identity.client_id must be configured (see docs/enforcement.md)")
    http = client or httpx.Client(timeout=30)
    base = f"{authority.rstrip('/')}/{tenant}/oauth2/v2.0"
    try:
        resp = http.post(f"{base}/devicecode", data={"client_id": client_id, "scope": SCOPES})
        if resp.status_code != 200:
            raise IdentityError(f"device code request failed: HTTP {resp.status_code}: {resp.text[:200]}")
        dc = resp.json()
        out(dc.get("message") or f"Open {dc.get('verification_uri')} and enter code {dc.get('user_code')}")
        if open_browser:
            try:
                webbrowser.open(dc.get("verification_uri_complete") or dc.get("verification_uri") or "")
            except Exception:  # noqa: BLE001 - browser launch is best effort
                pass
        interval = float(dc.get("interval") or 5)
        deadline = time.monotonic() + min(int(dc.get("expires_in") or max_wait_seconds), max_wait_seconds)
        while time.monotonic() < deadline:
            sleep(interval)
            tok = http.post(
                f"{base}/token",
                data={"grant_type": "urn:ietf:params:oauth:grant-type:device_code", "client_id": client_id, "device_code": dc["device_code"]},
            )
            if tok.status_code == 200:
                id_token = tok.json().get("id_token")
                if not id_token:
                    raise IdentityError("token response did not include an id_token (request the openid scope)")
                return _validate_claims(decode_jwt_claims(id_token), tenant, client_id, authority, allowed_domains or [])
            err = tok.json().get("error") if tok.headers.get("content-type", "").startswith("application/json") else ""
            if err == "authorization_pending":
                continue
            if err == "slow_down":
                interval += 5
                continue
            raise IdentityError(f"sign-in failed: {err or tok.status_code}")
        raise IdentityError("sign-in timed out")
    finally:
        if client is None:
            http.close()


def configure_git_identity(identity: Identity) -> None:
    subprocess.run(["git", "config", "--global", "user.email", identity.email], check=False, capture_output=True)
    if identity.name:
        subprocess.run(["git", "config", "--global", "user.name", identity.name], check=False, capture_output=True)


# ---------------------------------------------------------------------------- attestation

ATTEST_TRAILER = "SDLC-Gate-Client"
ATTEST_RE = re.compile(rf"^[ \t]*{ATTEST_TRAILER}[ \t]*:[ \t]*(?P<result>pass|waived)[ \t]+v(?P<version>[0-9.]+)[ \t]+(?P<email>[^\s]+@[^\s]+|anonymous)[ \t]+(?P<ts>\S+)", re.I | re.M)


def attestation_line(result: str, version: str, identity: Identity | None) -> str:
    who = identity.email if identity else "anonymous"
    return f"{ATTEST_TRAILER}: {result} v{version} {who} {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}"


def append_attestation(message_file: Path, line: str) -> bool:
    text = message_file.read_text(encoding="utf-8", errors="replace")
    if ATTEST_RE.search(text):
        return False
    body = text.rstrip("\n")
    sep = "\n\n" if body and not body.endswith("\n") and not re.search(r"^[A-Za-z-]+:\s", body.splitlines()[-1] if body.splitlines() else "") else "\n"
    message_file.write_text(body + sep + line + "\n", encoding="utf-8")
    return True


def parse_attestations(messages: list[str]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for m in messages or []:
        for match in ATTEST_RE.finditer(m):
            out.append({k: (v or "").lower() if k != "ts" else v for k, v in match.groupdict().items()})
    return out
