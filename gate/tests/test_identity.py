from __future__ import annotations

import base64
import json
import time
from pathlib import Path

import httpx
import pytest

from ai_sdlc_gate import identity as idm

TENANT = "11111111-2222-3333-4444-555555555555"
CLIENT = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


def _jwt(claims: dict) -> str:
    def b64(o: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(o).encode()).decode().rstrip("=")

    return f"{b64({'alg': 'RS256'})}.{b64(claims)}.sig"


# Tests fabricate unsigned tokens; stub out the cryptographic verification and exercise claims validation instead.
def _stub_verify(token: str, tenant: str, client_id: str, authority: str) -> dict:
    return idm.decode_jwt_claims(token)


VERIFY = {"verify_token": _stub_verify}


def _claims(**over):
    base = {
        "aud": CLIENT,
        "iss": f"https://login.microsoftonline.com/{TENANT}/v2.0",
        "tid": TENANT,
        "exp": time.time() + 3600,
        "preferred_username": "Arijit.Aich@og1o.in",
        "name": "Arijit Aich",
        "oid": "user-oid",
    }
    base.update(over)
    return base


def _transport(claims: dict, pending_polls: int = 1):
    state = {"polls": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/devicecode"):
            return httpx.Response(200, json={"device_code": "dc", "user_code": "ABCD", "verification_uri": "https://microsoft.com/devicelogin", "expires_in": 900, "interval": 0, "message": "go"})
        if request.url.path.endswith("/token"):
            state["polls"] += 1
            if state["polls"] <= pending_polls:
                return httpx.Response(400, json={"error": "authorization_pending"}, headers={"content-type": "application/json"})
            return httpx.Response(200, json={"id_token": _jwt(claims)})
        return httpx.Response(404)

    return httpx.MockTransport(handler)


def test_device_code_login_returns_verified_identity(tmp_path, monkeypatch):
    client = httpx.Client(transport=_transport(_claims()))
    opened: list[str] = []
    shown: list[str] = []
    monkeypatch.setattr(idm, "copy_to_clipboard", lambda text: True)
    ident = idm.device_code_login(TENANT, CLIENT, allowed_domains=["og1o.in"], out=shown.append, sleep=lambda s: None, open_browser=True, client=client, browser=opened.append, **VERIFY)
    assert opened == ["https://login.microsoftonline.com/common/oauth2/deviceauth?otc=ABCD"]
    assert any("Your code:   ABCD" in line for line in shown) and any("Sign-in confirmed" in line for line in shown)
    assert ident.email == "arijit.aich@og1o.in" and ident.name == "Arijit Aich" and ident.tid == TENANT
    monkeypatch.setenv("AI_SDLC_GATE_HOME", str(tmp_path))
    path = idm.save_identity(ident)
    assert path == tmp_path / "identity.json"
    loaded = idm.load_identity()
    assert loaded is not None and loaded.email == ident.email and not loaded.expired
    assert idm.clear_identity() and idm.load_identity() is None


@pytest.mark.parametrize(
    "bad, message",
    [
        ({"aud": "other"}, "audience"),
        ({"exp": time.time() - 10}, "expired"),
        ({"tid": "99999999-2222-3333-4444-555555555555"}, "different tenant"),
        ({"preferred_username": "someone@gmail.com"}, "allowed organisation domain"),
        ({"iss": "https://evil.example/x"}, "issuer"),
    ],
)
def test_login_rejects_invalid_tokens(bad, message):
    client = httpx.Client(transport=_transport(_claims(**bad), pending_polls=0))
    with pytest.raises(idm.IdentityError) as exc:
        idm.device_code_login(TENANT, CLIENT, allowed_domains=["og1o.in"], out=lambda m: None, sleep=lambda s: None, open_browser=False, client=client, **VERIFY)
    assert message in str(exc.value)


def test_login_requires_configuration():
    with pytest.raises(idm.IdentityError):
        idm.device_code_login("", "", out=lambda m: None, sleep=lambda s: None, open_browser=False)


def test_attestation_roundtrip(tmp_path):
    ident = idm.Identity(email="dev@og1o.in", name="Dev", oid="o", tid=TENANT)
    line = idm.attestation_line("pass", "1.0.0", ident)
    msg = tmp_path / "COMMIT_EDITMSG"
    msg.write_text("feat: add thing\n\nSDLC-Skip: 5\nSDLC-Skip-Reason: something long enough to count as a real justification here\n", encoding="utf-8")
    assert idm.append_attestation(msg, line)
    assert not idm.append_attestation(msg, line)  # idempotent
    parsed = idm.parse_attestations([msg.read_text(encoding="utf-8")])
    assert parsed and parsed[0]["email"] == "dev@og1o.in" and parsed[0]["result"] == "pass" and parsed[0]["version"] == "1.0.0"
    anon = idm.attestation_line("waived", "1.0.0", None)
    assert "anonymous" in anon and idm.parse_attestations([anon])[0]["email"] == "anonymous"


def test_attestation_flows_into_gate_context_and_event(cfg, skills_dir):
    from ai_sdlc_gate.changes import ChangeSet, ChangedFile
    from ai_sdlc_gate.intent import detect_intent
    from ai_sdlc_gate.llm import StaticLLM
    from ai_sdlc_gate.metrics import build_event, developer_key, summarize, validate_event
    from ai_sdlc_gate.runner import run_gate
    from ai_sdlc_gate.skills import load_skills
    from ai_sdlc_gate.skip import parse_skip

    skills = load_skills(skills_dir, cfg)
    msg = "feat: x\n\n" + idm.attestation_line("pass", "1.0.0", idm.Identity(email="priya.r@og1o.in", name="Priya", oid="o", tid=TENANT))
    cs = ChangeSet(files=[ChangedFile(path="a.py", status="M", diff="+x", content="x")], commit_messages=[msg], author_email="priya@personal.example")
    report = run_gate(cfg, StaticLLM(), skills, cs, detect_intent(cfg, explicit="commit"), parse_skip(cfg, []), context={"repo": "org/x", "actor": "priya-dev"})
    assert report.context["client_attested"] and report.context["developer_email"] == "priya.r@og1o.in" and report.context["email_verified"]
    ev = build_event(report)
    assert validate_event(ev) == [] and ev["developer_email"] == "priya.r@og1o.in" and ev["client_attested"]
    assert developer_key(ev) == "priya.r@og1o.in"

    unattested = run_gate(cfg, StaticLLM(), skills, ChangeSet(files=[ChangedFile(path="a.py", status="M", diff="+x", content="x")], commit_messages=["chore"]),
                          detect_intent(cfg, explicit="commit"), parse_skip(cfg, []), context={"repo": "org/x", "actor": "someone"})
    ev2 = build_event(unattested)
    assert not ev2["client_attested"] and developer_key(ev2) == "@someone"
    summary = summarize([ev, ev2])
    assert summary["organisation"]["attested_rate"] == 0.5
    assert set(summary["developers"]) == {"priya.r@og1o.in", "@someone"}


def test_dashboard_writes_scoreboard_and_badges(tmp_path):
    from ai_sdlc_gate.metrics import build_dashboard

    summary = build_dashboard(tmp_path / "events", tmp_path / "dash")
    assert summary["events"] == 0
    for name in ("README.md", "summary.json", "scoreboard.svg", "badge-pass-rate.svg", "badge-runs.svg"):
        assert (tmp_path / "dash" / name).is_file()
    svg = (tmp_path / "dash" / "scoreboard.svg").read_text(encoding="utf-8")
    assert svg.startswith("<svg") and "No gate runs recorded yet" in svg


def test_identity_check_command_respects_configuration(tmp_path, monkeypatch, cfg):
    from ai_sdlc_gate.cli import main

    monkeypatch.setenv("AI_SDLC_GATE_HOME", str(tmp_path))
    # Provider not configured (repository default): nothing is required.
    cfg_path = tmp_path / "gate.config.yaml"
    cfg_path.write_text("identity:\n  tenant: ''\n  client_id: ''\n  required: true\n", encoding="utf-8")
    assert main(["identity", "check", "--config", str(cfg_path), "--strict"]) == 0
    # Provider configured and required: missing identity blocks.
    cfg_path.write_text(f"identity:\n  tenant: '{TENANT}'\n  client_id: '{CLIENT}'\n  required: true\n", encoding="utf-8")
    assert main(["identity", "check", "--config", str(cfg_path)]) == 3
    idm.save_identity(idm.Identity(email="dev@og1o.in", name="Dev", oid="o", tid=TENANT))
    assert main(["identity", "check", "--config", str(cfg_path)]) == 0
    # attest honours the same rule
    msg = tmp_path / "msg"
    msg.write_text("feat: x\n", encoding="utf-8")
    idm.clear_identity()
    assert main(["attest", "--config", str(cfg_path), "--message-file", str(msg), "--quiet"]) == 3
    cfg_path.write_text("identity:\n  tenant: ''\n  client_id: ''\n  required: true\n", encoding="utf-8")
    assert main(["attest", "--config", str(cfg_path), "--message-file", str(msg), "--quiet"]) == 0
    assert "anonymous" in msg.read_text(encoding="utf-8")


def test_browser_login_pkce_roundtrip():
    import threading
    import urllib.parse
    import urllib.request

    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/token"):
            body = dict(urllib.parse.parse_qsl(request.content.decode()))
            seen["token_request"] = body
            claims = _claims(nonce=seen["nonce"])
            return httpx.Response(200, json={"id_token": _jwt(claims)})
        return httpx.Response(404)

    def fake_browser(url: str):
        q = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query))
        seen["nonce"] = q["nonce"]
        seen["challenge"] = q["code_challenge"]
        assert q["code_challenge_method"] == "S256" and q["client_id"] == CLIENT and q["redirect_uri"].startswith("http://localhost:")
        cb = f"{q['redirect_uri']}/?code=the-code&state={q['state']}"
        threading.Thread(target=lambda: urllib.request.urlopen(cb, timeout=5).read(), daemon=True).start()

    ident = idm.browser_login(TENANT, CLIENT, allowed_domains=["og1o.in"], out=lambda m: None, client=httpx.Client(transport=httpx.MockTransport(handler)), browser=fake_browser, timeout_seconds=10, **VERIFY)
    assert ident.email == "arijit.aich@og1o.in"
    body = seen["token_request"]
    assert body["grant_type"] == "authorization_code" and body["code"] == "the-code" and body["code_verifier"]
    import base64, hashlib
    assert base64.urlsafe_b64encode(hashlib.sha256(body["code_verifier"].encode()).digest()).rstrip(b"=").decode() == seen["challenge"]


