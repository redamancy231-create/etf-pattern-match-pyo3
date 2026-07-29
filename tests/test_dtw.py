"""从 C++ 原版 test_dtw.py 适配的 Rust/PyO3 专项测试。"""

import numpy as np
import pytest

from etf_pattern_match_pyo3 import cosine_similarity, dtw_distance, standardize_returns


class TestStandardizeReturns:
    """standardize_returns 正确性与边界测试。"""

    def test_normal_prices(self):
        prices = np.array([100.0, 101.0, 99.0, 102.0, 104.0])
        result = standardize_returns(prices)
        assert result.shape == (4,)
        assert np.mean(result) == pytest.approx(0.0, abs=1e-12)
        assert np.mean(result * result) == pytest.approx(1.0, abs=1e-12)

    def test_constant_prices(self):
        result = standardize_returns(np.full(5, 100.0))
        assert np.array_equal(result, np.zeros(4))

    def test_short_input(self):
        assert standardize_returns(np.array([100.0])).shape == (0,)

    def test_zero_price_is_clipped(self):
        result = standardize_returns(np.array([0.0, 50.0, 100.0]))
        assert result.shape == (2,)
        assert np.all(np.isfinite(result))

    def test_nan_value_returns_empty(self):
        result = standardize_returns(np.array([100.0, np.nan, 101.0]))
        assert result.shape == (0,)

    def test_inf_value_returns_empty(self):
        result = standardize_returns(np.array([100.0, np.inf, 101.0]))
        assert result.shape == (0,)

    def test_all_nan_returns_empty(self):
        result = standardize_returns(np.array([np.nan, np.nan]))
        assert result.shape == (0,)


class TestCosineSimilarity:
    """cosine_similarity 正确性与阈值测试。"""

    def test_identical_vectors(self):
        x = np.array([1.0, 2.0, 3.0])
        assert cosine_similarity(x, x) == pytest.approx(1.0)

    def test_opposite_vectors(self):
        x = np.array([1.0, 2.0, 3.0])
        assert cosine_similarity(x, -x) == pytest.approx(-1.0)

    def test_orthogonal_vectors(self):
        assert cosine_similarity(
            np.array([1.0, 0.0, 0.0]), np.array([0.0, 1.0, 0.0])
        ) == pytest.approx(0.0)

    def test_zero_vector(self):
        zero = np.zeros(3)
        other = np.array([1.0, 2.0, 3.0])
        assert cosine_similarity(zero, other) == 0.0
        assert cosine_similarity(other, zero) == 0.0

    def test_near_zero_norm(self):
        assert cosine_similarity(
            np.array([1e-13, 1e-13]), np.array([1.0, 2.0])
        ) == 0.0

    def test_exactly_at_threshold(self):
        result = cosine_similarity(np.array([1e-12, 0.0]), np.array([1.0, 0.0]))
        assert result == pytest.approx(1.0)


class TestDTWDistance:
    """DTW 距离与 Sakoe-Chiba band 测试。"""

    def test_identical_sequences(self):
        x = np.array([0.1, 0.2, -0.1, 0.05, 0.0] * 4)
        assert dtw_distance(x, x, window=5) == pytest.approx(0.0, abs=1e-12)

    def test_same_length_sequences(self):
        x = np.array([1.0, 2.0, 3.0, 2.0, 1.0])
        y = np.array([1.0, 2.0, 2.0, 3.0, 1.0])
        result = dtw_distance(x, y, window=5)
        assert result > 0.0
        assert np.isfinite(result)

    def test_different_length_sequences(self):
        x = np.array([0.1, -0.2, 0.3] * 5)
        y = np.array([0.1, -0.2, 0.3] * 7)
        result = dtw_distance(x, y, window=5)
        assert result >= 0.0
        assert np.isfinite(result)

    def test_window_constraint(self):
        rng = np.random.default_rng(123)
        x = rng.normal(size=20)
        y = rng.normal(size=20)
        narrow = dtw_distance(x, y, window=2)
        wide = dtw_distance(x, y, window=10)
        assert narrow >= wide - 1e-12

    def test_empty_input(self):
        assert dtw_distance(np.array([]), np.array([1.0, 2.0])) == np.inf
        assert dtw_distance(np.array([1.0, 2.0]), np.array([])) == np.inf

    def test_single_element(self):
        assert dtw_distance(np.array([0.5]), np.array([0.5])) == pytest.approx(
            0.0, abs=1e-12
        )

    def test_unequal_length_window_zero_remains_reachable(self):
        x = np.array([1.0, 2.0])
        y = np.array([1.0, 1.5, 2.0])
        result = dtw_distance(x, y, window=0)
        assert np.isfinite(result)

    def test_symmetry(self):
        x = np.array([0.2, -0.3, 0.4, 0.1])
        y = np.array([-0.1, 0.25, 0.35])
        assert dtw_distance(x, y, 2) == pytest.approx(
            dtw_distance(y, x, 2), abs=1e-12
        )