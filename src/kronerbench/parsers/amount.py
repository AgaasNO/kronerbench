"""Locale grammars. No context inference and no binary floating point."""

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

SPACE = "\u00a0\u202f\u2009\u2007"
ZERO_WIDTH = "\u200b\u200c\u200d\u2060\ufeff"
TOKENS = {
    "kr": None,
    "kr.": None,
    "nok": "NOK",
    "sek": "SEK",
    "dkk": "DKK",
    "isk": "ISK",
    "eur": "EUR",
    "€": "EUR",
    "chf": "CHF",
    "fr.": "CHF",
    "£": "GBP",
    "zł": "PLN",
    "kč": "CZK",
    "ft": "HUF",
}
TOKEN_PATTERN = "|".join(re.escape(x) for x in sorted(TOKENS, key=len, reverse=True))
CURRENCY = re.compile(rf"^(?P<pre>{TOKEN_PATTERN})\s*|\s*(?P<post>{TOKEN_PATTERN})$", re.I)
WHOLE = re.compile(r"(?:,--?|,–|\.–|\.-|:-)$")


@dataclass(frozen=True)
class Parsed:
    accepted: bool
    value: int | str | None = None
    currency: str | None = None
    sign: int = 1
    grammar: str = ""
    reason: str = ""


def reject(reason: str) -> Parsed:
    return Parsed(False, reason=reason)


def normalize(raw: str) -> str:
    text = raw.translate(
        str.maketrans(
            {**dict.fromkeys(SPACE, " "), **dict.fromkeys(ZERO_WIDTH, None), "−": "-", "’": "'"}
        )
    )
    return re.sub(r"^\s*–", "-", text)


def prepare(raw: str) -> tuple[str, str | None, int] | Parsed:
    text = normalize(raw).strip()
    match = CURRENCY.search(text)
    currency = None
    if match:
        currency = TOKENS[match.group().strip().lower()]
        text = (text[: match.start()] + text[match.end() :]).strip()
    # A suffix denoting zero cents is not a debit sign.
    text = WHOLE.sub("", text)
    sign = 1
    if text.startswith("(") and text.endswith(")"):
        sign, text = -1, text[1:-1].strip()
    elif text.startswith("-"):
        sign, text = -1, text[1:]
    elif text.endswith("-"):
        sign, text = -1, text[:-1]
    if not text or re.search(r"[^0-9 ,.'\:]", text):
        return reject("unsupported sign, currency, scale word or character")
    return text, currency, sign


def readings(
    text: str, decimals: tuple[int, ...] = (2,), norway_only: bool = False
) -> dict[Decimal, list[str]]:
    """Enumerate complete-string grammatical readings, preserving ties."""
    found: dict[Decimal, list[str]] = {}
    specs = [("comma", ",", (" ", ".", "'"))]
    if not norway_only:
        specs += [("dot", ".", (",", " ", "'")), ("colon", ":", (" ", ".", ",", "'"))]
    places = "|".join(f"[0-9]{{{n}}}" for n in decimals)
    for name, decimal, separators in specs:
        fraction = rf"(?:{re.escape(decimal)}({places}))?"
        integers = [r"[0-9]+"] + [
            rf"[0-9]{{1,3}}(?:{re.escape(sep)}[0-9]{{3}})+" for sep in separators
        ]
        for integer in integers:
            match = re.fullmatch(rf"({integer}){fraction}", text)
            if match:
                whole = re.sub(r"[^0-9]", "", match[1])
                value = Decimal(whole + "." + (match[2] or "0"))
                found.setdefault(value, []).append(name)
    return found


def parse_amount(raw: str, norway_only: bool = False) -> Parsed:
    prepared = prepare(raw)
    if isinstance(prepared, Parsed):
        return prepared
    text, currency, sign = prepared
    found = readings(text, norway_only=norway_only)
    if not found:
        return reject(
            "a group separator must be followed by exactly 3 digits; decimals require 2 digits"
        )
    # With exactly two decimal places the complete grammars cannot disagree.
    assert len(found) == 1
    value, grammars = next(iter(found.items()))
    return Parsed(True, int(value * 100) * sign, currency, sign, "+".join(sorted(set(grammars))))


def parse_strict(raw: str) -> Parsed:
    if not re.fullmatch(r"-?[0-9]+,[0-9]{2}", raw):
        return reject(
            "write digits, a comma and exactly two decimals with no thousands separators, e.g. 1234,56. Keep the same value."
        )
    return Parsed(
        True,
        int(Decimal(raw.replace(",", ".")) * 100),
        sign=-1 if raw.startswith("-") else 1,
        grammar="strict",
    )


def parse_json_number(value: object) -> Parsed:
    if isinstance(value, bool) or not isinstance(value, (int, Decimal)):
        return reject("expected a JSON number decoded as Decimal")
    number = Decimal(value)
    if not number.is_finite():
        return reject("number must be finite")
    cents = number * 100
    if cents != cents.to_integral_value():
        return reject("amount has a fraction of a minor unit")
    return Parsed(True, int(cents), sign=-1 if cents < 0 else 1, grammar="json-number")


def parse_naive(raw: str) -> Parsed:
    try:
        value = Decimal(re.sub(r"\s", "", raw).replace(".", "").replace(",", "."))
        if not value.is_finite():
            return reject("number must be finite")
        return Parsed(True, int((value * 100).to_integral_value()), grammar="naive")
    except InvalidOperation:
        return reject("not a number")
