"""Verified developer identity through Microsoft Entra ID (Azure AD).

The developer signs in once with the OAuth 2.0 device-code flow. The browser that opens is normally already
signed in to the organisation's Microsoft account (Outlook / Teams on the web use the same session), so the
step is a single confirmation click; nothing is read from Outlook, Teams or the browser itself. The ID token
returned by Microsoft carries the verified corporate e-mail (UPN), which is:

- stored locally in `~/.ai-sdlc-gate/identity.json` (user-only permissions),
- written to the developer's global git identity (`user.email`, `user.name`) so every commit is authored with
  the verified address,
- attached by the local hooks as a `AI-SDLC-Gate-Client` trailer so the server-side gate and the metrics can
  attribute each run to a verified person.

Set-up (platform team): register a public client application in Entra ID, enable "Allow public client flows",
and put its tenant id and client id in `gate.config.yaml` under `identity:`.
"""
from __future__ import annotations

import base64
import hashlib
import http.server
import json
import os
import platform
import re
import secrets as _secrets
import shutil
import socket
import stat
import subprocess
import threading
import time
import urllib.parse
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
    return Path(os.environ.get("AI_SDLC_GATE_HOME") or (Path.home() / ".ai-sdlc-gate"))


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


def copy_to_clipboard(text: str) -> bool:
    """Best-effort clipboard copy so the developer can paste the code if the browser did not pre-fill it."""
    try:
        system = platform.system()
        if system == "Windows":
            cmd = ["clip"]
        elif system == "Darwin":
            cmd = ["pbcopy"]
        elif shutil.which("wl-copy"):
            cmd = ["wl-copy"]
        elif shutil.which("xclip"):
            cmd = ["xclip", "-selection", "clipboard"]
        else:
            return False
        subprocess.run(cmd, input=text.encode("utf-8"), check=True, timeout=5, capture_output=True)
        return True
    except Exception:  # noqa: BLE001
        return False


def _print_out(message: str) -> None:
    print(message, flush=True)


def prefilled_login_url(authority: str, verification_uri: str, user_code: str) -> str:
    """Microsoft's device-login page accepts the code as `otc`, so the developer only confirms the account."""
    base = f"{authority.rstrip('/')}/common/oauth2/deviceauth"
    if "microsoftonline.com" in verification_uri or "microsoft.com/devicelogin" in verification_uri:
        return f"{base}?otc={user_code}"
    return verification_uri


