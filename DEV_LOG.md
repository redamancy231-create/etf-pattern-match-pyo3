# 开发手册：etf-pattern-match-pyo3

> 创建日期: 2026-07-29
> 框架参考: AI 协作项目全生命周期框架 §10
> 当前视图: 时间轴 + 辅助文件树快照；Phase 6 发布文件以路径作为可追溯 FK

---

## 变更时间轴


### 2026-07-29 — Phase 6 CI、文档与发布准备完成

- **涉及文件**：`.github/workflows/ci.yml`、`scripts/check_wheel.py`、`.gitignore`、`pyproject.toml`、三语 README、`CHANGELOG.md`、`CONTRIBUTING.md`、`notebooks/etf_pattern_matching_demo.ipynb`、`LICENSE`、`NOTICE`、`docs/releases/v0.1.0.md`、`project_status.md`、`_review/conclusions/codex_phase6_output.md`
- **CI**：Windows MSVC + Python 3.12，覆盖 fmt、clippy、Rust tests、maturin wheel、wheel 内容门禁、安装、pytest、两个 verify 脚本和 import smoke test
- **发布门禁**：`scripts/check_wheel.py` 禁止 `_reference`、`test_reference`、`fixtures/`、`_review/`，并强制检查 `_core.*.pyd`
- **文档**：完成简体中文、正體中文、English 三语 README，统一 15 个 `FEATURE_KEYS`、31 个 golden fixtures、14 + 62 测试基线及 NRR-2026-023 倾向性性能结论
- **Notebook**：从 C++ 原版结构适配，但移除原仓库与 Python 参考实现导入；算法调用统一走本项目 Rust/PyO3 后端
- **许可证**：新增 MIT `LICENSE` 与 `NOTICE`，记录原版归属及 PyO3、NumPy、rayon、ndarray、FastMCP、PyTorch、maturin 许可证摘要
- **发布准备**：新增 v0.1.0 Release notes 草稿与 tag/push 操作清单；未自动创建 tag、推送或发布 GitHub Release
- **边界**：依据 `CLAUDE.md` 禁止项，未修改 C++ 原版仓库；互链更新留待原版仓库单独审批
- **阶段裁决**：Phase 6 实现完成；全量本地验收结果记录于 Codex 输出日志，后续进入 HG-3 项目闭合

### 2026-07-29 — HG-2 Spec 变更：GPU 加速开放为可选 extra

- **涉及文件**：`CLAUDE.md`（Agent 边界：GPU 从禁止→Python 层可选 extra）, `pyproject.toml`（+`[gpu]` cupy extra）
- **理由**：学习 GPU 编程 + 设计 CPU vs GPU 对照实验（余弦预筛选为首个靶子）
- **约束**：(a) 不修改 Rust 核心，(b) `pip install etf-pattern-match-pyo3[gpu]` 独立启用，(c) GPU 缺失时核心不受影响，(d) 新增 GPU 代码附带 CPU vs GPU 对照 benchmark
- **HG-2 批准**：用户确认，2026-07-29

### 2026-07-29 — Phase 5 Panel 兼容层与 FastMCP Server 完成

