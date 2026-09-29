"""Real datasets for the benchmarks, downloaded on first use into bench/.cache/.

- Companies House (UK), "Basic Company Data", part 1 of 7: real registered
  company names, free to download without an account.
  https://download.companieshouse.gov.uk/en_output.html
- DBLP-ACM (Köpcke, Thor, Rahm, "Evaluation of entity resolution approaches on
  real-world match problems", PVLDB 3(1), 2010): paper titles from two
  bibliographies plus the list of true matches.
  https://dbs.uni-leipzig.de/research/projects/benchmark-datasets-for-entity-resolution
"""

from __future__ import annotations

import csv
import io
import random
import urllib.request
import zipfile
from pathlib import Path

CACHE = Path(__file__).resolve().parent / ".cache"
CH_URL = "https://download.companieshouse.gov.uk/BasicCompanyData-2026-09-01-part1_7.zip"
DBLP_ACM_URL = "https://dbs.uni-leipzig.de/files/datasets/DBLP-ACM.zip"


def _fetch(url: str, name: str) -> Path:
    CACHE.mkdir(exist_ok=True)
    path = CACHE / name
    if not path.exists():
        print(f"downloading {url} ...", flush=True)
        req = urllib.request.Request(url, headers={"User-Agent": "fuzzy-dedupe-benchmark"})
        with urllib.request.urlopen(req, timeout=600) as r, open(path, "wb") as f:  # noqa: S310 - fixed https URLs
            f.write(r.read())
    return path


def companies_house(n: int | None = None, seed: int = 1) -> list[str]:
    """Company names from Companies House part 1; a seeded random sample of `n` if given."""
    path = _fetch(CH_URL, "ch1.zip")
    with zipfile.ZipFile(path) as z, z.open(z.namelist()[0]) as f:
        reader = csv.reader(io.TextIOWrapper(f, encoding="utf-8", errors="replace"))
        next(reader)
        names = [row[0] for row in reader if row]
    if n is not None and n < len(names):
        names = random.Random(seed).sample(names, n)  # NOSONAR: reproducible sample
    return names


def dblp_acm() -> tuple[list[str], list[str], set[tuple[int, int]]]:
    """(DBLP titles, ACM titles, true matches as (dblp_index, acm_index))."""
    path = _fetch(DBLP_ACM_URL, "dblp-acm.zip")
    with zipfile.ZipFile(path) as z:
        def rows(name):
            with z.open(name) as f:
                return list(csv.DictReader(io.TextIOWrapper(f, encoding="latin-1")))
        dblp, acm, gold = rows("DBLP2.csv"), rows("ACM.csv"), rows("DBLP-ACM_perfectMapping.csv")
    d_ix = {r["id"]: i for i, r in enumerate(dblp)}
    a_ix = {r["id"]: i for i, r in enumerate(acm)}
    truth = {(d_ix[g["idDBLP"]], a_ix[g["idACM"]]) for g in gold if g["idDBLP"] in d_ix and g["idACM"] in a_ix}
    return [r["title"] for r in dblp], [r["title"] for r in acm], truth
