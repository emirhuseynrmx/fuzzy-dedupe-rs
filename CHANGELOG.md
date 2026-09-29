# Changelog

## 0.4.0 — 2026-09-29

- **`Index`**: a persistent, incremental index. `Index.build`, `add`, `query`, `query_many`, `save`, `load`. Answers "which stored names match this one?" without rescanning, with the same exact results as a full comparison, including names added after the index was built.
- **`strip_suffixes=True`**: drops legal forms at the end of a name ("Ltd", "Limited", "LLC", "GmbH", "A.Ş.", "Ltd. Şti."). Available on every function, the `Index` and the CLI (`--strip-suffixes`). Measured on a labelled Companies House benchmark (`bench/suffix_quality.py`).
- **Banded bit-parallel verification** (Hyyrö 2003) for strings over 64 characters when the edit budget fits in one machine word: the case where RapidFuzz used to be faster.
- **Character-frequency lower bound** (Kahveci and Singh, VLDB 2001) rejects far-apart pairs before any dynamic programming.
- The edit budget per length is computed once per search instead of once per pair.
- `stats(names, threshold)`: pairs found, candidate pairs the index verified, and all possible pairs.
- New benchmarks: `bench/index_bench.py`, `bench/suffix_quality.py`.

## 0.3.0 — 2026-09-29

- **License: Apache-2.0** (was MIT).
- `link(left, right)`: exact matching between two lists (PASS-JOIN R-S join), plus `--link` in the CLI.
- Multi-word bit-parallel edit distance (Myers 1999 §5, Hyyrö 2003) for strings over 64 characters.
- Match masks built once per name instead of once per pair.
- `method="auto"` now chooses between the index and all pairs from the data (typical edits per name).
- Real-data benchmarks: Companies House names and the labelled DBLP-ACM set, with RapidFuzz as the baseline; CI checks that both tools return the same pairs.
- Fixed: Rust property tests ignored `PROPTEST_CASES` because the case count was hard-coded.
- CONTRIBUTING, SECURITY, CITATION.cff, NOTICE.

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
