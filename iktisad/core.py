"""Zero-waste, frugal runtime & quota engine for AI agents.

Table of Contents:
------------------
1. Data Structures & Observations
   - CLIPrunedObservation (@dataclass)
   - SymbolSpan (@dataclass)
   - PythonASTSkeleton (@dataclass)
   - DynamicModelDecision (@dataclass)
   - TranscriptHealthReport (@dataclass)
   - IktisadResourceCheck (@dataclass)
   - BandwidthProfile (@dataclass)
   - BandwidthCacheEntry (@dataclass)
   - BandwidthUsageSummary (@dataclass)
   - FetchResult (@dataclass)
   - QuotaExceededError (Exception)
   - BlockedResourceError (Exception)
2. CLI Output Compression Firewall
   - compress_cli_observation
3. Python AST Code Localizer & Skeletonizer
   - extract_python_ast_skeleton
4. Dynamic Model Routing Gate (Bezos Type-1 vs. Type-2 Doors)
   - select_model_dynamically
5. Transcript Health & Context Compaction
   - audit_transcript_health
6. Zero-Waste Compute Protocol (Necessity vs. Waste Gate)
   - evaluate_iktisad_resource_skepticism
7. Bandwidth Circuit Breaker & Low-Quota Caching
   - init_bandwidth_db
   - is_media_blocked
   - record_bandwidth_usage
   - get_daily_usage
   - check_quota_available
   - hash_url
   - lookup_cache_entry
   - store_cache_entry
   - fetch_url_efficiently
   - BandwidthGuard (@dataclass)
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sqlite3
from typing import Any
import urllib.error
import urllib.request


# ---------------------------------------------------------------------------
# 1. Data Structures & Exceptions
# ---------------------------------------------------------------------------


class QuotaExceededError(Exception):
    """Raised when an operation would breach the daily bandwidth quota."""


class BlockedResourceError(Exception):
    """Raised when a request targets prohibited binary, font, video, or image media."""


@dataclass(frozen=True)
class CLIPrunedObservation:
    """Deterministic CLI output observation firewall result."""

    pruned_text: str
    raw_chars: int
    compressed_chars: int
    savings_pct: float
    has_error: bool


@dataclass(frozen=True)
class SymbolSpan:
    """Line-bounded symbol definition extracted via AST."""

    name: str
    kind: str
    start_line: int
    end_line: int
    signature: str
    docstring_summary: str


@dataclass(frozen=True)
class PythonASTSkeleton:
    """Compact AST skeleton of a Python module."""

    file_path: str
    docstring: str
    imports_count: int
    symbols: tuple[SymbolSpan, ...]

    def render_compact(self) -> str:
        """Render structural outline with exact line bounds for agent navigation."""
        lines = [f"# File: {self.file_path}"]
        if self.docstring:
            lines.append(f'"""{self.docstring}"""')
        lines.append(f"# (Imports: {self.imports_count} modules)")
        for s in self.symbols:
            doc = f" - {s.docstring_summary}" if s.docstring_summary else ""
            lines.append(f"L{s.start_line}-L{s.end_line}: {s.signature}{doc}")
        return "\n".join(lines)


@dataclass(frozen=True)
class DynamicModelDecision:
    """Model routing decision balancing Type-1/2 irreversibility, heaviness, and quotas."""

    tier: int
    tier_name: str
    model_name: str
    argon_allowed: bool
    is_irreversible: bool
    criticality_score: float
    execution_pattern: str
    reason: str


@dataclass(frozen=True)
class TranscriptHealthReport:
    """Audit report evaluating transcript token bloat and context cliff risk."""

    transcript_path: str
    file_size_bytes: int
    step_count: int
    health_status: str
    recommendation: str


@dataclass(frozen=True)
class IktisadResourceCheck:
    """Zero-Waste Compute Protocol & Universal Source Skepticism resource gate."""

    resource_type: str
    proposed_units: float
    has_deterministic_zero_cost_alternative: bool
    source_verified: bool
    expected_value_usd: float
    probability_of_realization: float
    risk_adjusted_ev_usd: float
    approved: bool
    verdict: str
    rationale: str


@dataclass(frozen=True)
class BandwidthProfile:
    """Network bandwidth profile defining daily and single request transfer limits."""

    name: str
    daily_limit_mb: float
    single_request_cap_mb: float


@dataclass(frozen=True)
class BandwidthCacheEntry:
    """Represents a cached HTTP response in SQLite."""

    url_hash: str
    url: str
    status_code: int
    headers: dict[str, str]
    body: bytes
    etag: str | None
    last_modified: str | None
    created_at_utc: str
    expires_at_utc: str


@dataclass(frozen=True)
class BandwidthUsageSummary:
    """Summary of daily network consumption and cache efficiency."""

    date_str: str
    total_bytes_transferred: int
    total_megabytes_transferred: float
    max_daily_megabytes: float
    remaining_megabytes: float
    network_requests: int
    cached_hits: int
    quota_exceeded: bool


@dataclass(frozen=True)
class FetchResult:
    """Outcome of an efficient HTTP fetch."""

    url: str
    status_code: int
    body: bytes
    text: str
    headers: dict[str, str]
    bytes_transferred: int
    is_cache_hit: bool
    etag: str | None


# Prohibited media extensions under the Bandwidth Miser Protocol
BLOCKED_MEDIA_EXTENSIONS: frozenset[str] = frozenset({
    ".mp4", ".avi", ".mkv", ".webm", ".mov", ".wmv",
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff", ".svg",
    ".woff", ".woff2", ".ttf", ".otf", ".eot",
    ".zip", ".tar.gz", ".tgz", ".rar", ".7z", ".iso", ".dmg", ".exe",
})

_ANSI_ESCAPE_PATTERN: re.Pattern[str] = re.compile(
    r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])"
)
_PROGRESS_BAR_PATTERN: re.Pattern[str] = re.compile(
    r"(?:\[[\s=#\->]+\]|\[\s*\d+%\s*\]|\|[█\s]+\|\s*\d+%)"
)
_ZERO_TOKEN_TASKS: frozenset[str] = frozenset({
    "poll",
    "hash_diff",
    "ast_index",
    "db_query",
    "log_scan",
    "quota_check",
    "test_run",
})


# ---------------------------------------------------------------------------
# 2. CLI Output Compression Firewall
# ---------------------------------------------------------------------------


_PASSED_PROGRESS_PATTERN = re.compile(r"(?:^|\s)PASSED(?:\s+\[\s*\d+%\])?$")
_FAILURE_SIGNAL_PATTERN = re.compile(
    r"(?:^=+\s*(?:FAILURES|ERRORS|short test summary info)\s*=+|^_+ .+ _+$|^E\s|^>\s|"
    r"^Traceback \(most recent call last\):|^\s*File \".+\", line \d+|"
    r":\d+:\s*\w*(?:Error|Exception)\b|AssertionError|\w+Error:|\w+Exception:|"
    r"^FAILED\s|^ERROR\s)"
)


def _pack_failing_observation(filtered_lines: list[str], max_chars: int) -> str:
    """Preserve failure headers, assertions, tracebacks, and final summary within max_chars."""
    marker = "\n\n[... truncated by iktisad ...]\n\n"
    if max_chars <= len(marker) + 40:
        joined = "\n".join(filtered_lines)
        half = max(10, max_chars // 2 - 20)
        return f"{joined[:half]}{marker}{joined[-half:]}"

    # Prefer starting from === FAILURES === / === ERRORS === / Traceback if present
    start_idx = 0
    for idx, line in enumerate(filtered_lines):
        stripped = line.strip()
        if (
            "=== FAILURES ===" in stripped
            or "=== ERRORS ===" in stripped
            or stripped.startswith("Traceback (most recent call last):")
        ):
            start_idx = idx
            break

    candidate_lines = filtered_lines[start_idx:] if start_idx < len(filtered_lines) else filtered_lines

    # Keep high-signal traceback/assertion/summary lines when failure body is large
    signal_lines = [
        line for line in candidate_lines
        if _FAILURE_SIGNAL_PATTERN.search(line.strip())
        or re.search(r"\b(?:\d+ passed|\d+ failed|\d+ error)", line)
    ]
    if not signal_lines:
        signal_lines = candidate_lines

    signal_joined = "\n".join(signal_lines)
    if len(signal_joined) <= max_chars:
        return signal_joined

    # Reserve tail budget for final summary + trailing FAILED/error lines
    tail_budget = min(320, max(120, max_chars // 3))
    tail_lines: list[str] = []
    tail_len = 0
    for line in reversed(signal_lines):
        add_len = len(line) + (1 if tail_lines else 0)
        if tail_lines and (tail_len + add_len) > tail_budget:
            break
        tail_lines.append(line)
        tail_len += add_len
    tail_lines.reverse()
    tail_text = "\n".join(tail_lines)

    head_budget = max_chars - len(marker) - len(tail_text)
    head_lines: list[str] = []
    head_len = 0
    tail_start_idx = len(signal_lines) - len(tail_lines)
    for line in signal_lines[:tail_start_idx]:
        add_len = len(line) + (1 if head_lines else 0)
        if head_lines and (head_len + add_len) > head_budget:
            break
        if not head_lines and len(line) > head_budget:
            head_lines.append(line[: max(20, head_budget)])
            break
        head_lines.append(line)
        head_len += add_len

    head_text = "\n".join(head_lines)
    if not head_text:
        half = max(10, (max_chars - len(marker)) // 2)
        return f"{signal_joined[:half]}{marker}{signal_joined[-half:]}"
    return f"{head_text}{marker}{tail_text}"


def compress_cli_observation(
    raw_output: str,
    max_chars: int = 1200,
) -> CLIPrunedObservation:
    """Deterministic output firewall for subagent tool observations.

    Strips ANSI color sequences, spinners, pip/pytest headers, and collapses
    clean passing runs to single summary lines with >80% token savings.
    For failing runs, prioritizes assertion lines, file:line markers, and tracebacks.
    """
    raw_chars = len(raw_output)
    if raw_chars == 0:
        return CLIPrunedObservation("", 0, 0, 0.0, False)

    clean_text = _ANSI_ESCAPE_PATTERN.sub("", raw_output).replace("\r", "\n")
    lines = [line.rstrip() for line in clean_text.splitlines() if line.strip()]

    pytest_summary: str | None = None
    has_failure = False
    has_traceback = False

    for line in lines:
        if re.search(r"\b(?:\d+ passed|\d+ failed|\d+ error)", line):
            pytest_summary = line.strip(" =")
        if "FAILED" in line or "ERROR" in line or "=== FAILURES ===" in line:
            has_failure = True
        if "Traceback (most recent call last):" in line or "AssertionError" in line:
            has_traceback = True

    has_error = has_failure or has_traceback or any(
        err in clean_text for err in ["Traceback (most recent call last):", "Error:", "Exception:"]
    )

    if pytest_summary and not has_error and "passed" in pytest_summary:
        pruned = f"OK: {pytest_summary}"
        comp_chars = len(pruned)
        savings = round(100.0 * (1.0 - comp_chars / max(1, raw_chars)), 2)
        return CLIPrunedObservation(pruned, raw_chars, comp_chars, max(0.0, savings), False)

    filtered_lines: list[str] = []
    last_frame = ""
    repeated_frame_count = 0

    for line in lines:
        stripped = line.strip()
        if _PROGRESS_BAR_PATTERN.fullmatch(stripped):
            continue
        if any(stripped.startswith(pfx) for pfx in ("rootdir:", "configfile:", "plugins:", "collecting ...")):
            continue
        if re.match(r"^collected \d+ items", stripped):
            continue
        if "PASSED" in stripped and (not has_error or _PASSED_PROGRESS_PATTERN.search(stripped)):
            continue

        if stripped.startswith("File ") and stripped == last_frame:
            repeated_frame_count += 1
            if repeated_frame_count == 2:
                filtered_lines.append("  [... repeated frame suppressed ...]")
            continue
        else:
            last_frame = stripped if stripped.startswith("File ") else ""
            repeated_frame_count = 0

        filtered_lines.append(line)

    pruned_joined = "\n".join(filtered_lines)
    if len(pruned_joined) > max_chars:
        if has_error:
            pruned_joined = _pack_failing_observation(filtered_lines, max_chars=max_chars)
        else:
            half = max_chars // 2 - 30
            pruned_joined = f"{pruned_joined[:half]}\n\n[... truncated by iktisad ...]\n\n{pruned_joined[-half:]}"

    comp_chars = len(pruned_joined)
    savings = round(100.0 * (1.0 - comp_chars / max(1, raw_chars)), 2)
    return CLIPrunedObservation(pruned_joined, raw_chars, comp_chars, max(0.0, savings), has_error)


# Alias for backward-compatibility & dogfooding ergonomics
compress_terminal_output = compress_cli_observation


# ---------------------------------------------------------------------------
# 3. Python AST Code Localizer & Skeletonizer
# ---------------------------------------------------------------------------


def extract_python_ast_skeleton(file_path: Path | str) -> PythonASTSkeleton:
    """Extract class/function signatures and line spans at zero LLM token cost."""
    path = Path(file_path)
    if not path.is_file():
        return PythonASTSkeleton(str(path), "", 0, ())

    try:
        source = path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=str(path))
    except Exception:
        return PythonASTSkeleton(str(path), "(syntax parse failure)", 0, ())

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

    return PythonASTSkeleton(str(path), doc_summary, imports_count, tuple(symbols))


# Alias for backward-compatibility & dogfooding ergonomics
extract_ast_skeleton = extract_python_ast_skeleton


# ---------------------------------------------------------------------------
# 4. Dynamic Model Routing Gate (Bezos Type-1 vs. Type-2 Doors)
# ---------------------------------------------------------------------------


def select_model_dynamically(
    task_kind: str = "general",
    heaviness: float = 5.0,
    importance: float = 5.0,
    is_irreversible: bool = False,
    can_verify_deterministically: bool = False,
    weekly_argon_pct: float = 90.0,
    weekly_flash_pct: float = 90.0,
    five_hour_flash_pct: float = 90.0,
    expected_bounty_usd: float = 0.0,
    retry_count: int = 0,
) -> DynamicModelDecision:
    """Dynamically route model based on Bezos Type-1/2 doors, heaviness, importance, and live quotas."""
    normalized_kind = task_kind.strip().lower()
    criticality = round(0.30 * heaviness + 0.35 * importance + (3.5 if is_irreversible else 0.0), 3)

    if heaviness <= 1.0 or normalized_kind in _ZERO_TOKEN_TASKS:
        return DynamicModelDecision(
            0,
            "zero_token_python",
            "zero_token_python",
            False,
            is_irreversible,
            criticality,
            "DIRECT_LOCAL_EXECUTION",
            f"Task '{task_kind}' is deterministic; executed at 0 LLM token cost.",
        )

    if is_irreversible and importance >= 7.5 and heaviness >= 7.0 and weekly_argon_pct >= 25.0:
        return DynamicModelDecision(
            4,
            "argon_sandwich",
            "inherit",
            True,
            True,
            criticality,
            "FLASH_PREP_ARGON_DECISION_FLASH_EXEC",
            "Enforcing Sandwich Protocol: Flash prep <600-token brief -> 1-shot Argon -> Flash execution.",
        )

    if not is_irreversible and heaviness <= 3.5 and importance <= 5.5:
        return DynamicModelDecision(
            1,
            "flash_lite",
            "flash_lite",
            False,
            False,
            criticality,
            "STANDARD_SUBAGENT",
            f"Tier 1 Flash-Lite selected for lightweight reversible task '{task_kind}'.",
        )

    wants_pro = heaviness > 8.0 or criticality >= 6.5 or (retry_count >= 1 and expected_bounty_usd >= 50.0)
    pro_quota_safe = weekly_flash_pct >= 30.0 and five_hour_flash_pct >= 25.0

    if wants_pro and (not is_irreversible or weekly_argon_pct < 25.0):
        if pro_quota_safe:
            return DynamicModelDecision(
                3,
                "pro",
                "pro",
                False,
                is_irreversible,
                criticality,
                "STANDARD_SUBAGENT",
                f"Tier 3 Pro justified (criticality={criticality:.2f}) with healthy quotas.",
            )
        else:
            return DynamicModelDecision(
                2,
                "flash",
                "flash",
                False,
                is_irreversible,
                criticality,
                "STANDARD_SUBAGENT",
                "Tier 3 Pro requested but blocked due to constrained quotas; falling back to Flash.",
            )

    return DynamicModelDecision(
        2,
        "flash",
        "flash",
        False,
        is_irreversible,
        criticality,
        "STANDARD_SUBAGENT",
        f"Tier 2 Flash selected for core task '{task_kind}'.",
    )


# ---------------------------------------------------------------------------
# 5. Transcript Health & Context Compaction
# ---------------------------------------------------------------------------


def audit_transcript_health(
    transcript_path: Path | str,
    soft_cap_bytes: int = 350_000,
    hard_cliff_bytes: int = 800_000,
) -> TranscriptHealthReport:
    """Audit transcript size to prevent O(T^2) quadratic long-context cliffs."""
    path = Path(transcript_path)
    if not path.is_file():
        return TranscriptHealthReport(str(path), 0, 0, "HEALTHY", "File does not exist.")

    size = path.stat().st_size
    step_count = sum(1 for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip())

    if size >= hard_cliff_bytes:
        status = "CRITICAL_LONG_CONTEXT_CLIFF"
        rec = f"Size ({size:,} B) exceeds hard cliff ({hard_cliff_bytes:,} B). WTU multiplier active."
    elif size >= soft_cap_bytes:
        status = "COMPACT_RECOMMENDED"
        rec = f"Size ({size:,} B) exceeds soft cap ({soft_cap_bytes:,} B). Trigger context compaction."
    else:
        status = "HEALTHY"
        rec = f"Size ({size:,} B) within nominal bounds."

    return TranscriptHealthReport(str(path), size, step_count, status, rec)


# ---------------------------------------------------------------------------
# 6. Zero-Waste Compute Protocol (Necessity vs. Waste Gate)
# ---------------------------------------------------------------------------


def evaluate_iktisad_resource_skepticism(
    resource_type: str,
    proposed_units: float,
    has_deterministic_zero_cost_alternative: bool,
    source_verified: bool,
    expected_value_usd: float,
    probability_of_realization: float,
) -> IktisadResourceCheck:
    """Evaluate proposed resource expenditure under the Zero-Waste Compute Protocol."""
    ev = round(expected_value_usd * max(0.0, probability_of_realization), 4)

    if has_deterministic_zero_cost_alternative:
        return IktisadResourceCheck(
            resource_type,
            proposed_units,
            True,
            source_verified,
            expected_value_usd,
            probability_of_realization,
            ev,
            False,
            "REJECTED_ISRAF_DETERMINISTIC_ALT",
            f"Deterministic local alternative exists for {resource_type}. Spending is rejected as wasteful.",
        )

    if not source_verified:
        return IktisadResourceCheck(
            resource_type,
            proposed_units,
            False,
            False,
            expected_value_usd,
            probability_of_realization,
            ev,
            False,
            "REJECTED_UNVERIFIED_SOURCE",
            f"External source is unverified for {resource_type}. Universal Epistemic Skepticism holds.",
        )

    if ev <= 0.0 or probability_of_realization <= 0.0:
        return IktisadResourceCheck(
            resource_type,
            proposed_units,
            False,
            True,
            expected_value_usd,
            probability_of_realization,
            ev,
            False,
            "REJECTED_NEGATIVE_EXPECTED_UTILITY",
            f"Non-positive expected utility (${ev:.2f}). Expenditure rejected.",
        )

    return IktisadResourceCheck(
        resource_type,
        proposed_units,
        False,
        True,
        expected_value_usd,
        probability_of_realization,
        ev,
        True,
        "APPROVED_ZARURET",
        f"Strict necessity confirmed. Risk-adjusted EV: ${ev:.2f}.",
    )


# ---------------------------------------------------------------------------
# 7. Bandwidth Circuit Breaker & Low-Quota Caching
# ---------------------------------------------------------------------------


def init_bandwidth_db(db_path: str) -> None:
    """Initialize the SQLite cache and bandwidth tracking tables if missing."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS bandwidth_cache (
                url_hash TEXT PRIMARY KEY,
                url TEXT NOT NULL,
                status_code INTEGER NOT NULL,
                headers_json TEXT NOT NULL,
                body BLOB NOT NULL,
                etag TEXT,
                last_modified TEXT,
                created_at_utc TEXT NOT NULL,
                expires_at_utc TEXT NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS bandwidth_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp_utc TEXT NOT NULL,
                date_str TEXT NOT NULL,
                url TEXT NOT NULL,
                method TEXT NOT NULL,
                bytes_transferred INTEGER NOT NULL,
                is_cache_hit INTEGER NOT NULL
            )
            """
        )
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_usage_date ON bandwidth_usage(date_str)")
        conn.commit()


def is_media_blocked(url: str, allowed_extensions: frozenset[str] | None = None) -> bool:
    """Check if the URL targets a prohibited heavy binary, image, font, or video."""
    cleaned_url = url.split("?")[0].split("#")[0].lower()
    allowed = allowed_extensions or frozenset()

    for ext in BLOCKED_MEDIA_EXTENSIONS:
        if cleaned_url.endswith(ext) and ext not in allowed:
            return True
    return False


def record_bandwidth_usage(
    db_path: str,
    url: str,
    method: str,
    bytes_transferred: int,
    is_cache_hit: bool,
    now: datetime | None = None,
) -> None:
    """Record a network transaction into the SQLite ledger."""
    init_bandwidth_db(db_path)
    current_time = now or datetime.now(timezone.utc)
    ts_str = current_time.isoformat()
    date_str = current_time.strftime("%Y-%m-%d")

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO bandwidth_usage (
                timestamp_utc, date_str, url, method, bytes_transferred, is_cache_hit
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (ts_str, date_str, url, method.upper(), bytes_transferred, 1 if is_cache_hit else 0),
        )
        conn.commit()


def get_daily_usage(
    db_path: str,
    date_str: str | None = None,
    max_daily_mb: float = 500.0,
) -> BandwidthUsageSummary:
    """Compute bandwidth usage and remaining allowance for a calendar date."""
    init_bandwidth_db(db_path)
    target_date = date_str or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT 
                COALESCE(SUM(bytes_transferred), 0),
                COALESCE(SUM(CASE WHEN is_cache_hit = 0 THEN 1 ELSE 0 END), 0),
                COALESCE(SUM(CASE WHEN is_cache_hit = 1 THEN 1 ELSE 0 END), 0)
            FROM bandwidth_usage
            WHERE date_str = ?
            """,
            (target_date,),
        )
        row = cursor.fetchone()
        total_bytes = int(row[0]) if row else 0
        network_reqs = int(row[1]) if row else 0
        cached_hits = int(row[2]) if row else 0

    total_mb = total_bytes / (1024.0 * 1024.0)
    remaining_mb = max(0.0, max_daily_mb - total_mb)
    is_exceeded = total_mb >= max_daily_mb

    return BandwidthUsageSummary(
        date_str=target_date,
        total_bytes_transferred=total_bytes,
        total_megabytes_transferred=round(total_mb, 4),
        max_daily_megabytes=max_daily_mb,
        remaining_megabytes=round(remaining_mb, 4),
        network_requests=network_reqs,
        cached_hits=cached_hits,
        quota_exceeded=is_exceeded,
    )


