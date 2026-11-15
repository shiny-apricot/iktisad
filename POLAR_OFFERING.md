# Kenz Cloud Gateway — Polar.sh Commercial Offering & Halal Commercial Tier

> **Product**: `iktisad` (v0.2.0) / Kenz Cloud Gateway  
> **Vendor**: Kenz Technologies (Kenz Labs)  
> **Corporate Doctrine**: *"Kırk Düşün, Bir Kes"* (Measure 40 times, cut once) — Autonomous Frugality & Zero-Waste Compute  
> **Governance Milestone**: `TASK-ECON-004` (Halal Commercialization & Polar.sh Listing)

---

## 1. Executive Summary & Value Proposition

Autonomous AI agent workflows (SWE-bench agents, coding assistants, CI/CD autodev daemons) suffer from catastrophic **context bloat**:
- A single test suite execution dumps 500–2,000 lines of terminal ANSI logs into the prompt window (1,500–6,000 tokens per roundtrip).
- Including raw multi-thousand-line source files causes sudden context cliffing, needle-in-a-haystack retrieval degradation, and runaway token bills.

**Kenz Cloud Gateway** acts as an ultra-lightweight, drop-in OpenAI-compatible reverse-proxy (`/v1/chat/completions`) that enforces **Zero-Waste Token Frugality**:
- **>85% Token Defense**: Collapses noisy pytest/terminal logs to single-line verified summaries and converts bulky code files into zero-loss Python AST skeletons.
- **Circuit Breaker Protection**: Automatically halts runaway agent loops before monthly budgets are breached.
- **Dynamic Routing**: Routes low-coupling ($\alpha < 0.60$) exploration and compression tasks to economical Hydrogen execution tiers while reserving Argon for high-coupling architectural gates.

---

## 2. Polar.sh Tier Matrix & Honest Licensing Model

> **100% Free OSS Core (MIT)**: The `iktisad` CLI, Python AST skeletonizer, terminal log firewall, and all 5 native MCP tools (`compress_terminal_log`, `extract_ast_skeleton`, `select_frugal_model`, `check_circuit_breaker`, `run_release_preflight_audit`) are **100% free and open-source under the MIT License** (`$0`, zero artificial paywalls on local CLI flags).

| Tier | Price | Scope & Deliverables | Support & Delivery |
| :--- | :--- | :--- | :--- |
| **Open-Source Core (MIT)** | **$0 / mo** (Free) | Full local CLI (`iktisad`), Python stdlib AST skeletonizer, deterministic pytest/terminal firewall, SQLite circuit breaker, and 5-tool stdio MCP server | `pip install iktisad` / Community GitHub Discussions |
| **Polar Pro (Commercial Convenience & Support)** | **$10 / mo** | Commercial team convenience, curated local gateway & IDE policy presets, and priority issue/email engineering support | Instant Polar access + **<24h SLA** via `kenzailabs@gmail.com` |
| **Hosted Gateway & CI Guard *(Roadmap)*** | **$15–$50 / mo** *(Hosted)* / **5% MoR** *(GitHub App)* | Planned managed hosted gateway policy presets and upcoming GitHub Marketplace CI Guard App (*not yet billed — roadmap only*) | Future opt-in cloud/CI add-on |

---

## 3. "Polar Pro" Tier Details ($10 / month)

### Core Benefits
1. **Commercial Team Convenience & Governance Clearance**:
   - Streamlined procurement receipt and commercial support coverage for engineering teams deploying `iktisad` across proprietary workflows.
2. **Curated Policy Presets & Local Gateway Configurations**:
   - Ready-to-use JSON policy presets and proxy defaults for Cursor, Claude Code, Windsurf, and your local `iktisad --serve-gateway` instance:
     ```python
     from openai import OpenAI

     client = OpenAI(
         base_url="http://127.0.0.1:8000/v1",
         api_key="local-proxy-key",
     )
     ```
3. **Deterministic Context Token Defense**:
   - Intercepts noisy terminal outputs, stripping ANSI escape codes, passing-test boilerplate, and duplicate stack frames while preserving assertion tracebacks.
   - Zero-LLM-token Python AST code skeletonization via Python's standard library `ast` module.
