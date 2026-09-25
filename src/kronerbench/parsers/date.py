"""Conservative calendar dates; slash forms need unambiguous order."""

import re
from datetime import date

from kronerbench.parsers.amount import Parsed, normalize, reject

MONTHS = {
    name: i
    for i, name in enumerate(
        "januar februar mars april mai juni juli august september oktober november desember".split(),
        1,
    )
}


def parse_date(raw: str, strict: bool = False) -> Parsed:
    text = normalize(raw).strip().lower()
    iso = re.fullmatch(r"([0-9]{4})-([0-9]{2})-([0-9]{2})", text)
    if iso:
        year, month, day = map(int, iso.groups())
    elif strict:
        return reject("write a date as YYYY-MM-DD")
    else:
        dotted = re.fullmatch(r"([0-9]{1,2})\.([0-9]{1,2})\.([0-9]{4})", text)
        informal = re.fullmatch(r"([0-9]{1,2})/([0-9]{1,2})-([0-9]{2})", text)
        slash = re.fullmatch(r"([0-9]{1,2})/([0-9]{1,2})/([0-9]{4})", text)
        named = re.fullmatch(r"([0-9]{1,2})\.\s*([a-zæøå]+)\s+([0-9]{4})", text)
        if dotted or informal or slash:
            match = dotted or informal or slash
            assert match is not None
            day, month, year = map(int, match.groups())
            if slash and day <= 12 and month <= 12:
                return reject("ambiguous slash date: day and month may swap")
            if informal:
                year += 2000
        elif named and named[2] in MONTHS:
            day, month, year = int(named[1]), MONTHS[named[2]], int(named[3])
        else:
            return reject("unrecognised date format")
    try:
        return Parsed(True, date(year, month, day).isoformat(), grammar="date")
    except ValueError:
        return reject("invalid calendar date")
