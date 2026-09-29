3,000 names, 4,498,500 pairs compared, 87,525 duplicates found, threshold 0.2
Machine: AMD64 Family 25 Model 33 Stepping 2, AuthenticAMD, 12 logical cores, Python 3.13.15, Windows

| Version | Time | Speed-up |
|---|---|---|
| Pure Python | 36.21 s | 1x |
| Rust (PyO3 + rayon) | 0.065 s | 560x |

Same run with `RAYON_NUM_THREADS=1` (Rust on one core):

| Version | Time | Speed-up |
|---|---|---|
| Pure Python | 35.92 s | 1x |
| Rust (PyO3, 1 thread) | 0.317 s | 113x |

Measured 2026-09-29 with `python bench/bench.py 3000`.
