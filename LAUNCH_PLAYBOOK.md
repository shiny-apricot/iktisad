# `iktisad` (v0.3.0) — Open-Source Launch Playbook

> **Positioning**: Zero-dependency Python token defense engine and native MCP server for AI coding agents.  
> **License & Pricing**: Free MIT Open-Source Core (CLI, Python AST, stdio MCP) + `$10/mo` Polar Pro (`https://buy.polar.sh/polar_cl_yzz3PkDzy0RGI5tD7PCly2oMkieyP5jUPKrF11bpqcA`) for commercial team convenience, curated local presets (`iktisad --export-presets`), and `<24h` priority support (`kenzailab@gmail.com`).  
> **Verified Baseline (`benchmarks/RESULTS.md` & live `pytest`)**: `85 passed` in `products/iktisad/tests/`, `-94.5%` failing pytest reduction (`21,842 -> 1,194 chars`, `1.59–1.61 ms`), `-99.7%` passing pytest reduction (`8,256 -> 22 chars`, `0.19 ms`), `-93.1%` Python AST skeleton reduction (`130,567 -> 8,977 chars` across 5 files / `3,637 LOC`, `17.46–17.96 ms`).

---

## Table of Contents
1. [Launch Strategy & Distribution Sequencing](#1-launch-strategy--distribution-sequencing)
2. [Show HN Submission](#2-show-hn-submission)
3. [Reddit r/LocalLLaMA Post](#3-reddit-rlocalllama-post)
4. [Reddit r/Python Post](#4-reddit-rpython-post)
5. [X / Twitter Launch Thread](#5-x--twitter-launch-thread)
6. [GitHub README Hero Section](#6-github-readme-hero-section)
7. [Community FAQ](#7-community-faq)

---

## 1. Launch Strategy & Distribution Sequencing

1. **Release Gate**:
   - Confirm GitHub release tag `v0.3.0` and MIT `LICENSE` are live on `https://github.com/shiny-apricot/iktisad`.
   - Confirm PyPI `pip install iktisad` (`0.3.0`) and `products/iktisad/tests/` (`85 passed`) pass cleanly.
2. **Wave 1 (Show HN)**:
   - Publish **Show HN** focusing on deterministic terminal log compression, Python AST skeletons, and native stdio MCP tools.
3. **Wave 2 (r/LocalLLaMA & r/Python)**:
   - Publish **r/LocalLLaMA** post on protecting 8k/32k local context windows with `iktisad compress -` and `iktisad --mcp`.
   - Publish **r/Python** post on pure stdlib `ast` skeletonization and `0` third-party dependencies.
4. **Wave 3 (X / Twitter & Ecosystem Follow-ups)**:
   - Publish the 7-part technical thread with reproducible `benchmarks/RESULTS.md` numbers.
   - Answer all comments with exact CLI flags (`iktisad run -- <cmd>`, `iktisad compress -`, `iktisad --ast-skeleton <file>`).

---

## 2. Show HN Submission

### Post Title
```text
Show HN: iktisad (v0.3.0) – Zero-dependency log compressor & MCP server for coding agents
```

### URL
```text
https://github.com/shiny-apricot/iktisad
```

### Post Body

```markdown
Hi HN,

I built **iktisad** (`v0.3.0`, MIT License), a zero-dependency Python CLI and native MCP server that filters terminal noise and extracts Python AST skeletons before prompts reach your LLM.

### Why I Built It
Coding agents (Claude Code, Cursor, Windsurf, Aider) repeatedly dump thousands of characters of passing test lines, ANSI escape codes, and full source files into prompts. In reasoning models, every noisy line inflates context pressure, triggers 429 rate limits, and crowds out architectural instructions.

### What `iktisad` Does (Pure Python 3.10+ Stdlib)
- **Native MCP Server (`iktisad --mcp` / `iktisad-mcp`)**: Connects directly to Cursor, Claude Code, and Windsurf over stdio JSON-RPC. Exposes 5 tools: `compress_terminal_log`, `extract_ast_skeleton`, `select_frugal_model`, `check_circuit_breaker`, and `run_release_preflight_audit`.
- **CLI Runner & Pipe (`iktisad run -- pytest` / `iktisad compress -`)**: Strips ANSI sequences and passing progress lines while keeping `=== FAILURES ===`, `E   AssertionError`, and `file:line` tracebacks intact.
- **Python AST Skeletonizer (`iktisad --ast-skeleton src/app.py`)**: Parses Python files via stdlib `ast` into class hierarchies, function signatures, type hints, docstrings, and exact line ranges at `0` LLM tokens.
- **Local Gateway & GitHub App CI Guard (`iktisad gateway --port 8000`, `iktisad github-app --manifest`)**: Optional local reverse proxy, SQLite budget tracking (`iktisad --bandwidth-usage`), and CI PR guard.

### Verified Benchmarks (`benchmarks/RESULTS.md`)
Measured on Python 3.12.3 and pytest 9.0.2 (median of 50 runs; `est. tokens = chars / 4`):
- **Failing pytest (`20 failed, 80 passed`)**: `21,842 chars` -> `1,194 chars` (**-94.5%**, `1.59–1.61 ms`)
- **Passing pytest (`99 passed`)**: `8,256 chars` -> `22 chars` (**-99.7%**, `0.19 ms`)
- **Python AST recon (`5 files, 3,637 LOC`)**: `130,567 chars` -> `8,977 chars` (**-93.1%**, `17.46–17.96 ms`)
- **Test suite**: `85 passed` in `products/iktisad/tests/` with `0` third-party dependencies.

### Quickstart
```bash
pip install iktisad

iktisad --mcp
iktisad run -- pytest -q
pytest -v | iktisad compress -
iktisad --ast-skeleton src/main.py
iktisad --export-presets
```

Core CLI, Python AST, and stdio MCP are free under MIT. A `$10/mo` Polar Pro tier is available for commercial team convenience, curated local presets, and `<24h` priority support (`kenzailab@gmail.com`).

GitHub: https://github.com/shiny-apricot/iktisad  
Docs & Visualizer: https://shiny-apricot.github.io/iktisad/  
PyPI: https://pypi.org/project/iktisad/
```

---

## 3. Reddit r/LocalLLaMA Post

### Subreddit
`r/LocalLLaMA`

### Post Title
```text
I built a zero-dependency MCP server & log firewall to protect local 8k/32k context windows
```

### Post Body

```markdown
When running local coding agents with Ollama, vLLM, or llama.cpp on 8k or 32k context windows, raw test output eats KV-cache fast.

A single pytest run with 20 failures and 80 passes outputs `21,842` chars (~`5,460` est. tokens at `chars / 4`). Dumping raw source files to inspect a single signature wastes tens of thousands more chars.

I built **`iktisad`** (`v0.3.0`, MIT License), a pure Python 3.10+ stdlib CLI and native MCP server with zero external dependencies.

### Key Features
1. **Terminal Log Compression (`iktisad run -- pytest` or `pytest | iktisad compress -`)**:
   - `20 failed, 80 passed`: `21,842 chars` -> `1,194 chars` (**-94.5%** in `1.59–1.61 ms`), preserving `=== FAILURES ===`, assertions, and `file:line` markers.
   - `99 passed`: `8,256 chars` -> `22 chars` (**-99.7%** in `0.19 ms`).
2. **Python AST Skeletons (`iktisad --ast-skeleton app.py`)**:
   - Across 5 Python files (`3,637 LOC`): `130,567 chars` -> `8,977 chars` (**-93.1%** in `17.46–17.96 ms`, `0` LLM tokens).
3. **Native MCP Server (`iktisad --mcp` / `iktisad-mcp`)**:
   - Exposes `compress_terminal_log`, `extract_ast_skeleton`, `select_frugal_model`, `check_circuit_breaker`, and `run_release_preflight_audit`.
4. **Local Gateway & Presets**:
   - Start a local proxy with `iktisad gateway --port 8000` (or `iktisad --serve-gateway --port 8000`) and export client configs with `iktisad --export-presets`.

### Quickstart
```bash
pip install iktisad
iktisad --mcp
pytest -v | iktisad compress -
```

Verified locally across `85 passed` tests.

GitHub (MIT): https://github.com/shiny-apricot/iktisad  
PyPI: https://pypi.org/project/iktisad/
```

---

## 4. Reddit r/Python Post

### Subreddit
`r/Python`

### Post Title
```text
iktisad v0.3.0: Zero-dependency Python stdlib log compressor, AST skeletonizer & MCP server
```

### Post Body

```markdown
Hi r/Python!

I built **`iktisad`** (`v0.3.0`, MIT License) using only the Python 3.10+ standard library (`ast`, `re`, `sqlite3`, `dataclasses`, `argparse`, `json`) to prevent AI coding agents from flooding context windows with raw pytest stdout and full source files.

### Highlights
- **Zero External Dependencies**: Installs cleanly via `pip install iktisad` with `dependencies = []`.
- **Failing-Traceback-Preserving Log Compressor**: Drops `PASSED` noise while keeping `=== FAILURES ===`, `> assert ...`, `E   AssertionError`, and `file:line` markers within a `1,200`-char default budget (`21,842 -> 1,194 chars`, `-94.5%` in `1.59–1.61 ms`). Passing suites (`99 passed`) collapse from `8,256 chars` to `22 chars` (`-99.7%` in `0.19 ms`).
- **Python AST Skeletonizer**: Uses `ast.parse` to extract class hierarchies, typed signatures, docstrings, and line ranges (`130,567 -> 8,977 chars` across 5 files / `3,637 LOC`, `-93.1%` in `17.46–17.96 ms`).
- **Native Stdio MCP & CLI**: Run `iktisad --mcp`, `iktisad run -- pytest`, `iktisad compress -`, `iktisad --bandwidth-usage`, `iktisad gateway --port 8000`, or `iktisad github-app --manifest`.
- **Verified Suite**: `85 passed` tests in `products/iktisad/tests/`.

### Usage
```bash
pip install iktisad
iktisad run -- pytest -q
iktisad --ast-skeleton iktisad/core.py
iktisad --export-presets
```

GitHub: https://github.com/shiny-apricot/iktisad  
Visualizer: https://shiny-apricot.github.io/iktisad/
```

---

## 5. X / Twitter Launch Thread

### Tweet 1
```text
AI coding agents waste huge context budgets on raw pytest stdout and full-file reads.

We released iktisad v0.3.0 (MIT): a zero-dependency Python CLI & native MCP server.

Verified in benchmarks/RESULTS.md:
- Failing pytest: -94.5% chars (1.59 ms)
- Passing pytest: -99.7% chars (0.19 ms)
- Python AST (5 files): -93.1% chars

Thread 👇
```

### Tweet 2
```text
When 20 tests fail and 80 pass, pytest outputs 21,842 chars (~5,460 est. tokens).

`iktisad compress -` and `iktisad run -- pytest` pack that down to 1,194 chars (~298 est. tokens) in 1.59–1.61 ms.

`PASSED` noise is stripped while `=== FAILURES ===`, assertions, and `file:line` tracebacks stay intact.
```

### Tweet 3
```text
When all 99 tests pass, raw stdout is 8,256 chars (~2,064 est. tokens).

iktisad collapses it to 22 chars (~6 est. tokens) in 0.19 ms.

That is a verified -99.7% reduction with zero LLM calls.
```

### Tweet 4
```text
Reading 5 Python modules (3,637 LOC) verbatim costs 130,567 chars (~32,642 est. tokens).

`iktisad --ast-skeleton <file>` uses Python stdlib `ast` to emit typed signatures, docstrings, and line bounds: 8,977 chars (~2,244 est. tokens, -93.1%) in 17.46–17.96 ms.
```

### Tweet 5
```text
Native Model Context Protocol (MCP) server over stdio:

`iktisad --mcp` (or `iktisad-mcp`)

Exposes 5 tools to Cursor, Claude Code, and Windsurf:
- `compress_terminal_log`
- `extract_ast_skeleton`
- `select_frugal_model`
- `check_circuit_breaker`
- `run_release_preflight_audit`
```

### Tweet 6
```text
Built with 0 third-party dependencies on Python 3.10+ stdlib.

Includes local SQLite accounting (`iktisad --bandwidth-usage`), local proxy (`iktisad gateway --port 8000`), GitHub App manifest (`iktisad github-app --manifest`), and client presets (`iktisad --export-presets`).

Verified across 85 passing tests.
```

### Tweet 7
```text
Core CLI, Python AST, and stdio MCP are free under the MIT License.

Polar Pro ($10/mo) adds commercial team convenience, curated presets, and <24h support (`kenzailab@gmail.com`).

pip install iktisad
GitHub: https://github.com/shiny-apricot/iktisad
Docs: https://shiny-apricot.github.io/iktisad/
Polar Pro: https://buy.polar.sh/polar_cl_yzz3PkDzy0RGI5tD7PCly2oMkieyP5jUPKrF11bpqcA
```

---

## 6. GitHub README Hero Section

```markdown
# iktisad (v0.3.0)

Deterministic, zero-dependency context firewall, Python AST skeletonizer, and native MCP server for AI coding agents.

- **Failing pytest (`20 failed, 80 passed`)**: `21,842 -> 1,194 chars` (**-94.5%**, `1.59–1.61 ms`)
- **Passing pytest (`99 passed`)**: `8,256 -> 22 chars` (**-99.7%**, `0.19 ms`)
- **Python AST (`5 files, 3,637 LOC`)**: `130,567 -> 8,977 chars` (**-93.1%**, `17.46–17.96 ms`)

### Quickstart
```bash
pip install iktisad
iktisad --mcp
iktisad run -- pytest -q
pytest -v | iktisad compress -
iktisad --ast-skeleton src/app.py
iktisad --bandwidth-usage
iktisad gateway --port 8000
iktisad github-app --manifest
iktisad --pro
iktisad --export-presets
```
```

---

## 7. Community FAQ

### Q: Why filter logs deterministically instead of summarizing with an LLM?
**A**: Summarizing raw logs with an LLM still consumes prompt tokens and adds latency. `iktisad` compresses failing pytest output in `1.59–1.61 ms` and passing output in `0.19 ms` on CPU with `0` LLM calls.

### Q: Does log compression drop failing tracebacks?
**A**: No. Passing test noise is stripped while `=== FAILURES ===`, `> assert ...`, `E   AssertionError`, and `file:line` traceback markers are preserved within the `1,200`-char default budget.

### Q: What languages does `--ast-skeleton` support right now?
**A**: Python 3.10+ via the built-in `ast` standard library module. It extracts classes, function signatures, type annotations, docstrings, and line bounds.

### Q: What is included in MIT Core vs. Polar Pro ($10/mo)?
**A**: The CLI, Python AST skeletonizer, local gateway, and 5-tool stdio MCP server are free under the MIT License (`85 passed` tests). Polar Pro (`$10/mo`) provides commercial team convenience, curated local presets (`iktisad --export-presets`), and `<24h` priority support via `kenzailab@gmail.com`.
