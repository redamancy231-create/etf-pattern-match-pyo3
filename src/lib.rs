//! etf-pattern-match-pyo3 Phase 2：PyO3 绑定层，将纯 Rust 核心暴露给 Python。

mod batch;
mod cosine;
mod dtw;
mod features;
mod pattern_match;
mod standardize;
mod types;

#[cfg(test)]
mod test_support;

use pyo3::exceptions::{PyTypeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyTuple};
use std::sync::atomic::{AtomicU64, Ordering};
use std::time::Instant;

use numpy::{PyArray1, PyArray2, PyReadonlyArray1};

pub use batch::match_batch;
pub use cosine::{cosine_similarity, cosine_similarity_checked};
pub use dtw::{dtw_distance, dtw_distance_checked};
pub use features::{compute_features, compute_features_checked, sort_scored_windows, FEATURE_KEYS};
pub use pattern_match::{pattern_match, pattern_match_core, pattern_match_core_checked};
pub use standardize::{standardize_returns, standardize_returns_checked};
pub use types::{BatchInput, InputError, MatchResult, ScoredWindow};

static LAST_INTERNAL_NS: AtomicU64 = AtomicU64::new(0);

fn record_internal_ns(elapsed_ns: u128) {
    LAST_INTERNAL_NS.store(elapsed_ns.min(u64::MAX as u128) as u64, Ordering::Relaxed);
}

impl From<InputError> for PyErr {
    fn from(err: InputError) -> Self {
        PyValueError::new_err(err.to_string())
    }
}

/// 将一维 f64 numpy 数组提取为 Rust 拥有的 Vec<f64>。
///
/// 对连续数组走零拷贝 as_slice 路径；非连续数组返回 TypeError（与
/// CLAUDE.md 架构约束 #2 一致）。
fn extract_f64_vec(arr: &PyReadonlyArray1<'_, f64>) -> PyResult<Vec<f64>> {
    if arr.as_array().is_standard_layout() {
        Ok(arr.as_slice()?.to_vec())
    } else {
        Err(PyTypeError::new_err(
            "input array must be contiguous and in standard layout",
        ))
    }
}

/// 将一维 i64 numpy 数组提取为 Rust 拥有的 Vec<i64>。
fn extract_i64_vec(arr: &PyReadonlyArray1<'_, i64>) -> PyResult<Vec<i64>> {
    if arr.as_array().is_standard_layout() {
        Ok(arr.as_slice()?.to_vec())
    } else {
        Err(PyTypeError::new_err(
            "input array must be contiguous and in standard layout",
        ))
    }
}

/// 验证 t_indices：非负、严格递增，并转换为 usize。
fn validate_t_indices(t_indices: &[i64]) -> PyResult<Vec<usize>> {
    let mut result = Vec::with_capacity(t_indices.len());
    let mut prev: Option<i64> = None;
    for (index, &value) in t_indices.iter().enumerate() {
        if value < 0 {
            return Err(PyValueError::new_err(format!(
                "t_indices[{index}] is negative"
            )));
        }
        if let Some(previous) = prev {
            if value <= previous {
                return Err(PyValueError::new_err(
                    "t_indices must be strictly increasing",
                ));
            }
        }
        prev = Some(value);
        result.push(value as usize);
    }
    Ok(result)
}

/// 把 MatchResult 的 15 维特征转换为由 FEATURE_KEYS 作为键的 Python dict。
fn match_result_to_dict<'py>(py: Python<'py>, result: &MatchResult) -> PyResult<Bound<'py, PyAny>> {
    let dict = PyDict::new(py);
    for (key, value) in FEATURE_KEYS.iter().zip(result.features.iter()) {
        dict.set_item(*key, *value)?;
    }
    Ok(dict.into_any())
}

/// 序列预处理：价格序列 → 标准化对数收益率（长度 n-1）。
#[pyfunction(name = "standardize_returns")]
fn standardize_returns_py<'py>(
    py: Python<'py>,
    price_series: PyReadonlyArray1<'py, f64>,
) -> PyResult<Bound<'py, PyAny>> {
    let prices = extract_f64_vec(&price_series)?;

    let (result, elapsed_ns) = py.allow_threads(|| {
        let started = Instant::now();
        let result = crate::standardize::standardize_returns(&prices);
        (result, started.elapsed().as_nanos())
    });
    record_internal_ns(elapsed_ns);

    let array = PyArray1::from_vec(py, result);
    Ok(array.into_any())
}

/// 余弦相似度。
#[pyfunction(name = "cosine_similarity")]
fn cosine_similarity_py(
    py: Python<'_>,
    x: PyReadonlyArray1<'_, f64>,
    y: PyReadonlyArray1<'_, f64>,
) -> PyResult<f64> {
    let x_vec = extract_f64_vec(&x)?;
    let y_vec = extract_f64_vec(&y)?;

    let (result, elapsed_ns) = py.allow_threads(|| {
        let started = Instant::now();
        let result = crate::cosine::cosine_similarity(&x_vec, &y_vec);
        (result, started.elapsed().as_nanos())
    });
    record_internal_ns(elapsed_ns);
    Ok(result)
}

/// DTW 距离，空序列返回 inf。
#[pyfunction(name = "dtw_distance")]
#[pyo3(signature = (x, y, window = 5))]
fn dtw_distance_py(
    py: Python<'_>,
    x: PyReadonlyArray1<'_, f64>,
    y: PyReadonlyArray1<'_, f64>,
    window: usize,
) -> PyResult<f64> {
    let x_vec = extract_f64_vec(&x)?;
    let y_vec = extract_f64_vec(&y)?;

    let (result, elapsed_ns) = py.allow_threads(|| {
        let started = Instant::now();
        let result = crate::dtw::dtw_distance(&x_vec, &y_vec, window);
        (result, started.elapsed().as_nanos())
    });
    record_internal_ns(elapsed_ns);
    Ok(result)
}

