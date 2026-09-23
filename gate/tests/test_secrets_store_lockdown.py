"""Windows credential-file lockdown: SID parsing and the icacls command it builds.

These test the pure helpers (no subprocess, no os.name branch) so they run on every CI platform, and they encode the
regression: the lockdown must grant the current account's SID, never a bare or domain user name, and must refuse to
strip inheritance when the SID is unknown (which is what locked domain users out of their own ~/.ai-sdlc-gate).
"""
from __future__ import annotations

import pytest

from ai_sdlc_gate import secrets_store as s


def test_parse_sid_extracts_valid_sid_from_whoami_csv():
    assert s._parse_sid('"OCN\\AAICH","S-1-5-21-1111111111-2222222222-3333333333-1001"') == "S-1-5-21-1111111111-2222222222-3333333333-1001"
    # Case-insensitive prefix, surrounding whitespace tolerated.
    assert s._parse_sid('"dom\\u"," s-1-5-21-1-2-3-500 "') == "S-1-5-21-1-2-3-500"


@pytest.mark.parametrize("bad", [
    "",                                   # no output (whoami failed)
    '"OCN\\AAICH"',                       # username only, no SID column
    '"OCN\\AAICH","not-a-sid"',           # malformed SID
    '"S-1-only","AAICH"',                 # a field that looks partial but is not a full SID
    "garbage,,,\n",                        # non-CSV / corrupted
])
def test_parse_sid_rejects_anything_that_is_not_a_sid(bad):
    assert s._parse_sid(bad) == ""


def test_icacls_args_directory_uses_inherit_flags_and_sid():
    sid = "S-1-5-21-9-8-7-1001"
    args = s._icacls_args(r"C:\Users\dev\.ai-sdlc-gate", sid, is_dir=True)
    assert args is not None
    joined = " ".join(args)
    assert args[0] == "icacls" and "/inheritance:r" in args
    # The current user is granted by SID (prefixed with *), never by name.
    assert f"*{sid}:(OI)(CI)F" in args
    assert "AAICH" not in joined and "OCN\\AAICH" not in joined
    # SYSTEM and Administrators are always kept, by well-known SID.
    assert "*S-1-5-18:(OI)(CI)F" in args and "*S-1-5-32-544:(OI)(CI)F" in args


def test_icacls_args_file_uses_plain_F_not_inherit_flags():
    args = s._icacls_args(r"C:\Users\dev\.ai-sdlc-gate\env.enc", "S-1-5-21-9-8-7-1001", is_dir=False)
    assert args is not None
    assert "*S-1-5-21-9-8-7-1001:F" in args
    assert not any("(OI)(CI)" in a for a in args)  # inherit flags are rejected by icacls on a file


def test_icacls_args_refuses_when_sid_unknown_so_inheritance_is_not_stripped():
    # This is the regression guard: without a valid SID we must NOT build an icacls that removes inheritance,
    # because a grant to the wrong principal would lock the real user out (the original domain bug).
    for bad_sid in ["", "AAICH", "OCN\\AAICH", "not-a-sid"]:
        assert s._icacls_args(r"C:\x", bad_sid, is_dir=True) is None


def test_lock_down_returns_false_when_sid_cannot_be_determined(monkeypatch, tmp_path):
    monkeypatch.setattr(s.os, "name", "nt")
    monkeypatch.setattr(s, "_current_user_sid", lambda: "")
    called = {"n": 0}
    import subprocess

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: called.__setitem__("n", called["n"] + 1))
    # No valid SID -> skip the lockdown entirely (do not run icacls, do not strip inheritance) and report False.
    assert s._lock_down(tmp_path) is False
    assert called["n"] == 0


def test_lock_down_runs_icacls_with_sid_and_reports_success(monkeypatch, tmp_path):
    monkeypatch.setattr(s.os, "name", "nt")
    monkeypatch.setattr(s, "_current_user_sid", lambda: "S-1-5-21-9-8-7-1001")
    seen = {}

    class _R:
        returncode = 0

    import subprocess

    def fake_run(args, **kwargs):
        seen["args"] = args
        return _R()

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert s._lock_down(tmp_path) is True
    assert "*S-1-5-21-9-8-7-1001:(OI)(CI)F" in seen["args"] and "/inheritance:r" in seen["args"]
