"""The pure-Python version: the code a client typically starts with.

Two names are duplicates when their edit distance, divided by the longer
name's length, is at most `threshold`. Every pair is compared, so the work
grows with the square of the list.
"""

from __future__ import annotations


def normalize(name: str) -> str:
    """Lowercase and collapse whitespace, so 'ACME  Ltd' and 'acme ltd' compare equal."""
    return " ".join(name.lower().split())


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


def find_duplicates(names: list[str], threshold: float = 0.2) -> list[tuple[int, int, float]]:
    """All pairs (i, j, score) with i < j whose normalized distance is <= threshold.

    `score` is the edit distance divided by the longer name's length. Both
    versions divide the same two integers, so the floats match bit for bit.
    """
    cleaned = [normalize(n) for n in names]
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
