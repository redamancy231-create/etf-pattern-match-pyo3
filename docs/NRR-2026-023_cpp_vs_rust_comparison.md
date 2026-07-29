# NRR-2026-023: C++ (pybind11) vs Rust (PyO3) 量化计算场景对比

- 预登记：`docs/nrr_gate2_preregistration.md`，冻结 hash `454873aab2db2d92`（`dcb734fd` 为历史计算错误，R6 审查后更正）
- 原始结果：因含本地环境路径，不直接公开推送。SHA-256 `25339709471FDD8D20620A8946CADB4C2CF5FB4E6A5EB51EE6596BFB98691EC5`，可在 GitHub Release asset 中获取或联系维护者
- 执行时间：2026-07-29 20:59–21:19（Asia/Hong_Kong）
- 判定层：C++/Rust 的主结论只使用 wrapper-internal；Python wrapper 与 fresh-process 端到端用于解释 FFI 和用户体验开销

> **corpus 为合成高斯序列，外推需谨慎**。20 组标准 corpus 使用固定种子 `np.random.seed(42)`；5 组 edge corpus 不参与 10% 性能阈值。

## 性能（可复现实验）

### 实验协议与环境

- 3 次独立实验；每项每 corpus 预热 5 次、正式计时 100 次；不剔除 outlier；最终取三次实验 median 的中位数。
- 标准 corpus 20 组，edge corpus 5 组；单次形态匹配在后 25% 区间均匀选择 3 个 `T_idx`，batch 使用 100 个严格递增 `T_idx`。
- `RAYON_NUM_THREADS=1/16`；Windows 高性能电源计划已固定。
- Turbo Boost、CPU affinity 未固定；后台进程未由脚本强制终止，仅在运行期间尽量最小化。因此所有 CoV >5% 的分类均按预登记降级为”倾向性结论”（CoV 5-10%），CoV >10% 明确视为高变异（高变异是倾向性结论的子类，非并列关系）。
- C++ 原仓库固定在 commit `7c1269a70f3079b14e25365bd908e6f40f478fc0`，`etf_core.cpp` SHA-256 为 `db37815c379667159fba4e8b5be7c08b87bfa9eaf48dcc4e8753176f0a05e366`。原版未修改；C++ wrapper-internal 计时来自冻结源文件生成副本，计时点位于 `py::gil_scoped_release` 内。副本的构建配置（`/O2 /fp:precise`、`pybind11` 版本、Python ABI）与原始 `CMakeLists.txt` 保持一致，未引入 benchmark 专用代码路径。
- **判定分类**: 预登记 §6.1 定义了"Rust 更快 / 打平 / C++ 更快"三类。本次 NRR 新增**第四类："不可判定"**——判定条件为双方 median 均低于计时器有效分辨率（~100 ns），无法应用 0.90/1.10 阈值计算 ratio。该分类仅适用于 cosine (L=19)，对应指标在预登记三类空间外显式标注。

### 指标 1–6：单线程

下表格式均为 `median / p95 / CoV`。DTW、cosine、standardize 单位为 µs/call；形态匹配单次与 batch 单位为 ms/call（batch 是 ms/100 calls）。

| 指标 | Rust wrapper-internal | C++ wrapper-internal | Rust/C++ | 预登记判定 | Rust Python wrapper | C++ Python wrapper |
|------|-----------------------|----------------------|----------|------------|---------------------|--------------------|
| DTW L=19 | 0.700 / 0.700 / 7.4% | 2.200 / 2.300 / 7.5% | 0.318 | Rust 更快，倾向性 | 1.100 / 1.200 / 14.1% | 2.900 / 3.203 / 10.3% |
| DTW L=60 | 2.200 / 2.300 / 14.9% | 7.650 / 9.500 / 10.2% | 0.288 | Rust 更快，高变异 | 2.800 / 2.950 / 15.5% | 8.550 / 10.418 / 9.8% |
| cosine L=19 | 0.000 / 0.100 / 136.3% | 0.000 / 0.100 / 170.6% | 不可定义 | 计时分辨率不足 | 0.400 / 0.500 / 11.6% | 0.675 / 0.700 / 8.8% |
| standardize L=19 | 0.200 / 0.200 / 28.2% | 0.300 / 0.300 / 13.9% | 0.667 | Rust 更快，高变异 | 0.550 / 0.600 / 10.0% | 0.900 / 1.000 / 7.5% |
| pattern single | 0.282 / 0.358 / 13.5% | 0.533 / 0.756 / 14.3% | 0.528 | Rust 更快，高变异 | 0.283 / 0.361 / 13.5% | 0.535 / 0.760 / 14.3% |
| batch 100 | 30.875 / 34.520 / 5.5% | 33.569 / 37.831 / 6.3% | 0.920 | 打平，倾向性 | 30.920 / 34.607 / 5.5% | 33.582 / 37.849 / 6.3% |

