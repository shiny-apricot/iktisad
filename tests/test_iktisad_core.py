"""Unit tests for iktisad core runtime, model router, and bandwidth engine.

Conforms to Corporate Law V:
- Python 3.10+
- Top-level def test_*(): functions without class wrappers
- Pure functional assertions and deterministic local fixtures
"""

from __future__ import annotations

import json
from pathlib import Path
import tempfile

import pytest

from iktisad.cli import build_parser, main as cli_main
from iktisad.core import (
    BandwidthGuard,
    BandwidthProfile,
    BandwidthUsageSummary,
    BlockedResourceError,
    CLIPrunedObservation,
    DynamicModelDecision,
    IktisadResourceCheck,
    PythonASTSkeleton,
    QuotaExceededError,
    audit_transcript_health,
    check_quota_available,
    compress_cli_observation,
    evaluate_iktisad_resource_skepticism,
    extract_python_ast_skeleton,
    get_daily_usage,
    hash_url,
    init_bandwidth_db,
    is_media_blocked,
    lookup_cache_entry,
    record_bandwidth_usage,
    select_model_dynamically,
    store_cache_entry,
)


# ---------------------------------------------------------------------------
# 1. CLI Observation Compression Tests
# ---------------------------------------------------------------------------


def test_compress_cli_observation_empty() -> None:
    """Empty output should produce zero chars and no error."""
    obs = compress_cli_observation("")
    assert obs.raw_chars == 0
    assert obs.compressed_chars == 0
    assert obs.pruned_text == ""
    assert obs.has_error is False


def test_compress_cli_observation_clean_pytest() -> None:
    """Passing pytest log with ANSI escapes should collapse to single OK line."""
    raw = (
        "\x1b[1m============================= test session starts ==============================\x1b[0m\n"
        "rootdir: /home/user/repo\n"
        "plugins: asyncio-0.21.1\n"
        "collected 42 items\n\n"
        "tests/test_one.py \x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m [ 50%]\n"
        "tests/test_two.py \x1b[32m.\x1b[0m\x1b[32m.\x1b[0m\x1b[32m.\x1b[0m [100%]\n\n"
        "\x1b[32m============================== 42 passed in 1.25s ==============================\x1b[0m\n"
    )
    obs = compress_cli_observation(raw)
    assert obs.has_error is False
    assert "OK: 42 passed in 1.25s" in obs.pruned_text
    assert obs.savings_pct > 70.0


def test_compress_cli_observation_failure_traceback() -> None:
    """Failing pytest log should preserve traceback and flag has_error."""
    raw = (
        "collected 5 items\n"
        "tests/test_fail.py F....\n"
        "=== FAILURES ===\n"
        "___ test_logic ___\n"
        "Traceback (most recent call last):\n"
        '  File "/home/user/repo/tests/test_fail.py", line 12, in test_logic\n'
        "    assert result == 42\n"
        "AssertionError: assert 10 == 42\n"
        "=== 1 failed, 4 passed in 0.45s ===\n"
    )
    obs = compress_cli_observation(raw)
    assert obs.has_error is True
    assert "AssertionError: assert 10 == 42" in obs.pruned_text
    assert "1 failed, 4 passed" in obs.pruned_text


def test_compress_cli_observation_truncation() -> None:
    """Super-long noisy logs must be truncated to within max_chars."""
    noisy_line = "DEBUG: processing item 1234567890 with status OK\n" * 200
    obs = compress_cli_observation(noisy_line, max_chars=400)
    assert len(obs.pruned_text) <= 450
    assert "[... truncated by iktisad ...]" in obs.pruned_text


# ---------------------------------------------------------------------------
# 2. Python AST Skeletonizer Tests
# ---------------------------------------------------------------------------


def test_extract_python_ast_skeleton_valid_module(tmp_path: Path) -> None:
    """AST extraction should capture module docstrings, classes, methods, and functions."""
    code = (
        '"""Core arithmetic and telemetry module."""\n\n'
        "import os\n"
        "from typing import Any\n\n"
        "class Calculator:\n"
        '    """Arithmetic processor."""\n'
        "    def add(self, a: int, b: int) -> int:\n"
        '        """Add two integers."""\n'
        "        return a + b\n\n"
        "    async def async_compute(self) -> None:\n"
        '        """Async compute operation."""\n'
        "        pass\n\n"
        "def helper_func() -> str:\n"
        '    """Standalone utility function."""\n'
        '    return "ok"\n'
    )
    test_file = tmp_path / "sample.py"
    test_file.write_text(code, encoding="utf-8")

    skeleton = extract_python_ast_skeleton(test_file)
    assert skeleton.docstring == "Core arithmetic and telemetry module."
    assert skeleton.imports_count == 2
    assert len(skeleton.symbols) == 4

    # Verify symbol details
    symbol_names = [s.name for s in skeleton.symbols]
    assert "Calculator" in symbol_names
    assert "Calculator.add" in symbol_names
    assert "Calculator.async_compute" in symbol_names
    assert "helper_func" in symbol_names

    rendered = skeleton.render_compact()
    assert "# File:" in rendered
    assert "class Calculator" in rendered
    assert "def add(...)" in rendered
    assert "async def async_compute(...)" in rendered
    assert "def helper_func(...)" in rendered


