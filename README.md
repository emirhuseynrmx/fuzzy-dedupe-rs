<h1>
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/logo-dark.svg">
    <img src="assets/logo-light.svg" alt="fuzzy-dedupe" width="560">
  </picture>
</h1>

[![CI](https://github.com/emirhuseynrmx/fuzzy-dedupe-rs/actions/workflows/ci.yml/badge.svg)](https://github.com/emirhuseynrmx/fuzzy-dedupe-rs/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/emirhuseynrmx/fuzzy-dedupe-rs/graph/badge.svg)](https://codecov.io/gh/emirhuseynrmx/fuzzy-dedupe-rs)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Find near-duplicate names in a list, "Acme Ltd", "ACME  ltd" and "Acme Ltd." being the same customer, **fast, and with exactly the answers a brute-force search would give.**

The core is Rust, called from Python (PyO3) or from the command line. It combines a partition filter from the similarity-join literature (PASS-JOIN) with bit-parallel edit distance (Myers / Hyyrö), so it compares only the pairs that can possibly match, and compares those in a few machine instructions per character. A plain-Python reference implementation ships alongside it, and the test suite checks that every strategy returns the same pairs as that reference.

## Results

3,000 to 100,000 synthetic company names with shared vocabulary and messy copies ([`bench/data.py`](bench/data.py)), threshold 0.2, on a Windows laptop (AMD, 12 threads, Python 3.13):

| Names | Duplicate pairs | Pure Python | Rust, all pairs | Rust, PASS-JOIN index |
|---:|---:|---:|---:|---:|
| 3,000 | 1,787 | 156.93 s | 55 ms | **18 ms** |
| 20,000 | 24,547 | too slow | 2.14 s | **243 ms** |
| 100,000 | 422,674 | too slow | 48.08 s | **5.75 s** |

On one thread, 3,000 names take 312 ms comparing all pairs and 41 ms with the index. Every row of both tables was checked to return identical pairs across all strategies. Full output and the exact commands are in [`bench/results.md`](bench/results.md); run `python bench/bench.py` to measure your own machine.

Where the speed comes from, in order of size:

1. **Native code with bit-parallel distance:** the same all-pairs loop is roughly 500x faster than Python on one core.
2. **The index:** checking only candidate pairs is 8–10x faster again at 20,000 names and up, and the gap grows with the list.
3. **All cores:** rows are processed in parallel with rayon, with the GIL released.

## Why the answers are exact

A pair is a duplicate when `edit_distance / longer_length <= threshold`, after lowercasing and collapsing spaces. For a longer name of length `L`, that allows at most `k` edits, where `k` is the largest integer with `k / L <= threshold`.

- **Partition filter (PASS-JOIN).** Cut the shorter name into `k + 1` segments. Each edit can disturb at most one segment, so if the two names are within `k` edits, at least one segment survives untouched and appears verbatim in the longer name, shifted by a bounded amount. So every segment is put in a hash index, and only names that share a segment at a compatible position are compared. The position window is PASS-JOIN's multi-match-aware bound, which is proven not to lose pairs. Hash collisions only add candidates, which verification then rejects.
- **Verification.** Each candidate gets the full edit distance and the same float comparison as the Python reference, so the scores match bit for bit.
- **Fallbacks.** Thresholds of 0.5 and above leave segments too short to filter anything, so the search compares all pairs. Names too short to cut into `k + 1` segments are compared directly.

## How it works

| Step | Technique | Source |
|---|---|---|
| Normalize | lowercase, collapse whitespace, optionally sort words (`token_sort`) | |
| Filter | length filter, then PASS-JOIN partition index with the multi-match-aware window | Li, Deng, Wang, Feng. *PASS-JOIN: A Partition-based Method for Similarity Joins.* PVLDB 5(3), 2011. [arXiv:1111.7171](https://arxiv.org/abs/1111.7171) |
| Verify | bit-parallel edit distance for names up to 64 characters, dynamic programming above | Myers. *A fast bit-vector algorithm for approximate string matching based on dynamic programming.* JACM 46(3), 1999. Hyyrö. *Explaining and extending the bit-parallel approximate string matching algorithm of Myers.* Tech. report A-2001-10, University of Tampere, 2001 |
| Group | connected components with union-find (`cluster`) | Papadakis et al. *Blocking and Filtering Techniques for Entity Resolution: A Survey.* ACM CSUR 53(2), 2020. [arXiv:1905.06167](https://arxiv.org/abs/1905.06167) |

## Install

Build from source (Python 3.9+ and a Rust toolchain):

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install maturin
maturin develop --release
```

## Python

```python
from fuzzy_dedupe import find_duplicates, cluster

names = ["Acme Ltd", "ACME  ltd", "Acme Ltd.", "Globex", "Ltd Acme"]

find_duplicates(names, threshold=0.2)
# [(0, 1, 0.0), (0, 2, 0.1111111111111111), (1, 2, 0.1111111111111111)]

find_duplicates(names, threshold=0.2, token_sort=True)   # word order no longer matters
# [(0, 1, 0.0), (0, 2, 0.1111111111111111), (0, 4, 0.0), (1, 2, 0.1111111111111111), (1, 4, 0.0), (2, 4, 0.1111111111111111)]

cluster(names, threshold=0.2, token_sort=True)
# [[0, 1, 2, 4]]
```

- `find_duplicates(names, threshold=0.2, *, token_sort=False, method="auto")` returns `(i, j, score)` with `i < j`, sorted. `score` is the edit distance divided by the longer name's length.
- `cluster(...)` returns groups of two or more positions linked by any chain of pairs.
- `method` is `"auto"`/`"indexed"` (PASS-JOIN) or `"brute"` (all pairs). They return the same result; `"brute"` exists for checking.
- `find_duplicates_python` and `cluster_python` are the pure-Python reference with the same signature (no `method`).

## Command line

```bash
fuzzy-dedupe customers.csv --column name                       # pairs, CSV to stdout
fuzzy-dedupe customers.csv --column name --groups -o groups.csv
fuzzy-dedupe customers.csv --column name --threshold 0.15 --token-sort
```

## A real cleanup: check first, then dedupe

[`examples/clean_customers.py`](examples/clean_customers.py) runs the whole job on a messy customer file. It checks the rows first with [ProofFrame](https://github.com/emirhuseynrmx/proofframe), my data validation library, so a missing name or a repeated id is reported instead of quietly skewing the result, then runs `find_duplicates` on the rows that passed.

```bash
pip install proofframe pyarrow pandas
python examples/clean_customers.py examples/customers.csv
```

```text
Step 1: checked 15 rows, 2 problems
  line 8 (customer #7): name - Null value is not allowed
  line 10 (customer #8): customer_id - Duplicate value detected

Step 2: looking for duplicates in the 13 rows that passed
  #1 'Acme Ltd'               ~ #2 'ACME  ltd'              distance 0.00
  #1 'Acme Ltd'               ~ #3 'Acme Ltd.'              distance 0.11
  #2 'ACME  ltd'              ~ #3 'Acme Ltd.'              distance 0.11
  #9 'Şişecam A.Ş.'           ~ #10 'şişecam a.ş'            distance 0.08
  #12 'Stark Industries'       ~ #13 'Stark Industires'       distance 0.12
```

## When to use something else

- **[RapidFuzz](https://github.com/rapidfuzz/RapidFuzz)** for scoring functions (ratio, partial ratio, Jaro-Winkler) and top-k lookups. It is mature and fast; this project does one thing, an exact thresholded edit-distance self-join, and focuses on not comparing pairs that can't match.
- **[Splink](https://github.com/moj-analytical-services/splink)** or **[dedupe](https://github.com/dedupeio/dedupe)** when records have several fields and you want probabilistic or learned matching.
- **Embedding or LLM-based matching** when duplicates don't look alike as strings ("IBM" vs "International Business Machines").

## Limitations

- One similarity: character edit distance relative to the longer name. No phonetic or semantic matching.
- `cluster` uses transitive closure, so a chain of close names can link two names that are far apart. That is the usual trade-off of connected components; inspect large groups.
- Normalization is Unicode-aware lowercasing plus whitespace collapsing. Python's `str.split()` also treats a few ASCII control characters (`\x1c`–`\x1f`) as whitespace, while Rust doesn't; strip those before matching if your data has them.
- The index keeps every segment of every name in memory, so memory grows with the total length of the names.

## How it is tested

- **Rust** (`cargo test`): property tests with proptest check that bit-parallel distance equals dynamic programming and that the PASS-JOIN index returns exactly the brute-force pairs, on random names and thresholds (2,000 cases each in CI), plus unit tests for the partition and threshold arithmetic.
- **Python** (`pytest`): Hypothesis generates random lists with case, spacing and non-ASCII characters and checks that `auto`, `indexed` and `brute` all equal the Python reference, for pairs and clusters, at thresholds from 0 to 1, with and without `token_sort`. The CLI is tested end to end.
- **CI** runs both on Linux, macOS and Windows with Python 3.9 and 3.13, builds wheels for all three, runs `cargo fmt`, `clippy -D warnings` and coverage. Actions are pinned to commit SHAs and test dependencies are installed from a hash-locked file, wheels only.

## Layout

```
src/core.rs                      Algorithms: normalize, bit-parallel distance, PASS-JOIN, clusters
src/lib.rs                       Python bindings (feature "python")
python/fuzzy_dedupe/reference.py Pure-Python reference
python/fuzzy_dedupe/cli.py       Command line
tests/                           Python property and CLI tests
bench/                           Data generator, timing script, results
examples/clean_customers.py      Check a CSV with ProofFrame, then dedupe it
```

## License

MIT