- **涉及文件**：`python/etf_pattern_match_pyo3/panel_adapter.py`、`python/etf_pattern_match_pyo3/mcp_server.py`、`python/etf_pattern_match_pyo3/__init__.py`、`tests/test_panel_adapter.py`、`tests/test_mcp_server.py`、`project_status.md`、`_review/conclusions/codex_phase5_output.md`
- **Panel 适配**：运行时不顶层导入 `torch`/`mlquant`，通过 `detach/cpu/numpy` 协议转为连续 `float64`/`bool` NumPy 数组；同时兼容提示词的 `panel.fields["close"]` + list stocks 契约和本地真实 mlquant 的 `panel.close` + NumPy stocks 契约
- **Mask 兼容**：查询点不可交易时直接返回 `None`；优先按冻结策略把不可交易点标为 NaN。当前 Rust `pattern_match` 会在入口全局拒绝任意非有限值，因此仅捕获该特定错误并以线性插值序列重试，保留自然日历索引；其他 `ValueError` 不吞掉
- **MCP Server**：`fastmcp` 仅在 `create_server()` 内延迟导入；注册原子工具 `match_pattern`，只消费调用方提供的价格序列，不直接调用 ashare-mcp；工具逻辑拆为可独立测试的 `_match_pattern_impl()`
- **接口差异处理**：PyO3 绑定的参数名为大写 `T_idx`，MCP 通过位置参数调用避免提示词示例中的小写关键字不匹配；MCP 文案按核心实际行为接收价格序列，由 Rust 内部标准化，不把已标准化收益率误传给价格接口
- **FastMCP 兼容**：本轮 `.venv` 安装并验证 FastMCP 3.4.5；测试优先使用 3.x 公共异步 `list_tools()`，兼容旧版本 `get_tools()`，私有属性仅作末级回退
- **验收结果**：`cargo test --release` 14/14 PASS；既有 pytest 51/51 PASS；完整 pytest 62 PASS + 1 SKIP（`.venv` 未安装 torch）；系统 Python + Torch 的 Panel 测试 9/9 PASS；MCP 测试 3/3 PASS；Ruff PASS；两个 verify 脚本全部 PASS；无 torch 核心导入与 FastMCP 创建均成功
- **真实链路**：使用本地 `mlquant.data.make_panel("synthetic", n_dates=800, n_stocks=3)` 完成 Torch Panel → adapter → Rust core 端到端，返回 15 维结果；未运行 `akshare` 网络数据验收，避免把外部行情源可用性混入本地实现验收
- **阶段裁决**：Phase 5 P1/P2 PASS，可进入 Phase 6 CI、wheel、README 与发布闭合

### 2026-07-29 — Phase 4 Benchmark + C++ vs Rust NRR 完成

- **涉及文件**：`benchmarks/generate_corpus.py`、`benchmarks/build_cpp_benchmark.py`、`benchmarks/run_benchmark.py`、`benches/core.rs`、`src/lib.rs`、`Cargo.toml`、`pyproject.toml`、`benchmarks/corpus/`、`benchmarks/results/benchmark_20260729_211951.json`、`docs/NRR-2026-023_cpp_vs_rust_comparison.md`、`project_status.md`、`_review/conclusions/codex_phase4_output.md`
- **Corpus**：按冻结规格生成 20 组标准合成 corpus + 5 组 edge corpus；seed=42。corpus 23 因未安装 akshare 使用 deterministic fallback，不是真实 510050.SH，并已在 NRR 披露
- **计时设计**：Rust wrapper-internal 计时位于 `py.allow_threads()` 闭包内；C++ 使用冻结 `etf_core.cpp` 的生成副本，在 `py::gil_scoped_release` 内计时；C++ 原仓库未修改
- **正式实验**：3 次独立实验，warmup=5，timed=100，20 个标准 corpus，1/16 线程，fresh-process 端到端与 3 次 clean build 均完成；结果 `formal_preregistered_run=true`，SHA-256 `25339709471FDD8D20620A8946CADB4C2CF5FB4E6A5EB51EE6596BFB98691EC5`
- **主结论**：Rust 在 DTW、standardize、pattern single 的 wrapper-internal median 上更快；batch 单线程打平、16 线程 Rust 更快且约 5.33x 自身加速。多数核心项 CoV >5%，均按预登记降级为倾向性；cosine 因 100 ns 时钟量化导致双方 median=0，判为不可判定
- **工程指标**：Rust clean build 8.692 s，C++ build 5.306 s（另 configure 2.493 s）；Rust/C++ 原版二进制 474.5/244.0 KiB，Rust 比值 1.94，未满足预登记 `<1.5` 期望；项目 `src/` unsafe 文本命中 0，cargo metadata 113 个 package、许可证无 unknown
- **Criterion 偏离**：提示词命令 `cargo bench --bench core --release` 被 Cargo 1.97.1 拒绝；等价 `cargo bench --bench core` 成功。Criterion 只作 Rust core-only 分析，不参与 C++/Rust 主判定
- **兼容性**：cargo test 14/14、pytest 51/51、31/31 golden fixtures、verify_batch 全部通过；edge corpus 22 上 Rust 抛非有限值 `ValueError`，C++ 接受，已记录为契约差异
- **环境限制**：高性能电源计划与线程数已固定；Turbo、CPU affinity 未固定；后台进程未由脚本强制清理。RSS 为独立 Python wrapper 进程级，不是纯 Rust core-only
- **阶段裁决**：Phase 4 完成；冻结 §8 的 DTW/pattern/golden 死亡判据未触发，可按计划进入 Phase 5

