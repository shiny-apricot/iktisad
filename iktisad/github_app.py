"""Zero-dependency GitHub App & Marketplace CI Guard for iktisad.

Provides fail-closed HMAC-SHA256 webhook verification, GitHub Marketplace
plan entitlement parsing, AST-skeleton PR preflight auditing, and a stdlib
HTTP webhook server.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import re
import tempfile
import threading
from typing import Any
import urllib.request

from iktisad.core import extract_python_ast_skeleton

_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
_ALLOW_TEST_PREFIXES_RE = re.compile(r"\ballow_test_prefixes\s*=\s*True\b")
_HARDCODED_SECRET_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("GitHub personal access token", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}\b")),
    ("GitHub fine-grained PAT", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b")),
    ("AWS access key ID", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("Live API/Polar secret key", re.compile(r"\b(?:sk_live|rk_live|polar_live)_[A-Za-z0-9_]{16,}\b")),
    (
        "Hardcoded secret literal",
        re.compile(
            r"""(?i)\b(?:api_key|secret_key|webhook_secret|access_token|private_key|client_secret)\b\s*=\s*["'](?!test_|example|changeme|placeholder|your_|<)([^"'\s]{16,})["']"""
        ),
    ),
)

_LICENSE_FILENAMES = frozenset({"LICENSE", "LICENSE.MD", "LICENSE.TXT", "COPYING"})
_ACTIVE_MARKETPLACE_ACTIONS = frozenset({"purchased", "changed", "pending_change"})


@dataclass(frozen=True)
class MarketplacePlanEntitlement:
    """Normalized entitlement parsed from a GitHub Marketplace purchase event."""

    account_login: str
    account_id: int
    plan_id: int
    plan_name: str
    action: str
    active: bool
    monthly_price_usd: float


@dataclass(frozen=True)
class PRGuardReport:
    """Deterministic preflight and AST-skeleton audit report for a pull request."""

    repo_full_name: str
    pr_number: int
    python_files_scanned: int
    raw_chars: int
    skeleton_chars: int
    reduction_pct: float
    preflight_errors: tuple[str, ...]
    conclusion: str
    markdown_summary: str


def verify_github_webhook_signature(
    payload_bytes: bytes,
    signature_header: str,
    webhook_secret: str,
) -> bool:
    """Verify GitHub X-Hub-Signature-256 header in constant time (fail-closed)."""
    if not isinstance(payload_bytes, (bytes, bytearray)):
        return False
    if not webhook_secret or not signature_header:
        return False

    header = signature_header.strip()
    if not header.startswith("sha256="):
        return False

    provided_hex = header[7:].lower()
    if not _HEX64_RE.fullmatch(provided_hex):
        return False

    expected_hex = hmac.new(
        webhook_secret.encode("utf-8"),
        bytes(payload_bytes),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected_hex, provided_hex)


def parse_marketplace_plan_event(payload: dict[str, Any]) -> MarketplacePlanEntitlement:
    """Parse a GitHub `marketplace_purchase` webhook payload into an entitlement."""
    action = str(payload.get("action", "")).strip().lower()
    purchase = payload.get("marketplace_purchase")
    if not isinstance(purchase, dict):
        purchase = {}

    account = purchase.get("account")
    if not isinstance(account, dict):
        account = {}

    plan = purchase.get("plan")
    if not isinstance(plan, dict):
        plan = {}

    billing_cycle = str(purchase.get("billing_cycle", "monthly")).strip().lower()
    monthly_cents = plan.get("monthly_price_in_cents")
    yearly_cents = plan.get("yearly_price_in_cents")

    if isinstance(monthly_cents, (int, float)):
        monthly_price_usd = round(float(monthly_cents) / 100.0, 2)
    elif billing_cycle == "yearly" and isinstance(yearly_cents, (int, float)):
        monthly_price_usd = round(float(yearly_cents) / 1200.0, 2)
    else:
        monthly_price_usd = 0.0

    try:
        account_id = int(account.get("id") or 0)
    except (TypeError, ValueError):
        account_id = 0

    try:
        plan_id = int(plan.get("id") or 0)
    except (TypeError, ValueError):
        plan_id = 0

    return MarketplacePlanEntitlement(
        account_login=str(account.get("login", "")),
        account_id=account_id,
        plan_id=plan_id,
        plan_name=str(plan.get("name", "")),
        action=action,
        active=action in _ACTIVE_MARKETPLACE_ACTIONS,
        monthly_price_usd=monthly_price_usd,
    )


def _scan_source_for_risks(rel_path: str, content: str) -> list[str]:
    """Scan a single file content for insecure test bypasses and hardcoded secrets."""
    findings: list[str] = []
    if rel_path.endswith(".py") and _ALLOW_TEST_PREFIXES_RE.search(content):
        findings.append(f"Insecure test prefix bypass (`allow_test_prefixes=True`) in `{rel_path}`")

    for label, pattern in _HARDCODED_SECRET_PATTERNS:
        if pattern.search(content):
            findings.append(f"Potential hardcoded secret ({label}) in `{rel_path}`")
    return findings


def _format_pr_markdown_summary(
    repo_full_name: str,
    pr_number: int,
    python_files_scanned: int,
    raw_chars: int,
    skeleton_chars: int,
    reduction_pct: float,
    preflight_errors: tuple[str, ...],
    conclusion: str,
) -> str:
    """Format a compact <=15-line Markdown summary without marketing fluff."""
    lines = [
        f"### iktisad CI Guard - `{repo_full_name}` (#{pr_number})",
        f"- **Conclusion:** `{conclusion}`",
        f"- **Python Files Scanned:** {python_files_scanned}",
        f"- **AST Skeleton:** {raw_chars:,} -> {skeleton_chars:,} chars ({reduction_pct:.1f}% reduction)",
        f"- **Preflight Findings:** {len(preflight_errors)}",
    ]
    max_error_lines = 15 - len(lines)
    if preflight_errors and max_error_lines > 0:
        if len(preflight_errors) > max_error_lines and max_error_lines > 1:
            shown = preflight_errors[: max_error_lines - 1]
            remaining = len(preflight_errors) - len(shown)
            for err in shown:
                lines.append(f"  - {err}")
            lines.append(f"  - ... (+{remaining} more findings)")
        else:
            for err in preflight_errors[:max_error_lines]:
                lines.append(f"  - {err}")
    return "\n".join(lines[:15])


def evaluate_pull_request_guard(
    repo_full_name: str,
    pr_number: int,
    python_sources: dict[str, str],
    repo_files: dict[str, str] | None = None,
) -> PRGuardReport:
    """Run AST-skeleton extraction and preflight safety checks on PR files."""
    raw_chars = 0
    skeleton_chars = 0
    errors: list[str] = []

    with tempfile.TemporaryDirectory(prefix="iktisad_pr_guard_") as tmp_dir:
        tmp_root = Path(tmp_dir)
        for idx, (rel_path, source) in enumerate(sorted(python_sources.items())):
            raw_chars += len(source)
            safe_name = f"file_{idx}_{Path(rel_path).name or 'module.py'}"
            if not safe_name.endswith(".py"):
                safe_name = f"{safe_name}.py"
            tmp_file = tmp_root / safe_name
            tmp_file.write_text(source, encoding="utf-8")

            skeleton = extract_python_ast_skeleton(tmp_file)
            rendered = skeleton.render_compact().replace(str(tmp_file), rel_path, 1)
            skeleton_chars += len(rendered)

            if skeleton.docstring == "(syntax parse failure)":
                errors.append(f"Python syntax error in `{rel_path}`")

            errors.extend(_scan_source_for_risks(rel_path, source))

    if repo_files is not None:
        normalized_names = {Path(name).name.upper() for name in repo_files}
        root_names = {name.upper() for name in repo_files if "/" not in name.strip("/")}
        if not ((root_names or normalized_names) & _LICENSE_FILENAMES):
            errors.append("Missing LICENSE file at repository root")

        for rel_path, content in sorted(repo_files.items()):
            if rel_path in python_sources:
                continue
            errors.extend(_scan_source_for_risks(rel_path, content))

    reduction_pct = (
        round(max(0.0, 100.0 * (1.0 - skeleton_chars / raw_chars)), 2)
        if raw_chars > 0
        else 0.0
    )

    preflight_errors = tuple(dict.fromkeys(errors))
    has_security_or_syntax_failure = any(
        "secret" in err.lower()
        or "allow_test_prefixes" in err.lower()
        or "syntax error" in err.lower()
        for err in preflight_errors
    )

    if has_security_or_syntax_failure:
        conclusion = "failure"
    elif preflight_errors:
        conclusion = "action_required"
    else:
        conclusion = "success"

    summary = _format_pr_markdown_summary(
        repo_full_name=repo_full_name,
        pr_number=pr_number,
        python_files_scanned=len(python_sources),
        raw_chars=raw_chars,
        skeleton_chars=skeleton_chars,
        reduction_pct=reduction_pct,
        preflight_errors=preflight_errors,
        conclusion=conclusion,
    )

    return PRGuardReport(
        repo_full_name=repo_full_name,
        pr_number=pr_number,
        python_files_scanned=len(python_sources),
        raw_chars=raw_chars,
        skeleton_chars=skeleton_chars,
        reduction_pct=reduction_pct,
        preflight_errors=preflight_errors,
        conclusion=conclusion,
        markdown_summary=summary,
    )


def handle_github_webhook_payload(
    event_name: str,
    payload_bytes: bytes,
    signature_header: str,
    webhook_secret: str,
    python_sources: dict[str, str] | None = None,
    repo_files: dict[str, str] | None = None,
) -> tuple[int, dict[str, Any]]:
    """Authenticate and deterministically route a GitHub webhook request."""
    if not verify_github_webhook_signature(payload_bytes, signature_header, webhook_secret):
        return (
            401,
            {"status": "unauthorized", "error": "Invalid or missing webhook signature"},
        )

    try:
        decoded = payload_bytes.decode("utf-8")
        payload = json.loads(decoded)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return (
            400,
            {"status": "bad_request", "error": "Invalid JSON webhook payload"},
        )

    if not isinstance(payload, dict):
        return (
            400,
            {"status": "bad_request", "error": "Expected JSON object webhook payload"},
        )

    normalized_event = event_name.strip().lower()

    if normalized_event == "ping":
        return (
            200,
            {
                "status": "ok",
                "event": "ping",
                "zen": str(payload.get("zen", "")),
                "hook_id": payload.get("hook_id"),
            },
        )

    if normalized_event == "marketplace_purchase":
        entitlement = parse_marketplace_plan_event(payload)
        return (
            200,
            {
                "status": "ok",
                "event": "marketplace_purchase",
                "entitlement": asdict(entitlement),
            },
        )

    if normalized_event == "pull_request":
        repo_obj = payload.get("repository")
        repo_full_name = (
            str(repo_obj.get("full_name", ""))
            if isinstance(repo_obj, dict)
            else ""
        )
        pr_obj = payload.get("pull_request")
        raw_pr_number = payload.get("number")
        if raw_pr_number is None and isinstance(pr_obj, dict):
            raw_pr_number = pr_obj.get("number")
        try:
            pr_number = int(raw_pr_number or 0)
        except (TypeError, ValueError):
            pr_number = 0

        report = evaluate_pull_request_guard(
            repo_full_name=repo_full_name,
            pr_number=pr_number,
            python_sources=python_sources or {},
            repo_files=repo_files,
        )
        return (
            200,
            {
                "status": "ok",
                "event": "pull_request",
                "action": str(payload.get("action", "")),
                "report": asdict(report),
            },
        )

    return (
        200,
        {"status": "ignored", "event": normalized_event},
    )


def build_check_run_payload(
    head_sha: str,
    report: PRGuardReport,
    check_name: str = "iktisad-ci-guard",
) -> dict[str, Any]:
    """Build a GitHub Checks API payload from a PRGuardReport."""
    return {
        "name": check_name,
        "head_sha": head_sha,
        "status": "completed",
        "conclusion": report.conclusion,
        "output": {
            "title": f"iktisad CI Guard ({report.conclusion})",
            "summary": report.markdown_summary,
        },
    }


def post_github_check_run(
    repo_full_name: str,
    head_sha: str,
    report: PRGuardReport,
    installation_token: str,
    api_base_url: str = "https://api.github.com",
    timeout_sec: float = 10.0,
) -> tuple[int, dict[str, Any]]:
    """Post a completed GitHub Check Run using stdlib urllib.request."""
    if not installation_token:
        raise ValueError("installation_token must not be empty")

    url = f"{api_base_url.rstrip('/')}/repos/{repo_full_name}/check-runs"
    body = json.dumps(build_check_run_payload(head_sha=head_sha, report=report)).encode("utf-8")
    req = urllib.request.Request(
        url=url,
        data=body,
        method="POST",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {installation_token}",
            "Content-Type": "application/json",
            "User-Agent": "iktisad-ci-guard/0.2.0",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
        parsed = json.loads(raw) if raw.strip() else {}
        return resp.status, parsed


def build_github_app_manifest(
    base_url: str = "https://shiny-apricot.github.io/iktisad/",
    webhook_url: str = "https://shiny-apricot.github.io/iktisad/",
    webhook_active: bool = False,
) -> dict[str, Any]:
    """Return the canonical GitHub App manifest dictionary."""
    return {
        "name": "iktisad-ci-guard",
        "url": base_url,
        "hook_attributes": {
            "url": webhook_url,
            "active": webhook_active,
        },
        "redirect_url": f"{base_url.rstrip('/')}/setup",
        "public": True,
        "default_permissions": {
            "checks": "write",
            "contents": "read",
            "pull_requests": "write",
            "metadata": "read",
        },
        "default_events": [
            "pull_request",
            "marketplace_purchase",
        ],
    }


def create_github_webhook_handler(
    webhook_secret: str,
) -> type[BaseHTTPRequestHandler]:
    """Create a stdlib HTTP handler for GitHub App webhook delivery."""

    class GitHubAppWebhookHandler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:
            return None

        def _write_json(self, status_code: int, payload: dict[str, Any]) -> None:
            encoded = json.dumps(payload).encode("utf-8")
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def do_GET(self) -> None:
            clean_path = self.path.split("?")[0].rstrip("/")
            if clean_path in ("", "/health"):
                self._write_json(200, {"status": "healthy", "service": "iktisad-github-app"})
                return
            self._write_json(404, {"error": "Not found"})

        def do_POST(self) -> None:
            clean_path = self.path.split("?")[0].rstrip("/")
            if clean_path not in ("", "/webhook"):
                self._write_json(404, {"error": "Not found"})
                return

            try:
                content_length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                self._write_json(400, {"status": "bad_request", "error": "Invalid Content-Length"})
                return

            payload_bytes = self.rfile.read(max(0, content_length))
            event_name = self.headers.get("X-GitHub-Event", "")
            signature = self.headers.get("X-Hub-Signature-256", "")

            status_code, response_body = handle_github_webhook_payload(
                event_name=event_name,
                payload_bytes=payload_bytes,
                signature_header=signature,
                webhook_secret=webhook_secret,
            )
            self._write_json(status_code, response_body)

    return GitHubAppWebhookHandler


def create_github_webhook_server(
    host: str = "127.0.0.1",
    port: int = 8080,
    webhook_secret: str = "",
) -> HTTPServer:
    """Instantiate a local stdlib HTTPServer for GitHub App webhooks."""
    handler_cls = create_github_webhook_handler(webhook_secret=webhook_secret)
    return HTTPServer((host, port), handler_cls)


def serve_github_app(
    host: str = "127.0.0.1",
    port: int = 8080,
    webhook_secret: str | None = None,
    block: bool = True,
) -> HTTPServer:
    """Start the GitHub App webhook server, optionally blocking the main thread."""
    secret = webhook_secret if webhook_secret is not None else os.environ.get("IKTISAD_GITHUB_WEBHOOK_SECRET", "")
    server = create_github_webhook_server(host=host, port=port, webhook_secret=secret)
    if block:
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            server.shutdown()
    else:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
    return server
