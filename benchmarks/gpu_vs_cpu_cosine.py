#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""GPU vs CPU 余弦相似度对照 benchmark。

用法：PYTHONIOENCODING=utf-8 python benchmarks/gpu_vs_cpu_cosine.py
"""

import time
from collections.abc import Callable
from typing import Any

import numpy as np


def _elapsed_ms(
    function: Callable[[], Any],
    repeats: int,
    synchronize: Callable[[], Any] | None = None,
) -> float:
    if synchronize is not None:
        synchronize()
    started = time.perf_counter()
    for _ in range(repeats):
        function()
    if synchronize is not None:
        synchronize()
    return (time.perf_counter() - started) / repeats * 1000.0


def benchmark() -> None:
    from etf_pattern_match_pyo3.gpu_adapter import (
        _cosine_similarity_batch_device,
        cosine_similarity_batch_cpu,
        cosine_similarity_batch_gpu,
        has_gpu,
    )

    if not has_gpu():
        print("GPU not available — skipping benchmark")
        return

    import cupy as cp

    rng = np.random.default_rng(42)
    sizes = [100, 500, 1000, 5000]
    synchronize = cp.cuda.get_current_stream().synchronize

    header = (
        f"{'N_candidates':>12} {'CPU循环(ms)':>12} {'GPU计算(ms)':>12} "
        f"{'GPU含传输(ms)':>15} {'计算加速比':>10} {'端到端加速比':>12}"
    )
    print(header)
    print("-" * len(header))

    for candidate_count in sizes:
        query = rng.normal(size=19).astype(np.float64)
        candidates = rng.normal(size=(candidate_count, 19)).astype(np.float64)

        # 预热 Rust/PyO3 与 CuPy，避免首次加载时间污染计时。
        cosine_similarity_batch_cpu(query, candidates[:10])
        cosine_similarity_batch_gpu(query, candidates[:10])

        query_gpu = cp.asarray(query, dtype=cp.float64)
        candidates_gpu = cp.asarray(candidates, dtype=cp.float64)
        _cosine_similarity_batch_device(cp, query_gpu, candidates_gpu)
        synchronize()

        cpu_ms = _elapsed_ms(
            lambda: cosine_similarity_batch_cpu(query, candidates), repeats=10
        )
        gpu_compute_ms = _elapsed_ms(
            lambda: _cosine_similarity_batch_device(
                cp, query_gpu, candidates_gpu
            ),
            repeats=100,
            synchronize=synchronize,
        )
        gpu_total_ms = _elapsed_ms(
            lambda: cosine_similarity_batch_gpu(query, candidates),
            repeats=100,
            synchronize=synchronize,
        )

        compute_speedup = cpu_ms / gpu_compute_ms
        total_speedup = cpu_ms / gpu_total_ms
        print(
            f"{candidate_count:>12} {cpu_ms:>12.3f} "
            f"{gpu_compute_ms:>12.4f} {gpu_total_ms:>15.4f} "
            f"{compute_speedup:>9.1f}x {total_speedup:>11.1f}x"
        )


if __name__ == "__main__":
    benchmark()