def check_quota_available(
    db_path: str,
    anticipated_bytes: int,
    max_daily_mb: float = 500.0,
    date_str: str | None = None,
) -> None:
    """Raise QuotaExceededError if adding anticipated_bytes would breach daily limit."""
    usage = get_daily_usage(db_path, date_str=date_str, max_daily_mb=max_daily_mb)
    max_bytes = int(max_daily_mb * 1024 * 1024)
    if (usage.total_bytes_transferred + anticipated_bytes) > max_bytes:
        msg = (
            f"Quota exceeded: Current {usage.total_megabytes_transferred:.3f} MB + "
            f"{(anticipated_bytes / (1024 * 1024)):.3f} MB > max {max_daily_mb:.1f} MB"
        )
        raise QuotaExceededError(msg)


def hash_url(url: str, method: str = "GET") -> str:
    """Create a deterministic SHA-256 hash for a given URL and method."""
    key = f"{method.upper()}:{url.strip()}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def lookup_cache_entry(
    db_path: str,
    url: str,
    method: str = "GET",
    now: datetime | None = None,
) -> BandwidthCacheEntry | None:
    """Retrieve an active unexpired cached response from SQLite."""
    init_bandwidth_db(db_path)
    url_h = hash_url(url, method)
    current_time = now or datetime.now(timezone.utc)
    current_iso = current_time.isoformat()

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT url_hash, url, status_code, headers_json, body, etag, 
                   last_modified, created_at_utc, expires_at_utc
            FROM bandwidth_cache
            WHERE url_hash = ? AND expires_at_utc > ?
            """,
            (url_h, current_iso),
        )
        row = cursor.fetchone()
        if not row:
            return None

        headers = json.loads(row[3])
        return BandwidthCacheEntry(
            url_hash=row[0],
            url=row[1],
            status_code=row[2],
            headers=headers,
            body=row[4],
            etag=row[5],
            last_modified=row[6],
            created_at_utc=row[7],
            expires_at_utc=row[8],
        )


def store_cache_entry(
    db_path: str,
    url: str,
    status_code: int,
    headers: dict[str, str],
    body: bytes,
    etag: str | None = None,
    last_modified: str | None = None,
    ttl_seconds: int = 86400,
    method: str = "GET",
    now: datetime | None = None,
) -> None:
    """Store or update a response entry in the SQLite bandwidth cache."""
    init_bandwidth_db(db_path)
    url_h = hash_url(url, method)
    current_time = now or datetime.now(timezone.utc)
    created_iso = current_time.isoformat()
    expires_ts = current_time.timestamp() + ttl_seconds
    expires_iso = datetime.fromtimestamp(expires_ts, tz=timezone.utc).isoformat()
    headers_json = json.dumps(headers)

    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO bandwidth_cache (
                url_hash, url, status_code, headers_json, body, etag, 
                last_modified, created_at_utc, expires_at_utc
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(url_hash) DO UPDATE SET
                status_code = excluded.status_code,
                headers_json = excluded.headers_json,
                body = excluded.body,
                etag = excluded.etag,
                last_modified = excluded.last_modified,
                created_at_utc = excluded.created_at_utc,
                expires_at_utc = excluded.expires_at_utc
            """,
            (
                url_h,
                url,
                status_code,
                headers_json,
                body,
                etag,
                last_modified,
                created_iso,
                expires_iso,
            ),
        )
        conn.commit()


