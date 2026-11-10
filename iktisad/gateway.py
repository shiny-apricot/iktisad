"""Kenz Cloud Gateway: Lightweight OpenAI-Compatible Reverse-Proxy with Pre-flight Frugality Engine.

=============================================================================
Table of Contents:
1. Data Models: GatewayConfig, GatewayUsageStats, GatewayCompletionResult
2. SQLite Token Ledger: init_gateway_db, record_gateway_token_usage, get_gateway_daily_stats, is_token_budget_exceeded
3. Pre-flight Frugality Engine: estimate_token_count, estimate_prompt_tokens, skeletonize_python_source, compress_message_content, apply_preflight_frugality
4. Forwarder Functions: default_mock_forwarder, http_upstream_forwarder
5. Completion Request Processor: process_chat_completion
6. HTTP Server & Handler: KenzGatewayHandler, create_gateway_server, serve_gateway
=============================================================================

Zero external dependencies: pure Python standard library (http.server, urllib, sqlite3).
Rooted in Zero-Waste Compute Principles and Autonomous Frugality.
"""

from __future__ import annotations

import ast
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import re
import sqlite3
import sys
import time
from typing import Any, Callable
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import uuid

from iktisad.core import (
    PythonASTSkeleton,
    SymbolSpan,
    compress_cli_observation,
    extract_python_ast_skeleton,
    select_model_dynamically,
)

logger = logging.getLogger("iktisad.gateway")

# ---------------------------------------------------------------------------
# 1. Data Models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GatewayConfig:
    """Configuration for Kenz Cloud Gateway reverse-proxy."""

    host: str = "127.0.0.1"
    port: int = 8000
    daily_token_budget: int = 1_000_000
    db_path: str = ".cache/iktisad_gateway.db"
    upstream_url: str = ""
    upstream_api_key: str = ""
    enable_cli_compression: bool = True
    enable_ast_skeleton: bool = True
    enable_dynamic_routing: bool = True
    default_fallback_model: str = "gemini-1.5-flash"


@dataclass(frozen=True)
class GatewayUsageStats:
    """Daily token consumption and quota statistics."""

    date_str: str
    total_requests: int
    original_tokens: int
    compressed_tokens: int
    saved_tokens: int
    savings_pct: float
    daily_budget: int
    remaining_tokens: int
    circuit_breaker_tripped: bool


@dataclass(frozen=True)
class GatewayCompletionResult:
    """Outcome of processing an OpenAI chat completion request."""

    status_code: int
    response_payload: dict[str, Any]
    original_tokens: int
    compressed_tokens: int
    savings_pct: float
    routed_model: str
    circuit_breaker_tripped: bool
    headers: dict[str, str]


# ---------------------------------------------------------------------------
# 2. SQLite Token Ledger
# ---------------------------------------------------------------------------


def init_gateway_db(db_path: str) -> None:
    """Initialize SQLite token ledger for the gateway."""
    if db_path != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS gateway_token_ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date_str TEXT NOT NULL,
                timestamp_utc TEXT NOT NULL,
                model TEXT NOT NULL,
                original_tokens INTEGER NOT NULL,
                compressed_tokens INTEGER NOT NULL,
                saved_tokens INTEGER NOT NULL
            );
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_gateway_date ON gateway_token_ledger(date_str);"
        )
        conn.commit()


