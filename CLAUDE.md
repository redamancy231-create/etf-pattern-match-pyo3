# CLAUDE.md — etf-pattern-match-pyo3

> Rust/PyO3 重写 ETF 形态匹配计算核心。Spec 约束见本文件，执行顺序见 `IMPLEMENTATION_PLAN.md`。框架合规状态/工具版本/审查追溯见 `project_status.md`。

## 术语表

| 术语 | 含义 | 误用后果 |
|------|------|---------|
| **golden fixtures** | C++ 原版 `etf-pattern-match-pybind11` 的精确输出（JSON），只读基准，**不是** Python 参考实现 | 用 Python 参考当 golden → 同源错误双向通过、测试绿灯但算法错 |
| **Panel** | ml-quant-trading 的 `(dates, stocks, fields, mask)` 四元组。`dates`=日历日 numpy array，`stocks`=股票代码 list，`fields`=`{"open","high","low","close","volume","amount","vwap"}` 各为 `(T, N) tensor`，`mask`=`(T, N) bool tensor`（True=可交易） | 混淆 mask 语义（True=可交易 vs 停牌）→ DTW 窗口在不可交易日上生成候选；混淆交易日计数 vs 日历日索引 → t_idx 映射错误 |
| **golden fixtures** | C++ 原版固定输入的**精确输出文件**（JSON），来源/commit hash 不可变，作为 Rust 实现的数值验收基准。**不是** Python 参考实现代码 | 用 Python 参考当 golden → 同源错误双向通过；文件内容（字节）不可变，但数值验收按容差（`abs+rel`）——两者不矛盾：基准文件锁定，验收允许浮点容差 |
| **HG-0/1/2/3** | AI 协作框架定义的四个 Human Gate：HG-0=启动闸门（Plan+Spec 审查），HG-1=里程碑闸门（每 Phase 完成），HG-2=Spec 变更闸门（改 CLAUDE.md 架构约束/停止条件/禁止列表），HG-3=闭合闸门 | 混淆 HG 编号 → 该走 HG-2 的 Spec 变更走了 HG-1，人未被告知宪法级修改 |
| **API 兼容性** | 函数名/签名/默认值/返回类型与 schema/异常类型/模块常量（`FEATURE_KEYS`）与原版 C++ 模块一致。按锁定的 API manifest 逐项验收 | 仅检查"函数能调用"→ 返回 schema 变化（dict vs tuple）或异常类型不同，下游代码静默出错 |
| **VWAP proxy** | `(O+C+H+L)/4` 替代真实 VWAP——因 akshare 复权后 amount/volume 与 OHLC 不同基准 | 直接用 amount/volume 算 VWAP → 复权不一致 |
| **NRR** | Negative Results Registry — 记录"哪种技术选择在什么场景下不 work"的条目格式 | 把 NRR 写成 benchmark 报告 → 缺少"为什么不 work"的核心信息 |
| **NRR 门 2 预登记** | kill-test-first 协议：跑 benchmark 前冻结指标/方法/成功标准，防事后挑有利指标 | 不预登记 → cherry-pick 有利指标，对比报告不可信 |
| **Sakoe-Chiba band** | DTW 约束窗口宽度 = `max(window, abs(len_x - len_y))`（**C++ 原版兼容定义**——不等长序列的工程扩展。不等同于原始论文的等长序列带状约束），限制累积矩阵搜索范围 | 用 `min(window, max(...))` → 不等长序列下 band 可能小于长度差，终点不可达，golden 输出不兼容 |

## Agent 边界

### 可派

- 在 `src/` 写 Rust 代码，在 `python/` 写 Python 代码，在 `tests/` 写测试
- 运行 `cargo test` / `cargo fmt --check` / `cargo clippy` / `pytest`
- 按 `IMPLEMENTATION_PLAN.md` Phase 顺序执行，允许调整同一 Phase 内的任务顺序
- 追加 `DEV_LOG.md`（每次 Phase 完成或出现偏离计划的情况）

### 禁止

- ❌ 修改 C++ 原版仓库（`etf-pattern-match-pybind11`，路径见 `reference_files.md`）下任何文件——golden fixtures 来源，独立仓库
- ❌ 实现 DTW 变体（DDTW/Soft-DTW/ShapeDTW）
- ⚠️ GPU 加速（CUDA/cupy/wgpu）——**已开放为 Python 层可选 extra**（`[gpu]`）。理由：学习 GPU 编程 + 设计 CPU vs GPU 对照实验。约束：(a) 不修改 Rust 核心，(b) 作为独立 feature gate，`pip install etf-pattern-match-pyo3[gpu]` 启用，(c) GPU 功能缺失时核心功能不受影响，(d) 新增 GPU 代码需附带 CPU vs GPU 对照 benchmark。HG-2 批准：2026-07-29
- ❌ 添加回测引擎、交易信号、数据获取层
- ❌ 将 Python 参考实现代码打包进 runtime wheel（仅限 `tests/fixtures/`）
- ❌ MCP server 自动链式调用 ashare-mcp（模型驱动编排——Claude Code 是编排者）
- ❌ 公开函数中使用 `unwrap()` / `expect()`——用 `Result<T, E>` + 跨 FFI 转 `PyErr`
- ❌ 在 `py.allow_threads()` 闭包内或 rayon worker 线程中访问 `py` handle、创建 Python 对象、调用 `PyErr`
- ❌ 未触发 HG-2 即修改本文件的 Spec 级内容（架构约束/停止条件/禁止列表）

