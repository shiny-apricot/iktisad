# İktisad (`iktisad`)

> **Zero-waste, frugal runtime & quota engine for AI agents — Token Governors, Bandwidth Circuit Breakers & Low-Quota Caching.**  
> *Doctrinal & Fiqh Basis: Bey' al-Mülk & 19. Lem'a (İktisad Risalesi) — Build once, distribute infinitely at 0 marginal tokens and 0 wasted bandwidth.*

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Zero Dependencies](https://img.shields.io/badge/dependencies-0-brightgreen.svg)]()
[![PyPI version](https://img.shields.io/pypi/v/iktisad.svg)](https://pypi.org/project/iktisad/)
[![Sponsor on Polar](https://img.shields.io/badge/Sponsor-Polar.sh-purple.svg)](https://polar.sh/autonomy-corp)

---

## 🎯 The Problem: $O(T^2)$ Token Bleed & Unbounded Quota Burn

Autonomous developer agents (Claude Code, SWE-bench runners, OpenHands, custom subagent teams) hemorrhage **80–90% of their operational budget** on:
1. **Noisy Terminal Dumps**: Repetitive pytest tracebacks, ANSI color codes, spinners, and pip logs injected raw into LLM context.
2. **Brute-Force Code Reads**: Ingesting 2,500-line Python files into context windows just to discover a function signature or method boundary.
3. **Model Misrouting**: Using expensive frontier reasoning models (Opus / Gemini Pro / Argon) for trivial regex, linting, or deterministic queries.
4. **Context Cliff Collapse**: Hitting long-context cliffs where quadratic attention costs degrade model intelligence and spike latency.
5. **Bandwidth Profligacy**: Uncached HTTP queries, downloading heavy media/images, and blowing through metered data allowances.

**`iktisad` solves this deterministically in pure Python with ZERO third-party dependencies.**

---

## ⚡ Core Engines

- 🛡️ **Deterministic CLI Output Firewall**: Compresses noisy pytest/compiler outputs by **80–97%**, collapsing clean runs to a single `OK` status line and extracting only critical traceback frames.
- 🗺️ **Zero-Token AST Code Skeletonizer**: Extracts class/function signatures, line numbers, and docstring outlines at **0 LLM tokens**.
- 🚪 **Bezos Type-1 vs. Type-2 Dynamic Router**: Routes reversible mechanical tasks to lightweight/flash models, reserving frontier reasoning models strictly for irreversible decisions under the **Sandwich Protocol** (Flash prep `<600` tokens -> 1-shot Frontier decision -> Flash execution).
- 📉 **Context Compaction Gate**: Audits session transcripts to prevent quadratic KV-cache degradation and detect transcript cliffs before token blowout occurs.
- 🌐 **Bandwidth Circuit Breaker & SQLite Caching (`BandwidthGuard`)**: Enforces hard daily transfer quotas (e.g. 15.0 MB daily limit), blocks bloated media (`.mp4`, `.png`, `.woff2`), and deduplicates HTTP requests with SQLite ETag caching.
- ⚖️ **19. Lem'a Zaruret vs. İsraf Gate**: Prohibits compute or network spend if a deterministic zero-cost alternative exists or if risk-adjusted expected utility is non-positive.

---

## 📦 Installation

```bash
pip install iktisad
```

*Or install directly from source:*
```bash
git clone https://github.com/autonomy-corp/iktisad.git
cd iktisad
pip install .
```

---

## 🚀 CLI Usage

The package installs both `iktisad` and `iktisad-guard` command line binaries.

### 1. Compress Noisy CLI / Test Logs
```bash
iktisad --compress-log pytest_output.log
```
*Output:*
```text
Original: 14,280 chars -> Compressed: 380 chars (97.3% savings)
--------------------------------------------------
OK: 99 passed in 2.53s
```

### 2. Extract AST Code Skeleton (Zero Tokens)
```bash
iktisad --ast-skeleton src/my_service.py
```
*Output:*
```text
# File: src/my_service.py
"""User authentication and billing gateway."""
# (Imports: 6 modules)
L15-L45: class BillingEngine
L18-L24:   def charge_card(...) - Process card payment
L26-L40:   def refund(...) - Issue refund
L48-L60: def verify_webhook(...) - Check HMAC signature
```

### 3. Dynamic Model Routing
```bash
# Reversible mechanical task -> Flash-Lite
iktisad --route-task lint_check --heaviness 2.0 --importance 3.0

# Irreversible Type-1 one-way door -> Argon Sandwich Protocol
iktisad --route-task deploy_production_db --heaviness 8.5 --importance 9.0 --irreversible
```

### 4. Audit Context Transcript
```bash
iktisad --audit-transcript session_transcript.jsonl
```

### 5. Check Bandwidth Usage & Quota Ledger
```bash
iktisad --bandwidth-usage
```

---

## 🐍 Python API

```python
from iktisad import (
    BandwidthGuard,
    extract_python_ast_skeleton,
    compress_cli_observation,
    select_model_dynamically,
)

# 1. Compress terminal tool outputs before injecting into LLM context
obs = compress_cli_observation(raw_terminal_stream)
if obs.has_error:
    feed_to_agent_context(obs.pruned_text)
else:
    feed_to_agent_context(f"Tests passed ({obs.savings_pct:.1f}% context tokens saved)")

# 2. Extract AST skeleton for fast agent codebase reconnaissance
skeleton = extract_python_ast_skeleton("src/engine.py")
print(skeleton.render_compact())

# 3. Dynamic model routing (Bezos Type-1 vs. Type-2 doors)
decision = select_model_dynamically(
    task_kind="fix_security_flaw",
    heaviness=8.0,
    importance=9.0,
    is_irreversible=True,
)
print(f"Tier {decision.tier}: {decision.model_name} via {decision.execution_pattern}")

# 4. Bandwidth Circuit Breaker & Local SQLite Caching
guard = BandwidthGuard(db_path=".cache/network.db", daily_limit_mb=15.0)

# Check media blockade
if guard.is_blocked("https://example.com/huge_banner.png"):
    print("Blocked bloated media asset at 0 wire bytes.")

# Check remaining quota before network query
guard.check_quota(anticipated_bytes=10_240)
summary = guard.get_usage()
print(f"Remaining daily quota: {summary.remaining_megabytes:.2f} MB")
```

---

## 🏛️ Theoretical Foundations

1. **Risale-i Nur (19. Lem'a - İktisad Risalesi)**: Prohibits resource squandering (*israf*) and demands strict necessity (*zaruret*) before compute/bandwidth consumption.
2. **Stafford Beer's Cybernetic Algedonic Filter**: Collapses operational routine noise and escalates only anomalous pain signals (tracebacks, assertion errors) to the executive decision core.
3. **Bezos Two-Way Door Heuristic**: Fast-paths reversible (Type-2) queries to sub-cent lightweight models while reserving frontier reasoning models for irreversible (Type-1) decisions under the **Sandwich Protocol**.

---

## 📜 License & Support

- **License**: MIT License.
- **Commercial Support & Sponsorship**: Support ongoing development or sponsor micro-features via [Polar.sh/autonomy-corp](https://polar.sh/autonomy-corp).
- Built by **Kenz Labs** ("Kırk Düşün, Bir Kes").
