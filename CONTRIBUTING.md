# 贡献指南

本项目主要用于个人编程与跨语言工程实践。欢迎提交 issue 和 pull request；如果计划进行大规模重构、修改公开 API、改变算法语义或调整 golden fixtures，请先开 issue 讨论范围和兼容性影响。

## 开发环境

要求：Windows 11、Python 3.12+、Rust 1.97+、MSVC Build Tools。

```powershell
git clone https://github.com/redamancy231-create/etf-pattern-match-pyo3.git
cd etf-pattern-match-pyo3
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install maturin numpy pytest ruff
maturin develop --release
```

如需测试可选集成：

```powershell
python -m pip install ".[panel,mcp]"
maturin develop --release
```

## 提交前检查

```powershell
cargo fmt --all -- --check
cargo clippy --all-targets --all-features -- -D warnings
cargo test --release
python -m pytest tests/ -v
python verify_etf_core.py
python verify_batch.py
maturin build --release --out dist
$wheel = Get-ChildItem dist/*.whl | Select-Object -First 1
python scripts/check_wheel.py $wheel.FullName
```

## 约束

- 不把 Python 参考实现、golden fixtures、`_review/` 或构建产物打进 runtime wheel。
- 不修改 C++ 原版仓库中的冻结基准来迁就本项目输出。
- 公开 API 或架构级约束变更必须先讨论，并同步测试与文档。
- 新增代码应包含针对行为和边界条件的测试；中文代码注释保持 UTF-8。
