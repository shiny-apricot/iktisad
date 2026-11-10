# İktisad (`iktisad`)

> **Zero-waste, frugal token defense engine & native MCP server for AI coding agents — Token Bill Defense, Rate Limit Armor & Context Retention.**  
> *Doctrinal & Fiqh Basis: Bey' al-Mülk & 19. Lem'a (İktisad Risalesi) — Build once, run autonomously with zero wasted tokens, zero thinking bloat, and zero runaway loop spend.*

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Zero Dependencies](https://img.shields.io/badge/dependencies-0-brightgreen.svg)]()
[![Model Context Protocol](https://img.shields.io/badge/MCP-Native%20Server-purple.svg)](https://modelcontextprotocol.io/)
[![PyPI version](https://img.shields.io/pypi/v/iktisad.svg)](https://pypi.org/project/iktisad/)
[![Sponsor on Polar](https://img.shields.io/badge/Sponsor-Polar.sh-purple.svg)](https://buy.polar.sh/polar_cl_yzz3PkDzy0RGI5tD7PCly2oMkieyP5jUPKrF11bpqcA)

---

## 🎯 The Problem: $O(T^2)$ Token Bleed, HTTP 429 Cascades & Thinking Token Bloat

Developers running autonomous coding agents (Claude Code, Cursor, Windsurf, SWE-bench loops, OpenHands, custom agentic frameworks) have gigabit fiber. **They don't care about internet megabytes—they get crushed by:**

1. **💸 Runaway Token Bills ($50–$100/day)**: Agents caught in infinite error-fix-retry loops, feeding thousands of tokens of redundant logs back into frontier models on every iteration.
2. **🧠 Thinking Token Bloat in 2026 Reasoning Models**: Frontier models (`Claude Fable`, `Claude Opus 5.5`, `o3`, `DeepSeek-R1`) generate internal reasoning chains (Chain-of-Thought / thinking tokens) before emitting code. When fed 4,000 tokens of raw terminal stdout (ANSI escapes, passing dots, traceback frame noise, environment dumps), their reasoning engines ponder, simulate, and obsess over every irrelevant line. This inflates internal thinking tokens by **3x to 10x**, multiplying API costs and latency.
3. **🚦 HTTP 429 Rate Limit Cascades**: Spiky prompt payloads in CI pipelines and multi-agent loops rapidly exhaust TPM (tokens per minute) and RPM quotas, causing catastrophic cascading pipeline failures.
4. **📉 Context Drift & System Prompt Eviction**: Long, noisy test logs push critical system instructions, architectural boundaries, and safety constraints completely out of the model's active attention window.
5. **📚 Brute-Force File Ingestion**: Ingesting 2,500-line Python files into context just to locate a 10-line function signature or method boundary.

**`iktisad` solves this deterministically in pure Python with ZERO third-party dependencies.**

---

## ⚡ Core Engines

- 🛡️ **Deterministic CLI Output Firewall**: Compresses noisy pytest/compiler outputs by **80–97%**, collapsing clean runs to a single `OK` status line and isolating only critical traceback frames.
- 🗺️ **Zero-Token AST Code Skeletonizer**: Extracts class/function signatures, line numbers, and docstring outlines at **0 LLM tokens** using Python's native `ast` engine.
- 🚪 **The Bezos Sandwich Protocol (2026 Edition)**: Dynamic Type-1 (irreversible) vs. Type-2 (reversible) routing. Routes mechanical, reversible tasks to ultra-frugal models (`Gemini 3.8 Flash`, local models) while reserving expensive 2026 frontier reasoning models (`Claude Fable`, `Claude Opus 5.5`, `o3`, `DeepSeek-R1`) for high-stakes decisions under the Sandwich Protocol (`<600`-token distilled brief prep -> 1-shot Frontier reasoning decision -> frugal execution).
- ⚡ **Rate Limit Armor & Token Circuit Breaker**: Local SQLite token ledger tracking hourly and daily token velocity, killing runaway agent loops before they drain API budgets or trigger HTTP 429 rate limit exceptions.
- 🔌 **Native Model Context Protocol (MCP) Server**: Zero-dependency stdio JSON-RPC server allowing Cursor, Claude Code, Windsurf, and Antigravity agents to invoke `iktisad` tools natively.
- ⚖️ **19. Lem'a Zaruret vs. İsraf Gate**: Strictly enforces token conservation: if an AST parser or deterministic regex can solve it locally at $0.00, calling a cloud LLM is prohibited as waste (*israf*).

---

## 🔌 Native Model Context Protocol (MCP) Server

Connect `iktisad` directly to **Cursor**, **Claude Code**, **Claude Desktop**, or **Windsurf**. Your agents will autonomously compress logs, extract AST outlines, and enforce circuit breakers.

### Claude Desktop / Claude Code Configuration
Add `iktisad` to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "iktisad": {
      "command": "iktisad",
      "args": ["--mcp"]
    }
  }
}
```

*Or use the dedicated binary:*
```json
{
  "mcpServers": {
    "iktisad": {
      "command": "iktisad-mcp"
    }
  }
}
```

### Cursor / Windsurf Configuration
Add under MCP Settings:
- **Type**: `stdio`
- **Command**: `iktisad --mcp`

### Exposed MCP Tools:
| Tool | Description | Token Reduction |
| :--- | :--- | :--- |
| `compress_terminal_log` | Compresses noisy terminal, pytest, or compiler output, isolating failure frames | **80%–97%** |
| `extract_ast_skeleton` | Extracts class/function signatures, line numbers, and docstrings from Python source | **100% (0 tokens)** |
| `select_frugal_model` | Recommends optimal 2026 model tier (Gemini 3.8 Flash vs. Claude Opus 5.5 / o3 Sandwich) | **50%–90%** |
| `check_circuit_breaker` | Inspects daily token spend and trips circuit breaker to halt runaway agent loops | **Prevents Overages** |

---

## 📦 Installation

```bash
pip install iktisad
```

*Or install directly from source:*
```bash
git clone https://github.com/shiny-apricot/iktisad.git
cd iktisad
pip install .
```

---

## 🚀 CLI Usage

The package installs `iktisad`, `iktisad-mcp`, and `iktisad-guard` command line binaries.

### 1. Launch Native MCP Server
```bash
iktisad --mcp
# or
iktisad-mcp
```

### 2. Compress Noisy CLI / Test Logs
```bash
iktisad --compress-log pytest_output.log
```
*Output:*
```text
Original: 14,280 chars -> Compressed: 380 chars (97.3% savings)
--------------------------------------------------
OK: 99 passed in 2.53s
```

### 3. Extract AST Code Skeleton (Zero Tokens)
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

### 4. Dynamic Model Routing (2026 Edition)
```bash
# Reversible mechanical task -> Gemini 3.8 Flash / Flash-Lite
iktisad --route-task lint_check --heaviness 2.0 --importance 3.0

# Irreversible Type-1 one-way door -> 2026 Sandwich Protocol (Claude Opus 5.5 / o3 / DeepSeek-R1)
iktisad --route-task deploy_production_db --heaviness 8.5 --importance 9.0 --irreversible
```

### 5. Launch Frugal Gateway Reverse Proxy (Rate Limit Armor)
```bash
iktisad --serve-gateway --port 8000 --daily-token-budget 1000000
```

---

## 🐍 Python API

```python
from iktisad import (
    compress_cli_observation,
    extract_python_ast_skeleton,
    select_model_dynamically,
    get_gateway_daily_stats,
)

# 1. Compress terminal tool outputs before injecting into LLM context
# Eliminates Thinking Token Bloat in 2026 reasoning models (o3, DeepSeek-R1, Opus 5.5)
obs = compress_cli_observation(raw_terminal_stream)
if obs.has_error:
    feed_to_agent_context(obs.pruned_text)
else:
    feed_to_agent_context(f"Tests passed ({obs.savings_pct:.1f}% context tokens saved)")

# 2. Extract AST skeleton for fast agent codebase reconnaissance at 0 tokens
skeleton = extract_python_ast_skeleton("src/engine.py")
print(skeleton.render_compact())

# 3. Dynamic model routing (Bezos Type-1 vs. Type-2 doors, 2026 Edition)
decision = select_model_dynamically(
    task_kind="fix_security_flaw",
    heaviness=8.0,
    importance=9.0,
    is_irreversible=True,
)
print(f"Tier {decision.tier}: {decision.model_name} via {decision.execution_pattern}")

# 4. Token Circuit Breaker & Rate Limit Armor
stats = get_gateway_daily_stats(db_path=".cache/iktisad_gateway.db", daily_budget=1_000_000)
if stats.circuit_breaker_tripped:
    raise RuntimeError("Daily token budget reached! Halting agent loop to prevent bill overrun.")
```

---

## 🏛️ Theoretical Foundations

1. **Risale-i Nur (19. Lem'a - İktisad Risalesi)**: Prohibits resource squandering (*israf*) and demands strict necessity (*zaruret*) before compute/token consumption. Local deterministic alternatives (AST, regex) must always precede cloud API calls.
2. **Stafford Beer's Cybernetic Algedonic Filter**: Collapses operational routine noise and escalates only anomalous pain signals (tracebacks, assertion errors) to the executive decision core.
3. **Bezos Two-Way Door Heuristic (2026 Edition)**: Fast-paths reversible (Type-2) queries to sub-cent lightweight models (`Gemini 3.8 Flash`) while reserving 2026 frontier reasoning models (`Claude Fable`, `Claude Opus 5.5`, `o3`, `DeepSeek-R1`) for irreversible (Type-1) decisions under the **Sandwich Protocol**.

---

## 📜 License & Support

- **License**: MIT License.
- **Commercial Support & Sponsorship**: Support ongoing development or subscribe to the Pro Tier via [Polar Pro ($19/mo)](https://buy.polar.sh/polar_cl_yzz3PkDzy0RGI5tD7PCly2oMkieyP5jUPKrF11bpqcA).
- Built by **Kenz Labs** ("Kırk Düşün, Bir Kes").
