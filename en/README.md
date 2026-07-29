# etf-pattern-match-pyo3

[简体中文](../README.md) · [正體中文](../zh-Hant/README.md) · [English](README.md)

[![CI](https://github.com/redamancy231-create/etf-pattern-match-pyo3/actions/workflows/ci.yml/badge.svg)](https://github.com/redamancy231-create/etf-pattern-match-pyo3/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](../LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB.svg)](https://www.python.org/)
[![Rust](https://img.shields.io/badge/Rust-1.97%2B-000000.svg)](https://www.rust-lang.org/)

A **Rust + PyO3** compute core for ETF pattern matching, with DTW, cosine similarity, return standardization, a 15-dimensional morphology vector, and rayon-powered batch execution.

## Related projects

| Project | Relationship |
|---|---|
| [etf-pattern-match-pybind11](https://github.com/redamancy231-create/etf-pattern-match-pybind11) | Original C++/pybind11 implementation and source of the golden fixtures |
| [ml-quant-trading](https://github.com/initial-d/ml-quant-trading) | Panel data format and backtesting system |
| [ashare-mcp](https://github.com/CharmYue/ashare-mcp) | MCP data source and atomic-tool integration reference |
| [Profile](https://github.com/redamancy231-create/redamancy231-create) | All public repositories and project relationship overview |

## Quick start

```bash
pip install etf-pattern-match-pyo3
```

```python
import numpy as np
from etf_pattern_match_pyo3 import FEATURE_KEYS, pattern_match_single
prices = 100.0 * np.cumprod(1.0 + np.random.default_rng(42).normal(0, 0.01, 800))
features = pattern_match_single(prices, T_idx=500)
print({key: features[key] for key in FEATURE_KEYS} if features else None)
```

`pattern_match_single` returns `None` when there is not enough history; otherwise it returns a 15-feature dictionary keyed by `FEATURE_KEYS`.

## API reference

| Public symbol | Description |
|---|---|
| `standardize_returns(prices)` | Converts prices to standardized log returns and returns a length `n-1` `float64` array |
| `cosine_similarity(x, y)` | Computes cosine similarity for two equal-length one-dimensional sequences |
| `dtw_distance(x, y, window=5)` | Computes DTW distance with a Sakoe-Chiba constraint |
| `pattern_match_single(prices, T_idx, ...)` | Runs the full matcher at one time point and returns a 15-feature dictionary or `None` |
| `pattern_match_batch(prices, t_indices, ...)` | Runs rayon-parallel matching and returns `(features_X15, valid_mask)` |
| `FEATURE_KEYS` | Stable ordering of the 15 feature names |

The optional Panel adapter exposes `panel_to_prices`, `pattern_match_single_panel`, and `pattern_match_batch_panel`. The optional FastMCP server is enabled separately. Neither changes the six core public symbols above.

## Validation baseline

- Rust: 14/14 tests PASS.
- Python: 68 PASS + 2 SKIP when Torch/GPU is not available.
- Golden fixtures: 31/31 PASS.

## Performance summary

[NRR-2026-023](../docs/NRR-2026-023_cpp_vs_rust_comparison.md) compares Rust/PyO3 with the C++/pybind11 baseline on a frozen corpus. Wrapper-internal medians show single-threaded DTW L=19 at `0.700 µs` versus `2.200 µs`, and single pattern matching at `0.282 ms` versus `0.533 ms`; single-threaded batch 100 is classified as tied. With 16 threads, Rust batch takes `5.788 ms`, provides about **5.33×** self-speedup over its single-threaded path, and is faster than the C++ baseline.

These numbers are not a universal speed guarantee. Most core metrics have CoV above 5%, so the preregistered protocol downgrades them to directional findings. Internal cosine timing is below the effective timer resolution and cannot support a language-performance conclusion. Rebenchmark on your target hardware and real data.

## Installation

```bash
pip install etf-pattern-match-pyo3
pip install "etf-pattern-match-pyo3[panel]"  # Torch Panel adapter
pip install "etf-pattern-match-pyo3[mcp]"    # FastMCP server
pip install "etf-pattern-match-pyo3[dev]"    # pytest + ruff
```

Python 3.12+ is required. Source builds also require Rust 1.97+ and the MSVC toolchain.

## Development

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install maturin numpy pytest
maturin develop --release
cargo fmt --all -- --check
cargo clippy --all-targets --all-features -- -D warnings
cargo test --release
python -m pytest tests/ -v
python verify_etf_core.py
python verify_batch.py
```

Build and inspect a wheel:

```powershell
maturin build --release --out dist
$wheel = Get-ChildItem dist/*.whl | Select-Object -First 1
python scripts/check_wheel.py $wheel.FullName
```

See [notebooks/etf_pattern_matching_demo.ipynb](../notebooks/etf_pattern_matching_demo.ipynb) for an interactive demo, [CONTRIBUTING.md](../CONTRIBUTING.md) for contribution guidance, and [CHANGELOG.md](../CHANGELOG.md) for release history.

## License

Licensed under the [MIT License](../LICENSE). Original-project attribution and key dependency licenses are listed in [NOTICE](../NOTICE).
