"""Find near-duplicate names fast, with exactly the answers of a brute-force search.

    >>> from fuzzy_dedupe import find_duplicates, cluster, link
    >>> find_duplicates(["Acme Ltd", "ACME  ltd", "Globex"])
    [(0, 1, 0.0)]
    >>> cluster(["Acme Ltd", "Globex", "acme ltd.", "Acme Ltd"])
    [[0, 2, 3]]
    >>> link(["Acme Ltd", "Globex"], ["GLOBEX", "Initech", "acme ltd."])
    [(0, 2, 0.1111111111111111), (1, 0, 0.0)]

`find_duplicates`, `cluster`, `link` and `Index` run in Rust. The `*_python` functions are the
pure-Python reference they are tested against.
"""

from ._native import cluster, find_duplicates, levenshtein, link, stats
from .index import Index
from .reference import cluster as cluster_python
from .reference import find_duplicates as find_duplicates_python
from .reference import link as link_python

__all__ = ["Index", "cluster", "cluster_python", "find_duplicates", "find_duplicates_python", "levenshtein", "link", "link_python", "stats"]
__version__ = "0.4.0"