### 2026-07-29 — NRR 门 2 预登记 R5 修正 + 重新冻结

- **涉及文件**：`docs/nrr_gate2_preregistration.md`（Kimi R5 审查后 6 项修正，hash `dcb734fd3317570b`）
- **审查模型**: Kimi-K2.7-Code（方法论完备性审查）
- **P0 修正**:
  - C++ core-only 不可行→改为非对称四层对比（Rust core-only + wrapper-internal 作为核心对比层 + Python wrapper + 端到端）
  - Rust bench harness→补充 `benches/core.rs` Criterion target + `cargo bench` 命令
  - Rerun 规则（最多 3 次实验，取中位数 median）+ outlier 规则（不剔除，3×p95 标注）+ p95 辅助阈值（15% 尾部差异必须讨论）+ CoV >5% 降级规则
- **P1 修正**:
  - 环境固定执行细则（电源计划/Turbo/亲和性/后台进程 + 逐项标记"已固定/未固定"）
  - 死亡判据归因可接受性清单（6 类归因×可接受/不可接受两列）
  - 指标从 9 项扩展为 12 项（+wrapper 开销占比 + 多线程加速比），全部指标并列 median + p95 + CoV
- **关联变更**: 依赖 Kimi R5 审查报告

### 2026-07-29 — NRR 门 2 预登记冻结

- **涉及文件**：`docs/nrr_gate2_preregistration.md`（新建，🔒 FROZEN，hash `9ce48371a3736aea`）
- **内容**：benchmark 方法（预热 5 + 计时 100 + median/p95）、20 组 corpus 规格、三层测量、9 项对比指标、性能/内存/编译阈值（10% 显著差异）、预期方向、死亡判据（>50% 记 NRR 不阻塞）、报告模板
- **协议**：Phase 4 跑完后不得修改本文件，原样引用。防事后 cherry-pick

### 2026-07-29 — Phase 3 Rust/Python/C++ 一致性验证完成

- **涉及文件**：`verify_etf_core.py`、`verify_batch.py`、`tests/test_dtw.py`、`tests/test_consistency.py`、`tests/test_golden_pyo3.py`、`src/lib.rs`、`_review/conclusions/codex_phase3_output.md`
- **Golden 验收**：31/31 fixtures 全部通过（standardize 9、cosine 4、DTW 13、pattern_match 4、constants 1）；有效 pattern fixture 均按 `FEATURE_KEYS` 顺序逐项验证 15 维特征
- **交叉验证**：增加独立 Python 标量参考实现，覆盖 standardize/cosine/DTW 随机输入；增加 NumPy/BLAS reduction 与潜在 FMA 顺序差异的双容差测试
- **Batch 验收**：3 个随机 `T_idx` 与 single 一致；边界、空输入、全部无效、单有效输入均通过；本机非门控性能观测为 2.36x
- **兼容性修复**：`pattern_match_batch(match_step=0)` 原先吞掉内部参数错误并返回 `False` 掩码，现于 PyO3 绑定入口显式抛出 `ValueError`
- **工程检查**：`cargo test --release` 14/14 PASS；`cargo fmt --check` PASS；`cargo clippy --release --all-targets -- -D warnings` PASS；`maturin develop --release` PASS；pytest 51/51 PASS（由 13 扩展至 51）
- **阶段裁决**：Phase 3 PASS，可进入 HG-1 审查；Phase 4 前仍需执行 NRR 门 2 预登记冻结

