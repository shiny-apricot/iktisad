"""Model Context Protocol (MCP) JSON-RPC Server for Iktisad Token Defense.

Table of Contents:
------------------
1. Protocol Constants & Server Metadata
2. MCP Tool Specifications (AVAILABLE_TOOLS)
3. Tool Execution Dispatchers
   - run_compress_terminal_log
   - run_extract_ast_skeleton
   - run_select_frugal_model
   - run_check_circuit_breaker
4. JSON-RPC Request Handler (handle_mcp_request)
5. Stdio Communication Server Runner (run_stdio_server, main)

Provides standard MCP tool interfaces for AI coding agents (Cursor, Claude Code, Windsurf, Antigravity)
to autonomously compress terminal logs, extract AST outlines, route models frugally,
and inspect token circuit breaker health over stdio.
"""

from __future__ import annotations

import ast
from dataclasses import asdict
import json
from pathlib import Path
import sys
from typing import Any, TextIO

from iktisad.core import (
    PythonASTSkeleton,
    SymbolSpan,
    compress_cli_observation,
    extract_python_ast_skeleton,
    select_model_dynamically,
)
from iktisad.gateway import (
    GatewayUsageStats,
    get_gateway_daily_stats,
    init_gateway_db,
)

# ---------------------------------------------------------------------------
# 1. Protocol Constants & Server Metadata
# ---------------------------------------------------------------------------

MCP_PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {
    "name": "iktisad-mcp",
    "version": "0.1.0",
}

# ---------------------------------------------------------------------------
# 2. MCP Tool Specifications
# ---------------------------------------------------------------------------

MCP_AVAILABLE_TOOLS: list[dict[str, Any]] = [
    {
        "name": "compress_terminal_log",
        "description": (
            "Compress noisy terminal, pytest, or compiler stdout/stderr by 80-97%. "
            "Strips ANSI codes, progress bars, and passing tests while strictly isolating "
            "root-cause tracebacks and assertion errors to stop thinking token bloat."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "raw_log": {
                    "type": "string",
                    "description": "Raw terminal output with ANSI sequences, spinners, or test frames.",
                },
                "max_chars": {
                    "type": "integer",
                    "description": "Maximum character length for compressed text (default: 1200).",
                    "default": 1200,
                },
            },
            "required": ["raw_log"],
        },
    },
    {
        "name": "extract_ast_skeleton",
        "description": (
            "Extract class and function signatures, line ranges, and docstrings from Python source "
            "code at 0 LLM tokens. Allows agents to locate target functions without reading entire files."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to Python source file on disk.",
                },
                "code": {
                    "type": "string",
                    "description": "Raw Python source code string to skeletonize directly if not reading from disk.",
                },
            },
        },
    },
    {
        "name": "select_frugal_model",
        "description": (
            "Dynamically routes tasks based on Bezos Type-1 (irreversible) vs Type-2 (reversible) doors. "
            "Recommends frugal sub-cent models (Gemini 3.8 Flash, local models) for mechanical tasks, "
            "or the 2026 Sandwich Protocol (prep <600 tokens -> Claude Opus 5.5 / Claude Fable / o3 / DeepSeek-R1 -> Flash exec) "
            "for irreversible architectural decisions."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "task_kind": {
                    "type": "string",
                    "description": "Task descriptor (e.g. 'lint_check', 'refactor', 'deploy_db', 'fix_security_flaw').",
                    "default": "general",
                },
                "heaviness": {
                    "type": "number",
                    "description": "Reasoning heaviness (0.0 to 10.0, default: 5.0).",
                    "default": 5.0,
                },
                "importance": {
                    "type": "number",
                    "description": "Strategic importance (0.0 to 10.0, default: 5.0).",
                    "default": 5.0,
                },
                "is_irreversible": {
                    "type": "boolean",
                    "description": "True for Bezos Type-1 irreversible one-way doors.",
                    "default": False,
                },
            },
            "required": ["task_kind"],
        },
    },
    {
        "name": "check_circuit_breaker",
        "description": (
            "Inspect daily token consumption, remaining budget, and circuit breaker status "
            "from the local SQLite ledger to prevent runaway agent loops and $50/day bill spikes."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "db_path": {
                    "type": "string",
                    "description": "SQLite token ledger path (default: .cache/iktisad_gateway.db).",
                    "default": ".cache/iktisad_gateway.db",
                },
                "daily_budget": {
                    "type": "integer",
                    "description": "Daily token budget cap (default: 1,000,000).",
                    "default": 1000000,
                },
            },
        },
    },
]

# ---------------------------------------------------------------------------
# 3. Tool Execution Dispatchers
# ---------------------------------------------------------------------------


