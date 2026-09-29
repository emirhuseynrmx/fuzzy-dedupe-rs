# Changelog

## 0.2.0 — 2026-09-29

- PASS-JOIN partition index with the multi-match-aware window: compares only pairs that can match, with results identical to brute force. 8–10x faster than all-pairs from 20,000 names up.
- Bit-parallel edit distance (Myers / Hyyrö) for names up to 64 characters.
- `cluster()`: groups of names linked by duplicate pairs (union-find).
- `token_sort=True`: ignore word order.
- `method="auto" | "indexed" | "brute"`; `levenshtein()`.
- `fuzzy-dedupe` command line tool for CSV files.
- Type stubs (`py.typed`).
- Rust core split from the Python bindings so `cargo test` runs without Python; proptest and Hypothesis property tests.
- CI: actions pinned to commit SHAs, hash-locked test dependencies (wheels only), `uv.lock`, fmt/clippy job, coverage to Codecov.
- Benchmark on realistic company names instead of random strings.

## 0.1.0 — 2026-09-29

- Pure-Python and Rust (PyO3 + rayon) versions of the same all-pairs search.
