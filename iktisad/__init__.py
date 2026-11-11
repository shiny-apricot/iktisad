"""İktisad: Zero-waste, frugal runtime & token defense engine for AI agents.

Token Governors, AST Skeletonizers, Circuit Breakers & Native MCP Server.
Rooted in Zero-Waste Compute Principles and Stafford Beer's Algedonic Filter.
"""

from __future__ import annotations

import importlib
from typing import Any

from iktisad.core import (
    BLOCKED_MEDIA_EXTENSIONS,
    BandwidthCacheEntry,
    BandwidthGuard,
    BandwidthProfile,
    BandwidthUsageSummary,
    BlockedResourceError,
    CLIPrunedObservation,
    DynamicModelDecision,
    FetchResult,
    IktisadResourceCheck,
    PythonASTSkeleton,
    QuotaExceededError,
    SymbolSpan,
    TranscriptHealthReport,
    audit_transcript_health,
    check_quota_available,
    compress_cli_observation,
    compress_terminal_output,
    evaluate_iktisad_resource_skepticism,
    extract_ast_skeleton,
    extract_python_ast_skeleton,
    fetch_url_efficiently,
    get_daily_usage,
    hash_url,
    init_bandwidth_db,
    is_media_blocked,
    lookup_cache_entry,
    record_bandwidth_usage,
    select_model_dynamically,
    store_cache_entry,
)
from iktisad.gateway import (
    BudgetEnforcer,
    GatewayCompletionResult,
    GatewayConfig,
    GatewayUsageStats,
    LicenseStatus,
    apply_preflight_frugality,
    calculate_request_cost,
    check_budget_limits,
    compress_message_content,
    compress_python_blocks_in_text,
    create_gateway_handler,
    create_gateway_server,
    default_mock_forwarder,
    detect_token_blowout,
    dispatch_alert_webhook,
    estimate_prompt_tokens,
    estimate_token_count,
    get_gateway_daily_stats,
    http_upstream_forwarder,
    init_gateway_db,
    is_token_budget_exceeded,
    process_chat_completion,
    record_enforcer_usage,
    record_gateway_token_usage,
    serve_gateway,
    skeletonize_python_source,
    verify_polar_license,
)

__version__ = "0.2.0"

_LAZY_MCP_EXPORTS: dict[str, str] = {
    "MCP_AVAILABLE_TOOLS": "iktisad.mcp_server",
    "handle_mcp_request": "iktisad.mcp_server",
    "run_stdio_server": "iktisad.mcp_server",
}


def __getattr__(name: str) -> Any:
    """PEP 562 lazy attribute loader to prevent eager import collisions with python -m iktisad.mcp_server."""
    if name in _LAZY_MCP_EXPORTS:
        mod = importlib.import_module(_LAZY_MCP_EXPORTS[name])
        val = getattr(mod, name)
        globals()[name] = val
        return val
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


def __dir__() -> list[str]:
    """Expose lazy attributes in dir()."""
    return sorted(set(list(globals().keys()) + list(_LAZY_MCP_EXPORTS.keys())))


__all__ = [
    "BLOCKED_MEDIA_EXTENSIONS",
    "BandwidthCacheEntry",
    "BandwidthGuard",
    "BandwidthProfile",
    "BandwidthUsageSummary",
    "BlockedResourceError",
    "BudgetEnforcer",
    "CLIPrunedObservation",
    "DynamicModelDecision",
    "FetchResult",
    "GatewayCompletionResult",
    "GatewayConfig",
    "GatewayUsageStats",
    "IktisadResourceCheck",
    "LicenseStatus",
    "MCP_AVAILABLE_TOOLS",
    "PythonASTSkeleton",
    "QuotaExceededError",
    "SymbolSpan",
    "TranscriptHealthReport",
    "apply_preflight_frugality",
    "audit_transcript_health",
    "calculate_request_cost",
    "check_budget_limits",
    "check_quota_available",
    "compress_cli_observation",
    "compress_message_content",
    "compress_python_blocks_in_text",
    "compress_terminal_output",
    "create_gateway_handler",
    "create_gateway_server",
    "default_mock_forwarder",
    "detect_token_blowout",
    "dispatch_alert_webhook",
    "estimate_prompt_tokens",
    "estimate_token_count",
    "evaluate_iktisad_resource_skepticism",
    "extract_ast_skeleton",
    "extract_python_ast_skeleton",
    "fetch_url_efficiently",
    "get_daily_usage",
    "get_gateway_daily_stats",
    "handle_mcp_request",
    "hash_url",
    "http_upstream_forwarder",
    "init_bandwidth_db",
    "init_gateway_db",
    "is_media_blocked",
    "is_token_budget_exceeded",
    "lookup_cache_entry",
    "process_chat_completion",
    "record_bandwidth_usage",
    "record_enforcer_usage",
    "record_gateway_token_usage",
    "run_stdio_server",
    "select_model_dynamically",
    "serve_gateway",
    "skeletonize_python_source",
    "store_cache_entry",
    "verify_polar_license",
]
