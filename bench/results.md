# Benchmark results

Measured 2026-09-29 on a Windows laptop (AMD, 12 threads). Commands are shown above each table.

## Real data: DBLP-ACM (labelled), fuzzy-dedupe vs RapidFuzz

`python bench/rapidfuzz_compare.py --dblp-acm`

DBLP-ACM: 2,616 DBLP titles, 2,294 ACM titles, 2,224 true matches (Köpcke, Thor, Rahm, PVLDB 2010). Matching on title only.

| Threshold | Pairs found | Precision | Recall | F1 | fuzzy-dedupe | RapidFuzz `cdist` | Same pairs |
|---:|---:|---:|---:|---:|---:|---:|:---:|
| 0.0 | 2,217 | 0.885 | 0.883 | 0.884 | 7 ms | 56 ms | yes |
| 0.05 | 2,384 | 0.876 | 0.939 | 0.906 | 8 ms | 63 ms | yes |
| 0.1 | 2,406 | 0.876 | 0.947 | 0.910 | 16 ms | 62 ms | yes |
| 0.15 | 2,433 | 0.874 | 0.956 | 0.913 | 30 ms | 63 ms | yes |
| 0.2 | 2,466 | 0.869 | 0.964 | 0.914 | 62 ms | 66 ms | yes |
| 0.3 | 2,556 | 0.849 | 0.976 | 0.908 | 151 ms | 77 ms | yes |

## Real data: Companies House names, fuzzy-dedupe vs RapidFuzz, all threads

`python bench/rapidfuzz_compare.py --sizes 10000 50000 100000 800000 --rapidfuzz-limit 100000`

fuzzy-dedupe 0.3.0, RapidFuzz 3.14.6. AMD64 Family 25 Model 33 Stepping 2, AuthenticAMD, 12 thread(s), Python 3.13.15, Windows. Companies House names, threshold 0.1.

| Names | Pairs | RapidFuzz `cdist` | fuzzy-dedupe | Speed-up | Same pairs |
|---:|---:|---:|---:|---:|:---:|
| 10,000 | 226 | 634 ms | 28 ms | 22.3x | yes |
| 50,000 | 5,646 | 16.04 s | 459 ms | 35.0x | yes |
| 100,000 | 21,513 | 61.17 s | 1.72 s | 35.6x | yes |
| 800,000 | 1,383,297 | skipped | 258.83 s | | |

## Same, one thread each

`python bench/rapidfuzz_compare.py --sizes 10000 --threads 1`

fuzzy-dedupe 0.3.0, RapidFuzz 3.14.6. AMD64 Family 25 Model 33 Stepping 2, AuthenticAMD, 1 thread(s), Python 3.13.15, Windows. Companies House names, threshold 0.1.

| Names | Pairs | RapidFuzz `cdist` | fuzzy-dedupe | Speed-up | Same pairs |
|---:|---:|---:|---:|---:|:---:|
| 10,000 | 226 | 2.89 s | 168 ms | 17.2x | yes |

## Synthetic names, pure Python vs Rust strategies

`python bench/bench.py 3000 20000 100000`

Machine: AMD64 Family 25 Model 33 Stepping 2, AuthenticAMD, 12 thread(s), Python 3.13.15, Windows. Threshold 0.2.

| Names | Pairs found | Pure Python | Rust, all pairs | Rust, PASS-JOIN index | Index vs all pairs |
|---:|---:|---:|---:|---:|---:|
| 3,000 | 1,787 | 168.29 s | 24 ms | 10 ms | 2.3x |
| 20,000 | 24,547 | skipped | 1.29 s | 216 ms | 5.9x |
| 100,000 | 422,674 | skipped | 27.11 s | 3.55 s | 7.6x |
