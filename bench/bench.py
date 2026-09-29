"""Time every strategy on the same names and check they agree.

    python bench/bench.py                    # 3,000 names, includes pure Python
    python bench/bench.py 20000 100000       # bigger lists, Rust only
    python bench/bench.py --threads 1 3000   # pin rayon to one thread (set before import)

Prints a Markdown table. The numbers in the README come from this script.
"""

from __future__ import annotations

import argparse
import os
import platform
import sys
import time
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("sizes", nargs="*", type=int, default=[3000])
parser.add_argument("--threshold", type=float, default=0.2)
parser.add_argument("--threads", type=int, default=None)
parser.add_argument("--python-limit", type=int, default=5000, help="skip pure Python above this size")
args = parser.parse_args()
if args.threads:
    os.environ["RAYON_NUM_THREADS"] = str(args.threads)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from data import names as make_names  # noqa: E402

from fuzzy_dedupe import find_duplicates, find_duplicates_python  # noqa: E402


def timed(fn, *a, **kw):
    start = time.perf_counter()
    out = fn(*a, **kw)
    return out, time.perf_counter() - start


def fmt(t: float) -> str:
    return f"{t:.2f} s" if t >= 1 else f"{t * 1000:.0f} ms"


def main() -> None:
    cores = args.threads or os.cpu_count()
    print(f"Machine: {platform.processor() or platform.machine()}, {cores} thread(s), "
          f"Python {platform.python_version()}, {platform.system()}. Threshold {args.threshold}.\n")
    print("| Names | Pairs found | Pure Python | Rust, all pairs | Rust, PASS-JOIN index | Index vs all pairs |")
    print("|---:|---:|---:|---:|---:|---:|")
    for n in args.sizes:
        ns = make_names(n)
        indexed, t_idx = timed(find_duplicates, ns, args.threshold, method="indexed")
        brute, t_brute = timed(find_duplicates, ns, args.threshold, method="brute")
        assert indexed == brute, "index and brute force disagree"
        py = "skipped"
        if n <= args.python_limit:
            ref, t_py = timed(find_duplicates_python, ns, args.threshold)
            assert ref == brute, "Rust and Python disagree"
            py = fmt(t_py)
        print(f"| {n:,} | {len(brute):,} | {py} | {fmt(t_brute)} | {fmt(t_idx)} | {t_brute / t_idx:.1f}x |")


if __name__ == "__main__":
    main()
