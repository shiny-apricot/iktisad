"""Unit tests for iktisad Model Context Protocol (MCP) server.

Conforms to Corporate Law V:
- Python 3.10+
- Top-level def test_*(): functions without class wrappers
- Pure functional assertions and deterministic local fixtures
"""

from __future__ import annotations

import io
import json
from pathlib import Path
import tempfile

import pytest

from iktisad.cli import main as cli_main
from iktisad.gateway import record_gateway_token_usage
from iktisad.mcp_server import (
    MCP_AVAILABLE_TOOLS,
    handle_mcp_request,
    run_stdio_server,
)


def test_mcp_initialize_handshake() -> None:
    """Verify standard MCP initialize handshake returns protocol and server metadata."""
    req = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "cursor", "version": "0.45.0"},
        },
    }
    resp = handle_mcp_request(req)
    assert resp["jsonrpc"] == "2.0"
    assert resp["id"] == 1
    assert "result" in resp
    assert resp["result"]["protocolVersion"] == "2024-11-05"
    assert resp["result"]["serverInfo"]["name"] == "iktisad-mcp"
    assert resp["result"]["serverInfo"]["version"] == "0.2.0"
    assert "tools" in resp["result"]["capabilities"]


def test_mcp_notifications_initialized() -> None:
    """Verify notifications/initialized is acknowledged without error."""
    req = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "notifications/initialized",
        "params": {},
    }
    resp = handle_mcp_request(req)
    assert resp["jsonrpc"] == "2.0"
    assert resp["id"] == 2
    assert "result" in resp


def test_mcp_tools_list() -> None:
    """Verify tools/list returns all four registered token defense tools."""
    req = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/list",
        "params": {},
    }
    resp = handle_mcp_request(req)
    assert resp["jsonrpc"] == "2.0"
    assert resp["id"] == 3
    tools = resp["result"]["tools"]
    tool_names = [t["name"] for t in tools]
    assert "compress_terminal_log" in tool_names
    assert "extract_ast_skeleton" in tool_names
    assert "select_frugal_model" in tool_names
    assert "check_circuit_breaker" in tool_names

    for tool in tools:
        assert "description" in tool
        assert "inputSchema" in tool
        assert tool["inputSchema"]["type"] == "object"


def test_mcp_tool_call_compress_terminal_log_clean() -> None:
    """Verify compress_terminal_log compresses clean pytest runs by >70%."""
    raw_pytest = (
        "============================= test session starts ==============================\n"
        "rootdir: /home/dev/app\n"
        "collecting ... collected 145 items\n"
        "test_a.py " + "." * 100 + "\n"
        "test_b.py " + "." * 45 + "\n"
        "============================== 145 passed in 2.14s =============================\n"
    )
    req = {
        "jsonrpc": "2.0",
        "id": 10,
        "method": "tools/call",
        "params": {
            "name": "compress_terminal_log",
            "arguments": {"raw_log": raw_pytest},
        },
    }
    resp = handle_mcp_request(req)
    assert resp["jsonrpc"] == "2.0"
    assert resp["id"] == 10
    assert not resp["result"]["isError"]
    content = json.loads(resp["result"]["content"][0]["text"])
    assert "OK:" in content["pruned_text"]
    assert content["has_error"] is False
    assert content["savings_pct"] >= 70.0


def test_mcp_tool_call_compress_terminal_log_failure() -> None:
    """Verify compress_terminal_log preserves root cause tracebacks on failure."""
    raw_failure = (
        "test_math.py::test_division FAILED\n"
        "=================================== FAILURES ===================================\n"
        "________________________________ test_division _________________________________\n"
        "    def test_division():\n"
        ">       assert 10 / 0 == 1\n"
        "E       ZeroDivisionError: division by zero\n"
        "tests/test_math.py:12: ZeroDivisionError\n"
        "=========================== 1 failed in 0.12s ==================================\n"
    )
    req = {
        "jsonrpc": "2.0",
        "id": 11,
        "method": "tools/call",
        "params": {
            "name": "compress_terminal_log",
            "arguments": {"raw_log": raw_failure},
        },
    }
    resp = handle_mcp_request(req)
    assert not resp["result"]["isError"]
    content = json.loads(resp["result"]["content"][0]["text"])
    assert content["has_error"] is True
    assert "ZeroDivisionError" in content["pruned_text"]


