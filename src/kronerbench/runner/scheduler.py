"""Pair conditions back to back within each shuffled case and model."""

import asyncio
import fnmatch
import importlib.metadata
import json
import platform
import random
import subprocess
from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import typer
import yaml

from kronerbench.cases.model import Case, case_hash, load_cases
from kronerbench.conditions.core import CONDITIONS
from kronerbench.config import ROOT, digest, dumps, read_json, write_json
from kronerbench.providers.cache import Cache
from kronerbench.providers.costguard import CostCap, CostGuard
from kronerbench.providers.fake import FAKES
from kronerbench.providers.openrouter import (
    CredentialsError,
    ProviderError,
    Transport,
    configured,
    discover,
)
from kronerbench.runner.trial import trial
from kronerbench.scoring.metrics import score_run

DEFAULTS = dict(
    profile="standard",
    models="",
    conditions="",
    suites="",
    cases="*",
    sample=0,
    repeats=0,
    max_retries=2,
    error_style="neutral",
    prompt_lang="en",
    verify="",
    exacto=False,
    concurrency=8,
    max_cost=75.0,
    seed=42,
    run_id="",
    resume=False,
    no_cache=False,
    dry_run=False,
    allow_full=False,
)


def git(*args: str) -> str:
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def select_cases(options: dict[str, Any]) -> list[Case]:
    allowed = set(options["suites"].split(",")) if options["suites"] else None
    cases = [
        c
        for c in load_cases()
        if fnmatch.fnmatch(c.id, options["cases"])
        and (
            c.suite in allowed if allowed else options["profile"] == "full" or c.suite != "derived"
        )
    ]
    rng = random.Random(options["seed"])
    rng.shuffle(cases)
    sample = options["sample"]
    if sample and sample < len(cases):
        groups: dict[str, list[Case]] = defaultdict(list)
        for case in cases:
            groups[case.suite].append(case)
        picked: list[Case] = []
        while len(picked) < sample:
            for suite in sorted(groups):
                if groups[suite] and len(picked) < sample:
                    picked.append(groups[suite].pop())
        cases = picked
        rng.shuffle(cases)
    return cases


def plan(
    raw: dict[str, Any], models: list[dict[str, Any]] | None = None
) -> tuple[dict[str, Any], list[Case], list[dict[str, Any]], list[str]]:
    options = {**DEFAULTS, **raw}
    profiles = yaml.safe_load((ROOT / "config/profiles.yaml").read_text())
    if options["profile"] not in profiles:
        raise typer.BadParameter("Choose quick, standard or full.")
    profile = profiles[options["profile"]]
    options["sample"] = options["sample"] or profile["sample"]
    options["repeats"] = options["repeats"] or profile["repeats"]
    if (
        options["repeats"] < 1
        or options["max_retries"] < 0
        or options["concurrency"] < 1
        or options["max_cost"] <= 0
    ):
        raise typer.BadParameter(
            "Repeats, concurrency and cost must be positive; retries cannot be negative."
        )
    if (
        options["prompt_lang"] not in ["en", "no"]
        or options["error_style"] not in ["neutral", "bare"]
        or options["verify"] not in ["", "jev"]
    ):
        raise typer.BadParameter("Invalid prompt language, error style or verifier.")
    conditions = (
        options["conditions"].split(",") if options["conditions"] else profile["conditions"]
    )
    if set(conditions) - set(CONDITIONS):
        raise typer.BadParameter("Unknown condition. Choose " + ",".join(CONDITIONS))
    pool = models or configured()
    selected = [m for m in pool if options["profile"] == "full" or m["group"] != "frontier-xl"]
    if options["profile"] == "quick":
        selected = sorted(
            [m for m in selected if m["group"] != "decision"],
            key=lambda m: sum(
                Decimal(v) for v in m.get("pricing", {"prompt": "1", "completion": "1"}).values()
            ),
        )[:3] + [m for m in selected if m["group"] == "decision"]
    if options["dry_run"]:
        pool = [{"id": name, "group": "fake", "structured_outputs": True} for name in FAKES]
        selected = pool
    tokens = [t for t in options["models"].split(",") if t]
    if tokens:
        if not tokens[0].startswith(("+", "-")):
            selected = []
        for token in tokens:
            selector = token.lstrip("+-")
            matches = [m for m in pool if m["id"] == selector or m["group"] == selector]
            if not matches:
                raise typer.BadParameter(f"Unknown model or group {selector}.")
            if token.startswith("-"):
                selected = [m for m in selected if m not in matches]
            else:
                selected += [m for m in matches if m not in selected]
    cases = select_cases(options)
    if not cases or not selected:
        raise typer.BadParameter("Selectors matched no cases or models.")
    return options, cases, selected, list(conditions)


