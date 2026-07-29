# NRR 门 2 预登记 — C++ vs Rust 量化计算场景对比

> **冻结日期**: 2026-07-29
> **冻结状态**: 🔒 FROZEN — Phase 4 跑完后不得修改本文件，原样引用
> **触发条件**: Phase 3 完成，Phase 4 开跑前
> **关联 NRR 条目**: NRR-2026-00X（Phase 4 完成后编号）
> **协议依据**: IMPLEMENTATION_PLAN.md §五 kill-test-first 门 2

---

## 1. 实验环境快照

| 组件 | 版本/配置 | 锁定方式 |
|------|----------|---------|
| Rust 编译器 | rustc 1.97.1 (8bab26f4f 2026-07-14) | `rust-toolchain.toml` |
| Cargo | 1.97.1 (c980f4866 2026-06-30) | `rust-toolchain.toml` |
| MSVC | VS 2026 Community 19.51 | Windows SDK |
| C++ 编译选项 | `/O2 /fp:precise` | C++ 原版 CMakeLists.txt |
| Rust 编译选项 | `--release` (`opt-level = 2`, `lto = false`) | `Cargo.toml` [profile.release] |
| Python | 3.12.7 | `.python-version` |
| pyo3 | 0.23.5 | `Cargo.lock` |
| numpy crate | 0.23.0 | `Cargo.lock` |
| rayon | 1.12.0 | `Cargo.lock` |
| ndarray | 0.16.1 | `Cargo.lock` |
| C++ 原版 commit | `7c1269a70f3079b14e25365bd908e6f40f478fc0` | golden fixture manifest |
| CPU | 32 logical cores (x86_64) | — |
| OS | Windows 11 Home China | — |

## 2. Benchmark Corpus

### 2.1 生成方法

20 组固定输入，覆盖以下维度。使用 `np.random.seed(42)` + 确定性生成脚本。每组存为 `benchmarks/corpus/corpus_{i:02d}.npz`，含 `prices` 数组和 `config` 字典。

### 2.2 Corpus 维度覆盖

| 维度 | 取值 | 组数 |
|------|------|------|
| 价格序列长度 | 500, 1000, 2000, 4000 | 各 5 组 |
| 窗口长度 L_query | 19 (短), 60 (长) | 各 10 组 |
| T_idx 分布 | 均匀分布在后 25% 区间 | 每序列 3 个 T_idx |
| 波动率水平 | σ = 0.01 (低), 0.03 (高) | 各 10 组 |

### 2.3 Corpus 清单（冻结）

| 文件 | len(prices) | L_query | σ | 说明 |
|------|------------|---------|---|------|
| corpus_00–04 | 500 | 19 | 0.01 | 短序列 × 短窗口 × 低波动 |
| corpus_05–09 | 1000 | 19 | 0.03 | 中序列 × 短窗口 × 高波动 |
| corpus_10–14 | 2000 | 60 | 0.01 | 长序列 × 长窗口 × 低波动 |
| corpus_15–19 | 4000 | 60 | 0.03 | 超长序列 × 长窗口 × 高波动 |

## 3. Benchmark 方法（冻结）

### 3.1 测量协议

```
预热: 5 次（不计时）
计时: 100 次（独立采样）
统计量: median, p95, min, max（仅报告 median + p95，min/max 作为附录）
```

### 3.2 环境固定

| 配置项 | 目标值 | 方法 | 若不可行的替代 |
|--------|--------|------|--------------|
| CPU 电源计划 | 高性能 | `powercfg /setactive 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c` | 标注"未固定" |
| Turbo Boost | 禁用 | BIOS 或 `powercfg` | 标注"未禁用——含频率缩放噪声" |
| CPU 亲和性 | 固定到 core 0-15（共 16 核） | `start /affinity 0xFFFF` | 标注"未固定亲和性" |
| 后台进程 | 最小化（关闭浏览器/IDE/通知） | 手动 | 标注"未清理" |
| 计时器分辨率 | `time.perf_counter()`（Windows 高精度） | 默认 | — |

**记录要求**：在 NRR 报告中逐项标记"已固定 / 未固定"，未固定的项目说明原因。至少必须固定 **电源计划 + 线程数**。

### 3.3 线程配置

