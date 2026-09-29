"""Time both versions on the same list and check they agree.

    python bench/bench.py            # 3,000 names
    python bench/bench.py 5000       # any size

Prints a Markdown table. The numbers in the README come from this script.
"""

from __future__ import annotations

import os
import platform
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))

from fuzzy_dedupe import find_duplicates, find_duplicates_python  # noqa: E402
from test_same_answers import messy_list  # noqa: E402


def timed(fn, *args):
    start = time.perf_counter()
    result = fn(*args)
    return result, time.perf_counter() - start


def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 3000
    names = messy_list(n, seed=7)
    threshold = 0.2

    rust, t_rust = timed(find_duplicates, names, threshold)
    python, t_python = timed(find_duplicates_python, names, threshold)
    assert rust == python, "the two versions disagree"

    pairs = n * (n - 1) // 2
    print(f"{n:,} names, {pairs:,} pairs compared, {len(rust):,} duplicates found, threshold {threshold}")
    print(f"Machine: {platform.processor() or platform.machine()}, {os.cpu_count()} logical cores, "
          f"Python {platform.python_version()}, {platform.system()}\n")
    print("| Version | Time | Speed-up |")
    print("|---|---|---|")
    print(f"| Pure Python | {t_python:.2f} s | 1x |")
    print(f"| Rust (PyO3 + rayon) | {t_rust:.3f} s | {t_python / t_rust:.0f}x |")


if __name__ == "__main__":
    main()