def test_extract_python_ast_skeleton_missing_and_syntax_error(tmp_path: Path) -> None:
    """Missing file or invalid syntax should return empty or fallback skeleton."""
    nonexistent = tmp_path / "does_not_exist.py"
    skel_missing = extract_python_ast_skeleton(nonexistent)
    assert skel_missing.imports_count == 0
    assert len(skel_missing.symbols) == 0

    bad_syntax = tmp_path / "broken.py"
    bad_syntax.write_text("def broken_syntax(:\n", encoding="utf-8")
    skel_broken = extract_python_ast_skeleton(bad_syntax)
    assert skel_broken.docstring == "(syntax parse failure)"


# ---------------------------------------------------------------------------
# 3. Dynamic Model Routing Tests
# ---------------------------------------------------------------------------


def test_select_model_dynamically_zero_token() -> None:
    """Deterministic, lightweight tasks should route to Tier 0 zero_token_python."""
    decision_poll = select_model_dynamically(task_kind="poll", heaviness=2.0)
    assert decision_poll.tier == 0
    assert decision_poll.model_name == "zero_token_python"

    decision_light = select_model_dynamically(task_kind="inspect", heaviness=0.8)
    assert decision_light.tier == 0


def test_select_model_dynamically_flash_lite() -> None:
    """Reversible low-heaviness tasks should route to Tier 1 Flash-Lite."""
    dec = select_model_dynamically(
        task_kind="lint_fix",
        heaviness=2.5,
        importance=3.0,
        is_irreversible=False,
    )
    assert dec.tier == 1
    assert dec.model_name == "flash_lite"
    assert dec.argon_allowed is False


def test_select_model_dynamically_argon_sandwich() -> None:
    """Irreversible high-importance tasks must enforce the Sandwich Protocol."""
    dec = select_model_dynamically(
        task_kind="deploy_security_patch",
        heaviness=8.0,
        importance=9.0,
        is_irreversible=True,
        weekly_argon_pct=85.0,
    )
    assert dec.tier == 4
    assert dec.model_name == "inherit"
    assert dec.argon_allowed is True
    assert dec.execution_pattern == "FLASH_PREP_ARGON_DECISION_FLASH_EXEC"


def test_select_model_dynamically_pro_and_fallback() -> None:
    """Pro tier selection with quota fallback."""
    dec_pro = select_model_dynamically(
        task_kind="complex_architecture_redesign",
        heaviness=9.0,
        importance=8.5,
        is_irreversible=False,
        weekly_flash_pct=80.0,
        five_hour_flash_pct=80.0,
    )
    assert dec_pro.tier == 3
    assert dec_pro.model_name == "pro"

    # When quota is constrained, fallback to Flash
    dec_fallback = select_model_dynamically(
        task_kind="complex_architecture_redesign",
        heaviness=9.0,
        importance=8.5,
        is_irreversible=False,
        weekly_flash_pct=15.0,
        five_hour_flash_pct=10.0,
    )
    assert dec_fallback.tier == 2
    assert dec_fallback.model_name == "flash"


# ---------------------------------------------------------------------------
# 4. Transcript Health & Compaction Tests
# ---------------------------------------------------------------------------


def test_audit_transcript_health_levels(tmp_path: Path) -> None:
    """Audit should categorize healthy, compact recommended, and critical cliff states."""
    transcript_file = tmp_path / "transcript.jsonl"

    # Missing file
    rep_missing = audit_transcript_health(tmp_path / "missing.jsonl")
    assert rep_missing.health_status == "HEALTHY"

    # Small healthy file
    small_lines = [{"step": i, "content": "nominal token trace"} for i in range(10)]
    transcript_file.write_text("\n".join(json.dumps(x) for x in small_lines), encoding="utf-8")
    rep_healthy = audit_transcript_health(transcript_file, soft_cap_bytes=10_000, hard_cliff_bytes=20_000)
    assert rep_healthy.health_status == "HEALTHY"

    # Soft cap reached
    medium_lines = [{"step": i, "content": "x" * 2000} for i in range(10)]
    transcript_file.write_text("\n".join(json.dumps(x) for x in medium_lines), encoding="utf-8")
    rep_soft = audit_transcript_health(transcript_file, soft_cap_bytes=5_000, hard_cliff_bytes=50_000)
    assert rep_soft.health_status == "COMPACT_RECOMMENDED"

    # Hard cliff reached
    rep_hard = audit_transcript_health(transcript_file, soft_cap_bytes=2_000, hard_cliff_bytes=10_000)
    assert rep_hard.health_status == "CRITICAL_LONG_CONTEXT_CLIFF"


