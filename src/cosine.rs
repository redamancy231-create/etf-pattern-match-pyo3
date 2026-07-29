use crate::types::{first_non_finite, InputError};

/// 计算余弦相似度；长度不一致或零向量按兼容约定返回 0。
pub fn cosine_similarity(a: &[f64], b: &[f64]) -> f64 {
    if a.len() != b.len() || a.is_empty() {
        return 0.0;
    }

    let mut dot = 0.0;
    let mut norm_a_squared = 0.0;
    let mut norm_b_squared = 0.0;
    for index in 0..a.len() {
        dot += a[index] * b[index];
        norm_a_squared += a[index] * a[index];
        norm_b_squared += b[index] * b[index];
    }

    let norm_a = norm_a_squared.sqrt();
    let norm_b = norm_b_squared.sqrt();
    if norm_a < 1e-12 || norm_b < 1e-12 {
        0.0
    } else {
        dot / (norm_a * norm_b)
    }
}

/// 严格校验输入的余弦相似度版本。
pub fn cosine_similarity_checked(a: &[f64], b: &[f64]) -> Result<f64, InputError> {
    if a.is_empty() || b.is_empty() {
        return Err(InputError::EmptySequence);
    }
    if a.len() != b.len() {
        return Err(InputError::LengthMismatch {
            a: a.len(),
            b: b.len(),
        });
    }
    if let Some(index) = first_non_finite(a) {
        return Err(InputError::NonFinite { index });
    }
    if let Some(index) = first_non_finite(b) {
        return Err(InputError::NonFinite { index });
    }
    Ok(cosine_similarity(a, b))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::test_support::{close, f64_array, f64_value, fixture_names, read_fixture};

    #[test]
    fn test_cosine_against_golden() {
        for name in fixture_names("cosine_") {
            let json = read_fixture(&name);
            let x = f64_array(&json, "x");
            let y = f64_array(&json, "y");
            let expected = f64_value(&json, "output");
            let actual = cosine_similarity(&x, &y);
            assert!(
                close(actual, expected, 1e-12, 1e-12),
                "{name}: {actual} != {expected}"
            );
        }
    }

    #[test]
    fn checked_version_reports_shape_errors() {
        assert_eq!(
            cosine_similarity_checked(&[1.0], &[1.0, 2.0]),
            Err(InputError::LengthMismatch { a: 1, b: 2 })
        );
        assert_eq!(cosine_similarity(&[], &[]), 0.0);
    }
}
