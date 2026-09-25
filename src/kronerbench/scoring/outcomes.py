"""Field-level outcomes: a rejected value can never be a silent error."""

from typing import Any

from kronerbench.cases.model import Case


def outcome(case: Case, field: str, result: dict[str, Any]) -> str:
    action = result["action"]
    truth = case.fields[field]
    if action == "api_error":
        return "api_error"
    if action == "flag":
        return "correct_flag" if truth.flag or case.flag_ok else "loud_flag"
    if action == "no_call":
        return "loud_no_call"
    if action == "exhausted":
        return "loud_exhausted"
    if action == "record":
        return (
            "correct"
            if not truth.flag and result.get("value") == truth.expected
            else "silent_error"
        )
    raise ValueError(f"Unknown action {action}")