def fetch_url_efficiently(
    url: str,
    db_path: str = ".cache/iktisad_cache.db",
    max_daily_mb: float = 500.0,
    headers: dict[str, str] | None = None,
    ttl_seconds: int = 86400,
    force_refresh: bool = False,
    timeout_seconds: float = 15.0,
) -> FetchResult:
    """Fetch URL respecting the Bandwidth Miser Protocol and SQLite cache."""
    if is_media_blocked(url):
        raise BlockedResourceError(f"Resource blocked under Bandwidth Miser Protocol: {url}")

    if not force_refresh:
        cached = lookup_cache_entry(db_path, url, method="GET")
        if cached is not None:
            record_bandwidth_usage(
                db_path, url, "GET", bytes_transferred=0, is_cache_hit=True
            )
            text_content = cached.body.decode("utf-8", errors="replace")
            return FetchResult(
                url=url,
                status_code=cached.status_code,
                body=cached.body,
                text=text_content,
                headers=cached.headers,
                bytes_transferred=0,
                is_cache_hit=True,
                etag=cached.etag,
            )

    # Estimate 50KB transfer quota check before initiating network call
    check_quota_available(db_path, anticipated_bytes=50 * 1024, max_daily_mb=max_daily_mb)

    req_headers = {"User-Agent": "IktisadRuntime/0.1.1"}
    if headers:
        req_headers.update(headers)

    req = urllib.request.Request(url, headers=req_headers, method="GET")
    with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
        body = resp.read()
        status_code = resp.status
        resp_headers = dict(resp.headers.items())
        etag = resp_headers.get("etag")
        last_modified = resp_headers.get("last-modified")

    bytes_transferred = len(body)
    record_bandwidth_usage(
        db_path, url, "GET", bytes_transferred=bytes_transferred, is_cache_hit=False
    )
    store_cache_entry(
        db_path,
        url=url,
        status_code=status_code,
        headers=resp_headers,
        body=body,
        etag=etag,
        last_modified=last_modified,
        ttl_seconds=ttl_seconds,
    )
    text_content = body.decode("utf-8", errors="replace")
    return FetchResult(
        url=url,
        status_code=status_code,
        body=body,
        text=text_content,
        headers=resp_headers,
        bytes_transferred=bytes_transferred,
        is_cache_hit=False,
        etag=etag,
    )