## 环境与命令

- **OS**: Windows 11 + Git Bash，编码 UTF-8
- **Python**: 3.12.7（完整环境约束见 `project_status.md`）
- **Rust**: stable-x86_64-pc-windows-msvc（通过 rustup 安装，Phase 0）

```bash
# 开发安装（在项目根目录）
maturin develop --release

# 构建 wheel + clean venv 验证
python -m venv .venv-test
.venv-test\Scripts\activate
maturin build --release --out dist
pip install dist/*.whl
python -c "from etf_pattern_match_pyo3._core import ..."
deactivate

# Rust 测试
cargo test
cargo fmt --check
cargo clippy

# Python 测试
PYTHONIOENCODING=utf-8 python -m pytest tests/ -v

# 一致性验证（Phase 3）
python verify_etf_core.py
python verify_batch.py

# Benchmark（Phase 4）——仅手动触发，不在 CI 自动跑
python benchmarks/run_benchmark.py
```

## 架构约束

以下为非默认约定，违反会导致构建失败或行为错误：

1. **maturin 布局**: `module-name = "etf_pattern_match_pyo3._core"`, `python-source = "python"`——Rust 扩展编译为 `_core.pyd`，Python 包在 `python/` 目录
2. **numpy 零拷贝借用 + owned 复制**: `PyReadonlyArray1<f64>` 接收输入时零拷贝借用（不额外分配）；为脱离 Python 生命周期和释放 GIL，在输入层立即复制到 owned `Vec<f64>`。非连续数组在提取阶段调 `is_standard_layout()` 检查——不连续则 `.to_owned()` 复制为连续数组或返回 `TypeError`。具体 API（`.as_array()`/`.as_slice()`/`.to_owned()`）按锁定的 `numpy` crate 版本（`numpy>=0.23`）选择
3. **GIL 三层策略**: 输入层（GIL 持有期）提取 numpy → `Vec<f64>` → 计算层 `py.allow_threads(|| {...})` 包裹纯 Rust 计算（rayon worker 不接触 Python C API）→ 输出层主线程创建返回对象。**PyO3 版本锁定**: 在 `Cargo.toml` 中锁定 `pyo3 = "0.23"`（GIL 释放 API 为 `allow_threads`）。若后续升级到 0.26+，需同步将 `allow_threads` 替换为 `detach`，并更新本文件
4. **浮点容差**: 采用 `abs_tol + rel_tol` 双重标准，禁止单一绝对阈值

| 对象 | abs_tol | rel_tol | 阻塞规则 |
|------|---------|---------|---------|
| DTW 距离 | 1e-8 | 1e-12 | 影响 Top-K 窗口选择 → 阻塞发布 |
| 余弦相似度 | 1e-8 | 1e-12 | — |
| 15 维特征/得分 | 1e-6 | 1e-9 | — |
| 排序索引 | 完全一致 | — | Top-K 窗口 ID 必须完全一致（按确定性总排序键） |

**Top-K 确定性排序键**: `(score desc, end_idx asc)`。相同 score 时按窗口结束位置升序打破并列；`abs+rel` 容差内的 near-tie（`|score_a - score_b| <= max(abs_tol, rel_tol * max(|score_a|, |score_b|))`，含边界）视为得分相等，同样适用 `end_idx asc`。NaN 得分窗口排在末尾（不进入 Top-K）。正负零视为相等。此规则在 HG-0 前冻结，Rust 实现使用稳定排序（`sort_by` 非 `sort_unstable_by`）。

**跨编译器浮点差异**: 当两个 score 的差值恰好接近容差边界时，MSVC 和 rustc 可能因运算顺序差异导致一侧判定为 near-tie（走 tie-break）、另一侧判定为显著不同（按 score 排序）。若 Phase 3 验证发现跨编译器 Top-K 不一致：(1) 优先统计 near-tie 数量和得分差值分布；(2) 必要时在 tie-break 前将 score 截断到固定精度（如 `round(score, 10)`）再比较。此策略作为备用方案，默认不启用——先用 golden fixtures 实测差异程度。

5. **编译选项**: Rust `--release`，MSVC `/O2 /fp:precise`（禁用 `/fp:fast`），不允许 FMA 收缩改变计算顺序
6. **Cargo.lock 提交到仓库**（可复现构建）
7. **Panel 兼容为 optional extra**: `pip install etf-pattern-match-pyo3[panel]`，核心不硬依赖 torch/mlquant。`panel_adapter.py` 不 `import mlquant` 在模块顶层
8. **Golden fixtures 来自 C++ 原版**（锁定 commit hash），不是 Python 参考实现。Phase 1 开始前从原版提取为 JSON fixtures

