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
    ident = idm.device_code_login(TENANT, CLIENT, allowed_domains=["og1o.in"], out=lambda m: None, sleep=lambda s: None, open_browser=False, client=client)
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
        idm.device_code_login(TENANT, CLIENT, allowed_domains=["og1o.in"], out=lambda m: None, sleep=lambda s: None, open_browser=False, client=client)
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