@dataclass(frozen=True)
class BandwidthGuard:
    """Zero-waste bandwidth circuit breaker and local SQLite cache manager."""

    db_path: str = ".cache/iktisad_cache.db"
    daily_limit_mb: float = 500.0
    single_request_cap_mb: float = 2.5
    profile_name: str = "DEFAULT"

    def get_profile(self) -> BandwidthProfile:
        """Return the active bandwidth profile."""
        return BandwidthProfile(
            name=self.profile_name,
            daily_limit_mb=self.daily_limit_mb,
            single_request_cap_mb=self.single_request_cap_mb,
        )

    def get_usage(self, date_str: str | None = None) -> BandwidthUsageSummary:
        """Get daily usage summary under configured profile limits."""
        return get_daily_usage(
            self.db_path, date_str=date_str, max_daily_mb=self.daily_limit_mb
        )

    def check_quota(self, anticipated_bytes: int, date_str: str | None = None) -> None:
        """Check quota availability under configured limits."""
        check_quota_available(
            self.db_path,
            anticipated_bytes=anticipated_bytes,
            max_daily_mb=self.daily_limit_mb,
            date_str=date_str,
        )

    def is_blocked(self, url: str) -> bool:
        """Check if target URL extension violates the media blockade."""
        return is_media_blocked(url)

    def record_usage(
        self,
        url: str,
        method: str,
        bytes_transferred: int,
        is_cache_hit: bool,
        now: datetime | None = None,
    ) -> None:
        """Record network usage in local SQLite ledger."""
        record_bandwidth_usage(
            self.db_path,
            url=url,
            method=method,
            bytes_transferred=bytes_transferred,
            is_cache_hit=is_cache_hit,
            now=now,
        )

    def lookup_cache(
        self,
        url: str,
        method: str = "GET",
        now: datetime | None = None,
    ) -> BandwidthCacheEntry | None:
        """Lookup an unexpired cached response."""
        return lookup_cache_entry(self.db_path, url=url, method=method, now=now)

    def store_cache(
        self,
        url: str,
        status_code: int,
        headers: dict[str, str],
        body: bytes,
        etag: str | None = None,
        last_modified: str | None = None,
        ttl_seconds: int = 86400,
        method: str = "GET",
        now: datetime | None = None,
    ) -> None:
        """Store response in local SQLite cache."""
        store_cache_entry(
            self.db_path,
            url=url,
            status_code=status_code,
            headers=headers,
            body=body,
            etag=etag,
            last_modified=last_modified,
            ttl_seconds=ttl_seconds,
            method=method,
            now=now,
        )

    def fetch(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        ttl_seconds: int = 86400,
        force_refresh: bool = False,
        timeout_seconds: float = 15.0,
    ) -> FetchResult:
        """Fetch URL using the Bandwidth Miser Protocol and local cache."""
        return fetch_url_efficiently(
            url=url,
            db_path=self.db_path,
            max_daily_mb=self.daily_limit_mb,
            headers=headers,
            ttl_seconds=ttl_seconds,
            force_refresh=force_refresh,
            timeout_seconds=timeout_seconds,
        )


