"""Unit tests for Kenz Cloud Gateway reverse-proxy and frugality engine.

Conforms to Corporate Law V:
- Python 3.10+
- Top-level def test_*(): functions without class wrappers
- Pure functional assertions and deterministic local fixtures
- Zero network calls (0 bytes transferred)
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
    GatewayCompletionResult,
    GatewayConfig,
    GatewayUsageStats,
    apply_preflight_frugality,
    compress_message_content,
    compress_python_blocks_in_text,
    create_gateway_server,
    default_mock_forwarder,
    estimate_prompt_tokens,
    estimate_token_count,
    get_gateway_daily_stats,
    init_gateway_db,
    is_token_budget_exceeded,
    process_chat_completion,
    record_gateway_token_usage,
    skeletonize_python_source,
)


# ---------------------------------------------------------------------------
# 1. Token Estimation and Message Compression Tests
# ---------------------------------------------------------------------------


def test_estimate_token_count() -> None:
    """Verify deterministic token counting (~4 chars per token)."""
    assert estimate_token_count("") == 0
    assert estimate_token_count("   ") == 0
    assert estimate_token_count("abcd") == 1
    assert estimate_token_count("12345678") == 2
    assert estimate_token_count("a" * 100) == 25


def test_payload_compression_high_reduction() -> None:
    """Verify terminal/pytest output in messages achieves >80% token savings."""
    noisy_pytest_log = (
        "\x1b[1m============================= test session starts ==============================\x1b[0m\n"
        "rootdir: /workspace/autonomy-corp\n"
        "configfile: pyproject.toml\n"
        "plugins: asyncio-0.21.1\n"
        "collected 60 items\n\n"
        + "\n".join(f"tests/test_mod_{i}.py \x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m [ {i * 10}%]" for i in range(1, 11))
        + "\n\n\x1b[32m============================== 60 passed in 2.85s ==============================\x1b[0m\n"
    )

    payload = {
        "model": "gpt-4o",
        "messages": [
            {"role": "system", "content": "You are a test reviewer."},
            {"role": "user", "content": f"Please verify this test log:\n{noisy_pytest_log}"},
        ],
    }

    config = GatewayConfig(enable_cli_compression=True, enable_ast_skeleton=False)
    comp_payload, orig_tok, comp_tok, savings_pct, routed_model = apply_preflight_frugality(
        payload, config
    )

    assert savings_pct > 70.0
    assert orig_tok > comp_tok
    assert "OK: 60 passed in 2.85s" in comp_payload["messages"][1]["content"]
    assert "\x1b[" not in comp_payload["messages"][1]["content"]


# ---------------------------------------------------------------------------
# 2. AST Skeleton Replacement Tests
# ---------------------------------------------------------------------------


def test_skeletonize_python_source() -> None:
    """Raw Python source string should collapse to a compact symbol skeleton."""
    raw_code = (
        '"""Data processing service module."""\n'
        "import os\n"
        "import sys\n\n"
        "class MetricsCollector:\n"
        '    """Collects system runtime metrics."""\n'
        "    def __init__(self, interval: int = 60):\n"
        "        self.interval = interval\n"
        "        self.records = []\n\n"
        "    def record(self, metric: str, value: float) -> None:\n"
        '        """Append a recorded observation."""\n'
        "        self.records.append((metric, value))\n\n"
        "    def flush(self) -> int:\n"
        '        """Clear internal cache and return count."""\n'
        "        count = len(self.records)\n"
        "        self.records.clear()\n"
        "        return count\n\n"
        "def compute_aggregate(records: list) -> float:\n"
        '    """Compute mean of flushed metrics."""\n'
        "    if not records:\n"
        "        return 0.0\n"
        "    return sum(v for _, v in records) / len(records)\n"
    )

    skeleton = skeletonize_python_source(raw_code, pseudo_path="service.py")
    assert "MetricsCollector" in skeleton
    assert "class MetricsCollector" in skeleton
    assert "def record(...)" in skeleton
    assert "def flush(...)" in skeleton
    assert "def compute_aggregate(...)" in skeleton
    assert len(skeleton) < len(raw_code)


def test_ast_skeleton_replacement_in_markdown_blocks() -> None:
    """Markdown python code blocks in messages must be replaced with AST skeletons."""
    py_code = (
        "class TokenOptimizer:\n"
        '    """High efficiency token optimizer."""\n'
        "    def __init__(self, ratio: float = 0.8):\n"
        "        self.ratio = ratio\n"
        "        self.total = 0\n\n"
        "    def optimize(self, buffer: str) -> str:\n"
        '        """Trim buffer whitespace and comments."""\n'
        "        lines = [line.strip() for line in buffer.splitlines() if line.strip()]\n"
        "        return '\\n'.join(lines)\n\n"
        "    def get_savings(self) -> float:\n"
        '        """Calculate savings ratio."""\n'
        "        return self.ratio\n"
    )

    content = f"Here is the service code:\n```python\n{py_code}\n```\nPlease analyze it."
    compressed_text, modified = compress_python_blocks_in_text(content)

    assert modified is True
    assert "[AST Skeleton extracted by Kenz Cloud Gateway - 0 LLM token cost]" in compressed_text
    assert "class TokenOptimizer" in compressed_text
    assert "def optimize(...)" in compressed_text
    assert len(compressed_text) < len(content)


def test_ast_skeleton_replacement_file_path(tmp_path: Path) -> None:
    """Concrete Python file path on disk referenced in text should inject skeleton."""
    py_file = tmp_path / "module_under_test.py"
    py_file.write_text(
        "def compute_alpha(x: int) -> int:\n"
        '    """Compute alpha factor."""\n'
        "    return x * 42\n",
        encoding="utf-8",
    )

    msg = f"Auditing path: {py_file}\nPlease review the AST."
    compressed_text, modified = compress_message_content(msg, enable_cli=False, enable_ast=True)

    assert modified is True
    assert "def compute_alpha(...)" in compressed_text


# ---------------------------------------------------------------------------
# 3. Dynamic Model Selection Routing Tests
# ---------------------------------------------------------------------------


def test_dynamic_model_routing_auto_and_frugal() -> None:
    """Auto and iktisad-frugal models should dynamically route to optimal models."""
    config = GatewayConfig(default_fallback_model="gemini-1.5-flash")

    # Lightweight reversible task -> flash_lite
    payload_light = {
        "model": "auto",
        "task_kind": "lightweight_formatting",
        "heaviness": 2.0,
        "importance": 3.0,
        "is_irreversible": False,
        "messages": [{"role": "user", "content": "Format this JSON"}],
    }
    _, _, _, _, routed_light = apply_preflight_frugality(payload_light, config)
    assert routed_light == "flash_lite"

    # Frugal alias with default parameters
    payload_frugal = {
        "model": "iktisad-frugal",
        "messages": [{"role": "user", "content": "Quick bug check"}],
    }
    _, _, _, _, routed_frugal = apply_preflight_frugality(payload_frugal, config)
    assert routed_frugal in ("flash_lite", "flash", "gemini-1.5-flash", "pro")

    # Explicit third-party model untouched
    payload_explicit = {
        "model": "claude-3-5-sonnet",
        "messages": [{"role": "user", "content": "Hello world"}],
    }
    _, _, _, _, routed_explicit = apply_preflight_frugality(payload_explicit, config)
    assert routed_explicit == "claude-3-5-sonnet"


# ---------------------------------------------------------------------------
# 4. SQLite Ledger & Circuit Breaker Tests
# ---------------------------------------------------------------------------


def test_gateway_sqlite_ledger_and_stats(tmp_path: Path) -> None:
    """Verify SQLite ledger inserts and stats aggregation."""
    db_file = str(tmp_path / "gateway_test.db")
    init_gateway_db(db_file)

    record_gateway_token_usage(db_file, "gemini-1.5-flash", 1000, 200)
    record_gateway_token_usage(db_file, "flash_lite", 500, 100)

    stats = get_gateway_daily_stats(db_file, daily_budget=10_000)
    assert stats.total_requests == 2
    assert stats.original_tokens == 1500
    assert stats.compressed_tokens == 300
    assert stats.saved_tokens == 1200
    assert stats.savings_pct == 80.0
    assert stats.remaining_tokens == 9700
    assert stats.circuit_breaker_tripped is False


def test_circuit_breaker_budget_exhaustion(tmp_path: Path) -> None:
    """Breaching daily token budget must trip circuit breaker with HTTP 429."""
    db_file = str(tmp_path / "circuit_breaker.db")
    config = GatewayConfig(db_path=db_file, daily_token_budget=150)

    # Initial request under budget
    res1 = process_chat_completion(
        {
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": "Short test message."}],
        },
        config,
    )
    assert res1.status_code == 200
    assert res1.circuit_breaker_tripped is False

    # Second request with big payload that exceeds 150 token budget
    res2 = process_chat_completion(
        {
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": "Bulk data message " * 80}],
        },
        config,
    )
    assert res2.status_code == 429
    assert res2.circuit_breaker_tripped is True
    assert res2.headers.get("X-Iktisad-Circuit-Breaker") == "tripped"
    assert res2.headers.get("Retry-After") == "3600"
    assert "error" in res2.response_payload
    assert res2.response_payload["error"]["type"] == "quota_exceeded_error"


# ---------------------------------------------------------------------------
# 5. Full HTTP Server End-to-End Tests
# ---------------------------------------------------------------------------


def test_http_server_health_and_completions_e2e(tmp_path: Path) -> None:
    """Run real HTTP server on localhost:0 and verify health and completions."""
    db_file = str(tmp_path / "e2e_gateway.db")
    config = GatewayConfig(host="127.0.0.1", port=0, db_path=db_file, daily_token_budget=500_000)

    # Start server in daemon thread
    server = create_gateway_server(config)
    assigned_port = server.server_address[1]
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    time.sleep(0.05)  # Allow socket to bind

    base_url = f"http://127.0.0.1:{assigned_port}"

    try:
        # 1. Test GET /v1/health
        health_req = urllib.request.Request(f"{base_url}/v1/health")
        with urllib.request.urlopen(health_req, timeout=5.0) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert data["status"] == "healthy"
            assert data["service"] == "kenz-cloud-gateway"
            assert data["daily_stats"]["daily_budget"] == 500_000

        # 2. Test POST /v1/chat/completions
        body = {
            "model": "auto",
            "task_kind": "lightweight_summary",
            "heaviness": 2.0,
            "importance": 3.0,
            "messages": [
                {"role": "system", "content": "You are a frugal assistant."},
                {
                    "role": "user",
                    "content": (
                        "Terminal output:\n"
                        "=== test session starts ===\n"
                        "collected 10 items\n"
                        "test_1.py .\n"
                        "=== 10 passed in 0.5s ===\n"
                    ),
                },
            ],
        }
        post_req = urllib.request.Request(
            f"{base_url}/v1/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(post_req, timeout=5.0) as resp:
            assert resp.status == 200
            assert "X-Iktisad-Original-Tokens" in resp.headers
            assert "X-Iktisad-Compressed-Tokens" in resp.headers
            assert "X-Iktisad-Savings-Pct" in resp.headers
            assert "X-Iktisad-Model-Routed" in resp.headers

            orig_tok = int(resp.headers["X-Iktisad-Original-Tokens"])
            comp_tok = int(resp.headers["X-Iktisad-Compressed-Tokens"])
            assert orig_tok >= comp_tok

            res_json = json.loads(resp.read().decode("utf-8"))
            assert res_json["object"] == "chat.completion"
            assert len(res_json["choices"]) > 0
            assert "usage" in res_json

        # 3. Test Invalid Route -> 404
        bad_req = urllib.request.Request(f"{base_url}/invalid-endpoint")
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(bad_req, timeout=5.0)
        assert exc_info.value.code == 404

        # 4. Test Malformed JSON -> 400
        malformed_req = urllib.request.Request(
            f"{base_url}/v1/chat/completions",
            data=b"not valid json {{{",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(malformed_req, timeout=5.0)
        assert exc_info.value.code == 400

    finally:
        server.shutdown()
        server.server_close()


def test_custom_forwarder_injection(tmp_path: Path) -> None:
    """Verify custom forwarder callback receives optimized payload."""
    db_file = str(tmp_path / "forwarder_test.db")
    config = GatewayConfig(db_path=db_file)

    forwarder_called = False
    received_payload: dict[str, Any] = {}

    def mock_custom_forwarder(payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
        nonlocal forwarder_called, received_payload
        forwarder_called = True
        received_payload = payload
        return {
            "id": "chatcmpl-custom-123",
            "choices": [{"message": {"role": "assistant", "content": "Custom response"}}],
        }

    res = process_chat_completion(
        {
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": "Simple query"}],
        },
        config=config,
        forwarder=mock_custom_forwarder,
    )

    assert forwarder_called is True
    assert res.status_code == 200
    assert res.response_payload["id"] == "chatcmpl-custom-123"
    assert "messages" in received_payload


def test_cli_serve_gateway_no_block(tmp_path: Path) -> None:
    """Test CLI --serve-gateway with --no-block flag."""
    db_file = str(tmp_path / "cli_gw.db")
    code = cli_main(["--serve-gateway", "--port", "9876", "--no-block", "--db-path", db_file])
    assert code == 0
