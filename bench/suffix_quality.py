"""Does `strip_suffixes` help? Precision, recall and F1 on a labelled registry benchmark.

    python bench/suffix_quality.py --n 50000

Ground truth is built the standard way (as in Febrl): take real Companies House
names as distinct entities, add messy copies of a known share of them, and
record which rows are copies of the same entity. The copies change case,
spacing and punctuation, make typos, and swap or drop the legal form
("Ltd" <-> "Limited", dropped entirely). Real registry names are all distinct,
but many are lexically close to each other, so false positives are realistic.
"""

from __future__ import annotations

import argparse
import random
import sys
from itertools import combinations
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from real_data import companies_house  # noqa: E402

from fuzzy_dedupe import find_duplicates  # noqa: E402

p = argparse.ArgumentParser()
p.add_argument("--n", type=int, default=50000)
p.add_argument("--dup-share", type=float, default=0.2)
args = p.parse_args()

FORMS = ["Ltd", "Ltd.", "Limited", "LIMITED", "LTD", ""]


def variant(name: str, rng: random.Random) -> str:
    words = name.split()
    if len(words) > 1 and words[-1].strip(".").lower() in {"ltd", "limited", "plc", "llp"} and rng.random() < 0.7:
        form = rng.choice(FORMS)
        words = words[:-1] + ([form] if form else [])
    out = " ".join(words)
    r = rng.random()
    if r < 0.35 and len(out) > 3:
        chars = list(out)
        k = rng.randrange(len(chars))
        op = rng.choice(("drop", "swap", "double"))
        if op == "drop":
            del chars[k]
        elif op == "swap" and k + 1 < len(chars):
            chars[k], chars[k + 1] = chars[k + 1], chars[k]
        else:
            chars.insert(k, chars[k])
        out = "".join(chars)
    elif r < 0.6:
        out = out.title() if rng.random() < 0.5 else out.lower()
    elif r < 0.75:
        out = "  " + out.replace(" ", "  ") + " "
    return out


def main() -> None:
    rng = random.Random(11)  # NOSONAR: reproducible benchmark data
    base = companies_house(args.n, seed=5)
    rows: list[str] = []
    entity: list[int] = []
    for e, name in enumerate(base):
        rows.append(name)
        entity.append(e)
        if rng.random() < args.dup_share:
            for _ in range(rng.choice((1, 1, 2))):
                rows.append(variant(name, rng))
                entity.append(e)
    groups: dict[int, list[int]] = {}
    for i, e in enumerate(entity):
        groups.setdefault(e, []).append(i)
    truth = {pair for g in groups.values() for pair in combinations(sorted(g), 2)}
    print(f"{len(rows):,} rows ({len(base):,} real Companies House names plus messy copies), "
          f"{len(truth):,} true duplicate pairs.\n")
    print("| Threshold | strip_suffixes | Pairs found | Precision | Recall | F1 |")
    print("|---:|:---:|---:|---:|---:|---:|")
    for t in (0.05, 0.1, 0.15, 0.2):
        for strip in (False, True):
            found = {(i, j) for i, j, _ in find_duplicates(rows, t, strip_suffixes=strip)}
            tp = len(found & truth)
            prec = tp / len(found) if found else 0.0
            rec = tp / len(truth)
            f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
            print(f"| {t} | {'yes' if strip else 'no'} | {len(found):,} | {prec:.3f} | {rec:.3f} | {f1:.3f} |")


if __name__ == "__main__":
    main()
