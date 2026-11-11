"""Reproducible iktisad benchmark.

Usage (from products/iktisad):
    python benchmarks/run_benchmark.py

Everything is generated inside this script:
  1. A temp pytest project with 20 failing + 80 passing tests -> real `pytest -v` stdout.
  2. A temp pytest project with 99 passing tests -> real `pytest -v` stdout.
  3. AST recon over the real source files in iktisad/ (raw file text vs. skeleton).

Measured: raw chars, compressed chars, compression wall-clock time
(median of 50 repetitions; pytest's own runtime is NOT included).

Token counts are ESTIMATED as chars / 4 (no tokenizer dependency) and are
labelled "est. tokens". Real tokenizer counts will differ.
Pure stdlib + the local iktisad package; requires pytest to be installed.
"""

from __future__ import annotations

import os
import platform
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from iktisad.core import compress_cli_observation, extract_ast_skeleton  # noqa: E402

REPS = 50


def est_tokens(chars: int) -> int:
    """Estimated tokens = chars / 4 (rounded)."""
    return round(chars / 4)


def median_ms(fn: Callable[[], object]) -> float:
    """Median wall-clock time of fn() over REPS runs, in milliseconds."""
    samples: list[float] = []
    for _ in range(REPS):
        t0 = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - t0) * 1000.0)
    return statistics.median(samples)


def failing_project_source(n_fail: int, n_pass: int) -> str:
    """Deterministic test module with nested-call failures (real tracebacks)."""
    parts = [
        "def parse_record(row):\n"
        "    key, value = row.split('=')\n"
        "    return {key: int(value)}\n\n",
        "def aggregate(rows):\n"
        "    out = {}\n"
        "    for r in rows:\n"
        "        out.update(parse_record(r))\n"
        "    return out\n\n",
    ]
    for i in range(n_fail):
        parts.append(
            f"def test_fail_{i:03d}():\n"
            f"    result = aggregate(['a=1', 'b=2', 'c={i}'])\n"
            f"    assert result == {{'a': 1, 'b': 2, 'c': {i + 1}}}\n\n"
        )
    for i in range(n_pass):
        parts.append(f"def test_pass_{i:03d}():\n    assert aggregate(['x={i}']) == {{'x': {i}}}\n\n")
    return "".join(parts)


def passing_project_source(n_pass: int) -> str:
    return "".join(f"def test_ok_{i:03d}():\n    assert {i} + 1 == {i + 1}\n\n" for i in range(n_pass))


def run_pytest_on(source: str, name: str) -> str:
    """Write source into a fixed-name temp dir and return real pytest stdout+stderr."""
    proj = Path(tempfile.gettempdir()) / f"iktisad_bench_{name}"
    shutil.rmtree(proj, ignore_errors=True)
    proj.mkdir(parents=True)
    (proj / "test_generated.py").write_text(source, encoding="utf-8")
    env = dict(os.environ, PYTHONHASHSEED="0", PYTEST_ADDOPTS="", NO_COLOR="1")
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "-v", "-p", "no:cacheprovider", "test_generated.py"],
        cwd=proj, capture_output=True, text=True, env=env,
    )
    shutil.rmtree(proj, ignore_errors=True)
    return proc.stdout + proc.stderr


def bench_log(label: str, raw: str) -> dict[str, object]:
    obs = compress_cli_observation(raw)
    ms = median_ms(lambda: compress_cli_observation(raw))
    return {"label": label, "raw": obs.raw_chars, "comp": obs.compressed_chars, "ms": ms,
            "has_error": obs.has_error}


def bench_ast() -> dict[str, object]:
    os.chdir(ROOT)  # relative paths -> deterministic skeleton text
    files = sorted(Path("iktisad").glob("*.py"))
    raw = sum(len(f.read_text(encoding="utf-8")) for f in files)
    loc = sum(len(f.read_text(encoding="utf-8").splitlines()) for f in files)
    comp = sum(len(extract_ast_skeleton(f).render_compact()) for f in files)
    ms = median_ms(lambda: [extract_ast_skeleton(f).render_compact() for f in files])
    return {"label": f"AST recon: iktisad/*.py ({len(files)} files, {loc:,} LOC)",
            "raw": raw, "comp": comp, "ms": ms, "has_error": False}


def main() -> int:
    import pytest  # only for version reporting

    rows = [
        bench_log("pytest -v: 20 failing + 80 passing tests",
                  run_pytest_on(failing_project_source(20, 80), "fail")),
        bench_log("pytest -v: 99 passing tests",
                  run_pytest_on(passing_project_source(99), "pass")),
        bench_ast(),
    ]
    print(f"Python {platform.python_version()} | pytest {pytest.__version__} | {platform.system()}")
    print("est. tokens = chars / 4 (estimate, no tokenizer); time = median of "
          f"{REPS} runs of compression/skeleton only\n")
    print("| Scenario | Raw chars (est. tokens) | iktisad chars (est. tokens) | Reduction | Time |")
    print("| :--- | ---: | ---: | ---: | ---: |")
    for r in rows:
        raw, comp = int(r["raw"]), int(r["comp"])  # type: ignore[arg-type]
        red = 100.0 * (1.0 - comp / raw) if raw else 0.0
        print(f"| {r['label']} | {raw:,} ({est_tokens(raw):,}) | {comp:,} ({est_tokens(comp):,}) "
              f"| -{red:.1f}% | {float(r['ms']):.2f} ms |")  # type: ignore[arg-type]
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