| 配置 | 线程数 | 实现 |
|------|--------|------|
| **单线程** | 1 | `RAYON_NUM_THREADS=1` + C++ 单线程 |
| **多线程** | 16（固定） | `RAYON_NUM_THREADS=16` + C++ 对应 |

> CPU 亲和性：Windows 上通过 `start /affinity` 或 `taskset` 等效工具固定到同一 NUMA 节点。若无法固定亲和性，在报告中标注"未固定——结果含调度噪声"。

### 3.3 三层测量

> **C++ core-only 约束**: C++ 原版的 `dtw_distance_span()` 和 `pattern_match_core()` 是内部 helper 函数，pybind11 扩展模块（`.pyd`）不导出这些符号。且项目 Spec（CLAUDE.md Agent 边界）明确禁止修改 C++ 原版仓库。因此 C++ 侧**无法获得与 Rust 对称的 core-only 层**。

采用以下非对称对比方案：

| 层 | Rust 测量方式 | C++ 测量方式 | 可比性 |
|----|---------------|--------------|--------|
| **Core-only** | `cargo bench --bench core`（纯 Rust 函数，无 PyO3） | **不可得**（内部符号未导出，且不允许修改原版） | — |
| **Wrapper-internal** | 在 PyO3 wrapper 内部计时（`py.allow_threads()` 闭包内，含纯计算不含 FFI） | 在 pybind11 wrapper 内部计时（`py::gil_scoped_release` 块内，含纯计算不含 FFI） | ✅ **核心对比层**——双方均排除 Python FFI 开销 |
| **Python wrapper** | `time.perf_counter()` 包裹 Python 调用（含 numpy→Vec 转换 + GIL 进出） | `time.perf_counter()` 包裹 Python 调用（含 numpy→C++ 转换 + GIL 进出） | ✅ |
| **端到端** | `python -c "import ..."` 加载 + 调用 | 同左 | ✅ |

> Rust core-only 仅作为 Rust 自身的内部对比（wrapper overhead 分析），**不作为 C++ vs Rust 的决策依据**。C++ vs Rust 的性能结论基于 **wrapper-internal** 和 **Python wrapper** 两层。

### 3.4 Rust bench harness

在 `benches/core.rs` 添加 Criterion benchmark target：

```toml
# Cargo.toml 新增
[dev-dependencies]
criterion = "0.5"

[[bench]]
name = "core"
harness = false
```

运行命令：`cargo bench --bench core --release`

### 3.5 计时方式

- Core-only (Rust): `cargo bench --bench core`（Criterion, median + MAD）
- Wrapper-internal: Rust 用 `std::time::Instant` 在 `py.allow_threads()` 闭包内，C++ 用 `std::chrono::high_resolution_clock` 在 `py::gil_scoped_release` 块内
- Python wrapper: `time.perf_counter()`
- 所有计时排除 I/O（corpus 预加载到内存）

### 3.6 实验纪律（冻结）

**Rerun 规则**: 最多进行 **3 次**独立实验（每次完整重跑所有 corpus 和指标），每次实验都完整记录，最终报告取三次 median 的中位数。不得只报告最有利的一次。若某次实验的任一指标 CoV > 10%，在报告中标注"高变异——结论置信度降低"。

**Outlier 规则**: **不剔除任何样本**。100 次计时全部纳入统计。若发现单次耗时超出 p95 的 3×，在附录中标注为"离群候选"（不剔除，只标注）。

**p95 辅助阈值**: p95 不作为独立判据，但若 median 落在"打平"区间而 p95 差异 > 15%（`|Rust_p95 / C++_p95 - 1| > 0.15`），必须在 NRR 的"性能"节中作为**尾部延迟差异**单独讨论，不得忽略。

**变异系数**：对每个指标的 100 次计时计算 CoV = std/mean。若 CoV > 5%，±10% 分类从"显著结论"降级为"倾向性结论"。CoV 在报告中与 median/p95 并列呈现。

## 4. 对比指标列表（冻结）— 12 项

每项均报告 **median + p95 + CoV**（100 次计时）。CoV = std/mean。CoV > 5% 时 ±10% 分类从"显著结论"降级为"倾向性结论"（§3.6）。

