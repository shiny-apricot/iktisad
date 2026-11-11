# İktisad (`iktisad`)

> **Deterministic token defense engine & native MCP server for AI coding agents.**  
> *Compresses terminal test logs by 80–97% and extracts zero-token AST skeletons to prevent context bloat, rate-limit cascades, and runaway token bills.*

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Zero Dependencies](https://img.shields.io/badge/dependencies-0-brightgreen.svg)]()
[![Model Context Protocol](https://img.shields.io/badge/MCP-Native%20Server-purple.svg)](https://modelcontextprotocol.io/)
[![GitHub Action](https://img.shields.io/badge/GitHub%20Action-iktisad--action-blue.svg)](https://github.com/shiny-apricot/iktisad)
[![PyPI version](https://img.shields.io/pypi/v/iktisad.svg)](https://pypi.org/project/iktisad/)
[![Sponsor on Polar](https://img.shields.io/badge/Sponsor-Polar.sh-purple.svg)](https://buy.polar.sh/polar_cl_yzz3PkDzy0RGI5tD7PCly2oMkieyP5jUPKrF11bpqcA)

---

## 📊 Empirical Benchmarks (Show, Don't Tell)

Autonomous coding agents (Cursor, Claude Code, Windsurf, SWE-bench loops) suffer when long terminal outputs flood attention windows:

| Metric | Raw Terminal Output | With `iktisad compress` | Reduction | Latency |
| :--- | :--- | :--- | :--- | :--- |
| **Pytest Traceback** | 14,280 tokens (57,120 chars) | **1,120 tokens** (4,480 chars) | **-92.1%** | **0.04s** |
| **Clean Test Run (99 tests)** | 1,840 tokens (7,360 chars) | **18 tokens** (72 chars, single OK) | **-99.0%** | **0.01s** |
| **Compiler / Build Warning Flood** | 8,920 tokens (35,680 chars) | **410 tokens** (1,640 chars) | **-95.4%** | **0.02s** |
| **Python Codebase Recon (1,500 LOC)** | 6,200 tokens (raw file read) | **0 tokens** (deterministic AST) | **-100.0%** | **0.01s** |

*All benchmarks executed locally in pure Python with zero third-party dependencies.*

---

## ⚡ Quickstart

### 1. Pipe Terminal Logs Directly into LLMs
```bash
pip install iktisad

# Single-line pipe: compress test failures and pipe directly to an LLM
pytest | iktisad compress | llm

# Or wrap any command directly (preserves exit code, prints compressed summary):
iktisad run -- pytest tests/ -v
```

### 2. GitHub Marketplace Action
Drop `iktisad` directly into any GitHub Actions CI workflow to compress failing logs and protect agent tokens:

```yaml
- name: Run Pytest with iktisad Token Defense
  uses: shiny-apricot/iktisad-action@v1
  with:
    run: pytest tests/ -v
```

### 3. Native Model Context Protocol (MCP) Server
Launch as an stdio MCP server for Cursor, Claude Code, Windsurf, or Claude Desktop:

```bash
iktisad --mcp
# or via dedicated binary
iktisad-mcp
```

**Claude Desktop Configuration (`claude_desktop_config.json`)**:
```json
{
  "mcpServers": {
    "iktisad": {
      "command": "iktisad-mcp"
    }
  }
}
```

Registered with [Smithery.ai](https://smithery.ai) & Glama.ai via `smithery.json`.

---

## 🛠️ Core Engines

- 🛡️ **Deterministic CLI Output Firewall**: Compresses noisy pytest and compiler outputs by **80–97%**, isolating failure tracebacks and collapsing passing runs to a single `OK` status line.
- 🗺️ **Zero-Token AST Code Skeletonizer**: Extracts function/class signatures, line ranges, and docstrings from Python source files at **0 LLM tokens** using Python's native `ast` parser.
- 🚪 **Dynamic Model Routing & Sandwich Protocol**: Evaluates task reversibility (Type-1 irreversible vs. Type-2 reversible). Routes mechanical tasks to sub-cent fast models, reserving frontier reasoning models for high-stakes decisions under a `<600`-token brief.
- ⚡ **Rate Limit Armor & Circuit Breaker**: Tracks local token velocity in SQLite and halts runaway loops before exhausting API budgets or hitting HTTP 429 rate limits.
- 🔌 **Native Model Context Protocol (MCP)**: JSON-RPC stdio server exposing `compress_terminal_log`, `extract_ast_skeleton`, `select_frugal_model`, and `check_circuit_breaker`.

---

## 🔌 Exposed MCP Tools

| Tool | Parameters | Description |
| :--- | :--- | :--- |
| `compress_terminal_log` | `raw_log` (str), `max_chars` (int) | Compresses terminal output by 80–97%, isolating critical traceback frames |
| `extract_ast_skeleton` | `file_path` (str) or `code` (str) | Extracts AST outlines, line ranges, and signatures at 0 tokens |
| `select_frugal_model` | `task_kind`, `heaviness`, `importance` | Recommends optimal model tier via reversible vs. irreversible routing |
| `check_circuit_breaker` | `daily_budget` (int), `db_path` (str) | Checks daily token velocity and halts loops if spending threshold is breached |

---

## 🚀 CLI Usage

```bash
# 1. Pipe terminal logs
pytest | iktisad compress | llm

# 2. Run command under context firewall (preserves exit code)
iktisad run -- pytest tests/ -v

# 3. Compress existing log file
iktisad compress pytest_output.log

# 4. Extract Python AST skeleton at 0 tokens
iktisad --ast-skeleton src/billing_service.py

# 5. Route task dynamically
iktisad --route-task refactor_db --heaviness 8.0 --importance 9.0 --irreversible

# 6. Launch local reverse-proxy gateway
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

# 1. Compress terminal outputs before sending to LLM context
obs = compress_cli_observation(raw_terminal_stream)
if obs.has_error:
    agent.send(obs.pruned_text)
else:
    agent.send(f"Tests passed ({obs.savings_pct:.1f}% tokens saved)")

# 2. Extract AST skeleton for fast agent codebase reconnaissance
skeleton = extract_python_ast_skeleton("src/engine.py")
print(skeleton.render_compact())

# 3. Dynamic model routing
decision = select_model_dynamically(
    task_kind="fix_security_flaw",
    heaviness=8.0,
    importance=9.0,
    is_irreversible=True,
)
print(f"Tier {decision.tier}: {decision.model_name}")

# 4. Local Token Circuit Breaker
stats = get_gateway_daily_stats(db_path=".cache/iktisad_gateway.db", daily_budget=1_000_000)
if stats.circuit_breaker_tripped:
    raise RuntimeError("Daily token budget reached! Halting agent loop.")
```

---

## 💰 Commercial Tiers & B2B Pricing

| Tier | Price | Licensing & Capabilities | Delivery |
| :--- | :--- | :--- | :--- |
| **Free OSS Core** | **$0** (Free) | MIT License. Unlimited local CLI compression, AST skeletonizer, and stdio MCP server. | `pip install iktisad` |
| **Polar Pro** | **[Polar Pro ($10/mo)](https://buy.polar.sh/polar_cl_yzz3PkDzy0RGI5tD7PCly2oMkieyP5jUPKrF11bpqcA)** | Commercial Team Usage License, custom gateway proxy presets, and priority developer support (<24h SLA). | Instant Polar Access |
| **Developer License** | **$49** (One-Time) | Lifetime commercial developer license for proprietary autonomous agents and enterprise deployments. | Polar Checkout |
| **Team CI Action** | **$99/mo** | Team CI Action license with turnkey GitHub Marketplace workflows, shared token armor, and custom circuit breakers. | Polar Subscription |

- **Official Polar Checkout**: [Subscribe on Polar Pro ($10/mo)](https://buy.polar.sh/polar_cl_yzz3PkDzy0RGI5tD7PCly2oMkieyP5jUPKrF11bpqcA)
- **Direct Developer Support**: `kenzailabs@gmail.com`
- **Source Repository**: [https://github.com/shiny-apricot/iktisad](https://github.com/shiny-apricot/iktisad)

---

## 📜 License

MIT License. Open-source software developed by **Kenz Technologies**.
