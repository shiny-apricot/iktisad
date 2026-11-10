"""Unit tests for commercial gateway features: Polar Licensing, Budget Limits, and Blowout Breaker.

Conforms to Corporate Law V:
- Python 3.10+
- Top-level def test_*(): functions without class wrappers
- Pure functional assertions and deterministic local fixtures
- Zero unsolicited external network calls (0 bytes transferred)
"""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import threading
import time
from typing import Any
import urllib.request
import urllib.error

import pytest

from iktisad.cli import main as cli_main
from iktisad.gateway import (
    BudgetEnforcer,
    GatewayCompletionResult,
    GatewayConfig,
    GatewayUsageStats,
    LicenseStatus,
    calculate_request_cost,
    check_budget_limits,
    create_gateway_server,
    detect_token_blowout,
    dispatch_alert_webhook,
    get_gateway_daily_stats,
    init_gateway_db,
    process_chat_completion,
    record_enforcer_usage,
    record_gateway_token_usage,
    verify_polar_license,
)


# ---------------------------------------------------------------------------
# 1. Polar License Verification Tests
# ---------------------------------------------------------------------------


def test_verify_polar_license_deterministic_valid() -> None:
    """Verify deterministic validation for valid Polar test/live keys."""
    res = verify_polar_license("polar_test_valid_key_123")
    assert res.valid is True
    assert res.status == "active"
    assert res.plan == "pro"
    assert res.customer_id is not None
    assert "verified" in res.message.lower()

    res_live = verify_polar_license("polar_live_production_999")
    assert res_live.valid is True
    assert res_live.status == "active"

    res_pro = verify_polar_license("iktisad_pro_subscriber_abc")
    assert res_pro.valid is True
    assert res_pro.status == "active"


def test_verify_polar_license_deterministic_expired() -> None:
    """Verify deterministic rejection for expired keys."""
    res = verify_polar_license("polar_test_expired_key")
    assert res.valid is False
    assert res.status == "expired"
    assert "expired" in res.message.lower()


def test_verify_polar_license_deterministic_revoked() -> None:
    """Verify deterministic rejection for revoked keys."""
    res = verify_polar_license("polar_test_revoked_key")
    assert res.valid is False
    assert res.status == "revoked"
    assert "revoked" in res.message.lower()


def test_verify_polar_license_deterministic_invalid() -> None:
    """Verify deterministic rejection for invalid keys."""
    res = verify_polar_license("polar_test_invalid_token")
    assert res.valid is False
    assert res.status == "invalid"


def test_verify_polar_license_empty_or_none() -> None:
    """Verify missing or blank license keys return invalid status."""
    assert verify_polar_license("").valid is False
    assert verify_polar_license("   ").valid is False
    assert verify_polar_license("").status == "invalid"


def test_verify_polar_license_offline_grace_cache(tmp_path: Path) -> None:
    """Verify 24-hour offline grace caching works when external endpoint is unreachable."""
    key = "custom_unrecognized_corp_key_456"
    import hashlib
    key_hash = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
    cache_file = tmp_path / f"polar_license_{key_hash}.json"

    # Pre-populate valid cache file created 1 hour ago
    cache_file.write_text(
        json.dumps(
            {
                "valid": True,
                "status": "active",
                "plan": "enterprise",
                "customer_id": "cust_cached_corp",
                "expires_at": "2027-01-01T00:00:00Z",
                "verified_at_epoch": time.time() - 3600,
            }
        ),
        encoding="utf-8",
    )

    # Call with non-routable port to force network failure
    res = verify_polar_license(
        key,
        cache_dir=tmp_path,
        offline_grace_seconds=86_400,
        validation_url="http://127.0.0.1:59999/unreachable",
    )

    assert res.valid is True
    assert res.status == "grace_period"
    assert res.plan == "enterprise"
    assert res.customer_id == "cust_cached_corp"
    assert res.cached is True
    assert "grace cache" in res.message.lower()


def test_verify_polar_license_grace_cache_expired(tmp_path: Path) -> None:
    """Verify offline grace cache is rejected if older than 24 hours."""
    key = "stale_corp_key_789"
    import hashlib
    key_hash = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
    cache_file = tmp_path / f"polar_license_{key_hash}.json"

    # Pre-populate cache file created 25 hours ago (> 86,400s)
    cache_file.write_text(
        json.dumps(
            {
                "valid": True,
                "status": "active",
                "plan": "pro",
                "verified_at_epoch": time.time() - 90_000,
            }
        ),
        encoding="utf-8",
    )

    res = verify_polar_license(
        key,
        cache_dir=tmp_path,
        offline_grace_seconds=86_400,
        validation_url="http://127.0.0.1:59999/unreachable",
    )

    assert res.valid is False
    assert res.status == "unreachable"
    assert "unreachable and no valid 24h grace cache" in res.message


