# 关键文件索引

> 最后更新: 2026-07-29
> 对应框架 S2

## 项目治理

- [CLAUDE.md](CLAUDE.md) — Agent 操作约束（非 S1-S10 容器；S1-S10 metadata 见 `project_status.md`）
- [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) — 实现计划（6 Phase + 审查附录）
- [project_status.md](project_status.md) — 会话级状态追踪
- [DEV_LOG.md](DEV_LOG.md) — 累积式变更日志
- [README.md](README.md) — 项目首页

## 审查

审查提示词与报告为内部产物，存放于 `_review/`（不公开发布）。

## Rust 核心

- `src/lib.rs` — PyO3 入口，注册 Python 模块
- `src/types.rs` — 共享数据结构
- `src/features.rs` — 15 维特征常量和聚合逻辑
- `src/standardize.rs` — 序列标准化
- `src/dtw.rs` — DTW 距离 + Sakoe-Chiba band
- `src/cosine.rs` — 余弦相似度 + 预筛选
- `src/pattern_match.rs` — 形态匹配引擎
- `src/batch.rs` — 批量匹配 + rayon 并行

## Python 包

- `python/etf_pattern_match_pyo3/__init__.py` — 包入口，re-export 全部符号
- `python/etf_pattern_match_pyo3/panel_adapter.py` — [P1] Panel 格式适配器
- `python/etf_pattern_match_pyo3/mcp_server.py` — [P2] MCP server
- `python/etf_pattern_match_pyo3/gpu_adapter.py` — GPU 加速余弦预筛选（[gpu] extra）
- `python/etf_pattern_match_pyo3/py.typed` — PEP 561 标记

## 测试

- `tests/test_dtw.py` — DTW 专项测试
- `tests/test_consistency.py` — Rust vs Python 参考实现一致性
- `tests/test_golden_pyo3.py` — Golden fixtures 验证（PyO3 接口）
- `tests/test_pyo3_bindings.py` — PyO3 绑定测试
- `tests/test_gpu_adapter.py` — GPU 适配器测试（需 cupy）
- `tests/test_mcp_server.py` — MCP server 测试（需 fastmcp）
- `tests/test_panel_adapter.py` — Panel 适配器测试（需 torch）
- `tests/fixtures/` — 31 个 golden fixtures（JSON，C++ 原版 commit `7c1269a`）

## 验证与基准

- `verify_etf_core.py` — Rust vs golden fixtures 一致性验证
- `verify_batch.py` — 批量形态匹配验证
- `benchmarks/generate_corpus.py` — Benchmark corpus 生成
- `benchmarks/gpu_vs_cpu_cosine.py` — GPU vs CPU 余弦相似度基准测试

## 构建配置

- `Cargo.toml` — Rust 项目配置
- `pyproject.toml` — Python 构建配置（maturin）
- `rust-toolchain.toml` — Rust 工具链版本锁定

## CI

- `.github/workflows/ci.yml` — Windows MSVC + Python 3.12 CI

## 文档

- `README.md` — 项目首页（简体中文）
- `zh-Hant/README.md` — 正體中文 README
- `en/README.md` — English README
- `CHANGELOG.md` — 版本记录
- `CONTRIBUTING.md` — 贡献指南
- [docs/NRR-2026-023_cpp_vs_rust_comparison.md](docs/NRR-2026-023_cpp_vs_rust_comparison.md) — NRR-2026-023：C++ vs Rust 对比
- [docs/nrr_gate2_preregistration.md](docs/nrr_gate2_preregistration.md) — Phase 4 预登记（🔒 FROZEN）
- [docs/project_summary.md](docs/project_summary.md) — 终期总结
- [docs/releases/v0.1.0.md](docs/releases/v0.1.0.md) — v0.1.0 Release notes（Draft）
- `notebooks/etf_pattern_matching_demo.ipynb` — 交互演示

## 关联项目（外部）

- [etf-pattern-match-pybind11](https://github.com/redamancy231-create/etf-pattern-match-pybind11) — C++ 原版，golden fixtures 来源
- [ml-quant-trading](https://github.com/initial-d/ml-quant-trading) — Panel 格式来源
- [ashare-mcp](https://github.com/CharmYue/ashare-mcp) — MCP 模式参考
- [AI 协作框架](https://github.com/redamancy231-create/ai-collaboration-framework) — 方法论上游
