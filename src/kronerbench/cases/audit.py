"""Independent answers expose questionable truth; they never rewrite it automatically."""

import json
from pathlib import Path

import polars as pl

from kronerbench.cases.model import SUITES
from kronerbench.config import ROOT, read_json, write_json
from kronerbench.runner.scheduler import run_benchmark


def audit(models: list[str], max_cost: float = 10) -> Path:
    if len(models) != 2 or models[0] == models[1]:
        raise ValueError("Audit requires two different model ids.")
    path = run_benchmark(
        dict(
            profile="standard",
            models=",".join(models),
            conditions="lenient",
            suites=",".join(SUITES),
            sample=470,
            max_cost=max_cost,
            run_id="case-audit",
            resume=(ROOT / "runs/case-audit").exists(),
        )
    )
    rows = pl.read_parquet(path / "fields.parquet").to_dicts()
    cases = {c["id"]: c for c in read_json(path / "cases.json")}
    disputed = []
    for case_id, case in cases.items():
        group = [r for r in rows if r["case_id"] == case_id]
        failed = {r["model"] for r in group if r["outcome"] not in ["correct", "correct_flag"]}
        if set(models) <= failed:
            disputed.append(
                {
                    "case_id": case_id,
                    "status": "open",
                    "source": case["source"],
                    "fields": case["fields"],
                    "answers": group,
                    "judgement": "Open: inspect whether the ground truth, instruction or model answer is wrong. Do not tune to a hypothesis.",
                }
            )
    lines = [
        "# Case audit",
        "",
        f"Independent lenient answers from {models[0]} and {models[1]}.",
        f"All {len(cases)} cases were submitted. Disagreements remain open until adjudicated.",
        "",
    ]
    for item in disputed:
        lines += [
            f"## {item['case_id']} · open",
            "",
            item["source"],
            "",
            "Ground truth: `" + json.dumps(item["fields"], ensure_ascii=False) + "`",
            "",
        ]
        lines += [
            f"- {r['model']}, {r['field']}: {r['committed'] or r['outcome']}; expected {r['expected']}."
            for r in item["answers"]
        ]
        lines += ["", item["judgement"], ""]
    if not disputed:
        lines += ["No case had both models disagree with the expected outcome."]
    (ROOT / "CASE_AUDIT.md").write_text("\n".join(lines) + "\n")
    write_json(
        ROOT / "results/audit.json",
        dict(
            passed=True,
            case_count=len(cases),
            models=models,
            run_id=path.name,
            cost_usd=read_json(path / "manifest.json")["total_cost_usd"],
            disputed=disputed,
        ),
    )
    return path
