"""GPU adapter 测试；无可用 GPU 时跳过 GPU 数值用例。"""

import numpy as np
import pytest

from etf_pattern_match_pyo3.gpu_adapter import (
    cosine_prefilter_gpu,
    cosine_similarity_batch_cpu,
    cosine_similarity_batch_gpu,
    has_gpu,
)

HAS_GPU = has_gpu()


def test_has_gpu_returns_bool():
    assert isinstance(HAS_GPU, bool)


@pytest.mark.skipif(not HAS_GPU, reason="GPU not available")
class TestGPUCosine:
    def test_batch_cosine_identical_to_cpu(self):
        """GPU 批量余弦应与 CPU 逐个计算结果一致（容差内）。"""
        rng = np.random.default_rng(42)
        query = rng.normal(size=19).astype(np.float64)
        candidates = rng.normal(size=(500, 19)).astype(np.float64)

        gpu_result = cosine_similarity_batch_gpu(query, candidates)
        cpu_result = cosine_similarity_batch_cpu(query, candidates)

        assert gpu_result.dtype == np.float64
        assert gpu_result.shape == (500,)
        assert np.allclose(gpu_result, cpu_result, atol=1e-10, rtol=1e-12)

    def test_prefilter_matches_cpu_order(self):
        rng = np.random.default_rng(7)
        query = rng.normal(size=19).astype(np.float64)
        candidates = rng.normal(size=(200, 19)).astype(np.float64)

        indices, scores = cosine_prefilter_gpu(query, candidates, top_n=30)
        cpu_scores = cosine_similarity_batch_cpu(query, candidates)
        eligible = np.flatnonzero(cpu_scores > 0.0).astype(np.int64)
        expected_order = np.lexsort((eligible, -cpu_scores[eligible]))[:30]
        expected_indices = eligible[expected_order]

        assert len(indices) <= 30
        assert len(indices) == len(scores)
        assert np.array_equal(indices, expected_indices)
        assert np.allclose(scores, cpu_scores[indices], atol=1e-10, rtol=1e-12)
        assert np.all(np.diff(scores) <= 0.0)

    def test_zero_vector_handling(self):
        rng = np.random.default_rng(11)
        query = np.zeros(19, dtype=np.float64)
        candidates = rng.normal(size=(100, 19)).astype(np.float64)

        result = cosine_similarity_batch_gpu(query, candidates)
        assert np.all(result == 0.0)

    def test_near_zero_norm_matches_cpu_threshold(self):
        query = np.array([1e-13, 0.0], dtype=np.float64)
        candidates = np.array(
            [[1e13, 0.0], [1.0, 0.0], [0.0, 0.0]], dtype=np.float64
        )
        assert np.array_equal(
            cosine_similarity_batch_gpu(query, candidates),
            cosine_similarity_batch_cpu(query, candidates),
        )

        threshold_query = np.array([1e-12, 0.0], dtype=np.float64)
        threshold_result = cosine_similarity_batch_gpu(
            threshold_query, np.array([[1.0, 0.0]], dtype=np.float64)
        )
        assert threshold_result[0] == pytest.approx(1.0)

    def test_prefilter_ties_use_index_ascending(self):
        query = np.array([1.0, 0.0], dtype=np.float64)
        candidates = np.array(
            [[1.0, 0.0], [2.0, 0.0], [1.0, 1.0]], dtype=np.float64
        )
        indices, scores = cosine_prefilter_gpu(query, candidates, top_n=2)

        assert np.array_equal(indices, np.array([0, 1], dtype=np.int64))
        assert np.allclose(scores, np.array([1.0, 1.0]))


@pytest.mark.skipif(HAS_GPU, reason="GPU is available")
class TestGPUNotAvailable:
    def test_has_gpu_returns_false(self):
        assert not has_gpu()