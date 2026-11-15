"""Unit tests for iktisad GitHub App Marketplace CI Guard MVP."""

from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path
import threading
import urllib.error
import urllib.request

from iktisad.cli import main as cli_main
from iktisad.github_app import (
    MarketplacePlanEntitlement,
    PRGuardReport,
    build_check_run_payload,
    build_github_app_manifest,
    create_github_webhook_server,
    evaluate_pull_request_guard,
    handle_github_webhook_payload,
    parse_marketplace_plan_event,
    verify_github_webhook_signature,
)


def _sign_payload(payload_bytes: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def test_verify_github_webhook_signature_valid_and_invalid() -> None:
    """Verify constant-time HMAC-SHA256 validation and fail-closed edge cases."""
    secret = "whsec_iktisad_unit_test_secret_001"
    payload = b'{"zen":"Speak like a human."}'
    valid_sig = _sign_payload(payload, secret)

    assert verify_github_webhook_signature(payload, valid_sig, secret) is True
    assert verify_github_webhook_signature(payload, valid_sig.upper().replace("SHA256=", "sha256="), secret) is True
    assert verify_github_webhook_signature(payload, "", secret) is False
    assert verify_github_webhook_signature(payload, valid_sig, "") is False
    assert verify_github_webhook_signature(payload, "sha1=deadbeef", secret) is False
    assert verify_github_webhook_signature(payload, "sha256=" + ("0" * 64), secret) is False
    assert verify_github_webhook_signature(payload + b" ", valid_sig, secret) is False


def test_parse_marketplace_plan_event_purchased_and_cancelled() -> None:
    """Verify GitHub marketplace_purchase payload parsing for purchased and cancelled events."""
    purchased_payload = {
        "action": "purchased",
        "marketplace_purchase": {
            "account": {"id": 4201, "login": "kenz-labs", "type": "Organization"},
            "billing_cycle": "monthly",
            "plan": {
                "id": 77,
                "name": "Pro Guard",
                "monthly_price_in_cents": 1000,
                "yearly_price_in_cents": 10000,
            },
        },
    }
    ent_active = parse_marketplace_plan_event(purchased_payload)
    assert isinstance(ent_active, MarketplacePlanEntitlement)
    assert ent_active.account_login == "kenz-labs"
    assert ent_active.account_id == 4201
    assert ent_active.plan_id == 77
    assert ent_active.plan_name == "Pro Guard"
    assert ent_active.action == "purchased"
    assert ent_active.active is True
    assert ent_active.monthly_price_usd == 10.0

    cancelled_payload = {
        "action": "cancelled",
        "marketplace_purchase": purchased_payload["marketplace_purchase"],
    }
    ent_cancelled = parse_marketplace_plan_event(cancelled_payload)
    assert ent_cancelled.action == "cancelled"
    assert ent_cancelled.active is False


def test_parse_marketplace_plan_event_changed_and_pending_change() -> None:
    """Verify changed and pending_change marketplace actions remain active."""
    base_purchase = {
        "account": {"id": 99, "login": "octocat"},
        "billing_cycle": "yearly",
        "plan": {"id": 12, "name": "Team", "yearly_price_in_cents": 12000},
    }
    changed = parse_marketplace_plan_event({"action": "changed", "marketplace_purchase": base_purchase})
    pending = parse_marketplace_plan_event({"action": "pending_change", "marketplace_purchase": base_purchase})

    assert changed.active is True
    assert changed.monthly_price_usd == 10.0
    assert pending.active is True


def test_evaluate_pull_request_guard_clean_success() -> None:
    """Verify AST compression and clean success conclusion when LICENSE exists and no risks exist."""
    source = (
        '"""Sample calculator module."""\n\n'
        "def add_numbers(a: int, b: int) -> int:\n"
        '    """Add two integers together cleanly."""\n'
        "    intermediate_value = a + b\n"
        "    # Verbose comment explaining the arithmetic step for human readers\n"
        "    return intermediate_value\n\n"
        "class Calculator:\n"
        '    """Stateful calculator helper."""\n\n'
        "    def multiply(self, x: int, y: int) -> int:\n"
        '        """Multiply two integers."""\n'
        "        product = x * y\n"
        "        return product\n"
    )
    report = evaluate_pull_request_guard(
        repo_full_name="kenz-labs/iktisad",
        pr_number=14,
        python_sources={"src/calc.py": source},
        repo_files={"LICENSE": "MIT License\n", "README.md": "# calc\n"},
    )
    assert isinstance(report, PRGuardReport)
    assert report.repo_full_name == "kenz-labs/iktisad"
    assert report.pr_number == 14
    assert report.python_files_scanned == 1
    assert report.raw_chars == len(source)
    assert report.skeleton_chars > 0
    assert report.skeleton_chars < report.raw_chars
    assert report.reduction_pct > 0.0
    assert report.preflight_errors == ()
    assert report.conclusion == "success"
    assert len(report.markdown_summary.splitlines()) <= 15


def test_evaluate_pull_request_guard_missing_license_and_security_risks() -> None:
    """Verify missing LICENSE triggers action_required and insecure test prefix/secret triggers failure."""
    clean_py = "def ping() -> str:\n    return 'pong'\n"
    missing_license_report = evaluate_pull_request_guard(
        repo_full_name="acme/demo",
        pr_number=2,
        python_sources={"app.py": clean_py},
        repo_files={"README.md": "# demo\n"},
    )
    assert missing_license_report.conclusion == "action_required"
    assert any("LICENSE" in err for err in missing_license_report.preflight_errors)
    assert len(missing_license_report.markdown_summary.splitlines()) <= 15

    risky_py = (
        "def check_auth() -> bool:\n"
        "    token = 'ghp_1234567890abcdefghij1234567890'\n"
        "    return verify_key(token, allow_test_prefixes=True)\n"
    )
    risky_report = evaluate_pull_request_guard(
        repo_full_name="acme/demo",
        pr_number=3,
        python_sources={"auth.py": risky_py},
        repo_files={"LICENSE": "MIT"},
    )
    assert risky_report.conclusion == "failure"
    assert any("allow_test_prefixes=True" in err for err in risky_report.preflight_errors)
    assert any("secret" in err.lower() for err in risky_report.preflight_errors)
    assert len(risky_report.markdown_summary.splitlines()) <= 15


def test_handle_github_webhook_payload_fail_closed_and_routing() -> None:
    """Verify 401 on bad signature, 400 on bad JSON, and deterministic event routing."""
    secret = "whsec_router_test_12345"

    status_401, body_401 = handle_github_webhook_payload(
        event_name="ping",
        payload_bytes=b'{"zen":"ok"}',
        signature_header="sha256=" + ("f" * 64),
        webhook_secret=secret,
    )
    assert status_401 == 401
    assert body_401["status"] == "unauthorized"

    bad_json_bytes = b"{not-valid-json"
    status_400, body_400 = handle_github_webhook_payload(
        event_name="ping",
        payload_bytes=bad_json_bytes,
        signature_header=_sign_payload(bad_json_bytes, secret),
        webhook_secret=secret,
    )
    assert status_400 == 400
    assert body_400["status"] == "bad_request"

    ping_bytes = json.dumps({"zen": "Keep it logically awesome.", "hook_id": 101}).encode("utf-8")
    status_ping, body_ping = handle_github_webhook_payload(
        event_name="ping",
        payload_bytes=ping_bytes,
        signature_header=_sign_payload(ping_bytes, secret),
        webhook_secret=secret,
    )
    assert status_ping == 200
    assert body_ping["event"] == "ping"
    assert body_ping["hook_id"] == 101

    mp_bytes = json.dumps(
        {
            "action": "purchased",
            "marketplace_purchase": {
                "account": {"id": 55, "login": "builder"},
                "plan": {"id": 9, "name": "Pro", "monthly_price_in_cents": 1000},
            },
        }
    ).encode("utf-8")
    status_mp, body_mp = handle_github_webhook_payload(
        event_name="marketplace_purchase",
        payload_bytes=mp_bytes,
        signature_header=_sign_payload(mp_bytes, secret),
        webhook_secret=secret,
    )
    assert status_mp == 200
    assert body_mp["entitlement"]["active"] is True
    assert body_mp["entitlement"]["monthly_price_usd"] == 10.0

    pr_bytes = json.dumps(
        {
            "action": "synchronize",
            "number": 88,
            "repository": {"full_name": "kenz-labs/iktisad"},
        }
    ).encode("utf-8")
    status_pr, body_pr = handle_github_webhook_payload(
        event_name="pull_request",
        payload_bytes=pr_bytes,
        signature_header=_sign_payload(pr_bytes, secret),
        webhook_secret=secret,
        python_sources={"mod.py": "def hello() -> int:\n    return 1\n"},
        repo_files={"LICENSE": "MIT"},
    )
    assert status_pr == 200
    assert body_pr["event"] == "pull_request"
    assert body_pr["report"]["conclusion"] == "success"
    assert body_pr["report"]["pr_number"] == 88


def test_github_webhook_http_server_and_manifest_contract(capsys: object) -> None:
    """Verify local stdlib webhook HTTPServer, check-run payload builder, and manifest concordance."""
    manifest_file = Path(__file__).resolve().parent.parent / "docs" / "github_app_manifest.json"
    disk_manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    code_manifest = build_github_app_manifest()
    assert disk_manifest == code_manifest
    assert "pull_request" in disk_manifest["default_events"]
    assert "marketplace_purchase" in disk_manifest["default_events"]
    assert disk_manifest["default_permissions"]["checks"] == "write"

    assert cli_main(["github-app", "--manifest"]) == 0
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    assert json.loads(captured.out) == code_manifest

    report = evaluate_pull_request_guard("kenz-labs/iktisad", 1, {"a.py": "def f() -> None:\n    pass\n"})
    check_payload = build_check_run_payload("abc123def", report)
    assert check_payload["head_sha"] == "abc123def"
    assert check_payload["conclusion"] == "success"

    secret = "whsec_http_loopback_test"
    server = create_github_webhook_server(host="127.0.0.1", port=0, webhook_secret=secret)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2.0) as resp:
            assert resp.status == 200
            health = json.loads(resp.read().decode("utf-8"))
            assert health["status"] == "healthy"

        body = json.dumps({"zen": "Design for failure."}).encode("utf-8")
        req = urllib.request.Request(
            url=f"http://127.0.0.1:{port}/webhook",
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "X-GitHub-Event": "ping",
                "X-Hub-Signature-256": _sign_payload(body, secret),
            },
        )
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            assert resp.status == 200
            ping_resp = json.loads(resp.read().decode("utf-8"))
            assert ping_resp["event"] == "ping"

        bad_req = urllib.request.Request(
            url=f"http://127.0.0.1:{port}/webhook",
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "X-GitHub-Event": "ping",
                "X-Hub-Signature-256": "sha256=" + ("0" * 64),
            },
        )
        try:
            urllib.request.urlopen(bad_req, timeout=2.0)
            raise AssertionError("Expected HTTP 401 for invalid webhook signature")
        except urllib.error.HTTPError as err:
            assert err.code == 401
    finally:
        server.shutdown()
        server.server_close()