def projected(
    options: dict[str, Any], cases: list[Case], models: list[dict[str, Any]], conditions: list[str]
) -> dict[str, Any]:
    estimates = []
    for model in models:
        count = (
            sum(len(c.fields) if model["group"] == "decision" else 1 for c in cases)
            * options["repeats"]
            * (1 if model["group"] == "decision" else len(conditions))
        )
        price = model.get("pricing", {"prompt": "0", "completion": "0"})
        # Planning assumptions include schemas, context, tool calls and low reasoning.
        inp, out = 800, 350
        cost = count * (inp * float(price["prompt"]) + out * float(price["completion"])) * 1.15
        estimates.append(
            dict(
                model=model["id"],
                requests=count,
                input_tokens=count * inp,
                output_tokens=count * out,
                expected_usd=cost,
                minutes=count * 2 / max(1, options["concurrency"]) / 60,
            )
        )
    return dict(
        models=estimates,
        expected_usd=sum(m["expected_usd"] for m in estimates),
        case_count=len(cases),
        assumptions="800 input + 350 output tokens per trial, 15% retry allowance; actual cost depends on reasoning and provider. Per-request reservations enforce the cap.",
    )


def estimate_run(raw: dict[str, Any]) -> dict[str, Any]:
    try:
        models = asyncio.run(discover())
    except CredentialsError as e:
        typer.echo(str(e))
        raise typer.Exit(3) from None
    options, cases, selected, conditions = plan(raw, models)
    return projected(options, cases, selected, conditions)


async def execute(
    options: dict[str, Any],
    cases: list[Case],
    models: list[dict[str, Any]],
    conditions: list[str],
    path: Path,
    manifest: dict[str, Any],
) -> None:
    cache = Cache(path / "transcripts.sqlite")
    guard = CostGuard(options["max_cost"], manifest["total_cost_usd"])
    transport = None if options["dry_run"] else Transport(guard)
    completed = set()
    trials_file = path / "trials.jsonl"
    if trials_file.exists():
        for line in trials_file.read_text().splitlines():
            t = json.loads(line)
            completed.add((t["case_id"], t["model"], t["condition"], t["repeat"]))
    semaphores = {m["id"]: asyncio.Semaphore(options["concurrency"]) for m in models}
    locks = asyncio.Lock()
    done = len(completed)

    async def case_job(model: dict[str, Any], case: Case, repeat: int) -> None:
        nonlocal done
        async with semaphores[model["id"]]:
            for condition in ["select"] if model["group"] == "decision" else conditions:
                if (case.id, model["id"], condition, repeat) in completed:
                    continue
                t = await trial(case, model, condition, repeat, options, cache, transport)
                async with locks:
                    with trials_file.open("a") as f:
                        f.write(dumps(t) + "\n")
                        f.flush()
                    manifest["total_cost_usd"] = float(guard.spent)
                    manifest["completed_trials"] = done = done + 1
                    write_json(path / "manifest.json", manifest)
                    if done % 100 == 0:
                        typer.echo(f"{done} trials saved; USD {guard.spent:.4f}")

    tasks = [
        asyncio.create_task(case_job(m, c, r))
        for m in models
        for r in range(options["repeats"])
        for c in cases
    ]
    try:
        await asyncio.gather(*tasks)
        manifest["status"] = "completed"
    except BaseException:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        manifest["status"] = "interrupted"
        raise
    finally:
        manifest["total_cost_usd"] = float(guard.spent)
        manifest["downgrades"] = transport.downgrades if transport else []
        write_json(path / "manifest.json", manifest)
        if transport:
            await transport.close()
        cache.close()


