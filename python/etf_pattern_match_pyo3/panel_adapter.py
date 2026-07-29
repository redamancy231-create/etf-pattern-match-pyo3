# -*- coding: utf-8 -*-
"""Panel 格式适配器：ml-quant Panel → NumPy → Rust 形态匹配核心。

真实 Panel 通常由 torch.Tensor 承载字段，但本模块只依赖其 ``cpu()`` /
``numpy()`` 协议，不在模块顶层导入 mlquant 或 torch。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Union

import numpy as np

if TYPE_CHECKING:
    from mlquant.data import Panel

AssetColumn = Union[int, str]


def _to_numpy_1d(value: Any, dtype: np.dtype[Any]) -> np.ndarray:
    """将 tensor/array-like 转为连续的一维 NumPy 数组。"""
    detach = getattr(value, "detach", None)
    if callable(detach):
        value = detach()

    cpu = getattr(value, "cpu", None)
    if callable(cpu):
        value = cpu()

    to_numpy = getattr(value, "numpy", None)
    array = to_numpy() if callable(to_numpy) else np.asarray(value)
    array = np.asarray(array)
    if array.ndim != 1:
        raise ValueError(f"expected a 1-D asset series, got shape {array.shape}")
    return np.ascontiguousarray(array, dtype=dtype)


def _resolve_asset_index(panel: Any, asset_col: AssetColumn) -> int:
    """把股票代码或整数列索引解析为非负整数索引。"""
    stocks = panel.stocks
    if isinstance(asset_col, str):
        return list(stocks).index(asset_col)
    if not isinstance(asset_col, (int, np.integer)) or isinstance(asset_col, bool):
        raise TypeError("asset_col must be an integer index or stock symbol")

    index = int(asset_col)
    if index < 0:
        index += len(stocks)
    if index < 0 or index >= len(stocks):
        raise IndexError("asset_col is out of range")
    return index


def panel_to_prices(
    panel: "Panel",
    asset_col: AssetColumn = 0,
) -> tuple[np.ndarray, np.ndarray, str]:
    """从 Panel 提取单资产的收盘价、可交易掩码和股票代码。

    ``panel.mask`` 的语义是 ``True=可交易``。返回数组始终是一维、连续，
    且价格为 ``float64``、掩码为 ``bool``。
    """
    index = _resolve_asset_index(panel, asset_col)
    fields = getattr(panel, "fields", None)
    close_matrix = fields["close"] if fields is not None and "close" in fields else panel.close
    close = close_matrix[:, index]
    mask = panel.mask[:, index]

    prices = _to_numpy_1d(close, np.dtype(np.float64))
    mask_array = _to_numpy_1d(mask, np.dtype(bool))
    if prices.shape != mask_array.shape:
        raise ValueError(
            "close and mask series must have the same shape, "
            f"got {prices.shape} and {mask_array.shape}"
        )

    return prices, mask_array, str(panel.stocks[index])


def _filtered_prices(prices: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """保留自然日历轴，并把不可交易位置标记为 NaN。"""
    filtered = prices.copy()
    filtered[~mask] = np.nan
    return np.ascontiguousarray(filtered, dtype=np.float64)


def _finite_mask_fallback(prices: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """为拒绝 NaN 的旧核心插值不可交易位置，同时保留日历轴。"""
    valid = mask & np.isfinite(prices)
    if not np.any(valid):
        raise ValueError("no finite tradable prices are available")

    positions = np.arange(prices.size)
    interpolated = np.interp(positions, positions[valid], prices[valid])
    return np.ascontiguousarray(interpolated, dtype=np.float64)


def _call_with_mask_fallback(
    matcher: Any,
    prices: np.ndarray,
    mask: np.ndarray,
    *args: Any,
    **kwargs: Any,
):
    """优先传入 NaN 掩码；若当前核心全局拒绝 NaN，则回退到插值序列。"""
    try:
        return matcher(_filtered_prices(prices, mask), *args, **kwargs)
    except ValueError as exc:
        if "non-finite value at index" not in str(exc):
            raise
        return matcher(_finite_mask_fallback(prices, mask), *args, **kwargs)


def pattern_match_single_panel(
    panel: "Panel",
    t_idx: int,
    asset_col: AssetColumn = 0,
    **kwargs: Any,
):
    """Panel 版本的 ``pattern_match_single``，其余参数原样透传。"""
    from etf_pattern_match_pyo3 import pattern_match_single

    prices, mask, _symbol = panel_to_prices(panel, asset_col)
    if not isinstance(t_idx, (int, np.integer)) or isinstance(t_idx, bool):
        raise TypeError("t_idx must be an integer")

    t_idx = int(t_idx)
    if t_idx < 0 or t_idx >= prices.size:
        raise IndexError("t_idx is out of range")
    if not mask[t_idx] or not np.isfinite(prices[t_idx]):
        return None

    return _call_with_mask_fallback(pattern_match_single, prices, mask, t_idx, **kwargs)


def pattern_match_batch_panel(
    panel: "Panel",
    t_indices: np.ndarray,
    asset_col: AssetColumn = 0,
    **kwargs: Any,
):
    """Panel 版本的 ``pattern_match_batch``。"""
    from etf_pattern_match_pyo3 import pattern_match_batch

    prices, mask, _symbol = panel_to_prices(panel, asset_col)
    indices = np.asarray(t_indices)
    if indices.ndim != 1:
        raise ValueError("t_indices must be a 1-D array")
    if not np.issubdtype(indices.dtype, np.integer):
        raise TypeError("t_indices must contain integers")
    indices = np.ascontiguousarray(indices, dtype=np.int64)

    return _call_with_mask_fallback(
        pattern_match_batch,
        prices,
        mask,
        indices,
        **kwargs,
    )
