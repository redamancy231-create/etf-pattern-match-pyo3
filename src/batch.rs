use rayon::prelude::*;

use crate::pattern_match::pattern_match;
use crate::types::{BatchInput, MatchResult};

/// 并行执行独立匹配；单个输入失败只在对应位置返回 `None`。
pub fn match_batch(inputs: &[BatchInput<'_>]) -> Vec<Option<MatchResult>> {
    inputs
        .par_iter()
        .map(|input| {
            pattern_match(
                input.prices,
                input.t_idx,
                input.k,
                input.L_query,
                input.T_back,
                input.match_step,
                input.M_forward,
                input.dtw_window,
                input.cos_prefilter_top,
            )
            .ok()
            .flatten()
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::test_support::{f64_array, read_fixture};

    #[test]
    fn batch_preserves_order_and_isolates_failures() {
        let json = read_fixture("pattern_match_t500.json");
        let prices = f64_array(&json, "prices");
        let valid = BatchInput {
            prices: &prices,
            t_idx: 500,
            k: 10,
            L_query: 20,
            T_back: 750,
            match_step: 1,
            M_forward: 5,
            dtw_window: 5,
            cos_prefilter_top: 50,
        };
        let invalid = BatchInput {
            t_idx: prices.len(),
            ..valid
        };
        let expected = pattern_match(&prices, 500, 10, 20, 750, 1, 5, 5, 50)
            .expect("serial input should be valid");
        let actual = match_batch(&[valid, invalid]);
        assert_eq!(actual.len(), 2);
        assert_eq!(actual[0], expected);
        assert!(actual[1].is_none());
    }

    #[test]
    fn empty_batch_is_empty() {
        assert!(match_batch(&[]).is_empty());
    }
}