def run_benchmark(raw: dict[str, Any]) -> Path:
    try:
        options = {**DEFAULTS, **raw}
        if options["profile"] == "full" and not options["allow_full"]:
            raise typer.BadParameter("Full is opt-in. Add --allow-full after reviewing estimate.")
        models = None if options["dry_run"] else asyncio.run(discover())
        options, cases, selected, conditions = plan(options, models)
        estimate = projected(options, cases, selected, conditions)
        if estimate["expected_usd"] > options["max_cost"]:
            raise CostCap(
                f"Projected USD {estimate['expected_usd']:.2f} exceeds cap {options['max_cost']:.2f}. Raise --max-cost to approve this run."
            )
        run_id = options["run_id"] or datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        if not all(c.isalnum() or c in "-_" for c in run_id):
            raise typer.BadParameter("Run ids use letters, digits, hyphens and underscores.")
        path = ROOT / "runs" / run_id
        identity = {
            k: v for k, v in options.items() if k not in ["resume", "max_cost", "concurrency"]
        }
        fingerprint = digest([identity, case_hash(cases), selected, conditions])
        if path.exists():
            if not options["resume"]:
                raise typer.BadParameter("Run exists. Use --resume or a new --run-id.")
            manifest = read_json(path / "manifest.json")
            # Dynamic endpoint uptime and price data are not part of trial identity.
            prior = {
                k: v
                for k, v in manifest["arguments"].items()
                if k not in ["resume", "max_cost", "concurrency"]
            }
            if prior != identity or manifest["case_set_hash"] != case_hash(cases):
                raise typer.BadParameter(
                    "Resume configuration or case set differs from the saved manifest."
                )
            selected = manifest["models"]
        else:
            path.mkdir(parents=True)
            manifest = dict(
                schema_version="1.0",
                run_id=run_id,
                created_utc=datetime.now(UTC).isoformat(),
                git_commit=git("rev-parse", "HEAD"),
                analysis_plan_commit=git("log", "-1", "--format=%H", "--", "ANALYSIS_PLAN.md"),
                arguments=options,
                profile=options["profile"],
                seed=options["seed"],
                case_set_hash=case_hash(cases),
                prompt_hashes={
                    str(p.relative_to(ROOT)): digest(p.read_text())
                    for p in (ROOT / "prompts").glob("*/*.md")
                },
                models=selected,
                conditions=conditions,
                case_count=len(cases),
                dry_run=options["dry_run"],
                total_cost_usd=0,
                status="running",
                fingerprint=fingerprint,
                python=platform.python_version(),
                packages={
                    p: importlib.metadata.version(p)
                    for p in ["kronerbench", "httpx", "pydantic", "polars", "scipy"]
                },
            )
            write_json(path / "manifest.json", manifest)
            write_json(path / "cases.json", [c.model_dump() for c in cases])
        if options["verify"]:
            options["verifier_model"] = next(m for m in models or [] if m["group"] == "decision")
        asyncio.run(execute(options, cases, selected, conditions, path, manifest))
        score_run(path)
        typer.echo(f"Saved {path}. Total USD {manifest['total_cost_usd']:.6f}.")
        return path
    except CredentialsError as e:
        typer.echo(str(e))
        raise typer.Exit(3) from None
    except CostCap as e:
        typer.echo(str(e))
        raise typer.Exit(4) from None
    except ProviderError as e:
        typer.echo(str(e))
        raise typer.Exit(6) from None
