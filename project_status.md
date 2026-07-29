# etf-pattern-match-pyo3 项目状态

> 最后更新：2026-07-29
> 框架合规：AI 协作项目全生命周期框架 v1.6.4，L 档（正式研究）
> Spec 文档：`CLAUDE.md`（agent 操作指令；write-claude-md skill Step 1–5 已完成，GPT-5.6-Sol R3 + Kimi-K2.7-Code R4 双后端审查已汇总）
> 执行计划：`IMPLEMENTATION_PLAN.md`

## 当前阶段

## 当前阶段

**MAINTENANCE** — v0.1.0 已发布。Phase 0-6 全部完成，计划目标已达成。预期后续零散改进（功能增强、bug 修复、性能优化），无需走 S7 重启门槛。

## 关键文件

| 文件 | 说明 |
|------|------|
| `CLAUDE.md` | Agent 操作指令（write-claude-md skill 模板：Agent 边界/命令/停止条件/坑位/更新协议） |
| `IMPLEMENTATION_PLAN.md` | 581 行实现计划（6 Phase + 审查附录） |
| `DEV_LOG.md` | 累积式变更日志 |
| `reference_files.md` | 关键文件路径索引 |
| — | R1 审查报告存档于 `_review/conclusions/`（不公开发布） |
| `docs/nrr_gate2_preregistration.md` | Phase 4 冻结预登记（hash `dcb734fd3317570b`） |
| `docs/NRR-2026-023_cpp_vs_rust_comparison.md` | NRR-2026-023：C++ vs Rust 对比报告 |
| `docs/project_summary.md` | 终期总结 |
| `.github/workflows/ci.yml` | Windows MSVC/Python 3.12 持续集成门禁 |
| `README.md` / `zh-Hant/README.md` / `en/README.md` | 三语项目文档 |
| `docs/releases/v0.1.0.md` | GitHub Release notes 草稿 |
| `_review/conclusions/codex_phase6_output.md` | Phase 6 Codex 执行日志与验收结论 |

## 框架合规声明

本项目按 AI 协作项目全生命周期框架 v1.6.4 的 **L 档（正式研究）** 标准执行。**L 档为用户在项目启动时明确选择**——理由是：(a) 项目含正式 NRR 对比实验（C++ vs Rust），需深度 Retrospect + 外部审阅；(b) 产出将公开（GitHub + wheel 发布 + 三语文档），验收标准高于个人练习；(c) 预估 30-41h 接近 M 档上限且无法在一周内完成（非全职）。

- **使用强度**: 最低强制版 + S5 + S6 + S8 + S9。**当前落地状态**：S1-S4 ✅，HG-0/1/3 已定义，Phase 0-5 已执行，Dev Log 单时间轴 ✅，S5/S6/S8/S9 已生成 Phase 0-5 证据，后续阶段证据待生成。Phase 3-5 的验证、benchmark 与集成验收均保留了可复现脚本、原始结果或审计日志。
- **闭合标准**: L 档 — 终期总结 (.md) + 项目评估分析 + 深度 Retrospect + 外部审阅 + ≥3 条跨项目方法论写回。`.docx` 仅学术项目必须，本项目为工程型 L 档，不强制
- **HG 闸门**: HG-0（启动，含 Plan + Spec 双检查点）→ HG-1（每 Phase 完成）→ HG-3（闭合）
- **Dev Log**: `DEV_LOG.md` 单时间轴视图，Phase 6 升级为双视图 + FK
- **逃生口**: 工具/数据不可用 → 停止并报告，不用替代数据（框架 §4.3）。本规则已加入 CLAUDE.md 停止条件
- **CLAUDE.md 编写标准**: write-claude-md skill 五步协议，非框架附录 A 模板

## 成功标准（S5）

### 首要主指标

**行为兼容率**：按锁定的 API manifest（函数名/签名/默认值/返回 schema/异常类型/dtype/shape/模块常量）逐项验收 + golden fixtures 全部在容差内通过 = **100%**。任一未达标 → REDESIGN 或 STOP。

### 硬约束（必须全部满足，非目标-底线关系）

| 约束 | 标准 | 测量阶段 | 未达标的后果 |
|------|------|---------|------------|
| Golden fixtures | 100% 在容差内（`<=`，含边界） | Phase 3 | STOP——定位根因，修正后重跑 |
| API manifest | 100% 逐项匹配 | Phase 2-3 | STOP——修正 API 或更新 manifest（走 HG-2） |
| 测试通过率 | cargo test + pytest 全 PASS | Phase 1-3 | STOP——修正后重跑 |
| Wheel 可分发 | clean venv `pip install` + `import` 成功 | Phase 0, 2 | STOP——修正构建配置 |

