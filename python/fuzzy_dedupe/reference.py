"""The pure-Python version: the code a client typically starts with, and the
reference the Rust version must match exactly.

Two names are duplicates when their edit distance, divided by the longer
name's length, is at most `threshold`. Every pair is compared, so the work
grows with the square of the list.
"""

from __future__ import annotations

import re
from collections import Counter


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


_LONG_TURKISH = sorted(w for w in TURKISH_SUFFIXES if len(w) >= 6)


def osa_distance(a: str, b: str) -> int:
    """Optimal string alignment distance: Levenshtein plus adjacent transpositions."""
    d = [list(range(len(b) + 1))] + [[i] + [0] * len(b) for i in range(1, len(a) + 1)]
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            v = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + (a[i - 1] != b[j - 1]))
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                v = min(v, d[i - 2][j - 2] + 1)
            d[i][j] = v
    return d[len(a)][len(b)]


def _listed_suffix(w: str, turkish: bool) -> bool:
    """Listed, or (Turkish mode) a long Turkish tail word with one typo or swapped pair."""
    if w in LEGAL_SUFFIXES or (turkish and w in TURKISH_SUFFIXES):
        return True
    return turkish and len(w) >= 6 and any(osa_distance(w, s) <= 1 for s in _LONG_TURKISH)


def _suffix_pieces(word: str) -> list[str]:
    """Dot- or comma-separated pieces, runs of single letters joined: 'san.tic.a.s.' -> san, tic, as."""
    out: list[str] = []
    prev_single = False
    for p in re.split(r"[.,]", word):
        if not p:
            continue
        single = len(p) == 1
        if single and prev_single and out:
            out[-1] += p
        else:
            out.append(p)
        prev_single = single
    return out


def _is_legal_suffix(word: str, turkish: bool) -> bool:
    bare = word.replace(".", "").replace(",", "")
    pieces = _suffix_pieces(word)
    return _listed_suffix(bare, turkish) or (bool(pieces) and all(_listed_suffix(p, turkish) for p in pieces))


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


_ONES = ("birinci", "ikinci", "ucuncu", "dorduncu", "besinci", "altinci", "yedinci", "sekizinci", "dokuzuncu")
_TENS = ("onuncu", "yirminci", "otuzuncu", "kirkinci", "ellinci", "altmisinci", "yetmisinci", "sekseninci", "doksaninci")
_TEN_PREFIXES = ("on", "yirmi", "otuz", "kirk", "elli", "altmis", "yetmis", "seksen", "doksan")
# Turkish ordinal words up to one hundred, ASCII-folded. Kept in step with is_turkish_ordinal in src/core.rs.
TURKISH_ORDINALS = frozenset(_ONES + _TENS + ("yuzuncu",) + tuple(p + o for p in _TEN_PREFIXES for o in _ONES))


def _numbers(words: list[str], turkish: bool) -> list[str]:
    return sorted(w for w in words if any("0" <= c <= "9" for c in w) or (turkish and w in TURKISH_ORDINALS))


def pair_accepted(a: str, b: str, *, numbers_must_match: bool = False, word_threshold: float | None = None,
                  turkish: bool = False) -> bool:
    """The extra pair rules, on two normalized names.

    `numbers_must_match`: words with digits (and Turkish ordinals in Turkish mode) must be the
    same. `word_threshold`: the words not shared by the two names, sorted and joined, must be
    within this normalized edit distance of each other.
    """
    wa, wb = a.split(), b.split()
    if numbers_must_match and _numbers(wa, turkish) != _numbers(wb, turkish):
        return False
    if word_threshold is not None:
        ca, cb = Counter(wa), Counter(wb)
        da, db = " ".join(sorted((ca - cb).elements())), " ".join(sorted((cb - ca).elements()))
        longest = max(len(da), len(db))
        if longest and levenshtein(da, db) / longest > word_threshold:
            return False
    return True


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
                    strip_suffixes: bool = False, turkish: bool = False, numbers_must_match: bool = False,
                    word_threshold: float | None = None) -> list[tuple[int, int, float]]:
    """All pairs (i, j, score) with i < j whose normalized distance is <= threshold.

    `score` is the edit distance divided by the longer name's length. Both
    versions divide the same two integers, so the floats match bit for bit.
    With `numbers_must_match` or `word_threshold`, a pair must also pass `pair_accepted`.
    """
    cleaned = [normalize(n, token_sort, strip_suffixes, turkish) for n in names]
    rules = {"numbers_must_match": numbers_must_match, "word_threshold": word_threshold, "turkish": turkish}
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
            if score <= threshold and pair_accepted(a, b, **rules):
                out.append((i, j, score))
    return out


def link(left: list[str], right: list[str], threshold: float = 0.2, *, token_sort: bool = False,
         strip_suffixes: bool = False, turkish: bool = False, numbers_must_match: bool = False,
         word_threshold: float | None = None) -> list[tuple[int, int, float]]:
    """All pairs (i, j, score) where left[i] and right[j] are within the threshold, sorted."""
    rules = {"numbers_must_match": numbers_must_match, "word_threshold": word_threshold, "turkish": turkish}
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
            if score <= threshold and pair_accepted(a, b, **rules):
                out.append((i, j, score))
    return out


def cluster(names: list[str], threshold: float = 0.2, *, token_sort: bool = False,
            strip_suffixes: bool = False, turkish: bool = False, numbers_must_match: bool = False,
            word_threshold: float | None = None) -> list[list[int]]:
    """Groups of two or more names linked by any chain of duplicate pairs.

    Each group is a sorted list of positions; groups are ordered by their first member.
    """
    parent = list(range(len(names)))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    pairs = find_duplicates(names, threshold, token_sort=token_sort, strip_suffixes=strip_suffixes, turkish=turkish,
                            numbers_must_match=numbers_must_match, word_threshold=word_threshold)
    for i, j, _ in pairs:
        a, b = find(i), find(j)
        if a != b:
            parent[max(a, b)] = min(a, b)
    groups: dict[int, list[int]] = {}
    for i in range(len(names)):
        groups.setdefault(find(i), []).append(i)
    return sorted((g for g in groups.values() if len(g) > 1), key=lambda g: g[0])
