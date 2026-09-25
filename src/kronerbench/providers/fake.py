"""Deterministic fault injection through the same raw tool-call interface."""

import json
from typing import Any

from kronerbench.cases.model import Case
from kronerbench.conditions.core import property_name
from kronerbench.config import digest
from kronerbench.parsers.extract import Candidate

FAKES = [
    "fake/perfect",
    "fake/english-drift",
    "fake/digit-dropper",
    "fake/retry-corruptor",
    "fake/flagger",
]


def respond(
    case: Case,
    condition: str,
    model: str,
    turn: int,
    pending: list[str],
    candidates: list[Candidate],
    seed: int,
) -> dict[str, Any]:
    calls = []
    for field in pending:
        expected = case.fields[field].expected
        name = "record_amount"
        args: dict[str, Any] = {"field": field}
        if expected is None or model == "fake/flagger":
            name = "flag_for_review"
            args["reason"] = "Review requested by deterministic fixture."
        elif condition == "select":
            args["candidate_id"] = next(
                (c.id for c in candidates if c.value == expected), "none_of_these"
            )
        else:
            value = expected
            drop = (
                model == "fake/digit-dropper"
                and isinstance(value, int)
                and len(str(abs(value) // 100)) >= 4
                and int(digest([case.id, field, seed])[:8], 16) % 10 == 0
            )
            if drop:
                assert isinstance(value, int)
                digits = str(abs(value))
                from kronerbench.scoring.taxonomy import classify

                alternatives = [
                    int(digits[:i] + digits[i + 1 :]) * (-1 if value < 0 else 1)
                    for i in range(1, len(digits))
                ]
                value = next(
                    (
                        v
                        for v in alternatives
                        if classify(value, v, case.source, [c.value for c in candidates])
                        == "digit_drop"
                    ),
                    value,
                )
            if model == "fake/retry-corruptor" and turn > 0 and isinstance(value, int):
                value += 100
            if case.kind == "amount":
                assert isinstance(value, int)
                units, cents = divmod(abs(value), 100)
                canonical = ("-" if value < 0 else "") + f"{units},{cents:02}"
                raw: object = canonical
                if model == "fake/english-drift" or (model == "fake/retry-corruptor" and turn == 0):
                    raw = ("-" if value < 0 else "") + f"{units:,}.{cents:02}"
                if condition == "json_number":
                    raw = {"raw_number": canonical.replace(",", ".")}
                if condition == "minor_units":
                    raw = value
                if condition == "verbatim":
                    match = next(
                        (c for c in candidates if c.value == expected and c.text in case.source),
                        None,
                    )
                    if match:
                        raw = match.text
                args[property_name(case, condition)] = raw
                args["currency"] = case.fields[field].currency
            elif case.kind == "percent":
                args["rate_percent"] = (
                    {"raw_number": str(value)}
                    if condition == "json_number"
                    else str(value).replace(".", ",")
                    + (" %" if condition in ["lenient", "verbatim"] else "")
                )
            else:
                args["date"] = value
        raw = json.dumps(args, ensure_ascii=False)
        # Inject a JSON numeric token without first creating a Python float.
        import re

        raw = re.sub(r'\{"raw_number": "([^"\n]+)"\}', r"\1", raw)
        if condition == "verbatim" and name == "record_amount":
            from kronerbench.conditions.core import validate
            from kronerbench.config import decode_arguments

            checked = validate(case, condition, decode_arguments(raw), candidates)
            if not checked.accepted or checked.value != expected:
                name = "flag_for_review"
                raw = json.dumps(
                    {
                        "field": field,
                        "reason": "The source cannot be copied into an accepted exact value.",
                    }
                )
        calls.append(
            {
                "id": f"fake-{field}-{turn}",
                "type": "function",
                "function": {"name": name, "arguments": raw},
            }
        )
    return {
        "id": f"fake-{digest([case.id, condition, model, turn, seed])[:16]}",
        "model": model,
        "provider": "fake",
        "choices": [{"message": {"role": "assistant", "content": None, "tool_calls": calls}}],
        "usage": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "cost": 0,
            "completion_tokens_details": {"reasoning_tokens": 0},
        },
    }
