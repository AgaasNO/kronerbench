"""Re-score immutable attempts. All report findings derive from these rows."""

import itertools
import json
import math
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path
from typing import Any

import polars as pl

from kronerbench.cases.model import Case
from kronerbench.conditions.core import property_name
from kronerbench.config import decode_arguments, digest, read_json, write_json
from kronerbench.parsers import parse_value
from kronerbench.scoring.outcomes import outcome
from kronerbench.scoring.stats import cluster_bootstrap, holm, paired, wilson
from kronerbench.scoring.taxonomy import classify, digits


def signature(raw: str) -> str:
    result = parse_value(raw)
    if result.accepted:
        return digits(result.value)
    return digits(raw)


def field_rows(
    run_id: str, trials: list[dict[str, Any]], cases: dict[str, Case]
) -> list[dict[str, Any]]:
    rows = []
    for trial in trials:
        if trial["skip_reason"]:
            continue
        case = cases[trial["case_id"]]
        for field, truth in case.fields.items():
            result = trial["results"][field]
            state = outcome(case, field, result)
            attempts = [a for a in trial["attempts"] if a["field"] == field]
            prop = property_name(case, trial["condition"])
            raws = []
            for attempt in attempts:
                try:
                    raws.append(decode_arguments(attempt["raw_arguments"]).get(prop))
                except (ValueError, TypeError):
                    raws.append(None)
            rejected = [
                (a, r)
                for a, r in zip(attempts, raws, strict=True)
                if not a["accepted"] and isinstance(r, str)
            ]
            retry = bool(rejected and result["action"] == "record")
            first_rejected = rejected[0][1] if rejected else None
            final_raw = raws[-1] if raws else None
            drift = retry and signature(str(first_rejected)) != signature(str(final_raw))
            safe_rejected = (
                parse_value(
                    str(first_rejected),
                    "percent"
                    if case.kind == "percent"
                    else "date"
                    if case.kind == "date"
                    else "safe-eu",
                )
                if rejected
                else None
            )
            rejected_correct = bool(
                safe_rejected and safe_rejected.accepted and safe_rejected.value == truth.expected
            )
            offline = {}
            if (
                trial["condition"] == "lenient"
                and case.kind == "amount"
                and raws
                and isinstance(raws[0], str)
            ):
                for parser in ["safe-eu", "safe-no", "naive"]:
                    parsed = parse_value(raws[0], parser)
                    offline[parser] = (
                        outcome(case, field, {"action": "record", "value": parsed.value})
                        if parsed.accepted
                        else "loud_exhausted"
                    )
            float_changed = False
            if (
                trial["condition"] == "json_number"
                and case.kind == "amount"
                and raws
                and isinstance(raws[0], (int, Decimal))
            ):
                value = Decimal(raws[0])
                rounded = round(float(value) * 100)
                float_changed = Decimal(rounded) != value * 100
            metadata = case.metadata(field)
            row = dict(
                schema_version="1.0",
                run_id=run_id,
                trial_id=digest([trial["trial_id"], field])[:24],
                case_id=case.id,
                suite=case.suite,
                field=field,
                model=trial["model"],
                condition=trial["condition"],
                repeat=trial["repeat"],
                expected=str(truth.expected) if truth.expected is not None else "FLAG",
                committed=str(result.get("value")) if result["action"] == "record" else None,
                outcome=state,
                error_class=classify(
                    truth.expected,
                    result["value"],
                    case.source,
                    [c["value"] for c in trial["candidates"]],
                    case.kind,
                )
                if state == "silent_error"
                else None,
                attempts=len(attempts),
                first_attempt_valid=bool(attempts and attempts[0]["accepted"]),
                retry_eligible=retry,
                retry_drift=drift,
                retry_corruption=retry and rejected_correct and state == "silent_error",
                retry_rescue=retry and not rejected_correct and state == "correct",
                safe_eu_outcome=offline.get("safe-eu"),
                naive_outcome=offline.get("naive"),
                safe_no_outcome=offline.get("safe-no"),
                float_changed=float_changed,
                jev_choice=result.get("jev_choice"),
                jev_confidence=result.get("jev_confidence"),
                jev_probs=json.dumps(result.get("jev_probs")),
                jev_ambiguous=result.get("jev_ambiguous"),
                jev_candidate_value=str(result["jev_candidate_value"])
                if result.get("jev_candidate_value") is not None
                else None,
                verifier_noul=result.get("verifier_noul"),
                currency_ok=(result.get("currency") == truth.currency)
                if result["action"] == "record"
                and case.kind == "amount"
                and trial["condition"] != "select"
                else None,
                cost_usd=(trial["cost_usd"] + trial.get("cached_cost_usd", 0)) / len(case.fields),
                latency_ms=trial["latency_ms"],
                input_tokens=trial["input_tokens"] / len(case.fields),
                output_tokens=trial["output_tokens"] / len(case.fields),
                reasoning_tokens=trial["reasoning_tokens"] / len(case.fields),
                extractor_miss=field in trial["extractor_miss"],
                **metadata,
            )
            rows.append(row)
    return rows


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    scored = [r for r in rows if r["outcome"] != "api_error"]
    n = len(scored)
    silent = sum(r["outcome"] == "silent_error" for r in scored)
    success = sum(r["outcome"] in ["correct", "correct_flag"] for r in scored)
    loud = n - silent - success
    latency = sorted(r["latency_ms"] for r in rows)
    eligible = [r for r in rows if r["retry_eligible"]]
    return dict(
        n=n,
        trials=len({(r["case_id"], r["repeat"]) for r in rows}),
        silent=silent,
        ser=silent / n if n else None,
        ser_ci=wilson(silent, n),
        accuracy=success / n if n else None,
        accuracy_ci=wilson(success, n),
        loud_rate=loud / n if n else None,
        loud_ci=wilson(loud, n),
        api_errors=len(rows) - n,
        compliance=sum(r["first_attempt_valid"] for r in scored) / n if n else None,
        retry_drift=sum(r["retry_drift"] for r in eligible) / len(eligible) if eligible else None,
        retry_eligible=len(eligible),
        retry_corruption=sum(r["retry_corruption"] for r in rows),
        retry_rescue=sum(r["retry_rescue"] for r in rows),
        cost_usd=sum(r["cost_usd"] for r in rows),
        usd_per_1000=sum(r["cost_usd"] for r in rows) / n * 1000 if n else None,
        p50_ms=latency[len(latency) // 2] if latency else None,
        p95_ms=latency[min(len(latency) - 1, math.ceil(len(latency) * 0.95) - 1)]
        if latency
        else None,
        input_tokens=sum(r["input_tokens"] for r in rows),
        output_tokens=sum(r["output_tokens"] for r in rows),
        reasoning_tokens=sum(r["reasoning_tokens"] for r in rows),
    )


def calibration(rows: list[dict[str, Any]]) -> dict[str, Any]:
    jev = [r for r in rows if r["jev_confidence"] is not None]
    cal = [r for r in jev if int(digest(r["case_id"])[:8], 16) % 100 < 30]
    evaluation = [r for r in jev if r not in cal]
    thresholds = [i / 100 for i in range(101)]

    def curve(data: list[dict[str, Any]]) -> list[dict[str, Any]]:
        values = []
        for threshold in thresholds:
            committed = [
                r
                for r in data
                if r["jev_confidence"] >= threshold
                and r["jev_ambiguous"] < 0.5
                and r["jev_candidate_value"] is not None
            ]
            errors = sum(r["jev_candidate_value"] != r["expected"] for r in committed)
            values.append(
                dict(
                    threshold=threshold,
                    coverage=len(committed) / len(data) if data else 0,
                    ser=errors / len(committed) if committed else None,
                    n=len(committed),
                    ser_ci=wilson(errors, len(committed)),
                )
            )
        return values

    cal_curve = curve(cal)
    eligible = [p for p in cal_curve if p["n"] >= 10 and p["ser"] <= 0.01]
    threshold = min((p["threshold"] for p in eligible), default=1.01)
    bins = []
    ece = 0.0
    for index in range(10):
        group = [r for r in evaluation if min(9, int(r["jev_confidence"] * 10)) == index]
        if group:
            confidence = sum(r["jev_confidence"] for r in group) / len(group)
            accuracy = sum(r["jev_candidate_value"] == r["expected"] for r in group) / len(group)
            bins.append(dict(confidence=confidence, accuracy=accuracy, n=len(group)))
            ece += len(group) / max(1, len(evaluation)) * abs(confidence - accuracy)
    return dict(
        threshold=threshold,
        calibration_n=len(cal),
        evaluation_n=len(evaluation),
        curve=curve(evaluation),
        reliability=bins,
        ece=ece if evaluation else None,
        policy="Maximise calibration coverage with observed SER <= 1% and >= 10 commitments; otherwise abstain. Evaluation cases are never used to choose the threshold.",
    )


def summarize(
    rows: list[dict[str, Any]], manifest: dict[str, Any], trials: list[dict[str, Any]]
) -> dict[str, Any]:
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    by_condition: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[(row["model"], row["condition"], row["suite"])].append(row)
        groups[(row["model"], row["condition"], "all")].append(row)
        by_condition[row["condition"]].append(row)
    cells = [
        dict(model=m, condition=c, suite=s, **aggregate(group))
        for (m, c, s), group in sorted(groups.items())
    ]
    comparisons = []
    pooled = []
    for model in sorted({r["model"] for r in rows}):
        lookups: dict[str, dict[tuple[str, str, int], dict[str, Any]]] = defaultdict(dict)
        for row in rows:
            if row["model"] == model and row["outcome"] != "api_error":
                lookups[row["condition"]][(row["case_id"], row["field"], row["repeat"])] = row
        tests = []
        for a, b in itertools.combinations(sorted(lookups), 2):
            keys = sorted(lookups[a].keys() & lookups[b].keys())
            x = [int(lookups[a][k]["outcome"] == "silent_error") for k in keys]
            y = [int(lookups[b][k]["outcome"] == "silent_error") for k in keys]
            tests.append(dict(model=model, a=a, b=b, **paired(x, y)))
        holm(tests)
        comparisons += tests
        if "strict" in lookups and "lenient" in lookups:
            for k in sorted(lookups["strict"].keys() & lookups["lenient"].keys()):
                pooled.append(
                    (
                        k[0],
                        int(lookups["strict"][k]["outcome"] == "silent_error"),
                        int(lookups["lenient"][k]["outcome"] == "silent_error"),
                    )
                )
    effect = cluster_bootstrap(pooled)
    hypotheses = []
    for i in range(1, 9):
        status = "inconclusive"
        detail = "Not enough paired evidence for this pre-specified hypothesis."
        if i == 1 and effect["difference"] is not None:
            lo, hi = effect["ci"]
            status = "supported" if lo > 0 else "rejected" if hi < 0 else "inconclusive"
            detail = "Paired strict minus lenient SER; the length interaction is exploratory."
        hypotheses.append(dict(id=f"H{i}", status=status, detail=detail))
    findings = []
    if effect["difference"] is not None:
        findings.append(
            dict(
                id="paired",
                page="strict-vs-lenient",
                text=f"Strict minus lenient: {effect['difference'] * 100:.2f} percentage points, case-bootstrap 95% interval {effect['ci'][0] * 100:.2f} to {effect['ci'][1] * 100:.2f}.",
            )
        )
    suite_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        suite_groups[row["suite"]].append(row)
    if suite_groups:
        hardest = max(suite_groups, key=lambda s: aggregate(suite_groups[s])["ser"] or 0)
        metric = aggregate(suite_groups[hardest])
        findings.append(
            dict(
                id="hardest",
                page="where-it-breaks",
                text=f"{hardest} has the highest pooled silent error rate: {metric['ser'] * 100:.2f}% across {metric['n']} scored fields.",
            )
        )
    corrupt = sum(r["retry_corruption"] for r in rows)
    findings.append(
        dict(
            id="retry",
            page="retry-lab",
            text=f"{corrupt} retries changed a recoverable correct value into a silent error.",
        )
    )
    offline = []
    for parser, key in [
        ("safe-eu", "safe_eu_outcome"),
        ("safe-no", "safe_no_outcome"),
        ("naive", "naive_outcome"),
    ]:
        selected = [r for r in rows if r[key] is not None]
        n = len(selected)
        errors = sum(r[key] == "silent_error" for r in selected)
        offline.append(
            dict(
                parser=parser,
                n=n,
                silent=errors,
                ser=errors / n if n else None,
                ser_ci=wilson(errors, n),
                loud=sum(r[key].startswith("loud") for r in selected),
            )
        )
    return dict(
        schema_version="1.0",
        run_id=manifest["run_id"],
        fixture=manifest["dry_run"],
        cells=cells,
        conditions=[
            dict(condition=c, **aggregate(group)) for c, group in sorted(by_condition.items())
        ],
        comparisons=comparisons,
        pooled=effect,
        hypotheses=hypotheses,
        findings=findings,
        offline_parsers=offline,
        float_changed=sum(r["float_changed"] for r in rows),
        calibration=calibration(rows),
        error_classes=dict(Counter(r["error_class"] for r in rows if r["error_class"])),
        total_cost_usd=manifest["total_cost_usd"],
        trial_count=len(trials),
        scored_trial_fraction=sum(not t["api_error"] for t in trials if not t["skip_reason"])
        / max(1, sum(not t["skip_reason"] for t in trials)),
        skips=dict(Counter(t["skip_reason"] for t in trials if t["skip_reason"])),
        power_note="A few hundred fields cannot resolve small effects near a 2% base error rate. Intervals spanning zero are inconclusive. Synthetic cases do not estimate production prevalence.",
    )


def score_run(path: Path) -> dict[str, Any]:
    manifest = read_json(path / "manifest.json")
    trials = [json.loads(line) for line in (path / "trials.jsonl").read_text().splitlines()]
    cases = {c["id"]: Case.model_validate(c) for c in read_json(path / "cases.json")}
    rows = field_rows(manifest["run_id"], trials, cases)
    table = pl.DataFrame(rows, infer_schema_length=None)
    table.write_parquet(path / "fields.parquet")
    table.write_csv(path / "fields.csv")
    summary = summarize(rows, manifest, trials)
    write_json(path / "summary.json", summary)
    return summary


def compare_runs(a: Path, b: Path) -> list[dict[str, Any]]:
    old = {
        (c["model"], c["condition"]): c
        for c in read_json(a / "summary.json")["cells"]
        if c["suite"] == "all"
    }
    return [
        dict(
            model=c["model"],
            condition=c["condition"],
            before=old[(c["model"], c["condition"])]["ser"],
            after=c["ser"],
            before_ci=old[(c["model"], c["condition"])]["ser_ci"],
            after_ci=c["ser_ci"],
        )
        for c in read_json(b / "summary.json")["cells"]
        if c["suite"] == "all" and (c["model"], c["condition"]) in old
    ]
