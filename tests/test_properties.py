"""Property tests: for any list of names, every Rust strategy equals the Python reference."""

import csv

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from fuzzy_dedupe import cluster, cluster_python, find_duplicates, find_duplicates_python, levenshtein, stats
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


@settings(max_examples=300, deadline=None)
@given(names, names, thresholds, st.booleans())
def test_link_matches_python(left, right, t, token_sort):
    from fuzzy_dedupe import link, link_python

    expected = link_python(left, right, t, token_sort=token_sort)
    for method in ("auto", "indexed", "brute"):
        assert link(left, right, t, token_sort=token_sort, method=method) == expected


def test_cli_link(tmp_path):
    a = tmp_path / "crm.csv"
    a.write_text("name\nAcme Ltd\nGlobex\n", encoding="utf-8")
    b = tmp_path / "invoices.csv"
    b.write_text("customer\nGLOBEX\nInitech\nacme ltd.\n", encoding="utf-8")
    out = tmp_path / "links.csv"
    assert cli([str(a), "--column", "name", "--link", str(b), "--link-column", "customer", "-o", str(out)]) == 0
    rows = list(csv.DictReader(out.open(encoding="utf-8")))
    assert [(r["row"], r["other_row"]) for r in rows] == [("1", "3"), ("2", "1")]


@settings(max_examples=200, deadline=None)
@given(names, st.sampled_from([0.0, 0.1, 0.2, 0.3, 0.45]))
def test_stats_counts_are_consistent(ns, t):
    from fuzzy_dedupe import stats

    found, verified, allpairs = stats(ns, t)
    assert found == len(find_duplicates_python(ns, t))
    assert allpairs == len(ns) * (len(ns) - 1) // 2
    assert found <= verified <= allpairs  # every pair found was verified; the filter never adds pairs


# ---- 0.4: strip_suffixes and the persistent Index ----

SUFFIX_WORDS = st.sampled_from(["", " Ltd", " Ltd.", " LIMITED", " GmbH", " A.Ş.", " Ltd. Şti.", " Inc", " co"])
company_names = st.lists(st.builds(lambda a, b: a + b, st.text(alphabet=ALPHABET, max_size=25), SUFFIX_WORDS), max_size=30)


@settings(max_examples=300, deadline=None)
@given(company_names, thresholds, st.booleans())
def test_strip_suffixes_matches_python(ns, t, token_sort):
    expected = find_duplicates_python(ns, t, token_sort=token_sort, strip_suffixes=True)
    for method in ("auto", "indexed", "brute"):
        assert find_duplicates(ns, t, token_sort=token_sort, strip_suffixes=True, method=method) == expected


@settings(max_examples=300, deadline=None)
@given(company_names, company_names, st.lists(st.text(alphabet=ALPHABET, max_size=30), min_size=1, max_size=6),
       thresholds, st.booleans())
def test_index_query_equals_full_comparison(first, later, queries, t, strip):
    from fuzzy_dedupe import Index, link_python

    idx = Index.build(first, t, strip_suffixes=strip)
    idx.add(later)
    stored = first + later
    assert len(idx) == len(stored) and idx.names() == stored
    for q in queries:
        expected = [(j, s) for _, j, s in link_python([q], stored, t, strip_suffixes=strip)]
        assert idx.query(q) == expected
    assert idx.query_many(queries) == [idx.query(q) for q in queries]


