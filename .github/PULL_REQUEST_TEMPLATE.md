## Description

<!-- What does this PR do? -->

## Checklist

- [ ] `cargo test --release` passes
- [ ] `cargo fmt --all -- --check` passes
- [ ] `cargo clippy --all-targets --all-features -- -D warnings` passes
- [ ] `PYTHONIOENCODING=utf-8 python -m pytest tests/ -v` passes
- [ ] `python verify_etf_core.py` passes
- [ ] `python verify_batch.py` passes
- [ ] Wheel builds with `maturin build --release --out dist`
- [ ] Wheel content does not include reference code or fixtures
- [ ] `src/` does not contain `unwrap()` / `expect()` in public code

## Related

<!-- Link related issues or NRR entries -->