def test_browser_login_rejects_wrong_state():
    import threading
    import urllib.parse
    import urllib.request

    def fake_browser(url: str):
        q = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query))
        cb = f"{q['redirect_uri']}/?code=x&state=forged"
        threading.Thread(target=lambda: urllib.request.urlopen(cb, timeout=5).read(), daemon=True).start()

    with pytest.raises(idm.IdentityError) as exc:
        idm.browser_login(TENANT, CLIENT, out=lambda m: None, client=httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(404))), browser=fake_browser, timeout_seconds=10)
    assert "did not match" in str(exc.value)


def test_open_url_uses_windows_launcher_inside_wsl(monkeypatch):
    calls: list[list[str]] = []
    monkeypatch.setattr(idm, "is_wsl", lambda: True)
    monkeypatch.setattr(idm.shutil, "which", lambda name: None)

    class R:
        returncode = 0

    monkeypatch.setattr(idm.subprocess, "run", lambda cmd, **kw: calls.append(cmd) or R())
    assert idm.open_url("https://login.example/x?a=1&b=2")
    assert calls and calls[0][0] == "powershell.exe" and "Start-Process" in calls[0][-1]


def test_browser_login_prints_link_when_no_browser():
    import threading, urllib.parse, urllib.request

    shown: list[str] = []

    def no_browser(url: str):
        q = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query))
        cb = f"{q['redirect_uri']}/?code=c&state={q['state']}"
        threading.Thread(target=lambda: urllib.request.urlopen(cb, timeout=5).read(), daemon=True).start()
        return False

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/token"):
            body = dict(urllib.parse.parse_qsl(request.content.decode()))
            return httpx.Response(200, json={"id_token": _jwt(_claims(nonce=shown_nonce[0]))})
        return httpx.Response(404)

    shown_nonce: list[str] = []
    real_no_browser = no_browser

    def capture(url: str):
        shown_nonce.append(dict(urllib.parse.parse_qsl(urllib.parse.urlparse(url).query))["nonce"])
        return real_no_browser(url)

    idm.browser_login(TENANT, CLIENT, allowed_domains=["og1o.in"], out=shown.append, client=httpx.Client(transport=httpx.MockTransport(handler)), browser=capture, timeout_seconds=10, **VERIFY)
    assert any("Open this link in your browser" in line for line in shown) and any("https://login.microsoftonline.com/" in line for line in shown)


