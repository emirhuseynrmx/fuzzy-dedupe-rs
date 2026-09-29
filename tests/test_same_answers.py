"""The Rust version must return exactly what the Python version returns."""

import random
import string

import pytest

from fuzzy_dedupe import find_duplicates, find_duplicates_python
from fuzzy_dedupe.reference import levenshtein

BASE = ["Acme Ltd", "Globex Corporation", "Initech", "Umbrella Corp", "Hooli", "Stark Industries",
        "Wayne Enterprises", "Wonka Industries", "Şişecam A.Ş.", "Ülker Bisküvi", "Öztürk Gıda"]


def typo(name: str, rng: random.Random) -> str:
    """One random edit: drop, swap, double a letter, or change the case and spacing."""
    chars = list(name)
    k = rng.randrange(len(chars))
    move = rng.choice(("drop", "swap", "double", "case"))
    if move == "drop" and len(chars) > 1:
        del chars[k]
    elif move == "swap" and k + 1 < len(chars):
        chars[k], chars[k + 1] = chars[k + 1], chars[k]
    elif move == "double":
        chars.insert(k, chars[k])
    else:
        return "  " + name.upper() + " "
    return "".join(chars)


def messy_list(n: int, seed: int) -> list[str]:
    rng = random.Random(seed)
    out = []
    for _ in range(n):
        if rng.random() < 0.5:
            out.append(typo(rng.choice(BASE), rng))
        else:
            out.append("".join(rng.choices(string.ascii_letters + " ", k=rng.randint(0, 24))))
    return out


@pytest.mark.parametrize("seed", range(20))
@pytest.mark.parametrize("threshold", [0.0, 0.1, 0.2, 0.35])
def test_rust_matches_python(seed, threshold):
    names = messy_list(120, seed)
    assert find_duplicates(names, threshold) == find_duplicates_python(names, threshold)


def test_finds_the_obvious_duplicates():
    names = ["Acme Ltd", "ACME  ltd", "Acme Ltd.", "Globex"]
    pairs = {(i, j) for i, j, _ in find_duplicates(names, 0.2)}
    assert {(0, 1), (0, 2), (1, 2)} <= pairs
    assert not any(3 in p for p in pairs)


def test_edge_cases():
    assert find_duplicates([]) == []
    assert find_duplicates(["only one"]) == []
    assert find_duplicates(["", "  "]) == [(0, 1, 0.0)]
    assert find_duplicates(["Şişecam", "şişecam"], 0.0) == [(0, 1, 0.0)]


def test_levenshtein_known_values():
    assert levenshtein("kitten", "sitting") == 3
    assert levenshtein("", "abc") == 3
    assert levenshtein("same", "same") == 0
