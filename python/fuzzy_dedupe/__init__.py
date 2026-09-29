"""Near-duplicate names, in pure Python (`reference`) and in Rust (`find_duplicates`)."""

from ._native import find_duplicates
from .reference import find_duplicates as find_duplicates_python

__all__ = ["find_duplicates", "find_duplicates_python"]
