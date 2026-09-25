import pytest

from kronerbench.cases.generate import generated, verify_catalogue
from kronerbench.cases.model import Case, load_cases
from kronerbench.cases.styles import STYLES
from kronerbench.parsers.amount import parse_amount


@pytest.mark.parametrize("name", list(STYLES))
def test_styles_hand_checked(name):
    style = STYLES[name]
    amount = 123400 if style.whole else 123450
    assert parse_amount(style.render(amount)).value == amount
    # Trailing zero markers and a trailing minus are inherently overlapping.
    if not style.whole:
        assert parse_amount(style.render(-amount)).value == -amount


def test_case_catalogue_and_reproducibility():
    assert verify_catalogue()
    cases = load_cases()
    authored = [c for c in cases if c.origin == "handwritten"]
    assert generated(42, authored) == generated(42, authored)
    assert generated(43, authored) != generated(42, authored)
    assert len(cases) == 470
    assert all(c.rationale for c in authored)
    assert all(
        isinstance(f.expected_minor, int)
        for c in cases
        for f in c.fields.values()
        if f.expected_minor is not None
    )


def test_truth_is_exclusive():
    with pytest.raises(ValueError):
        Case.model_validate(
            dict(
                id="x",
                suite="words",
                source="x",
                tags=[],
                rationale="x",
                fields={"total": {"expected_minor": 1, "flag": True}},
            )
        )