### 辅指标（不阻塞发布，达标为加分项）

| 指标 | 期望值 | 测量阶段 | 不达标的处理 |
|------|--------|---------|------------|
| 单线程 DTW 性能 | ≥ C++ 版的 90% | Phase 4 | 记录 NRR + 性能分析，不阻塞 |
| 多线程 batch 性能 | ≥ C++ 单线程版的 150% | Phase 4 | 记录 NRR，不阻塞 |
| Rust core-only 内存峰值 | ≤ C++ 版的 120% | Phase 4 | 记录 NRR，不阻塞 |

### 反例（什么不算成功）

- 仅 cargo test 通过但 pytest 失败 → 不算完成 Phase 2
- 仅开发环境可导入但 wheel 分发失败 → 不算完成 Phase 0
- Rust 单线程比 C++ 慢 >50% → 不算"单线程性能达标"，须在 NRR 中记录根因。**不阻塞项目**（学习价值存在），但不可声称"性能接近 C++"

## 评估节点（S6）

| 节点 | 阶段 | AI 自评（每 Phase 结束时） | 独立模型审查 | 人类裁决（HG） | 放行条件 |
|------|------|--------------------------|------------|---------------|---------|
| E0 | Phase 0 | `maturin build --release` + clean venv 验证通过 | — | HG-1 | wheel 可分发 |
| E1 | Phase 1 | `cargo test` + `cargo fmt --check` + `cargo clippy` 全 PASS，golden fixtures 全部在容差内 | — | HG-1 | 纯 Rust 核心正确 |
| E2 | Phase 2 | `maturin develop --release` + pytest 全 PASS | — | HG-1 | PyO3 绑定可用 |
| E3 | Phase 3 | verify 脚本全 PASS，差异报告（含浮点分布） | ≥1 异后端审查 verify 结果 + 差异报告 | HG-1 | 数值一致性确认 |
| E4 | Phase 4 | benchmark 数据（median+p95）+ NRR 条目草稿 | ≥1 异后端审查 benchmark 方法 + NRR 内容 | HG-1 | 对比报告可信 |
| E5 | Phase 6 | CI 绿勾 + wheel 内容检查（无参考代码）+ 三语 README | — | HG-3 | 闭合 |

## 审查追溯

| 轮次 | 模型 | 角度 | 对象 | 关键发现 |
|------|------|------|------|---------|
| R1 | GPT-5.6-Sol (via Codex CLI) | 完备性审查 | IMPLEMENTATION_PLAN.md | 21 条（6 🔴 + 13 🟡 + 2 🟢），**19/21 已闭合，2 项带责任阶段延期**（#14 测试边界矩阵→Phase 1, #20 版本策略→Phase 6） |
| R2 | DeepSeek-V4-Pro (via Claude Code CLI) | write-claude-md skill 审计 | CLAUDE.md v1（254 行） | 五步协议自审：砍 ~60% 冗余 + 补术语表/避坑指南/合并命令 → v2（~120 行）。**Step 1–4 自审通过，Step 5 待多后端汇总** |
| R3 | GPT-5.6-Sol (via Codex CLI) | 魔鬼代言人 + 跨文件一致性 | 5 份治理文件（CLAUDE.md v2 等） | 22 条（7 🔴 + 14 🟡 + 1 🟢），**7 🔴已全部修正，🟡修正中**。报告：`_review/conclusions/gpt56-framework-compliance-review.md` |
| R4 | Kimi-K2.7-Code (via Kimi Code CLI) | 独立审查（Step 5 第二后端） | CLAUDE.md v3 + project_status.md v3 | 8 条（1 🔴 + 6 🟡 + 1 🟢），**与 R3 零冲突**——收敛 4 项、互补 6 项。报告：`_review/conclusions/kimi_step5_review_report.md` |
| Phase 2 执行 | Kimi-K2.7-Code (via Kimi Code CLI) | PyO3 绑定实现 | `src/lib.rs` + `python/etf_pattern_match_pyo3/__init__.py` + `tests/` | 13/13 pytest PASS |
| Phase 3 执行 | GPT-5.6-Sol (via Codex CLI) | 数值一致性验证 | Rust/Python/C++ 核心与 batch 路径 | 31/31 golden fixtures、51/51 pytest、verify_batch 全 PASS；执行日志：`_review/conclusions/codex_phase3_output.md` |
| Phase 4 执行 | GPT-5.6-Sol (via Codex CLI) | 预登记 benchmark + NRR | 25 个 corpus、3 次正式实验、12 项指标 | 正式结果：`benchmark_20260729_211951.json`；NRR：`docs/NRR-2026-023_cpp_vs_rust_comparison.md`；死亡判据未触发 |
| Phase 5 执行 | GPT-5.6-Sol (via Codex CLI) | Panel 兼容 + FastMCP | Python 可选适配层、MCP 原子工具、真实 mlquant synthetic 链路 | Rust 14/14、完整 pytest 62 PASS + 1 SKIP、Torch Panel 9/9、Ruff 与 verify 全 PASS；日志：`_review/conclusions/codex_phase5_output.md` |