def run_compress_terminal_log(arguments: dict[str, Any]) -> str:
    """Execute compress_terminal_log tool."""
    raw_log = str(arguments.get("raw_log", ""))
    max_chars = int(arguments.get("max_chars", 1200))
    obs = compress_cli_observation(raw_output=raw_log, max_chars=max_chars)
    payload = {
        "pruned_text": obs.pruned_text,
        "raw_chars": obs.raw_chars,
        "compressed_chars": obs.compressed_chars,
        "savings_pct": obs.savings_pct,
        "has_error": obs.has_error,
    }
    return json.dumps(payload, indent=2)


def run_extract_ast_skeleton(arguments: dict[str, Any]) -> str:
    """Execute extract_ast_skeleton tool."""
    file_path_str = str(arguments.get("file_path", "")).strip()
    raw_code = arguments.get("code")

    if file_path_str and Path(file_path_str).is_file():
        skel = extract_python_ast_skeleton(file_path_str)
    elif raw_code is not None:
        try:
            tree = ast.parse(str(raw_code), filename="<in_memory>")
            doc = ast.get_docstring(tree) or ""
            doc_sum = doc.strip().splitlines()[0] if doc.strip() else ""
            imports_count = 0
            symbols: list[SymbolSpan] = []
            for stmt in tree.body:
                if isinstance(stmt, (ast.Import, ast.ImportFrom)):
                    imports_count += 1
                elif isinstance(stmt, ast.ClassDef):
                    s_l = stmt.lineno
                    e_l = getattr(stmt, "end_lineno", stmt.lineno)
                    c_doc = ast.get_docstring(stmt) or ""
                    c_sum = c_doc.strip().splitlines()[0] if c_doc.strip() else ""
                    bases = [ast.unparse(b) for b in stmt.bases]
                    base_str = f"({', '.join(bases)})" if bases else ""
                    symbols.append(
                        SymbolSpan(stmt.name, "class", s_l, e_l, f"class {stmt.name}{base_str}", c_sum)
                    )
                    for item in stmt.body:
                        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            m_s = item.lineno
                            m_e = getattr(item, "end_lineno", item.lineno)
                            m_doc = ast.get_docstring(item) or ""
                            m_sum = m_doc.strip().splitlines()[0] if m_doc.strip() else ""
                            prefix = "async def " if isinstance(item, ast.AsyncFunctionDef) else "def "
                            symbols.append(
                                SymbolSpan(
                                    f"{stmt.name}.{item.name}",
                                    "method",
                                    m_s,
                                    m_e,
                                    f"  {prefix}{item.name}(...)",
                                    m_sum,
                                )
                            )
                elif isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    f_s = stmt.lineno
                    f_e = getattr(stmt, "end_lineno", stmt.lineno)
                    f_doc = ast.get_docstring(stmt) or ""
                    f_sum = f_doc.strip().splitlines()[0] if f_doc.strip() else ""
                    prefix = "async def " if isinstance(stmt, ast.AsyncFunctionDef) else "def "
                    symbols.append(
                        SymbolSpan(stmt.name, "function", f_s, f_e, f"{prefix}{stmt.name}(...)", f_sum)
                    )
            skel = PythonASTSkeleton(
                file_path=file_path_str or "<in_memory>",
                docstring=doc_sum,
                imports_count=imports_count,
                symbols=tuple(symbols),
            )
        except Exception as exc:
            return json.dumps({"error": f"Failed to parse provided code: {exc}"}, indent=2)
    elif file_path_str:
        skel = extract_python_ast_skeleton(file_path_str)
    else:
        return json.dumps({"error": "Either file_path or code must be provided."}, indent=2)

    payload = {
        "file_path": skel.file_path,
        "docstring": skel.docstring,
        "imports_count": skel.imports_count,
        "symbols_count": len(skel.symbols),
        "compact_skeleton": skel.render_compact(),
        "symbols": [
            {
                "name": s.name,
                "kind": s.kind,
                "start_line": s.start_line,
                "end_line": s.end_line,
                "signature": s.signature.strip(),
                "docstring": s.docstring_summary,
            }
            for s in skel.symbols
        ],
    }
    return json.dumps(payload, indent=2)