def test_index_save_and_load(tmp_path):
    from fuzzy_dedupe import Index

    idx = Index.build(["Acme Ltd", "Globex Corp", "Şişecam A.Ş."], 0.15, token_sort=True, strip_suffixes=True)
    path = tmp_path / "names.idx.json"
    idx.save(path)
    back = Index.load(path)
    assert (back.threshold, back.token_sort, back.strip_suffixes) == (0.15, True, True)
    assert back.names() == idx.names()
    for q in ["ACME", "globex", "şişecam", "nothing like it"]:
        assert back.query(q) == idx.query(q)
    (tmp_path / "bad.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError):
        Index.load(tmp_path / "bad.json")


def test_cli_strip_suffixes(tmp_path):
    src = tmp_path / "in.csv"
    src.write_text("name\nAcme Ltd\nAcme Limited\nGlobex\n", encoding="utf-8")
    out = tmp_path / "pairs.csv"
    assert cli([str(src), "--column", "name", "--threshold", "0.0", "-o", str(out)]) == 0
    assert list(csv.DictReader(out.open(encoding="utf-8"))) == []
    assert cli([str(src), "--column", "name", "--threshold", "0.0", "--strip-suffixes", "-o", str(out)]) == 0
    rows = list(csv.DictReader(out.open(encoding="utf-8")))
    assert [(r["row_a"], r["row_b"]) for r in rows] == [("1", "2")]


# ---- 0.5: Turkish mode ----

TR_ALPHABET = "abcçdegğhıiİIoöşsuüÂâ "
TR_TAILS = st.sampled_from(["", " A.Ş.", " Ltd. Şti.", " San. ve Tic. Ltd. Şti.", " SANAYİ VE TİCARET LİMİTED ŞİRKETİ",
                            " İthalat İhracat A.Ş.", " SAN.VE TIC.LTD.STI.", " Anonim Şirketi", " ve Ortakları"])
tr_names = st.lists(st.builds(lambda a, b: a + b, st.text(alphabet=TR_ALPHABET, max_size=20), TR_TAILS), max_size=30)


@settings(max_examples=400, deadline=None)
@given(tr_names, thresholds, st.booleans(), st.booleans())
def test_turkish_mode_matches_python(ns, t, strip, token_sort):
    expected = find_duplicates_python(ns, t, token_sort=token_sort, strip_suffixes=strip, turkish=True)
    for method in ("auto", "indexed", "brute"):
        assert find_duplicates(ns, t, token_sort=token_sort, strip_suffixes=strip, turkish=True, method=method) == expected


@settings(max_examples=200, deadline=None)
@given(tr_names, tr_names, st.lists(st.text(alphabet=TR_ALPHABET, max_size=25), min_size=1, max_size=5), thresholds)
def test_turkish_index_and_link_match_python(first, later, queries, t):
    from fuzzy_dedupe import Index, link, link_python

    assert link(first, later, t, strip_suffixes=True, turkish=True) == link_python(first, later, t, strip_suffixes=True, turkish=True)
    idx = Index.build(first, t, strip_suffixes=True, turkish=True)
    idx.add(later)
    stored = first + later
    for q in queries:
        assert idx.query(q) == [(j, s) for _, j, s in link_python([q], stored, t, strip_suffixes=True, turkish=True)]


def test_turkish_spellings_agree():
    from fuzzy_dedupe.reference import normalize

    same = ["ABC TEKSTİL SANAYİ VE TİCARET LİMİTED ŞİRKETİ", "Abc Tekstil San. ve Tic. Ltd. Şti.",
            "ABC TEKSTIL SAN.VE TIC.LTD.STI.", "abc tekstıl sanayi ve ticaret ltd şti"]
    assert {normalize(s, strip_suffixes=True, turkish=True) for s in same} == {"abc tekstil"}
    assert find_duplicates(same, 0.0, strip_suffixes=True, turkish=True) == [(i, j, 0.0) for i in range(4) for j in range(i + 1, 4)]
    assert find_duplicates(same, 0.0) == []  # without Turkish mode none of them match exactly
    assert normalize("İSTANBUL", turkish=True) == normalize("Istanbul", turkish=True) == "istanbul"
    assert normalize("Ahmet Yılmaz ve Ortakları Kollektif Şirketi", strip_suffixes=True, turkish=True) == "ahmet yilmaz ve ortaklari"


def test_turkish_index_saves_its_mode(tmp_path):
    from fuzzy_dedupe import Index

    idx = Index.build(["Kuzey Gıda A.Ş."], 0.1, strip_suffixes=True, turkish=True)
    idx.save(tmp_path / "tr.json")
    back = Index.load(tmp_path / "tr.json")
    assert back.turkish and back.query("KUZEY GIDA SANAYİ VE TİCARET LTD. ŞTİ.") == [(0, 0.0)]


# ---- 0.6: typo-tolerant Turkish tails, pair rules ----

TR_TAILS_TYPO = st.sampled_from(["", " San.Tic.A.Ş.", " SAN.TİC.A.Ş.", " Sanayi ve Ticaert", " Sanaiy", " İthalat İhraca",
                                 " S.A.", " 2", " 3", " Birinci", " İkinci", " Onbeşinci"])
tr_rule_names = st.lists(st.builds(lambda a, b, c: a + b + c, st.text(alphabet=TR_ALPHABET + "12", max_size=20),
                                   TR_TAILS_TYPO, TR_TAILS), max_size=30)
word_thresholds = st.sampled_from([None, 0.0, 0.25, 0.34, 0.5, 1.0])


@settings(max_examples=300, deadline=None)
@given(tr_rule_names, thresholds, st.booleans(), word_thresholds, st.booleans())
def test_pair_rules_match_python(ns, t, numbers, wt, tr):
    opts = {"strip_suffixes": True, "turkish": tr, "numbers_must_match": numbers, "word_threshold": wt}
    expected = find_duplicates_python(ns, t, **opts)
    for method in ("auto", "indexed", "brute"):
        assert find_duplicates(ns, t, method=method, **opts) == expected
    assert cluster(ns, t, **opts) == cluster_python(ns, t, **opts)
    assert stats(ns, t, **opts)[0] == len(expected)


@settings(max_examples=150, deadline=None)
@given(tr_rule_names, tr_rule_names, st.lists(st.text(alphabet=TR_ALPHABET + "12", max_size=25), min_size=1, max_size=5),
       thresholds, word_thresholds)
def test_pair_rules_index_and_link_match_python(first, later, queries, t, wt):
    from fuzzy_dedupe import Index, link, link_python

    opts = {"strip_suffixes": True, "turkish": True, "numbers_must_match": True, "word_threshold": wt}
    assert link(first, later, t, **opts) == link_python(first, later, t, **opts)
    idx = Index.build(first, t, **opts)
    idx.add(later)
    stored = first + later
    for q in queries:
        assert idx.query(q) == [(j, s) for _, j, s in link_python([q], stored, t, **opts)]


def test_turkish_tail_typos_are_stripped():
    from fuzzy_dedupe.reference import normalize

    def tr(s):
        return normalize(s, strip_suffixes=True, turkish=True)

    assert tr("AS OFIS YEM GIDA SANAYI VE TICAERT") == "as ofis yem gida"
    assert tr("Morpa Ofset Lojistik Sanaiy") == "morpa ofset lojistik"
    assert tr("KLN LOJİSTİK SAN.TİC.A.Ş.") == "kln lojistik"
    assert tr("Durr Systems Makine İthalat ve İhraca") == "durr systems makine"
    assert normalize("Acme S.A.", strip_suffixes=True) == "acme"
    assert normalize("Acme Sanaiy", strip_suffixes=True) == "acme sanaiy"  # typo tolerance is Turkish mode only
    same = ["KLN LOJİSTİK SAN.TİC.A.Ş.", "Kln Lojistik Sanayi ve Ticaret Anonim Şirketi"]
    assert find_duplicates(same, 0.0, strip_suffixes=True, turkish=True) == [(0, 1, 0.0)]


def test_pair_rules_reject_template_neighbours():
    precise = {"strip_suffixes": True, "turkish": True, "numbers_must_match": True, "word_threshold": 0.34}
    funds = ["Neo Portföy Birinci Serbest Fon", "Neo Portföy İkinci Serbest Fon",
             "Pera Emeklilik 2 Fonu", "Pera Emeklilik 3 Fonu"]
    assert find_duplicates(funds, 0.2, strip_suffixes=True, turkish=True) != []
    assert find_duplicates(funds, 0.2, **precise) == []
    assert find_duplicates(["Deniz Portföy Armut Serbest Fon", "Deniz Portföy Ru Serbest Fon"], 0.2, **precise) == []
    assert find_duplicates(["Başaranlar İnşaat Malzemeleri", "BSAARANLAR INSAAT MALZEMELERI"], 0.2, **precise) == [(0, 1, 2 / 29)]


def test_pair_rules_validation_and_persistence(tmp_path):
    from fuzzy_dedupe import Index

    with pytest.raises(ValueError):
        find_duplicates(["a"], 0.1, word_threshold=1.5)
    idx = Index.build(["Pera Emeklilik 2 Fonu"], 0.2, turkish=True, numbers_must_match=True, word_threshold=0.34)
    idx.save(tmp_path / "rules.json")
    back = Index.load(tmp_path / "rules.json")
    assert back.numbers_must_match and back.word_threshold == 0.34
    assert back.query("Pera Emeklilik 3 Fonu") == [] and back.query("PERA EMEKLİLİK 2 FONU") == [(0, 0.0)]


def test_cli_precise(tmp_path, capsys):
    src = tmp_path / "funds.csv"
    src.write_text("name\nPera Emeklilik 2 Fonu\nPera Emeklilik 3 Fonu\nPERA EMEKLİLİK 2 FONU\n", encoding="utf-8")
    assert cli([str(src), "--column", "name", "--turkish", "--precise"]) == 0
    rows = list(csv.reader(capsys.readouterr().out.splitlines()))
    assert [r[:2] for r in rows[1:]] == [["1", "3"]]
