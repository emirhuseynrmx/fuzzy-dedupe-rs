"""Property tests: for any list of names, every Rust strategy equals the Python reference."""

import csv

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from fuzzy_dedupe import cluster, cluster_python, find_duplicates, find_duplicates_python, levenshtein
from fuzzy_dedupe.cli import main as cli
from fuzzy_dedupe.reference import levenshtein as levenshtein_python

# Few distinct letters so near-duplicates are common; spaces, case and non-ASCII on purpose.
ALPHABET = "abcABCçÇşŞğİı "
names = st.lists(st.text(alphabet=ALPHABET, max_size=40), max_size=40)
thresholds = st.sampled_from([0.0, 0.05, 0.1, 0.15, 0.2, 0.25, 1 / 3, 0.4, 0.49, 0.5, 0.75, 1.0])


@settings(max_examples=400, deadline=None)
@given(names, thresholds, st.booleans())
def test_every_strategy_matches_python(ns, t, token_sort):
    expected = find_duplicates_python(ns, t, token_sort=token_sort)
    for method in ("auto", "indexed", "brute"):
        assert find_duplicates(ns, t, token_sort=token_sort, method=method) == expected


@settings(max_examples=200, deadline=None)
@given(names, thresholds)
def test_clusters_match_python(ns, t):
    assert cluster(ns, t) == cluster_python(ns, t)


@settings(max_examples=500, deadline=None)
@given(st.text(alphabet=ALPHABET + "xyz", max_size=90), st.text(alphabet=ALPHABET + "xyz", max_size=90))
def test_levenshtein_matches_python(a, b):
    # Covers both the bit-parallel path (<= 64 chars) and the fallback (longer).
    assert levenshtein(a, b) == levenshtein_python(a, b)


def test_token_sort_ignores_word_order():
    assert find_duplicates(["Ltd Acme", "Acme Ltd"], 0.0) == []
    assert find_duplicates(["Ltd Acme", "Acme Ltd"], 0.0, token_sort=True) == [(0, 1, 0.0)]


def test_clusters_follow_chains():
    # a~b and b~c link a and c even though a and c are too far apart on their own.
    ns = ["abcdefghij", "abcdefghix", "abcdefghxx", "zzzz"]
    assert find_duplicates(ns, 0.1) == [(0, 1, 0.1), (1, 2, 0.1)]
    assert cluster(ns, 0.1) == [[0, 1, 2]]


def test_rejects_bad_arguments():
    with pytest.raises(ValueError):
        find_duplicates(["a"], 1.5)
    with pytest.raises(ValueError):
        find_duplicates(["a"], 0.2, method="magic")


def test_cli_pairs_and_groups(tmp_path, capsys):
    src = tmp_path / "in.csv"
    src.write_text("id,name\n1,Acme Ltd\n2,ACME  ltd\n3,Globex\n4,Acme Ltd.\n", encoding="utf-8")
    out = tmp_path / "pairs.csv"
    assert cli([str(src), "--column", "name", "-o", str(out)]) == 0
    rows = list(csv.DictReader(out.open(encoding="utf-8")))
    assert [(r["row_a"], r["row_b"]) for r in rows] == [("1", "2"), ("1", "4"), ("2", "4")]
    groups = tmp_path / "groups.csv"
    assert cli([str(src), "--column", "name", "--groups", "-o", str(groups)]) == 0
    rows = list(csv.DictReader(groups.open(encoding="utf-8")))
    assert {r["row"] for r in rows} == {"1", "2", "4"} and {r["group"] for r in rows} == {"1"}
    assert "3 pairs" in capsys.readouterr().err