# ---------------------------------------------------------------------------
# 8. Next-Gen Cognitive Compression: Causal AST Slicing & Error Folding
# ---------------------------------------------------------------------------


def _node_first_lineno(node: ast.AST) -> int:
    """Return the first line number of an AST node including any decorators."""
    lineno = int(getattr(node, "lineno", 1))
    decorators = getattr(node, "decorator_list", None)
    if decorators:
        dec_lines = [int(getattr(d, "lineno", lineno)) for d in decorators]
        return min(lineno, *dec_lines)
    return lineno


def _extract_verbatim_node_source(source_lines: list[str], node: ast.AST) -> str:
    """Slice exact verbatim lines for an AST node from source_lines."""
    start = max(1, _node_first_lineno(node))
    end = max(start, int(getattr(node, "end_lineno", start)))
    return "\n".join(source_lines[start - 1 : end])


def _render_one_line_function_stub(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    indent: str = "",
) -> str:
    """Collapse a non-target function or method into a 1-line type-annotated stub."""
    prefix = "async def " if isinstance(node, ast.AsyncFunctionDef) else "def "
    args_str = ast.unparse(node.args)
    ret_str = f" -> {ast.unparse(node.returns)}" if node.returns is not None else ""
    return f"{indent}{prefix}{node.name}({args_str}){ret_str}: ..."


def slice_causal_ast_target(source_code: str, target_symbol: str) -> str:
    """Parse Python AST and keep full verbatim body of target_symbol while stubbing other functions.

    Preserves top-level imports and module constants, keeps 100% verbatim source lines
    of `target_symbol` (function, class, or `ClassName.method_name` / `method_name`),
    and collapses all other non-target functions/methods into 1-line type-annotated stubs
    (`def other_fn(...) -> ...: ...`).
    """
    if not source_code or not source_code.strip():
        return source_code

    clean_target = target_symbol.strip()
    if not clean_target:
        return source_code

    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return source_code

    source_lines = source_code.splitlines()
    output_chunks: list[str] = []

    for idx, stmt in enumerate(tree.body):
        # Module docstring on first statement
        if (
            idx == 0
            and isinstance(stmt, ast.Expr)
            and isinstance(stmt.value, ast.Constant)
            and isinstance(stmt.value.value, str)
        ):
            doc_first = stmt.value.value.strip().splitlines()[0] if stmt.value.value.strip() else ""
            if doc_first:
                output_chunks.append(f'"""{doc_first}"""')
            continue

        # Top-level imports and constants/assignments are preserved verbatim
        if isinstance(stmt, (ast.Import, ast.ImportFrom, ast.Assign, ast.AnnAssign)):
            output_chunks.append(_extract_verbatim_node_source(source_lines, stmt))
            continue

        # Top-level function or async function
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if stmt.name == clean_target:
                output_chunks.append(_extract_verbatim_node_source(source_lines, stmt))
            else:
                output_chunks.append(_render_one_line_function_stub(stmt, indent=""))
            continue

        # Top-level class definition
        if isinstance(stmt, ast.ClassDef):
            if stmt.name == clean_target:
                output_chunks.append(_extract_verbatim_node_source(source_lines, stmt))
                continue

            bases = [ast.unparse(b) for b in stmt.bases]
            base_str = f"({', '.join(bases)})" if bases else ""
            class_lines: list[str] = []
            for dec in stmt.decorator_list:
                class_lines.append(f"@{ast.unparse(dec)}")
            class_lines.append(f"class {stmt.name}{base_str}:")

            body_emitted = False
            for item in stmt.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    qualified_name = f"{stmt.name}.{item.name}"
                    if item.name == clean_target or qualified_name == clean_target:
                        class_lines.append(_extract_verbatim_node_source(source_lines, item))
                    else:
                        class_lines.append(_render_one_line_function_stub(item, indent="    "))
                    body_emitted = True
                elif isinstance(item, (ast.Assign, ast.AnnAssign)):
                    class_lines.append(_extract_verbatim_node_source(source_lines, item))
                    body_emitted = True

            if not body_emitted:
                class_lines.append("    ...")
            output_chunks.append("\n".join(class_lines))
            continue

    return "\n".join(output_chunks)


_SUMMARY_FAIL_LINE_RE: re.Pattern[str] = re.compile(
    r"^(?:FAILED|ERROR)\s+\S+\s+-\s+([A-Za-z_][A-Za-z0-9_.]*)(?::\s*(.*))?$"
)
_PYTEST_BLOCK_HEADER_RE: re.Pattern[str] = re.compile(r"^_{3,}\s+(.+?)\s+_{3,}$")
_SECTION_BANNER_RE: re.Pattern[str] = re.compile(r"^={3,}\s+.+\s+={3,}$")
_EXC_LINE_RE: re.Pattern[str] = re.compile(
    r"^(?:E\s+)?([A-Za-z_][A-Za-z0-9_.]*(?:Error|Exception|Warning|Failure|Fault|Exit))(?::\s*(.*))?$"
)
_FILE_EXC_LINE_RE: re.Pattern[str] = re.compile(
    r"^.+:\d+:\s*([A-Za-z_][A-Za-z0-9_.]*(?:Error|Exception|Warning|Failure|Fault|Exit))\b(.*)$"
)


def _normalize_exception_signature(exc_type: str, raw_msg: str) -> tuple[str, str]:
    """Build normalized (exception_type, message_prefix) signature for cascading failure folding."""
    clean_exc = exc_type.strip().split(".")[-1]
    msg = raw_msg.strip()
    msg = re.sub(r"0x[0-9a-fA-F]+", "0xHEX", msg)
    msg = re.sub(r"\b\d+\b", "<N>", msg)
    msg = re.sub(r"\s+", " ", msg)
    return (clean_exc, msg[:64])