# ---------------------------------------------------------------------------
# 2. Hard Budget Enforcer & Cost Calculation Tests
# ---------------------------------------------------------------------------


def test_calculate_request_cost() -> None:
    """Verify deterministic request cost calculation across models."""
    # gpt-4o: $5.00 / 1M prompt, $15.00 / 1M completion
    cost_gpt4o = calculate_request_cost(prompt_tokens=1_000_000, completion_tokens=1_000_000, model="gpt-4o")
    assert cost_gpt4o == 20.0

    # gpt-4o-mini: $0.15 / 1M prompt, $0.60 / 1M completion
    cost_mini = calculate_request_cost(prompt_tokens=2_000_000, completion_tokens=1_000_000, model="gpt-4o-mini")
    assert cost_mini == round((2 * 0.15) + 0.60, 6)

    # gemini-1.5-flash: $0.075 / 1M prompt
    cost_flash = calculate_request_cost(prompt_tokens=10_000, completion_tokens=0, model="gemini-1.5-flash")
    assert cost_flash == 0.00075

    # Fallback default model
    cost_default = calculate_request_cost(prompt_tokens=500_000, completion_tokens=0, model="unknown-custom-model")
    assert cost_default == 1.0


def test_budget_enforcer_token_limits() -> None:
    """Verify BudgetEnforcer trips when session token limit is exceeded."""
    enforcer = BudgetEnforcer(max_tokens=1_000)

    # 1. Initial state
    tripped, _ = check_budget_limits(enforcer, anticipated_tokens=500)
    assert tripped is False

    # 2. Record 800 tokens
    record_enforcer_usage(enforcer, prompt_tokens=600, completion_tokens=200)
    assert enforcer.session_tokens == 800
    assert enforcer.circuit_breaker_tripped is False

    # 3. Next request with 300 tokens breaches 1,000 ceiling
    tripped, reason = check_budget_limits(enforcer, anticipated_tokens=300)
    assert tripped is True
    assert "token limit breached" in (reason or "").lower()
    assert enforcer.circuit_breaker_tripped is True

    # 4. Reset restores normal state
    enforcer.reset_session()
    assert enforcer.session_tokens == 0
    assert enforcer.circuit_breaker_tripped is False


def test_budget_enforcer_dollar_limits() -> None:
    """Verify BudgetEnforcer trips when USD spending budget is breached."""
    # Set hard budget to $0.05 USD
    enforcer = BudgetEnforcer(max_budget_usd=0.05)

    # Spend $0.04 using gpt-4o (8,000 prompt tokens = 8,000 / 1,000,000 * 5 = $0.04)
    cost = record_enforcer_usage(enforcer, prompt_tokens=8_000, completion_tokens=0, model="gpt-4o")
    assert cost == 0.04
    assert enforcer.circuit_breaker_tripped is False

    # Check request anticipated at 4,000 prompt tokens ($0.02) -> total $0.06 > $0.05 limit
    tripped, reason = check_budget_limits(enforcer, anticipated_tokens=4_000, model="gpt-4o")
    assert tripped is True
    assert "dollar budget circuit breaker tripped" in (reason or "").lower()
    assert "exceeds hard limit of $0.05" in (reason or "")


def test_budget_enforcer_alert_webhook_safe_handling() -> None:
    """Verify dispatch_alert_webhook handles unreachable URLs gracefully without throwing."""
    # Dispatching to an invalid endpoint must return False without crashing
    res = dispatch_alert_webhook("http://127.0.0.1:59998/no_webhook", "Test breaker trip")
    assert res is False

    # Empty URL returns False immediately
    assert dispatch_alert_webhook("", "Test") is False


def test_gateway_sqlite_cost_ledger_recording(tmp_path: Path) -> None:
    """Verify SQLite ledger persists cost_usd and calculates total daily spend."""
    db_file = str(tmp_path / "test_gateway_cost.db")
    init_gateway_db(db_file)

    record_gateway_token_usage(
        db_path=db_file,
        model="gpt-4o",
        original_tokens=10_000,
        compressed_tokens=4_000,
        cost_usd=0.020,
    )
    record_gateway_token_usage(
        db_path=db_file,
        model="claude-3-5-sonnet",
        original_tokens=5_000,
        compressed_tokens=2_000,
        cost_usd=0.006,
    )

    stats = get_gateway_daily_stats(db_file)
    assert stats.total_requests == 2
    assert stats.original_tokens == 15_000
    assert stats.compressed_tokens == 6_000
    assert stats.saved_tokens == 9_000
    assert stats.total_cost_usd == 0.026


