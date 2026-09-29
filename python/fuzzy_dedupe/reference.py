"""The pure-Python version: the code a client typically starts with, and the
reference the Rust version must match exactly.

Two names are duplicates when their edit distance, divided by the longer
name's length, is at most `threshold`. Every pair is compared, so the work
grows with the square of the list.
"""

from __future__ import annotations


def normalize(name: str, token_sort: bool = False) -> str:
    """Lowercase and collapse whitespace, so 'ACME  Ltd' and 'acme ltd' compare equal.

    With `token_sort`, the words are also sorted, so 'Ltd Acme' equals 'Acme Ltd'.
    """
    words = name.lower().split()
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


def find_duplicates(names: list[str], threshold: float = 0.2, *, token_sort: bool = False) -> list[tuple[int, int, float]]:
    """All pairs (i, j, score) with i < j whose normalized distance is <= threshold.

    `score` is the edit distance divided by the longer name's length. Both
    versions divide the same two integers, so the floats match bit for bit.
    """
    cleaned = [normalize(n, token_sort) for n in names]
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


def link(left: list[str], right: list[str], threshold: float = 0.2, *, token_sort: bool = False) -> list[tuple[int, int, float]]:
    """All pairs (i, j, score) where left[i] and right[j] are within the threshold, sorted."""
    a_clean = [normalize(n, token_sort) for n in left]
    b_clean = [normalize(n, token_sort) for n in right]
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


def cluster(names: list[str], threshold: float = 0.2, *, token_sort: bool = False) -> list[list[int]]:
    """Groups of two or more names linked by any chain of duplicate pairs.

    Each group is a sorted list of positions; groups are ordered by their first member.
    """
    parent = list(range(len(names)))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i, j, _ in find_duplicates(names, threshold, token_sort=token_sort):
        a, b = find(i), find(j)
        if a != b:
            parent[max(a, b)] = min(a, b)
    groups: dict[int, list[int]] = {}
    for i in range(len(names)):
        groups.setdefault(find(i), []).append(i)
    return sorted((g for g in groups.values() if len(g) > 1), key=lambda g: g[0])
