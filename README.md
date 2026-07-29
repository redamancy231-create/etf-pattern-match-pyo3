# etf-pattern-match-pyo3

[简体中文](README.md) · [正體中文](zh-Hant/README.md) · [English](en/README.md)

[![CI](https://github.com/redamancy231-create/etf-pattern-match-pyo3/actions/workflows/ci.yml/badge.svg)](https://github.com/redamancy231-create/etf-pattern-match-pyo3/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB.svg)](https://www.python.org/)
[![Rust](https://img.shields.io/badge/Rust-1.97%2B-000000.svg)](https://www.rust-lang.org/)

基于 **Rust + PyO3** 的 ETF 形态匹配计算核心，提供 DTW、余弦相似度、序列标准化、15 维形态特征和 rayon 并行批量计算。

## 关联项目

| 项目 | 关系 |
|---|---|
| [etf-pattern-match-pybind11](https://github.com/redamancy231-create/etf-pattern-match-pybind11) | C++/pybind11 原版与 golden fixtures 来源 |
| [ml-quant-trading](https://github.com/initial-d/ml-quant-trading) | Panel 数据格式与回测系统 |
| [ashare-mcp](https://github.com/CharmYue/ashare-mcp) | MCP 数据源与原子工具协作参考 |

## 快速开始

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

`pattern_match_single` 在历史样本不足时返回 `None`；成功时返回以 `FEATURE_KEYS` 为键的 15 维特征字典。

## API 参考

| 公开符号 | 说明 |
|---|---|
| `standardize_returns(prices)` | 将价格序列转换为标准化对数收益率，返回长度 `n-1` 的 `float64` 数组 |
| `cosine_similarity(x, y)` | 计算两个等长一维序列的余弦相似度 |
| `dtw_distance(x, y, window=5)` | 计算带 Sakoe-Chiba 约束的 DTW 距离 |
| `pattern_match_single(prices, T_idx, ...)` | 在单个时间点运行完整形态匹配，返回 15 维字典或 `None` |
| `pattern_match_batch(prices, t_indices, ...)` | rayon 并行批量匹配，返回 `(features_X15, valid_mask)` |
| `FEATURE_KEYS` | 15 个特征名的稳定顺序常量 |

Panel 适配器提供 `panel_to_prices`、`pattern_match_single_panel` 和 `pattern_match_batch_panel`；FastMCP server 通过可选依赖启用。它们不改变上述六个核心公开符号。

## 验证基线

- Rust：14/14 tests PASS。
- Python：68 PASS + 2 SKIP（未安装 Torch/GPU 时）。
- Golden fixtures：31/31 PASS。

## 性能摘要

[NRR-2026-023](docs/NRR-2026-023_cpp_vs_rust_comparison.md) 使用冻结 corpus 比较 Rust/PyO3 与 C++/pybind11。wrapper-internal 中位数显示：单线程 DTW L=19 为 `0.700 µs` 对 `2.200 µs`，单次形态匹配为 `0.282 ms` 对 `0.533 ms`；单线程 batch 100 落入“打平”区间。16 线程下 Rust batch 为 `5.788 ms`，相对自身单线程实现约 **5.33×** 加速，并快于 C++ 对照。

这些结果不是普适速度承诺：多数核心指标的 CoV 超过 5%，按预登记均降级为“倾向性结论”；cosine 的内部计时低于计时器有效分辨率，无法作语言性能判定。请在目标硬件和真实数据上复测。

## 安装

```bash
pip install etf-pattern-match-pyo3
pip install "etf-pattern-match-pyo3[panel]"  # Torch Panel 适配器
pip install "etf-pattern-match-pyo3[mcp]"    # FastMCP server
pip install "etf-pattern-match-pyo3[dev]"    # pytest + ruff
```

要求 Python 3.12+。从源码构建还需要 Rust 1.97+ 与 MSVC 工具链。

## 开发

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

构建并检查 wheel：

```powershell
maturin build --release --out dist
$wheel = Get-ChildItem dist/*.whl | Select-Object -First 1
python scripts/check_wheel.py $wheel.FullName
```

交互演示见 [notebooks/etf_pattern_matching_demo.ipynb](notebooks/etf_pattern_matching_demo.ipynb)。贡献方式见 [CONTRIBUTING.md](CONTRIBUTING.md)，版本记录见 [CHANGELOG.md](CHANGELOG.md)。

## 许可证

本项目采用 [MIT License](LICENSE)。原版归属与关键依赖许可证见 [NOTICE](NOTICE)。