# ---------------------------------------------------------------------------
# 3. Context Blowout Detection Tests
# ---------------------------------------------------------------------------


def test_detect_token_blowout_prompt_threshold() -> None:
    """Verify blowout detection when prompt token count exceeds ceiling."""
    safe_payload = {
        "messages": [{"role": "user", "content": "Hello world"}]
    }
    tripped, reason = detect_token_blowout(safe_payload, max_prompt_tokens=100)
    assert tripped is False
    assert reason is None

    # Multiple small messages where none exceeds single message bounds,
    # but aggregate token count (5 * 35 = 175 tokens) exceeds 100 token ceiling.
    large_payload = {
        "messages": [{"role": "user", "content": "short sentence words " * 8} for _ in range(5)]
    }
    tripped_blow, reason_blow = detect_token_blowout(large_payload, max_prompt_tokens=100)
    assert tripped_blow is True
    assert "prompt tokens" in (reason_blow or "").lower()


def test_detect_token_blowout_completion_threshold() -> None:
    """Verify blowout detection when requested max completion tokens exceeds limit."""
    payload = {
        "messages": [{"role": "user", "content": "Test prompt"}],
        "max_tokens": 30_000,
    }
    tripped, reason = detect_token_blowout(payload, max_completion_tokens=16_384)
    assert tripped is True
    assert "completion blowout risk" in (reason or "").lower()


def test_detect_token_blowout_single_message_runaway() -> None:
    """Verify blowout detection when a single message exceeds safe length ceiling."""
    # 50 tokens limit * 4 = 200 chars safe single message limit
    payload = {
        "messages": [
            {"role": "user", "content": "x" * 250}
        ]
    }
    tripped, reason = detect_token_blowout(payload, max_prompt_tokens=50)
    assert tripped is True
    assert "message blowout detected" in (reason or "").lower()


# ---------------------------------------------------------------------------
# 4. End-to-End Completion Pipeline Tests with Commercial Gates
# ---------------------------------------------------------------------------


def test_process_chat_completion_license_enforcement(tmp_path: Path) -> None:
    """Verify process_chat_completion enforces valid license when required."""
    db_file = str(tmp_path / "license_gate.db")

    payload = {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": "Hello."}],
    }

    # 1. Invalid license with require_license=True -> 401 Unauthorized
    cfg_invalid = GatewayConfig(
        db_path=db_file,
        license_key="polar_test_invalid_license",
        require_license=True,
    )
    res_invalid = process_chat_completion(payload, cfg_invalid)
    assert res_invalid.status_code == 401
    assert "License verification failed" in res_invalid.response_payload["error"]["message"]

    # 2. Valid license with require_license=True -> 200 OK
    cfg_valid = GatewayConfig(
        db_path=db_file,
        license_key="polar_test_valid_key_001",
        require_license=True,
    )
    res_valid = process_chat_completion(payload, cfg_valid)
    assert res_valid.status_code == 200
    assert res_valid.headers.get("X-Iktisad-License") == "active"


def test_process_chat_completion_budget_breaker_enforcement(tmp_path: Path) -> None:
    """Verify process_chat_completion returns 429 when BudgetEnforcer budget is exhausted."""
    db_file = str(tmp_path / "budget_gate.db")
    cfg = GatewayConfig(db_path=db_file)
    enforcer = BudgetEnforcer(max_budget_usd=0.003)  # $0.003 budget

    payload = {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": "Perform deep architectural analysis." * 50}],
    }

    # First request consumes ~$0.0023, succeeding within budget
    res1 = process_chat_completion(payload, cfg, enforcer=enforcer)
    assert res1.status_code == 200
    assert enforcer.session_cost_usd > 0.0

    # Next request breaches $0.003 budget limit -> 429 Quota Exceeded
    res2 = process_chat_completion(payload, cfg, enforcer=enforcer)
    assert res2.status_code == 429
    assert "circuit breaker tripped" in res2.response_payload["error"]["message"].lower()
    assert res2.circuit_breaker_tripped is True
    assert res2.headers.get("X-Iktisad-Circuit-Breaker") == "budget_tripped"


