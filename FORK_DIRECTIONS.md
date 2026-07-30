# Fork 修改方向

> 本文档为有意 fork 本仓库进行二次开发的维护者提供方向指引。
> 当前版本：v0.1.0 · 2026-07-30

## 设计哲学

理解以下几个设计原则有助于判断某个修改方向是"自然扩展"还是"和上游设计冲突"：

| 原则 | 含义 | 违反后果 |
|------|------|---------|
| **计算核心只做计算** | Rust 核心不碰数据获取、不碰交易信号、不碰回测 | 核心变胖、golden fixture 验证失效 |
| **Python 是编排层** | GPU、MCP、Panel 都在 Python 层，Rust 不知道它们存在 | Rust 核心引入 CUDA 依赖 → 跨平台构建崩溃 |
| **Legacy golden fixtures 是兼容基线** | C++ 原版的精确输出是旧 API、默认参数和 legacy 算法的数值验收基准，不可降级；C++ 不存在的新算法使用独立 oracle | 失去与上游的回归锚点；新算法用自产期望值自证 |
| **GIL 三层策略不可绕过** | 输入提取→`allow_threads` 纯计算→主线程返回对象 | 绕过 → 死锁或 segfault |
| **可选 extra 不污染核心** | `[panel]`/`[gpu]`/`[mcp]` 缺失时核心仍正常工作 | 核心不可导入 |

---

## Fork 后第一步：建立不可变基线

在任何修改之前，先锁定基线。基线失败 → 先修复或记录环境差异，不得把失败与 fork 改动混在同一提交。

```powershell
# 运行前将 $RepoUrl 替换为实际 fork 仓库地址
$RepoUrl = "https://github.com/YOUR_USERNAME/YOUR_FORK.git"
$CheckoutDir = Join-Path $PWD "etf-pattern-match-pyo3-fork"
git clone $RepoUrl $CheckoutDir
Set-Location -LiteralPath $CheckoutDir

git rev-parse HEAD
git status --short

python -m venv .venv
$Python = Join-Path $PWD ".venv\Scripts\python.exe"
$Maturin = Join-Path $PWD ".venv\Scripts\maturin.exe"
& $Python -m pip install --upgrade pip
& $Python -m pip install maturin numpy pytest
& $Maturin develop --release

cargo fmt --all -- --check
cargo clippy --all-targets --all-features -- -D warnings
cargo test --release
& $Python -m pytest tests/ -v
& $Python verify_etf_core.py
& $Python verify_batch.py
```

保存 commit hash、`git status --short`、Python/Rust 版本、操作系统和上述结果。涉及可选 extra 时，按该方向补装依赖并运行对应测试。

---

## Fork 身份与版本策略

在第一次发布前固定以下决策：

- **私有兼容构建**：仅供内部使用且保持 API/schema 兼容，可在私有索引使用 PEP 440 local version，并记录上游基线 commit；
- **公开兼容 fork**：面向公众发布且保持兼容时，使用新的 Python distribution 名和 Rust crate 名，避免与上游制品冲突；
- **破坏性 fork**：改变了默认数值语义或返回 schema 时，必须使用新命名空间或明确主版本迁移，不得沿用 `etf_pattern_match_pyo3` import path；
- 同步更新 `pyproject.toml`、`Cargo.toml`、`Cargo.lock`、README、CI、wheel 内容检查、发布元数据和依赖锁定；
- 每个制品必须暴露 fork 版本、上游 commit 和启用的算法/backend feature，便于结果审计。

---

## 方向分类

| 类别 | 判定标准 | 兼容要求 | 示例 |
|------|---------|---------|------|
| **A 兼容性扩展** | 不改变现有公开 schema 与默认数值路径 | 旧测试和旧 API 全部保持 | Python 分析、纯格式 adapter、严格 API、新增独立 metric |
| **B 版本化 API/算法变更** | 改变候选、评分、特征或结果 schema | 保留 legacy 路径；新入口显式 opt-in | 特征动态化、DDTW、LB_Keogh approximate、多分辨率 |
| **C 构建/运行时重构** | 改 crate 边界、硬件后端、线程或 FFI | 独立 feature/制品/CI，必须有 CPU/native fallback | GPU core、streaming state、全市场扫描、多语言、WASM |
| **D 仓库外上层应用** | 仅消费已发布 API，不修改本仓库 | 固定依赖版本和数据契约 | 回测、告警、Web UI、联网 connector |

