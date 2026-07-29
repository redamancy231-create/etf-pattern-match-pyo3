# etf-pattern-match-pyo3 实现计划

> 创建日期：2026-07-29
> 生成模型：DeepSeek-V4-Pro (via Claude Code CLI)
> 状态：MAINTENANCE（Phase 0-6 已完成，含 GPU extra）
> **Spec 文档**: [CLAUDE.md](CLAUDE.md) — Agent 操作约束（非 S1-S10 容器；S1-S10 metadata 见 `project_status.md`）。本文件定义执行顺序和任务拆分，CLAUDE.md 定义跨任务不变的约束。两者互补，不互相替代。
> 关联项目：[etf-pattern-match-pybind11](https://github.com/redamancy231-create/etf-pattern-match-pybind11)（C++ 原版）· [ml-quant-trading](https://github.com/initial-d/ml-quant-trading)（Panel 格式来源）· [ashare-mcp](https://github.com/CharmYue/ashare-mcp)（MCP 模式参考）

---

## 一、项目定位

将 `etf-pattern-match-pybind11` 的 C++/pybind11 计算核心用 **Rust + PyO3** 重写，保持相同 Python API，产出三项交付物：

| 交付物 | 类型 | 优先级 |
|--------|------|--------|
| Rust/PyO3 计算核心 + Python 包 | pip install 可用的库 | P0 |
| C++ vs Rust 量化计算场景对比报告 | NRR 条目 | P1 |
| 可选 MCP server extra | LLM 可直接调用的形态匹配工具 | P2 |

**非目标**（明确排除）：
- 不是交易系统，不含实盘/回测/信号推送
- 不重复实现数据获取层（直接依赖 ashare-mcp 或用户自供数据）
- 不复制 ml-quant 的因子引擎/组合优化/回测
- 不改动原 `etf-pattern-match-pybind11` 仓库

---

## 二、架构设计

### 分层架构

```
┌──────────────────────────────────────────────────┐
│  [P2] MCP Server（可选 extra）                    │
│  match_pattern(symbol, date) → LLM tool          │
│  依赖: ashare-mcp(取数) + 本项目(计算)             │
├──────────────────────────────────────────────────┤
│  Python API 层（maturin 构建的 .pyd）             │
│  pattern_match_single(prices, ...) → 15 维特征    │
│  pattern_match_batch(prices, t_indices, ...)     │
│  可选: pattern_match_single_panel(panel, ...)    │
│        ↑ 接受 ml-quant Panel 格式                │
├──────────────────────────────────────────────────┤
│  Rust/PyO3 核心（本项目主体）                      │
│  ├── dtw.rs            DTW 距离 + Sakoe-Chiba    │
│  ├── cosine.rs         余弦相似度 + 预筛选        │
│  ├── pattern_match.rs  形态匹配引擎 + 15 维特征   │
│  ├── standardize.rs    序列标准化                 │
│  └── batch.rs          批量匹配 + rayon 并行      │
├──────────────────────────────────────────────────┤
│  Rust 原生层（无 Python 依赖，可独立测试）          │
│  ├── 纯 Rust 数据结构（不依赖 numpy/pyo3）        │
│  └── 单元测试（cargo test）                       │
└──────────────────────────────────────────────────┘
```

### 和原 C++ 版的对应关系

| C++ (etf_core.cpp, ~1100行) | Rust (新) |
|---|---|
| `dtw_distance_span()` | `dtw::distance_span()` |
| `cosine_similarity_vec()` | `cosine::similarity()` |
| `standardize_returns_cpp()` | `standardize::returns()` |
| `pattern_match_core()` | `pattern_match::core()` |
| `pattern_match_batch()` | `batch::match_batch()` + rayon |
| `FEATURE_KEYS` 15 维 | 相同的特征顺序和命名 |
| `verify_etf_core.py` | 同名验证脚本，对比对象换成 Rust |

### 关键设计决策

1. **保持相同的 Python API 签名**——让用户可以在 C++ 版和 Rust 版之间无缝切换
2. **浮点容差对齐原版**——采用 `abs_tol + rel_tol` 双重标准（非单一绝对阈值）：
   - DTW 距离：`abs_tol=1e-8, rel_tol=1e-12`（距离数量级变化大）
   - 余弦相似度：`abs_tol=1e-8, rel_tol=1e-12`（值在 [0,1]）
   - 15 维特征/得分：`abs_tol=1e-6, rel_tol=1e-9`
   - 排序索引：更严格的业务门槛——Top-K 窗口 ID 必须完全一致，排名变化阻塞发布
   - 零值附近：以 `abs_tol` 为主判断，避免 `rel_tol` 在分母为零时失效
   - 编译选项：Rust `--release`、MSVC `/O2 /fp:precise`（禁用 `/fp:fast`），明确不允许 FMA 收缩改变计算顺序
   - 任何影响窗口选择、Top-K 或特征含义的差异需先定位根因，再决定修算法、降优化或记录
3. **numpy crate 零拷贝**——`PyReadonlyArray1<f64>` 直接映射 NumPy 数组内存，不额外分配
4. **rayon 做并行**——C++ 版未做多线程批量（fork-modification-directions §2.3），Rust 版借 rayon 天然支持
5. **Panel 兼容为可选特性**——`pattern_match_single_panel()` 作为 feature gate，不强制依赖 ml-quant
6. **maturin 构建**——比手动 setuptools-rust 简单，直接产 wheel

### GIL 与并行策略（审查修正 #4）

PyO3 暴露的函数默认在 GIL 下执行，rayon 的 `par_iter()` 也不会自动释放 GIL。解决分三层：

**输入层（GIL 持有期）**：从 `PyReadonlyArray1<f64>` 提取数据为 Rust owned `Vec<f64>`。这是唯一接触 Python 对象的地方，完成后立即 drop GIL 引用。

**计算层（无 GIL）**：用 `py.allow_threads(|| { ... })` 包裹纯 Rust 计算。内部只操作 owned Rust 类型，不引用任何 Python 对象。rayon worker 线程永远不接触 Python C API。

**输出层（重新获取 GIL）**：将计算结果转为 Python dict/list，仅在主线程创建返回对象。

关键约束：
- 禁止 worker 线程访问 `py` handle、创建 Python 对象或调用 `PyErr`
- 批量输入在进入 rayon 前完成所有数组提取和验证
- rayon 内部 panic 通过 `std::panic::catch_unwind` 捕获。panic payload 归一化为内部 `InternalError`（字符串 payload 保留原文，其他 payload 用固定消息），在 GIL 外边界完成捕获，返回主线程重新附着 Python 后再构造 `PyRuntimeError`。需注意 `UnwindSafe` 边界、`panic=abort` 时无法捕获（须在 CI 中锁定 `panic=unwind`），以及 GIL 外不能构造 `PyErr`
- 非连续 NumPy 数组在提取阶段自动 `as_contiguous_array()` 或返回 `TypeError`
- 区分"输入零拷贝引用"和"内部 owned 数据"——前者不额外分配，后者在 GIL 外独立管理

### 错误处理策略（审查修正 #5）

Rust 内部所有可恢复错误用 `Result<T, E>`，禁止 `unwrap()`/`expect()` 在公开函数中。跨 PyO3 FFI 边界统一转为 `PyErr`，不允许 panic 穿过 Python 边界。

| 场景 | Rust 内部 | Python 异常 | 说明 |
|------|-----------|------------|------|
| 空输入序列 | `Err(InputError::EmptySequence)` | `ValueError` | 含参数名和实际长度 |
| 长度不匹配 | `Err(InputError::LengthMismatch {...})` | `ValueError` | 含两组长度 |
| window=0 | `Err(InputError::InvalidWindow)` | `ValueError` | window 必须 ≥1 |
| NaN/Inf 在输入中 | `Err(InputError::NonFinite)` | `ValueError` | 标出首个非有限值位置 |
| 索引越界 | `Err(InputError::IndexOutOfRange)` | `IndexError` | t_idx + query_len > len |
| 无有效候选 | `Ok(MatchResult::empty())` | 正常返回（空结果） | `matches: []`，非错误 |
| NaN/Inf 在中间计算 | 传播或窗口级跳过 | 正常返回（跳过该窗口） | 不抛异常，结果中标记 |
| 整数溢出 | `Err(InternalError)` | `OverflowError` | debug 构建 panic，release 返回 Err |
| rayon panic | `catch_unwind` | `RuntimeError` | 返回原 panic 消息 |

**错误消息格式**：每个 `PyErr` 携带 `(function_name, param_name, actual_value, expected_constraint)`，方便 LLM 和人类调试。

---

## 三、项目文件结构

```
etf-pattern-match-pyo3/
├── Cargo.toml                     # Rust 项目配置
├── pyproject.toml                 # Python 构建配置（maturin）
├── README.md                      # 简体中文
├── zh-Hant/README.md               # 正體中文
├── en/README.md                    # English
├── LICENSE                        # MIT
├── CLAUDE.md                      # 开发笔记
├── IMPLEMENTATION_PLAN.md         # 本文件
│
├── src/
│   ├── lib.rs                     # PyO3 入口，注册 Python 模块
│   ├── dtw.rs                     # DTW 距离计算 + Sakoe-Chiba band
│   ├── cosine.rs                  # 余弦相似度 + 预筛选
│   ├── pattern_match.rs          # 形态匹配引擎
│   ├── standardize.rs            # 序列标准化
│   ├── batch.rs                  # 批量匹配 + rayon 并行
│   ├── features.rs               # 15 维特征常量和聚合逻辑
│   └── types.rs                  # 共享数据结构
│
├── python/
│   └── etf_pattern_match_pyo3/
│       ├── __init__.py            # Python 包入口，re-export Rust 函数
│       ├── panel_adapter.py       # [可选] Panel 格式适配器
│       ├── mcp_server.py          # [P2] MCP server（可选 extra）
│       └── py.typed               # PEP 561 标记
│
├── tests/
│   ├── test_dtw.py                # DTW 测试（从原版适配）
│   ├── test_pattern_match.py     # 形态匹配测试（从原版适配）
│   ├── test_standardize.py       # 标准化测试
│   ├── test_batch.py             # 批量匹配测试
│   ├── test_consistency.py       # Rust vs Python 参考实现一致性
│   └── conftest.py               # pytest fixtures
│
├── benchmarks/
│   ├── run_benchmark.py           # 基准测试脚本（从原版适配）
│   ├── results/                   # 历史 benchmark JSON
│   └── compare_cpp_rust.py       # C++ vs Rust 对比脚本
│
├── verify_etf_core.py            # Rust vs Python 一致性验证（从原版适配）
├── verify_batch.py               # 批量验证（从原版适配）
│
├── notebooks/
│   └── etf_pattern_matching_demo.ipynb  # 交互演示（从原版适配）
│
├── docs/
│   ├── NRR-2026-023_cpp_vs_rust_comparison.md  # NRR 条目：C++ vs Rust 对比报告
│   └── performance-analysis.md   # 性能分析（Amdahl's Law 等）
│
├── .github/
│   └── workflows/
│       ├── ci.yml                 # Rust + Python 测试
│       └── benchmark.yml          # 性能回归监控
│
└── .gitignore
```

---

## 四、实现阶段

### Phase 0：环境搭建（预计 2-3 小时，含排错缓冲）

| 任务 | 产出 |
|------|------|
| 安装 Rust 工具链（rustup + stable-x86_64-pc-windows-msvc） | `rustc --version` |
| 安装 maturin（`pip install maturin`） | `maturin --version` |
| `maturin init` 创建项目骨架 | `Cargo.toml` + `pyproject.toml` + `src/lib.rs` |
| 配置 maturin 布局：`[tool.maturin]` 中 `module-name = "_core"`, `python-source = "python"` | `pyproject.toml` 配置就绪 |
| 验证：`maturin develop` + `python -c "import etf_pattern_match_pyo3"` | 空模块可导入 |
| 新建 venv 验证 wheel：`maturin build` + `pip install dist/*.whl` → clean venv 导入 | wheel 可分发 |
| 初始化 git + `.gitignore` | git repo 就绪 |

**maturin 配置要点**（审查修正 #11）：
```toml
# pyproject.toml
[build-system]
requires = ["maturin>=1.0"]
build-backend = "maturin"

[tool.maturin]
module-name = "etf_pattern_match_pyo3._core"   # Rust 扩展编译为 _core.pyd
python-source = "python"                         # Python 包在 python/ 目录
features = ["pyo3/extension-module"]
```
导入路径：`python/etf_pattern_match_pyo3/__init__.py` → `from etf_pattern_match_pyo3._core import ...`——避免 Rust 扩展名与 Python 包名冲突。

**阻塞项**：无。Rust 工具链安装参考 [rustup.rs](https://rustup.rs)。Windows 上已有 VS 2026 Community（含 C++ build tools）。

**排错缓冲**：首次 Windows maturin 构建可能遇到 toolchain/Python ABI/链接器问题，预留 1 小时排错。

### Phase 1：Rust 纯计算核心（预计 4-6 小时）

按依赖关系从底向上实现，每完成一个模块立即写 Rust 原生单元测试。

| 顺序 | 模块 | 功能 | 测试 |
|------|------|------|------|
| 1.1 | `types.rs` | 定义共享结构体：`MatchResult`、`ScoredWindow`、`BatchInput`、`InputShape` | — |
| 1.2 | `features.rs` | `FEATURE_KEYS: [&str; 15]`、特征聚合函数、结果排序与 tie-break 规则 | 特征数=15、顺序一致、并列处理（确定性排序键: `(score desc, end_idx asc)`，near-tie 容差内视为相等，NaN 排末尾） |
| 1.3 | `standardize.rs` | `fn standardize_returns(prices: &[f64]) -> Vec<f64>` | 常数序列、NaN/Inf 输入、空序列、零方差 |
| 1.4 | `dtw.rs` | `fn distance_span(x: &[f64], y: &[f64], window: usize) -> f64` | 相同序列→0、对称性、window 截断、不等长、不可达 band |
| 1.5 | `cosine.rs` | `fn similarity(a: &[f64], b: &[f64]) -> f64` | 相同向量→1、正交→0、零向量→0 |
| 1.6 | `pattern_match.rs` | `fn pattern_match_core(...) -> MatchResult`（调用 1.2-1.5，含 15 维特征） | 已知输入→已知输出、边界条件、窗口重叠排除、Top-K tie-break |
| 1.7 | `batch.rs` | `fn match_batch(inputs: &[BatchInput]) -> Vec<Option<MatchResult>>` + rayon | 串行 vs 并行一致、空输入、部分失败隔离 |

**Golden Fixtures 策略（审查修正 #1, #6, #7）**：

在 Phase 1 开始前，先从原 C++ 版生成固定 golden fixtures：
- 从原版 `verify_etf_core.py` 的测试输入提取为 JSON fixtures（短序列、不等长、band 不可达、常数/零向量、NaN、重叠窗口、并列得分）
- 同时保存 C++ 输出的精确二进制/JSON 作为 golden outputs
- 锁定原版 commit hash + 依赖版本
- Python 参考实现作为**只读基准**，不复制进新项目的发布包（仅 tests/fixtures/ 下保留 golden outputs）

Fixtures 覆盖的场景：
- 正常序列（L=19, window=5）
- 不等长序列（L_x=15, L_y=25）
- 常数序列（全 1.0 → 余弦为 1.0）
- 零向量（全 0.0 → 余弦为 0.0）
- NaN 在输入中 → 预期 `ValueError`
- band 不可达（window=1 但最优路径在 band 外）
- 重叠候选窗口（t_idx 间距 < query_len）
- 并列得分（两个窗口得分完全相同或 near-tie → 按确定性排序键 `(score desc, end_idx asc)` 打破。详见 CLAUDE.md 架构约束）

测试分层（审查修正 #7）：
1. Rust core ↔ golden outputs（`cargo test`）
2. PyO3 wrapper ↔ Rust core（Python 调 Rust，结果与 golden 比较）
3. batch serial ↔ batch parallel（`cargo test` + pytest）
4. Rust ↔ C++ 原版（verify 脚本，同输入下比较）

**验收**：`cargo test` 全 PASS，覆盖每个模块的正常/边界/异常路径。所有 golden fixtures 匹配。

**设计细节**：
- DTW 的 Sakoe-Chiba band 宽度 = `max(window, abs(len_x - len_y))`，与原版 C++ `etf_core.cpp:170` 一致（已核实：`std::max(window, static_cast<int>(std::abs(n - m)))`）
- 余弦相似度处理零向量：返回 0.0（而非 NaN）
- 15 维特征的计算公式和顺序严格照搬原版 `pattern_match.py:192-200`
- rayon 使用 `par_iter()` 而非 `par_bridge()`——前者不依赖 Python GIL

### Phase 2：PyO3 绑定 + Python 包（预计 3-4 小时）

| 任务 | 产出 |
|------|------|
| 2.1 `src/lib.rs`：注册 `#[pymodule]`，暴露 6-8 个函数 | Python 可调用的 `.pyd` |
| 2.2 numpy 零拷贝：`PyReadonlyArray1<f64>` 接收输入 | 无额外内存分配 |
| 2.3 返回类型：`PyResult<PyObject>` 返回 dict/list | 与原版 Python API 一致 |
| 2.4 `python/etf_pattern_match_pyo3/__init__.py` | 包入口，re-export + docstring |
| 2.5 `pyproject.toml` + maturin 配置 | `pip install` 可用 |
| 2.6 从原版复制 Python 参考实现到 `tests/reference/`（仓库内但**不在 Python package 源树中**） | 供 verify 脚本对比；wheel 构建时自动排除——maturin 只打包 `python-source = "python"` 目录下的文件 |

**验收**：
- `maturin develop` 成功
- `python -c "from etf_pattern_match_pyo3 import pattern_match_single; help(pattern_match_single)"` 正常
- Python 测试用例可调用 Rust 函数

**API 对照**（和原 C++ 版保持一致，以锁定的 API manifest 为准）：

| C++ 公开函数 | Python 签名 | 备注 |
|-------------|------------|------|
| `dtw_distance()` | `(x, y, window=5) -> float` | 公开名是 `dtw_distance`，`dtw_distance_span` 是内部 helper |
| `dtw_distance_batch()` | `(query, candidates, window=5, top_k=0) -> ndarray 或 (indices, distances)` | top_k>0 时返回 tuple |
| `cosine_similarity()` | `(x, y) -> float` | 公开名是 `cosine_similarity`，`cosine_similarity_vec` 是内部 |
| `standardize_returns()` | `(prices) -> np.ndarray` | — |
| `compute_adx()` | `(high, low, close, period=14) -> np.ndarray` | — |
| `compute_atr()` | `(high, low, close, period=14) -> np.ndarray` | — |
| `pattern_match_single()` | `(prices, t_idx, ...) -> dict 或 None` | 返回 `dict`（匹配成功）或 `None` |
| `pattern_match_batch()` | `(prices, t_indices, ...) -> (features_X15, valid_mask)` | 返回 tuple，非 dict |
| `FEATURE_KEYS` | 模块常量 `tuple[str, ...]`（15 个） | — |

> **API manifest 策略**：Phase 0 前从原版自动导出完整 API manifest（函数名/签名/默认值/返回类型与 schema/异常类型/dtype/shape/模块常量），Rust 实现按 manifest 逐项验收。本表仅列公开函数概要，完整契约以 manifest 文件为准。

### Phase 3：一致性验证（预计 2 小时）

| 任务 | 产出 |
|------|------|
| 3.1 从原版复制 `verify_etf_core.py`，修改对比对象为 Rust | Rust vs Python 参考实现一致性 |
| 3.2 从原版复制 `verify_batch.py`，修改对比对象为 Rust | 批量匹配一致性 |
| 3.3 从原版适配 54 个单元测试（`tests/`） | pytest 全 PASS |
| 3.4 新增浮点差异测试：Rust vs C++ 的 FMA/reduction 差异 | 差异在容差内 |
| 3.5 `benchmarks/run_benchmark.py` 适配 Rust 版 | 基准测试可运行 |

**验收**：
- `python verify_etf_core.py` → ALL PASS
- `python verify_batch.py` → ALL PASS
- `python -m pytest tests/ -v` → 54+ PASS

**关键风险**：Rust 的浮点运算顺序（尤其是 FMA 和 sum reduction）可能与 MSVC C++ 产生微小差异。应对：先在容差内验收，如超出则记录到 `docs/NRR-2026-023_cpp_vs_rust_comparison.md` 的"已知差异"节。

### Phase 4：基准测试 + C++ vs Rust 对比（预计 4-5 小时，含缓冲）

| 任务 | 产出 |
|------|------|
| 4.1 固定 benchmark corpus（20 组不同长度/特征的输入） | 可复现输入文件 |
| 4.2 测三层：Rust core-only → Python wrapper → 端到端 | 三层性能数据 |
| 4.3 C++ 与 Rust 对比：同输入、同线程数、同编译优化级别 | 对比表格（median + p95，非单次计时） |
| 4.4 内存对比（峰值 RSS、分配次数） | 内存报告 |
| 4.5 撰写 NRR 条目 | NRR-2026-023 |

**Benchmark 方法**（审查修正 #15）：
- 固定线程数（单线程 + 多线程两组），CPU 亲和性固定
- 预热 5 次 + 计时 100 次 → 报告 median, p95, min, max
- 明确 Rust `--release` 和 C++ `/O2 /fp:precise` 的编译选项
- 分别测 core-only（无 Python 开销）和端到端（含 Python wrapper）
- 记录版本哈希（rustc/msvc/依赖版本）供复现

**NRR 条目**分四个维度（审查修正 #16）：
1. **性能**（可复现实验）：DTW/匹配/批量的 median+p95，含三层测量和线程配置
2. **兼容性**（可验证）：golden fixtures 通过率、浮点差异分布、API 契约一致性
3. **工程成本**（可观测）：编译时间、二进制大小、代码行数、依赖数
4. **风险与审计**（定性，标注主观性）：unsafe 代码位置及审计结果（非"数量"）、依赖审计、测试覆盖率、DX 定性评价（标注主观）

### Phase 5：Panel 兼容 + MCP Server（P1/P2，独立里程碑）

| 优先级 | 任务 | 产出 |
|--------|------|------|
| P1 | `panel_adapter.py`：接受 ml-quant `Panel`，提取 numpy 数组 | `pattern_match_single_panel(panel, ...)` |
| P1 | `python -c "from mlquant.data import make_panel; from etf_pattern_match_pyo3 import pattern_match_single_panel; ..."` | 端到端链路通 |
| P2 | `mcp_server.py`：FastMCP server，暴露 `match_pattern` tool | `claude mcp add` 可用 |
| P2 | MCP 两步协作验证：Claude Code 先调 ashare-mcp 取数据 → 再调本项目做匹配 | 模型驱动编排链路通 |

> **MCP 架构修正**：MCP server 之间不能直接相互调用。改为模型驱动编排——Claude Code 是编排者，ashare-mcp 和本项目各自提供原子能力。详见上文"MCP server 设计"节。

**Panel 数据契约**（审查修正 #3）：

Panel 适配前需先定义数据契约，避免 mask 语义和 DTW 时间索引冲突：

| 属性 | 含义 | 对 DTW 的影响 |
|------|------|--------------|
| `mask[t, i] = True` | 股票 i 在日期 t **可交易**（非停牌、非涨跌停） | 不可交易日的价格可能为 NaN 或 stale |
| `panel.returns` | 基于 `close` 和 `last_close` 计算的日收益率，masked cells 填 0 | 收益率 0 的日期不能直接用于形态匹配（会扭曲 DTW） |
| 日期轴 | 自然日历日，含非交易日 | DTW 的 L_query 和 T_back 是**交易日计数**，需映射 |

**采用策略**：「保留时间轴，mask 处跳过窗口」——不删除不可交易日（保持索引连续），但在生成候选窗口时，任何窗口包含 masked 日期则跳过该窗口。`t_idx` 为 DataFrame 的整数位置索引（0-based），上游负责将"2024-12-31"映射到正确位置。

```python
# python/etf_pattern_match_pyo3/panel_adapter.py
def panel_to_arrays(panel: "Panel", asset_col: int | str):
    """从 Panel 提取单资产的价格数组。
    
    不硬编码 [:, 0]，按 asset_col 选择列。
    mask 用于候选窗口过滤，不在这里删除日期。
    返回: (prices, mask, symbol_name)
    """
    ...
```

**Panel 兼容作为 Python optional extra**：`pip install etf-pattern-match-pyo3[panel]`，不在核心 Rust 中硬依赖 torch/mlquant。核心导入不触发可选依赖导入。

**MCP server 设计**（修正：不自动链式调用，改为模型驱动编排）：
```python
# python/etf_pattern_match_pyo3/mcp_server.py
from fastmcp import FastMCP

mcp = FastMCP("etf-pattern-match")

@mcp.tool
def match_pattern(
    prices: list[float],        # 标准化后的价格序列（由上游提供）
    t_idx: int,                 # 查询窗口在序列中的位置索引（0-based）
    symbol: str = "",           # 可选：标的名称（用于结果标注）
    top_k: int = 5,
    query_len: int = 20,
    lookback: int = 750,
) -> dict:
    """在历史序列中找出与 t_idx 处窗口形态最相似的 Top-K 历史窗口。
    
    输入 prices 应为标准化后的收益率序列。上游（模型或其他 MCP）负责
    获取原始价格、做标准化、传入本工具。
    设计理由：MCP server 之间不能直接相互调用；应由宿主模型先调
    ashare-mcp 取数据，再调本工具做形态匹配。
    """
    ...
```

**和 ashare-mcp 的协作模式**（模型驱动的两步调用，非 server 间自动链式）：
```
Claude Code 会话:
  1. 用户: "帮我找一下 510050 在 2024-12-31 的形态匹配"
  2. Claude 调 ashare-mcp: get_daily_kline("510050", ...)  → 返回价格序列
  3. Claude 在内部做标准化
  4. Claude 调 etf-pattern-match: match_pattern(prices=..., t_idx=..., symbol="510050")
  5. Claude 解读匹配结果返回给用户
```

这不需要 server 间通信——Claude Code 是编排者，两个 server 各自提供原子能力。

### Phase 6：CI + 文档 + 发布（预计 4-5 小时，含缓冲）

| 任务 | 产出 |
|------|------|
| 6.1 CI 配置（`.github/workflows/ci.yml`）：Windows MSVC + Python 3.12, `cargo fmt --check`, `cargo clippy`, `cargo test`, `maturin build`, pytest | CI 绿勾 |
| 6.2 Python extras 定义（`[project.optional-dependencies]`：panel, mcp, dev） | `pip install ...[...]` 可用 |
| 6.3 三语 README（简中/正体/英） | 含安装/API/示例/benchmark 表/license 声明 |
| 6.4 CLAUDE.md + CHANGELOG.md + CONTRIBUTING.md | 开发笔记 + 版本记录 + 贡献指南 |
| 6.5 从原版适配 Jupyter Notebook（仅用本项目 Rust 后端） | 交互演示可用 |
| 6.6 许可证审查：原版 MIT attribution + 本项目依赖许可证清单 | NOTICE 或 LICENSE 节就位 |
| 6.7 GitHub repo 创建 + 推送 + 原版 README 互链更新 | 第 11 个公开仓库 |

**CI 门禁**（审查修正 #13）：
- 至少覆盖 Windows MSVC + Python 3.12 的 wheel build/install/test
- Rust fmt + clippy + cargo test + pytest + 安装后 smoke test
- benchmark 仅手动触发（共享 runner 噪声高），固定输入和线程数
- 性能回归阈值设为 20%（超过触发告警，不阻塞 PR）

**许可证处理**（审查修正 #17）：
- Python 参考实现仅作测试夹具（`tests/fixtures/`），不打包进 runtime wheel
- 保留原版 MIT copyright notice
- 本项目依赖清单含 numpy、fastmcp（可选）、torch（可选），各自许可证在 NOTICE 中列出

---

## 五、Kill-Test-First 适用性分析

### 项目本身：轻量提醒（不走完整协议）

kill-test-first 的触发判定：

> 「这是 Phase 1 建设前的**新方向决策**，还是**已批准项目内的常规实验**？」

| 维度 | 判断 |
|------|------|
| 是新方向吗？ | 技术上是——新仓库、新语言、新工具链 |
| 有未验证的假设吗？ | **没有**。算法已在 C++ 版验证（DTW 34×、匹配 53×、54 tests），Rust 版目标 = 翻译到相同结果 |
| 有"值不值得做"的疑问吗？ | 已解决。分析文件方向 3 已评估，GitHub 搜索确认无直接竞品 |
| 有被否决的可能吗？ | 不应该。学习 Rust 本身即目标——即使性能打平，学习价值也存在 |

**结论**：仅触发轻量提醒——确认命题可证伪即可。不走完整 8 步门 1 协议。

**可证伪命题**：「Rust/PyO3 可以实现与原 C++/pybind11 版数值一致（容差内）的 DTW + 形态匹配，且 Python API 签名兼容。」

### NRR 条目的对比实验：门 2 预登记（Phase 3 结束时触发）

Phase 4 的 C++ vs Rust 对比报告存在一个风险：**跑完 benchmark 之后挑有利指标报**。kill-test-first 的门 2（预登记冻结）正好防这个。

**触发时机**：Phase 3 完成、Phase 4 开跑前。

**预登记冻结内容**：
- Benchmark 方法——预热次数（5）、计时次数（100）、统计量（median + p95）、线程配置（单线程 + N 线程两组）、CPU 亲和性固定方式
- 对比指标列表——DTW 单次 / 形态匹配单次 / 批量匹配（100 窗口）/ 内存峰值 RSS
- 三层测量——Rust core-only / Python wrapper / 端到端，以及 C++ 同等三层
- 成功标准——预先定义"Rust 更快""打平""C++ 更快"的阈值（建议 10% 为"显著差异"）
- 预期方向——基于 Rust 零成本抽象 + rayon 并行 → 单线程接近 C++、多线程超越
- 死亡判据——如果 Rust 单线程比 C++ 慢 >50% 且无法归因到可修复原因，需记录 NRR 但不阻塞项目

跑完后不管结果如何原样报告，不事后调整指标选择或"发现更有趣的维度"。

**不适用量化策略红线**：本项目不涉及回测、因子 IC 声明、策略收益或实盘信号，kill-test-first 的量化策略红线（`quant-redlines.md`）不触发。

---

## 六、关键风险与缓解（审查修正 #21）

| 风险 | 触发条件 | 影响 | 缓解 | 退出条件 |
|------|---------|------|------|---------|
| Rust FMA/reduction 与 C++ 浮点结果不一致 | 编译优化差异 | 排序变化→NRR 不可比 | `abs+rel` 双容差；先定位根因再决定修/降/记 | 影响 Top-K 窗口选择→阻塞发布 |
| maturin Windows wheel 构建失败 | toolchain/ABI/链接器 | 无法分发 | Phase 0.3 提前验证 clean venv wheel；回退方案暂不启用 setuptools-rust | wheel 无法在 clean venv 安装→阻塞 Phase 2 |
| rayon 并行结果顺序错乱 | 索引映射错误 | 批量结果不可用 | `par_iter().enumerate()` 保持索引；输出按输入顺序 | 顺序不一致→阻塞 Phase 3 |
| 参考实现和 Rust 同源错误 | 都基于错误理解实现 | 测试绿灯但算法错 | golden fixtures 来自 C++ 原版输出；参考代码只读、不复制 | golden 不匹配→阻塞 Phase 3 |
| 依赖升级破坏 | PyO3/numpy/akshare 大版本 | 构建/运行时 break | Cargo.lock + `>=` 下限 + `~=` 上限 | CI 红→调查 |
| 内存峰值超预期 | 大批量输入 + rayon | OOM | benchmark 含内存测量；批量分块策略 | 单次匹配 OOM→降级为串行 |
| 许可证冲突 | 参考实现误打进 wheel | MIT 声明不充分 | CI 检查 wheel 内容；参考代码仅 tests/fixtures | wheel 含未授权文件→阻塞发布 |
| 学习曲线阻塞 | Rust 所有权/生命周期 | 进度严重滞后 | Phase 1 纯 Rust 无 PyO3；时间估算含学习缓冲 | Phase 0-1 超时 2×→重新评估 |

---

## 七、和三个关联项目的接口契约

### 对 etf-pattern-match-pybind11（原 C++ 版）

```
Python API 签名 100% 兼容 → 用户改 import 即可切换后端
verify_etf_core.py 将 Rust 版与 Python 参考实现对比
benchmark 结果可并排比较 C++ vs Rust
```

### 对 ml-quant-trading

```
panel_adapter.py: Panel → numpy → Rust（零拷贝）
不依赖 mlquant 包（可选 feature gate）
如 ml-quant 的 akshare loader 已合并，可直接串联:
  make_panel("akshare", ...) → pattern_match_single_panel(panel, ...)
```

### 对 ashare-mcp

```
MCP server extra 内部依赖 ashare-mcp 取数
不 import ashare-mcp 代码（通过 MCP 协议通信）
用户需在同一 Claude Code 会话同时连接两个 MCP
```

---

## 八、不做的（防止范围蔓延）

- ❌ 实现新的 DTW 变体（DDTW/Soft-DTW/ShapeDTW）→ 留给未来的 fork
- ❌ GPU 加速（CUDA）→ 偏离学习 Rust 的目标
- ❌ 回测引擎 / 交易信号生成 → 不是本项目定位
- ❌ 数据获取层 → ashare-mcp 已覆盖
- ❌ 修改原 `etf-pattern-match-pybind11` → 两个仓库独立演进
- ❌ 多 ETF 截面轮动 / ML Stacking → ml-quant 的领域

---

## 九、NRR 条目产出规划

| 条目 | 触发条件 | 内容 |
|------|---------|------|
| NRR-2026-023 | Phase 4 完成 | C++ vs Rust 量化计算场景实测（性能+DX+安全） |
| （可能） | 浮点差异超容差 | Rust vs C++ 浮点行为差异根因分析 |

---

## 十、关联

- [etf-pattern-match-pybind11](https://github.com/redamancy231-create/etf-pattern-match-pybind11) — C++ 原版
- [ml-quant-trading](https://github.com/initial-d/ml-quant-trading) — Panel 格式来源，回测引擎
- [CharmYue/ashare-mcp](https://github.com/CharmYue/ashare-mcp) — MCP 模式参考，数据获取
- 新项目方向分析（内部文档，不公开发布）
- [fork-modification-directions.md](https://github.com/redamancy231-create/etf-pattern-match-pybind11/blob/master/docs/fork-modification-directions.md) — 原版 §4.1 的 Rust 重写方向

---

## 附录：Codex 审查反馈与修正追踪

> 审查模型：GPT-5.6-Sol (via Codex CLI) · 审查日期：2026-07-29
> 审查报告：`docs/审查报告存档于 `_review/conclusions/``

| # | 严重程度 | 发现摘要 | 修正状态 | 修正位置 |
|---|---------|---------|---------|---------|
| 1 | 🔴阻塞 | API contract 未定义，不能机器核对 | ✅ 已修正 | Phase 1 Golden Fixtures + 结果语义节 |
| 2 | 🔴阻塞 | MCP 链式调用不可行 | ✅ 已修正 | MCP 设计改为模型驱动编排 |
| 3 | 🔴阻塞 | Panel 适配层时序索引未定义 | ✅ 已修正 | Panel 数据契约节 |
| 4 | 🔴阻塞 | PyO3 GIL 与 rayon 生命周期未说明 | ✅ 已修正 | GIL 与并行策略节 |
| 5 | 🔴阻塞 | 错误处理策略未定义 | ✅ 已修正 | 错误处理策略节（含完整映射表） |
| 6 | 🔴阻塞 | 算法保真度缺少 golden fixtures | ✅ 已修正 | Golden Fixtures 策略节 |
| 7 | 🟡改进 | 参考实现复制时机和测试分层 | ✅ 已修正 | 测试分层（四层）+ 只读基准策略 |
| 8 | 🟡改进 | Phase 1 实现顺序循环依赖 | ✅ 已修正 | Phase 1 表重排（features.rs 提前） |
| 9 | 🟡改进 | 时间估算过于乐观 | ✅ 已修正 | 各 Phase 增加学习/排错缓冲列 |
| 10 | 🟡改进 | 浮点容差标准不完整 | ✅ 已修正 | abs+rel 双容差 + 编译选项 + 阻塞规则 |
| 11 | 🟡改进 | maturin 布局配置不明确 | ✅ 已修正 | Phase 0 增加 maturin 配置要点 |
| 12 | 🟡改进 | Python extras 未定义 | ✅ 已修正 | Phase 6 含 extras 定义任务 |
| 13 | 🟡改进 | CI 计划缺失 | ✅ 已修正 | Phase 6 增加 CI 任务 + 门禁定义 |
| 14 | 🟡改进 | 测试覆盖不完整 | ⏳ 开工时补充 | Golden Fixtures 场景列表已写，边界矩阵 Phase 1 展开 |
| 15 | 🟡改进 | Benchmark 方法未定义 | ✅ 已修正 | Phase 4 增加方法描述（预热/统计/编译选项） |
| 16 | 🟡改进 | NRR 维度混杂 | ✅ 已修正 | NRR 拆为四维度（性能/兼容性/工程成本/风险） |
| 17 | 🟡改进 | 许可证归属未处理 | ✅ 已修正 | Phase 6 增加许可证审查任务 |
| 18 | 🟡改进 | MCP 数据契约未定义 | ✅ 已修正 | MCP server 设计节（参数 schema + 数据源说明） |
| 19 | 🟡改进 | 结果语义/防前视未定义 | ✅ 已修正 | 结果语义与防前视节（窗口公式+tie-break） |
| 20 | 🟢建议 | 缺少版本策略和发布清单 | ⏳ 开工 Phase 6 时细化 | CHANGELOG/CONTRIBUTING 已加入 Phase 6 任务 |
| 21 | 🟢建议 | 风险登记不完整 | ✅ 已修正 | 重写风险表（触发条件→影响→缓解→退出条件） |

**未修正项说明**：
- #14（测试边界矩阵）：完整边界条件矩阵需在 Phase 1 开始时根据实际 Rust 类型定义展开。计划已列出覆盖场景清单，开工时逐一映射为具体测试用例。
- #20（版本策略）：SemVer/MSRV/平台矩阵的具体取值需在 Phase 6 发布前根据实际支持的平台确定。任务已加入 Phase 6。

**方法论注**：本附录实现的是闭环审查模式——审查发现→计划修正→追踪表。21 条发现中 19 条已修正入计划正文，2 条标记为开工时细化。计划正文不再包含审查指出的设计缺陷。

---

*生成模型：DeepSeek-V4-Pro (via Claude Code CLI) · 2026-07-29*
*审查修正：GPT-5.6-Sol (via Codex CLI) · 2026-07-29*