## 本轮完成 (2026-07-29)

- 创建仓库、写入 IMPLEMENTATION_PLAN.md（581 行，6 Phase + 审查附录）
- GPT-5.6-Sol 审查（21 条发现：6 🔴阻塞 + 13 🟡改进 + 2 🟢建议），19 已修正，2 开工时细化
- Kill-test-first 适用性分析：项目本体 = 轻量提醒，NRR 对比实验 = 门 2 预登记
- **框架合规差距分析**：对照 AI 协作框架 v1.6.4 发现 4 项 P0 缺口 + 5 项 P1/P2 缺口
- **全量合规修正 v1**：创建 CLAUDE.md（S1-S10 模板，254 行）+ reference_files.md + DEV_LOG.md + 本文件
- **write-claude-md skill 审计 v2**：按五步协议重写 CLAUDE.md（254→~120 行），补术语表/避坑指南/合并命令，砍可推导/通用惯例/文件详述，版本号指针化
- **Phase 0-1 完成**：Rust/PyO3 项目骨架与 31 个 golden fixtures 就绪；纯 Rust 计算核心通过 Debug/Release、fmt 与 Clippy 验收
- **Phase 2 完成**：PyO3/numpy 绑定与 Python API 兼容层就绪；13/13 pytest PASS；6 个公开符号可导入
- **Phase 3 完成**：31/31 golden fixtures、51/51 pytest、`verify_etf_core.py` 与 `verify_batch.py` 全部通过
- **Phase 4 完成**：25 个 corpus、Criterion、3 次正式 C++/Rust benchmark、12 项指标与 NRR-2026-023 已产出；冻结死亡判据未触发
- **Phase 5 完成**：Panel adapter、FastMCP `match_pattern` tool、包导出与测试就绪；真实 mlquant synthetic Panel 端到端成功，核心无 torch 导入正常

## 发现的问题

- **框架 §2.2 模板 vs write-claude-md skill 目标冲突**：前者把 CLAUDE.md 当项目宪法（人读），后者当 agent 操作指令（删掉→会犯错）。v1 按框架模板写，v2 按 skill 协议重写——agent 操作指令进 CLAUDE.md，人读 metadata 进本文件
- IMPLEMENTATION_PLAN.md 混合 Spec 和 Plan 内容 → v1 提取到 CLAUDE.md → v2 砍回：Spec 级约束留在 CLAUDE.md（架构约束/停止条件/禁止列表），参考级内容（成功标准/评估节点/审查追溯）移入本文件
- **write-claude-md skill 未被 v1 调用**：会话直接写了 CLAUDE.md 而未加载 skill 的五步协议——这是流程失误，已在 v2 纠正

## 已完成

