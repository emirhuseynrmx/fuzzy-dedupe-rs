from collections.abc import Sequence
from typing import Literal

Method = Literal["auto", "indexed", "brute"]

def find_duplicates(
    names: Sequence[str],
    threshold: float = 0.2,
    *,
    token_sort: bool = False,
    strip_suffixes: bool = False,
    method: Method = "auto",
) -> list[tuple[int, int, float]]: ...
def cluster(
    names: Sequence[str],
    threshold: float = 0.2,
    *,
    token_sort: bool = False,
    strip_suffixes: bool = False,
    method: Method = "auto",
) -> list[list[int]]: ...
def link(
    left: Sequence[str],
    right: Sequence[str],
    threshold: float = 0.2,
    *,
    token_sort: bool = False,
    strip_suffixes: bool = False,
    method: Method = "auto",
) -> list[tuple[int, int, float]]: ...
def stats(
    names: Sequence[str], threshold: float = 0.2, *, token_sort: bool = False, strip_suffixes: bool = False
) -> tuple[int, int, int]:
    """(pairs found, candidate pairs verified by the index, all pairs)."""
def levenshtein(a: str, b: str) -> int: ...

class Index:
    def __init__(self, threshold: float = 0.2, *, token_sort: bool = False, strip_suffixes: bool = False) -> None: ...
    def add(self, names: Sequence[str]) -> int: ...
    def query(self, name: str) -> list[tuple[int, float]]: ...
    def query_many(self, names: Sequence[str]) -> list[list[tuple[int, float]]]: ...
    def names(self) -> list[str]: ...
    @property
    def threshold(self) -> float: ...
    @property
    def token_sort(self) -> bool: ...
    @property
    def strip_suffixes(self) -> bool: ...
    def __len__(self) -> int: ...