def record_gateway_token_usage(
    db_path: str,
    model: str,
    original_tokens: int,
    compressed_tokens: int,
    timestamp_utc: str | None = None,
) -> None:
    """Record token consumption and savings in the gateway ledger."""
    init_gateway_db(db_path)
    now = datetime.now(timezone.utc)
    ts = timestamp_utc or now.isoformat()
    date_str = ts.split("T")[0]
    saved = max(0, original_tokens - compressed_tokens)

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO gateway_token_ledger (
                date_str, timestamp_utc, model, original_tokens, compressed_tokens, saved_tokens
            ) VALUES (?, ?, ?, ?, ?, ?);
            """,
            (date_str, ts, model, original_tokens, compressed_tokens, saved),
        )
        conn.commit()


def get_gateway_daily_stats(
    db_path: str,
    date_str: str | None = None,
    daily_budget: int = 1_000_000,
) -> GatewayUsageStats:
    """Compute daily token statistics and check circuit breaker state."""
    init_gateway_db(db_path)
    current_date = date_str or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT
                COUNT(id),
                COALESCE(SUM(original_tokens), 0),
                COALESCE(SUM(compressed_tokens), 0),
                COALESCE(SUM(saved_tokens), 0)
            FROM gateway_token_ledger
            WHERE date_str = ?;
            """,
            (current_date,),
        ).fetchone()

    total_requests = row[0] if row else 0
    orig_tokens = row[1] if row else 0
    comp_tokens = row[2] if row else 0
    saved_tokens = row[3] if row else 0

    savings_pct = (
        round(100.0 * (1.0 - (comp_tokens / orig_tokens)), 2)
        if orig_tokens > 0
        else 0.0
    )
    savings_pct = max(0.0, savings_pct)
    remaining = max(0, daily_budget - comp_tokens)
    tripped = comp_tokens >= daily_budget

    return GatewayUsageStats(
        date_str=current_date,
        total_requests=total_requests,
        original_tokens=orig_tokens,
        compressed_tokens=comp_tokens,
        saved_tokens=saved_tokens,
        savings_pct=savings_pct,
        daily_budget=daily_budget,
        remaining_tokens=remaining,
        circuit_breaker_tripped=tripped,
    )


def is_token_budget_exceeded(
    db_path: str,
    daily_budget: int = 1_000_000,
    anticipated_tokens: int = 0,
    date_str: str | None = None,
) -> tuple[bool, str | None]:
    """Check if token budget is exceeded or would be breached by anticipated tokens."""
    stats = get_gateway_daily_stats(db_path, date_str=date_str, daily_budget=daily_budget)
    if stats.circuit_breaker_tripped:
        return (
            True,
            f"Daily token budget circuit breaker tripped: {stats.compressed_tokens:,} tokens used >= {daily_budget:,} budget limit.",
        )
    if (stats.compressed_tokens + anticipated_tokens) > daily_budget:
        return (
            True,
            f"Daily token budget circuit breaker tripped: current {stats.compressed_tokens:,} + request {anticipated_tokens:,} > {daily_budget:,} budget limit.",
        )
    return (False, None)


# ---------------------------------------------------------------------------
# 3. Pre-flight Frugality Engine
# ---------------------------------------------------------------------------