def test_identity_is_trusted_for_90_days_and_legacy_records_are_extended(tmp_path, monkeypatch):
    from datetime import datetime, timedelta, timezone

    monkeypatch.setenv("AI_SDLC_GATE_HOME", str(tmp_path))
    client = httpx.Client(transport=_transport(_claims(exp=time.time() + 3600), pending_polls=0))
    ident = idm.device_code_login(TENANT, CLIENT, allowed_domains=["og1o.in"], out=lambda m: None, sleep=lambda s: None, open_browser=False, client=client,
                                  verify_token=lambda token, *a, **k: idm.decode_jwt_claims(token))
    assert (datetime.fromisoformat(ident.expires_at) - datetime.now(timezone.utc)) > timedelta(days=89)
    # legacy record: token expiry one hour after issue -> extended on load
    now = datetime.now(timezone.utc) - timedelta(days=3)
    legacy = idm.Identity(email="dev@og1o.in", name="Dev", oid="o", tid=TENANT, issued_at=now.isoformat(timespec="seconds"), expires_at=(now + timedelta(hours=1)).isoformat(timespec="seconds"))
    idm.save_identity(legacy)
    loaded = idm.load_identity()
    assert loaded is not None and not loaded.expired
    assert (datetime.fromisoformat(loaded.expires_at) - now) > timedelta(days=89)
