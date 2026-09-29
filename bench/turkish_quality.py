"""Turkish mode on real Turkish company names: precision, recall and F1.

    python bench/turkish_quality.py

Names: the first 10,000 Turkish legal entities the GLEIF LEI API returns (legal
names as registered, CC0), downloaded once into bench/.cache/. Ground truth is built the
standard way (as in Febrl): each real name is a distinct entity, and a known
share get messy copies of the kinds Turkish data entry produces:

- typed without Turkish letters ("TEKSTİL" -> "TEKSTIL", "ŞİRKETİ" -> "SIRKETI")
- different case ("Abc Tekstil" / "abc tekstil")
- the legal tail abbreviated or dropped ("SANAYİ VE TİCARET ANONİM ŞİRKETİ" ->
  "SAN. VE TİC. A.Ş." / "SAN.TİC.A.Ş." / "A.Ş." / nothing)
- one typo, or extra spaces
"""

from __future__ import annotations

import json
import random
import re
import sys
import time
import urllib.request
from itertools import combinations
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fuzzy_dedupe import find_duplicates  # noqa: E402

CACHE = Path(__file__).resolve().parent / ".cache" / "gleif_tr.json"
API = "https://api.gleif.org/api/v1/lei-records?filter[entity.legalAddress.country]=TR&page[size]=200&page[number]={}"


def gleif_turkey() -> list[str]:
    if not CACHE.exists():
        CACHE.parent.mkdir(exist_ok=True)
        names, page, pages = [], 1, 1
        while page <= pages:
            req = urllib.request.Request(API.format(page), headers={"Accept": "application/vnd.api+json",
                                                                    "User-Agent": "fuzzy-dedupe-benchmark"})
            with urllib.request.urlopen(req, timeout=120) as r:  # noqa: S310 - fixed https URL
                d = json.load(r)
            # The API pages through at most 10,000 records; that is plenty for this benchmark.
            pages = min(d["meta"]["pagination"]["lastPage"], 10000 // 200)
            names += [x["attributes"]["entity"]["legalName"]["name"] for x in d["data"]]
            print(f"  GLEIF page {page}/{pages}", flush=True)
            page += 1
            time.sleep(1.1)  # stay under the API's rate limit
        CACHE.write_text(json.dumps(names, ensure_ascii=False), encoding="utf-8")
    return list(dict.fromkeys(json.loads(CACHE.read_text(encoding="utf-8"))))


ASCII = str.maketrans("çğıöşüÇĞİÖŞÜâÂ", "cgiosuCGIOSUaA")
TAIL = re.compile(r"\s+(SANAY[İI]\s+VE\s+T[İI]CARET|T[İI]CARET\s+VE\s+SANAY[İI]|SANAY[İI]|T[İI]CARET)?\s*"
                  r"(ANON[İI]M\s+Ş[İI]RKET[İI]|L[İI]M[İI]TED\s+Ş[İI]RKET[İI]|A\.?\s?Ş\.?|LTD\.?\s*ŞT[İI]\.?)\s*$",
                  re.IGNORECASE)
AS_TAILS = [" SAN. VE TİC. A.Ş.", " SAN.TİC.A.Ş.", " A.Ş.", ""]
LTD_TAILS = [" SAN. VE TİC. LTD. ŞTİ.", " SAN.TİC.LTD.ŞTİ.", " LTD. ŞTİ.", ""]


def tr_title(s: str) -> str:
    return " ".join(w[:1] + w[1:].replace("I", "ı").replace("İ", "i").lower() for w in s.split())


def variant(name: str, rng: random.Random) -> str:
    out = name
    m = TAIL.search(out)
    if m and rng.random() < 0.7:
        form = m.group(2).upper()
        limited = form.startswith("L")  # LİMİTED ŞİRKETİ / LTD. ŞTİ. rather than ANONİM / A.Ş.
        out = out[: m.start()] + rng.choice(LTD_TAILS if limited else AS_TAILS)
    r = rng.random()
    if r < 0.4:
        out = out.translate(ASCII)
    elif r < 0.6:
        out = tr_title(out)
    elif r < 0.7:
        out = "  " + out.replace(" ", "  ") + " "
    if rng.random() < 0.3 and len(out) > 4:
        chars = list(out)
        k = rng.randrange(len(chars))
        chars[k:k + 2] = chars[k:k + 2][::-1]
        out = "".join(chars)
    return out


def main() -> None:
    base = gleif_turkey()
    rng = random.Random(21)  # NOSONAR: reproducible benchmark data
    rows: list[str] = []
    entity: list[int] = []
    for e, name in enumerate(base):
        rows.append(name)
        entity.append(e)
        if rng.random() < 0.25:
            for _ in range(rng.choice((1, 1, 2))):
                rows.append(variant(name, rng))
                entity.append(e)
    groups: dict[int, list[int]] = {}
    for i, e in enumerate(entity):
        groups.setdefault(e, []).append(i)
    truth = {p for g in groups.values() for p in combinations(sorted(g), 2)}
    print(f"{len(rows):,} rows ({len(base):,} Turkish legal names from GLEIF plus messy copies), "
          f"{len(truth):,} true duplicate pairs.\n")
    print("| Threshold | Settings | Pairs found | Precision | Recall | F1 |")
    print("|---:|---|---:|---:|---:|---:|")
    settings = [("default", {}), ("strip_suffixes", {"strip_suffixes": True}), ("turkish", {"turkish": True}),
                ("turkish + strip_suffixes", {"turkish": True, "strip_suffixes": True}),
                ("turkish + strip_suffixes + numbers_must_match + word_threshold=0.34",
                 {"turkish": True, "strip_suffixes": True, "numbers_must_match": True, "word_threshold": 0.34})]
    for t in (0.05, 0.1, 0.15, 0.2):
        for label, kw in settings:
            found = {(i, j) for i, j, _ in find_duplicates(rows, t, **kw)}
            tp = len(found & truth)
            prec = tp / len(found) if found else 0.0
            rec = tp / len(truth)
            f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
            print(f"| {t} | {label} | {len(found):,} | {prec:.3f} | {rec:.3f} | {f1:.3f} |")


if __name__ == "__main__":
    main()
