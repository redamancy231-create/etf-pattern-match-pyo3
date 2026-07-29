use crate::types::{first_non_finite, InputError};

/// 使用 Sakoe-Chiba 带与双行滚动数组计算兼容版 DTW 距离。
pub fn dtw_distance(x: &[f64], y: &[f64], window: usize) -> f64 {
    let n = x.len();
    let m = y.len();
    if n == 0 || m == 0 {
        return f64::INFINITY;
    }

    let band = window.max(n.abs_diff(m));
    let mut previous = vec![f64::INFINITY; m + 1];
    let mut current = vec![f64::INFINITY; m + 1];
    previous[0] = 0.0;

    for i in 1..=n {
        let start = 1usize.max(i.saturating_sub(band));
        let end = m.min(i.saturating_add(band));
        for j in start..=end {
            let difference = x[i - 1] - y[j - 1];
            let cost = difference * difference;
            let vertical = if (i - 1).abs_diff(j) <= band {
                previous[j]
            } else {
                f64::INFINITY
            };
            let horizontal = if j > start {
                current[j - 1]
            } else {
                f64::INFINITY
            };
            let diagonal = previous[j - 1];
            current[j] = cost + vertical.min(horizontal).min(diagonal);
        }
        std::mem::swap(&mut previous, &mut current);
        // C++ 原版的关键修复：交换后第 0 列必须重新设为无穷大。
        previous[0] = f64::INFINITY;
    }

    previous[m].sqrt() / (n + m) as f64
}

/// 严格校验输入的 DTW 版本。
pub fn dtw_distance_checked(x: &[f64], y: &[f64], window: usize) -> Result<f64, InputError> {
    if x.is_empty() || y.is_empty() {
        return Err(InputError::EmptySequence);
    }
    if let Some(index) = first_non_finite(x) {
        return Err(InputError::NonFinite { index });
    }
    if let Some(index) = first_non_finite(y) {
        return Err(InputError::NonFinite { index });
    }
    Ok(dtw_distance(x, y, window))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::test_support::{
        close, f64_array, f64_value, fixture_names, read_fixture, usize_value,
    };

    #[test]
    fn test_dtw_against_golden() {
        for name in fixture_names("dtw_") {
            let json = read_fixture(&name);
            let x = f64_array(&json, "x");
            let y = f64_array(&json, "y");
            let window = usize_value(&json, "window");
            let expected = f64_value(&json, "output");
            let actual = dtw_distance(&x, &y, window);
            assert!(
                close(actual, expected, 1e-8, 1e-12),
                "{name}: {actual} != {expected}"
            );
        }
    }

    #[test]
    fn handles_empty_and_unequal_sequences() {
        assert!(dtw_distance(&[], &[1.0], 5).is_infinite());
        let left = dtw_distance(&[1.0, 2.0], &[1.0, 1.5, 2.0], 0);
        let right = dtw_distance(&[1.0, 1.5, 2.0], &[1.0, 2.0], 0);
        assert!(close(left, right, 1e-12, 1e-12));
    }
}