## 停止条件

满足任一条 → 停止当前 Phase，触发 HG-2：

- Golden fixtures 任何一条不匹配 → 阻塞 Phase 3，先定位根因
- maturin wheel 在 clean Windows venv 无法 `pip install` + `import` → 阻塞 Phase 2
- 浮点差异超出容差且根因无法定位 → 阻塞 Phase 3
- 排序索引（Top-K 窗口 ID）不一致 → 阻塞发布
- Phase 0-1 实际耗时 > 预估 2× → 重新评估项目可行性，不自动继续
- 触及范围红线（见 Agent 边界禁止列表）

## 已知坑位

### 来自 pybind11/C++ 原版

- **DTW 双行滚动 prev[0] bug**: swap 后 `prev[0]` 残留旧值致 pj1 取错。修法：每次 swap 后 `prev[0]=INF`。Rust 实现同样须注意——`Vec::swap` 语义不同于 C++ `std::swap`
- **浮点运算顺序差异**: Rust 的 FMA 和 sum reduction 可能与 MSVC `/O2` 产生不同舍入。先测 `--release` 默认行为，如超出容差再尝试 `rustc -C target-feature=-fma`
- **scipy 隐式依赖**: C++ 原版曾因 `scipy.stats.rankdata` 致 CI 失败。本项目用纯 Rust 实现 rank 逻辑——不引入 scipy 依赖

### 来自 Rust/PyO3/Windows

- **Windows maturin 首次构建**: 可能遇 toolchain/Python ABI/链接器问题。若 `maturin build` 在 MSVC toolchain 下持续失败，检查 `rustup default` 是否为 `stable-x86_64-pc-windows-msvc`（非 gnu）。排错时间预算见 `IMPLEMENTATION_PLAN.md` Phase 0
- **非连续 NumPy 数组**: `PyReadonlyArray1<f64>` 对非连续数组的行为取决于 pyo3 numpy 版本——提取阶段显式检查 `.is_standard_layout()`；不连续则 `.to_owned()` 复制（额外分配）或 `.as_slice()` 失败时返回 `TypeError`。**注意**: rust-numpy 没有 `as_contiguous_array()` 方法——这是常见错误 API 名
- **rayon `par_iter()` 在 GIL 下**: `par_iter()` 不会自动释放 GIL。必须手动 `py.allow_threads(|| { ... })`（或锁定 PyO3 版本对应的 `detach` API）包裹。忘记 → 调用线程持续附着 Python 解释器，阻塞其他 Python 线程，且若 worker 回调 Python 可能死锁。注意：纯 Rust rayon worker 本身仍并行——性能退化来自 Python 线程调度受阻，而非 rayon 串行化
- **PyO3 返回 dict 内存**: `PyDict` 在 GIL 外创建 → segfault。确保所有 Python 对象创建在 `allow_threads` 闭包**之后**

### 来自项目特有

- **`reference_files.md` 含"待创建"文件**: 项目在 PLAN 阶段，大部分文件尚不存在。Agent 不要因文件缺失而报错——按 IMPLEMENTATION_PLAN.md 逐 Phase 创建。已创建文件列表以 `git ls-files` 和实际目录为准，`reference_files.md` 仅作为规划索引

## 更新协议

- **改 CLAUDE.md（本文件）**: 仅限于 Spec 级约束变更（架构约束/停止条件/禁止列表增删）→ 触发 HG-2，人确认后修改。不改"最后更新日期"（git log 追踪）
- **改 IMPLEMENTATION_PLAN.md**: Phase 内任务顺序调整无需更新本文件；Phase 的新增/删除/合并 → 追加 DEV_LOG.md
- **每次 Phase 完成**: 追加 `DEV_LOG.md`，更新 `project_status.md` 的"本轮完成"和"下一步"
- **外部审查后**: 审查发现追加到 `project_status.md` 审查追溯表

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **etf-pattern-match-pyo3** (595 symbols, 1037 relationships, 50 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> Index stale? Run `node .gitnexus/run.cjs analyze` from the project root — it auto-selects an available runner. No `.gitnexus/run.cjs` yet? `npx gitnexus analyze` (npm 11 crash → `npm i -g gitnexus`; #1939).

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows. For regression review, compare against the default branch: `detect_changes({scope: "compare", base_ref: "main"})`.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `query({query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `context({name: "symbolName"})`.

## Never Do

- NEVER edit a function, class, or method without first running `impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `rename` which understands the call graph.
- NEVER commit changes without running `detect_changes()` to check affected scope.

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/etf-pattern-match-pyo3/context` | Codebase overview, check index freshness |
| `gitnexus://repo/etf-pattern-match-pyo3/clusters` | All functional areas |
| `gitnexus://repo/etf-pattern-match-pyo3/processes` | All execution flows |
| `gitnexus://repo/etf-pattern-match-pyo3/process/{name}` | Step-by-step execution trace |

## CLI

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->
