import numpy as np
import pytest

from etf_pattern_match_pyo3 import (
    FEATURE_KEYS,
    cosine_similarity,
    dtw_distance,
    pattern_match_batch,
    pattern_match_single,
    standardize_returns,
)


def test_standardize_returns_shape():
    prices = np.array([100.0, 101.0, 102.5, 99.8, 103.2, 105.0])
    result = standardize_returns(prices)
    assert len(result) == len(prices) - 1
    assert result.dtype == np.float64


def test_cosine_similarity():
    a = np.array([1.0, 2.0, 3.0])
    b = np.array([1.0, 2.0, 3.0])
    assert abs(cosine_similarity(a, b) - 1.0) < 1e-10


def test_cosine_similarity_orthogonal():
    a = np.array([1.0, 0.0])
    b = np.array([0.0, 1.0])
    assert abs(cosine_similarity(a, b)) < 1e-10


def test_dtw_identical():
    x = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    assert dtw_distance(x, x) < 1e-10


def test_dtw_empty_returns_inf():
    assert np.isinf(dtw_distance(np.array([]), np.array([1.0])))


def test_pattern_match_single():
    np.random.seed(42)
    prices = 100.0 * np.cumprod(1.0 + np.random.randn(800) * 0.02)
    result = pattern_match_single(prices, 500)
    if result is not None:
        assert isinstance(result, dict)
        assert len(result) == 15
        for key in FEATURE_KEYS:
            assert key in result


def test_pattern_match_single_short_history_returns_none():
    prices = np.array([100.0, 101.0, 102.0], dtype=np.float64)
    assert pattern_match_single(prices, 2) is None


def test_pattern_match_batch():
    np.random.seed(42)
    prices = 100.0 * np.cumprod(1.0 + np.random.randn(800) * 0.02)
    features, mask = pattern_match_batch(
        prices, np.array([500, 600], dtype=np.int64)
    )
    assert features.shape[1] == 15
    assert mask.shape[0] == 2
    assert mask.dtype == bool or str(mask.dtype).startswith("bool")


def test_pattern_match_batch_requires_strictly_increasing():
    prices = np.array([100.0] * 800, dtype=np.float64)
    with pytest.raises(ValueError):
        pattern_match_batch(prices, np.array([600, 600], dtype=np.int64))


def test_feature_keys():
    assert len(FEATURE_KEYS) == 15
    assert FEATURE_KEYS[0] == "top1_sim"
    assert isinstance(FEATURE_KEYS, tuple)
