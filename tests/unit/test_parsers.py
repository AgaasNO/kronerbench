import json
from decimal import Decimal
from pathlib import Path

import pytest

from kronerbench.config import decode_arguments
from kronerbench.parsers import parse_value
from kronerbench.parsers.amount import parse_json_number, parse_strict, readings
from kronerbench.parsers.date import parse_date
from kronerbench.parsers.extract import extract
from kronerbench.parsers.percent import parse_percent
from kronerbench.parsers.provenance import occurs

VECTORS = json.loads((Path(__file__).parents[1] / "parser_vectors.json").read_text())


@pytest.mark.parametrize("vector", VECTORS)
def test_vectors(vector):
    result = parse_value(vector["raw"], vector["parser"])
    assert result.accepted == vector["accepted"], result
    assert result.value == vector["value"], result


def test_strict_and_json():
    assert parse_strict("-1234,50").value == -123450
    assert parse_strict("0,00").value == 0
    assert not parse_strict("1.00").accepted
    assert not parse_strict("١,00").accepted
    for value in [True, "1.00", 1.0, Decimal("NaN"), Decimal("Inf"), Decimal("0.001")]:
        assert not parse_json_number(value).accepted
    assert parse_json_number(Decimal("-1234.50")).value == -123450
    assert parse_json_number(1).value == 100
    assert decode_arguments('{"amount": 90071992547409.93}')["amount"] == Decimal(
        "90071992547409.93"
    )
    with pytest.raises(ValueError):
        decode_arguments("[]")
    with pytest.raises(ValueError):
        decode_arguments('{"amount": NaN}')


def test_provenance():
    for raw, source in [
        ("2 500", "12 500"),
        ("2 500", "2 500,00"),
        ("500", "1 500"),
        ("500", "1.500"),
        ("12", "123"),
        ("", "12"),
        ("abc", "abc"),
        ("1", "12"),
    ]:
        assert not occurs(raw, source)
    for raw, source in [
        ("2 500", "Total: 2 500 NOK"),
        ("1 000,00", "NOK 1\u00a0000\u200b,00"),
        ("500", "1500; 500"),
    ]:
        assert occurs(raw, source)


def test_rates_and_dates():
    assert parse_percent("25,50", strict=True).value == "25.5"
    assert not parse_percent("25%", strict=True).accepted
    assert not parse_date("3.4.2026", strict=True).accepted
    assert parse_date("2026-04-03", strict=True).value == "2026-04-03"
    assert set(readings("1,250", (1, 2, 3, 4))) == {Decimal("1.250"), Decimal("1250")}
    with pytest.raises(ValueError):
        parse_value("1", "unknown")


def test_extractor_source_only():
    values = {c.value for c in extract("Total 1.500; cell 12,00. Beløp i TNOK")}
    assert {150, 150000, 1200, 1200000} <= values
    assert all(c.id.startswith("c") and len(c.context) <= 60 for c in extract("100,00 200,00"))
    assert extract("no figures") == []
    assert {c.value for c in extract("500 CR")} >= {-50000, 50000}
    assert {c.value for c in extract("25,5 %", kind="percent")} >= {"25.5"}
    assert {c.value for c in extract("0,25", kind="percent")} == {"0.25"}
    assert {c.value for c in extract("3/4-26 2026-04-03", kind="date")} == {"2026-04-03"}
    assert extract("99/99/9999", kind="date") == []
    assert extract("(12") == []
    assert extract("1,2345") == []
    assert extract("100,00")[0].to_dict()["value"] == 10000
