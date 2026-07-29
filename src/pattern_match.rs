use crate::dtw::dtw_distance;
use crate::features::{compare_scores, compute_features};
use crate::standardize::standardize_returns;
use crate::types::{first_non_finite, InputError, MatchResult};

#[derive(Debug)]
struct MatchCandidate {
    hist_end: usize,
    cos_similarity: f64,
    hist_returns: Vec<f64>,
}

/// 与提示词签名兼容的核心入口；无效输入或无候选均返回 `None`。
#[allow(clippy::too_many_arguments)]
#[allow(non_snake_case)]
pub fn pattern_match_core(
    prices: &[f64],
    T_idx: usize,
    k: usize,
    L_query: usize,
    T_back: usize,
    match_step: usize,
    M_forward: usize,
    dtw_window: usize,
    cos_prefilter_top: usize,
    query_rets: &[f64],
    search_start: usize,
    search_end: usize,
    precomputed_rets: Option<&Vec<Vec<f64>>>,
) -> Option<MatchResult> {
    pattern_match_core_checked(
        prices,
        T_idx,
        k,
        L_query,
        T_back,
        match_step,
        M_forward,
        dtw_window,
        cos_prefilter_top,
        query_rets,
        search_start,
        search_end,
        precomputed_rets,
    )
    .ok()
    .flatten()
}