### 2026-07-29 — Phase 2 PyO3 绑定与 E2 验收完成

- **涉及文件**：`src/lib.rs`（重写 PyO3 绑定层）、`python/etf_pattern_match_pyo3/__init__.py`（符号桥接）、`Cargo.toml`（+ `ndarray`）、`tests/test_pyo3_bindings.py`、`tests/test_golden_pyo3.py`、`_review/conclusions/kimi_phase2_output.md`
- **参考基线**：C++ 原版 commit `7c1269a70f3079b14e25365bd908e6f40f478fc0`
- **实现**：在 `src/lib.rs` 中注册 5 个 Python 可见函数（`standardize_returns`、`cosine_similarity`、`dtw_distance`、`pattern_match_single`、`pattern_match_batch`）与 `FEATURE_KEYS` 常量；输入层使用 `PyReadonlyArray1` 零拷贝借用并复制到 owned `Vec`，计算层用 `py.allow_threads()` 释放 GIL，输出层构造 `PyDict`/`PyTuple`/`ndarray`
- **兼容性**：Python 函数名、默认参数、返回 schema（`dict|None`、`(features_X15, valid_mask)`）、`FEATURE_KEYS` tuple 顺序均与 C++ 原版 API manifest 一致
- **Golden 验收**：通过 PyO3 接口复验 standardize 9/9、cosine 4/4、DTW 13/13 全部在容差内通过
- **工程检查**：`cargo test` 14/14 PASS；`cargo test --release` 14/14 PASS；`cargo fmt --check` 无差异；`cargo clippy --all-targets --all-features -- -D warnings` 零警告；`maturin develop --release` 构建成功；pytest 13/13 PASS；6 个公开符号 `from etf_pattern_match_pyo3 import *` 可导入
- **阶段裁决**：Phase 2 PASS，公共代码无 `unwrap()` / `expect()`，待 HG-1 审查；通过后进入 Phase 3 一致性验证

### 2026-07-29 — Phase 1 纯 Rust 核心实现与 E1 验收完成

- **涉及文件**：`src/types.rs`、`src/features.rs`、`src/standardize.rs`、`src/dtw.rs`、`src/cosine.rs`、`src/pattern_match.rs`、`src/batch.rs`、`src/test_support.rs`、`src/lib.rs`、`_review/conclusions/codex_phase1_output.md`
- **参考基线**：C++ 原版 commit `7c1269a70f3079b14e25365bd908e6f40f478fc0`
- **实现**：完成标准化、余弦相似度、带窗口 DTW、15 维特征、单项/批量形态匹配；批量接口使用 Rayon 并保持输入顺序
- **兼容性**：实现 C++ 原版边界语义；Top-K 使用 `(score desc, end_idx asc)` 的确定性排序；公共/运行时代码无 `unwrap()` / `expect()`
- **Golden 验收**：31/31 fixtures 全部覆盖并通过（standardize 9、cosine 4、DTW 13、pattern_match 4、constants 1）
- **工程检查**：`cargo test` 14/14 PASS；`cargo test --release` 14/14 PASS；`cargo fmt --all -- --check` 无差异；`cargo clippy --all-targets --all-features -- -D warnings` 零警告
- **阶段裁决**：Phase 1 PASS，待 HG-1 审查；通过后进入 Phase 2 PyO3 绑定

### 2026-07-29 19:00 — Kimi-K2.7-Code R4 审查 + 逐条修正