单线程 batch 的 median 落入打平区间；其 wrapper-internal p95 比值为 `34.520 / 37.831 = 0.912`，差异约 8.8%，未达到预登记要求单独判定尾延迟的 15% 阈值。

cosine 的 wrapper-internal 中位数在两种实现中均量化为 0 ns，p95 均为 100 ns。正式 JSON 的自动汇总因 C++ 分母为 0 写出 `Infinity`、标记“C++ 更快”；该字段是计时器分辨率/汇总逻辑产物，不能作为有效语言性能结论，也不构成预登记 §8 的实质死亡判据。Python wrapper 层虽显示 Rust median 较低，但它混合了 FFI 与 Python 调用成本。

### 指标 1–6：16 线程模式

| 指标 | Rust wrapper-internal | C++ wrapper-internal | Rust/C++ | 预登记判定 | Rust Python wrapper | C++ Python wrapper |
|------|-----------------------|----------------------|----------|------------|---------------------|--------------------|
| DTW L=19 | 0.850 / 1.000 / 10.7% | 2.200 / 2.300 / 9.1% | 0.386 | Rust 更快，高变异 | 1.250 / 1.600 / 8.6% | 2.900 / 3.050 / 11.7% |
| DTW L=60 | 2.850 / 3.200 / 7.9% | 7.400 / 8.008 / 10.0% | 0.385 | Rust 更快，倾向性¹ | 3.600 / 4.058 / 10.0% | 8.100 / 8.865 / 9.8% |
| cosine L=19 | 0.000 / 0.100 / 131.9% | 0.000 / 0.100 / 168.8% | 不可定义 | 计时分辨率不足 | 0.500 / 0.503 / 11.5% | 0.650 / 0.700 / 8.0% |
| standardize L=19 | 0.200 / 0.200 / 25.0% | 0.250 / 0.300 / 18.8% | 0.800 | Rust 更快，高变异 | 0.600 / 0.650 / 7.8% | 0.900 / 1.000 / 7.2% |
| pattern single | 0.297 / 0.402 / 16.4% | 0.553 / 0.754 / 12.4% | 0.537 | Rust 更快，高变异 | 0.299 / 0.405 / 16.4% | 0.556 / 0.760 / 12.4% |
| batch 100 | 5.788 / 6.865 / 10.2% | 33.906 / 41.130 / 5.7% | 0.171 | Rust 更快，高变异 | 5.842 / 6.929 / 10.0% | 33.922 / 41.203 / 5.7% |

> ¹ DTW L=60 多线程 C++ CoV=10.0% 恰好处于"高变异"临界值（预登记规定 CoV>10% 为高变异）；Rust CoV=7.9% 在倾向性区间。报告主表标注"倾向性"略偏宽松——实质是 C++ 侧刚好触及边界、Rust 侧未触及。不影响 ±10% 阈值判定（ratio=0.385，远在"Rust 更快"区间内）。

### 端到端（fresh Python process）

端到端包含 Python 进程启动、import、corpus 加载和一次调用，因此不用于核心语言判定。

| 线程 | 指标 | Rust median / p95 / CoV (ms) | C++ median / p95 / CoV (ms) | Rust/C++ median |
|------|------|-------------------------------|------------------------------|-----------------|
| 1 | pattern single | 129.137 / 138.520 / 3.6% | 134.408 / 155.062 / 7.5% | 0.961 |
| 1 | batch 100 | 180.517 / 194.783 / 3.6% | 190.562 / 223.356 / 6.5% | 0.947 |
| 16 | pattern single | 129.281 / 137.693 / 3.3% | 130.118 / 138.159 / 3.4% | 0.994 |
| 16 | batch 100 | 148.437 / 158.468 / 4.2% | 186.633 / 197.522 / 2.7% | 0.795 |

### 指标 7：Wrapper 开销占比

