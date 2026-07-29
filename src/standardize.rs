use crate::types::{first_non_finite, InputError};

/// 按 C++ 原版顺序计算对数收益率、去均值并标准化。
pub fn standardize_returns(prices: &[f64]) -> Vec<f64> {
    if prices.len() < 2 || first_non_finite(prices).is_some() {
        return Vec::new();
    }

    let mut returns = Vec::with_capacity(prices.len() - 1);
    for pair in prices.windows(2) {
        let previous = pair[0].max(1e-12);
        let current = pair[1].max(1e-12);
        returns.push((current / previous).ln());
    }

    let mean = returns.iter().sum::<f64>() / returns.len() as f64;
    for value in &mut returns {
        *value -= mean;
    }

    let square_sum = returns.iter().map(|value| value * value).sum::<f64>();
    let standard_deviation = (square_sum / returns.len() as f64).sqrt();
    if standard_deviation >= 1e-12 {
        for value in &mut returns {
            *value /= standard_deviation;
        }
    }
    returns
}

/// 提供需要显式错误信息的内部/上层调用版本。
pub fn standardize_returns_checked(prices: &[f64]) -> Result<Vec<f64>, InputError> {
    if prices.is_empty() {
        return Err(InputError::EmptySequence);
    }
    if let Some(index) = first_non_finite(prices) {
        return Err(InputError::NonFinite { index });
    }
    Ok(standardize_returns(prices))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::test_support::{close, f64_array, fixture_names, read_fixture};

    #[test]
    fn test_standardize_against_golden() {
        for name in fixture_names("standardize_") {
            let json = read_fixture(&name);
            let input = f64_array(&json, "input");
            let expected = f64_array(&json, "output");
            let actual = standardize_returns(&input);
            assert_eq!(actual.len(), expected.len(), "{name}");
            for (index, (left, right)) in actual.iter().zip(&expected).enumerate() {
                assert!(
                    close(*left, *right, 1e-10, 1e-12),
                    "{name}[{index}]: {left} != {right}"
                );
            }
        }
    }

    #[test]
    fn rejects_non_finite_window() {
        assert!(standardize_returns(&[1.0, f64::NAN, 2.0]).is_empty());
        assert_eq!(
            standardize_returns_checked(&[1.0, f64::INFINITY]),
            Err(InputError::NonFinite { index: 1 })
        );
    }
}
