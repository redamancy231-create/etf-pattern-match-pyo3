#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""生成 NRR Gate 2 冻结的 Phase 4 benchmark corpus。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

SEED = 42
STANDARD_SPEC = [
    (5, 500, 19, 0.01, "短×短×低波动"),
    (5, 1000, 19, 0.03, "中×短×高波动"),
    (5, 2000, 60, 0.01, "长×长×低波动"),
    (5, 4000, 60, 0.03, "超长×长×高波动"),
]


def _save(output_dir: Path, index: int, prices: np.ndarray, config: dict[str, Any]) -> None:
    prices = np.ascontiguousarray(prices, dtype=np.float64)
    payload = np.array(config, dtype=object)
    np.savez(output_dir / f"corpus_{index:02d}.npz", prices=prices, config=payload)


def _try_real_etf() -> tuple[np.ndarray | None, str]:
    """尽力获取 510050.SH；失败时由调用方使用确定性本地替代。"""
    try:
        import akshare as ak  # type: ignore[import-not-found]

        frame = ak.stock_zh_index_daily_em(symbol="sh510050")
        close = np.asarray(frame["close"], dtype=np.float64)
        close = close[np.isfinite(close)]
        if close.size >= 500:
            return close[-500:], "akshare:sh510050:last_500"
        return None, "akshare 返回数据不足 500 点"
    except Exception as exc:  # noqa: BLE001 - edge corpus 必须允许离线降级
        return None, f"akshare 不可用: {type(exc).__name__}: {exc}"


def generate(output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    np.random.seed(SEED)
    manifest: dict[str, Any] = {
        "seed": SEED,
        "generator": "np.random.seed + np.random.randn + np.cumprod",
        "standard": [],
        "edge": [],
    }

    index = 0
    for count, length, l_query, sigma, desc in STANDARD_SPEC:
        for group in range(count):
            prices = 100.0 * np.cumprod(1.0 + np.random.randn(length) * sigma)
            config = {
                "kind": "standard",
                "L_query": l_query,
                "sigma": sigma,
                "len": length,
                "desc": desc,
                "group": group,
                "seed": SEED,
            }
            _save(output_dir, index, prices, config)
            manifest["standard"].append({"file": f"corpus_{index:02d}.npz", **config})
            index += 1

    edge_cases: list[tuple[np.ndarray, dict[str, Any]]] = []
    edge_cases.append(
        (
            np.full(500, 100.0, dtype=np.float64),
            {"kind": "edge", "L_query": 19, "sigma": 0.0, "len": 500, "desc": "常数序列"},
        )
    )
    near_zero = 100.0 * np.cumprod(1.0 + np.random.randn(1000) * 0.0001)
    edge_cases.append(
        (
            near_zero,
            {"kind": "edge", "L_query": 19, "sigma": 0.0001, "len": 1000, "desc": "近零波动"},
        )
    )
    with_nan = 100.0 * np.cumprod(1.0 + np.random.randn(1000) * 0.01)
    with_nan[99::100] = np.nan
    edge_cases.append(
        (
            with_nan,
            {
                "kind": "edge",
                "L_query": 19,
                "sigma": 0.01,
                "len": 1000,
                "desc": "含 NaN 序列（每 100 点插入一个 NaN）",
            },
        )
    )

    real_prices, real_source = _try_real_etf()
    if real_prices is None:
        # edge corpus 不参与 10% 阈值；离线时保留固定文件数并明确标记替代来源。
        real_prices = 100.0 * np.cumprod(1.0 + np.random.randn(500) * 0.012)
        real_source = f"deterministic_fallback; {real_source}"
    edge_cases.append(
        (
            real_prices,
            {
                "kind": "edge",
                "L_query": 19,
                "sigma": None,
                "len": int(real_prices.size),
                "desc": "510050.SH 真实 ETF 切片（离线时确定性替代）",
                "source": real_source,
            },
        )
    )

    trend = 100.0 * np.cumprod(1.0 + 0.001 + np.random.randn(1000) * 0.001)
    edge_cases.append(
        (
            trend,
            {
                "kind": "edge",
                "L_query": 19,
                "sigma": 0.001,
                "drift": 0.001,
                "len": 1000,
                "desc": "上升趋势（drift=+0.001，叠加低噪声）",
            },
        )
    )

    for prices, config in edge_cases:
        _save(output_dir, index, prices, config)
        manifest["edge"].append({"file": f"corpus_{index:02d}.npz", **config})
        index += 1

    manifest["file_count"] = index
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "corpus",
    )
    args = parser.parse_args()
    manifest = generate(args.output_dir.resolve())
    print(f"已生成 {manifest['file_count']} 个 corpus 文件: {args.output_dir.resolve()}")
    for item in manifest["edge"]:
        if item["file"] == "corpus_23.npz":
            print(f"corpus_23 来源: {item.get('source', 'unknown')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())