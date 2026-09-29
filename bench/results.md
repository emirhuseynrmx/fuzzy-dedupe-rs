# Benchmark results

Measured 2026-09-29 on a Windows laptop (AMD, 12 threads), fuzzy-dedupe 0.4.0. Commands are shown above each table.

## DBLP-ACM (labelled), fuzzy-dedupe vs RapidFuzz

`python bench/rapidfuzz_compare.py --dblp-acm`

DBLP-ACM: 2,616 DBLP titles, 2,294 ACM titles, 2,224 true matches (Köpcke, Thor, Rahm, PVLDB 2010). Matching on title only.

| Threshold | Pairs found | Precision | Recall | F1 | fuzzy-dedupe | RapidFuzz `cdist` | Same pairs |
|---:|---:|---:|---:|---:|---:|---:|:---:|
| 0.0 | 2,217 | 0.885 | 0.883 | 0.884 | 11 ms | 63 ms | yes |
| 0.05 | 2,384 | 0.876 | 0.939 | 0.906 | 9 ms | 55 ms | yes |
| 0.1 | 2,406 | 0.876 | 0.947 | 0.910 | 15 ms | 59 ms | yes |
| 0.15 | 2,433 | 0.874 | 0.956 | 0.913 | 25 ms | 59 ms | yes |
| 0.2 | 2,466 | 0.869 | 0.964 | 0.914 | 54 ms | 61 ms | yes |
| 0.3 | 2,556 | 0.849 | 0.976 | 0.908 | 55 ms | 83 ms | yes |

## Companies House names, fuzzy-dedupe vs RapidFuzz, all threads

`python bench/rapidfuzz_compare.py --sizes 10000 50000 100000 800000 --rapidfuzz-limit 100000`

fuzzy-dedupe 0.4.0, RapidFuzz 3.14.6. AMD64 Family 25 Model 33 Stepping 2, AuthenticAMD, 12 thread(s), Python 3.13.15, Windows. Companies House names, threshold 0.1.

| Names | Pairs | RapidFuzz `cdist` | fuzzy-dedupe | Speed-up | Same pairs |
|---:|---:|---:|---:|---:|:---:|
| 10,000 | 226 | 633 ms | 17 ms | 37.0x | yes |
| 50,000 | 5,646 | 17.15 s | 157 ms | 109.0x | yes |
| 100,000 | 21,513 | 68.21 s | 500 ms | 136.3x | yes |
| 800,000 | 1,383,297 | skipped | 102.54 s | | |

## Same, one thread each

`python bench/rapidfuzz_compare.py --sizes 10000 --threads 1`

fuzzy-dedupe 0.4.0, RapidFuzz 3.14.6. AMD64 Family 25 Model 33 Stepping 2, AuthenticAMD, 1 thread(s), Python 3.13.15, Windows. Companies House names, threshold 0.1.

| Names | Pairs | RapidFuzz `cdist` | fuzzy-dedupe | Speed-up | Same pairs |
|---:|---:|---:|---:|---:|:---:|
| 10,000 | 226 | 2.89 s | 37 ms | 77.7x | yes |

## Persistent index, one query at a time

`python bench/index_bench.py --n 800000 --queries 1000 --rapidfuzz-queries 50`

fuzzy-dedupe 0.4.0, RapidFuzz 3.14.6. AMD64 Family 25 Model 33 Stepping 2, AuthenticAMD, Python 3.13.15, Windows.
800,000 Companies House names, threshold 0.1, messy-copy queries. Index built in 1.1 s.

| | Queries timed | Median per query | 95th percentile | Same results |
|---|---:|---:|---:|:---:|
| fuzzy-dedupe `Index.query` | 1,000 | 0.05 ms | 5.66 ms | |
| RapidFuzz `process.extract` | 50 | 78.70 ms | 89.57 ms | 50/50 |

## strip_suffixes, labelled registry benchmark

`python bench/suffix_quality.py --n 50000`

63,466 rows (50,000 real Companies House names plus messy copies), 16,873 true duplicate pairs.

