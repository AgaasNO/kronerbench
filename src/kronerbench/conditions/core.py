"""A condition owns its prompt, schema and validator."""

import re
from decimal import Decimal
from typing import Any

from kronerbench.cases.model import Case
from kronerbench.config import ROOT
from kronerbench.parsers.amount import Parsed, parse_amount, parse_json_number, parse_strict, reject
from kronerbench.parsers.date import parse_date
from kronerbench.parsers.extract import Candidate
from kronerbench.parsers.percent import canonical, parse_percent
from kronerbench.parsers.provenance import occurs

CONDITIONS = [
    "strict",
    "strict_constrained",
    "lenient",
    "verbatim",
    "json_number",
    "minor_units",
    "select",
]


def property_name(case: Case, condition: str) -> str:
    if condition == "select":
        return "candidate_id"
    if case.kind == "date":
        return "date"
    if case.kind == "percent":
        return "rate_percent"
    return {"verbatim": "amount_as_written", "minor_units": "amount_minor"}.get(condition, "amount")


def prompt(case: Case, condition: str, lang: str = "en") -> str:
    text = (ROOT / f"prompts/{lang}/{condition}.md").read_text()
    if case.kind == "date":
        text += "\nFor this date task, the date field replaces the amount. " + (
            "Write ISO YYYY-MM-DD."
            if condition.startswith("strict")
            else "Record the date. Use the requested tool schema."
        )
    elif case.kind == "percent":
        text += "\nFor this rate task, use percentage points: 25 means 25%, not 0.25. " + (
            "Write digits with an optional comma and 1 to 4 decimals."
            if condition.startswith("strict")
            else "Include the percent unit in string values, unless copying verbatim."
        )
    return text


def schema(case: Case, condition: str, candidates: list[Candidate]) -> list[dict[str, Any]]:
    prop = property_name(case, condition)
    value: dict[str, Any] = {"type": "string"}
    if condition == "select":
        value["enum"] = [c.id for c in candidates] + ["none_of_these"]
    elif case.kind != "date" and condition == "json_number":
        value = {"type": "number"}
    elif case.kind == "amount" and condition == "minor_units":
        value = {"type": "integer"}
    if condition == "strict_constrained":
        value["pattern"] = {
            "amount": r"^-?[0-9]+,[0-9]{2}$",
            "percent": r"^-?[0-9]+(?:,[0-9]{1,4})?$",
            "date": r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$",
        }[case.kind]
    props = {"field": {"type": "string", "enum": list(case.fields)}, prop: value}
    if case.kind == "amount" and condition != "select":
        props["currency"] = {"type": "string", "description": "ISO 4217 currency code, e.g. NOK."}
    record: dict[str, Any] = {
        "name": "record_amount",
        "description": "Record one requested field in the ledger.",
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "required": list(props),
            "properties": props,
        },
    }
    flag: dict[str, Any] = {
        "name": "flag_for_review",
        "description": "Flag one uncertain field for human review.",
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "required": ["field", "reason"],
            "properties": {"field": props["field"], "reason": {"type": "string"}},
        },
    }
    if condition == "strict_constrained":
        record["strict"] = True
        flag["strict"] = True
    return [{"type": "function", "function": record}, {"type": "function", "function": flag}]


def validate(
    case: Case, condition: str, args: dict[str, Any], candidates: list[Candidate]
) -> Parsed:
    prop = property_name(case, condition)
    spec = schema(case, condition, candidates)[0]["function"]["parameters"]
    if set(args) != set(spec["required"]) or args.get("field") not in case.fields:
        return reject("unknown field, missing property or unexpected property")
    raw = args[prop]
    if (
        case.kind == "amount"
        and condition != "select"
        and (
            not isinstance(args["currency"], str) or not re.fullmatch("[A-Z]{3}", args["currency"])
        )
    ):
        return reject("currency must be a three-letter ISO code")
    if condition == "select":
        for candidate in candidates:
            if raw == candidate.id:
                return Parsed(True, candidate.value, grammar="select")
        return reject("candidate id is not listed")
    if condition == "json_number" and case.kind != "date":
        if case.kind == "amount":
            return parse_json_number(raw)
        if isinstance(raw, bool) or not isinstance(raw, (int, Decimal)):
            return reject("expected a JSON number")
        return Parsed(True, canonical(Decimal(raw)), grammar="numeric-percent")
    if condition == "minor_units" and case.kind == "amount":
        return (
            Parsed(True, raw, grammar="minor-units")
            if type(raw) is int
            else reject("expected an integer")
        )
    if not isinstance(raw, str):
        return reject("expected a string")
    if condition == "verbatim" and not occurs(raw, case.source):
        return reject("does not appear in the source. Copy the amount exactly as written.")
    strict = condition.startswith("strict")
    if case.kind == "date":
        return parse_date(raw, strict)
    if case.kind == "percent":
        return parse_percent(raw, strict)
    return parse_strict(raw) if strict else parse_amount(raw)


def error_message(raw: object, reason: str, style: str = "neutral") -> str:
    return "Invalid format." if style == "bare" else f"Rejected '{raw}': {reason}"
