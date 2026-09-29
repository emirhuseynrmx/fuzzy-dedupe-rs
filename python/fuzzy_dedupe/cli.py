"""Command line: find duplicate names in a CSV column.

    fuzzy-dedupe customers.csv --column name
    fuzzy-dedupe customers.csv --column name --threshold 0.15 --token-sort --groups -o groups.csv
    fuzzy-dedupe crm.csv --column name --link invoices.csv --link-column customer

Pairs mode writes one row per duplicate pair; `--groups` writes one row per
input row that belongs to a group, with a group number; `--link` matches the
rows of one file against another. Standard library only.
"""

from __future__ import annotations

import argparse
import csv
import sys
import time

from . import __version__, cluster, find_duplicates, link


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="fuzzy-dedupe", description="Find near-duplicate names in a CSV column.")
    p.add_argument("csv", help="input CSV file (UTF-8)")
    p.add_argument("--column", required=True, help="column with the names")
    p.add_argument("--threshold", type=float, default=0.2, help="max edit distance / longer length (default 0.2)")
    p.add_argument("--token-sort", action="store_true", help="ignore word order ('Ltd Acme' == 'Acme Ltd')")
    p.add_argument("--groups", action="store_true", help="output groups instead of pairs")
    p.add_argument("--link", metavar="OTHER_CSV", help="match against the rows of another CSV instead of deduplicating")
    p.add_argument("--link-column", help="column in OTHER_CSV (default: same as --column)")
    p.add_argument("-o", "--output", help="output CSV (default: stdout)")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    args = p.parse_args(argv)

    # Reading the file the user names is this tool's whole job.
    with open(args.csv, newline="", encoding="utf-8-sig") as f:  # NOSONAR
        rows = list(csv.DictReader(f))
    if rows and args.column not in rows[0]:
        p.error(f"column {args.column!r} not found; columns are {list(rows[0])}")
    names = [(r.get(args.column) or "") for r in rows]
    other: list[str] = []
    if args.link:
        other_col = args.link_column or args.column
        with open(args.link, newline="", encoding="utf-8-sig") as f:  # NOSONAR: user-chosen input path
            other_rows = list(csv.DictReader(f))
        if other_rows and other_col not in other_rows[0]:
            p.error(f"column {other_col!r} not found in {args.link}; columns are {list(other_rows[0])}")
        other = [(r.get(other_col) or "") for r in other_rows]

    start = time.perf_counter()
    if not args.output and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # names are UTF-8; don't let a Windows console mangle them
    out = open(args.output, "w", newline="", encoding="utf-8") if args.output else sys.stdout  # NOSONAR: user-chosen output path
    try:
        w = csv.writer(out)
        if args.link:
            pairs = link(names, other, args.threshold, token_sort=args.token_sort)
            w.writerow(["row", "other_row", "name", "other_name", "score"])
            for i, j, s in pairs:
                w.writerow([i + 1, j + 1, names[i], other[j], f"{s:.4f}"])
            found = f"{len(pairs):,} matches against {len(other):,} rows"
        elif args.groups:
            groups = cluster(names, args.threshold, token_sort=args.token_sort)
            w.writerow(["group", "row", args.column])
            for g, members in enumerate(groups, 1):
                for i in members:
                    w.writerow([g, i + 1, names[i]])
            found = f"{len(groups):,} groups"
        else:
            pairs = find_duplicates(names, args.threshold, token_sort=args.token_sort)
            w.writerow(["row_a", "row_b", "name_a", "name_b", "score"])
            for i, j, s in pairs:
                w.writerow([i + 1, j + 1, names[i], names[j], f"{s:.4f}"])
            found = f"{len(pairs):,} pairs"
    finally:
        if args.output:
            out.close()
    print(f"{len(names):,} names, {found}, {time.perf_counter() - start:.2f} s", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