def estimate_token_count(text: str) -> int:
    """Deterministically estimate LLM token count (~4 chars per token)."""
    if not text or not text.strip():
        return 0
    return max(1, (len(text.strip()) + 3) // 4)


def estimate_prompt_tokens(messages: list[dict[str, Any]]) -> int:
    """Calculate estimated prompt tokens for an OpenAI messages list."""
    total = 0
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            total += estimate_token_count(content) + 4
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    total += estimate_token_count(part.get("text", ""))
            total += 4
    return total


def skeletonize_python_source(source_code: str, pseudo_path: str = "snippet.py") -> str:
    """Extract AST skeleton from raw Python source string at 0 LLM token cost."""
    try:
        tree = ast.parse(source_code, filename=pseudo_path)
    except Exception:
        return source_code

    docstring = ast.get_docstring(tree) or ""
    doc_summary = docstring.strip().splitlines()[0] if docstring.strip() else ""

    imports_count = 0
    symbols: list[SymbolSpan] = []

    for stmt in tree.body:
        if isinstance(stmt, (ast.Import, ast.ImportFrom)):
            imports_count += 1
        elif isinstance(stmt, ast.ClassDef):
            start_l = stmt.lineno
            end_l = getattr(stmt, "end_lineno", stmt.lineno)
            c_doc = ast.get_docstring(stmt) or ""
            c_sum = c_doc.strip().splitlines()[0] if c_doc.strip() else ""
            bases = [ast.unparse(b) for b in stmt.bases]
            base_str = f"({', '.join(bases)})" if bases else ""
            symbols.append(
                SymbolSpan(stmt.name, "class", start_l, end_l, f"class {stmt.name}{base_str}", c_sum)
            )
            for item in stmt.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    m_start = item.lineno
                    m_end = getattr(item, "end_lineno", item.lineno)
                    m_doc = ast.get_docstring(item) or ""
                    m_sum = m_doc.strip().splitlines()[0] if m_doc.strip() else ""
                    prefix = "async def " if isinstance(item, ast.AsyncFunctionDef) else "def "
                    symbols.append(
                        SymbolSpan(
                            f"{stmt.name}.{item.name}",
                            "method",
                            m_start,
                            m_end,
                            f"  {prefix}{item.name}(...)",
                            m_sum,
                        )
                    )
        elif isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            start_l = stmt.lineno
            end_l = getattr(stmt, "end_lineno", stmt.lineno)
            f_doc = ast.get_docstring(stmt) or ""
            f_sum = f_doc.strip().splitlines()[0] if f_doc.strip() else ""
            prefix = "async def " if isinstance(stmt, ast.AsyncFunctionDef) else "def "
            symbols.append(
                SymbolSpan(stmt.name, "function", start_l, end_l, f"{prefix}{stmt.name}(...)", f_sum)
            )

    if not symbols:
        return source_code

    skel = PythonASTSkeleton(pseudo_path, doc_summary, imports_count, tuple(symbols))
    return skel.render_compact()


_PY_BLOCK_PATTERN = re.compile(r"```(?:python|py)\n(.*?)```", re.DOTALL)
_FILE_PATH_PATTERN = re.compile(r"(?:^|\s)(?:File|path|file):\s*([/\w\.\-\\]+\.py)\b", re.IGNORECASE)


def compress_python_blocks_in_text(text: str) -> tuple[str, bool]:
    """Identify and compress large Python source code or files into compact AST skeletons."""
    modified = False

    # 1. Check if the text references a concrete local python file on disk
    for match in _FILE_PATH_PATTERN.finditer(text):
        candidate_path = match.group(1).strip()
        p = Path(candidate_path)
        if p.is_file():
            skel = extract_python_ast_skeleton(p)
            skeleton_text = skel.render_compact()
            text = text.replace(candidate_path, f"{candidate_path}\n{skeleton_text}")
            modified = True

    # 2. Check for fenced Python code blocks ```python ... ```
    def _replace_py_block(match: re.Match[str]) -> str:
        nonlocal modified
        raw_code = match.group(1)
        # Only skeletonize code with substantive length (>= 5 lines or >= 120 chars)
        if len(raw_code.splitlines()) >= 5 or len(raw_code) >= 120:
            skel_str = skeletonize_python_source(raw_code)
            if len(skel_str) < len(raw_code):
                modified = True
                return f"```python\n# [AST Skeleton extracted by Kenz Cloud Gateway - 0 LLM token cost]\n{skel_str}\n```"
        return match.group(0)

    text = _PY_BLOCK_PATTERN.sub(_replace_py_block, text)

    # 3. Check if the entire message is raw Python code without fences
    if not modified and len(text.splitlines()) >= 8 and any(k in text for k in ("def ", "class ", "import ")):
        skel_str = skeletonize_python_source(text)
        if len(skel_str) < len(text) and "# File:" in skel_str:
            modified = True
            text = f"# [AST Skeleton extracted by Kenz Cloud Gateway - 0 LLM token cost]\n{skel_str}"

    return (text, modified)


def compress_message_content(
    content: str,
    enable_cli: bool = True,
    enable_ast: bool = True,
) -> tuple[str, bool]:
    """Apply CLI log compression and AST skeletonization to a single message string."""
    if not content or not content.strip():
        return (content, False)

    modified = False
    working = content

    # 1. CLI Log / Test Output Compression
    if enable_cli:
        # Check for typical indicators of terminal logs, pytests, or tracebacks
        cli_markers = (
            "\x1b[",
            "=== test session starts ===",
            "=== FAILURES ===",
            "Traceback (most recent call last):",
            "AssertionError",
            "collected ",
            " passed in ",
            " failed in ",
        )
        if any(marker in working for marker in cli_markers) or len(working.splitlines()) >= 15:
            obs = compress_cli_observation(working)
            if obs.compressed_chars < obs.raw_chars and obs.savings_pct > 0.0:
                working = obs.pruned_text
                modified = True

    # 2. AST Skeleton Extraction for Python
    if enable_ast:
        working, ast_modified = compress_python_blocks_in_text(working)
        if ast_modified:
            modified = True

    return (working, modified)


def apply_preflight_frugality(
    payload: dict[str, Any],
    config: GatewayConfig,
) -> tuple[dict[str, Any], int, int, float, str]:
    """Execute pre-flight compression and dynamic routing on OpenAI completion payload.

    Returns:
        (compressed_payload, original_tokens, compressed_tokens, savings_pct, routed_model)
    """
    raw_messages = payload.get("messages", [])
    original_tokens = estimate_prompt_tokens(raw_messages)

    # Transform messages
    compressed_messages: list[dict[str, Any]] = []
    for msg in raw_messages:
        new_msg = dict(msg)
        content = new_msg.get("content")
        if isinstance(content, str):
            compressed_content, _ = compress_message_content(
                content,
                enable_cli=config.enable_cli_compression,
                enable_ast=config.enable_ast_skeleton,
            )
            new_msg["content"] = compressed_content
        elif isinstance(content, list):
            new_parts: list[Any] = []
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    part_copy = dict(part)
                    c_text, _ = compress_message_content(
                        part_copy.get("text", ""),
                        enable_cli=config.enable_cli_compression,
                        enable_ast=config.enable_ast_skeleton,
                    )
                    part_copy["text"] = c_text
                    new_parts.append(part_copy)
                else:
                    new_parts.append(part)
            new_msg["content"] = new_parts
        compressed_messages.append(new_msg)

    # Dynamic Model Routing
    raw_model = str(payload.get("model", "auto")).strip()
    routed_model = raw_model

    if config.enable_dynamic_routing and raw_model in ("auto", "iktisad-frugal"):
        heaviness = float(payload.get("heaviness", 5.0))
        importance = float(payload.get("importance", 5.0))
        is_irreversible = bool(payload.get("is_irreversible", False))
        task_kind = str(payload.get("task_kind", "general"))

        decision = select_model_dynamically(
            task_kind=task_kind,
            heaviness=heaviness,
            importance=importance,
            is_irreversible=is_irreversible,
        )
        if decision.model_name in ("inherit", "zero_token_python"):
            routed_model = config.default_fallback_model
        else:
            routed_model = decision.model_name

    compressed_tokens = estimate_prompt_tokens(compressed_messages)
    savings_pct = (
        round(100.0 * (1.0 - (compressed_tokens / original_tokens)), 2)
        if original_tokens > 0
        else 0.0
    )
    savings_pct = max(0.0, savings_pct)

    compressed_payload = dict(payload)
    compressed_payload["messages"] = compressed_messages
    compressed_payload["model"] = routed_model

    return (compressed_payload, original_tokens, compressed_tokens, savings_pct, routed_model)


# ---------------------------------------------------------------------------
# 4. Forwarder Functions
# ---------------------------------------------------------------------------


def default_mock_forwarder(
    payload: dict[str, Any],
    headers: dict[str, str],
    routed_model: str,
    prompt_tokens: int,
    original_tokens: int,
    savings_pct: float,
) -> dict[str, Any]:
    """Default local OpenAI-compatible mock forwarder for zero-cost testing and local runtimes."""
    completion_id = f"chatcmpl-iktisad-{uuid.uuid4().hex[:12]}"
    created_ts = int(time.time())

    return {
        "id": completion_id,
        "object": "chat.completion",
        "created": created_ts,
        "model": routed_model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "Kenz Cloud Gateway: Request pre-processed and optimized successfully under Iktisad Frugality Protocol.",
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": 16,
            "total_tokens": prompt_tokens + 16,
        },
        "iktisad": {
            "original_tokens": original_tokens,
            "compressed_tokens": prompt_tokens,
            "savings_pct": savings_pct,
            "routed_model": routed_model,
        },
    }


