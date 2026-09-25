"""Strict case schema and source-independent metadata."""

import re
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, model_validator

from kronerbench.config import ROOT, digest

SUITES = {
    "no-formats": 60,
    "eu-formats": 70,
    "ambiguity": 30,
    "notation": 25,
    "scale": 25,
    "words": 25,
    "unicode": 25,
    "long": 40,
    "distractors": 30,
    "documents": 40,
    "percent": 45,
    "dates": 30,
    "derived": 25,
}


class Field(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_minor: int | None = None
    expected_rate: str | None = None
    expected_date: str | None = None
    flag: bool = False
    currency: str = "NOK"

    @model_validator(mode="after")
    def one_truth(self) -> "Field":
        if (
            sum(
                [
                    self.expected_minor is not None,
                    self.expected_rate is not None,
                    self.expected_date is not None,
                    self.flag,
                ]
            )
            != 1
        ):
            raise ValueError("A field must have exactly one expected value or FLAG.")
        return self

    @property
    def expected(self) -> int | str | None:
        if self.expected_minor is not None:
            return self.expected_minor
        return self.expected_rate if self.expected_rate is not None else self.expected_date


class Case(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    suite: str
    lang: str = "nb"
    source: str
    instruction: str = "Record the amount to pay."
    fields: dict[str, Field]
    ambiguity: Literal["none", "context", "true"] = "none"
    flag_ok: bool = False
    tags: list[str]
    rationale: str
    origin: Literal["handwritten", "generated"] = "handwritten"

    @model_validator(mode="after")
    def valid(self) -> "Case":
        if self.suite not in SUITES or not self.fields or not self.rationale.strip():
            raise ValueError("Unknown suite, empty fields or missing rationale.")
        return self

    @property
    def kind(self) -> str:
        return {"percent": "percent", "dates": "date"}.get(self.suite, "amount")

    def metadata(self, field: str) -> dict[str, object]:
        f = self.fields[field]
        number = (
            str(abs(f.expected_minor) // 100)
            if f.expected_minor is not None
            else re.sub(r"[^0-9]", "", str(f.expected or ""))
        )
        return dict(
            digits=len(number),
            repeat_score=max((number.count(d) for d in set(number)), default=0)
            / max(1, len(number)),
            sep_style=self.tags[0],
            currency=f.currency,
            lang=self.lang,
            ambiguity=self.ambiguity,
            distractors=sum(1 for tag in self.tags if "distractor" in tag),
        )


def load_cases(root: Path = ROOT) -> list[Case]:
    import json

    cases: list[Case] = []
    for path in sorted((root / "cases/handwritten").glob("*.yaml")):
        cases.extend(Case.model_validate(c) for c in yaml.safe_load(path.read_text()) or [])
    for path in sorted((root / "cases/generated").glob("*.jsonl")):
        cases.extend(
            Case.model_validate(json.loads(line)) for line in path.read_text().splitlines()
        )
    ids = [c.id for c in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate case ids.")
    return sorted(cases, key=lambda c: c.id)


def case_hash(cases: list[Case]) -> str:
    return digest([c.model_dump() for c in cases])