def test_mcp_tool_call_extract_ast_skeleton_from_code() -> None:
    """Verify extract_ast_skeleton correctly parses raw Python code string."""
    sample_code = (
        '"""User billing service."""\n'
        "import sys\n"
        "import os\n\n"
        "class PaymentProcessor:\n"
        '    """Handles credit card transactions."""\n'
        "    def charge(self, amount: int) -> bool:\n"
        '        """Charge amount in cents."""\n'
        "        return True\n\n"
        "def create_invoice(user_id: str) -> dict:\n"
        '    """Generate user invoice."""\n'
        "    return {'user': user_id}\n"
    )
    req = {
        "jsonrpc": "2.0",
        "id": 20,
        "method": "tools/call",
        "params": {
            "name": "extract_ast_skeleton",
            "arguments": {"code": sample_code},
        },
    }
    resp = handle_mcp_request(req)
    assert not resp["result"]["isError"]
    content = json.loads(resp["result"]["content"][0]["text"])
    assert content["imports_count"] == 2
    assert content["symbols_count"] >= 3
    assert "PaymentProcessor" in content["compact_skeleton"]
    assert "charge" in content["compact_skeleton"]
    assert "create_invoice" in content["compact_skeleton"]


def test_mcp_tool_call_extract_ast_skeleton_from_file(tmp_path: Path) -> None:
    """Verify extract_ast_skeleton reads and outlines a Python file on disk."""
    py_file = tmp_path / "service.py"
    py_file.write_text(
        "class HealthCheck:\n"
        "    def ping(self) -> str:\n"
        "        return 'pong'\n",
        encoding="utf-8",
    )
    req = {
        "jsonrpc": "2.0",
        "id": 21,
        "method": "tools/call",
        "params": {
            "name": "extract_ast_skeleton",
            "arguments": {"file_path": str(py_file)},
        },
    }
    resp = handle_mcp_request(req)
    assert not resp["result"]["isError"]
    content = json.loads(resp["result"]["content"][0]["text"])
    assert content["file_path"] == str(py_file)
    assert "HealthCheck" in content["compact_skeleton"]


def test_mcp_tool_call_select_frugal_model_type2() -> None:
    """Verify select_frugal_model routes reversible Type-2 tasks to Flash-Lite / Gemini 3.8 Flash."""
    req = {
        "jsonrpc": "2.0",
        "id": 30,
        "method": "tools/call",
        "params": {
            "name": "select_frugal_model",
            "arguments": {
                "task_kind": "lint_check",
                "heaviness": 2.0,
                "importance": 2.5,
                "is_irreversible": False,
            },
        },
    }
    resp = handle_mcp_request(req)
    assert not resp["result"]["isError"]
    content = json.loads(resp["result"]["content"][0]["text"])
    assert content["tier"] == 1
    assert "Flash" in content["recommended_2026_model"]
    assert content["is_irreversible"] is False


def test_mcp_tool_call_select_frugal_model_type1_sandwich() -> None:
    """Verify select_frugal_model enforces Sandwich Protocol for irreversible Type-1 tasks."""
    req = {
        "jsonrpc": "2.0",
        "id": 31,
        "method": "tools/call",
        "params": {
            "name": "select_frugal_model",
            "arguments": {
                "task_kind": "production_database_migration",
                "heaviness": 8.5,
                "importance": 9.0,
                "is_irreversible": True,
            },
        },
    }
    resp = handle_mcp_request(req)
    assert not resp["result"]["isError"]
    content = json.loads(resp["result"]["content"][0]["text"])
    assert content["tier"] == 4
    assert content["execution_pattern"] == "FLASH_PREP_ARGON_DECISION_FLASH_EXEC"
    assert "Sandwich Protocol" in content["recommended_2026_model"]


