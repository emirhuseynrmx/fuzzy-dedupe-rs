"""A realistic cleanup: check the file first, then find duplicate customers.

    pip install "fuzzy-dedupe[examples]"      # or: pip install proofframe pyarrow pandas
    python examples/clean_customers.py examples/customers.csv

Step 1 uses ProofFrame (https://github.com/emirhuseynrmx/proofframe) to catch
rows that would break or skew the dedupe: missing names, repeated ids.
Step 2 runs find_duplicates on the rows that passed.
"""

from __future__ import annotations

import sys

import proofframe
import pyarrow.csv as pacsv

from fuzzy_dedupe import find_duplicates

# What a usable customer row looks like. ProofFrame reports every row that breaks a rule.
CONTRACT = {
    "version": "proofframe.contract.v2",
    "status": "active",
    "columns": {
        "customer_id": {"type": "int64", "required": True, "not_null": True, "unique": True},
        "name": {"type": "utf8", "required": True, "not_null": True},
    },
}


def main(path: str) -> None:
    # Read with Arrow so column types are the same whatever pandas version is installed.
    # An empty cell is a missing name, not a name that happens to be "".
    table = pacsv.read_csv(path, convert_options=pacsv.ConvertOptions(strings_can_be_null=True))
    report = proofframe.check(table, CONTRACT)
    df = table.to_pandas()
    bad_rows = sorted({f["row"] for f in report["findings"]})
    print(f"Step 1: checked {report['rows']} rows, {report['violation_count']} problems")
    for f in report["findings"]:
        # ProofFrame counts rows from 0; the CSV line adds 2 for the header and 1-based lines.
        print(f"  line {f['row'] + 2} (customer #{df.loc[f['row'], 'customer_id']}): "
              f"{f['column']} - {f['message']}")

    clean = df.drop(index=bad_rows).reset_index(drop=True)
    print(f"\nStep 2: looking for duplicates in the {len(clean)} rows that passed")
    pairs = find_duplicates(clean["name"].tolist(), threshold=0.2)
    for i, j, score in pairs:
        a, b = clean.loc[i], clean.loc[j]
        print(f"  #{a.customer_id} {a['name']!r:<24} ~ #{b.customer_id} {b['name']!r:<24} distance {score:.2f}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "examples/customers.csv")
