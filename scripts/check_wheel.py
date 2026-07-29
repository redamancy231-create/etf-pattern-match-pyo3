"""检查 maturin wheel 不包含参考实现、测试夹具或审查材料。"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path


def check_wheel(path: Path) -> list[str]:
    """返回 wheel 文件列表；内容不符合发布约束时抛出 AssertionError。"""
    if not path.is_file():
        raise FileNotFoundError(f"wheel 不存在: {path}")
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
    normalized = [name.replace("\\", "/").lower() for name in names]
    forbidden = [
        name
        for name, lower in zip(names, normalized, strict=True)
        if "_reference" in lower
        or "test_reference" in lower
        or "fixtures/" in lower
        or "_review/" in lower
    ]
    if forbidden:
        raise AssertionError(f"wheel 包含禁止发布的文件: {forbidden}")
    core_extensions = [
        name
        for name, lower in zip(names, normalized, strict=True)
        if lower.endswith(".pyd") and "/_core." in lower
    ]
    if not core_extensions:
        raise AssertionError("wheel 缺少 etf_pattern_match_pyo3/_core.*.pyd")
    print(f"Wheel OK: {path.name}")
    print(f"  files: {len(names)}")
    print(f"  extension: {core_extensions[0]}")
    return names


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("用法: python scripts/check_wheel.py <wheel-path>", file=sys.stderr)
        return 2
    try:
        check_wheel(Path(argv[1]))
    except (OSError, AssertionError, zipfile.BadZipFile) as exc:
        print(f"Wheel check FAIL: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
