"""Synthetic company names that look like a real CRM export.

Names share a small vocabulary ("Global", "Tech", "Ltd", "A.Ş.") the way real
ones do, which is the hard case for filtering: many names share words. About
a third of the rows are messy copies of an earlier row (typos, case, spacing,
dropped suffix, word order).
"""

from __future__ import annotations

import random

FIRST = ["Acme", "Global", "Blue", "North", "Star", "Delta", "Prime", "Atlas", "Nova", "Ege", "Anadolu", "Marmara",
         "Bosphorus", "Summit", "Silver", "Golden", "Green", "Red", "Pacific", "Euro", "Metro", "Smart", "Rapid",
         "Bright", "United", "First", "Royal", "Alpha", "Omega", "Vertex", "Karadeniz", "Toros", "Kuzey", "Güney"]
MIDDLE = ["Tech", "Logistics", "Foods", "Textile", "Energy", "Systems", "Solutions", "Trading", "Holdings", "Capital",
          "Medical", "Construction", "Motors", "Software", "Consulting", "Retail", "Pharma", "Media", "Tekstil",
          "Gıda", "İnşaat", "Enerji", "Lojistik", "Yazılım", "Danışmanlık", "Otomotiv", "Kimya", "Tarım"]
LAST = ["Ltd", "Ltd.", "Inc", "Inc.", "LLC", "GmbH", "A.Ş.", "Ltd. Şti.", "Group", "Co", "Corp", "Partners", "", ""]


def company(rng: random.Random) -> str:
    words = [rng.choice(FIRST)]
    if rng.random() < 0.5:
        words.append(rng.choice(FIRST))
    words.append(rng.choice(MIDDLE))
    if rng.random() < 0.3:
        words.append(rng.choice(MIDDLE))
    last = rng.choice(LAST)
    return " ".join(words + ([last] if last else []))


def messy(name: str, rng: random.Random) -> str:
    move = rng.random()
    if move < 0.25:  # typo
        chars = list(name)
        k = rng.randrange(len(chars))
        op = rng.choice(("drop", "swap", "double", "replace"))
        if op == "drop" and len(chars) > 1:
            del chars[k]
        elif op == "swap" and k + 1 < len(chars):
            chars[k], chars[k + 1] = chars[k + 1], chars[k]
        elif op == "double":
            chars.insert(k, chars[k])
        else:
            chars[k] = rng.choice("aeiourstln")
        return "".join(chars)
    if move < 0.45:
        return name.upper()
    if move < 0.6:
        return "  " + name.replace(" ", "  ") + " "
    if move < 0.8:  # drop the legal suffix
        parts = name.split()
        return " ".join(parts[:-1]) if len(parts) > 2 else name
    parts = name.split()
    rng.shuffle(parts)
    return " ".join(parts)


def names(n: int, seed: int = 7) -> list[str]:
    rng = random.Random(seed)
    out: list[str] = []
    for _ in range(n):
        if out and rng.random() < 0.35:
            out.append(messy(rng.choice(out), rng))
        else:
            out.append(company(rng))
    return out