def run_select_frugal_model(arguments: dict[str, Any]) -> str:
    """Execute select_frugal_model tool with 2026 reasoning models mapping."""
    task_kind = str(arguments.get("task_kind", "general"))
    heaviness = float(arguments.get("heaviness", 5.0))
    importance = float(arguments.get("importance", 5.0))
    is_irreversible = bool(arguments.get("is_irreversible", False))

    dec = select_model_dynamically(
        task_kind=task_kind,
        heaviness=heaviness,
        importance=importance,
        is_irreversible=is_irreversible,
    )

    # 2026 Model alignment metadata
    recommended_2026_model = "Gemini 3.8 Flash"
    if dec.tier == 0:
        recommended_2026_model = "Local AST / Pure Python (0 tokens)"
    elif dec.tier == 1:
        recommended_2026_model = "Gemini 3.8 Flash / Flash-Lite"
    elif dec.tier == 2 or dec.tier == 3:
        recommended_2026_model = "DeepSeek-R1 / o3-mini"
    elif dec.tier == 4:
        recommended_2026_model = "Sandwich Protocol: Gemini 3.8 Flash prep -> 1-shot Claude Opus 5.5 / Claude Fable / o3 -> Gemini 3.8 Flash exec"

    payload = {
        "task_kind": task_kind,
        "tier": dec.tier,
        "tier_name": dec.tier_name,
        "base_model": dec.model_name,
        "recommended_2026_model": recommended_2026_model,
        "is_irreversible": dec.is_irreversible,
        "criticality_score": dec.criticality_score,
        "execution_pattern": dec.execution_pattern,
        "reason": dec.reason,
    }
    return json.dumps(payload, indent=2)


def run_check_circuit_breaker(arguments: dict[str, Any]) -> str:
    """Execute check_circuit_breaker tool."""
    db_path = str(arguments.get("db_path", ".cache/iktisad_gateway.db"))
    daily_budget = int(arguments.get("daily_budget", 1_000_000))

    init_gateway_db(db_path)
    stats: GatewayUsageStats = get_gateway_daily_stats(
        db_path=db_path,
        daily_budget=daily_budget,
    )
    payload = {
        "date_str": stats.date_str,
        "total_requests": stats.total_requests,
        "original_tokens": stats.original_tokens,
        "compressed_tokens": stats.compressed_tokens,
        "saved_tokens": stats.saved_tokens,
        "savings_pct": stats.savings_pct,
        "daily_budget": stats.daily_budget,
        "remaining_tokens": stats.remaining_tokens,
        "circuit_breaker_tripped": stats.circuit_breaker_tripped,
    }
    return json.dumps(payload, indent=2)


# ---------------------------------------------------------------------------
# 4. JSON-RPC Request Handler
# ---------------------------------------------------------------------------


def handle_mcp_request(request: dict[str, Any] | str) -> dict[str, Any]:
    """Pure-function JSON-RPC 2.0 request handler for Model Context Protocol."""
    if isinstance(request, str):
        try:
            req_dict = json.loads(request)
        except json.JSONDecodeError:
            return {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": "Parse error: Invalid JSON"},
            }
    else:
        req_dict = request

    if not isinstance(req_dict, dict):
        return {
            "jsonrpc": "2.0",
            "id": None,
            "error": {"code": -32600, "message": "Invalid Request: expected JSON object"},
        }

    req_id = req_dict.get("id")
    method = req_dict.get("method")
    params = req_dict.get("params") or {}

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": SERVER_INFO,
            },
        }

    if method == "notifications/initialized":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {},
        }

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"tools": MCP_AVAILABLE_TOOLS},
        }

    if method == "tools/call":
        tool_name = params.get("name")
        arguments = params.get("arguments") or {}

        try:
            if tool_name == "compress_terminal_log":
                content_text = run_compress_terminal_log(arguments)
            elif tool_name == "extract_ast_skeleton":
                content_text = run_extract_ast_skeleton(arguments)
            elif tool_name == "select_frugal_model":
                content_text = run_select_frugal_model(arguments)
            elif tool_name == "check_circuit_breaker":
                content_text = run_check_circuit_breaker(arguments)
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {
                        "code": -32601,
                        "message": f"Method not found: Unknown tool '{tool_name}'",
                    },
                }

            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": content_text}],
                    "isError": False,
                },
            }

        except Exception as exc:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": f"Error executing tool {tool_name}: {exc}"}],
                    "isError": True,
                },
            }

    if method == "ping":
        return {"jsonrpc": "2.0", "id": req_id, "result": {}}

    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32601, "message": f"Method not found: '{method}'"},
    }


# ---------------------------------------------------------------------------
# 5. Stdio Communication Server Runner
# ---------------------------------------------------------------------------


def run_stdio_server(
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
) -> None:
    """Run MCP server in line-delimited JSON-RPC stdio mode."""
    in_stream = stdin or sys.stdin
    out_stream = stdout or sys.stdout

    for line in in_stream:
        stripped = line.strip()
        if not stripped:
            continue
        response = handle_mcp_request(stripped)
        out_stream.write(json.dumps(response) + "\n")
        out_stream.flush()


def main() -> None:
    """Entry point for iktisad-mcp CLI."""
    run_stdio_server()


if __name__ == "__main__":
    main()
