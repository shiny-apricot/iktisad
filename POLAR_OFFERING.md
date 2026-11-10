# Kenz Cloud Gateway — Polar.sh Commercial Offering & Halal Commercial Tier

> **Product**: `iktisad` / Kenz Cloud Gateway  
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
- **Dynamic Routing**: Dispatches reversible subagent tasks to economical Flash/Flash-Lite models while reserving flagship models for irreversible Type-1 architectural gates.

---

## 2. Polar.sh Tier Matrix

| Tier | Price | Monthly Token Defense | Gateway & Forwarding | Ast Skeletonizer & CLI Firewall | Support & SLA |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Open-Source Community** | **$0 / mo** (Free) | Self-hosted (unlimited) | Self-hosted local proxy | Full standard library access via `pip install iktisad` | Best-effort GitHub Discussions |
| **Pro Developer (Recommended)** | **$10 / mo** | Unlimited local defense | Local Gateway Proxy Presets (`http://127.0.0.1:8000/v1`) | Commercial Team License + Real-time AST pruning + Quota circuit breaker | Priority email & GitHub triage (<24h SLA) |
| **Enterprise / Custom** | **$99 / mo** | Unlimited local defense | Custom local gateway presets + multi-agent configs | Multi-language AST filters (Python, TypeScript, Go) | Bilateral SLA, custom circuit breakers & direct support |

---

## 3. "Pro Developer" Tier Details ($10 / month)

### Core Benefits
1. **Commercial Team Usage License**:
   - Legal clearance for proprietary enterprise codebases and commercial client deployments.
2. **Local Gateway Proxy Presets & Prompt Filters**:
   - Pre-configured JSON presets and optimized prompt filters for Cursor, Claude Code, and Windsurf running against your local `iktisad --serve-gateway` instance:
     ```python
     from openai import OpenAI

     client = OpenAI(
         base_url="http://127.0.0.1:8000/v1",
         api_key="local-proxy-key",
     )
     ```
3. **Deterministic Context Token Defense**:
   - Intercepts noisy terminal outputs, stripping ANSI escape codes, duplicate tracebacks, and progress bars.
   - Zero-token AST code skeletonization for codebase context reduction.
4. **Direct Priority Developer Support**:
   - Guaranteed <24-hour response turnaround via `kenzailabs@gmail.com` and prioritized GitHub issues.

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
    api_key=os.environ.get("KENZ_GATEWAY_KEY", "mock-key"),
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
**Price**: $10 / month  
**Summary**: Drop-in OpenAI-compatible reverse proxy cutting >85% of LLM token waste in agent loops with AST code skeletons and CLI output firewalls. 100% Halal *İcâre* contract with zero interest.  
**URL**: `https://polar.sh/autonomy-corp/subscriptions`
