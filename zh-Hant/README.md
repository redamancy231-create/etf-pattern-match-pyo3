# etf-pattern-match-pyo3

[简体中文](../README.md) · [正體中文](README.md) · [English](../en/README.md)

[![CI](https://github.com/redamancy231-create/etf-pattern-match-pyo3/actions/workflows/ci.yml/badge.svg)](https://github.com/redamancy231-create/etf-pattern-match-pyo3/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](../LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB.svg)](https://www.python.org/)
[![Rust](https://img.shields.io/badge/Rust-1.97%2B-000000.svg)](https://www.rust-lang.org/)

以 **Rust + PyO3** 實作的 ETF 型態匹配計算核心，提供 DTW、餘弦相似度、序列標準化、15 維型態特徵與 rayon 平行批次計算。

## 關聯專案

| 專案 | 關係 |
|---|---|
| [etf-pattern-match-pybind11](https://github.com/redamancy231-create/etf-pattern-match-pybind11) | C++/pybind11 原版與 golden fixtures 來源 |
| [ml-quant-trading](https://github.com/initial-d/ml-quant-trading) | Panel 資料格式與回測系統 |
| [ashare-mcp](https://github.com/CharmYue/ashare-mcp) | MCP 資料來源與原子工具協作參考 |
| [個人主頁](https://github.com/redamancy231-create/redamancy231-create) | 全部公開倉庫索引與專案關係總覽 |

## 快速開始

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

`pattern_match_single` 在歷史樣本不足時回傳 `None`；成功時回傳以 `FEATURE_KEYS` 為鍵的 15 維特徵字典。

## API 參考

| 公開符號 | 說明 |
|---|---|
| `standardize_returns(prices)` | 將價格序列轉換為標準化對數報酬率，回傳長度 `n-1` 的 `float64` 陣列 |
| `cosine_similarity(x, y)` | 計算兩個等長一維序列的餘弦相似度 |
| `dtw_distance(x, y, window=5)` | 計算帶 Sakoe-Chiba 約束的 DTW 距離 |
| `pattern_match_single(prices, T_idx, ...)` | 在單一時間點執行完整型態匹配，回傳 15 維字典或 `None` |
| `pattern_match_batch(prices, t_indices, ...)` | rayon 平行批次匹配，回傳 `(features_X15, valid_mask)` |
| `FEATURE_KEYS` | 15 個特徵名稱的穩定順序常數 |

Panel 轉接器另提供 `panel_to_prices`、`pattern_match_single_panel` 與 `pattern_match_batch_panel`；FastMCP server 透過選用依賴啟用，不會改變上述六個核心公開符號。

## 驗證基線

- Rust：14/14 tests PASS。
- Python：68 PASS + 2 SKIP（未安裝 Torch/GPU 時）。
- Golden fixtures：31/31 PASS。

## 效能摘要

[NRR-2026-023](../docs/NRR-2026-023_cpp_vs_rust_comparison.md) 使用凍結 corpus 比較 Rust/PyO3 與 C++/pybind11。wrapper-internal 中位數顯示：單執行緒 DTW L=19 為 `0.700 µs` 對 `2.200 µs`，單次型態匹配為 `0.282 ms` 對 `0.533 ms`；單執行緒 batch 100 落在「打平」區間。16 執行緒下 Rust batch 為 `5.788 ms`，相對自身單執行緒實作約 **5.33×** 加速，且快於 C++ 對照。

這些結果不是普遍速度承諾：多數核心指標的 CoV 超過 5%，依預登錄均降級為「傾向性結論」；cosine 的內部計時低於計時器有效解析度，無法進行語言效能判定。請在目標硬體與真實資料上重測。

## 安裝

```bash
pip install etf-pattern-match-pyo3
pip install "etf-pattern-match-pyo3[panel]"  # Torch Panel 轉接器
pip install "etf-pattern-match-pyo3[mcp]"    # FastMCP server
pip install "etf-pattern-match-pyo3[dev]"    # pytest + ruff
```

需要 Python 3.12+。從原始碼建置另需 Rust 1.97+ 與 MSVC 工具鏈。

## 開發

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

建置並檢查 wheel：

```powershell
maturin build --release --out dist
$wheel = Get-ChildItem dist/*.whl | Select-Object -First 1
python scripts/check_wheel.py $wheel.FullName
```

互動示範見 [notebooks/etf_pattern_matching_demo.ipynb](../notebooks/etf_pattern_matching_demo.ipynb)。貢獻方式見 [CONTRIBUTING.md](../CONTRIBUTING.md)，版本紀錄見 [CHANGELOG.md](../CHANGELOG.md)。

## 授權

本專案採用 [MIT License](../LICENSE)。原版歸屬與主要依賴授權見 [NOTICE](../NOTICE)。
