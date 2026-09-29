"""A persistent, incremental index of names.

    >>> from fuzzy_dedupe import Index
    >>> idx = Index.build(["Acme Ltd", "Globex Corp", "Initech"], threshold=0.2)
    >>> idx.query("ACME ltd.")
    [(0, 0.1111111111111111)]
    >>> idx.add(["Umbrella Corp"])
    3
    >>> len(idx)
    4

`save` writes the settings and the names as JSON; `load` rebuilds the index
from them, so a saved file keeps working across versions of the algorithm.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

from ._native import Index as _Index

FORMAT = "fuzzy-dedupe-index"
VERSION = 1


class Index(_Index):
    """Names you can query one at a time, with the same exact results as a full comparison.

    Index(threshold=0.2, *, token_sort=False, strip_suffixes=False, turkish=False,
          numbers_must_match=False, word_threshold=None)
    """

    @classmethod
    def build(cls, names: Iterable[str], threshold: float = 0.2, *, token_sort: bool = False,
              strip_suffixes: bool = False, turkish: bool = False, numbers_must_match: bool = False,
              word_threshold: float | None = None) -> Index:
        """An index holding `names`, with ids 0..len(names)-1."""
        idx = cls(threshold, token_sort=token_sort, strip_suffixes=strip_suffixes, turkish=turkish,
                  numbers_must_match=numbers_must_match, word_threshold=word_threshold)
        idx.add(list(names))
        return idx

    def save(self, path: str | Path) -> None:
        """Write the settings and names to `path` as UTF-8 JSON."""
        data = {"format": FORMAT, "version": VERSION, "threshold": self.threshold,
                "token_sort": self.token_sort, "strip_suffixes": self.strip_suffixes, "turkish": self.turkish,
                "numbers_must_match": self.numbers_must_match, "word_threshold": self.word_threshold,
                "names": self.names()}
        Path(path).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> Index:
        """Rebuild an index saved with `save`."""
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if data.get("format") != FORMAT or data.get("version") != VERSION:
            raise ValueError(f"{path} is not a {FORMAT} v{VERSION} file")
        return cls.build(data["names"], data["threshold"], token_sort=data["token_sort"],
                         strip_suffixes=data["strip_suffixes"], turkish=data.get("turkish", False),
                         numbers_must_match=data.get("numbers_must_match", False),
                         word_threshold=data.get("word_threshold"))

    def __repr__(self) -> str:
        return (f"Index(names={len(self):,}, threshold={self.threshold}, token_sort={self.token_sort}, "
                f"strip_suffixes={self.strip_suffixes}, turkish={self.turkish}, "
                f"numbers_must_match={self.numbers_must_match}, word_threshold={self.word_threshold})")
