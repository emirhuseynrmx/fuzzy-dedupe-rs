## All threads

Machine: AMD64 Family 25 Model 33 Stepping 2, AuthenticAMD, 12 thread(s), Python 3.13.15, Windows. Threshold 0.2.

| Names | Pairs found | Pure Python | Rust, all pairs | Rust, PASS-JOIN index | Index vs all pairs |
|---:|---:|---:|---:|---:|---:|
| 3,000 | 1,787 | 156.93 s | 55 ms | 18 ms | 3.1x |
| 20,000 | 24,547 | skipped | 2.14 s | 243 ms | 8.8x |
| 100,000 | 422,674 | skipped | 48.08 s | 5.75 s | 8.4x |

## One thread (RAYON_NUM_THREADS=1)

Machine: AMD64 Family 25 Model 33 Stepping 2, AuthenticAMD, 1 thread(s), Python 3.13.15, Windows. Threshold 0.2.

| Names | Pairs found | Pure Python | Rust, all pairs | Rust, PASS-JOIN index | Index vs all pairs |
|---:|---:|---:|---:|---:|---:|
| 3,000 | 1,787 | skipped | 312 ms | 41 ms | 7.6x |
| 20,000 | 24,547 | skipped | 14.11 s | 1.36 s | 10.4x |

Measured 2026-09-29 with `python bench/bench.py 3000 20000 100000` and `python bench/bench.py --threads 1 3000 20000 --python-limit 0`.