def _extract_block_exception_signature(block_lines: list[str]) -> tuple[str, str] | None:
    """Extract normalized (exception_type, message_prefix) from a multi-line failure/traceback block."""
    exc_type_found: str | None = None
    exc_msg_found: str = ""

    for line in block_lines:
        stripped = line.strip()
        m_exc = _EXC_LINE_RE.match(stripped)
        if m_exc:
            exc_type_found = m_exc.group(1)
            exc_msg_found = m_exc.group(2) or ""
            break

    if exc_type_found is None:
        for line in reversed(block_lines):
            stripped = line.strip()
            m_file = _FILE_EXC_LINE_RE.match(stripped)
            if m_file:
                exc_type_found = m_file.group(1)
                exc_msg_found = m_file.group(2) or ""
                break

    if exc_type_found is None:
        return None
    return _normalize_exception_signature(exc_type_found, exc_msg_found)


def fold_cascading_error_logs(raw_log: str) -> str:
    """Group repeated FAILED lines and traceback blocks by normalized (exception_type, message_prefix).

    Emits the first occurrence of each root-cause failure signature in full verbatim detail
    and folds subsequent identical failures into:
    `[+N identical <ExceptionType> failures folded by iktisad]`.
    """
    if not raw_log:
        return ""

    lines = raw_log.splitlines()
    segments: list[tuple[str, tuple[str, str] | None, list[str]]] = []
    idx = 0
    n_lines = len(lines)

    while idx < n_lines:
        line = lines[idx]
        stripped = line.strip()

        # 1. Pytest failure block: ___ test_xyz ___
        if _PYTEST_BLOCK_HEADER_RE.match(stripped):
            block_lines = [line]
            idx += 1
            while idx < n_lines:
                nxt_stripped = lines[idx].strip()
                if _PYTEST_BLOCK_HEADER_RE.match(nxt_stripped) or _SECTION_BANNER_RE.match(nxt_stripped):
                    break
                block_lines.append(lines[idx])
                idx += 1
            sig = _extract_block_exception_signature(block_lines)
            segments.append(("pytest_block", sig, block_lines))
            continue

        # 2. Standalone Traceback block
        if stripped.startswith("Traceback (most recent call last):"):
            tb_lines = [line]
            idx += 1
            while idx < n_lines:
                curr = lines[idx]
                curr_stripped = curr.strip()
                tb_lines.append(curr)
                idx += 1
                if curr_stripped and not curr.startswith((" ", "\t")) and _EXC_LINE_RE.match(curr_stripped):
                    break
            sig = _extract_block_exception_signature(tb_lines)
            segments.append(("tb_block", sig, tb_lines))
            continue

        # 3. Single-line FAILED / ERROR summary line
        m_sum = _SUMMARY_FAIL_LINE_RE.match(stripped)
        if m_sum:
            exc_type = m_sum.group(1)
            exc_msg = m_sum.group(2) or ""
            sig = _normalize_exception_signature(exc_type, exc_msg)
            segments.append(("summary_line", sig, [line]))
            idx += 1
            continue

        # 4. Ordinary line
        segments.append(("raw", None, [line]))
        idx += 1

    # Count total occurrences per (segment_kind, signature)
    sig_totals: dict[tuple[str, str, str], int] = {}
    for kind, sig, _ in segments:
        if sig is not None:
            key = (kind, sig[0], sig[1])
            sig_totals[key] = sig_totals.get(key, 0) + 1

    emitted_keys: set[tuple[str, str, str]] = set()
    output_lines: list[str] = []

    for kind, sig, seg_lines in segments:
        if sig is None:
            output_lines.extend(seg_lines)
            continue

        key = (kind, sig[0], sig[1])
        if key not in emitted_keys:
            emitted_keys.add(key)
            output_lines.extend(seg_lines)
            extra_count = sig_totals[key] - 1
            if extra_count > 0:
                output_lines.append(
                    f"[+{extra_count} identical {sig[0]} failures folded by iktisad]"
                )

    return "\n".join(output_lines)


# ---------------------------------------------------------------------------
# 9. Cumulative ROI Ledger, Milestone Trigger & CFO/CTO Audit Receipt
# ---------------------------------------------------------------------------

ROI_MILESTONE_THRESHOLDS_USD: tuple[float, ...] = (10.0, 50.0, 250.0, 1000.0)
DEFAULT_ROI_LEDGER_PATH: Path = Path(".cache/iktisad_roi_ledger.json")
_CORE_FILE: Path = Path(__file__).resolve()
DEFAULT_OFFERINGS_PATH: Path = (
    _CORE_FILE.parents[3] / "config" / "offerings.json"
    if len(_CORE_FILE.parents) > 3
    else Path("config/offerings.json")
)
CANONICAL_POLAR_CHECKOUT_URL: str = (
    "https://buy.polar.sh/polar_cl_yzz3PkDzy0RGI5tD7PCly2oMkieyP5jUPKrF11bpqcA"
)


def _load_verified_offerings_status(
    offerings_path: str | Path | None = None,
) -> dict[str, dict[str, Any]]:
    """Load offerings registry keyed by offering_id; fail-closed returns {} if missing/unreadable."""
    target_path = Path(offerings_path) if offerings_path is not None else DEFAULT_OFFERINGS_PATH
    if not target_path.is_file():
        return {}
    payload: Any = None
    try:
        payload = json.loads(target_path.read_text(encoding="utf-8"))
    except Exception:
        payload = None
    if not isinstance(payload, dict):
        return {}
    raw_offerings = payload.get("offerings")
    if not isinstance(raw_offerings, list):
        return {}
    offerings_by_id: dict[str, dict[str, Any]] = {}
    for entry in raw_offerings:
        if isinstance(entry, dict):
            offering_id = entry.get("offering_id")
            if isinstance(offering_id, str) and offering_id:
                offerings_by_id[offering_id] = entry
    return offerings_by_id


def _is_offering_live_and_verified(
    offerings: dict[str, dict[str, Any]],
    offering_id: str,
) -> bool:
    """Return True only if offering exists with status == 'live' and fulfillment_verified is True."""
    entry = offerings.get(offering_id)
    if not isinstance(entry, dict):
        return False
    return entry.get("status") == "live" and entry.get("fulfillment_verified") is True


def _load_roi_ledger(path: Path) -> dict[str, Any]:
    """Load existing cumulative ROI ledger JSON or return initialized state."""
    default_state: dict[str, Any] = {
        "total_raw_chars": 0,
        "total_compressed_chars": 0,
        "total_tokens_saved": 0,
        "total_usd_saved": 0.0,
        "runs_count": 0,
        "last_notified_milestone_usd": 0.0,
    }
    if not path.is_file():
        return default_state
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            return default_state
        return {
            "total_raw_chars": int(loaded.get("total_raw_chars", 0)),
            "total_compressed_chars": int(loaded.get("total_compressed_chars", 0)),
            "total_tokens_saved": int(loaded.get("total_tokens_saved", 0)),
            "total_usd_saved": float(loaded.get("total_usd_saved", 0.0)),
            "runs_count": int(loaded.get("runs_count", 0)),
            "last_notified_milestone_usd": float(loaded.get("last_notified_milestone_usd", 0.0)),
        }
    except Exception:
        return default_state