def device_code_login(
    tenant: str,
    client_id: str,
    allowed_domains: list[str] | None = None,
    authority: str = DEFAULT_AUTHORITY,
    out: Callable[[str], None] = _print_out,
    sleep: Callable[[float], None] = time.sleep,
    open_browser: bool = True,
    client: httpx.Client | None = None,
    max_wait_seconds: int = 900,
    browser: Callable[[str], object] = webbrowser.open,
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
        code = str(dc.get("user_code") or "")
        verification_uri = str(dc.get("verification_uri") or "https://microsoft.com/devicelogin")
        url = str(dc.get("verification_uri_complete") or prefilled_login_url(authority, verification_uri, code))
        copied = copy_to_clipboard(code)
        out("")
        out("=" * 66)
        out("  MICROSOFT SIGN-IN")
        out("")
        out(f"  Your code:   {code}" + ("   (copied to the clipboard)" if copied else ""))
        out("")
        out("  A browser window is opening with this code already filled in.")
        out("  Choose your work account and click Next. Then return here.")
        out(f"  If no window opened: {verification_uri}")
        out("=" * 66)
        out("")
        if open_browser:
            try:
                browser(url)
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
                out("  Sign-in confirmed.")
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


# ---------------------------------------------------------------------------- browser sign-in (auth code + PKCE)

_CALLBACK_HTML = b"""<!doctype html><html><head><meta charset="utf-8"><title>AI SDLC Gate</title></head>
<body style="font-family:Segoe UI,Helvetica,Arial,sans-serif;background:#0d1117;color:#e6edf3;display:flex;align-items:center;justify-content:center;height:100vh;margin:0">
<div style="text-align:center"><h1 style="font-weight:600">Signed in to AI SDLC Gate</h1><p>You can close this window and return to the terminal.</p></div></body></html>"""


class _Callback(http.server.BaseHTTPRequestHandler):
    result: dict[str, str] = {}

    def do_GET(self) -> None:  # noqa: N802 - http.server API
        query = urllib.parse.urlparse(self.path).query
        params = {k: v[0] for k, v in urllib.parse.parse_qs(query).items()}
        type(self).result = params
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(_CALLBACK_HTML)))
        self.end_headers()
        self.wfile.write(_CALLBACK_HTML)

    def log_message(self, *args: object) -> None:  # silence the default access log
        return None


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def browser_login(
    tenant: str,
    client_id: str,
    allowed_domains: list[str] | None = None,
    authority: str = DEFAULT_AUTHORITY,
    out: Callable[[str], None] = _print_out,
    client: httpx.Client | None = None,
    browser: Callable[[str], object] = webbrowser.open,
    timeout_seconds: int = 300,
    port: int | None = None,
) -> Identity:
    """Authorization-code sign-in with PKCE and a loopback redirect: no code to type, one account click."""
    if not tenant or not client_id:
        raise IdentityError("identity.tenant and identity.client_id must be configured (see docs/enforcement.md)")
    session = client or httpx.Client(timeout=30)
    port = port or _free_port()
    redirect_uri = f"http://localhost:{port}"
    state = _secrets.token_urlsafe(24)
    nonce = _secrets.token_urlsafe(24)
    verifier = _secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).rstrip(b"=").decode("ascii")
    base = f"{authority.rstrip('/')}/{tenant}/oauth2/v2.0"
    params = {
        "client_id": client_id, "response_type": "code", "redirect_uri": redirect_uri, "response_mode": "query",
        "scope": SCOPES, "state": state, "nonce": nonce, "code_challenge": challenge, "code_challenge_method": "S256",
        "prompt": "select_account",
    }
    url = f"{base}/authorize?{urllib.parse.urlencode(params)}"
    server = http.server.HTTPServer(("127.0.0.1", port), _Callback)
    server.timeout = timeout_seconds
    _Callback.result = {}
    try:
        out("")
        out("=" * 66)
        out("  MICROSOFT SIGN-IN")
        out("")
        out("  A browser window is opening. Choose your work account; nothing to type.")
        out("  Waiting for the sign-in to complete...")
        out("=" * 66)
        out("")
        try:
            browser(url)
        except Exception:  # noqa: BLE001 - browser launch is best effort
            pass
        server.handle_request()
        result = dict(_Callback.result)
    finally:
        server.server_close()
        if client is None:
            session.close()
    if not result:
        raise IdentityError("sign-in timed out")
    if result.get("error"):
        raise IdentityError(f"sign-in failed: {result.get('error')}: {result.get('error_description', '')[:200]}")
    if result.get("state") != state or not result.get("code"):
        raise IdentityError("sign-in response did not match this request")
    session2 = client or httpx.Client(timeout=30)
    try:
        tok = session2.post(f"{base}/token", data={
            "grant_type": "authorization_code", "client_id": client_id, "code": result["code"],
            "redirect_uri": redirect_uri, "code_verifier": verifier, "scope": SCOPES,
        })
    finally:
        if client is None:
            session2.close()
    if tok.status_code != 200:
        err = tok.json().get("error_description", "") if tok.headers.get("content-type", "").startswith("application/json") else tok.text
        raise IdentityError(f"token exchange failed: {str(err)[:200]}")
    id_token = tok.json().get("id_token")
    if not id_token:
        raise IdentityError("token response did not include an id_token")
    claims = decode_jwt_claims(id_token)
    if claims.get("nonce") != nonce:
        raise IdentityError("token nonce does not match this request")
    out("  Sign-in confirmed.")
    return _validate_claims(claims, tenant, client_id, authority, allowed_domains or [])


def configure_git_identity(identity: Identity) -> None:
    subprocess.run(["git", "config", "--global", "user.email", identity.email], check=False, capture_output=True)
    if identity.name:
        subprocess.run(["git", "config", "--global", "user.name", identity.name], check=False, capture_output=True)


# ---------------------------------------------------------------------------- attestation

ATTEST_TRAILER = "AI-SDLC-Gate-Client"
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
