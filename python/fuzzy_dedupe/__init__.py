"""Find near-duplicate names fast, with exactly the answers of a brute-force search.

    >>> from fuzzy_dedupe import find_duplicates, cluster
    >>> find_duplicates(["Acme Ltd", "ACME  ltd", "Globex"])
    [(0, 1, 0.0)]
    >>> cluster(["Acme Ltd", "Globex", "acme ltd.", "Acme Ltd"])
    [[0, 2, 3]]

`find_duplicates` and `cluster` run in Rust. The `*_python` functions are the
pure-Python reference they are tested against.
"""

from ._native import cluster, find_duplicates, levenshtein
from .reference import cluster as cluster_python
from .reference import find_duplicates as find_duplicates_python

__all__ = ["cluster", "cluster_python", "find_duplicates", "find_duplicates_python", "levenshtein"]
__version__ = "0.2.0"