# ---------------------------------------------------------------------------
# 5. Zero-Waste Compute Protocol Evaluator Tests
# ---------------------------------------------------------------------------


def test_evaluate_iktisad_resource_skepticism() -> None:
    """Check rejection on deterministic alternatives, unverified sources, and necessity approval."""
    # Prohibited waste: local deterministic alternative exists
    check_alt = evaluate_iktisad_resource_skepticism(
        resource_type="API_TOKENS",
        proposed_units=5000,
        has_deterministic_zero_cost_alternative=True,
        source_verified=True,
        expected_value_usd=100.0,
        probability_of_realization=0.9,
    )
    assert check_alt.approved is False
    assert check_alt.verdict == "REJECTED_ISRAF_DETERMINISTIC_ALT"

    # Rejected unverified source
    check_unverified = evaluate_iktisad_resource_skepticism(
        resource_type="BANDWIDTH_MB",
        proposed_units=5.0,
        has_deterministic_zero_cost_alternative=False,
        source_verified=False,
        expected_value_usd=50.0,
        probability_of_realization=0.8,
    )
    assert check_unverified.approved is False
    assert check_unverified.verdict == "REJECTED_UNVERIFIED_SOURCE"

    # Rejected negative or zero expected utility
    check_zero_ev = evaluate_iktisad_resource_skepticism(
        resource_type="GPU_CYCLES",
        proposed_units=10.0,
        has_deterministic_zero_cost_alternative=False,
        source_verified=True,
        expected_value_usd=0.0,
        probability_of_realization=0.0,
    )
    assert check_zero_ev.approved is False
    assert check_zero_ev.verdict == "REJECTED_NEGATIVE_EXPECTED_UTILITY"

    # Approved necessity
    check_approved = evaluate_iktisad_resource_skepticism(
        resource_type="API_TOKENS",
        proposed_units=1500,
        has_deterministic_zero_cost_alternative=False,
        source_verified=True,
        expected_value_usd=250.0,
        probability_of_realization=0.85,
    )
    assert check_approved.approved is True
    assert check_approved.verdict == "APPROVED_ZARURET"
    assert check_approved.risk_adjusted_ev_usd > 200.0


# ---------------------------------------------------------------------------
# 6. Bandwidth Circuit Breaker & SQLite Caching Tests
# ---------------------------------------------------------------------------


def test_bandwidth_guard_media_blockade() -> None:
    """URL media filter must block heavy images, videos, fonts, and archives."""
    assert is_media_blocked("https://example.com/promo.mp4") is True
    assert is_media_blocked("https://example.com/avatar.png") is True
    assert is_media_blocked("https://example.com/font.woff2") is True
    assert is_media_blocked("https://example.com/archive.tar.gz") is True
    assert is_media_blocked("https://example.com/data.json") is False
    assert is_media_blocked("https://example.com/api/v1/health") is False


def test_bandwidth_guard_sqlite_cache_and_usage(tmp_path: Path) -> None:
    """BandwidthGuard should store, retrieve cached responses, and track quota."""
    db_file = str(tmp_path / "bandwidth.db")
    guard = BandwidthGuard(db_path=db_file, daily_limit_mb=15.0)

    # 1. Lookup missing URL
    url = "https://api.github.com/repos/kenz-labs/iktisad"
    assert guard.lookup_cache(url) is None

    # 2. Store response
    body_data = b'{"status": "ok", "version": "0.1.0"}'
    guard.store_cache(
        url=url,
        status_code=200,
        headers={"content-type": "application/json"},
        body=body_data,
        etag='"etag123"',
        ttl_seconds=3600,
    )

    # 3. Retrieve response from cache
    cached = guard.lookup_cache(url)
    assert cached is not None
    assert cached.status_code == 200
    assert cached.body == body_data
    assert cached.etag == '"etag123"'

    # 4. Record usage
    guard.record_usage(url=url, method="GET", bytes_transferred=len(body_data), is_cache_hit=False)
    guard.record_usage(url=url, method="GET", bytes_transferred=0, is_cache_hit=True)

    summary = guard.get_usage()
    assert summary.network_requests == 1
    assert summary.cached_hits == 1
    assert summary.total_bytes_transferred == len(body_data)
    assert summary.remaining_megabytes > 14.9
    assert summary.quota_exceeded is False