/// 单次形态匹配：返回 dict 或 None。
#[pyfunction(name = "pattern_match_single")]
#[pyo3(signature = (
    prices,
    T_idx,
    k = 10,
    L_query = 20,
    T_back = 750,
    match_step = 1,
    M_forward = 5,
    dtw_window = 5,
    cos_prefilter_top = 50
))]
#[allow(clippy::too_many_arguments)]
#[allow(non_snake_case)]
fn pattern_match_single_py<'py>(
    py: Python<'py>,
    prices: PyReadonlyArray1<'py, f64>,
    T_idx: usize,
    k: usize,
    L_query: usize,
    T_back: usize,
    match_step: usize,
    M_forward: usize,
    dtw_window: usize,
    cos_prefilter_top: usize,
) -> PyResult<Bound<'py, PyAny>> {
    let prices_vec = extract_f64_vec(&prices)?;

    let (result, elapsed_ns) = py.allow_threads(|| {
        let started = Instant::now();
        let result = crate::pattern_match::pattern_match(
            &prices_vec,
            T_idx,
            k,
            L_query,
            T_back,
            match_step,
            M_forward,
            dtw_window,
            cos_prefilter_top,
        );
        (result, started.elapsed().as_nanos())
    });
    record_internal_ns(elapsed_ns);
    let result = result?;

    match result {
        None => Ok(py.None().into_bound(py)),
        Some(ref matched) => match_result_to_dict(py, matched),
    }
}

/// 批量形态匹配：返回 (features_X15, valid_mask)。
#[pyfunction(name = "pattern_match_batch")]
#[pyo3(signature = (
    prices,
    t_indices,
    k = 10,
    L_query = 20,
    T_back = 750,
    match_step = 1,
    M_forward = 5,
    dtw_window = 5,
    cos_prefilter_top = 50
))]
#[allow(clippy::too_many_arguments)]
#[allow(non_snake_case)]
fn pattern_match_batch_py<'py>(
    py: Python<'py>,
    prices: PyReadonlyArray1<'py, f64>,
    t_indices: PyReadonlyArray1<'py, i64>,
    k: usize,
    L_query: usize,
    T_back: usize,
    match_step: usize,
    M_forward: usize,
    dtw_window: usize,
    cos_prefilter_top: usize,
) -> PyResult<Bound<'py, PyAny>> {
    let prices_vec = extract_f64_vec(&prices)?;
    let t_indices_vec = extract_i64_vec(&t_indices)?;
    let t_idx_usize = validate_t_indices(&t_indices_vec)?;
    if match_step == 0 {
        return Err(PyValueError::new_err(
            "match_step must be greater than zero",
        ));
    }

    let sample_count = t_idx_usize.len();

    let (results, elapsed_ns) = py.allow_threads(|| {
        let started = Instant::now();
        let inputs: Vec<BatchInput<'_>> = t_idx_usize
            .iter()
            .map(|&t_idx| BatchInput {
                prices: &prices_vec,
                t_idx,
                k,
                L_query,
                T_back,
                match_step,
                M_forward,
                dtw_window,
                cos_prefilter_top,
            })
            .collect();
        let results = crate::batch::match_batch(&inputs);
        (results, started.elapsed().as_nanos())
    });
    record_internal_ns(elapsed_ns);

    let mut valid_mask = vec![false; sample_count];
    let mut features_matrix: Vec<Vec<f64>> = Vec::new();
    for (index, result) in results.iter().enumerate() {
        if let Some(ref matched) = result {
            valid_mask[index] = true;
            features_matrix.push(matched.features.to_vec());
        }
    }

    let features_array = if features_matrix.is_empty() {
        let empty = ndarray::Array2::<f64>::from_shape_vec((0, 15), Vec::new())
            .map_err(|error| PyValueError::new_err(error.to_string()))?;
        PyArray2::from_owned_array(py, empty)
    } else {
        PyArray2::from_vec2(py, &features_matrix)
            .map_err(|error| PyValueError::new_err(error.to_string()))?
    };

    let mask_array = PyArray1::from_vec(py, valid_mask);
    let tuple = PyTuple::new(py, [features_array.into_any(), mask_array.into_any()])?;
    Ok(tuple.into_any())
}

/// Benchmark 专用：返回最近一次 wrapper 内纯计算区的耗时（ns）。
#[pyfunction(name = "_benchmark_last_internal_ns")]
fn benchmark_last_internal_ns_py() -> u64 {
    LAST_INTERNAL_NS.load(Ordering::Relaxed)
}

#[pymodule]
fn _core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(standardize_returns_py, m)?)?;
    m.add_function(wrap_pyfunction!(cosine_similarity_py, m)?)?;
    m.add_function(wrap_pyfunction!(dtw_distance_py, m)?)?;
    m.add_function(wrap_pyfunction!(pattern_match_single_py, m)?)?;
    m.add_function(wrap_pyfunction!(pattern_match_batch_py, m)?)?;
    m.add_function(wrap_pyfunction!(benchmark_last_internal_ns_py, m)?)?;

    let feature_keys_tuple = PyTuple::new(m.py(), FEATURE_KEYS.iter().copied())?;
    m.add("FEATURE_KEYS", feature_keys_tuple)?;

    Ok(())
}