| # | 指标 | 测量函数 | 对比层 | 单位 |
|----|------|---------|--------|------|
| 1 | DTW (L=19) | `dtw_distance(x, y, window=5)` | wrapper-internal → Python wrapper | µs/call |
| 2 | DTW (L=60) | `dtw_distance(x, y, window=5)` | wrapper-internal → Python wrapper | µs/call |
| 3 | 余弦相似度 (L=19) | `cosine_similarity(a, b)` | wrapper-internal → Python wrapper | µs/call |
| 4 | 标准化 (L=19) | `standardize_returns(prices)` | wrapper-internal → Python wrapper | µs/call |
| 5 | 形态匹配单次 | `pattern_match_single(prices, T_idx)` | wrapper-internal → Python wrapper → 端到端 | ms/call |
| 6 | 批量匹配 (100 T_idx) | `pattern_match_batch(prices, t_indices)` | wrapper-internal → Python wrapper → 端到端 | ms/100 calls |
| 7 | Wrapper 开销占比 | `(python_wrapper − wrapper_internal) / wrapper_internal` | 对比指标 1-6 各计算 | % |
| 8 | 多线程加速比 | 指标 1-6 的 `single_thread / multi_thread(16)` | — | ratio |
| 9 | 内存峰值 RSS | 形态匹配单次 + 批量匹配 (100 T_idx) | Rust core-only | MB |
| 10 | 编译时间 (clean) | `cargo build --release` / `cmake --build` | — | s |
| 11 | 二进制大小 | `_core.pyd` / `etf_core.pyd` | — | KB |
| 12 | unsafe 代码审计 + 依赖审计 | `grep -rn "unsafe" src/` + `cargo tree` | — | 位置/理由 + 计数/许可证 |

## 5. 额外指标（冻结）

以下指标在 NRR 条目中作为定性讨论，不为定量对比：

| 指标 | 测量方式 |
|------|---------|
| DX 定性评价 | 主观评分（1-5）：构建体验、调试体验、文档质量、错误信息可读性 |
| 测试覆盖率 | `cargo tarpaulin` 行覆盖 + C++ 对应工具的覆盖 |
| 浮点差异分布 | 31 golden fixtures 的逐值差异直方图（Phase 3 已验证容差内全通过） |

## 6. 成功标准与阈值（冻结）

### 6.1 性能阈值

| 判定 | DTW 单线程 | DTW 多线程 | 形态匹配单线程 | 形态匹配多线程 | 批量匹配 |
|------|-----------|-----------|-------------|-------------|---------|
| **Rust 更快** | Rust median < C++ median × 0.90 | Rust median < C++ median × 0.90 | Rust median < C++ median × 0.90 | Rust median < C++ median × 0.90 | Rust median < C++ median × 0.90 |
| **打平** | 0.90 ≤ ratio ≤ 1.10 | 0.90 ≤ ratio ≤ 1.10 | 0.90 ≤ ratio ≤ 1.10 | 0.90 ≤ ratio ≤ 1.10 | 0.90 ≤ ratio ≤ 1.10 |
| **C++ 更快** | Rust median > C++ median × 1.10 | Rust median > C++ median × 1.10 | Rust median > C++ median × 1.10 | Rust median > C++ median × 1.10 | Rust median > C++ median × 1.10 |

> "显著差异"阈值 = 10%。10% 以内的差异视为测量噪声或编译器差异范围内的打平。

### 6.2 内存阈值

| 判定 | 形态匹配单次峰值 | 批量匹配峰值 |
|------|----------------|-------------|
| **Rust 更优** | Rust < C++ × 0.80 | Rust < C++ × 0.80 |
| **打平** | 0.80 ≤ ratio ≤ 1.20 | 0.80 ≤ ratio ≤ 1.20 |
| **C++ 更优** | Rust > C++ × 1.20 | Rust > C++ × 1.20 |

### 6.3 编译产物阈值

| 指标 | 期望 |
|------|------|
| 二进制大小 | Rust < C++ × 1.5（允许 Rust 因 monomorphization 稍大） |
| 编译时间 | Rust < C++ × 2.0（首次编译含依赖下载） |
| 依赖数 | 不做阈值判断（生态不同），仅如实报告 |

## 7. 预期方向（冻结）

基于已知的 Rust/C++ 性能特征：