def test_bandwidth_guard_quota_exceeded_error(tmp_path: Path) -> None:
    """Breaching the configured daily limit must raise QuotaExceededError."""
    db_file = str(tmp_path / "bandwidth_quota.db")
    guard = BandwidthGuard(db_path=db_file, daily_limit_mb=1.0)

    # Record 0.9 MB
    guard.record_usage(
        url="https://example.com/file1",
        method="GET",
        bytes_transferred=int(0.9 * 1024 * 1024),
        is_cache_hit=False,
    )

    # Checking 50 KB should succeed (0.9 MB + 0.05 MB < 1.0 MB)
    guard.check_quota(anticipated_bytes=50 * 1024)

    # Checking 200 KB should raise QuotaExceededError (0.9 MB + 0.2 MB > 1.0 MB)
    with pytest.raises(QuotaExceededError) as exc_info:
        guard.check_quota(anticipated_bytes=200 * 1024)
    assert "Quota exceeded" in str(exc_info.value)


# ---------------------------------------------------------------------------
# 7. CLI Entry Point Invocation Tests
# ---------------------------------------------------------------------------


def test_cli_compress_log_runner(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """CLI --compress-log flag execution."""
    log_file = tmp_path / "test_run.log"
    log_file.write_text("tests/test_demo.py ..\n=== 2 passed in 0.12s ===\n", encoding="utf-8")

    ret = cli_main(["--compress-log", str(log_file)])
    assert ret == 0
    captured = capsys.readouterr()
    assert "Original:" in captured.out
    assert "OK: 2 passed in 0.12s" in captured.out


def test_cli_ast_skeleton_runner(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """CLI --ast-skeleton flag execution."""
    py_file = tmp_path / "mod.py"
    py_file.write_text("def ping() -> str:\n    return 'pong'\n", encoding="utf-8")

    ret = cli_main(["--ast-skeleton", str(py_file)])
    assert ret == 0
    captured = capsys.readouterr()
    assert "# File:" in captured.out
    assert "def ping(...)" in captured.out


def test_cli_route_task_runner(capsys: pytest.CaptureFixture[str]) -> None:
    """CLI --route-task flag execution."""
    ret = cli_main(["--route-task", "swe_bug_fix", "--heaviness", "8.0", "--importance", "9.0", "--irreversible"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "Task: swe_bug_fix" in captured.out
    assert "Sandwich Protocol" in captured.out


def test_cli_audit_transcript_runner(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """CLI --audit-transcript flag execution."""
    transcript_file = tmp_path / "transcript.jsonl"
    transcript_file.write_text('{"step": 1, "action": "test"}\n', encoding="utf-8")

    ret = cli_main(["--audit-transcript", str(transcript_file)])
    assert ret == 0
    captured = capsys.readouterr()
    assert "Health Status: HEALTHY" in captured.out


def test_cli_bandwidth_and_media_runners(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """CLI --bandwidth-usage and --check-media-url flags execution."""
    db_file = str(tmp_path / "cli_bw.db")
    ret_bw = cli_main(["--bandwidth-usage", "--db-path", db_file])
    assert ret_bw == 0
    captured_bw = capsys.readouterr()
    assert "Bandwidth Usage Report" in captured_bw.out

    ret_media = cli_main(["--check-media-url", "https://cdn.example.com/asset.png"])
    assert ret_media == 0
    captured_media = capsys.readouterr()
    assert "Media Blocked: True" in captured_media.out


def test_iktisad_cli_run_subcommand(capsys):
    """Verify iktisad run subcommand executes command and compresses output."""
    import sys
    from iktisad.cli import main as cli_main

    ret = cli_main(["run", "--", sys.executable, "-c", "print('hello from iktisad run')"])
    assert ret == 0
    captured = capsys.readouterr().out
    assert "[iktisad:run]" in captured
    assert "hello from iktisad run" in captured


def test_iktisad_cli_compress_log_stdin(capsys, monkeypatch):
    """Verify iktisad --compress-log - reads from stdin."""
    import io
    import sys
    from iktisad.cli import main as cli_main

    fake_stdin = io.StringIO("print('dummy test')\n1 passed in 0.01s\n")
    monkeypatch.setattr(sys, "stdin", fake_stdin)
    ret = cli_main(["--compress-log", "-"])
    assert ret == 0
    captured = capsys.readouterr().out
    assert "Original:" in captured
    assert "Compressed:" in captured


def test_iktisad_aliases():
    """Verify backward-compatibility and ergonomic function aliases in iktisad."""
    import iktisad
    from iktisad.core import compress_terminal_output, extract_ast_skeleton

    assert iktisad.compress_terminal_output is iktisad.compress_cli_observation
    assert iktisad.extract_ast_skeleton is iktisad.extract_python_ast_skeleton
    assert compress_terminal_output is iktisad.compress_cli_observation
    assert extract_ast_skeleton is iktisad.extract_python_ast_skeleton

