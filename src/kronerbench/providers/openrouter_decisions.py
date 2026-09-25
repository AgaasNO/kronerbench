"""Strict contract boundary for the alpha Decisions endpoint."""

from typing import Any

from kronerbench.cases.model import Case
from kronerbench.parsers.extract import Candidate
from kronerbench.providers.openrouter import ProviderError


def validate_response(data: dict[str, Any], ids: set[str]) -> None:
    try:
        pick = data["answers"]["pick"]
        probs = pick["probabilities"]
        assert pick["choice"] in ids and set(probs) == ids
        assert all(isinstance(p, (int, float)) and 0 <= p <= 1 for p in probs.values())
        assert abs(sum(probs.values()) - 1) < 0.02
        assert 0 <= pick["confidence"] <= 1 and 0 <= data["answers"]["ambiguous"]["noul"] <= 1
        assert isinstance(data["model"], str) and "usage" in data and "cost" in data["usage"]
    except (KeyError, TypeError, AssertionError):
        raise ProviderError(
            "Decisions API contract changed: expected choice, confidence, full probabilities, ambiguous.noul, snapshot and cost."
        ) from None


def request_body(case: Case, field: str, candidates: list[Candidate], model: str) -> dict[str, Any]:
    criteria = {
        c.id: f"{c.value} {'minor units' if case.kind == 'amount' else case.kind} | {c.context}"
        for c in candidates
    }
    criteria["none_of_these"] = "Correct value is absent or cannot be determined."
    return {
        "model": model,
        "state": {"document": case.source, "task": case.instruction, "field": field},
        "questions": {
            "pick": {
                "type": "choice",
                "instructions": "Which candidate is the value requested for this field?",
                "criteria": criteria,
            },
            "ambiguous": {
                "type": "noul",
                "instructions": "A careful bookkeeper could not determine this field with certainty from the document.",
            },
        },
    }