计算式为 `(Python wrapper - wrapper-internal) / wrapper-internal`。cosine 因内部 median 为 0 无法计算；standardize 等亚微秒指标的比例会被 100 ns 量化显著放大，绝对延迟比百分比更可信。

| 实现/线程 | DTW L19 | DTW L60 | cosine | standardize | pattern single | batch 100 |
|-----------|---------|---------|--------|-------------|----------------|-----------|
| Rust / 1 | 57.1% | 27.3% | N/A | 175.0% | 0.62% | 0.15% |
| C++ / 1 | 31.8% | 11.8% | N/A | 200.0% | 0.37% | 0.04% |
| Rust / 16 | 47.1% | 26.3% | N/A | 200.0% | 0.59% | 0.94% |
| C++ / 16 | 31.8% | 9.5% | N/A | 260.0% | 0.55% | 0.05% |

### 指标 8：单线程/16 线程加速比

| 实现 | DTW L19 内部/Python | DTW L60 内部/Python | cosine 内部/Python | standardize 内部/Python | pattern 内部/Python | batch 内部/Python |
|------|---------------------|---------------------|--------------------|-------------------------|---------------------|-------------------|
| Rust | 0.824 / 0.880 | 0.772 / 0.778 | N/A / 0.800 | 1.000 / 0.917 | 0.948 / 0.948 | **5.334 / 5.292** |
| C++ | 1.000 / 1.000 | 1.034 / 1.056 | N/A / 1.038 | 1.200 / 1.000 | 0.964 / 0.962 | 0.990 / 0.990 |

除 batch 外，原语和单次形态匹配没有并行工作可分，线程模式只改变进程环境，出现小于 1 的“加速比”不应解释为算法并行退化。Rust batch 的 Rayon 路径实现 5.33x wrapper-internal 加速；C++ 原版 batch 在两种线程环境下基本不变。fresh-process 端到端的 batch 加速比为 Rust 1.216x、C++ 1.021x，进程启动和加载成本稀释了核心层收益。

### Rust Criterion core-only

验收提示词中的 `cargo bench --bench core --release` 在 Cargo 1.97.1 上失败，报错为 `unexpected argument '--release'`；`cargo bench` 已隐含 optimized bench profile。随后使用等价命令 `cargo bench --bench core` 成功。Criterion 仅用于 Rust core-only 内部分析，不参与 C++/Rust 主判定。

| Criterion 项 | 95% CI 下界 | 点估计 | 95% CI 上界 |
|--------------|-------------|--------|-------------|
| DTW L19 | 643.47 ns | 652.77 ns | 660.24 ns |
| DTW L60 | 2.189 µs | 2.206 µs | 2.236 µs |
| cosine L19 | 9.927 ns | 9.957 ns | 10.013 ns |
| standardize L19 | 137.80 ns | 138.85 ns | 140.75 ns |
| pattern single | 422.70 µs | 426.75 µs | 428.68 µs |
| batch 100 | 5.241 ms | 5.295 ms | 5.368 ms |

### 离群候选

所有候选均保留在统计中。三次实验合计候选计数如下；端到端层全部为 0。逐 corpus 的候选样本与原始统计保存在正式 JSON 的 `experiments[*]` 中。

| 实现/线程 | wrapper-internal 候选数 | Python wrapper 候选数 | 端到端候选数 |
|-----------|-------------------------|-----------------------|---------------|
| Rust / 1 | 16 | 27 | 0 |
| Rust / 16 | 17 | 23 | 0 |
| C++ / 1 | 16 | 25 | 0 |
| C++ / 16 | 6 | 10 | 0 |

## 兼容性（可验证）

- `cargo test --release`：14/14 PASS。
- `pytest tests -v`：51/51 PASS。
- `verify_etf_core.py`：31/31 golden fixtures PASS，standardize/cosine/DTW/pattern/constants 全部在冻结容差内。
- `verify_batch.py`：全部验收项 PASS；随机 single/batch 对照、边界和错误语义均通过。
- Phase 3 只形成了“全部在容差内”的验证证据，未保存逐值差异直方图，因此本报告不虚构浮点差异分布图。

Edge corpus 工程行为：

| Corpus | Rust | C++ | 说明 |
|--------|------|-----|------|
| 20 常数序列 | OK，single 返回 `None`，batch 0 个有效项 | OK | 一致 |
| 21 近零波动 | OK | OK | 一致 |
| 22 含 NaN | `ValueError: non-finite value at index 99` | OK | **行为不一致**；Rust 主动拒绝非有限值，C++ 原版继续计算 |
| 23 ETF 切片 | OK | OK | 本次不是实时 ETF；见下方偏离说明 |
| 24 上升趋势 | OK | OK | 一致 |