def test_process_chat_completion_blowout_breaker_tripped(tmp_path: Path) -> None:
    """Verify process_chat_completion returns 413 when context blowout cannot be reduced below ceiling."""
    db_file = str(tmp_path / "blowout_gate.db")
    cfg = GatewayConfig(
        db_path=db_file,
        max_prompt_tokens=50,  # Strict 50 token limit
    )

    # 1,000 non-compressible characters = ~250 tokens > 50 ceiling
    payload = {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": "random raw unstructured text " * 50}],
    }

    res = process_chat_completion(payload, cfg)
    assert res.status_code == 413
    assert "Context blowout breaker tripped" in res.response_payload["error"]["message"]
    assert res.circuit_breaker_tripped is True
    assert res.headers.get("X-Iktisad-Circuit-Breaker") == "blowout_tripped"


def test_process_chat_completion_blowout_rescued_by_compression(tmp_path: Path) -> None:
    """Verify that a large pytest log exceeding raw limit is rescued by compression and succeeds."""
    db_file = str(tmp_path / "blowout_rescued.db")
    cfg = GatewayConfig(
        db_path=db_file,
        max_prompt_tokens=150,  # Limit that raw log exceeds, but compressed fits under
        enable_cli_compression=True,
    )

    # Verbose test log: 400 chars (~100 tokens), raw message 800 chars (~200 tokens)
    noisy_log = (
        "=== test session starts ===\n"
        + "\n".join(f"test_file_{i}.py . [ {i * 10}%]" for i in range(1, 11))
        + "\n=== 10 passed in 1.2s ==="
    )
    payload = {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": noisy_log}],
    }

    res = process_chat_completion(payload, cfg)
    assert res.status_code == 200
    assert res.compressed_tokens <= 150
    assert res.circuit_breaker_tripped is False


# ---------------------------------------------------------------------------
# 5. CLI Gateway Subcommand and Commercial Flags Tests
# ---------------------------------------------------------------------------


def test_cli_gateway_subcommand_flags(tmp_path: Path) -> None:
    """Verify iktisad gateway subcommand parses and runs with commercial flags in no-block mode."""
    db_file = str(tmp_path / "cli_gw.db")

    ret = cli_main(
        [
            "gateway",
            "--port",
            "8991",
            "--license-key",
            "polar_test_live_commercial",
            "--max-budget-usd",
            "25.50",
            "--alert-webhook",
            "http://127.0.0.1:9999/alert",
            "--db-path",
            db_file,
            "--no-block",
        ]
    )
    assert ret == 0


def test_cli_gateway_require_license_failure() -> None:
    """Verify iktisad gateway halts with code 1 if --require-license fails validation."""
    ret = cli_main(
        [
            "gateway",
            "--license-key",
            "polar_test_invalid_key",
            "--require-license",
            "--no-block",
        ]
    )
    assert ret == 1


# ---------------------------------------------------------------------------
# 6. HTTP Server Live Commercial Integration Tests
# ---------------------------------------------------------------------------


def test_http_server_commercial_integration(tmp_path: Path) -> None:
    """Run live ThreadingHTTPServer with BudgetEnforcer and verify /health and /chat/completions."""
    db_file = str(tmp_path / "live_commercial_gw.db")
    enforcer = BudgetEnforcer(max_budget_usd=10.0, db_path=db_file)

    config = GatewayConfig(
        host="127.0.0.1",
        port=0,  # Dynamic open port
        db_path=db_file,
        license_key="polar_test_pro_valid",
        max_budget_usd=10.0,
    )

    server = create_gateway_server(config, enforcer=enforcer)
    assigned_port = server.server_address[1]

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        base_url = f"http://127.0.0.1:{assigned_port}"

        # 1. Check /v1/health exposes budget enforcer status
        with urllib.request.urlopen(f"{base_url}/v1/health", timeout=3.0) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert data["version"] == "0.2.0"
            assert "budget_enforcer" in data
            assert data["budget_enforcer"]["max_budget_usd"] == 10.0
            assert data["budget_enforcer"]["circuit_breaker_tripped"] is False

        # 2. POST /v1/chat/completions
        req_data = json.dumps(
            {
                "model": "gpt-4o",
                "messages": [{"role": "user", "content": "Testing commercial reverse proxy."}],
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            f"{base_url}/v1/chat/completions",
            data=req_data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=3.0) as resp:
            assert resp.status == 200
            res_json = json.loads(resp.read().decode("utf-8"))
            assert "choices" in res_json
            assert resp.headers.get("X-Iktisad-License") == "active"
            assert "X-Iktisad-Cost-USD" in resp.headers

        # Verify enforcer recorded the transaction
        assert enforcer.session_tokens > 0
        assert enforcer.session_cost_usd > 0.0

    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2.0)
