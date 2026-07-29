# Changelog

本项目遵循语义化版本。日期使用 `YYYY-MM-DD`。

## v0.1.0 (2026-07-29)

- **Phase 0**：Rust 1.97.1 工具链 + maturin 骨架 + 31 个 golden fixtures（来自 C++ 原版 commit `7c1269a`）。
- **Phase 1**：纯 Rust 计算核心——DTW（Sakoe-Chiba band）、余弦相似度、序列标准化、15 维形态匹配引擎与 rayon 并行批量匹配。
- **Phase 2**：PyO3 绑定——5 个 Python 函数 + `FEATURE_KEYS` 常量，GIL 三层策略。
- **Phase 3**：一致性验证——31 golden fixtures、`verify_etf_core.py` 与 `verify_batch.py` 全部通过。
- **Phase 4**：C++ vs Rust benchmark——NRR-2026-023 完整对比报告。
- **Phase 5**：Panel 适配器 + FastMCP server（可选 extras）。
- **GPU**：cupy 余弦预筛选 GPU 加速（`[gpu]` extra），RTX 4060 Laptop 实测 N=5000 端到端约 6.0×。
- **Phase 6**：Windows/Python 3.12 CI、wheel 内容门禁、三语 README、Notebook、社区健康文件。

### 验证基线

- `cargo test --release`：14/14 PASS。
- `pytest tests/ -v`：68 PASS + 2 SKIP（未安装 Torch 时跳过对应 Panel 用例）。
- `verify_etf_core.py`：31/31 golden fixtures PASS。
- `verify_batch.py`：全部 7 项 PASS。