corpus 23 因环境未安装 `akshare`，实际来源为 deterministic fallback，错误原因为 `ModuleNotFoundError: No module named 'akshare'`。因此它不能作为真实 510050.SH 外部有效性证据。所有 edge corpus 均按预登记排除在 10% 阈值外。

## 工程成本（可观测）

### 指标 9：RSS

RSS 由独立 Python worker 进程通过 Windows `GetProcessMemoryInfo` 测量。预登记表把该项写为“Rust core-only”，但实际可行测量是包含 Python runtime 与扩展模块的 wrapper 进程；因此绝对值是进程级 RSS，不是纯 Rust allocator RSS。下表为三次实验中位数。

| 实现/线程 | single 峰值 / 相对 baseline 增量 (MiB) | batch 峰值 / 相对 baseline 增量 (MiB) |
|-----------|------------------------------------------|-----------------------------------------|
| Rust / 1 | 32.527 / 0.348 | 34.574 / 2.277 |
| C++ / 1 | 32.629 / 0.234 | 35.059 / 2.617 |
| Rust / 16 | 32.629 / 0.312 | 38.684 / 6.348 |
| C++ / 16 | 32.551 / 0.137 | 34.914 / 2.570 |

按预登记 ±20% 的**绝对峰值**阈值，single 与 batch 均为打平。Rust 16 线程 batch 的 baseline 增量约为 C++ 的 2.47x，说明 Rayon worker/任务执行带来额外进程增量；但绝对峰值比 C++ 高约 10.8%，仍在打平区间。

### 指标 10：clean 编译时间

| 项目 | median / p95 / CoV | 说明 |
|------|--------------------|------|
| Rust `cargo build --release` | 8.692 / 8.838 s / 0.89% | 隔离空 target；使用本机 Cargo registry/cache，不含网络下载 |
| C++ `cmake --build --config Release` | 5.306 / 5.371 s / 0.68% | 每次使用新 build 目录 |
| C++ configure | 2.493 / 2.497 s / 0.12% | 与 build 分开报告 |

Rust/C++ build-only 比值为 1.64，满足预登记 `<2.0` 期望；若把 C++ configure + build 合并，C++ 约 7.800 s，Rust/C++ 约 1.11。

### 指标 11：二进制大小

| 产物 | 大小 |
|------|------|
| Rust `_core.cp312-win_amd64.pyd` | 485,888 bytes（474.5 KiB） |
| C++ 原版 `etf_core.cp312-win_amd64.pyd` | 249,856 bytes（244.0 KiB） |
| C++ 计时副本 `etf_core_bench.cp312-win_amd64.pyd` | 251,904 bytes（246.0 KiB） |

Rust/原版 C++ 大小比为 1.94，**不满足**预登记 `Rust < C++ ×1.5` 的期望。未进一步做符号剥离、LTO 或 `codegen-units` 调优，因此根因暂记为未定位；不能仅以“编译器差异”解释。

### 代码规模与依赖

- Rust `src/*.rs` 物理行数 1,404（含 `test_support.rs`）；C++ 原版 `src/cpp/etf_core.cpp` 1,082 行。模块拆分、注释和测试支持不同，行数只作维护面观察，不作生产率结论。
- `cargo metadata` 解析到 113 个 package（包含运行时、build、dev/criterion 依赖）；许可证字段无 unknown。
- C++ 直接构建依赖为 Python Development.Module 与 pybind11；本次未生成与 Cargo metadata 同层级的 C++ 传递依赖/许可证清单，因此不做不对称的依赖数优劣判断。

## 风险与审计（定性）

### 指标 12：unsafe 与依赖审计

- 对本项目 `src/` 的文本扫描：`unsafe` 命中 0。
- 该结论只覆盖项目自有 Rust 源码，不代表 PyO3、numpy 或其他依赖内部没有 unsafe。
- `cargo tree` 和 `cargo metadata` 已保存到正式 JSON；113 个 resolved package 的许可证字段均可识别，主要为 MIT/Apache-2.0 兼容组合。
- 本次**没有**运行漏洞数据库型 `cargo audit`，因此不能声称“依赖无已知漏洞”。
- 本次**没有**运行 `cargo tarpaulin` 或 C++ coverage 工具，因此没有可报告的行覆盖率数字。

