"""Require an entire number span, with normalization shared by the parser."""

import re

from kronerbench.parsers.amount import normalize

SEPARATORS = " ,.'\u003a"


def occurs(raw: str, source: str) -> bool:
    needle, haystack = normalize(raw), normalize(source)
    if not needle or not any(c.isdigit() for c in needle):
        return False
    for match in re.finditer(re.escape(needle), haystack):
        before, after = haystack[: match.start()], haystack[match.end() :]
        left = bool(before and (before[-1].isdigit() or re.search(r"[0-9][ ,.'\:]+$", before)))
        right = bool(after and (after[0].isdigit() or re.match(r"[ ,.'\:]+[0-9]", after)))
        if not left and not right:
            return True
    return False
