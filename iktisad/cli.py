"""CLI entry point for iktisad."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from iktisad.core import (
    BandwidthGuard,
    audit_transcript_health,
    compress_cli_observation,
    extract_python_ast_skeleton,
    is_media_blocked,
    select_model_dynamically,
)
from iktisad.gateway import (
    BudgetEnforcer,
    GatewayConfig,
    serve_gateway,
    verify_polar_license,
)

POLAR_PRO_PRICE = "$10/mo"
POLAR_PRO_CHECKOUT_URL = "https://buy.polar.sh/polar_cl_yzz3PkDzy0RGI5tD7PCly2oMkieyP5jUPKrF11bpqcA"
POLAR_PRO_SUPPORT_EMAIL = "kenzailabs@gmail.com"


def get_pro_presets() -> dict[str, Any]:
    """Generate ready-to-use client presets for Cursor, Claude Code, Windsurf, and Gateway."""
    return {
        "cursor": {
            "name": "iktisad",
            "type": "stdio",
            "command": "iktisad",
            "args": ["--mcp"],
        },
        "claude_code": {
            "mcpServers": {
                "iktisad": {
                    "command": "iktisad",
                    "args": ["--mcp"],
                }
            }
        },
        "windsurf": {
            "mcpServers": {
                "iktisad": {
                    "command": "iktisad",
                    "args": ["--mcp"],
                }
            }
        },
        "local_gateway": {
            "base_url": "http://127.0.0.1:8000/v1",
            "route": "/v1/chat/completions",
            "daily_token_budget": 1_000_000,
            "frugal_mode": True,
        },
    }


def build_parser() -> argparse.ArgumentParser:
    """Build CLI argument parser with root flags and gateway subcommand."""
    parser = argparse.ArgumentParser(
        prog="iktisad",
        description="Zero-waste, frugal runtime & quota engine for AI agents",
    )
    parser.add_argument(
        "--compress-log",
        metavar="FILE",
        help="Compress terminal or pytest stdout log, stripping ANSI codes and boilerplate",
    )
    parser.add_argument(
        "--ast-skeleton",
        metavar="FILE",
        help="Extract compact AST signature skeleton from a Python source file",
    )
    parser.add_argument(
        "--route-task",
        metavar="KIND",
        help="Route an agent task dynamically (e.g. 'swe_bug_fix', 'code_review')",
    )
    parser.add_argument(
        "--heaviness",
        type=float,
        default=5.0,
        help="Reasoning heaviness (0.0 to 10.0, default: 5.0)",
    )
    parser.add_argument(
        "--importance",
        type=float,
        default=5.0,
        help="Strategic importance (0.0 to 10.0, default: 5.0)",
    )
    parser.add_argument(
        "--irreversible",
        action="store_true",
        help="Flag as Bezos Type-1 irreversible one-way door (enforces Sandwich Protocol)",
    )
    parser.add_argument(
        "--audit-transcript",
        metavar="FILE",
        help="Audit transcript JSONL for long-context bloat and cliff risk",
    )
    parser.add_argument(
        "--bandwidth-usage",
        action="store_true",
        help="Check and display daily bandwidth consumption from local SQLite cache",
    )
    parser.add_argument(
        "--check-media-url",
        metavar="URL",
        help="Check whether a URL is blocked under the Bandwidth Miser Protocol",
    )
    parser.add_argument(
        "--db-path",
        default=".cache/iktisad_cache.db",
        help="SQLite database path for bandwidth accounting (default: .cache/iktisad_cache.db)",
    )
    # Kenz Cloud Gateway root arguments (backward-compatibility)
    parser.add_argument(
        "--serve-gateway",
        action="store_true",
        help="Launch Kenz Cloud Gateway reverse-proxy server (/v1/chat/completions)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind Kenz Cloud Gateway (default: 8000)",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host interface to bind Kenz Cloud Gateway (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--daily-token-budget",
        type=int,
        default=1_000_000,
        help="Daily token budget before circuit breaker trips (default: 1,000,000)",
    )
    parser.add_argument(
        "--license-key",
        default="",
        help="Polar Pro / Enterprise license key for commercial deployment",
    )
    parser.add_argument(
        "--max-budget-usd",
        type=float,
        default=None,
        help="Hard spending budget limit in USD before circuit breaker cuts proxying",
    )
    parser.add_argument(
        "--alert-webhook",
        default=None,
        help="Webhook URL to dispatch budget breach and circuit breaker alerts",
    )
    parser.add_argument(
        "--max-prompt-tokens",
        type=int,
        default=32_000,
        help="Safe prompt token ceiling for context blowout detection (default: 32,000)",
    )
    parser.add_argument(
        "--require-license",
        action="store_true",
        help="Require valid Polar license before proxying",
    )
    parser.add_argument(
        "--no-block",
        action="store_true",
        help="Run gateway server without blocking main thread",
    )
    # Native MCP Server argument
    parser.add_argument(
        "--mcp",
        action="store_true",
        help="Launch native Model Context Protocol (MCP) server over stdio for Cursor/Claude Code/Windsurf",
    )
    # Polar.sh Pro Tier and Presets
    parser.add_argument(
        "--pro",
        action="store_true",
        help="Display Kenz Labs / Polar Pro Tier ($10/mo) benefits, status, and checkout URL",
    )
    parser.add_argument(
        "--export-presets",
        action="store_true",
        help="Export ready-to-use JSON presets for Cursor, Claude Code, Windsurf, and Local Gateway",
    )

    # Subcommand: iktisad gateway ...
    subparsers = parser.add_subparsers(dest="subcommand")
    gateway_parser = subparsers.add_parser(
        "gateway",
        help="Launch Kenz Cloud Gateway reverse-proxy server with token budget armor",
    )
    gateway_parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind Kenz Cloud Gateway (default: 8000)",
    )
    gateway_parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host interface to bind Kenz Cloud Gateway (default: 127.0.0.1)",
    )
    gateway_parser.add_argument(
        "--daily-token-budget",
        type=int,
        default=1_000_000,
        help="Daily token budget before circuit breaker trips (default: 1,000,000)",
    )
    gateway_parser.add_argument(
        "--license-key",
        default="",
        help="Polar Pro / Enterprise license key for commercial deployment",
    )
    gateway_parser.add_argument(
        "--max-budget-usd",
        type=float,
        default=None,
        help="Hard spending budget limit in USD before circuit breaker cuts proxying",
    )
    gateway_parser.add_argument(
        "--alert-webhook",
        default=None,
        help="Webhook URL to dispatch budget breach and circuit breaker alerts",
    )
    gateway_parser.add_argument(
        "--max-prompt-tokens",
        type=int,
        default=32_000,
        help="Safe prompt token ceiling for context blowout detection (default: 32,000)",
    )
    gateway_parser.add_argument(
        "--require-license",
        action="store_true",
        help="Require valid Polar license before proxying",
    )
    gateway_parser.add_argument(
        "--db-path",
        default=".cache/iktisad_gateway.db",
        help="SQLite database path for gateway ledger (default: .cache/iktisad_gateway.db)",
    )
    gateway_parser.add_argument(
        "--no-block",
        action="store_true",
        help="Run gateway server without blocking main thread",
    )

    return parser


def main(args: list[str] | None = None) -> int:
    """Run iktisad CLI."""
    parser = build_parser()
    parsed_args = parser.parse_args(args)

    if parsed_args.pro:
        presets = get_pro_presets()
        print("======================================================================")
        print("⚡ Kenz Labs — iktisad Polar Pro Tier ($10/mo)")
        print("======================================================================")
        print("Plan: Polar Pro Tier ($10/mo)")
        print("Status: Active & Available Worldwide")
        print(f"Checkout URL: {POLAR_PRO_CHECKOUT_URL}")
        print("\nIncluded Pro Benefits:")
        print("  ✓ Commercial Team Usage License: Full commercial enterprise deployment clearance")
        print(f"  ✓ Direct Priority Support: Direct developer support via {POLAR_PRO_SUPPORT_EMAIL}")
        print("  ✓ Custom Gateway Proxy Presets: Local & reverse-proxy configs with token budgeting")
        print("  ✓ Priority Issue Queue: Expedited issue triage (<24h SLA) on GitHub")
        print("\nReady-to-use Client Presets (JSON):")
        print(json.dumps(presets, indent=2))
        return 0

    if parsed_args.export_presets:
        presets = get_pro_presets()
        print(json.dumps(presets, indent=2))
        return 0

    if parsed_args.mcp:
        from iktisad.mcp_server import run_stdio_server
        run_stdio_server()
        return 0

    # Gateway launch (either `iktisad gateway` subcommand or `iktisad --serve-gateway`)
    is_gateway = (parsed_args.subcommand == "gateway") or getattr(parsed_args, "serve_gateway", False)
    if is_gateway:
        license_key = getattr(parsed_args, "license_key", "") or ""
        require_license = getattr(parsed_args, "require_license", False)
        max_budget_usd = getattr(parsed_args, "max_budget_usd", None)
        alert_webhook = getattr(parsed_args, "alert_webhook", None)
        max_prompt_tokens = getattr(parsed_args, "max_prompt_tokens", 32_000)
        db_path = getattr(parsed_args, "db_path", ".cache/iktisad_gateway.db")

        if license_key or require_license:
            lic = verify_polar_license(license_key)
            if lic.valid:
                print(f"  [Polar License] Active ({lic.plan.upper()}) - {lic.message}")
            else:
                print(f"  [Polar License Warning] {lic.message} (status: {lic.status})")
                if require_license:
                    print("  Error: Required commercial license verification failed. Halting.", file=sys.stderr)
                    return 1

        config = GatewayConfig(
            host=parsed_args.host,
            port=parsed_args.port,
            daily_token_budget=parsed_args.daily_token_budget,
            db_path=db_path,
            license_key=license_key,
            require_license=require_license,
            max_budget_usd=max_budget_usd,
            alert_webhook=alert_webhook,
            max_prompt_tokens=max_prompt_tokens,
        )

        enforcer = None
        if max_budget_usd is not None or alert_webhook is not None:
            enforcer = BudgetEnforcer(
                max_budget_usd=max_budget_usd,
                alert_webhook=alert_webhook,
                db_path=db_path,
            )

        block = not parsed_args.no_block
        serve_gateway(config=config, block=block, enforcer=enforcer)
        return 0

    if parsed_args.compress_log:
        path = Path(parsed_args.compress_log)
        if not path.is_file():
            print(f"Error: file not found: {parsed_args.compress_log}", file=sys.stderr)
            return 1
        raw = path.read_text(encoding="utf-8", errors="replace")
        obs = compress_cli_observation(raw)
        print(f"Original: {obs.raw_chars:,} chars -> Compressed: {obs.compressed_chars:,} chars ({obs.savings_pct:.1f}% savings)")
        print("-" * 50)
        print(obs.pruned_text)
        return 0

    if parsed_args.ast_skeleton:
        path = Path(parsed_args.ast_skeleton)
        if not path.is_file():
            print(f"Error: file not found: {parsed_args.ast_skeleton}", file=sys.stderr)
            return 1
        skel = extract_python_ast_skeleton(path)
        print(skel.render_compact())
        return 0

    if parsed_args.route_task:
        dec = select_model_dynamically(
            task_kind=parsed_args.route_task,
            heaviness=parsed_args.heaviness,
            importance=parsed_args.importance,
            is_irreversible=parsed_args.irreversible,
        )
        print(f"Task: {parsed_args.route_task}")
        print(f"Recommended Tier: {dec.tier} ({dec.tier_name})")
        print(f"Model: {dec.model_name}")
        print(f"Argon Allowed: {dec.argon_allowed}")
        print(f"Execution Pattern: {dec.execution_pattern}")
        print(f"Rationale: {dec.reason}")
        return 0

    if parsed_args.audit_transcript:
        path = Path(parsed_args.audit_transcript)
        rep = audit_transcript_health(path)
        print(f"Transcript: {rep.transcript_path}")
        print(f"File Size: {rep.file_size_bytes:,} bytes")
        print(f"Health Status: {rep.health_status}")
        print(f"Recommendation: {rep.recommendation}")
        return 0

    if parsed_args.bandwidth_usage:
        guard = BandwidthGuard(db_path=parsed_args.db_path)
        summary = guard.get_usage()
        print(f"Bandwidth Usage Report ({summary.date_str}):")
        print(f"  Total Transferred: {summary.total_megabytes_transferred:.3f} MB / {summary.max_daily_megabytes:.1f} MB")
        print(f"  Remaining Quota: {summary.remaining_megabytes:.3f} MB")
        print(f"  Network Requests: {summary.network_requests}")
        print(f"  Cache Hits: {summary.cached_hits}")
        print(f"  Quota Breached: {summary.quota_exceeded}")
        return 0

    if parsed_args.check_media_url:
        blocked = is_media_blocked(parsed_args.check_media_url)
        print(f"URL: {parsed_args.check_media_url}")
        print(f"Media Blocked: {blocked}")
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
