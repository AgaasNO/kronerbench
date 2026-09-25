"""Rates are stored as canonical decimal percentage points, never fractions."""

import re
from decimal import Decimal

from kronerbench.parsers.amount import Parsed, normalize, prepare, readings, reject


def canonical(value: Decimal) -> str:
    return format(value.normalize(), "f") if value else "0"


def parse_percent(raw: str, strict: bool = False) -> Parsed:
    if strict:
        if not re.fullmatch(r"-?[0-9]+(?:,[0-9]{1,4})?", raw):
            return reject("write a percentage as digits with an optional comma and 1 to 4 decimals")
        return Parsed(True, canonical(Decimal(raw.replace(",", "."))), grammar="strict-percent")
    text = normalize(raw).strip()
    unit = re.search(r"\s*(%|‰|bp|pp)$", text, re.I)
    scale = Decimal(1)
    if unit:
        scale = {"‰": Decimal("0.1"), "bp": Decimal("0.01")}.get(unit[1].lower(), Decimal(1))
        text = text[: unit.start()]
    parsed = prepare(text)
    if isinstance(parsed, Parsed):
        return parsed
    number, currency, sign = parsed
    if currency:
        return reject("currency is not a rate unit")
    found = readings(number, (1, 2, 3, 4))
    if not found:
        return reject("malformed percentage")
    if len(found) > 1:
        return reject("ambiguous percentage separator")
    value = next(iter(found)) * sign
    if unit is None and value != value.to_integral_value():
        return reject("bare fractional rate is ambiguous; include %")
    return Parsed(True, canonical(value * scale), sign=sign, grammar="percent")