- **涉及文件**: `CLAUDE.md`（6 处修正）, `project_status.md`（3 处修正）
- **审查模型**: Kimi-K2.7-Code (via Kimi Code CLI)，独立审查（Step 5 第二后端）
- **发现**: 8 条（1 🔴 + 6 🟡 + 1 🟢），**与 R3 零冲突**——收敛 4 项、互补 6 项
- **🔴修正**: D1-1 project_status.md 状态描述滞后（REDESIGN→已修正，R3 行"逐条修正中"→"已全部修正"）
- **🟡修正**:
  - D2-4 `as_contiguous_array()` API 不存在 → 改为 `.is_standard_layout()` + `.to_owned()`，坑位中标注为常见错误 API 名
  - D2-5 Python 版本悬空引用 → 在 CLAUDE.md 中直接写明 `3.12.7`
  - D2-3 PyO3 版本锁定 → 架构约束 #3 新增 `pyo3 = "0.23"` 锁定 + 0.26+ `detach` 迁移说明
  - D2-2 跨编译器 near-tie 风险 → 新增"跨编译器浮点差异"段，含 score 截断备用策略
  - D2-1 Sakoe-Chiba 术语 → 加"**C++ 原版兼容定义**——不等同于原始论文"说明
  - D3-3 容差边界语义 → near-tie 公式 `<` 改为 `<=`（含边界），project_status.md S5 同步
- **Step 5 汇总裁决**: R3 + R4 零冲突、高互补。R3 抓结构性矛盾（公式错误/路径冲突/状态矛盾），R4 抓技术细节（API 错误/悬空引用/边界语义）。两后端覆盖互补，治理文件可作为 HG-0 GO 决策依据
- **关联变更**: 依赖 R3 审查报告 + R3 修正

### 2026-07-29 18:00 — GPT-5.6-Sol R3 审查 + 逐条修正

- **涉及文件**: `CLAUDE.md`（7 处修正）, `project_status.md`（多处修正）, `reference_files.md`（2 处）, `DEV_LOG.md`（3 处）, `IMPLEMENTATION_PLAN.md`（待修正）, `docs/NEXT_STEPS.md`（待修正）
- **审查模型**: GPT-5.6-Sol (via Codex CLI)，魔鬼代言人 + 跨文件一致性角度
- **发现**: 22 条（7 🔴阻塞 + 14 🟡改进 + 1 🟢建议）
- **🔴阻塞修正**:
  - #1 Sakoe-Chiba band 公式修正：`min(window, max(len_x, len_y))` → `max(window, abs(len_x - len_y))`（与 C++ 原版一致）
  - #2 参考实现位置：计划中的 `python/.../_reference/` → `tests/reference/`（避免打进 wheel）
  - #3 Step 5 状态矛盾：统一为"Step 1–4 已自审，Step 5 进行中"
  - #4 API 兼容性范围：从"签名兼容"扩展到 manifest（函数名/返回 schema/异常/dtype/shape/常量）
  - #21 Top-K 确定性排序键：冻结为 `(score desc, end_idx asc)` + near-tie/NaN/正负零规则
- **🟡改进修正**: #5 审查闭合措辞、#6 CLAUDE.md 角色描述统一、#10 五滥残留清理、#11 术语表扩充（+HG/Panel/golden/API 定义）、#12 框架合规声明落地状态、#13 S5 主指标+性能冲突消解、#14 S6 三层责任矩阵、#15 S9 标记"设计完成证据待生成"、#16 L 档选择理由记录、#17 maturin 命令修正、#18 numpy 零拷贝叙述修正、#19 GIL/rayon 后果描述修正
- **关联变更**: 依赖 R3 审查报告

### 2026-07-29 16:30 — write-claude-md skill 审计：CLAUDE.md v1 → v2

- **涉及文件**: `CLAUDE.md`（254→~120 行，按 skill 模板重写）, `project_status.md`（吸收框架 metadata）
- **原因**: v1 按框架 §2.2 S1-S10 模板写（项目宪法），未加载 write-claude-md skill 的五步协议。v2 按 skill 模板重写：Agent 边界/环境与命令/停止条件/已知坑位/更新协议
- **Step 1 脆弱性测试**: 逐条审计 254 行 → 砍 ~60%（可推导信息/通用惯例/文件详述/空泛建议），保留 agent 删掉会犯错的内容
- **Step 2 五缺**: 补术语表（6 个术语）+ 避坑指南（10 条，分三类）+ 合并命令节
- **Step 3 五滥**: 砍 S2 文件路径表（Glob 可推导）、砍 S5 成功标准/S6 三层分工/S7 重启门槛/S8 风险登记（人读 metadata → project_status.md）、砍 S10 目录结构（Glob 可推导）、砍审查追溯/关联项目/框架合规声明（→ project_status.md）
- **Step 4 实证规则**: 版本号指针化（→ project_status.md 环境约束）、术语显式定义（新增术语表）、去最后更新日期（git log 追踪）
- **Step 5**: 待执行（HG-0 Spec 审查 = 异后端独立审查）
- **教训**: 框架 §2.2 模板和 write-claude-md skill 目标不同——前者是项目宪法（人读），后者是 agent 操作指令（删掉→会犯错）。解法：agent 操作指令进 CLAUDE.md，人读 metadata 进 project_status.md
- **关联变更**: 依赖 2026-07-29_框架合规外壳补全

