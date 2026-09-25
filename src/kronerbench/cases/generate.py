"""Reproducible catalogue generation; generated cases are never called handwritten."""

import json
import random
from collections import Counter
from datetime import date
from pathlib import Path

from kronerbench.cases.model import SUITES, Case, case_hash, load_cases
from kronerbench.cases.styles import STYLES, render
from kronerbench.config import ROOT, dumps

TEMPLATES = [
    "Kvittering\nÅ betale {amount}",
    "Faktura fra Eksempelfjell Test AS\nTotal {amount}",
    "bank_csv;amount\nsynthetic;{amount}",
    "Email: The amount to pay is {amount}.",
    "Chat: Hei, totalen er {amount}.",
    "| Description | Total |\n| Test service | {amount} |",
    "KREDIT/DEBIT\nBeløp til bokføring: {amount}",
    "Booking note\nLedger amount: {amount}",
    "Payment advice\nAmount due: {amount}",
    "Purchase order for Testkunde\nFinal amount: {amount}",
]


def generated(seed: int, handwritten: list[Case]) -> list[Case]:
    rng = random.Random(seed)
    counts = Counter(c.suite for c in handwritten)
    result = []
    for suite, total in SUITES.items():
        for index in range(total - counts[suite]):
            minor = max(1, round(10 ** rng.uniform(0, 10)))
            if rng.random() < 0.2:
                minor = int(str(rng.randint(1, 9)) * rng.randint(4, 10))
            names = list(STYLES)
            if suite == "no-formats":
                names = [
                    "canonical",
                    "space-comma",
                    "dot-comma",
                    "kr-prefix",
                    "dash-zero",
                    "double-dash",
                ]
            if suite == "unicode":
                names = ["nbsp", "narrow-nbsp", "thin-space", "figure-space", "curly-apostrophe"]
            if suite == "notation":
                names = ["parentheses", "sap-minus", "unicode-minus", "en-dash-minus"]
            style = rng.choice(names)
            if STYLES[style].whole:
                minor = minor // 100 * 100
            if suite == "notation":
                minor = -minor
            if suite == "long":
                minor = (
                    int(("7" if index % 4 == 0 else "100010001012")[:1] * (4 + index % 9)) * 100
                    + index % 100
                )
            if suite == "long" and STYLES[style].whole:
                minor = minor // 100 * 100
            currency = STYLES[style].currency
            source = TEMPLATES[index % len(TEMPLATES)].format(amount=render(minor, style))
            fields = {"total": {"expected_minor": minor, "currency": currency}}
            instruction = "Record the amount to pay."
            rationale = (
                f"The labeled total uses the {style} convention; preserve its value and sign."
            )
            ambiguity = "none"
            if suite == "ambiguity":
                source = f"Unresolved draft: total is either {index + 10},00 NOK or {index + 20},00 NOK. No final choice."
                fields = {"total": {"flag": True, "currency": "NOK"}}
                ambiguity = "true"
                rationale = "The document explicitly leaves two alternatives unresolved."
            elif suite == "scale":
                units = rng.randint(1, 10000)
                source = f"Beløp i TNOK\nÅ betale {units:,}".replace(",", " ")
                fields = {"total": {"expected_minor": units * 100000, "currency": "NOK"}}
                rationale = "A TNOK cell denotes thousands of kroner."
            elif suite == "words":
                words = [
                    ("ti", 10),
                    ("tjue", 20),
                    ("tretti", 30),
                    ("førti", 40),
                    ("femti", 50),
                    ("seksti", 60),
                    ("sytti", 70),
                    ("åtti", 80),
                    ("nitti", 90),
                    ("hundre", 100),
                ]
                word, value = words[index % len(words)]
                source = f"Å betale {word} kroner."
                fields = {"total": {"expected_minor": value * 100, "currency": "NOK"}}
                rationale = "The total is stated in Norwegian words."
            elif suite == "distractors":
                source = (
                    f"SYNTETISK TESTDOKUMENT\nKID 0000000000000\nKonto 0000 00 00000\nOrdre TEST-{index:04}\n"
                    + source
                )
            elif suite == "documents":
                net = rng.randint(100, 100000) * 100
                vat = net // 4
                source = f"SYNTETISK FAKTURA\nNetto NOK {render(net, 'space-comma')}\nMva NOK {render(vat, 'space-comma')}\nÅ betale NOK {render(net + vat, 'space-comma')} "
                fields = {
                    name: {"expected_minor": value, "currency": "NOK"}
                    for name, value in [("net", net), ("vat", vat), ("total", net + vat)]
                }
                instruction = "Record net, vat and total."
                rationale = "The invoice labels all three values separately."
            elif suite == "percent":
                n = rng.randint(1, 999)
                raw = f"{n // 10},{n % 10}"
                source = f"Rate {raw} %. Record the percentage."
                fields = {
                    "rate": {
                        "expected_rate": f"{n // 10}.{n % 10}".removesuffix(".0"),
                        "currency": "PERCENT",
                    }
                }
                instruction = "Record the rate as percentage points."
                rationale = "A percentage is already in percentage points."
            elif suite == "dates":
                d = date(2026, rng.randint(1, 12), rng.randint(1, 28))
                source = f"Dato {d.day:02}.{d.month:02}.{d.year}"
                fields = {"date": {"expected_date": d.isoformat(), "currency": "DATE"}}
                instruction = "Record the date."
                rationale = "A dotted European date is day-first."
            elif suite == "derived":
                net = rng.randint(1, 10000) * 100
                source = f"Netto NOK {render(net, 'space-comma')}; mva 25 %. Calculate gross."
                fields = {"total": {"expected_minor": net * 5 // 4, "currency": "NOK"}}
                instruction = "Calculate and record gross."
                rationale = "Multiply the stated net amount by 1.25."
            result.append(
                Case.model_validate(
                    dict(
                        id=f"{suite}-g{index + 1:04}",
                        suite=suite,
                        source=source,
                        fields=fields,
                        instruction=instruction,
                        rationale=rationale,
                        tags=[style]
                        + (["identifier-distractor"] if suite == "distractors" else []),
                        ambiguity=ambiguity,
                        origin="generated",
                    )
                )
            )
    return result


def build(seed: int = 42, root: Path = ROOT) -> dict[str, object]:
    import yaml

    authored = [
        Case.model_validate(c)
        for p in sorted((root / "cases/handwritten").glob("*.yaml"))
        for c in yaml.safe_load(p.read_text())
    ]
    cases = generated(seed, authored)
    directory = root / "cases/generated"
    directory.mkdir(parents=True, exist_ok=True)
    for suite in SUITES:
        (directory / f"{suite}.jsonl").write_text(
            "".join(dumps(c.model_dump()) + "\n" for c in cases if c.suite == suite)
        )
    return stats(root)


def stats(root: Path = ROOT) -> dict[str, object]:
    cases = load_cases(root)
    return dict(
        cases=len(cases),
        fields=sum(len(c.fields) for c in cases),
        suites=dict(Counter(c.suite for c in cases)),
        origins=dict(Counter(c.origin for c in cases)),
        hash=case_hash(cases),
        flags=sum(f.flag for c in cases for f in c.fields.values()),
    )


def verify_catalogue() -> str:
    cases = load_cases()
    assert len(cases) >= 450 and set(c.suite for c in cases) == set(SUITES), (
        "Need 450 cases across 13 suites."
    )
    expected = generated(42, [c for c in cases if c.origin == "handwritten"])
    actual = [c for c in cases if c.origin == "generated"]
    assert case_hash(sorted(expected, key=lambda c: c.id)) == case_hash(actual), (
        "Generated catalogue is not reproducible with seed 42."
    )
    return json.dumps(stats())