| Threshold | strip_suffixes | Pairs found | Precision | Recall | F1 |
|---:|:---:|---:|---:|---:|---:|
| 0.05 | no | 7,650 | 0.937 | 0.425 | 0.584 |
| 0.05 | yes | 11,935 | 0.983 | 0.695 | 0.814 |
| 0.1 | no | 16,492 | 0.553 | 0.540 | 0.547 |
| 0.1 | yes | 17,514 | 0.791 | 0.822 | 0.806 |
| 0.15 | no | 54,574 | 0.201 | 0.649 | 0.306 |
| 0.15 | yes | 36,677 | 0.403 | 0.875 | 0.552 |
| 0.2 | no | 191,475 | 0.068 | 0.775 | 0.125 |
| 0.2 | yes | 108,261 | 0.141 | 0.907 | 0.245 |

## Synthetic names, pure Python vs Rust strategies

`python bench/bench.py 3000 20000 100000`

Machine: AMD64 Family 25 Model 33 Stepping 2, AuthenticAMD, 12 thread(s), Python 3.13.15, Windows. Threshold 0.2.

| Names | Pairs found | Pure Python | Rust, all pairs | Rust, PASS-JOIN index | Index vs all pairs |
|---:|---:|---:|---:|---:|---:|
| 3,000 | 1,787 | 148.45 s | 8 ms | 8 ms | 1.0x |
| 20,000 | 24,547 | skipped | 302 ms | 83 ms | 3.6x |
| 100,000 | 422,674 | skipped | 7.93 s | 1.02 s | 7.8x |

## Turkish mode, real Turkish legal names (GLEIF)

`python bench/turkish_quality.py`

13,324 rows (9,992 Turkish legal names from GLEIF plus messy copies), 4,147 true duplicate pairs.

| Threshold | Settings | Pairs found | Precision | Recall | F1 |
|---:|---|---:|---:|---:|---:|
| 0.05 | default | 2,495 | 0.395 | 0.238 | 0.297 |
| 0.05 | strip_suffixes | 2,501 | 0.397 | 0.239 | 0.298 |
| 0.05 | turkish | 4,207 | 0.523 | 0.530 | 0.526 |
| 0.05 | turkish + strip_suffixes | 5,372 | 0.642 | 0.832 | 0.725 |
| 0.05 | turkish + strip_suffixes + numbers_must_match + word_threshold=0.34 | 3,393 | 0.971 | 0.794 | 0.874 |
| 0.1 | default | 17,984 | 0.075 | 0.326 | 0.122 |
| 0.1 | strip_suffixes | 17,996 | 0.076 | 0.329 | 0.123 |
| 0.1 | turkish | 22,577 | 0.106 | 0.577 | 0.179 |
| 0.1 | turkish + strip_suffixes | 21,388 | 0.179 | 0.925 | 0.300 |
| 0.1 | turkish + strip_suffixes + numbers_must_match + word_threshold=0.34 | 3,831 | 0.936 | 0.865 | 0.899 |
| 0.15 | default | 58,927 | 0.034 | 0.490 | 0.064 |
| 0.15 | strip_suffixes | 58,936 | 0.035 | 0.491 | 0.065 |
| 0.15 | turkish | 74,091 | 0.033 | 0.587 | 0.062 |
| 0.15 | turkish + strip_suffixes | 62,986 | 0.063 | 0.950 | 0.117 |
| 0.15 | turkish + strip_suffixes + numbers_must_match + word_threshold=0.34 | 4,050 | 0.903 | 0.882 | 0.893 |
| 0.2 | default | 170,099 | 0.014 | 0.575 | 0.027 |
| 0.2 | strip_suffixes | 170,094 | 0.014 | 0.575 | 0.027 |
| 0.2 | turkish | 197,072 | 0.013 | 0.599 | 0.025 |
| 0.2 | turkish + strip_suffixes | 161,092 | 0.025 | 0.964 | 0.048 |
| 0.2 | turkish + strip_suffixes + numbers_must_match + word_threshold=0.34 | 4,174 | 0.883 | 0.889 | 0.886 |

0.6 changes the `turkish + strip_suffixes` rows (0.678 -> 0.725 F1 at 0.05) by recognising tails with one typo and run-together tails such as `SAN.TİC.A.Ş.`. The last row per threshold adds the pair rules.
