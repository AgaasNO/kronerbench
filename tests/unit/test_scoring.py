from kronerbench.scoring.stats import cluster_bootstrap, holm, paired, wilson
from kronerbench.scoring.taxonomy import classify


def test_taxonomy_precedence():
    assert classify(12345, -12345, "", []) == "sign"
    assert classify(12345, 123450, "", []) == "scale_10ⁿ"
    assert classify(12345, 99999, "", [99999]) == "wrong_number"
    assert classify(12345, 13245, "", []) == "transposition"
    assert classify(12345, 1345, "", []) == "digit_drop"
    assert classify(12345, 123945, "", []) == "digit_insert"
    assert classify(12345, 92345, "", []) == "digit_sub"
    assert classify("2026-03-04", "2026-04-03", "", [], kind="date") == "date_swap"


def test_statistics_known_counts():
    assert wilson(0, 0) == [None, None]
    assert wilson(0, 100)[1] > 0.03
    result = paired([1] * 10 + [0] * 10, [0] * 20)
    assert result["difference"] == 0.5 and result["p"] < 0.01
    assert paired([0] * 10, [0] * 10)["p"] == 1
    tests = [{"p": 0.01}, {"p": 0.04}, {"p": 0.03}]
    holm(tests)
    assert tests[0]["p_adjusted"] == 0.03
    effect = cluster_bootstrap([("same-case", 1, 0)] * 20 + [("other", 0, 1)] * 20)
    assert effect["cases"] == 2 and effect["difference"] == 0 and effect["ci"] == [-1, 1]