/// 显式区分输入错误与“无有效候选”的严格核心入口。
#[allow(clippy::too_many_arguments)]
pub fn pattern_match_core_checked(
    prices: &[f64],
    t_idx: usize,
    k: usize,
    l_query: usize,
    t_back: usize,
    match_step: usize,
    m_forward: usize,
    dtw_window: usize,
    cos_prefilter_top: usize,
    query_returns: &[f64],
    search_start: usize,
    search_end: usize,
    precomputed_returns: Option<&Vec<Vec<f64>>>,
) -> Result<Option<MatchResult>, InputError> {
    if prices.is_empty() || query_returns.is_empty() {
        return Err(InputError::EmptySequence);
    }
    if let Some(index) = first_non_finite(prices) {
        return Err(InputError::NonFinite { index });
    }
    if let Some(index) = first_non_finite(query_returns) {
        return Err(InputError::NonFinite { index });
    }
    if t_idx >= prices.len() || search_end >= prices.len() {
        return Err(InputError::IndexOutOfRange);
    }
    if l_query < 3
        || t_back == 0
        || k == 0
        || match_step == 0
        || m_forward == 0
        || cos_prefilter_top == 0
    {
        return Err(InputError::InvalidWindow);
    }
    if query_returns.len() < 2 || search_start > search_end {
        return Ok(None);
    }

    // 第一遍：全量余弦预筛选，同时用全量有效窗口估计快速距离尺度。
    let mut candidates = Vec::new();
    let mut fast_shape_distances = Vec::new();
    let mut hist_end = search_start;
    loop {
        if let Some(hist_start) = hist_end.checked_sub(l_query - 1) {
            let hist_returns = if let Some(cache) = precomputed_returns {
                if hist_end < cache.len() {
                    cache[hist_end].clone()
                } else {
                    standardize_returns(&prices[hist_start..=hist_end])
                }
            } else {
                standardize_returns(&prices[hist_start..=hist_end])
            };

            if hist_returns.len() >= 2 && first_non_finite(&hist_returns).is_none() {
                let common_length = hist_returns.len().min(query_returns.len());
                let mut dot = 0.0;
                let mut history_norm_squared = 0.0;
                let mut query_norm_squared = 0.0;
                let mut fast_squared_distance = 0.0;
                for index in 0..common_length {
                    let history_value = hist_returns[index];
                    let query_value = query_returns[index];
                    dot += history_value * query_value;
                    history_norm_squared += history_value * history_value;
                    query_norm_squared += query_value * query_value;
                    let difference = history_value - query_value;
                    fast_squared_distance += difference * difference;
                }
                let history_norm = history_norm_squared.sqrt();
                let query_norm = query_norm_squared.sqrt();
                let cosine = if history_norm > 1e-12 && query_norm > 1e-12 {
                    dot / (history_norm * query_norm)
                } else {
                    0.0
                };
                fast_shape_distances.push((fast_squared_distance / common_length as f64).sqrt());
                if cosine > 0.0 {
                    candidates.push(MatchCandidate {
                        hist_end,
                        cos_similarity: cosine,
                        hist_returns,
                    });
                }
            }
        }

        if hist_end >= search_end {
            break;
        }
        let Some(next) = hist_end.checked_add(match_step) else {
            break;
        };
        if next > search_end {
            break;
        }
        hist_end = next;
    }

    if candidates.len() < 3 {
        return Ok(None);
    }

    let mut sigma_fast = 1.0;
    if fast_shape_distances.len() > 1 {
        let mean = fast_shape_distances.iter().sum::<f64>() / fast_shape_distances.len() as f64;
        let variance = fast_shape_distances
            .iter()
            .map(|distance| {
                let delta = distance - mean;
                delta * delta
            })
            .sum::<f64>()
            / fast_shape_distances.len() as f64;
        sigma_fast = variance.sqrt() / (2.0 * ((l_query - 1) as f64).sqrt());
    }
    sigma_fast = sigma_fast.max(1e-12);

    candidates.sort_by(|left, right| {
        compare_scores(
            left.cos_similarity,
            left.hist_end,
            right.cos_similarity,
            right.hist_end,
        )
    });
    let global_min_cosine = candidates
        .last()
        .map(|candidate| candidate.cos_similarity)
        .unwrap_or(0.0);
    let global_max_cosine = candidates
        .first()
        .map(|candidate| candidate.cos_similarity)
        .unwrap_or(0.0);
    candidates.truncate(cos_prefilter_top.min(candidates.len()));

    // 第二遍：仅对余弦 Top-N 执行 DTW 精排。
    let mut dtw_distances = Vec::with_capacity(candidates.len());
    let mut cosine_similarities = Vec::with_capacity(candidates.len());
    let mut future_returns = Vec::with_capacity(candidates.len());
    let mut match_ends = Vec::with_capacity(candidates.len());
    for candidate in &candidates {
        dtw_distances.push(dtw_distance(
            &candidate.hist_returns,
            query_returns,
            dtw_window,
        ));
        cosine_similarities.push(candidate.cos_similarity);
        let future_end = candidate.hist_end.saturating_add(m_forward);
        if future_end < prices.len() && future_end < t_idx {
            future_returns.push(prices[future_end] / prices[candidate.hist_end] - 1.0);
        } else {
            future_returns.push(f64::NAN);
        }
        match_ends.push(candidate.hist_end);
    }
    if dtw_distances.len() < 3 {
        return Ok(None);
    }

    let sigma = if sigma_fast > 1e-12 { sigma_fast } else { 1.0 };
    let similarities: Vec<f64> = dtw_distances
        .iter()
        .map(|distance| (-distance / sigma).exp())
        .collect();
    let minimum_dtw_similarity = similarities.iter().copied().fold(f64::MAX, f64::min);
    let maximum_dtw_similarity = similarities.iter().copied().fold(f64::MIN, f64::max);
    let dtw_range = if maximum_dtw_similarity - minimum_dtw_similarity > 1e-12 {
        maximum_dtw_similarity - minimum_dtw_similarity
    } else {
        1.0
    };
    let cosine_range = if global_max_cosine - global_min_cosine > 1e-12 {
        global_max_cosine - global_min_cosine
    } else {
        1.0
    };

    let mut scored = Vec::with_capacity(similarities.len());
    for index in 0..similarities.len() {
        let normalized_dtw = (similarities[index] - minimum_dtw_similarity) / dtw_range;
        let normalized_cosine = (cosine_similarities[index] - global_min_cosine) / cosine_range;
        scored.push((
            0.5 * normalized_dtw + 0.5 * normalized_cosine,
            future_returns[index],
            match_ends[index],
        ));
    }
    scored.sort_by(|left, right| compare_scores(left.0, left.2, right.0, right.2));
    scored.truncate(k.min(scored.len()));

    let valid: Vec<(f64, f64, usize)> = scored
        .into_iter()
        .filter(|(_, future_return, _)| !future_return.is_nan())
        .collect();
    if valid.len() < 2 {
        return Ok(None);
    }

    let valid_scores: Vec<f64> = valid.iter().map(|item| item.0).collect();
    let valid_future_returns: Vec<f64> = valid.iter().map(|item| item.1).collect();
    let valid_ends: Vec<usize> = valid.iter().map(|item| item.2).collect();
    let features = compute_features(&valid_scores, &valid_future_returns, &valid_ends, t_back);

    Ok(Some(MatchResult {
        features,
        top_k_scores: valid_scores,
        match_end_indices: valid_ends,
    }))
}