每个方向只按其最高风险变更归类；若实现过程中跨类，应拆成前置 issue 和后续 issue。

---

## A 类：兼容性扩展

不改变现有公开 schema 与默认数值路径。旧测试和 API 全部保持。

### A.1 诊断结果 API（可视化与二次排序的共同前置）

**入口文件**：`src/types.rs`、`src/pattern_match.rs`、`src/dtw.rs`、`src/lib.rs`、`python/etf_pattern_match_pyo3/__init__.py`；新增 `python/etf_pattern_match_pyo3/ranking.py`、`analysis.py`

现有 `pattern_match_single` 返回 15 维特征字典，不暴露 Top-K 得分、历史窗口索引或 DTW 对齐路径（`src/lib.rs:91-97` 的 `match_result_to_dict` 只转换 `features` 字段）。A.3 可视化和 A.6 二次排序都依赖此数据。

新增独立的 `pattern_match_diagnostics(...)`，不改变现有 `pattern_match_single` 的返回 schema：
- `features`：现有 15 维结果；
- `top_k`：每项至少包含 `score` 与 `match_end_index`；当 `include_path=True` 时附带 `dtw_path`。

**dtw_path 返回合同**（实现前冻结）：
- 先用现有标量 DTW 完成排序，仅对最终 Top-K 回溯路径（避免全量候选回溯放大内存/时间成本）；
- 路径定义为标准化收益率序列上的 0-based 二元索引对 `[(i, j), ...]`，同时返回或记录到原始价格索引的映射；
- 增加手算小例测试：路径端点、单调性、band 约束和距离重构验证。

路径回溯按需启用，避免默认承担显著的内存与计算成本。验收要求：诊断接口的 `features`、Top-K 分数与索引必须和现有 Rust 路径一致；关闭路径回溯时不得引入明显的默认开销。

### A.2 严格输入校验 API

**入口文件**：`src/lib.rs`、`src/types.rs`、`src/batch.rs`、`python/etf_pattern_match_pyo3/__init__.py`

当前纯 Rust 已具备 `_checked` 版本的严格错误返回（`standardize_returns_checked`、`cosine_similarity_checked`、`dtw_distance_checked`、`compute_features_checked`、`pattern_match_core_checked`），但 Python 包装层主要走兼容入口，batch 还把单项错误压成 `None`（`src/batch.rs:22-23` 的 `.ok().flatten()`），输入错误与"无有效候选"不可区分。

保留现有兼容函数不变，新增独立的 `*_strict` 函数（不修改旧函数签名，符合 A 类约束）：
- `InputError` 统一映射为 Python `ValueError`；
- `None` 只表示输入合法但没有足够的有效候选；
- strict batch 不得用 `.ok().flatten()` 吞掉错误，应返回逐项错误信息或采用 fail-fast 语义，并在实现前固定其一。

**验收要求**：
- 每个 `InputError` 变体至少有一组 Rust 单元测试和一组 Python 绑定测试；
- strict batch 的逐项错误 schema 与 fail-fast 语义在设计定稿前选定，不可两种并存；
- 旧 API 行为不变——引入 `*_strict` 后原有测试全部保持通过。

### A.3 形态特征分析与可视化

**入口文件**：新建 `python/etf_pattern_match_pyo3/analysis.py`；依赖 A.1 诊断结果 API 获取 Top-K 得分和窗口索引

**关键风险**：
- **首要风险**：现有公开 API 不返回 DTW 对齐路径、Top-K 得分或匹配窗口索引——路径图和窗口标注必须先完成 A.1。
- **第二风险**：在获得诊断数据后，IC/rank IC 分析仍需防止多重检验、样本外失效和参数选择过拟合。

### A.4 纯格式数据适配器与本地加载器

