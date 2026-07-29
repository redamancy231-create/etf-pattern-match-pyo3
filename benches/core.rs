use std::fs::File;
use std::path::{Path, PathBuf};
use std::time::Duration;

use _core::{
    cosine_similarity, dtw_distance, match_batch, pattern_match, standardize_returns, BatchInput,
};
use criterion::{black_box, criterion_group, criterion_main, BenchmarkId, Criterion};
use ndarray::Array1;
use ndarray_npy::NpzReader;

fn corpus_path(index: usize) -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("benchmarks")
        .join("corpus")
        .join(format!("corpus_{index:02}.npz"))
}

fn load_prices(index: usize) -> Vec<f64> {
    let path = corpus_path(index);
    let file = File::open(&path).unwrap_or_else(|error| {
        panic!(
            "无法读取 {}: {error}。请先运行 python benchmarks/generate_corpus.py",
            path.display()
        )
    });
    let mut npz = NpzReader::new(file).expect("corpus 必须是有效 npz");
    let prices: Array1<f64> = npz
        .by_name("prices.npy")
        .expect("corpus 必须包含一维 f64 prices.npy");
    prices.to_vec()
}

fn dtw_vectors(prices: &[f64], length: usize) -> (Vec<f64>, Vec<f64>) {
    let window = length + 1;
    assert!(prices.len() >= window * 2);
    let x = standardize_returns(&prices[prices.len() - window..]);
    let y = standardize_returns(&prices[prices.len() - window * 2..prices.len() - window]);
    assert_eq!(x.len(), length);
    assert_eq!(y.len(), length);
    (x, y)
}

fn batch_indices(length: usize, l_query: usize) -> Vec<usize> {
    let first = ((length - 1) * 3 / 4).max(l_query + 15);
    (0..100)
        .map(|index| first + index * (length - 1 - first) / 99)
        .collect()
}

fn bench_core(c: &mut Criterion) {
    let short_prices = load_prices(0);
    let long_prices = load_prices(10);
    let batch_prices = load_prices(19);
    let (dtw19_x, dtw19_y) = dtw_vectors(&short_prices, 19);
    let (dtw60_x, dtw60_y) = dtw_vectors(&long_prices, 60);

    let mut primitives = c.benchmark_group("core_primitives");
    primitives.bench_function(BenchmarkId::new("dtw", "L19"), |b| {
        b.iter(|| dtw_distance(black_box(&dtw19_x), black_box(&dtw19_y), black_box(5)))
    });
    primitives.bench_function(BenchmarkId::new("dtw", "L60"), |b| {
        b.iter(|| dtw_distance(black_box(&dtw60_x), black_box(&dtw60_y), black_box(5)))
    });
    primitives.bench_function(BenchmarkId::new("cosine", "L19"), |b| {
        b.iter(|| cosine_similarity(black_box(&dtw19_x), black_box(&dtw19_y)))
    });
    primitives.bench_function(BenchmarkId::new("standardize", "L19"), |b| {
        b.iter(|| standardize_returns(black_box(&short_prices[..20])))
    });
    primitives.finish();

    let mut patterns = c.benchmark_group("core_pattern_match");
    let t_idx = long_prices.len() - 1;
    patterns.bench_function("single_L60_len2000", |b| {
        b.iter(|| {
            pattern_match(
                black_box(&long_prices),
                black_box(t_idx),
                black_box(10),
                black_box(60),
                black_box(750),
                black_box(1),
                black_box(5),
                black_box(5),
                black_box(50),
            )
        })
    });

    let t_indices = batch_indices(batch_prices.len(), 60);
    let inputs: Vec<BatchInput<'_>> = t_indices
        .iter()
        .map(|&index| BatchInput {
            prices: &batch_prices,
            t_idx: index,
            k: 10,
            L_query: 60,
            T_back: 750,
            match_step: 1,
            M_forward: 5,
            dtw_window: 5,
            cos_prefilter_top: 50,
        })
        .collect();
    patterns.bench_function("batch_100_L60_len4000", |b| {
        b.iter(|| match_batch(black_box(&inputs)))
    });
    patterns.finish();
}

criterion_group! {
    name = benches;
    config = Criterion::default()
        .sample_size(100)
        .warm_up_time(Duration::from_secs(1))
        .measurement_time(Duration::from_secs(3));
    targets = bench_core
}
criterion_main!(benches);
