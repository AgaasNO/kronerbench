from hypothesis import given
from hypothesis import strategies as st

from kronerbench.parsers.amount import parse_amount


@given(
    st.integers(min_value=-(10**14), max_value=10**14), st.sampled_from([" ", ".", "'", "\u202f"])
)
def test_european_roundtrip(minor, sep):
    whole, cents = divmod(abs(minor), 100)
    raw = ("-" if minor < 0 else "") + f"{whole:,}".replace(",", sep) + f",{cents:02}"
    assert parse_amount(raw).value == minor


@given(st.integers(min_value=-(10**14), max_value=10**14))
def test_english_roundtrip(minor):
    whole, cents = divmod(abs(minor), 100)
    raw = ("-" if minor < 0 else "") + f"{whole:,}.{cents:02}"
    assert parse_amount(raw).value == minor