**入口文件**：新建 `python/etf_pattern_match_pyo3/adapters/`（内存对象转换）；新建 `python/etf_pattern_match_pyo3/loaders/`（本地文件 I/O）

- **adapters/**：只接收内存对象并纯转换为 `(prices, mask)`，不得发起网络请求或文件 I/O。模式参考 `panel_adapter.py` 的 `_to_numpy_1d` → `_filtered_prices` 链路。测试使用本地 fixture，核心安装不增加数据源 SDK。
- **loaders/**：负责 CSV/Parquet 等本地文件读取（仍不联网），处理路径、编码、schema 推断和 engine 依赖。文件 I/O 异常不应传播到计算核心。

**联网数据连接器（Tushare、Wind、Binance/OKX API、期货连续合约）不属于这两类**——它们涉及凭证、授权、限流、重试、时区、复权和换月规则，应作为 D 类仓库外上层应用或独立 optional distribution。每个 connector 必须记录价格口径、时区、复权方式、缺失值策略和可复现的数据快照标识。

### A.5 特征维度 Python 侧投影

**入口文件**：新建 `python/etf_pattern_match_pyo3/features_ext.py`

如果需求只是选择下游使用的列，优先在 Python 层按 key 投影（Rust 仍输出完整 15 维）。可基于现有 15 维计算衍生特征。若需要 OHLCV 新输入 schema，另行定义上层数据结构，不修改现有价格一维 API。

### A.6 自定义 Top-K 排序与过滤

**入口文件**：`src/types.rs`、`src/pattern_match.rs`、`src/lib.rs`（先暴露 Top-K 诊断数据）；新建 `python/etf_pattern_match_pyo3/ranking.py` 实现行业/市值权重和聚类去重；最后仅在 `__init__.py` 重导出稳定函数

**关键风险**：
- **首要风险**：现有 `pattern_match_single` 返回 15 维字典而不是 `MatchResult`，无法在 Python 侧直接二次排序。必须依赖 A.1 诊断结果 API。
- **第二风险**：候选窗口长度固定为 `L_query`，因此不得宣称可以按 60–120 天候选跨度过滤；如需多跨度候选，应作为独立 B 类算法变更处理。
- 不要在 `__init__.py` 内实现业务逻辑，也不要在 Python 重写 Rust 候选排序。

### A.7 批处理共享收益缓存

**入口文件**：`src/pattern_match.rs` 的 `precomputed_returns` 分支（`:98-106`）、`src/batch.rs`、`src/lib.rs`

源码已预留 `precomputed_returns` 参数——`pattern_match_core_checked` 支持传入预计算的历史窗口收益率缓存，但公共入口 `pattern_match`（`:314-328`）始终传 `None`。`match_batch` 对每个 `t_idx` 独立重跑匹配，重复生成历史窗口收益及标准化结果。

在一次 `pattern_match_batch` 调用内预计算并共享固定长度历史窗口的标准化收益，避免每个 `t_idx` 重复扫描和标准化。第一版只做调用内缓存，不引入跨请求全局状态。**注意**：本方向声称完全等价且不改变 schema，属于 A 类兼容性扩展——若实现过程中发现需要修改返回 schema 或评分语义，应转为独立 B 类 issue。

验收要求：(1) 缓存路径与现有路径的有效掩码、15 维特征、Top-K 得分和窗口索引一致；(2) 记录构建时间、峰值内存和端到端耗时；(3) 明确价格、`L_query` 或标准化规则变化时的失效条件；(4) 若缓存内存随历史长度增长过快，应提供阈值或退回无缓存路径。

---

## B 类：版本化 API/算法变更

改变候选、评分、特征或结果 schema。必须保留 legacy 路径，新入口显式 opt-in。

### B.1 额外距离/相似度度量

**入口文件**：新建 `src/distance.rs`（或各独立模块）作为实现；同时修改 `src/lib.rs` 的模块声明、PyO3 绑定和导出；新增 Rust/Python 测试

当前：余弦预筛选 + DTW 精排。可增加：
- **欧氏距离**（最简单，替换 DTW 做快速对比基线）
- **相关系数距离**（`1 - pearson_r`，适用于趋势形态匹配）
- **曼哈顿距离**（对异常值更鲁棒）
- **DDTW**（Derivative DTW，对形态拐点更敏感，原项目明确禁止的 DTW 变体之一——fork 可以放开）

每种新度量需要：(1) 纯 Rust 实现 + `_checked` 版本；(2) PyO3 绑定（参考 `cosine_similarity_py` 的 GIL 三层模式）；(3) 新算法 oracle fixture 验证（见下方"Fixture 与 oracle 分层"）。

### B.2 用户可配置特征维度

**入口文件**：`src/features.rs`、`src/types.rs`、`src/pattern_match.rs`、`src/lib.rs`、`FEATURE_KEYS`、fixtures、验证脚本和 API 文档

**关键风险与范围**：15 维不是 `features.rs` 的局部常量，而是 `compute_features -> [f64; 15]`、`MatchResult`、PyO3 NumPy shape、`FEATURE_KEYS`、fixtures 和验证脚本共同组成的公共 schema。

若需求只是选择下游使用的列，优先在 Python 层按 key 投影（见 A.5）。若需求是跳过未选特征的计算，应新增版本化 API 和动态结果类型，并明确：
- bit 0–14 与 `FEATURE_KEYS` 的映射及输出顺序；
- bit 15、零掩码和未知位的错误语义；
- 返回 shape 与 keys 的配对方式；
- 对 `types.rs`、`pattern_match.rs`、`lib.rs`、fixtures、验证脚本和 API 文档的迁移方案。

旧 API 必须继续返回固定 15 维。

### B.3 DTW 窗口策略优化

**入口文件**：`src/dtw.rs` 实现 envelope/lower bound；`src/pattern_match.rs` 集成候选剪枝与评分等价性；`src/lib.rs` 暴露显式模式；benchmark 与 Top-K 差分测试作为验证入口

当前 Sakoe-Chiba band 宽度 = `max(window, abs_diff(len_x, len_y))`。可改进：
- **Itakura 平行四边形约束**（更适合不等长序列）
- **自适应窗口**（根据序列波动率动态调整 band 宽度）

**LB_Keogh 下界剪枝**——特殊注意事项：

当前 Top-K 使用候选集合内 min-max 归一化后的 `0.5 * normalized_dtw + 0.5 * normalized_cosine`（`src/pattern_match.rs:214-240`）。LB_Keogh 若改变参与归一化的候选集合，可能改变最终排序，即使其 DTW 下界本身正确。

实现应提供：
- `exact=true` 默认模式：只有在能证明不改变归一化端点和最终 Top-K 时才剪枝；
- `approximate=true` 实验模式：允许候选削减，但必须在 API 和结果元数据中标明近似；
- 与未剪枝路径对比的 Top-K ID、分数、15 维特征差分测试；
- 与当前标准化方式和 Sakoe-Chiba band 一致的 envelope 定义。

在 exact 等价性未证明前，不得替换默认算法或 legacy golden。

### B.4 多分辨率形态匹配

**入口文件**：`src/pattern_match.rs` 的 `pattern_match_core_checked`

思路：先用粗粒度（如周线）快速扫描，锁定候选区域后只在细粒度（日线）跑 DTW。

该方向的性能收益是待验证假设。benchmark 至少报告：候选削减率、端到端 wall time、峰值内存、recall@K、Top-K overlap、最终 15 维特征差异，并按历史长度和 `L_query` 分层。降采样实现还必须定义：时间戳/索引回映射、尾部不完整桶、缺失值、复权跳变和候选边界处理。若 recall@K 或 Top-K overlap 未达到预登记阈值，只能作为显式 approximate 模式。

---

## C 类：构建/运行时重构

改 crate 边界、硬件后端、线程或 FFI。独立 feature/制品/CI，必须有 CPU/native fallback。

### C.1 GPU 原生 DTW（Rust 侧）

> **上游偏离声明**：本方向主动废止 `CLAUDE.md` 中"GPU 仅限 Python optional extra、不得修改 Rust 核心"的约束，属于 fork 专用架构分支，不应作为上游兼容 PR。若目标仍是向上游贡献，请继续扩展 `gpu_adapter.py`，不要执行本方向。

**入口文件**：新建 `src/dtw_gpu.rs`

当前 `[gpu]` extra 只是 Python 层 CuPy 做余弦预筛选。可以在 Rust 侧用 CUDA/wgpu 实现 DTW：
- **CUDA**：通过 `cudarc` crate 直接写 CUDA kernel，DTW 的 anti-diagonal 并行模式天然适合 GPU
- **wgpu**：跨平台后端（含 WebAssembly）；相对 CUDA/CPU 的实际性能取决于硬件、kernel 实现和数据规模，是待验证假设——必须在同输入、同 DTW 语义下比较 wall time、吞吐、峰值内存和 Top-K 一致性

`Cargo.toml` 至少采用以下隔离方式（版本必须在实现时锁定）：

```toml
[dependencies]
cudarc = { version = "<pin>", optional = true }

[features]
default = []
gpu-native = ["dep:cudarc"]
```

Rust GPU 后端必须保持默认关闭，保留 CPU fallback，并在无 CUDA 环境下完成核心 build/test/import。

**关键风险**：
- DTW 的并行粒度细，GPU kernel launch overhead 可能抵消小窗口的收益
- 任何性能结论都必须包含同输入、同算法语义的 CPU 对照
- 若 GPU 路径改变精度或 Top-K，必须使用独立 API 并标明近似语义
- GPU CI 使用已配置的组织级 GitHub-hosted larger runner，或带自定义标签的 self-hosted GPU runner；`runs-on` 必须填写实际配置的 runner 名称/标签，不假定存在标准 GPU 标签
- CI/发布矩阵至少覆盖：默认 CPU-only build；启用 feature 但无可用设备时的可诊断失败或 CPU fallback；受支持的 CUDA toolkit/driver/GPU 组合；GPU 对照 benchmark；GPU wheel 的命名、依赖与分发策略。GPU job 不得成为核心 CPU wheel 的隐式安装前提

### C.2 流式匹配

应拆为两阶段：

**阶段一：精确流式编排**

**入口文件**：新建 `src/streaming.rs`；事件队列、回调和推送放在绑定层或服务层

新增状态对象维护价格、标准化收益和调用内缓存；新 bar 到达后仍调用现有精确匹配，结果必须与离线重算一致。不把 `mpsc::channel` 视为增量算法本身。

**阶段二：实验性增量 DTW**（独立 B 类 issue）

**入口文件**：`src/dtw.rs` 新增增量 DP 状态类型

仅在有明确算法依据后实现。滑窗删除旧点并加入新点会改变 DTW 动态规划的边界条件，旧 DP 状态通常不能直接复用。必须说明窗口滑动时 DP 状态如何更新、是 exact 还是 approximate，并用逐 bar 的离线全量重算做差分 oracle。若改变 DTW 语义或引入 approximate 模式，按 B 类要求保留 legacy 路径并新增独立入口。

第一阶段通过正确性与性能基线后，才能评估第二阶段；第二阶段应作为独立 B 类 issue 单独评审。

### C.3 全市场并行扫描

**入口文件**：新建 `src/screening.rs`；同时修改 `src/lib.rs` 的二维 NumPy 输入绑定、`src/types.rs` 的多资产结果 schema，以及 `src/batch.rs`/Rayon 并行策略

输入：多资产价格矩阵 `(T, N)` → 对每列分别跑形态匹配 → 输出结果。

**并行策略**：不要默认采用双层 `par_iter`。比较"跨资产并行""跨时点并行"和扁平化 `(asset, t_idx)` 任务三种方案，在固定线程数下报告吞吐、尾延迟和峰值内存；实现只选择一个主并行轴，避免过度切分。

**输出语义**：默认返回每个资产自己的 Top-K。当前组合分数是候选集合内局部归一化值（`src/pattern_match.rs:214-240`），不可直接用于跨资产全局排序。若要提供全市场 Top-K，必须先定义基于固定训练期或固定尺度的校准分数，并用跨资产稳定性测试验证；否则 API 名称和文档应明确为 `per_asset_top_k`。

### C.4 多语言绑定

**前置重构**：建立 Cargo workspace，而不是在 `#[pymodule]` 旁继续堆绑定宏。

```
crates/core/          # 纯 Rust 算法与类型；不依赖 pyo3/numpy/napi/jni/uniffi
bindings/python/      # PyO3 + numpy
bindings/node/        # napi-rs
bindings/java/        # JNI
bindings/uniffi/      # Kotlin/Swift（仅在确有需求时）
```

各 wrapper 只依赖 `crates/core`，拥有独立 feature、crate-type、测试、制品名和 CI。一次只选择一种新语言做端到端验证，不把所有 toolchain 放进同一默认构建。当前根 crate 已包含 `cdylib` 与 `rlib`，不得用 `crate-type = ["cdylib"]` 覆盖并删除 `rlib`。

### C.5 WASM 绑定

**入口文件**：依赖 C.4 的 workspace 拆分后，新增 `bindings/wasm/`

先将算法迁入不依赖 PyO3/numpy 的 `crates/core`，再使用 `wasm-bindgen` 显式导出基于 `Float64Array`/`Uint32Array` 的 API，并定义错误对象与结果 schema。第一版按单线程构建；若启用并行，必须单独处理 Web Worker、cross-origin isolation 和 wasm 线程兼容。用浏览器测试验证与 native core 的数值及 Top-K 一致性。

如果不 fork 本项目，则 D 类浏览器工具应调用服务端 API，不应写成"将当前 `pattern_match_core` 直接用 `wasm-pack` 编译"。

---

## D 类：仓库外上层应用

仅消费已发布 API，不修改本仓库。固定依赖版本和数据契约。

### D.1 形态匹配回测系统

**技术栈**：本项目的 `pattern_match_batch` + backtrader/vectorbt

对每个历史时点跑形态匹配 → 用 `avg_future_ret`/`sign_consistency` 等特征做信号 → 回测。

**Batch 输出对齐规则**：`pattern_match_batch` 返回压缩后的 `features_X15` 与原长度 `valid_mask`；第 `j` 行特征对应 `t_indices[nonzero(valid_mask)[j]]`。回测前必须按 mask 回填到原时间轴，禁止把特征矩阵行号直接当作 `t_indices` 行号，并为首尾无效区间增加对齐测试。

**无未来泄漏要求**：`future_end < t_idx`（`src/pattern_match.rs:202-207`）只保证单次计算不读取该时点之后的价格，不等于整个研究无未来泄漏。资产池、参数、阈值、特征选择和标准化统计都必须在训练窗口内冻结，并采用 walk-forward 或严格的训练/验证/测试切分；测试期结果不得反向参与选择。

### D.2 实时形态告警服务

**技术栈**：本项目的 `pattern_match_single` + 行情 connector + scheduler + 通知渠道

定时拉取行情 → `pattern_match_single` → 若匹配到类似历史顶部/底部形态 → 推送。

注意：`mcp_server.py` 只是无状态的形态匹配计算端点（接收调用方传入的价格数组并返回特征），不是实时告警原型。最小可运行告警服务还需要：
- 独立 connector 或 WebSocket 行情输入；
- scheduler/事件循环与断线重连；
- 标的订阅、最新 bar 和时区/交易日状态；
- 告警规则、去重、冷却时间、幂等键和持久化；
- 通知渠道、失败重试、监控与审计日志。

这些组件应位于上层应用；核心包和 MCP 工具继续只做本地计算，不自动链式调用数据源。

### D.3 浏览器端形态探索工具

**技术栈**：

- **方案一（推荐）**：服务端 Python API（HTTP/WebSocket）+ 前端 React。服务端调用本项目已发布的 wheel，不 fork。前提：先完成 A.1 诊断结果 API 以暴露 Top-K 和路径数据。
- **方案二**：Rust → WASM（wasm-pack）+ 前端 React。依赖 C.4 workspace 拆分 + C.5 WASM 绑定。学习导向为主（不追求实时性）。

---

## 跨方向的通用注意事项

### Fixture 与 oracle 分层

1. **legacy compatibility fixtures**：继续以锁定 commit 的 C++ 原版输出为准；旧 API、默认参数和 legacy 算法必须持续通过，**禁止由 fork 重生成或替换**。
2. **new-algorithm oracle fixtures**：用于 C++ 原版不存在的新算法（DDTW、新距离度量、多分辨率等）。来源必须是独立参考实现、可手算小例、权威算法样例或性质/差分测试，并在 fixture 元数据中记录算法版本、参数和生成来源。
3. 新算法不得以"严格超集"为理由替换 legacy golden。若默认语义需要改变，应新增版本化 API/主版本，并同时保留 legacy 回归套件。
4. 性能优化若声称 exact，除数值容差外还必须比较有效性、排序顺序和 Top-K 窗口 ID。

### GIL 三层策略

任何新增 PyO3 函数都必须遵守：
1. **输入层**（GIL 持有）→ `extract_f64_vec` 复制到 `Vec<f64>`
2. **计算层** → `py.allow_threads(|| { ... })` 包裹，闭包内禁止访问 `py` handle
3. **输出层**（GIL 恢复）→ 创建 Python 对象返回

违反→CI 的 `cargo clippy` 不会报错，但运行时死锁/segfault。

### 浮点容差

新增数值计算时，参考 CLAUDE.md 的容差矩阵（`abs_tol + rel_tol` 双重标准）。不同运算类型需要不同容差——DTW 距离比余弦相似度对舍入误差更敏感。

### Benchmark 与性能结论

若 fork 继续沿用本项目的研究治理流程，则性能结论发布前执行 NRR 门 2 预登记。未沿用该流程的 fork，至少应在首次 benchmark 前冻结：
- 数据集/样本划分
- 指标定义
- 硬件与软件环境（含 CPU/GPU 型号、驱动版本、Rust 版本）
- 重复次数与统计方法
- 成功标准和停止条件

保存原始结果；不得在看到结果后修改主要指标或筛选样本而不披露。

---

## 快速决策表

以下是一名熟悉本仓库的开发者的量级估算，不含首次学习工具链时间；"可合并实现"包含 API 文档、回归测试、CI 与兼容性处理，不是承诺工期。

| 目标 | 最小方向（含/不含项） | 验证性原型 | 可合并实现 |
|------|---------|--------:|--------:|
| 学习 Rust/PyO3 | 新增一个简单 metric + checked Rust 函数 + PyO3 wrapper | 4–8h | 1–3d |
| 增加单一纯格式 adapter | 一个内存对象格式转换，不含 I/O 和联网 SDK | 4–12h | 1–2d |
| 基于现有 15 维做图 | 不含 DTW path/Top-K 标注 | 4–12h | 1–3d |
| 暴露诊断数据（A.1） | 不含 path 回溯的诊断 schema + Python wrapper；完整 A.1 另计 path 实现与差分测试 | 4–8h | 1–2d |
| 严格输入校验（A.2） | `*_strict` wrapper + 每类 InputError 的 Rust/Python 测试 | 4–8h | 1–2d |
| 批处理缓存（A.7） | 调用内共享 `precomputed_returns`，含缓存策略、内存阈值与差分验证 | 4–8h | 1–2d |
| exact LB_Keogh | 先证明 Top-K 等价 | 2–5d | 1–3w |
| 多分辨率近似匹配 | 含 recall@K/overlap 评估 | 2–5d | 1–3w |
| GPU 原生 DTW | 单机 benchmark | 1–2w | 3–8w |
| 全市场扫描 | per-asset 输出优先 | 3–7d | 2–6w |
| 单一新语言绑定 | 在 core 拆分之后 | 2–5d | 2–4w |
| 回测研究原型 | 含 mask 对齐与 walk-forward | 2–5d | 2–6w |

实际范围受操作系统、硬件、数据许可、数值一致性、CI 和制品分发要求影响；开始前应把成功标准与停止条件写入 issue/预登记。

---

*生成模型: DeepSeek-V4-Pro (via Claude Code CLI) · 2026-07-30*
*独立审查: GPT-5.6-Sol (via Codex CLI) R1 2026-07-30 + R2 复核 2026-07-30 · 闭合状态以最新复核报告为准*
