from kronerbench.parsers.amount import Parsed, parse_amount, parse_naive
from kronerbench.parsers.date import parse_date
from kronerbench.parsers.percent import parse_percent


def parse_value(raw: str, parser: str = "safe-eu") -> Parsed:
    if parser == "safe-eu":
        return parse_amount(raw)
    if parser == "safe-no":
        return parse_amount(raw, norway_only=True)
    if parser == "naive":
        return parse_naive(raw)
    if parser == "percent":
        return parse_percent(raw)
    if parser == "date":
        return parse_date(raw)
    raise ValueError(f"Unknown parser {parser}")
