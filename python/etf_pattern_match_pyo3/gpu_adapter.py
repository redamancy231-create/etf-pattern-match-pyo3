# -*- coding: utf-8 -*-
"""GPU 加速余弦预筛选 — CuPy 后端（可选 extra）。

依赖：cupy>=13（通过 ``pip install etf-pattern-match-pyo3[gpu]`` 安装）。

不修改 Rust 核心——GPU 作为 Python 层替代计算后端。
下游代码通过相同的 NumPy 接口消费结果，无需感知后端差异。
"""

from __future__ import annotations

from typing import Any

import numpy as np

_NORM_EPSILON = 1e-12
_has_gpu: bool | None = None


def has_gpu() -> bool:
    """检查 CuPy 与 GPU 运行时是否可用（结果只检测并缓存一次）。"""
    global _has_gpu
    if _has_gpu is None:
        try:
            import cupy as cp

            probe = cp.asarray([1.0, 2.0, 3.0], dtype=cp.float64)
            probe_sum = cp.asnumpy(cp.sum(probe * probe)).item()
            if probe_sum != 14.0:
                raise RuntimeError("CuPy GPU probe returned an unexpected value")
            cp.cuda.get_current_stream().synchronize()
            del probe
        except Exception:
            _has_gpu = False
        else:
            _has_gpu = True
    return _has_gpu


def _validate_batch_inputs(
    query: np.ndarray,
    candidates: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """规范化批量余弦输入，并给出明确的形状错误。"""
    query_array = np.asarray(query, dtype=np.float64)
    candidates_array = np.asarray(candidates, dtype=np.float64)

    if query_array.ndim != 1:
        raise ValueError("query must be a one-dimensional array")
    if candidates_array.ndim != 2:
        raise ValueError("candidates must be a two-dimensional array")
    if candidates_array.shape[1] != query_array.shape[0]:
        raise ValueError(
            "query length must match the second dimension of candidates"
        )

    return (
        np.ascontiguousarray(query_array),
        np.ascontiguousarray(candidates_array),
    )


def _cosine_similarity_batch_device(
    cp: Any,
    query_gpu: Any,
    candidates_gpu: Any,
) -> Any:
    """在已驻留 GPU 的数组上执行批量余弦计算。"""
    query_norm = cp.linalg.norm(query_gpu)
    candidate_norms = cp.linalg.norm(candidates_gpu, axis=1)
    dots = cp.dot(candidates_gpu, query_gpu)

    # 与 Rust CPU 路径一致：任一向量自身的 norm 小于阈值时返回 0。
    zero_norms = (query_norm < _NORM_EPSILON) | (
        candidate_norms < _NORM_EPSILON
    )
    norms = candidate_norms * query_norm
    safe_norms = cp.where(zero_norms, 1.0, norms)
    return cp.where(zero_norms, 0.0, dots / safe_norms)


def cosine_similarity_batch_gpu(
    query: np.ndarray,
    candidates: np.ndarray,
) -> np.ndarray:
    """使用 GPU 计算一批候选窗口与查询窗口的余弦相似度。

    Parameters
    ----------
    query : np.ndarray, shape (L,)
        查询窗口的标准化收益率序列。
    candidates : np.ndarray, shape (N, L)
        N 个候选窗口的标准化收益率序列。

    Returns
    -------
    np.ndarray, shape (N,)
        每个候选窗口与 query 的余弦相似度。
    """
    query_array, candidates_array = _validate_batch_inputs(query, candidates)

    try:
        import cupy as cp
    except ImportError as exc:
        raise ImportError(
            "CuPy is required; install etf-pattern-match-pyo3[gpu]"
        ) from exc

    query_gpu = cp.asarray(query_array, dtype=cp.float64)
    candidates_gpu = cp.asarray(candidates_array, dtype=cp.float64)
    result_gpu = _cosine_similarity_batch_device(cp, query_gpu, candidates_gpu)
    return cp.asnumpy(result_gpu).astype(np.float64, copy=False)


def cosine_prefilter_gpu(
    query_rets: np.ndarray,
    candidate_rets: np.ndarray,
    top_n: int = 50,
    min_cos: float = 0.0,
) -> tuple[np.ndarray, np.ndarray]:
    """GPU 批量余弦预筛选，并返回降序排列的 Top-N 索引和分数。

    分数相同时按候选原始索引升序排序，使结果具有确定性。
    ``min_cos`` 使用严格大于语义，与 Rust 形态匹配预筛选保持一致。
    """
    if isinstance(top_n, (bool, np.bool_)) or not isinstance(
        top_n, (int, np.integer)
    ):
        raise TypeError("top_n must be an integer")
    if top_n < 0:
        raise ValueError("top_n must be non-negative")

    similarities = cosine_similarity_batch_gpu(query_rets, candidate_rets)
    if top_n == 0:
        return np.empty(0, dtype=np.int64), np.empty(0, dtype=np.float64)

    filtered_idx = np.flatnonzero(similarities > min_cos).astype(
        np.int64, copy=False
    )
    if filtered_idx.size == 0:
        return np.empty(0, dtype=np.int64), np.empty(0, dtype=np.float64)

    filtered_scores = similarities[filtered_idx]
    order = np.lexsort((filtered_idx, -filtered_scores))[: int(top_n)]
    return filtered_idx[order], filtered_scores[order]


def cosine_similarity_batch_cpu(
    query: np.ndarray,
    candidates: np.ndarray,
) -> np.ndarray:
    """使用 Rust/PyO3 单条余弦函数逐个计算，作为 CPU 对照基线。"""
    from etf_pattern_match_pyo3 import cosine_similarity

    query_array, candidates_array = _validate_batch_inputs(query, candidates)
    result = np.empty(candidates_array.shape[0], dtype=np.float64)
    for index, candidate in enumerate(candidates_array):
        result[index] = cosine_similarity(query_array, candidate)
    return result