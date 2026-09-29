"""fuzzy-dedupe against RapidFuzz on the same rule, and a quality check on DBLP-ACM.

    pip install rapidfuzz numpy
    python bench/rapidfuzz_compare.py                         # Companies House samples
    python bench/rapidfuzz_compare.py --sizes 10000 50000 --threads 1
    python bench/rapidfuzz_compare.py --dblp-acm              # precision / recall on a labelled benchmark

Both tools compute the same number: Levenshtein distance divided by the longer
string's length (RapidFuzz's `Levenshtein.normalized_distance` with default
weights), on the same normalized strings. RapidFuzz scores every pair with
`process.cdist` in row chunks; fuzzy-dedupe skips pairs its PASS-JOIN index
proves can't match. The script checks that both return the same pairs.
"""

from __future__ import annotations

import argparse
import os
import platform
import sys
import time
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--sizes", nargs="*", type=int, default=[10000, 50000, 100000])
parser.add_argument("--threshold", type=float, default=0.1)
parser.add_argument("--threads", type=int, default=None, help="threads for both tools (default: all)")
parser.add_argument("--rapidfuzz-limit", type=int, default=100000, help="skip RapidFuzz above this size")
parser.add_argument("--dblp-acm", action="store_true")
args = parser.parse_args()
if args.threads:
    os.environ["RAYON_NUM_THREADS"] = str(args.threads)

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np  # noqa: E402
from rapidfuzz import __version__ as rf_version  # noqa: E402
from rapidfuzz import process  # noqa: E402
from rapidfuzz.distance import Levenshtein  # noqa: E402
from real_data import companies_house, dblp_acm  # noqa: E402

import fuzzy_dedupe  # noqa: E402
from fuzzy_dedupe import find_duplicates, link  # noqa: E402
from fuzzy_dedupe.reference import normalize  # noqa: E402

WORKERS = args.threads or -1
CHUNK = 2000


def rapidfuzz_pairs(left: list[str], right: list[str] | None, t: float) -> list[tuple[int, int]]:
    """All (i, j) with normalized distance <= t; i < j when deduplicating one list."""
    same = right is None
    right = left if same else right
    out = []
    for start in range(0, len(left), CHUNK):
        block = process.cdist(left[start:start + CHUNK], right, scorer=Levenshtein.normalized_distance,
                              score_cutoff=t, dtype=np.float64, workers=WORKERS)
        rows, cols = np.nonzero(block <= t)
        for r, c in zip(rows.tolist(), cols.tolist()):
            i = start + r
            if not same or i < c:
                out.append((i, c))
    out.sort()
    return out


def timed(fn, *a, **kw):
    start = time.perf_counter()
    res = fn(*a, **kw)
    return res, time.perf_counter() - start


def fmt(t: float) -> str:
    return f"{t:.2f} s" if t >= 1 else f"{t * 1000:.0f} ms"


def speed():
    threads = args.threads or os.cpu_count()
    print(f"fuzzy-dedupe {fuzzy_dedupe.__version__}, RapidFuzz {rf_version}. {platform.processor() or platform.machine()}, "
          f"{threads} thread(s), Python {platform.python_version()}, {platform.system()}. "
          f"Companies House names, threshold {args.threshold}.\n")
    print("| Names | Pairs | RapidFuzz `cdist` | fuzzy-dedupe | Speed-up | Same pairs |")
    print("|---:|---:|---:|---:|---:|:---:|")
    for n in args.sizes:
        raw = companies_house(n)
        cleaned = [normalize(x) for x in raw]
        ours, t_ours = timed(find_duplicates, raw, args.threshold)
        ours_ij = [(i, j) for i, j, _ in ours]
        if n <= args.rapidfuzz_limit:
            theirs, t_rf = timed(rapidfuzz_pairs, cleaned, None, args.threshold)
            same = "yes" if theirs == ours_ij else f"NO ({len(theirs)} vs {len(ours_ij)})"
            print(f"| {n:,} | {len(ours):,} | {fmt(t_rf)} | {fmt(t_ours)} | {t_rf / t_ours:.1f}x | {same} |")
        else:
            print(f"| {n:,} | {len(ours):,} | skipped | {fmt(t_ours)} | | |")


def quality():
    dblp, acm, truth = dblp_acm()
    print(f"DBLP-ACM: {len(dblp):,} DBLP titles, {len(acm):,} ACM titles, {len(truth):,} true matches "
          "(Köpcke, Thor, Rahm, PVLDB 2010). Matching on title only.\n")
    print("| Threshold | Pairs found | Precision | Recall | F1 | fuzzy-dedupe | RapidFuzz `cdist` | Same pairs |")
    print("|---:|---:|---:|---:|---:|---:|---:|:---:|")
    cl_d, cl_a = [normalize(x) for x in dblp], [normalize(x) for x in acm]
    for t in (0.0, 0.05, 0.1, 0.15, 0.2, 0.3):
        ours, t_ours = timed(link, dblp, acm, t)
        found = {(i, j) for i, j, _ in ours}
        theirs, t_rf = timed(rapidfuzz_pairs, cl_d, cl_a, t)
        tp = len(found & truth)
        p = tp / len(found) if found else 0.0
        r = tp / len(truth)
        f1 = 2 * p * r / (p + r) if p + r else 0.0
        same = "yes" if theirs == sorted(found) else "NO"
        print(f"| {t} | {len(found):,} | {p:.3f} | {r:.3f} | {f1:.3f} | {fmt(t_ours)} | {fmt(t_rf)} | {same} |")


if __name__ == "__main__":
    quality() if args.dblp_acm else speed()