- **DTW 单线程**：打平到 Rust 稍慢（10% 内）。两者都是编译型语言、同算法、同复杂度
- **余弦/标准化**：打平。纯循环无特殊优化空间
- **形态匹配单线程**：打平到 Rust 稍快。Rust 的零成本抽象可能在候选迭代上略优
- **批量匹配多线程**：Rust 更快（>10%）。rayon 的 work-stealing 优于 C++ 的简单 loop
- **内存峰值**：打平。同算法同数据结构
- **二进制大小**：Rust 更大（monomorphization + 静态链接）
- **编译时间**：Rust 更慢（首次编译含依赖）

## 8. 死亡判据（冻结）

满足任一条 → 记录 NRR，但不阻塞项目：

- Rust 单线程 DTW 比 C++ 慢 > **50%** 且无法归因到可修复原因
- Rust 单线程形态匹配比 C++ 慢 > **50%** 且无法归因到可修复原因
- 任何 golden fixture 在 benchmark corpus 上不匹配

> **注意**: 死亡判据**只记录 NRR，不触发 REDESIGN 或 STOP**。项目本体不纯以性能为目标——学习 Rust 本身即价值。此为 IMPLEMENTATION_PLAN.md §五已记录的决策。

**归因可接受性清单**：

| 归因类型 | 可接受（记录 NRR，不阻塞） | 不可接受（需重新实验或修正方法） |
|----------|--------------------------|--------------------------------|
| 算法实现差异 | ✅ 已定位到具体代码行，差异可解释 | ❌ 仅猜测"编译器优化差异"但未定位 |
| 语言/生态固有差异 | ✅ 有文档或社区共识支持（如 Rust monomorphization） | ❌ 无引用依据的主观推测 |
| 测量环境噪声 | ✅ 已固定电源/亲和性后仍存在，CoV > 5% | ❌ 未固定环境就声称"噪声" |
| 编译器/ABI 差异 | ✅ `cargo rustc -- --emit=asm` 对比汇编后定位 | ❌ 仅说"编译器版本不同"而不做汇编对比 |
| 第三方库差异 | ✅ 已锁定版本，差异有 changelog/issue 支持 | ❌ 未锁定版本、未查证变更 |
| 未知 | ✅ 诚实声明"未定位根因"，在 NRR 中列出排查路径 | ❌ 把"未知"解释为"偶然"并忽略 |

归因若属于"可接受"列 → 记录 NRR 即可。若属于"不可接受"列 → 必须先排除可排查的因素，无法排除后再降级为可接受归因。

## 9. 报告模板（冻结）

Phase 4 跑完后，原样按以下结构输出 NRR 条目。**不得事后增删维度或调整指标选择。**

```markdown
# NRR-2026-00X: C++ (pybind11) vs Rust (PyO3) 量化计算场景对比

## 性能（可复现实验）
（按 §4 指标列表逐项报告 median + p95，含三层测量和线程配置）

## 兼容性（可验证）
（golden fixtures 通过率、浮点差异分布、API 契约一致性）

## 工程成本（可观测）
（编译时间、二进制大小、代码行数、依赖数、unsafe 审计）

## 风险与审计（定性）
（unsafe 代码位置及理由、依赖许可证审计、测试覆盖率、DX 定性评价）

## 与预登记的一致性
（对照本文档 §6-8，逐项标记：符合预期 / 不符合预期-需解释 / 触及死亡判据）
```

## 10. 签署

本文件在 Phase 4 开跑前冻结。Phase 4 完成后，所有对比结论必须引用本文件的阈值定义。

- 冻结日期：2026-07-29
- 冻结者：DeepSeek-V4-Pro (via Claude Code CLI)
- 文件 hash（冻结后立即计算）：`9ce48371a3736aea` → R5 修正后重新冻结（实际 hash `454873aab2db2d92`——此前记录的 `dcb734fd3317570b` 为计算错误，R6 审查发现后已更正）
- Phase 3 基线：51/51 pytest PASS, 31/31 golden fixtures PASS, verify_etf_core.py ALL PASS, verify_batch.py ALL PASS

---

*生成模型: DeepSeek-V4-Pro (via Claude Code CLI) · 2026-07-29*
*🔒 FROZEN — Phase 4 完成后不得修改*