| 类别 | 项目 | 执行者 |
|------|------|--------|
| 设计 | IMPLEMENTATION_PLAN.md（581 行，6 Phase + 审查附录） | DeepSeek-V4-Pro |
| 审查 | GPT-5.6-Sol 完备性审查（21 发现，19 修正，2 开工细化） | GPT-5.6-Sol (via Codex CLI) |
| Spec v1 | CLAUDE.md（框架 S1-S10 模板，254 行） | DeepSeek-V4-Pro |
| Spec v2 | CLAUDE.md（write-claude-md skill 审计，254→~120 行） | DeepSeek-V4-Pro |
| 索引 | reference_files.md | DeepSeek-V4-Pro |
| 日志 | DEV_LOG.md（初始条目 4 条） | DeepSeek-V4-Pro |
| 状态 | project_status.md（v2：+ 成功标准 + 评估节点 + 审查追溯 + 框架合规声明） | DeepSeek-V4-Pro |
| 分析 | Kill-test-first 适用性分析 | DeepSeek-V4-Pro |
| Phase 0 | Rust 1.97.1 工具链、maturin 骨架、31 个 golden fixtures | 项目协作会话 |
| Phase 1 | 纯 Rust 计算核心；31/31 fixtures；Debug/Release 14/14；fmt/clippy clean | Codex |
| Phase 2 | PyO3 绑定；5 函数 + FEATURE_KEYS；13/13 pytest；maturin develop 成功 | Kimi-K2.7-Code |
| Phase 3 | Rust/Python/C++ 数值一致性；31/31 fixtures；51/51 pytest；batch 验证通过 | Codex |
| Phase 4 | 预登记 benchmark；25 个 corpus；3 次实验；12 项指标；NRR-2026-023 | Codex |
| Phase 5 | Panel adapter；FastMCP `match_pattern`；62 PASS + 1 SKIP；真实 mlquant synthetic E2E | Codex |

## 待完成

### 当前阶段待办

- [ ] **Phase 6**：配置 CI 与 wheel 构建/内容检查
- [ ] **Phase 6**：完成三语 README、GitHub 仓库与发布闭合材料

### Phase 0-6

详见 `IMPLEMENTATION_PLAN.md` §四。

## 不做的决定

- 不在原 C++ 仓库里加 Rust 代码（两个仓库独立演进）
- 不实现新的 DTW 变体 / 回测引擎 / 数据获取层
- GPU 加速已开放为 Python 层可选 extra（`[gpu]`，HG-2 批准），不修改 Rust 核心
- 参考实现仅作测试夹具（`tests/fixtures/`），不打包进 runtime wheel
- MCP server 不自动链式调用 ashare-mcp（模型驱动编排）

## 依赖关系

| 项目 | 关系 | 状态 |
|------|------|------|
| [etf-pattern-match-pybind11](https://github.com/redamancy231-create/etf-pattern-match-pybind11) | Golden fixtures 来源 | ✅ 已发布 v1.0.0 |
| [ml-quant-trading](https://github.com/initial-d/ml-quant-trading) | Panel 格式（可选） | PR #42 akshare loader 已合并 |
| [ashare-mcp](https://github.com/CharmYue/ashare-mcp) | MCP 模式参考 | 可用 |

## 阻塞项

- GitHub 仓库未创建（Phase 6）

## 可复现性（S9）

> **状态：Phase 0-5 证据已生成；Phase 6 证据按计划待生成。**

以下项目已有可复现快照或锁定文件；后续阶段继续补充：

| 项目 | 计划 | 产出阶段 |
|------|------|---------|
| C++ 原版 commit hash | 锁定 golden fixtures 来源版本 | Phase 1 前 |
| Golden fixture manifest | 文件列表 + hash + 生成脚本版本和日期 | Phase 1 前 |
| Benchmark corpus | 20 组标准 + 5 组 edge，`benchmarks/corpus/manifest.json` 含来源/hash；corpus 23 为 deterministic fallback | Phase 4（已产出） |
| Rust toolchain 精确版本 | `rust-toolchain.toml` | Phase 0 |
| PyO3/rust-numpy/rayon 精确版本 | `Cargo.lock`（提交到仓库） | Phase 1 |
| 编译选项 | `--release` + MSVC `/O2 /fp:precise` | CI 配置 |
| 随机性声明 | 形态匹配算法确定性计算；benchmark 输入用固定种子（`np.random.seed(42)`） | Phase 4 |
| Wheel 测试矩阵 | Python 3.12 + Windows MSVC ABI | Phase 0 |

## 环境约束

- OS: Windows 11 + Git Bash
- 编译器: MSVC 19.51 (VS 2026 Community) — 已安装
- Python: 3.12.7
- Rust: 1.97.1 (`stable-x86_64-pc-windows-msvc`)
- maturin: >=1.0
- 编码: UTF-8, `PYTHONIOENCODING=utf-8` 前缀

## 下一步

按 `IMPLEMENTATION_PLAN.md` §四进入 Phase 6：配置 CI、构建并检查 wheel 内容、完成三语 README 与 GitHub/发布闭合；随后执行 HG-3 终期总结、项目评估、深度 Retrospect 与外部审阅。

---

*生成模型: DeepSeek-V4-Pro (via Claude Code CLI) · 2026-07-29*
