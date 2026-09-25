"""Static report with classic scripts so file:// needs neither fetch nor a server."""

import json
import shutil
import sqlite3
from pathlib import Path

import polars as pl

from kronerbench.config import ROOT, read_json


def build_report(run: Path, out: Path | None = None) -> Path:
    target = out or ROOT / "reports" / run.name
    target.mkdir(parents=True, exist_ok=True)
    static = Path(__file__).parent / "static"
    if not (static / "app.js").exists():
        raise FileNotFoundError(
            "Prebuilt UI missing. In a source checkout run pnpm --dir ui install && pnpm --dir ui build."
        )
    shutil.copytree(static, target / "assets", dirs_exist_ok=True)
    with sqlite3.connect(run / "transcripts.sqlite") as db:
        transcripts = {
            key: dict(request=json.loads(request), response=json.loads(response))
            for key, request, response in db.execute("SELECT key,request,response FROM responses")
        }
    payload = dict(
        summary=read_json(run / "summary.json"),
        manifest=read_json(run / "manifest.json"),
        cases=read_json(run / "cases.json"),
        fields=pl.read_parquet(run / "fields.parquet").to_dicts(),
        trials=[json.loads(line) for line in (run / "trials.jsonl").read_text().splitlines()],
        transcripts=transcripts,
        prompts={
            str(p.relative_to(ROOT)): p.read_text()
            for p in sorted((ROOT / "prompts").glob("*/*.md"))
        },
        analysis_plan=(ROOT / "ANALYSIS_PLAN.md").read_text()
        if (ROOT / "ANALYSIS_PLAN.md").exists()
        else "Analysis plan has not been frozen. This report cannot be treated as a preregistered result.",
    )
    (target / "data").mkdir(exist_ok=True)
    encoded = (
        json.dumps(payload, ensure_ascii=False, allow_nan=False)
        .replace("<", "\\u003c")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )
    (target / "data/run.js").write_text("window.KRONERBENCH = " + encoded + ";\n")
    (target / "data/summary.json").write_text(
        json.dumps(payload["summary"], ensure_ascii=False, indent=2) + "\n"
    )
    css = next(static.glob("*.css")).name
    (target / "index.html").write_text(
        f'<!doctype html>\n<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="Silent money errors in model tool calls, with paired comparisons and auditable transcripts."><title>KronerBench</title><link rel="stylesheet" href="assets/{css}"></head><body><div id="app"></div><script src="data/run.js"></script><script src="assets/app.js"></script></body></html>\n'
    )
    latest = ROOT / "reports/latest"
    if target.resolve() != latest.resolve():
        if latest.exists():
            shutil.rmtree(latest)
        shutil.copytree(target, latest)
    return (target / "index.html").resolve()
