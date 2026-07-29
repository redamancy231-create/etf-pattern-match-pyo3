# -*- coding: utf-8 -*-
"""MCP server：把形态匹配核心暴露为 LLM 可调用的原子工具。

依赖 ``fastmcp`` 仅在 ``create_server`` 被调用时导入，因此未安装 MCP
extra 时，核心包及本模块仍可正常导入。

运行方式：``python -m etf_pattern_match_pyo3.mcp_server``
"""

from __future__ import annotations

from typing import Any


def _match_pattern_impl(
    prices: list[float],
    t_idx: int,
    top_k: int = 5,
    query_len: int = 20,
    lookback: int = 750,
) -> dict[str, Any]:
    """执行工具逻辑；与 FastMCP 注册解耦，便于无可选依赖时测试。"""
    import numpy as np

    from etf_pattern_match_pyo3 import FEATURE_KEYS, pattern_match_single

    prices_array = np.ascontiguousarray(prices, dtype=np.float64)
    if prices_array.ndim != 1:
        raise ValueError("prices must be a one-dimensional sequence")

    # PyO3 的第二个参数公开名为 T_idx；使用位置参数可避免大小写关键字差异。
    result = pattern_match_single(
        prices_array,
        t_idx,
        k=top_k,
        L_query=query_len,
        T_back=lookback,
    )

    query_info: dict[str, Any] = {
        "t_idx": t_idx,
        "query_len": query_len,
        "lookback": lookback,
    }
    if result is None:
        query_info["error"] = "no valid matches found"
        return {"matches": [], "query_info": query_info}

    features = {
        key: float(result[key])
        for key in FEATURE_KEYS
        if key in result
    }
    query_info["n_features"] = len(features)
    return {
        "matches": [{"features": features}],
        "query_info": query_info,
    }


def create_server():
    """创建 FastMCP server；延迟导入可选依赖。"""
    from fastmcp import FastMCP

    mcp = FastMCP("etf-pattern-match")

    @mcp.tool
    def match_pattern(
        prices: list[float],
        t_idx: int,
        top_k: int = 5,
        query_len: int = 20,
        lookback: int = 750,
    ) -> dict[str, Any]:
        """在历史价格序列中提取 t_idx 查询窗口的 Top-K 形态特征。

        数据获取由上游模型或其他 MCP 完成；本工具只执行本地形态匹配，
        不直接调用 ashare-mcp 或任何数据源。
        """
        return _match_pattern_impl(
            prices=prices,
            t_idx=t_idx,
            top_k=top_k,
            query_len=query_len,
            lookback=lookback,
        )

    return mcp


def main() -> None:
    """启动 MCP server。"""
    create_server().run()


if __name__ == "__main__":
    main()