def test_mcp_tool_call_check_circuit_breaker(tmp_path: Path) -> None:
    """Verify check_circuit_breaker reflects token usage and trips when budget is breached."""
    db_file = tmp_path / "test_mcp_tokens.db"
    req = {
        "jsonrpc": "2.0",
        "id": 40,
        "method": "tools/call",
        "params": {
            "name": "check_circuit_breaker",
            "arguments": {
                "db_path": str(db_file),
                "daily_budget": 50_000,
            },
        },
    }
    resp = handle_mcp_request(req)
    assert not resp["result"]["isError"]
    content = json.loads(resp["result"]["content"][0]["text"])
    assert content["daily_budget"] == 50_000
    assert content["remaining_tokens"] == 50_000
    assert content["circuit_breaker_tripped"] is False

    # Simulate heavy usage breaching budget
    record_gateway_token_usage(
        db_path=str(db_file),
        model="claude-3-opus",
        original_tokens=60_000,
        compressed_tokens=55_000,
    )

    resp2 = handle_mcp_request(req)
    content2 = json.loads(resp2["result"]["content"][0]["text"])
    assert content2["circuit_breaker_tripped"] is True
    assert content2["remaining_tokens"] == 0


def test_mcp_unknown_tool_and_methods() -> None:
    """Verify error reporting for unknown tools and methods."""
    req_unknown_tool = {
        "jsonrpc": "2.0",
        "id": 90,
        "method": "tools/call",
        "params": {"name": "non_existent_tool", "arguments": {}},
    }
    resp_tool = handle_mcp_request(req_unknown_tool)
    assert "error" in resp_tool
    assert resp_tool["error"]["code"] == -32601

    req_unknown_method = {
        "jsonrpc": "2.0",
        "id": 91,
        "method": "custom/unknown",
        "params": {},
    }
    resp_method = handle_mcp_request(req_unknown_method)
    assert "error" in resp_method
    assert resp_method["error"]["code"] == -32601

    ping_req = {"jsonrpc": "2.0", "id": 92, "method": "ping"}
    resp_ping = handle_mcp_request(ping_req)
    assert resp_ping["result"] == {}


def test_mcp_invalid_json_handling() -> None:
    """Verify JSON parse error and invalid request responses."""
    resp_bad_json = handle_mcp_request("{malformed json")
    assert resp_bad_json["error"]["code"] == -32700

    resp_bad_type = handle_mcp_request([1, 2, 3])  # type: ignore[arg-type]
    assert resp_bad_type["error"]["code"] == -32600


def test_mcp_run_stdio_server_e2e() -> None:
    """Verify run_stdio_server processes newline-delimited JSON-RPC streams."""
    lines = [
        json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}),
        json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}),
        "",  # Empty line should be skipped cleanly
        json.dumps({
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "compress_terminal_log",
                "arguments": {"raw_log": "OK: 10 passed in 0.5s\n"},
            },
        }),
    ]
    stdin = io.StringIO("\n".join(lines) + "\n")
    stdout = io.StringIO()

    run_stdio_server(stdin=stdin, stdout=stdout)

    output_lines = [line.strip() for line in stdout.getvalue().splitlines() if line.strip()]
    assert len(output_lines) == 3

    r1 = json.loads(output_lines[0])
    assert r1["id"] == 1
    assert "protocolVersion" in r1["result"]

    r2 = json.loads(output_lines[1])
    assert r2["id"] == 2
    assert len(r2["result"]["tools"]) >= 4

    r3 = json.loads(output_lines[2])
    assert r3["id"] == 3
    assert not r3["result"]["isError"]