### DX 主观评分（1–5）

以下评分是本次实现/构建过程的定性观察，不是统计测量。

| 维度 | Rust/PyO3 | C++/pybind11 | 观察 |
|------|-----------|--------------|------|
| 构建体验 | 4 | 3 | maturin/Cargo 一体化较顺；C++ 需 CMake、Python 与 pybind11 路径协同 |
| 调试体验 | 4 | 3 | Rust 类型与边界错误较早暴露；C++ 扩展错误定位更依赖构建日志 |
| 文档质量 | 4 | 4 | 两侧主流生态文档均足够，本项目已有冻结基线和脚本化入口 |
| 错误信息可读性 | 4 | 3 | Cargo/Clippy 提示具体；CMake/MSVC 日志更长且含生成器层信息 |

### 主要风险

1. **短原语计时分辨率**：100 ns 量化导致 cosine 内部中位数为 0，standardize/DTW 的 CoV 也偏高（standardize 在 100 ns 刻度上仅有 2 个有效采样点，CoV 28.2% 很可能高估了真实运行抖动）。后续应在同一计时区间内循环 1,000–10,000 次再除以次数，或使用 Criterion 风格批量采样。**对当前结论的影响**：DTW/standardize 的"Rust 更快"判定受 100 ns 量化噪声影响，应视为**高度倾向性**而非显著结论——即使 median ratio 远超 0.90 阈值，CoV 中可能混入了不可忽略的量化误差。
2. **环境未完全固定**：Turbo、affinity 和后台进程未严格固定，限制了亚微秒指标的置信度。
3. **NaN 契约差异**：Rust 拒绝非有限值而 C++ 继续执行。若目标是逐行为兼容，需要明确是否保留 Rust 的防御性校验，或在 Python 层形成共同契约。
4. **真实数据缺失**：corpus 23 是确定性替代，不支持真实 ETF 外推。
5. **JSON 非有限值**：正式 JSON 的 cosine 自动比值包含 Python JSON 扩展 token `Infinity`；严格 JSON 消费者可能拒绝。原始 median/p95 数据有效，报告将该项明确视为不可判定。

## 与预登记的一致性

| 预登记项 | 状态 | 证据/解释 |
|----------|------|-----------|
| 20 组标准 corpus，固定 seed=42 | 符合 | `benchmarks/corpus/corpus_00.npz`–`corpus_19.npz` 与 `manifest.json` |
| 5 组 edge corpus | 部分偏离 | 20–22、24 按规格；23 因无 akshare 使用 deterministic fallback，不是真实 510050.SH |
| 预热 5、计时 100、3 次实验 | 符合 | 正式 JSON `formal_preregistered_run=true` |
| 不剔除 outlier | 符合 | 候选仅标注，全部纳入统计 |
| 单线程/16 线程 | 符合 | worker 子进程固定 `RAYON_NUM_THREADS=1/16` |
| 高性能电源计划 | 符合 | GUID `8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c` |
| 后台进程最小化 | 部分符合 | 未由脚本强制终止；运行期间仅尽量最小化 |
| Turbo/affinity | 已披露未固定 | 不伪称已固定 |
| C++ 原版只读 | 符合 | 前后 `git status` 均为用户已有的 `M CLAUDE.md`、`?? generate_fixtures.py` |
| wrapper-internal 为主结论 | 符合 | Rust 计时位于 `py.allow_threads()` 内；C++ 使用冻结副本的 GIL release 区内计时 |
| Criterion core-only | 命令偏离、语义符合 | 原命令带 `--release` 被 Cargo 1.97.1 拒绝；等价 `cargo bench --bench core` 成功 |
| 12 项指标 | 符合，含层级说明 | 指标 1–12 均报告；RSS 实际为 wrapper 进程级，修正了预登记“Rust core-only”的层级歧义 |
| CoV >5% 降级 | 符合 | 性能分类均按“倾向性/高变异”标注；cosine 因 0 ns 单独判为不可判定 |
| median 打平且 p95 差异 >15% 单独讨论 | 未触发 | 单线程 batch 是唯一内部 median 打平项，p95 差异约 8.8% |
| DTW/形态匹配单线程死亡判据 | 未触发 | 两项 Rust/C++ ratio 均 <1.0；31/31 golden fixtures 无不匹配 |
| 内存预期打平 | 符合 | 绝对峰值均在 ±20% 内；Rust 16 线程增量偏高已披露 |
| 编译时间 Rust < C++×2 | 符合 | build-only ratio 1.64 |
| 二进制 Rust < C++×1.5 | **不符合预期** | ratio 1.94；未做事后阈值调整 |
| 预期方向 | 部分不符合、需解释 | 见下方「预期方向偏离分析」 |
| 归因可接受性清单 §8 | 符合 | 二进制未达预期按"未知"类处理——诚实声明未定位根因，已列出初步排查方向（LTO/symbol-strip/codegen-units）；不可接受的归因（如"编译器差异"）未被采用 |
| 性能阈值规则 §6.1 | 符合 | 未事后调整 10% 阈值、p95 阈值或内存/编译阈值；cosine "不可判定"为新增第四类，在预登记三类空间外显式声明 |

