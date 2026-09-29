"""The pure-Python version: the code a client typically starts with, and the
reference the Rust version must match exactly.

Two names are duplicates when their edit distance, divided by the longer
name's length, is at most `threshold`. Every pair is compared, so the work
grows with the square of the list.
"""

from __future__ import annotations

import re


# Legal-form words dropped from the end by `strip_suffixes`, compared after
# lowercasing and removing '.' and ','. Kept in step with LEGAL_SUFFIXES in src/core.rs.
LEGAL_SUFFIXES = frozenset({
    "limited", "ltd", "llc", "llp", "lp", "plc", "inc", "incorporated", "corp", "corporation",
    "co", "company", "gmbh", "ag", "kg", "sa", "sas", "sarl", "srl", "spa", "bv", "nv", "oy", "ab",
    "as", "pty", "pvt", "aş", "şti", "ltdşti",
})


# Turkish legal-form and trade words dropped from the end with `strip_suffixes` in
# Turkish mode, ASCII-folded. Sector words ("tekstil", "gida") are not in the list.
# Kept in step with TURKISH_SUFFIXES in src/core.rs.
TURKISH_SUFFIXES = frozenset({
    "sanayi", "san", "sanayii", "ticaret", "tic", "ve", "anonim", "sirketi", "sirket", "sti",
    "ltdsti", "limited", "ltd", "as", "ithalat", "ihracat", "ith", "ihr", "ic", "dis", "kollektif",
    "koll", "komandit", "kom", "kooperatifi", "koop", "ortakligi", "adi",
})

_TURKISH_FOLD = str.maketrans({"ç": "c", "ğ": "g", "ı": "i", "ö": "o", "ş": "s", "ü": "u",
                               "â": "a", "î": "i", "û": "u", "\u0307": None})


def turkish_lower(name: str) -> str:
    """Turkish lowercasing (I -> ı, İ -> i), then Turkish letters folded to ASCII."""
    return name.replace("I", "ı").replace("İ", "i").lower().translate(_TURKISH_FOLD)


def _is_legal_suffix(word: str, turkish: bool) -> bool:
    def listed(w: str) -> bool:
        return w in LEGAL_SUFFIXES or (turkish and w in TURKISH_SUFFIXES)

    bare = word.replace(".", "").replace(",", "")
    pieces = [p for p in re.split(r"[.,]", word) if p]
    return listed(bare) or (bool(pieces) and all(listed(p) for p in pieces))


def normalize(name: str, token_sort: bool = False, strip_suffixes: bool = False, turkish: bool = False) -> str:
    """Lowercase and collapse whitespace, so 'ACME  Ltd' and 'acme ltd' compare equal.

    With `turkish`, Turkish case rules apply and Turkish letters fold to ASCII, so
    'TEKSTİL', 'TEKSTIL' and 'Tekstil' agree. With `strip_suffixes`, legal-form words at
    the end are dropped ('Acme Ltd.' -> 'acme'; in Turkish mode also 'Sanayi ve Ticaret
    Ltd. Şti.'), as long as one word is left. With `token_sort`, the words are sorted.
    """
    words = (turkish_lower(name) if turkish else name.lower()).split()
    if strip_suffixes:
        while len(words) > 1 and _is_legal_suffix(words[-1], turkish):
            words.pop()
    if token_sort:
        words.sort()
    return " ".join(words)


def levenshtein(a: str, b: str) -> int:
    """Edit distance: insertions, deletions and substitutions, one row at a time."""
    if len(a) < len(b):
        a, b = b, a
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(min(
                previous[j] + 1,               # deletion
                current[j - 1] + 1,            # insertion
                previous[j - 1] + (ca != cb),  # substitution
            ))
        previous = current
    return previous[-1]


def find_duplicates(names: list[str], threshold: float = 0.2, *, token_sort: bool = False,
                    strip_suffixes: bool = False, turkish: bool = False) -> list[tuple[int, int, float]]:
    """All pairs (i, j, score) with i < j whose normalized distance is <= threshold.

    `score` is the edit distance divided by the longer name's length. Both
    versions divide the same two integers, so the floats match bit for bit.
    """
    cleaned = [normalize(n, token_sort, strip_suffixes, turkish) for n in names]
    out = []
    for i in range(len(cleaned)):
        a = cleaned[i]
        for j in range(i + 1, len(cleaned)):
            b = cleaned[j]
            longest = max(len(a), len(b))
            if longest == 0:
                out.append((i, j, 0.0))
                continue
            # Lengths alone rule out most pairs: the distance is at least the length difference.
            if abs(len(a) - len(b)) / longest > threshold:
                continue
            score = levenshtein(a, b) / longest
            if score <= threshold:
                out.append((i, j, score))
    return out


def link(left: list[str], right: list[str], threshold: float = 0.2, *, token_sort: bool = False,
         strip_suffixes: bool = False, turkish: bool = False) -> list[tuple[int, int, float]]:
    """All pairs (i, j, score) where left[i] and right[j] are within the threshold, sorted."""
    a_clean = [normalize(n, token_sort, strip_suffixes, turkish) for n in left]
    b_clean = [normalize(n, token_sort, strip_suffixes, turkish) for n in right]
    out = []
    for i, a in enumerate(a_clean):
        for j, b in enumerate(b_clean):
            longest = max(len(a), len(b))
            if longest == 0:
                out.append((i, j, 0.0))
                continue
            if abs(len(a) - len(b)) / longest > threshold:
                continue
            score = levenshtein(a, b) / longest
            if score <= threshold:
                out.append((i, j, score))
    return out


def cluster(names: list[str], threshold: float = 0.2, *, token_sort: bool = False,
            strip_suffixes: bool = False, turkish: bool = False) -> list[list[int]]:
    """Groups of two or more names linked by any chain of duplicate pairs.

    Each group is a sorted list of positions; groups are ordered by their first member.
    """
    parent = list(range(len(names)))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i, j, _ in find_duplicates(names, threshold, token_sort=token_sort, strip_suffixes=strip_suffixes, turkish=turkish):
        a, b = find(i), find(j)
        if a != b:
            parent[max(a, b)] = min(a, b)
    groups: dict[int, list[int]] = {}
    for i in range(len(names)):
        groups.setdefault(find(i), []).append(i)
    return sorted((g for g in groups.values() if len(g) > 1), key=lambda g: g[0])