/// 构造查询窗口和搜索边界，等价于 C++ `pattern_match_single` 的纯 Rust 部分。
#[allow(clippy::too_many_arguments)]
pub fn pattern_match(
    prices: &[f64],
    t_idx: usize,
    k: usize,
    l_query: usize,
    t_back: usize,
    match_step: usize,
    m_forward: usize,
    dtw_window: usize,
    cos_prefilter_top: usize,
) -> Result<Option<MatchResult>, InputError> {
    if prices.is_empty() {
        return Err(InputError::EmptySequence);
    }
    if let Some(index) = first_non_finite(prices) {
        return Err(InputError::NonFinite { index });
    }
    if t_idx >= prices.len() {
        return Err(InputError::IndexOutOfRange);
    }
    if l_query < 3
        || t_back == 0
        || k == 0
        || match_step == 0
        || m_forward == 0
        || cos_prefilter_top == 0
    {
        return Err(InputError::InvalidWindow);
    }
    if t_idx < l_query.saturating_add(m_forward).saturating_add(10) {
        return Ok(None);
    }
    let Some(query_start) = t_idx.checked_sub(l_query - 1) else {
        return Ok(None);
    };
    let query_returns = standardize_returns(&prices[query_start..=t_idx]);
    if query_returns.len() < 2 {
        return Ok(None);
    }
    let Some(search_end) = t_idx.checked_sub(l_query) else {
        return Ok(None);
    };
    if search_end < l_query {
        return Ok(None);
    }
    let search_start = (l_query - 1).max(t_idx.saturating_sub(t_back));

    pattern_match_core_checked(
        prices,
        t_idx,
        k,
        l_query,
        t_back,
        match_step,
        m_forward,
        dtw_window,
        cos_prefilter_top,
        &query_returns,
        search_start,
        search_end,
        None,
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::features::FEATURE_KEYS;
    use crate::test_support::{
        close, f64_array, f64_value, fixture_names, read_fixture, usize_value, value,
    };

    #[test]
    fn test_pattern_match_against_golden() {
        for name in fixture_names("pattern_match_") {
            let json = read_fixture(&name);
            let prices = f64_array(&json, "prices");
            let t_idx = usize_value(&json, "t_idx");
            let actual = pattern_match(&prices, t_idx, 10, 20, 750, 1, 5, 5, 50)
                .expect("golden input should be valid");
            if value(&json, "output") == "null" {
                assert!(actual.is_none(), "{name}");
                continue;
            }
            let result = actual.expect("golden fixture should produce a result");
            for (index, key) in FEATURE_KEYS.iter().enumerate() {
                let expected = f64_value(&json, key);
                let observed = result.features[index];
                assert!(
                    close(observed, expected, 1e-6, 1e-9),
                    "{name} {key}: {observed} != {expected}"
                );
            }
        }
    }

    #[test]
    fn invalid_index_is_an_error_and_short_history_is_none() {
        assert_eq!(
            pattern_match(&[1.0, 2.0, 3.0], 3, 10, 20, 750, 1, 5, 5, 50),
            Err(InputError::IndexOutOfRange)
        );
        let prices = vec![100.0; 50];
        assert_eq!(
            pattern_match(&prices, 40, 10, 20, 750, 1, 5, 5, 50),
            Ok(None)
        );
    }
}