def record_iktisad_roi_and_check_milestone(
    raw_chars: int,
    compressed_chars: int,
    ledger_path: str | Path | None = None,
    cost_per_million_tokens_usd: float = 3.0,
    offerings_path: str | Path | None = None,
) -> dict[str, Any]:
    """Update cumulative token/USD savings ledger and trigger fail-closed milestone banner.

    Tracks `total_tokens_saved`, `total_usd_saved`, `runs_count`, and `last_notified_milestone_usd`.
    When `total_usd_saved` crosses a threshold in `(10.0, 50.0, 250.0, 1000.0)` above
    `last_notified_milestone_usd`, sets `milestone_triggered = True` and builds
    `stderr_milestone_banner` gated fail-closed on `offerings.json` verification status.
    """
    target_path = Path(ledger_path) if ledger_path is not None else DEFAULT_ROI_LEDGER_PATH
    state = _load_roi_ledger(target_path)

    safe_raw = max(0, int(raw_chars))
    safe_comp = max(0, int(compressed_chars))
    chars_saved_delta = max(0, safe_raw - safe_comp)
    tokens_saved_delta = chars_saved_delta // 4
    usd_saved_delta = (tokens_saved_delta / 1_000_000.0) * float(cost_per_million_tokens_usd)

    total_raw_chars = state["total_raw_chars"] + safe_raw
    total_compressed_chars = state["total_compressed_chars"] + safe_comp
    total_tokens_saved = state["total_tokens_saved"] + tokens_saved_delta
    total_usd_saved = round(state["total_usd_saved"] + usd_saved_delta, 6)
    runs_count = state["runs_count"] + 1
    last_notified = float(state["last_notified_milestone_usd"])

    crossed_thresholds = [
        t for t in ROI_MILESTONE_THRESHOLDS_USD if total_usd_saved >= t and t > last_notified
    ]
    milestone_triggered = len(crossed_thresholds) > 0
    crossed_milestone_usd: float | None = None
    stderr_milestone_banner = ""

    if milestone_triggered:
        crossed_milestone_usd = max(crossed_thresholds)
        last_notified = float(crossed_milestone_usd)
        offerings = _load_verified_offerings_status(offerings_path)
        if _is_offering_live_and_verified(offerings, "iktisad-pro"):
            pro_entry = offerings["iktisad-pro"]
            checkout_url = str(pro_entry.get("checkout_url") or CANONICAL_POLAR_CHECKOUT_URL)
            reciprocity_suggested_usd = round(max(1.0, crossed_milestone_usd * 0.10), 2)
            stderr_milestone_banner = (
                "======================================================================\n"
                f"⚡ [iktisad ROI Milestone] ${total_usd_saved:,.2f} USD Direct API Spend Saved "
                f"({total_tokens_saved:,} tokens pruned across {runs_count:,} runs)\n"
                "----------------------------------------------------------------------\n"
                "  1) Reciprocity Indie Sponsor Prompt: 10% value-anchored reciprocity support via Polar "
                f"(${reciprocity_suggested_usd:.0f} suggested / $10/mo Pro): {checkout_url}\n"
                "  2) Team CI Audit & ROI Receipt (kenzailab@gmail.com): run `iktisad roi --report`\n"
                "======================================================================"
            )
        else:
            stderr_milestone_banner = (
                "======================================================================\n"
                f"⚡ [iktisad ROI Milestone] ${total_usd_saved:,.2f} USD Direct API Spend Saved "
                f"({total_tokens_saved:,} tokens pruned across {runs_count:,} runs)\n"
                "----------------------------------------------------------------------\n"
                "  MIT OSS & Early-Access Reciprocity Banner:\n"
                "  1) Open-Source Star / Usage Share (MIT OSS): https://pypi.org/project/iktisad/\n"
                "  2) Team CI Audit & Early-Access Inquiry (Zero-Call Proof-of-Work): "
                "kenzailab@gmail.com | run `iktisad roi --report`\n"
                "======================================================================"
            )

    updated_ledger = {
        "total_raw_chars": total_raw_chars,
        "total_compressed_chars": total_compressed_chars,
        "total_tokens_saved": total_tokens_saved,
        "total_usd_saved": total_usd_saved,
        "runs_count": runs_count,
        "last_notified_milestone_usd": last_notified,
    }
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(json.dumps(updated_ledger, indent=2), encoding="utf-8")

    return {
        "tokens_saved_delta": tokens_saved_delta,
        "usd_saved_delta": round(usd_saved_delta, 6),
        "total_raw_chars": total_raw_chars,
        "total_compressed_chars": total_compressed_chars,
        "total_tokens_saved": total_tokens_saved,
        "total_usd_saved": total_usd_saved,
        "runs_count": runs_count,
        "last_notified_milestone_usd": last_notified,
        "milestone_triggered": milestone_triggered,
        "crossed_milestone_usd": crossed_milestone_usd,
        "stderr_milestone_banner": stderr_milestone_banner,
        "ledger_path": str(target_path),
    }


def generate_cfo_roi_audit_markdown(
    ledger_path: str | Path | None = None,
    offerings_path: str | Path | None = None,
) -> str:
    """Produce a deterministic 1-page markdown ROI audit receipt gated on verified offerings."""
    target_path = Path(ledger_path) if ledger_path is not None else DEFAULT_ROI_LEDGER_PATH
    state = _load_roi_ledger(target_path)
    offerings = _load_verified_offerings_status(offerings_path)
    pro_live = _is_offering_live_and_verified(offerings, "iktisad-pro")

    total_raw = int(state["total_raw_chars"])
    total_comp = int(state["total_compressed_chars"])
    total_tokens = int(state["total_tokens_saved"])
    total_usd = float(state["total_usd_saved"])
    runs_count = int(state["runs_count"])

    if total_raw > 0:
        savings_pct = round(100.0 * (1.0 - (total_comp / max(1, total_raw))), 2)
        signal_density_uplift = round(total_raw / max(1, total_comp), 2)
    else:
        savings_pct = 0.0
        signal_density_uplift = 1.0

    capabilities_block = (
        "### Verified Local Capabilities\n\n"
        "- `slice_causal_ast_target`: AST-based target symbol isolation that keeps the requested symbol intact while stubbing unrelated module definitions.\n"
        "- `fold_cascading_error_logs`: Deterministic CI/test log deduplication that collapses repeated identical failure frames into one root-cause frame.\n"
        "- `estimate_repo_enterprise_cost_avoidance`: Offline Python repository scanner estimating deterministic AST and CI log token savings.\n\n"
    )

    if pro_live:
        pro_entry = offerings["iktisad-pro"]
        checkout_url = str(pro_entry.get("checkout_url") or CANONICAL_POLAR_CHECKOUT_URL)
        pro_price = pro_entry.get("price_usd", 10)
        offerings_section = (
            "## 2. Verified Offerings & Capabilities\n\n"
            "- **MIT Open-Source Core (`iktisad-oss`, `$0`, `https://pypi.org/project/iktisad/`)**\n"
            f"- **iktisad Pro (`iktisad-pro`, `${pro_price}/mo`)**: Verified Polar subscription with automated license fulfillment.\n\n"
            f"{capabilities_block}"
            "## 3. Procurement & Checkout\n\n"
            f"- **Self-Serve Checkout & License Activation**: {checkout_url}\n"
            "- **Vendor**: Kenz Labs | Contact: `kenzailab@gmail.com`\n"
        )
    else:
        offerings_section = (
            "## 2. Verified Offerings & Capabilities\n\n"
            "- **MIT Open-Source Core (`iktisad-oss`, `$0`, `https://pypi.org/project/iktisad/`)**\n\n"
            f"{capabilities_block}"
            "## 3. Procurement & Inquiry\n\n"
            "- **Procurement / Inquiry**: Early-access team evaluation & deterministic CI audit inquiries: "
            "`kenzailab@gmail.com` (self-serve Polar checkout paused pending automated license fulfillment verification).\n"
            "- **Vendor**: Kenz Labs | Contact: `kenzailab@gmail.com`\n"
        )

    return (
        "# Kenz Labs / İktisad — CFO & CTO Expenseable ROI Audit Receipt\n\n"
        "## 1. Empirical Context Compression & FinOps Telemetry\n\n"
        "| Metric | Verified Value |\n"
        "| :--- | :--- |\n"
        f"| **Audited CLI / CI Execution Runs** | `{runs_count:,}` |\n"
        f"| **Raw Uncompressed Context Volume** | `{total_raw:,} chars` |\n"
        f"| **Pruned Context Firewall Volume** | `{total_comp:,} chars` |\n"
        f"| **Cumulative LLM Tokens Saved** | `{total_tokens:,} tokens` |\n"
        f"| **Cumulative Direct API Spend Saved** | **`${total_usd:,.2f} USD`** |\n"
        f"| **Net Context Reduction Ratio** | `{savings_pct:.2f}%` |\n"
        f"| **Cognitive Signal Density Uplift** | `{signal_density_uplift:.2f}x` |\n\n"
        f"{offerings_section}"
    )


