use std::fs;
use std::path::{Path, PathBuf};

pub(crate) fn fixture_path(name: &str) -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("tests")
        .join("fixtures")
        .join(name)
}

pub(crate) fn read_fixture(name: &str) -> String {
    fs::read_to_string(fixture_path(name)).expect("fixture should be readable UTF-8")
}

pub(crate) fn fixture_names(prefix: &str) -> Vec<String> {
    let directory = Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("tests")
        .join("fixtures");
    let mut names: Vec<String> = fs::read_dir(directory)
        .expect("fixtures directory should exist")
        .filter_map(Result::ok)
        .filter_map(|entry| entry.file_name().into_string().ok())
        .filter(|name| name.starts_with(prefix) && name.ends_with(".json"))
        .collect();
    names.sort();
    names
}

fn value_start(json: &str, key: &str) -> usize {
    let marker = format!("\"{key}\"");
    let key_pos = json.find(&marker).expect("fixture key should exist");
    let colon = json[key_pos + marker.len()..]
        .find(':')
        .map(|offset| key_pos + marker.len() + offset)
        .expect("fixture key should have a value");
    json[colon + 1..]
        .find(|character: char| !character.is_whitespace())
        .map(|offset| colon + 1 + offset)
        .expect("fixture value should not be empty")
}

fn balanced_end(json: &str, start: usize, open: u8, close: u8) -> usize {
    let bytes = json.as_bytes();
    let mut depth = 0usize;
    let mut in_string = false;
    let mut escaped = false;
    for (index, byte) in bytes.iter().enumerate().skip(start) {
        if in_string {
            if escaped {
                escaped = false;
            } else if *byte == b'\\' {
                escaped = true;
            } else if *byte == b'"' {
                in_string = false;
            }
            continue;
        }
        if *byte == b'"' {
            in_string = true;
        } else if *byte == open {
            depth += 1;
        } else if *byte == close {
            depth -= 1;
            if depth == 0 {
                return index + 1;
            }
        }
    }
    panic!("unterminated JSON value")
}

pub(crate) fn value<'a>(json: &'a str, key: &str) -> &'a str {
    let start = value_start(json, key);
    let bytes = json.as_bytes();
    let end = match bytes[start] {
        b'[' => balanced_end(json, start, b'[', b']'),
        b'{' => balanced_end(json, start, b'{', b'}'),
        _ => json[start..]
            .find([',', '}', '\n', '\r'])
            .map(|offset| start + offset)
            .unwrap_or(json.len()),
    };
    json[start..end].trim()
}

pub(crate) fn f64_value(json: &str, key: &str) -> f64 {
    value(json, key)
        .parse()
        .expect("fixture value should be f64")
}

pub(crate) fn usize_value(json: &str, key: &str) -> usize {
    value(json, key)
        .parse()
        .expect("fixture value should be usize")
}

pub(crate) fn f64_array(json: &str, key: &str) -> Vec<f64> {
    let raw = value(json, key);
    raw[1..raw.len() - 1]
        .split(',')
        .filter_map(|part| {
            let part = part.trim();
            (!part.is_empty()).then(|| part.parse().expect("array item should be f64"))
        })
        .collect()
}

pub(crate) fn string_array(json: &str, key: &str) -> Vec<String> {
    let raw = value(json, key);
    raw[1..raw.len() - 1]
        .split(',')
        .map(|part| part.trim().trim_matches('"').to_string())
        .filter(|part| !part.is_empty())
        .collect()
}

pub(crate) fn close(actual: f64, expected: f64, abs_tol: f64, rel_tol: f64) -> bool {
    (actual - expected).abs() <= abs_tol + rel_tol * actual.abs().max(expected.abs())
}