4. **Priority Developer Support (<24h SLA)**:
   - Guaranteed <24-hour response turnaround via `kenzailabs@gmail.com` and prioritized GitHub issue triage.

---

## 4. Islamic Sharia & Halal Governance Compliance (*İslami İktisat ve Fıkıh Güvencesi*)

Every commercial tier of Kenz Labs is strictly audited and ratified by the **İslami İktisat ve Fıkıh Denetim Kurulu (`@dept-islamic-sharia-board`)** in accordance with *Fiqh al-Mu'amalat* (Islamic Commercial Jurisprudence):

### 1. Lawful Contract Structure: *Aqd al-İcâre* (عقد الإجارة - Service Lease)
- The $10/mo subscription constitutes an **İcâre** (leasing of a known service for a defined fee and duration).
- The scope of work (hosted proxy gateway, AST filtering, priority triage) is explicitly defined, eliminating ambiguity.

### 2. Absolute Prohibition of Riba (Zero Interest / Faiz)
- **Zero Late Payment Fees**: If a subscriber fails to renew or a credit card fails, the subscription is simply suspended. **Under no circumstances are compounding interest penalties or late fee surcharges assessed.**
- **No Deferred Debt Financing**: Services are billed strictly upfront on a month-to-month basis without credit or lending mechanisms.

### 3. Absolute Elimination of Gharar (Deception / Excessive Uncertainty)
- The service delivers concrete, measurable, deterministic token savings verifiable via HTTP response headers and local test scripts.
- No hidden conditions, lock-in clauses, or cancellation barriers; subscribers can cancel at any time with a single click in Polar.sh.

### 4. Prohibition of Maysir (Gambling / Paid Lotteries)
- All subscription tiers represent pure software engineering utilities; no speculative reward schemes, lottery draws, or pay-to-win mechanisms exist.

### 5. Halal Treasury Settlement Rails
- Settlement is processed through **Polar.sh** with direct disbursement to our **Kuveyt Türk Katılım Bankası Vadesiz (Non-Interest Demand Deposit) USD/TRY account**.
- No funds pass through interest-yielding DeFi pools, overnight repo instruments, or conventional interest-bearing accounts.

---

## 5. Quickstart & Integration

### A. Python OpenAI SDK
```python
import os
from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:8000/v1",  # Local reverse-proxy gateway
    api_key=os.environ.get("KENZ_GATEWAY_KEY", "local-key"),
)

response = client.chat.completions.create(
    model="auto",  # Automatically routed to the optimal frugal model
    messages=[
        {"role": "system", "content": "You are a senior bug localization assistant."},
        {
            "role": "user",
            "content": (
                "Here is the failing pytest log:\n"
                "============================= test session starts ==============================\n"
                "collected 50 items\n"
                "tests/test_core.py ................................................. F\n"
                "=== FAILURES ===\n"
                "AssertionError: assert 10 == 42\n"
                "========================= 1 failed, 49 passed in 2.1s =========================\n"
            ),
        },
    ],
)

print("Assistant:", response.choices[0].message.content)
```

### B. Self-Hosted Local CLI Mode
```bash
# Launch zero-cost local gateway proxy
iktisad --serve-gateway --port 8000 --daily-token-budget 500000

# Query gateway health and daily statistics
curl http://127.0.0.1:8000/v1/health
```

---

## 6. Polar.sh Sponsor Listing Copy

**Title**: Kenz Cloud Gateway Pro Developer  
**Price**: $10 / month ($10/mo)  
**Summary**: Drop-in OpenAI-compatible reverse proxy cutting >85% of LLM token waste in agent loops with AST code skeletons and CLI output firewalls. 100% Halal *İcâre* contract with zero interest.  
**Canonical Checkout URL**: [Subscribe on Polar Pro ($10/mo)](https://buy.polar.sh/polar_cl_yzz3PkDzy0RGI5tD7PCly2oMkieyP5jUPKrF11bpqcA)