### 2026-07-29 15:00 — 框架合规外壳补全

- **涉及文件**: `CLAUDE.md`（新建，254 行）, `reference_files.md`（新建）, `DEV_LOG.md`（新建）
- **原因**: 对照 AI 协作框架 v1.6.4 §2.2 S1-S10 全量合规检查，从 IMPLEMENTATION_PLAN.md 提取 Spec 级内容 + 补 S5/S6/S9 缺失组件
- **决策**: 选择全量合规（L 档正式研究），非 pybind11 项目的"够用就好"路线
- **关联变更**: 依赖 2026-07-29_创建仓库与实现计划

### 2026-07-29 14:30 — 框架合规差距分析

- **涉及文件**: 无文件变更（分析阶段）
- **原因**: 在 PLAN 阶段而非开工后做框架对齐检查——设计阶段修正成本远低于返工
- **结论**: 4 项 P0 缺口（无 CLAUDE.md / S5/S6 缺失 / HG-0 未正式触发 / DEV_LOG 缺失）+ 5 项 P1/P2 缺口
- **关联变更**: 依赖 2026-07-29_Codex审查闭合

### 2026-07-29 13:00 — Codex 审查闭合

- **涉及文件**: `IMPLEMENTATION_PLAN.md`（修正 19 处）, `审查报告存档于 `_review/conclusions/``（新建）
- **审查模型**: GPT-5.6-Sol (via Codex CLI)
- **发现**: 21 条（6 🔴阻塞 + 13 🟡改进 + 2 🟢建议）
- **闭合状态**: 19/21 已闭合（修正入计划正文），2 项带责任阶段延期（#14 测试边界矩阵→Phase 1, #20 版本策略→Phase 6）
- **关联变更**: 依赖 2026-07-29_创建仓库与实现计划

### 2026-07-29 12:00 — 创建仓库与实现计划

- **涉及文件**: `IMPLEMENTATION_PLAN.md`（新建，541 行）, `README.md`（新建）, `project_status.md`（新建）
- **原因**: 将 C++/pybind11 的 ETF 形态匹配计算核心用 Rust + PyO3 重写
- **关键决策**:
  - 新仓库（不在原 C++ 仓库加 Rust）
  - Python API 签名 100% 兼容 C++ 版
  - maturin 构建 + numpy 零拷贝 + rayon 并行
  - Panel 兼容为 Python optional extra
  - MCP server 为模型驱动编排（非 server 间链式调用）
  - NRR 对比实验走 kill-test-first 门 2 预登记
- **关联项目**: etf-pattern-match-pybind11（golden fixtures）+ ml-quant-trading（Panel）+ ashare-mcp（MCP 模式参考）

---

## 项目文件树地图

```
etf-pattern-match-pyo3/
├── CLAUDE.md              ← [7/29 框架合规补全]
├── IMPLEMENTATION_PLAN.md ← [7/29 创建] [7/29 Codex审查修正×19]
├── project_status.md      ← [7/29 创建]
├── DEV_LOG.md             ← [7/29 框架合规补全]
├── reference_files.md     ← [7/29 框架合规补全]
├── README.md              ← [7/29 创建]
├── docs/
│   ├── codex_review_prompt.md  ← [7/29 创建]
│   └── codex_review_report.md  ← [7/29 创建]
└── （其余文件待 Phase 0-6 创建，见 reference_files.md）
```
