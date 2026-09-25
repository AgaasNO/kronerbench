"""Source-only candidate extraction. This module never receives ground truth."""

import random
import re
from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Any

from kronerbench.parsers.amount import Parsed, normalize, prepare, readings
from kronerbench.parsers.date import parse_date
from kronerbench.parsers.percent import canonical, parse_percent


@dataclass(frozen=True)
class Candidate:
    id: str
    value: int | str
    text: str
    context: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def extract(source: str, seed: int = 42, kind: str = "amount") -> list[Candidate]:
    text = normalize(source)
    found: dict[int | str, tuple[str, str]] = {}
    scales = {1}
    for pattern, multiplier in [
        (r"\bTNOK\b|i tusen|T€", 1000),
        (r"\bMNOK\b|\bmill\.", 10**6),
        (r"\bmrd\.", 10**9),
        (r"[0-9]\s*k\b", 1000),
    ]:
        if re.search(pattern, text, re.I):
            scales.add(multiplier)
    pattern = r"-?\(?[0-9]+(?:[ ,.' ][0-9]{3})*(?:[.,:][0-9]{1,4})?(?:,--?|,–|\.–|\.-|:-|-|\))?(?:\s*(?:%|‰|bp|pp))?"
    if kind == "date":
        pattern = r"[0-9]{4}-[0-9]{2}-[0-9]{2}|[0-9]{1,2}[./][0-9]{1,2}[./-][0-9]{2,4}|[0-9]{1,2}\.\s*[a-zæøå]+\s+[0-9]{4}"
    for match in re.finditer(r"(?<![0-9])(?:" + pattern + r")(?![0-9])", text):
        raw = match[0].strip()
        context = text[max(0, match.start() - 30) : match.end() + 30][:60]
        if kind == "date":
            parsed = parse_date(raw)
            if parsed.accepted:
                assert isinstance(parsed.value, str)
                found.setdefault(parsed.value, (raw, context))
            continue
        if kind == "percent":
            rate = parse_percent(raw)
            if rate.accepted:
                assert isinstance(rate.value, str)
                found.setdefault(rate.value, (raw, context))
        prepared = prepare(re.sub(r"\s*(%|‰|bp|pp)$", "", raw))
        if isinstance(prepared, Parsed):
            continue
        number, _, sign = prepared
        # Extraction deliberately admits decimal and grouped readings of 1.500.
        for value in readings(number, (1, 2, 3, 4)):
            for scale in sorted(scales):
                scaled = value * sign * scale
                signs = {1, -1} if re.search(r"\bCR\b", context) else {1}
                for debit in sorted(signs):
                    amount = scaled * debit
                    if kind == "percent":
                        found.setdefault(canonical(amount), (raw, context))
                    elif amount * 100 == (amount * 100).to_integral_value():
                        found.setdefault(int(amount * Decimal(100)), (raw, context))
    values = list(found.items())
    random.Random(seed).shuffle(values)
    return [
        Candidate(f"c{i}", value, raw, context)
        for i, (value, (raw, context)) in enumerate(values, 1)
    ]
