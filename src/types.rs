use std::error::Error;
use std::fmt::{Display, Formatter};

/// 单次形态匹配的纯 Rust 结果。
#[derive(Clone, Debug, PartialEq)]
pub struct MatchResult {
    pub features: [f64; 15],
    pub top_k_scores: Vec<f64>,
    pub match_end_indices: Vec<usize>,
}

/// 排序阶段使用的候选窗口。
#[derive(Clone, Debug, PartialEq)]
pub struct ScoredWindow {
    pub score: f64,
    pub future_return: f64,
    pub end_idx: usize,
}

/// 批量匹配的借用式输入，避免复制价格序列。
#[allow(non_snake_case)]
#[derive(Clone, Copy, Debug)]
pub struct BatchInput<'a> {
    pub prices: &'a [f64],
    pub t_idx: usize,
    pub k: usize,
    pub L_query: usize,
    pub T_back: usize,
    pub match_step: usize,
    pub M_forward: usize,
    pub dtw_window: usize,
    pub cos_prefilter_top: usize,
}

/// 纯 Rust 核心统一输入错误。
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum InputError {
    EmptySequence,
    LengthMismatch { a: usize, b: usize },
    NonFinite { index: usize },
    IndexOutOfRange,
    InvalidWindow,
}

impl Display for InputError {
    fn fmt(&self, f: &mut Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::EmptySequence => write!(f, "sequence must not be empty"),
            Self::LengthMismatch { a, b } => {
                write!(f, "sequence lengths differ: {a} vs {b}")
            }
            Self::NonFinite { index } => write!(f, "non-finite value at index {index}"),
            Self::IndexOutOfRange => write!(f, "index is out of range"),
            Self::InvalidWindow => write!(f, "window or matching parameter is invalid"),
        }
    }
}

impl Error for InputError {}

pub(crate) fn first_non_finite(values: &[f64]) -> Option<usize> {
    values.iter().position(|value| !value.is_finite())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn input_error_has_stable_message() {
        assert_eq!(
            InputError::LengthMismatch { a: 2, b: 3 }.to_string(),
            "sequence lengths differ: 2 vs 3"
        );
    }
}
