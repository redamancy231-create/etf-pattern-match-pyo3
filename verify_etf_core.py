#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""etf-pattern-match-pyo3 Rust vs Python 参考实现 + golden fixtures 验证。

C++ 原版 commit: 7c1269a70f3079b14e25365bd908e6f40f478fc0
用法: PYTHONIOENCODING=utf-8 python verify_etf_core.py
"""

from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path

import numpy as np

from etf_pattern_match_pyo3 import (
    FEATURE_KEYS,
    cosine_similarity,
    dtw_distance,
    pattern_match_single,
    standardize_returns,
)

ROOT = Path(__file__).resolve().parent
FIXTURE_DIR = ROOT / "tests" / "fixtures"
STANDARDIZE_ATOL = 1e-10
COSINE_ATOL = 1e-10
DTW_ATOL = 1e-8
PATTERN_ATOL = 1e-6


def load_fixture(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)["data"]


def close(actual: float, expected: float, atol: float, rtol: float) -> bool:
    return math.isclose(actual, expected, abs_tol=atol, rel_tol=rtol)


def standardize_reference(prices: np.ndarray) -> np.ndarray:
    values = np.asarray(prices, dtype=np.float64)
    if values.size < 2 or not np.all(np.isfinite(values)):
        return np.empty(0, dtype=np.float64)
    returns = []
    for previous, current in zip(values[:-1], values[1:]):
        previous = max(float(previous), 1e-12)
        current = max(float(current), 1e-12)
        returns.append(math.log(current / previous))
    mean = sum(returns) / len(returns)
    centered = [value - mean for value in returns]
    std = math.sqrt(sum(value * value for value in centered) / len(centered))
    if std >= 1e-12:
        centered = [value / std for value in centered]
    return np.asarray(centered, dtype=np.float64)


def cosine_reference(x: np.ndarray, y: np.ndarray) -> float:
    left = np.asarray(x, dtype=np.float64)
    right = np.asarray(y, dtype=np.float64)
    if left.size == 0 or left.shape != right.shape:
        return 0.0
    dot = 0.0
    norm_left_sq = 0.0
    norm_right_sq = 0.0
    for a, b in zip(left, right):
        a = float(a)
        b = float(b)
        dot += a * b
        norm_left_sq += a * a
        norm_right_sq += b * b
    norm_left = math.sqrt(norm_left_sq)
    norm_right = math.sqrt(norm_right_sq)
    if norm_left < 1e-12 or norm_right < 1e-12:
        return 0.0
    return dot / (norm_left * norm_right)


def dtw_reference(x: np.ndarray, y: np.ndarray, window: int = 5) -> float:
    left = np.asarray(x, dtype=np.float64)
    right = np.asarray(y, dtype=np.float64)
    n, m = len(left), len(right)
    if n == 0 or m == 0:
        return math.inf
    band = max(int(window), abs(n - m))
    previous = [math.inf] * (m + 1)
    current = [math.inf] * (m + 1)
    previous[0] = 0.0
    for i in range(1, n + 1):
        start = max(1, i - band)
        end = min(m, i + band)
        for j in range(start, end + 1):
            difference = float(left[i - 1]) - float(right[j - 1])
            cost = difference * difference
            vertical = previous[j] if abs((i - 1) - j) <= band else math.inf
            horizontal = current[j - 1] if j > start else math.inf
            diagonal = previous[j - 1]
            current[j] = cost + min(vertical, horizontal, diagonal)
        previous, current = current, previous
        previous[0] = math.inf
    return math.sqrt(previous[m]) / (n + m)


def verify_standardize_golden() -> int:
    paths = sorted(FIXTURE_DIR.glob("standardize_*.json"))
    for path in paths:
        data = load_fixture(path)
        actual = standardize_returns(np.asarray(data["input"], dtype=np.float64))
        expected = np.asarray(data["output"], dtype=np.float64)
        if not np.allclose(actual, expected, atol=STANDARDIZE_ATOL, rtol=1e-12):
            diff = float(np.max(np.abs(actual - expected)))
            raise AssertionError(f"{path.name}: max diff {diff:.3e}")
    print(f"PASS standardize_returns golden: {len(paths)} fixtures")
    return len(paths)


def verify_cosine_golden() -> int:
    paths = sorted(FIXTURE_DIR.glob("cosine_*.json"))
    for path in paths:
        data = load_fixture(path)
        actual = cosine_similarity(
            np.asarray(data["x"], dtype=np.float64),
            np.asarray(data["y"], dtype=np.float64),
        )
        expected = float(data["output"])
        if not close(actual, expected, COSINE_ATOL, 1e-12):
            raise AssertionError(f"{path.name}: {actual} != {expected}")
    print(f"PASS cosine_similarity golden: {len(paths)} fixtures")
    return len(paths)


def verify_dtw_golden() -> int:
    paths = sorted(FIXTURE_DIR.glob("dtw_*.json"))
    for path in paths:
        data = load_fixture(path)
        actual = dtw_distance(
            np.asarray(data["x"], dtype=np.float64),
            np.asarray(data["y"], dtype=np.float64),
            int(data.get("window", 5)),
        )
        expected = float(data["output"])
        if math.isinf(expected):
            if not math.isinf(actual):
                raise AssertionError(f"{path.name}: expected inf, got {actual}")
        elif not close(actual, expected, DTW_ATOL, 1e-12):
            raise AssertionError(f"{path.name}: {actual} != {expected}")
    print(f"PASS dtw_distance golden: {len(paths)} fixtures")
    return len(paths)


def verify_pattern_match_golden() -> int:
    paths = sorted(FIXTURE_DIR.glob("pattern_match_*.json"))
    for path in paths:
        data = load_fixture(path)
        actual = pattern_match_single(
            np.asarray(data["prices"], dtype=np.float64), int(data["t_idx"])
        )
        expected = data["output"]
        if expected is None:
            if actual is not None:
                raise AssertionError(f"{path.name}: expected None, got {actual}")
            continue
        if actual is None:
            raise AssertionError(f"{path.name}: expected feature dict, got None")
        if tuple(actual) != FEATURE_KEYS:
            raise AssertionError(f"{path.name}: FEATURE_KEYS order mismatch")
        if len(actual) != 15:
            raise AssertionError(f"{path.name}: expected 15 features, got {len(actual)}")
        for key in FEATURE_KEYS:
            if not close(float(actual[key]), float(expected[key]), PATTERN_ATOL, 1e-9):
                raise AssertionError(
                    f"{path.name}/{key}: {actual[key]} != {expected[key]}"
                )
    print(f"PASS pattern_match_single golden: {len(paths)} fixtures")
    return len(paths)


def verify_constants_golden() -> int:
    expected = tuple(load_fixture(FIXTURE_DIR / "constants.json")["FEATURE_KEYS"])
    if FEATURE_KEYS != expected:
        raise AssertionError(f"FEATURE_KEYS mismatch: {FEATURE_KEYS!r} != {expected!r}")
    if len(FEATURE_KEYS) != 15:
        raise AssertionError(f"FEATURE_KEYS length is {len(FEATURE_KEYS)}, expected 15")
    print("PASS constants golden: 1 fixture")
    return 1


def verify_random_cross_validation() -> None:
    for seed in range(5):
        rng = np.random.default_rng(seed)
        prices = 100.0 * np.exp(np.cumsum(rng.normal(0.0003, 0.02, size=64)))
        actual = standardize_returns(prices.astype(np.float64))
        expected = standardize_reference(prices)
        if not np.allclose(actual, expected, atol=STANDARDIZE_ATOL, rtol=1e-12):
            raise AssertionError(f"random standardize seed={seed}")

    fixed_cosine = [
        (np.array([1.0, 2.0]), np.array([1.0, 2.0])),
        (np.array([1.0, 2.0]), np.array([-1.0, -2.0])),
        (np.array([1.0, 0.0]), np.array([0.0, 1.0])),
        (np.zeros(3), np.array([1.0, 2.0, 3.0])),
    ]
    for index, (x, y) in enumerate(fixed_cosine):
        actual = cosine_similarity(x, y)
        expected = cosine_reference(x, y)
        if not close(actual, expected, COSINE_ATOL, 1e-12):
            raise AssertionError(f"fixed cosine case={index}")

    for seed in range(10):
        rng = np.random.default_rng(seed + 100)
        x = rng.normal(size=19).astype(np.float64)
        y = rng.normal(size=19).astype(np.float64)
        window = seed % 7
        actual = dtw_distance(x, y, window)
        expected = dtw_reference(x, y, window)
        if not close(actual, expected, DTW_ATOL, 1e-12):
            raise AssertionError(
                f"random DTW seed={seed}: {actual} != {expected}"
            )
    print("PASS random cross-validation: standardize=5, cosine=4, DTW=10")


def verify_fixture_manifest_count(total: int) -> None:
    with (FIXTURE_DIR / "_manifest.json").open(encoding="utf-8") as handle:
        manifest = json.load(handle)
    expected = int(manifest["_meta"]["total_fixtures"])
    listed = len(manifest["files"])
    if total != expected or listed != expected:
        raise AssertionError(
            f"fixture count mismatch: verified={total}, listed={listed}, expected={expected}"
        )
    print(f"PASS fixture manifest count: {total}/{expected}")


def report_timing() -> None:
    data = load_fixture(FIXTURE_DIR / "dtw_random_0.json")
    x = np.asarray(data["x"], dtype=np.float64)
    y = np.asarray(data["y"], dtype=np.float64)
    started = time.perf_counter()
    for _ in range(200):
        dtw_distance(x, y, int(data["window"]))
    dtw_elapsed = time.perf_counter() - started

    pattern = load_fixture(FIXTURE_DIR / "pattern_match_t700.json")
    prices = np.asarray(pattern["prices"], dtype=np.float64)
    started = time.perf_counter()
    for _ in range(5):
        pattern_match_single(prices, int(pattern["t_idx"]))
    pattern_elapsed = time.perf_counter() - started
    print(
        f"INFO timing (non-gating): DTW 200 calls={dtw_elapsed:.4f}s; "
        f"pattern_match_single 5 calls={pattern_elapsed:.4f}s"
    )


def main() -> int:
    try:
        total = 0
        total += verify_standardize_golden()
        total += verify_cosine_golden()
        total += verify_dtw_golden()
        total += verify_pattern_match_golden()
        total += verify_constants_golden()
        verify_fixture_manifest_count(total)
        verify_random_cross_validation()
        report_timing()
    except Exception as error:
        print(f"FAIL {type(error).__name__}: {error}", file=sys.stderr)
        return 1
    print("\nALL VERIFICATIONS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())