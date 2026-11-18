"""CLI entry point for iktisad."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from iktisad.core import (
    BandwidthGuard,
    _is_offering_live_and_verified,
    _load_verified_offerings_status,
    audit_transcript_health,
    compress_cli_observation,
    estimate_repo_enterprise_cost_avoidance,
    extract_python_ast_skeleton,
    fold_cascading_error_logs,
    generate_cfo_roi_audit_markdown,
    is_media_blocked,
    record_iktisad_roi_and_check_milestone,
    select_model_dynamically,
    slice_causal_ast_target,
)
from iktisad.gateway import (
    BudgetEnforcer,
    GatewayConfig,
    serve_gateway,
    verify_polar_license,
)

POLAR_PRO_PRICE = "$10/mo"
POLAR_PRO_CHECKOUT_URL = "https://buy.polar.sh/polar_cl_yzz3PkDzy0RGI5tD7PCly2oMkieyP5jUPKrF11bpqcA"
POLAR_PRO_SUPPORT_EMAIL = "kenzailab@gmail.com"


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
        "--slice-ast",
        metavar="FILE",
        help="Slice a Python file keeping full verbatim body of --target-symbol and 1-line stubs for other functions",
    )
    parser.add_argument(
        "--target-symbol",
        metavar="SYMBOL",
        default="",
        help="Target function, class, or Class.method name for --slice-ast",
    )
    parser.add_argument(
        "--fold-errors",
        metavar="FILE",
        help="Fold cascading repeated error tracebacks and FAILED summary lines in a log file",
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

    # Subcommand: iktisad run ...
    run_parser = subparsers.add_parser(
        "run",
        help="Execute a command and compress its terminal stdout/stderr via iktisad context firewall",
    )
    run_parser.add_argument(
        "cmd",
        nargs=argparse.REMAINDER,
        help="Command and arguments to execute (e.g. pytest tests/ -q)",
    )

    # Subcommand: iktisad compress ...
    compress_parser = subparsers.add_parser(
        "compress",
        help="Compress terminal logs or pytest output from file or stdin pipe",
    )
    compress_parser.add_argument(
        "file",
        nargs="?",
        default="-",
        help="Log file to compress (defaults to '-' for stdin pipe)",
    )

    # Subcommand: iktisad github-app ...
    github_app_parser = subparsers.add_parser(
        "github-app",
        help="GitHub App Marketplace CI Guard manifest and webhook server",
    )
    github_app_parser.add_argument(
        "--manifest",
        action="store_true",
        help="Print the GitHub App manifest JSON",
    )
    github_app_parser.add_argument(
        "--serve",
        action="store_true",
        help="Launch the GitHub App webhook HTTP server",
    )
    github_app_parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host interface for GitHub App webhook server (default: 127.0.0.1)",
    )
    github_app_parser.add_argument(
        "--port",
        type=int,
        default=8080,
        help="Port for GitHub App webhook server (default: 8080)",
    )
    github_app_parser.add_argument(
        "--webhook-secret",
        default=None,
        help="GitHub App webhook secret (defaults to IKTISAD_GITHUB_WEBHOOK_SECRET env var)",
    )
    github_app_parser.add_argument(
        "--no-block",
        action="store_true",
        help="Run webhook server without blocking main thread",
    )

    # Subcommand: iktisad roi ...
    roi_parser = subparsers.add_parser(
        "roi",
        help="Inspect cumulative token/USD savings and generate expenseable CFO/CTO B2B ROI markdown receipt",
    )
    roi_parser.add_argument(
        "--report",
        action="store_true",
        help="Generate 1-page CFO/CTO expenseable markdown ROI audit receipt",
    )
    roi_parser.add_argument(
        "--ledger-path",
        default=None,
        help="Path to cumulative ROI JSON ledger (default: .cache/iktisad_roi_ledger.json)",
    )

    # Subcommand: iktisad audit-repo ...
    audit_repo_parser = subparsers.add_parser(
        "audit-repo",
        help="Audit a local Python repository offline for AST & CI log token cost avoidance",
    )
    audit_repo_parser.add_argument(
        "path",
        help="Path to local repository directory to scan offline",
    )
    audit_repo_parser.add_argument(
        "--monthly-runs",
        type=int,
        default=1500,
        help="Estimated monthly CI/agent runs (default: 1500)",
    )
    audit_repo_parser.add_argument(
        "--cost-per-million",
        type=float,
        default=3.0,
        help="LLM token cost in USD per 1M tokens (default: 3.0)",
    )
    audit_repo_parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Emit cost-avoidance telemetry as machine-readable JSON",
    )

    return parser


def _record_roi_milestone_safely(raw_chars: int, compressed_chars: int) -> None:
    """Record cumulative CLI compression ROI and print milestone banner only to TTY stderr."""
    try:
        milestone_res = record_iktisad_roi_and_check_milestone(
            raw_chars=raw_chars,
            compressed_chars=compressed_chars,
        )
        if milestone_res.get("milestone_triggered") and sys.stderr.isatty():
            banner = milestone_res.get("stderr_milestone_banner", "")
            if banner:
                print(banner, file=sys.stderr)
    except Exception:
        pass


def main(args: list[str] | None = None) -> int:
    """Run iktisad CLI."""
    parser = build_parser()
    parsed_args = parser.parse_args(args)

    if parsed_args.pro:
        presets = get_pro_presets()
        offerings = _load_verified_offerings_status()
        pro_live = _is_offering_live_and_verified(offerings, "iktisad-pro")
        pro_entry = offerings.get("iktisad-pro", {})
        pro_status = str(pro_entry.get("status") or "paused_pending_benefits")
        checkout_url = str(pro_entry.get("checkout_url") or POLAR_PRO_CHECKOUT_URL)

        print("======================================================================")
        print("⚡ Kenz Labs — iktisad Polar Pro Tier ($10/mo)")
        print("======================================================================")
        print("Plan: Polar Pro Tier ($10/mo)")
        if pro_live:
            print("Status: Active & Available Worldwide")
            print(f"Checkout URL: {checkout_url}")
        else:
            print(
                f"Status: Paused ({pro_status}) — "
                "Polar Pro self-serve temporarily paused pending license key benefit setup"
            )
            print(f"Checkout URL: Paused (early access & commercial inquiries: {POLAR_PRO_SUPPORT_EMAIL})")
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

    if parsed_args.subcommand == "run":
        cmd_args = parsed_args.cmd
        if cmd_args and cmd_args[0] == "--":
            cmd_args = cmd_args[1:]
        if not cmd_args:
            print("Error: No command specified to run.", file=sys.stderr)
            return 1
        import subprocess
        proc = subprocess.run(cmd_args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        raw_output = proc.stdout or ""
        obs = compress_cli_observation(raw_output)
        _record_roi_milestone_safely(obs.raw_chars, obs.compressed_chars)
        print(f"[iktisad:run] {obs.raw_chars:,} chars -> {obs.compressed_chars:,} chars ({obs.savings_pct:.1f}% context savings | exit: {proc.returncode})")
        print(obs.pruned_text)
        return proc.returncode

    if parsed_args.subcommand == "compress":
        if parsed_args.file == "-" or not parsed_args.file:
            raw = sys.stdin.read()
        else:
            path = Path(parsed_args.file)
            if not path.is_file():
                print(f"Error: file not found: {parsed_args.file}", file=sys.stderr)
                return 1
            raw = path.read_text(encoding="utf-8", errors="replace")
        obs = compress_cli_observation(raw)
        print(obs.pruned_text)
        return 0

    if parsed_args.subcommand == "github-app":
        from iktisad.github_app import build_github_app_manifest, serve_github_app

        if parsed_args.manifest:
            print(json.dumps(build_github_app_manifest(), indent=2))
            return 0
        if parsed_args.serve:
            serve_github_app(
                host=parsed_args.host,
                port=parsed_args.port,
                webhook_secret=parsed_args.webhook_secret,
                block=not parsed_args.no_block,
            )
            return 0
        parser.parse_args(["github-app", "--help"])
        return 0

    if parsed_args.subcommand == "roi":
        report_md = generate_cfo_roi_audit_markdown(ledger_path=parsed_args.ledger_path)
        print(report_md)
        return 0

    if parsed_args.subcommand == "audit-repo":
        target = Path(parsed_args.path)
        if not target.exists() or not target.is_dir():
            print(f"Error: repository directory not found: {parsed_args.path}", file=sys.stderr)
            return 1
        report = estimate_repo_enterprise_cost_avoidance(
            repo_path=target,
            monthly_ci_runs=parsed_args.monthly_runs,
            cost_per_million_tokens_usd=parsed_args.cost_per_million,
        )
        if parsed_args.as_json:
            print(json.dumps(report, indent=2))
        else:
            print("======================================================================")
            print("Kenz Labs / iktisad — Enterprise Token & CI Cost-Avoidance Audit")
            print("======================================================================")
            print(f"Repository:           {report['repo_path']}")
            print(f"Python Files Scanned: {report['files_scanned']:,}")
            print(
                f"AST Code Size:        {report['raw_code_bytes']:,} bytes -> "
                f"{report['compressed_code_bytes']:,} bytes ({report['ast_compression_pct']:.2f}% savings)"
            )
            print(
                f"CI Log Compression:   {report['log_compression_pct']:.2f}% savings "
                f"({report['avg_log_chars_per_run']:,} chars/run)"
            )
            print(f"Monthly CI Runs:      {report['monthly_ci_runs']:,}")
            print(f"Monthly Tokens Saved: {report['monthly_tokens_saved']:,} tokens")
            print(f"Monthly USD Saved:    ${report['monthly_usd_saved']:,.2f} USD")
            print(f"Annual USD Saved:     ${report['annual_usd_saved']:,.2f} USD")
            print(f"Recommended Tier:     {report['recommended_tier']}")
            print("======================================================================")
        return 0

    if parsed_args.slice_ast:
        path = Path(parsed_args.slice_ast)
        if not path.is_file():
            print(f"Error: file not found: {parsed_args.slice_ast}", file=sys.stderr)
            return 1
        source = path.read_text(encoding="utf-8", errors="replace")
        sliced = slice_causal_ast_target(source, parsed_args.target_symbol)
        print(sliced)
        return 0

    if parsed_args.fold_errors:
        if parsed_args.fold_errors == "-":
            raw = sys.stdin.read()
        else:
            path = Path(parsed_args.fold_errors)
            if not path.is_file():
                print(f"Error: file not found: {parsed_args.fold_errors}", file=sys.stderr)
                return 1
            raw = path.read_text(encoding="utf-8", errors="replace")
        print(fold_cascading_error_logs(raw))
        return 0

    if parsed_args.compress_log:
        if parsed_args.compress_log == "-":
            raw = sys.stdin.read()
        else:
            path = Path(parsed_args.compress_log)
            if not path.is_file():
                print(f"Error: file not found: {parsed_args.compress_log}", file=sys.stderr)
                return 1
            raw = path.read_text(encoding="utf-8", errors="replace")
        obs = compress_cli_observation(raw)
        _record_roi_milestone_safely(obs.raw_chars, obs.compressed_chars)
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
