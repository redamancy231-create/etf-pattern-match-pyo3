"""Rust 与独立 Python 参考实现的浮点一致性测试。"""

import math

import numpy as np
import pytest

from etf_pattern_match_pyo3 import (
    cosine_similarity,
    dtw_distance,
    pattern_match_batch,
    standardize_returns,
)


def standardize_reference(prices: np.ndarray) -> np.ndarray:
    values = np.asarray(prices, dtype=np.float64)
    if values.size < 2 or not np.all(np.isfinite(values)):
        return np.empty(0, dtype=np.float64)
    returns = [
        math.log(max(float(current), 1e-12) / max(float(previous), 1e-12))
        for previous, current in zip(values[:-1], values[1:])
    ]
    mean = sum(returns) / len(returns)
    centered = [value - mean for value in returns]
    std = math.sqrt(sum(value * value for value in centered) / len(centered))
    if std >= 1e-12:
        centered = [value / std for value in centered]
    return np.asarray(centered, dtype=np.float64)


def cosine_reference(x: np.ndarray, y: np.ndarray) -> float:
    dot = 0.0
    norm_x_sq = 0.0
    norm_y_sq = 0.0
    for left, right in zip(x, y):
        left = float(left)
        right = float(right)
        dot += left * right
        norm_x_sq += left * left
        norm_y_sq += right * right
    norm_x = math.sqrt(norm_x_sq)
    norm_y = math.sqrt(norm_y_sq)
    if norm_x < 1e-12 or norm_y < 1e-12:
        return 0.0
    return dot / (norm_x * norm_y)


def dtw_reference(x: np.ndarray, y: np.ndarray, window: int) -> float:
    n, m = len(x), len(y)
    if n == 0 or m == 0:
        return math.inf
    band = max(window, abs(n - m))
    previous = [math.inf] * (m + 1)
    current = [math.inf] * (m + 1)
    previous[0] = 0.0
    for i in range(1, n + 1):
        start = max(1, i - band)
        end = min(m, i + band)
        for j in range(start, end + 1):
            difference = float(x[i - 1]) - float(y[j - 1])
            cost = difference * difference
            vertical = previous[j] if abs((i - 1) - j) <= band else math.inf
            horizontal = current[j - 1] if j > start else math.inf
            current[j] = cost + min(vertical, horizontal, previous[j - 1])
        previous, current = current, previous
        previous[0] = math.inf
    return math.sqrt(previous[m]) / (n + m)


@pytest.mark.parametrize("seed", range(5))
def test_standardize_matches_scalar_reference(seed):
    rng = np.random.default_rng(seed)
    prices = 100.0 * np.exp(np.cumsum(rng.normal(0.0, 0.03, size=257)))
    actual = standardize_returns(prices.astype(np.float64))
    expected = standardize_reference(prices)
    assert np.allclose(actual, expected, atol=1e-10, rtol=1e-12)


@pytest.mark.parametrize("seed", range(4))
def test_cosine_reduction_difference_within_tolerance(seed):
    rng = np.random.default_rng(seed + 20)
    scales = np.logspace(-8, 8, 513)
    x = (rng.normal(size=513) * scales).astype(np.float64)
    y = (rng.normal(size=513) / scales).astype(np.float64)
    actual = cosine_similarity(x, y)
    scalar_expected = cosine_reference(x, y)
    numpy_reduction = float(np.dot(x, y) / (np.linalg.norm(x) * np.linalg.norm(y)))
    assert actual == pytest.approx(scalar_expected, abs=1e-10, rel=1e-12)
    # BLAS/vectorized reduction may reorder operations or use FMA; only tolerance is contractual.
    assert actual == pytest.approx(numpy_reduction, abs=1e-10, rel=1e-12)


@pytest.mark.parametrize("seed,window", [(30, 0), (31, 2), (32, 5), (33, 9)])
def test_dtw_matches_python_reference(seed, window):
    rng = np.random.default_rng(seed)
    x = rng.normal(size=19).astype(np.float64)
    y = rng.normal(size=17).astype(np.float64)
    actual = dtw_distance(x, y, window)
    expected = dtw_reference(x, y, window)
    assert actual == pytest.approx(expected, abs=1e-8, rel=1e-12)


def test_standardize_vectorized_reduction_difference_within_tolerance():
    rng = np.random.default_rng(99)
    prices = 100.0 * np.exp(np.cumsum(rng.normal(0.0, 0.02, size=4097)))
    actual = standardize_returns(prices.astype(np.float64))
    raw = np.diff(np.log(np.maximum(prices, 1e-12)))
    vectorized = raw - np.mean(raw)
    std = np.sqrt(np.mean(vectorized * vectorized))
    vectorized = vectorized / std
    assert np.allclose(actual, vectorized, atol=1e-10, rtol=1e-12)


def test_batch_match_step_zero_raises_value_error():
    prices = np.linspace(100.0, 200.0, 200, dtype=np.float64)
    with pytest.raises(ValueError, match="match_step|window"):
        pattern_match_batch(
            prices, np.array([100], dtype=np.int64), match_step=0
        )