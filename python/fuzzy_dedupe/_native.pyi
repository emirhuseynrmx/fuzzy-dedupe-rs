from collections.abc import Sequence
from typing import Literal

Method = Literal["auto", "indexed", "brute"]

def find_duplicates(
    names: Sequence[str],
    threshold: float = 0.2,
    *,
    token_sort: bool = False,
    method: Method = "auto",
) -> list[tuple[int, int, float]]: ...
def cluster(
    names: Sequence[str],
    threshold: float = 0.2,
    *,
    token_sort: bool = False,
    method: Method = "auto",
) -> list[list[int]]: ...
def link(
    left: Sequence[str],
    right: Sequence[str],
    threshold: float = 0.2,
    *,
    token_sort: bool = False,
    method: Method = "auto",
) -> list[tuple[int, int, float]]: ...
def stats(names: Sequence[str], threshold: float = 0.2, *, token_sort: bool = False) -> tuple[int, int, int]:
    """(pairs found, candidate pairs verified by the index, all pairs)."""
def levenshtein(a: str, b: str) -> int: ...