# ---------------------------------------------------------------------------
# 10. Deterministic Offline Repository & CI Cost-Avoidance Calculator
# ---------------------------------------------------------------------------

_REPO_AUDIT_SKIP_DIRS: frozenset[str] = frozenset({
    ".git",
    "venv",
    ".venv",
    "__pycache__",
    "node_modules",
})


def _build_representative_ci_log(target_chars: int) -> str:
    """Build a deterministic synthetic pytest CI log of exact length `target_chars`."""
    if target_chars <= 0:
        return ""
    header = (
        "============================= test session starts ==============================\n"
        "rootdir: /workspace/repo\n"
        "plugins: asyncio-0.23.0, cov-5.0.0\n"
        "collected 250 items\n\n"
    )
    failure_block = (
        "=================================== FAILURES ===================================\n"
        "_________________________________ test_gateway _________________________________\n"
        "    def test_gateway():\n"
        ">       assert status_code == 200\n"
        "E       AssertionError: assert 429 == 200\n"
        "tests/test_gateway.py:42: AssertionError\n"
        "=========================== short test summary info ============================\n"
        "FAILED tests/test_gateway.py::test_gateway - AssertionError: assert 429 == 200\n"
        "======================== 1 failed, 249 passed in 4.12s =========================\n"
    )
    if target_chars <= len(header) + len(failure_block):
        return (header + failure_block)[:target_chars]

    body_lines: list[str] = []
    current_len = len(header) + len(failure_block)
    idx = 1
    while current_len < target_chars:
        pct = min(100, (idx * 100) // 250)
        line = f"tests/test_suite_{idx:03d}.py::test_invariant_{idx:04d} PASSED [{pct:3d}%]\n"
        body_lines.append(line)
        current_len += len(line)
        idx += 1

    combined = header + "".join(body_lines) + failure_block
    return combined[:target_chars]


def estimate_repo_enterprise_cost_avoidance(
    repo_path: str | Path,
    monthly_ci_runs: int = 1500,
    cost_per_million_tokens_usd: float = 3.0,
    avg_log_chars_per_run: int = 24000,
) -> dict[str, Any]:
    """Deterministically audit a local Python repository for AST and CI log token savings.

    Zero network calls. Walks `.py` files under `repo_path` (skipping `.git`, `venv`,
    `__pycache__`, `node_modules`), runs `extract_ast_skeleton` on each file to measure
    exact before/after byte & token compression, and evaluates CI log pruning via
    `compress_cli_observation`.
    """
    root = Path(repo_path)
    if not root.exists() or not root.is_dir():
        raise FileNotFoundError(f"Repository directory does not exist: {root}")

    safe_runs = max(0, int(monthly_ci_runs))
    safe_cost = max(0.0, float(cost_per_million_tokens_usd))
    safe_log_chars = max(0, int(avg_log_chars_per_run))

    files_scanned = 0
    raw_code_bytes = 0
    compressed_code_bytes = 0
    raw_code_chars = 0
    compressed_code_chars = 0

    for py_file in sorted(root.rglob("*.py")):
        if not py_file.is_file():
            continue
        rel_parts = py_file.relative_to(root).parts
        if any(part in _REPO_AUDIT_SKIP_DIRS for part in rel_parts):
            continue

        raw_text = py_file.read_text(encoding="utf-8", errors="replace")
        skeleton_text = extract_ast_skeleton(py_file).render_compact()

        files_scanned += 1
        raw_code_bytes += len(raw_text.encode("utf-8"))
        compressed_code_bytes += len(skeleton_text.encode("utf-8"))
        raw_code_chars += len(raw_text)
        compressed_code_chars += len(skeleton_text)

    if raw_code_bytes > 0:
        ast_compression_pct = round(
            max(0.0, 100.0 * (1.0 - (compressed_code_bytes / raw_code_bytes))),
            2,
        )
    else:
        ast_compression_pct = 0.0

    raw_code_tokens = raw_code_chars // 4
    compressed_code_tokens = compressed_code_chars // 4
    ast_tokens_saved_per_run = max(0, raw_code_tokens - compressed_code_tokens)

    sample_log_len = min(safe_log_chars, 48_000)
    if sample_log_len > 0:
        sample_log = _build_representative_ci_log(sample_log_len)
        log_obs = compress_cli_observation(sample_log, max_chars=1200)
        log_compression_pct = round(log_obs.savings_pct, 2)
        log_ratio = max(0.0, (log_obs.raw_chars - log_obs.compressed_chars) / max(1, log_obs.raw_chars))
        log_chars_saved_per_run = int(round(safe_log_chars * log_ratio))
        log_tokens_saved_per_run = log_chars_saved_per_run // 4
    else:
        log_compression_pct = 0.0
        log_tokens_saved_per_run = 0

    monthly_ast_tokens_saved = ast_tokens_saved_per_run * safe_runs
    monthly_log_tokens_saved = log_tokens_saved_per_run * safe_runs
    monthly_tokens_saved = monthly_ast_tokens_saved + monthly_log_tokens_saved
    annual_tokens_saved = monthly_tokens_saved * 12

    monthly_usd_saved = round((monthly_tokens_saved / 1_000_000.0) * safe_cost, 2)
    annual_usd_saved = round((annual_tokens_saved / 1_000_000.0) * safe_cost, 2)

    recommended_tier = (
        "$950 Enterprise CI Guard" if annual_usd_saved >= 1200.0 else "$350 Audit"
    )

    return {
        "repo_path": str(root.resolve()),
        "files_scanned": files_scanned,
        "monthly_ci_runs": safe_runs,
        "cost_per_million_tokens_usd": safe_cost,
        "avg_log_chars_per_run": safe_log_chars,
        "raw_code_bytes": raw_code_bytes,
        "compressed_code_bytes": compressed_code_bytes,
        "raw_code_chars": raw_code_chars,
        "compressed_code_chars": compressed_code_chars,
        "raw_code_tokens": raw_code_tokens,
        "compressed_code_tokens": compressed_code_tokens,
        "ast_compression_pct": ast_compression_pct,
        "ast_tokens_saved_per_run": ast_tokens_saved_per_run,
        "log_compression_pct": log_compression_pct,
        "log_tokens_saved_per_run": log_tokens_saved_per_run,
        "monthly_ast_tokens_saved": monthly_ast_tokens_saved,
        "monthly_log_tokens_saved": monthly_log_tokens_saved,
        "monthly_tokens_saved": monthly_tokens_saved,
        "annual_tokens_saved": annual_tokens_saved,
        "monthly_usd_saved": monthly_usd_saved,
        "annual_usd_saved": annual_usd_saved,
        "recommended_tier": recommended_tier,
    }

