import glob
import json
from pathlib import Path

import numpy as np

from etf_pattern_match_pyo3 import (
    FEATURE_KEYS,
    cosine_similarity,
    dtw_distance,
    pattern_match_single,
    standardize_returns,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def load_data(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)["data"]


def test_standardize_golden():
    for path in sorted(glob.glob(f"{FIXTURE_DIR}/standardize_*.json")):
        data = load_data(path)
        result = standardize_returns(np.array(data["input"], dtype=np.float64))
        expected = np.array(data["output"], dtype=np.float64)
        assert np.allclose(result, expected, atol=1e-10, rtol=1e-12), path


def test_cosine_golden():
    for path in sorted(glob.glob(f"{FIXTURE_DIR}/cosine_*.json")):
        data = load_data(path)
        result = cosine_similarity(
            np.array(data["x"], dtype=np.float64),
            np.array(data["y"], dtype=np.float64),
        )
        expected = data["output"]
        assert np.isclose(result, expected, atol=1e-10, rtol=1e-12), path


def test_dtw_golden():
    for path in sorted(glob.glob(f"{FIXTURE_DIR}/dtw_*.json")):
        data = load_data(path)
        result = dtw_distance(
            np.array(data["x"], dtype=np.float64),
            np.array(data["y"], dtype=np.float64),
            data.get("window", 5),
        )
        expected = data["output"]
        if np.isinf(expected):
            assert np.isinf(result), path
        else:
            assert np.isclose(result, expected, atol=1e-8, rtol=1e-12), path


def test_pattern_match_golden():
    for path in sorted(glob.glob(f"{FIXTURE_DIR}/pattern_match_*.json")):
        data = load_data(path)
        result = pattern_match_single(
            np.array(data["prices"], dtype=np.float64), int(data["t_idx"])
        )
        expected = data["output"]
        if expected is None:
            assert result is None, path
            continue
        assert result is not None, path
        assert tuple(result) == FEATURE_KEYS, path
        assert len(result) == 15, path
        for key in FEATURE_KEYS:
            assert np.isclose(
                float(result[key]), float(expected[key]), atol=1e-6, rtol=1e-9
            ), f"{path}: {key}"


def test_feature_keys_golden():
    expected = tuple(load_data(FIXTURE_DIR / "constants.json")["FEATURE_KEYS"])
    assert FEATURE_KEYS == expected
    assert len(FEATURE_KEYS) == 15