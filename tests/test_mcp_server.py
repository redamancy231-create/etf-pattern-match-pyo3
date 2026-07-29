"""MCP server 单元测试。"""

import asyncio
import importlib.util
import inspect

import numpy as np
import pytest

from etf_pattern_match_pyo3 import FEATURE_KEYS
from etf_pattern_match_pyo3.mcp_server import _match_pattern_impl, create_server


def _resolve_maybe_awaitable(value):
    if not inspect.isawaitable(value):
        return value

    async def resolve():
        return await value

    return asyncio.run(resolve())


def test_match_pattern_impl_returns_serializable_feature_mapping():
    rng = np.random.default_rng(42)
    prices = 100.0 * np.cumprod(1.0 + rng.normal(0.0, 0.02, size=800))
    response = _match_pattern_impl(prices.tolist(), t_idx=500)

    assert response["query_info"]["t_idx"] == 500
    if response["matches"]:
        features = response["matches"][0]["features"]
        assert tuple(features) == FEATURE_KEYS
        assert all(isinstance(value, float) for value in features.values())
        assert response["query_info"]["n_features"] == 15


def test_match_pattern_impl_returns_empty_result_for_short_history():
    response = _match_pattern_impl([100.0, 101.0, 102.0], t_idx=2)
    assert response["matches"] == []
    assert response["query_info"]["error"] == "no valid matches found"


@pytest.mark.skipif(
    importlib.util.find_spec("fastmcp") is None,
    reason="fastmcp not installed",
)
def test_create_server_registers_match_pattern_tool():
    mcp = create_server()
    assert mcp is not None

    if hasattr(mcp, "list_tools"):
        tools = _resolve_maybe_awaitable(mcp.list_tools())
        names = {tool.name for tool in tools}
    elif hasattr(mcp, "get_tools"):
        tools = _resolve_maybe_awaitable(mcp.get_tools())
        names = set(tools) if isinstance(tools, dict) else {tool.name for tool in tools}
    elif hasattr(mcp, "_tool_manager") and hasattr(mcp._tool_manager, "_tools"):
        names = set(mcp._tool_manager._tools)
    else:
        names = {tool.name for tool in mcp._tools}

    assert "match_pattern" in names
