use std::cmp::Ordering;

use crate::types::InputError;

pub const FEATURE_KEYS: [&str; 15] = [
    "top1_sim",
    "top5_avg_sim",
    "sim_decay",
    "sim_variance",
    "match_distance_ratio",
    "avg_future_ret",
    "weighted_future_ret",
    "median_future_ret",
    "ret_sign_consistency",
    "best_match_ret",
    "max_dd_in_matches",
    "match_time_span",
    "match_time_span_ratio",
    "match_cluster_ratio",
    "n_matches_above_thresh",
];

const SCORE_ABS_TOLERANCE: f64 = 1e-12;
const SCORE_REL_TOLERANCE: f64 = 1e-12;

fn scores_are_near(left: f64, right: f64) -> bool {
    let tolerance = SCORE_ABS_TOLERANCE.max(SCORE_REL_TOLERANCE * left.abs().max(right.abs()));
    (left - right).abs() <= tolerance
}

fn score_order(left_score: f64, left_end: usize, right_score: f64, right_end: usize) -> Ordering {
    match (left_score.is_nan(), right_score.is_nan()) {
        (true, true) => left_end.cmp(&right_end),
        (true, false) => Ordering::Greater,
        (false, true) => Ordering::Less,
        (false, false) if scores_are_near(left_score, right_score) => left_end.cmp(&right_end),
        (false, false) => right_score.total_cmp(&left_score),
    }
}

/// 按得分降序、结束索引升序稳定排序，并过滤 NaN 后续收益。
pub fn sort_scored_windows(
    scored: &mut Vec<(f64, f64, usize)>,
    k: usize,
) -> Vec<(f64, f64, usize)> {
    scored.retain(|(_, future_return, _)| !future_return.is_nan());
    scored.sort_by(|left, right| score_order(left.0, left.2, right.0, right.2));
    scored.truncate(k.min(scored.len()));
    scored.clone()
}

/// 计算与 C++ `PatternResult` 字段顺序一致的 15 维特征。
#[allow(non_snake_case)]
pub fn compute_features(
    scores: &[f64],
    future_rets: &[f64],
    match_ends: &[usize],
    T_back: usize,
) -> [f64; 15] {
    if scores.is_empty()
        || scores.len() != future_rets.len()
        || scores.len() != match_ends.len()
        || T_back == 0
    {
        return [0.0; 15];
    }

    let count = scores.len();
    let count_f64 = count as f64;
    let top1_similarity = scores[0];
    let average_count = 5usize.min(count);
    let top5_average = scores[..average_count].iter().sum::<f64>() / average_count as f64;
    let similarity_decay = top1_similarity - top5_average;

    let mean_score = scores.iter().sum::<f64>() / count_f64;
    let similarity_variance = scores
        .iter()
        .map(|score| {
            let delta = score - mean_score;
            delta * delta
        })
        .sum::<f64>()
        / count_f64;
    let distance_ratio = if top1_similarity > 1e-12 {
        similarity_decay / top1_similarity
    } else {
        0.0
    };

    let average_future_return = future_rets.iter().sum::<f64>() / count_f64;
    let weighted_sum = scores
        .iter()
        .zip(future_rets)
        .map(|(score, future_return)| score * future_return)
        .sum::<f64>();
    let weight_sum = scores.iter().sum::<f64>();
    let weighted_future_return = if weight_sum > 1e-12 {
        weighted_sum / weight_sum
    } else {
        average_future_return
    };

    let mut sorted_returns = future_rets.to_vec();
    sorted_returns.sort_by(f64::total_cmp);
    let median_future_return = if count % 2 == 1 {
        sorted_returns[count / 2]
    } else {
        (sorted_returns[count / 2 - 1] + sorted_returns[count / 2]) / 2.0
    };
    let positive_count = future_rets.iter().filter(|value| **value > 0.0).count();
    let sign_consistency = positive_count as f64 / count_f64;
    let best_match_return = future_rets[0];
    let minimum_return = future_rets.iter().copied().fold(f64::INFINITY, f64::min);
    let maximum_drawdown = 0.0f64.max(-minimum_return);

    let minimum_end = match_ends.iter().copied().min().unwrap_or(0);
    let maximum_end = match_ends.iter().copied().max().unwrap_or(0);
    let time_span = maximum_end.saturating_sub(minimum_end) as f64;
    let time_span_ratio = time_span / T_back as f64;

    let mut sorted_ends = match_ends.to_vec();
    sorted_ends.sort_unstable();
    let mut maximum_in_window = 0usize;
    for (index, end) in sorted_ends.iter().enumerate() {
        let upper = end.saturating_add(60);
        let after = sorted_ends.partition_point(|candidate| *candidate <= upper);
        maximum_in_window = maximum_in_window.max(after - index);
    }
    let cluster_ratio = maximum_in_window as f64 / count_f64;
    let matches_above_threshold = scores.iter().filter(|score| **score > 0.8).count() as f64;

    [
        top1_similarity,
        top5_average,
        similarity_decay,
        similarity_variance,
        distance_ratio,
        average_future_return,
        weighted_future_return,
        median_future_return,
        sign_consistency,
        best_match_return,
        maximum_drawdown,
        time_span,
        time_span_ratio,
        cluster_ratio,
        matches_above_threshold,
    ]
}

/// 严格校验长度与回看窗口的特征计算版本。
pub fn compute_features_checked(
    scores: &[f64],
    future_rets: &[f64],
    match_ends: &[usize],
    t_back: usize,
) -> Result<[f64; 15], InputError> {
    if scores.is_empty() {
        return Err(InputError::EmptySequence);
    }
    if scores.len() != future_rets.len() {
        return Err(InputError::LengthMismatch {
            a: scores.len(),
            b: future_rets.len(),
        });
    }
    if scores.len() != match_ends.len() {
        return Err(InputError::LengthMismatch {
            a: scores.len(),
            b: match_ends.len(),
        });
    }
    if t_back == 0 {
        return Err(InputError::InvalidWindow);
    }
    Ok(compute_features(scores, future_rets, match_ends, t_back))
}

pub(crate) fn compare_scores(
    left_score: f64,
    left_end: usize,
    right_score: f64,
    right_end: usize,
) -> Ordering {
    score_order(left_score, left_end, right_score, right_end)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::test_support::{read_fixture, string_array};

    #[test]
    fn feature_keys_match_golden_constant() {
        let json = read_fixture("constants.json");
        let expected = string_array(&json, "FEATURE_KEYS");
        assert_eq!(FEATURE_KEYS.as_slice(), expected.as_slice());
    }

    #[test]
    fn deterministic_sort_handles_ties_and_nan_returns() {
        let mut scored = vec![
            (0.9, 0.1, 20),
            (0.9 + 1e-13, 0.2, 10),
            (f64::NAN, 0.3, 5),
            (1.0, f64::NAN, 1),
        ];
        let sorted = sort_scored_windows(&mut scored, 10);
        assert_eq!(
            sorted.iter().map(|item| item.2).collect::<Vec<_>>(),
            vec![10, 20, 5]
        );
    }

    #[test]
    fn feature_computation_covers_even_median_and_cluster() {
        let features = compute_features(&[1.0, 0.5], &[0.2, -0.1], &[10, 80], 100);
        assert_eq!(features[0], 1.0);
        assert_eq!(features[7], 0.05);
        assert_eq!(features[11], 70.0);
        assert_eq!(features[13], 0.5);
    }
}
