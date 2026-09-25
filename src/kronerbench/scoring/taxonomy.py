"""First-match error taxonomy, applied only to committed wrong values."""

import re
from decimal import Decimal, InvalidOperation


def digits(value: object) -> str:
    return re.sub("[^0-9]", "", str(value))


def classify(
    expected: int | str | None,
    committed: int | str,
    source: str,
    candidates: list[int | str],
    kind: str = "amount",
) -> str:
    if kind == "date":
        e, c = str(expected).split("-"), str(committed).split("-")
        if len(e) == len(c) == 3 and e == [c[0], c[2], c[1]]:
            return "date_swap"
    try:
        a, b = Decimal(str(expected)), Decimal(str(committed))
    except InvalidOperation:
        a = b = Decimal(0)
    if a and b == -a:
        return "sign"
    if a and b / a in [Decimal(10) ** n for n in [-12, -9, -6, -3, -2, -1, 1, 2, 3, 6, 9, 12]]:
        return "scale_10ⁿ"
    if committed in candidates:
        return "wrong_number"
    x, y = digits(expected), digits(committed)
    if len(x) == len(y):
        changed = [i for i in range(len(x)) if x[i] != y[i]]
        if (
            len(changed) == 2
            and changed[1] == changed[0] + 1
            and x[changed[0]] == y[changed[1]]
            and x[changed[1]] == y[changed[0]]
        ):
            return "transposition"
    if len(x) == len(y) + 1 and any(x[:i] + x[i + 1 :] == y for i in range(len(x))):
        return "digit_drop"
    if len(y) == len(x) + 1 and any(y[:i] + y[i + 1 :] == x for i in range(len(y))):
        return "digit_insert"
    if len(x) == len(y) and sum(a != b for a, b in zip(x, y, strict=True)) == 1:
        return "digit_sub"
    if a != b and abs(a - b) < (100 if kind == "amount" else 1):
        return "rounding"
    if y not in digits(source):
        return "hallucination"
    return "other"
