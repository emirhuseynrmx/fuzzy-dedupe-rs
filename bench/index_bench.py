"""Persistent index: build time and per-query latency, against RapidFuzz on the same rule.

    pip install rapidfuzz numpy
    python bench/index_bench.py --n 800000 --queries 1000

Queries are messy copies of stored names (typo, case, spacing, suffix change),
the "is this customer already in the CRM?" case. For every query the script
checks that `Index.query` returns exactly what RapidFuzz's
`process.extract(..., scorer=Levenshtein.normalized_distance, score_cutoff=t, limit=None)`
returns over the whole list, then reports the median and 95th-percentile time
of each. RapidFuzz is timed on a subset of queries because each one scans
every stored name.
"""

from __future__ import annotations

import argparse
import platform
import random
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from data import messy  # noqa: E402
from rapidfuzz import __version__ as rf_version  # noqa: E402
from rapidfuzz import process  # noqa: E402
from rapidfuzz.distance import Levenshtein  # noqa: E402
from real_data import companies_house  # noqa: E402

import fuzzy_dedupe  # noqa: E402
from fuzzy_dedupe import Index  # noqa: E402
from fuzzy_dedupe.reference import normalize  # noqa: E402

p = argparse.ArgumentParser()
p.add_argument("--n", type=int, default=800000)
p.add_argument("--queries", type=int, default=1000)
p.add_argument("--rapidfuzz-queries", type=int, default=50)
p.add_argument("--threshold", type=float, default=0.1)
args = p.parse_args()


def ms(x: float) -> str:
    return f"{x * 1000:.2f} ms" if x < 1 else f"{x:.2f} s"


def main() -> None:
    names = companies_house(args.n)
    rng = random.Random(3)  # NOSONAR: reproducible benchmark queries
    queries = [messy(rng.choice(names), rng) for _ in range(args.queries)]

    start = time.perf_counter()
    idx = Index.build(names, args.threshold)
    build = time.perf_counter() - start

    ours = []
    results = []
    for q in queries:
        s = time.perf_counter()
        results.append(idx.query(q))
        ours.append(time.perf_counter() - s)

    cleaned = [normalize(x) for x in names]
    theirs = []
    same = 0
    for q, got in list(zip(queries, results))[: args.rapidfuzz_queries]:
        s = time.perf_counter()
        hits = process.extract(normalize(q), cleaned, scorer=Levenshtein.normalized_distance,
                               score_cutoff=args.threshold, limit=None)
        theirs.append(time.perf_counter() - s)
        same += sorted(h[2] for h in hits) == [i for i, _ in got]

    p95 = lambda xs: sorted(xs)[max(0, int(len(xs) * 0.95) - 1)]  # noqa: E731
    print(f"fuzzy-dedupe {fuzzy_dedupe.__version__}, RapidFuzz {rf_version}. {platform.processor() or platform.machine()}, "
          f"Python {platform.python_version()}, {platform.system()}.")
    print(f"{len(names):,} Companies House names, threshold {args.threshold}, messy-copy queries. "
          f"Index built in {build:.1f} s.\n")
    print("| | Queries timed | Median per query | 95th percentile | Same results |")
    print("|---|---:|---:|---:|:---:|")
    print(f"| fuzzy-dedupe `Index.query` | {len(ours):,} | {ms(statistics.median(ours))} | {ms(p95(ours))} | |")
    print(f"| RapidFuzz `process.extract` | {len(theirs):,} | {ms(statistics.median(theirs))} | {ms(p95(theirs))} | "
          f"{same}/{len(theirs)} |")


if __name__ == "__main__":
    main()