def http_upstream_forwarder(
    payload: dict[str, Any],
    headers: dict[str, str],
    upstream_url: str,
    api_key: str = "",
    timeout: float = 30.0,
) -> dict[str, Any]:
    """Forward compressed payload to an external OpenAI-compatible upstream endpoint."""
    target_url = upstream_url.rstrip("/")
    if not target_url.endswith("/chat/completions"):
        target_url = f"{target_url}/chat/completions"

    req_data = json.dumps(payload).encode("utf-8")
    req_headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if api_key:
        req_headers["Authorization"] = f"Bearer {api_key}"

    req = urllib.request.Request(
        url=target_url,
        data=req_data,
        headers=req_headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            resp_body = resp.read().decode("utf-8")
            return json.loads(resp_body)
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")
        try:
            return json.loads(err_body)
        except Exception:
            return {"error": {"message": f"Upstream HTTP error {exc.code}: {exc.reason}", "code": exc.code}}
    except Exception as exc:
        return {"error": {"message": f"Upstream network failure: {exc}", "code": 502}}


# ---------------------------------------------------------------------------
# 5. Completion Request Processor
# ---------------------------------------------------------------------------


def process_chat_completion(
    payload: dict[str, Any],
    config: GatewayConfig,
    forwarder: Callable[[dict[str, Any], dict[str, str]], dict[str, Any]] | None = None,
) -> GatewayCompletionResult:
    """Execute complete frugality pipeline, circuit breaker gate, and forwarder dispatch."""
    # 1. Validation
    if not isinstance(payload, dict) or "messages" not in payload:
        return GatewayCompletionResult(
            status_code=400,
            response_payload={
                "error": {
                    "message": "Invalid request: missing required 'messages' array in payload.",
                    "type": "invalid_request_error",
                    "code": 400,
                }
            },
            original_tokens=0,
            compressed_tokens=0,
            savings_pct=0.0,
            routed_model="unknown",
            circuit_breaker_tripped=False,
            headers={"Content-Type": "application/json"},
        )

    # 2. Pre-check Circuit Breaker
    tripped, reason = is_token_budget_exceeded(config.db_path, config.daily_token_budget)
    if tripped:
        return GatewayCompletionResult(
            status_code=429,
            response_payload={
                "error": {
                    "message": reason or "Daily token budget exceeded.",
                    "type": "quota_exceeded_error",
                    "code": 429,
                }
            },
            original_tokens=0,
            compressed_tokens=0,
            savings_pct=0.0,
            routed_model=str(payload.get("model", "unknown")),
            circuit_breaker_tripped=True,
            headers={
                "Content-Type": "application/json",
                "X-Iktisad-Circuit-Breaker": "tripped",
                "Retry-After": "3600",
            },
        )

    # 3. Apply Frugality Transformation
    (
        compressed_payload,
        orig_tokens,
        comp_tokens,
        savings_pct,
        routed_model,
    ) = apply_preflight_frugality(payload, config)

    # 4. Post-compression Circuit Breaker Gate
    tripped_post, reason_post = is_token_budget_exceeded(
        config.db_path,
        config.daily_token_budget,
        anticipated_tokens=comp_tokens,
    )
    if tripped_post:
        return GatewayCompletionResult(
            status_code=429,
            response_payload={
                "error": {
                    "message": reason_post or "Daily token budget breached.",
                    "type": "quota_exceeded_error",
                    "code": 429,
                }
            },
            original_tokens=orig_tokens,
            compressed_tokens=comp_tokens,
            savings_pct=savings_pct,
            routed_model=routed_model,
            circuit_breaker_tripped=True,
            headers={
                "Content-Type": "application/json",
                "X-Iktisad-Circuit-Breaker": "tripped",
                "Retry-After": "3600",
            },
        )

    # 5. Formulate Response Headers
    response_headers = {
        "Content-Type": "application/json",
        "X-Iktisad-Original-Tokens": str(orig_tokens),
        "X-Iktisad-Compressed-Tokens": str(comp_tokens),
        "X-Iktisad-Savings-Pct": f"{savings_pct:.2f}%",
        "X-Iktisad-Model-Routed": routed_model,
    }

    # 6. Execute Forwarding
    if forwarder is not None:
        response_body = forwarder(compressed_payload, response_headers)
    elif config.upstream_url:
        response_body = http_upstream_forwarder(
            compressed_payload,
            response_headers,
            config.upstream_url,
            config.upstream_api_key,
        )
    else:
        response_body = default_mock_forwarder(
            compressed_payload,
            response_headers,
            routed_model,
            comp_tokens,
            orig_tokens,
            savings_pct,
        )

    # 7. Record Usage in SQLite Ledger
    record_gateway_token_usage(
        db_path=config.db_path,
        model=routed_model,
        original_tokens=orig_tokens,
        compressed_tokens=comp_tokens,
    )

    return GatewayCompletionResult(
        status_code=200,
        response_payload=response_body,
        original_tokens=orig_tokens,
        compressed_tokens=comp_tokens,
        savings_pct=savings_pct,
        routed_model=routed_model,
        circuit_breaker_tripped=False,
        headers=response_headers,
    )


# ---------------------------------------------------------------------------
# 6. HTTP Server & Handler
# ---------------------------------------------------------------------------


def create_gateway_handler(
    config: GatewayConfig,
    forwarder: Callable[[dict[str, Any], dict[str, str]], dict[str, Any]] | None = None,
) -> type[BaseHTTPRequestHandler]:
    """Create HTTP request handler class closed over config and forwarder."""

    class KenzGatewayHandler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:
            # Quiet logging in testing/production unless level is DEBUG
            logger.debug("%s - - [%s] %s\n", self.address_string(), self.log_date_time_string(), format % args)

        def do_GET(self) -> None:
            clean_path = self.path.split("?")[0].rstrip("/")
            if clean_path in ("/health", "/v1/health", ""):
                stats = get_gateway_daily_stats(config.db_path, daily_budget=config.daily_token_budget)
                body = {
                    "status": "healthy",
                    "service": "kenz-cloud-gateway",
                    "version": "0.1.0",
                    "daily_stats": asdict(stats),
                }
                body_bytes = json.dumps(body, indent=2).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body_bytes)))
                self.end_headers()
                self.wfile.write(body_bytes)
                return

            self.send_response(404)
            self.send_header("Content-Type", "application/json")
            err_bytes = json.dumps({"error": {"message": f"Endpoint not found: {self.path}", "code": 404}}).encode("utf-8")
            self.send_header("Content-Length", str(len(err_bytes)))
            self.end_headers()
            self.wfile.write(err_bytes)

        def do_POST(self) -> None:
            clean_path = self.path.split("?")[0].rstrip("/")
            if clean_path in ("/v1/chat/completions", "/chat/completions"):
                content_len = int(self.headers.get("Content-Length", 0))
                raw_body = self.rfile.read(content_len) if content_len > 0 else b"{}"
                try:
                    payload = json.loads(raw_body.decode("utf-8"))
                except Exception:
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json")
                    err = json.dumps({"error": {"message": "Malformed JSON payload.", "code": 400}}).encode("utf-8")
                    self.send_header("Content-Length", str(len(err)))
                    self.end_headers()
                    self.wfile.write(err)
                    return

                res = process_chat_completion(payload, config, forwarder)
                resp_bytes = json.dumps(res.response_payload).encode("utf-8")

                self.send_response(res.status_code)
                for k, v in res.headers.items():
                    self.send_header(k, v)
                self.send_header("Content-Length", str(len(resp_bytes)))
                self.end_headers()
                self.wfile.write(resp_bytes)
                return

            self.send_response(404)
            self.send_header("Content-Type", "application/json")
            err_bytes = json.dumps({"error": {"message": f"Endpoint not found: {self.path}", "code": 404}}).encode("utf-8")
            self.send_header("Content-Length", str(len(err_bytes)))
            self.end_headers()
            self.wfile.write(err_bytes)

    return KenzGatewayHandler