def test_cli_mcp_flag() -> None:
    """Verify iktisad --mcp flag invokes MCP server on stdio."""
    stdin_data = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping"}) + "\n"
    stdin = io.StringIO(stdin_data)
    stdout = io.StringIO()

    import sys
    orig_stdin = sys.stdin
    orig_stdout = sys.stdout
    try:
        sys.stdin = stdin
        sys.stdout = stdout
        code = cli_main(["--mcp"])
        assert code == 0
    finally:
        sys.stdin = orig_stdin
        sys.stdout = orig_stdout

    resp = json.loads(stdout.getvalue().strip())
    assert resp["id"] == 1
    assert resp["result"] == {}


def test_cli_pro_and_export_presets_flags(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify iktisad --pro and --export-presets flags output canonical polar url and presets."""
    code_pro = cli_main(["--pro"])
    assert code_pro == 0
    captured_pro = capsys.readouterr().out
    assert "https://buy.polar.sh/polar_cl_yzz3PkDzy0RGI5tD7PCly2oMkieyP5jUPKrF11bpqcA" in captured_pro
    assert "$10/mo" in captured_pro
    assert "cursor" in captured_pro
    assert "local_gateway" in captured_pro

    code_presets = cli_main(["--export-presets"])
    assert code_presets == 0
    captured_presets = capsys.readouterr().out
    data = json.loads(captured_presets)
    assert "cursor" in data
    assert "claude_code" in data
    assert "windsurf" in data
    assert "local_gateway" in data


def test_mcp_run_release_preflight_audit_tool() -> None:
    """Verify run_release_preflight_audit tool executes and returns PASS."""
    req = {
        "jsonrpc": "2.0",
        "id": 10,
        "method": "tools/call",
        "params": {
            "name": "run_release_preflight_audit",
            "arguments": {"base_dir": "."},
        },
    }
    resp = handle_mcp_request(req)
    assert resp["id"] == 10
    assert not resp["result"]["isError"]
    payload = json.loads(resp["result"]["content"][0]["text"])
    assert payload["version"] == "0.2.0"


def test_action_yml_and_marketplace_manifest_integrity() -> None:
    """Verify products/iktisad/action.yml exists, is composite, and wraps iktisad cli."""
    action_file = Path(__file__).resolve().parent.parent / "action.yml"
    assert action_file.is_file(), f"action.yml missing at {action_file}"
    content = action_file.read_text(encoding="utf-8")

    assert "using: 'composite'" in content or "using: composite" in content
    assert "iktisad.cli run --" in content
    assert "shiny-apricot" in content or "iktisad" in content


def test_smithery_json_mcp_manifest_integrity() -> None:
    """Verify products/iktisad/smithery.json exists, declares iktisad-mcp, and lists core tools."""
    smithery_file = Path(__file__).resolve().parent.parent / "smithery.json"
    assert smithery_file.is_file(), f"smithery.json missing at {smithery_file}"
    data = json.loads(smithery_file.read_text(encoding="utf-8"))

    assert data.get("name") == "iktisad"
    start_cmd = data.get("startCommand", {})
    assert start_cmd.get("command") == "iktisad-mcp"

    declared_tools = [t.get("name") for t in data.get("tools", [])]
    assert "compress_terminal_log" in declared_tools
    assert "extract_ast_skeleton" in declared_tools
    assert "select_frugal_model" in declared_tools
    assert "check_circuit_breaker" in declared_tools


def test_cli_compress_subcommand_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Verify iktisad compress <file> compresses noisy output cleanly."""
    log_file = tmp_path / "test.log"
    log_file.write_text("pytest\n..................\n18 passed in 0.05s\n", encoding="utf-8")

    code = cli_main(["compress", str(log_file)])
    assert code == 0
    out = capsys.readouterr().out
    assert "OK: 18 passed" in out