### 预期方向偏离分析

预登记 §7 预期 DTW 单线程"打平到 Rust 稍慢（10% 内）"、standardize/cosine"打平"、pattern single"打平到 Rust 稍快"。实际 DTW ratio=0.29–0.39（Rust 快 2.6–3.5 倍）、standardize ratio=0.67（Rust 快 50%）、pattern ratio=0.53（Rust 快 47%）。这些偏离远超预登记的"打平"区间，需要解释而非仅记录。

**已排除的因素**：
- 算法差异：Phase 3 已验证 Rust 与 C++ 原版在 31 个 golden fixtures 上数值一致（容差内），算法逻辑相同。
- 编译优化级别：双方均为 release 模式（Rust `--release`/C++ `/O2`）。
- 计时边界不一致：双方 wrapper-internal 均排除了 Python FFI 开销（Rust: `py.allow_threads()` 内，C++: `py::gil_scoped_release` 内）。

**候选根因**（需后续跟踪）：
1. **C++ numpy→std::vector 转换**: C++ pybind11 wrapper 中 `ArrD::unchecked<1>()` 返回的是 numpy 内存视图，但 C++ 原版在这些函数中并未做显式 copy；Rust 侧在进入 `allow_threads()` 前做了 `to_vec()`。如果 C++ 在 GIL release 内反复访问 numpy buffer 触发边界检查或内存屏障，可能导致额外开销。需用 profiler 验证。
2. **C++ `std::vector` vs Rust `Vec` 的分配策略**: C++ 的 `extract_window` 每次创建新的 `std::vector`（堆分配），Rust 的 `Vec::with_capacity` 更激进地预留空间。对短序列高频调用场景，allocator 差异可能放大。
3. **编译器 auto-vectorization 差异**: Rust 1.97.1 的 LLVM 后端与 MSVC 19.51 在循环向量化上的启发式不同。需对比关键循环（`standardize_returns` 的对数/减法/除法循环、`cosine_similarity` 的点积循环）的汇编输出来确认。
4. **C++ 副本编译路径**: benchmark 使用的 C++ 副本可能与原始 `CMakeLists.txt` 有微小的编译选项偏差（如 `/GL` 全程序优化未启用）。需 MD5 对比原始 `.pyd` 和副本 `.pyd` 的二进制内容。

这些偏离不改变 NRR 的核心结论（"Rust 在 DTW/standardize/pattern single 上更快"），但限制了结论的可解释性——目前只能描述"更快"，不能解释"为什么更快"。建议 Phase 6 后增加一次汇编级别 profiling 分析。

### 最终裁决

- **核心性能**：在本次合成 corpus 上，Rust wrapper-internal 对 DTW、standardize、pattern single 显示明显的 median 优势；单线程 batch 打平，16 线程 batch 显著更快。由于大多数核心项 CoV >5%，结论强度统一降级为倾向性；cosine 不可判定。
- **兼容性**：冻结 golden/API 主路径通过，但 NaN edge 行为不一致，需在后续版本明确契约。
- **工程成本**：clean 编译时间满足预期；Rust 二进制大小未满足预登记阈值；依赖/unsafe 审计范围已明确，不夸大为漏洞或覆盖率证明。
- **死亡判据**：冻结预登记 §8 的 DTW 单线程、pattern 单线程、golden fixture 三项均未触发。项目可继续进入后续 Phase，但应保留计时分辨率、NaN 契约和二进制尺寸三个跟踪项。