def create_gateway_server(
    config: GatewayConfig,
    forwarder: Callable[[dict[str, Any], dict[str, str]], dict[str, Any]] | None = None,
) -> ThreadingHTTPServer:
    """Instantiate a ThreadingHTTPServer bound to config.host and config.port."""
    handler_class = create_gateway_handler(config, forwarder)
    return ThreadingHTTPServer((config.host, config.port), handler_class)


def serve_gateway(
    config: GatewayConfig | None = None,
    block: bool = True,
    forwarder: Callable[[dict[str, Any], dict[str, str]], dict[str, Any]] | None = None,
) -> ThreadingHTTPServer:
    """Run Kenz Cloud Gateway reverse-proxy server."""
    cfg = config or GatewayConfig()
    server = create_gateway_server(cfg, forwarder)
    actual_port = server.server_address[1]
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Kenz Cloud Gateway active on http://{cfg.host}:{actual_port}")
    print(f"  Frugality Engine: CLI compression={cfg.enable_cli_compression}, AST skeleton={cfg.enable_ast_skeleton}")
    print(f"  Daily Token Budget: {cfg.daily_token_budget:,} tokens (Circuit Breaker armed)")
    print(f"  Endpoints: GET http://{cfg.host}:{actual_port}/v1/health | POST http://{cfg.host}:{actual_port}/v1/chat/completions")

    if block:
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down Kenz Cloud Gateway gracefully...")
            server.shutdown()

    return server
