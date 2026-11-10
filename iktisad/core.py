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
6. 19th Lem'a Zaruret vs. İsraf Resource Evaluator
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
    """19th Lem'a İktisad & Universal Source Skepticism resource gate."""

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


def compress_cli_observation(
    raw_output: str,
    max_chars: int = 1200,
) -> CLIPrunedObservation:
    """Deterministic output firewall for subagent tool observations.

    Strips ANSI color sequences, spinners, pip/pytest headers, and collapses
    clean passing runs to single summary lines with >80% token savings.
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
        if "PASSED" in stripped and not has_error:
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
        half = max_chars // 2 - 30
        pruned_joined = f"{pruned_joined[:half]}\n\n[... truncated by iktisad ...]\n\n{pruned_joined[-half:]}"

    comp_chars = len(pruned_joined)
    savings = round(100.0 * (1.0 - comp_chars / max(1, raw_chars)), 2)
    return CLIPrunedObservation(pruned_joined, raw_chars, comp_chars, max(0.0, savings), has_error)


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
# 6. 19th Lem'a Zaruret vs. İsraf Resource Evaluator
# ---------------------------------------------------------------------------


def evaluate_iktisad_resource_skepticism(
    resource_type: str,
    proposed_units: float,
    has_deterministic_zero_cost_alternative: bool,
    source_verified: bool,
    expected_value_usd: float,
    probability_of_realization: float,
) -> IktisadResourceCheck:
    """Evaluate proposed resource expenditure under the 19th Lem'a İktisad doctrine."""
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
            f"Deterministic local alternative exists for {resource_type}. Spending is prohibited israf.",
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
        f"Strict zaruret confirmed. Risk-adjusted EV: ${ev:.2f}.",
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
    max_daily_mb: float = 15.0,
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
    max_daily_mb: float = 15.0,
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
    max_daily_mb: float = 15.0,
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

    req_headers = {"User-Agent": "IktisadRuntime/0.1.0"}
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
    daily_limit_mb: float = 15.0
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
