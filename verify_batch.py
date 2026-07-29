#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""验证 Rust pattern_match_batch 的一致性、边界条件、性能和参数守卫。"""

from __future__ import annotations

import sys
import time

import numpy as np

from etf_pattern_match_pyo3 import (
    FEATURE_KEYS,
    pattern_match_batch,
    pattern_match_single,
)

SEED = 42
K = 10
L_QUERY = 20
T_BACK = 750
MATCH_STEP = 1
M_FORWARD = 5
DTW_WINDOW = 5
COS_PREFILTER_TOP = 50
MIN_T = L_QUERY + M_FORWARD + 10


def make_prices() -> np.ndarray:
    rng = np.random.default_rng(SEED)
    returns = rng.normal(loc=0.0005, scale=0.01, size=2000)
    return (100.0 * np.exp(np.cumsum(returns))).astype(np.float64)


def single(prices: np.ndarray, t_idx: int, match_step: int = MATCH_STEP):
    return pattern_match_single(
        prices,
        int(t_idx),
        K,
        L_QUERY,
        T_BACK,
        match_step,
        M_FORWARD,
        DTW_WINDOW,
        COS_PREFILTER_TOP,
    )


def batch(prices: np.ndarray, t_indices: np.ndarray, match_step: int = MATCH_STEP):
    return pattern_match_batch(
        prices,
        np.asarray(t_indices, dtype=np.int64),
        K,
        L_QUERY,
        T_BACK,
        match_step,
        M_FORWARD,
        DTW_WINDOW,
        COS_PREFILTER_TOP,
    )


def assert_feature_row(expected: dict[str, float], actual: np.ndarray) -> None:
    if expected is None:
        raise AssertionError("single returned None")
    if actual.shape != (15,):
        raise AssertionError(f"feature row shape is {actual.shape}, expected (15,)")
    for index, key in enumerate(FEATURE_KEYS):
        if not np.isclose(
            float(actual[index]), float(expected[key]), atol=1e-6, rtol=1e-9
        ):
            raise AssertionError(
                f"{key}: batch={actual[index]:.12e}, single={expected[key]:.12e}"
            )


def verify_batch_vs_single(prices: np.ndarray) -> None:
    rng = np.random.default_rng(SEED + 1)
    sample = np.sort(rng.choice(np.arange(100, len(prices) - 10), size=3, replace=False))
    features, mask = batch(prices, sample)
    if not np.all(mask):
        raise AssertionError(f"expected all valid, got mask={mask}")
    if features.shape != (3, 15):
        raise AssertionError(f"features shape is {features.shape}, expected (3, 15)")
    for row, t_idx in zip(features, sample):
        assert_feature_row(single(prices, int(t_idx)), row)
    print(f"PASS batch vs single: t_indices={sample.tolist()}")


def verify_boundaries(prices: np.ndarray) -> None:
    boundary = np.array([0, 5, MIN_T - 1, MIN_T], dtype=np.int64)
    features, mask = batch(prices, boundary)
    if mask.tolist() != [False, False, False, False]:
        raise AssertionError(f"unexpected boundary mask: {mask}")
    if features.shape != (0, 15):
        raise AssertionError(f"boundary features shape is {features.shape}")

    valid_t = 2 * L_QUERY + M_FORWARD + 10
    valid_features, valid_mask = batch(prices, np.array([valid_t], dtype=np.int64))
    if valid_mask.tolist() != [True] or valid_features.shape != (1, 15):
        raise AssertionError(
            f"known-valid T_idx={valid_t}: shape={valid_features.shape}, mask={valid_mask}"
        )
    print(f"PASS boundaries: invalid={boundary.tolist()}, valid={valid_t}")


def report_performance(prices: np.ndarray) -> None:
    test_indices = np.arange(1600, 1700, dtype=np.int64)
    single(prices, int(test_indices[0]))
    batch(prices, test_indices[:5])

    started = time.perf_counter()
    for t_idx in test_indices:
        single(prices, int(t_idx))
    single_elapsed = time.perf_counter() - started

    started = time.perf_counter()
    features, mask = batch(prices, test_indices)
    batch_elapsed = time.perf_counter() - started
    speedup = single_elapsed / batch_elapsed if batch_elapsed > 0 else float("inf")
    print(
        "INFO performance (non-gating): "
        f"single(100)={single_elapsed:.4f}s, batch(100)={batch_elapsed:.4f}s, "
        f"speedup={speedup:.2f}x, valid={int(mask.sum())}/100, shape={features.shape}"
    )


def verify_empty(prices: np.ndarray) -> None:
    features, mask = batch(prices, np.empty(0, dtype=np.int64))
    if features.shape != (0, 15) or mask.shape != (0,):
        raise AssertionError(f"empty result shapes: features={features.shape}, mask={mask.shape}")
    print("PASS empty t_indices")


def verify_all_invalid(prices: np.ndarray) -> None:
    indices = np.array([0, 1, 2, 5, MIN_T - 1], dtype=np.int64)
    features, mask = batch(prices, indices)
    if features.shape != (0, 15) or mask.any():
        raise AssertionError(f"all-invalid result: shape={features.shape}, mask={mask}")
    print("PASS all-invalid t_indices")


def verify_single_valid(prices: np.ndarray) -> None:
    valid_t = 2 * L_QUERY + M_FORWARD + 100
    features, mask = batch(prices, np.array([valid_t], dtype=np.int64))
    if features.shape != (1, 15) or mask.tolist() != [True]:
        raise AssertionError(f"single-valid result: shape={features.shape}, mask={mask}")
    expected = single(prices, valid_t)
    assert_feature_row(expected, features[0])
    print(f"PASS single-valid T_idx={valid_t}")


def verify_match_step_guard(prices: np.ndarray) -> None:
    valid_t = 2 * L_QUERY + M_FORWARD + 100
    for name, call in (
        ("single", lambda: single(prices, valid_t, match_step=0)),
        (
            "batch",
            lambda: batch(prices, np.array([valid_t], dtype=np.int64), match_step=0),
        ),
    ):
        try:
            call()
        except ValueError as error:
            if "match_step" not in str(error).lower() and "window" not in str(error).lower():
                raise AssertionError(f"{name}: unclear ValueError: {error}") from error
        else:
            raise AssertionError(f"{name}: match_step=0 did not raise ValueError")
    print("PASS match_step=0 ValueError guard")


def main() -> int:
    prices = make_prices()
    print(f"prices={len(prices)}, minimum boundary T_idx={MIN_T}")
    try:
        verify_batch_vs_single(prices)
        verify_boundaries(prices)
        report_performance(prices)
        verify_empty(prices)
        verify_all_invalid(prices)
        verify_single_valid(prices)
        verify_match_step_guard(prices)
    except Exception as error:
        print(f"FAIL {type(error).__name__}: {error}", file=sys.stderr)
        return 1
    print("\nALL BATCH VERIFICATIONS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())