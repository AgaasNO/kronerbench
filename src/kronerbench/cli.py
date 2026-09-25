"""Human and agent entry point. Network commands always state their cost."""

import json
from pathlib import Path
from typing import Annotated

import typer

from kronerbench.config import ROOT

app = typer.Typer(no_args_is_help=True, help="""KronerBench: do LLMs write wrong money amounts into tool calls?

Compare strict formats with deterministic parsing. Live commands need OPENROUTER_API_KEY.
Examples:
  kronerbench doctor
  kronerbench cases build
  kronerbench run --profile quick
  kronerbench report latest --open

Offline commands cost nothing. Exit codes: 0 ok, 2 usage, 3 credentials,
4 cost cap, 5 selfcheck failures, 6 provider unavailable.
""")
models_app = typer.Typer(help="List and validate models. Examples: kronerbench models list. Listing is free.")
cases_app = typer.Typer(help="Build and audit synthetic cases. Examples: kronerbench cases build. Only audit costs money.")
app.add_typer(models_app, name="models")
app.add_typer(cases_app, name="cases")
Json = Annotated[bool, typer.Option("--json", help="Emit machine-readable JSON. Default: false.")]


def emit(value: object) -> None:
    typer.echo(json.dumps(value, ensure_ascii=False, indent=2, default=str))


@app.command()
def doctor(json: Json = False) -> None:
    """Check credentials, credits and tool support.

    Includes one chat and one Decisions probe, costing a fraction of a cent.
    Examples: kronerbench doctor --json
    """
    from kronerbench.providers.openrouter import doctor as check
    emit(check())


@models_app.command("list")
def models_list(group: str = typer.Option("", help="Filter a model group; empty means all."), json: Json = False) -> None:
    """List configured models without network access. Free.

    Examples: kronerbench models list --group frontier --json
    """
    from kronerbench.providers.openrouter import configured
    emit([m for m in configured() if not group or m["group"] == group])


@models_app.command("check")
def models_check(group: str = typer.Option("", help="Filter a model group; empty means all."), json: Json = False) -> None:
    """Validate model ids, capabilities and live prices. No inference charges.

    Examples: kronerbench models check --json
    """
    import asyncio

    from kronerbench.providers.openrouter import discover
    emit(asyncio.run(discover(group)))


@cases_app.command("build")
def cases_build(seed: int = typer.Option(42, help="Seed for reproducible case generation.")) -> None:
    """Render generated cases and validate the complete catalogue. Free.

    Examples: kronerbench cases build --seed 42
    """
    from kronerbench.cases.generate import build
    emit(build(seed))


@cases_app.command("list")
def cases_list(suite: str = typer.Option("", help="Restrict to one suite; empty means all."), json: Json = False) -> None:
    """List case ids, suites and instructions. Free.

    Examples: kronerbench cases list --suite notation --json
    """
    from kronerbench.cases.model import load_cases
    emit([{"id": c.id, "suite": c.suite, "instruction": c.instruction} for c in load_cases() if not suite or c.suite == suite])


@cases_app.command("show")
def cases_show(case_id: str) -> None:
    """Show source, ground truth and rationale for one case. Free.

    Examples: kronerbench cases show no-formats-0001
    """
    from kronerbench.cases.model import load_cases
    for c in load_cases():
        if c.id == case_id:
            emit(c.model_dump())
            return
    raise typer.BadParameter(f"Unknown case {case_id}; use cases list.")


@cases_app.command("stats")
def cases_stats(json: Json = False) -> None:
    """Summarise the catalogue by suite, fields and flags. Free.

    Examples: kronerbench cases stats --json
    """
    from kronerbench.cases.generate import stats
    emit(stats())


@cases_app.command("audit")
def cases_audit(models: str = typer.Option("anthropic/claude-opus-5.5,openai/gpt-5.6-sol", help="Two independent strong model ids."), max_cost: float = typer.Option(10.0, help="Maximum audit spend in USD.")) -> None:
    """Compare every case with two independent models and write CASE_AUDIT.md.

    Costs money; preserves unresolved disagreements for owner review.
    Examples: kronerbench cases audit --max-cost 10
    """
    from kronerbench.cases.audit import audit
    audit(models.split(","), max_cost)


@app.command()
def parse(value: str, parser: str = typer.Option("safe-eu", help="Reference parser: safe-eu, safe-no, naive, percent or date.")) -> None:
    """Parse one amount, rate or date deterministically. Free.

    Examples: kronerbench parse 'kr 1.234,50-' --parser safe-eu
    """
    from dataclasses import asdict

    from kronerbench.parsers import parse_value
    emit(asdict(parse_value(value, parser)))


@app.command()
def run(
    profile: str = typer.Option("standard", help="quick, standard or full. Full requires --allow-full."),
    models: str = typer.Option("", help="Comma-separated ids or groups; + and - modify profile defaults."),
    conditions: str = typer.Option("", help="Comma-separated condition ids; empty uses the profile."),
    suites: str = typer.Option("", help="Comma-separated suites; empty uses profile suites."),
    cases: str = typer.Option("*", help="Glob selecting case ids."),
    sample: int = typer.Option(0, help="Stratified case count; zero uses the profile."),
    repeats: int = typer.Option(0, help="Trial repeats; zero uses the profile."),
    max_retries: int = typer.Option(2, help="Validator retries per field, excluding the first attempt."),
    error_style: str = typer.Option("neutral", help="neutral or bare validator error messages."),
    prompt_lang: str = typer.Option("en", help="System prompt language, en or no."),
    verify: str = typer.Option("", help="Set jev to verify generative commitments, at extra cost."),
    exacto: bool = typer.Option(False, help="Use OpenRouter :exacto routing and record it."),
    concurrency: int = typer.Option(8, help="Maximum simultaneous cases per model."),
    max_cost: float = typer.Option(75.0, help="USD spending cap; estimate must fit before calls begin."),
    seed: int = typer.Option(42, help="Case ordering, candidate and generation seed."),
    run_id: str = typer.Option("", help="Unique output folder name; empty uses a UTC timestamp."),
    resume: bool = typer.Option(False, help="Resume the named run after verifying its configuration."),
    no_cache: bool = typer.Option(False, help="Bypass response reuse; still store an audit transcript."),
    dry_run: bool = typer.Option(False, help="Use all five deterministic fake models with no API calls."),
    allow_full: bool = typer.Option(False, help="Explicitly approve the optional full profile."),
) -> None:
    """Run paired trials, persist transcripts and score every field.

    Costs money unless --dry-run. Resumable with --run-id and --resume.
    Examples: kronerbench run --profile quick --dry-run --run-id fixture
    """
    from kronerbench.runner.scheduler import run_benchmark
    run_benchmark(dict(locals()))


@app.command()
def estimate(
    profile: str = typer.Option("standard", help="Profile to estimate: quick, standard or full."),
    models: str = typer.Option("", help="Model ids or groups; + and - modify defaults."),
    conditions: str = typer.Option("", help="Condition ids; empty uses the profile."),
    suites: str = typer.Option("", help="Suite ids; empty uses profile defaults."),
    cases: str = typer.Option("*", help="Case-id glob."),
    sample: int = typer.Option(0, help="Case count; zero uses the profile."),
    repeats: int = typer.Option(0, help="Repeat count; zero uses the profile."),
    max_retries: int = typer.Option(2, help="Validator retries included in the conservative upper bound."),
    verify: str = typer.Option("", help="Set jev to include verifier cost."),
    json: Json = False,
) -> None:
    """Project spend from live model prices. No inference charges.

    Includes a conservative request ceiling as well as the expected spend.
    Examples: kronerbench estimate --profile standard --json
    """
    from kronerbench.runner.scheduler import estimate_run
    emit(estimate_run(dict(locals())))


@app.command()
def score(run: str, parsers: str = typer.Option("safe-eu,safe-no,naive,float", help="Offline parser analyses to compute.")) -> None:
    """Re-score stored trials without API calls. Free.

    Examples: kronerbench score latest
    """
    from kronerbench.scoring.metrics import score_run
    emit(score_run(resolve_run(run)))


def resolve_run(name: str) -> Path:
    if name == "latest":
        paths = sorted((ROOT / "runs").glob("*/manifest.json"), key=lambda p: p.stat().st_mtime)
        if not paths:
            raise typer.BadParameter("No stored runs. Run kronerbench run --dry-run first.")
        return paths[-1].parent
    path = ROOT / "runs" / name
    if not path.is_dir():
        raise typer.BadParameter(f"Run {name} does not exist.")
    return path


@app.command()
def report(run: str = "latest", out: str = typer.Option("", help="Output directory; empty uses reports/<run-id>."), open: bool = typer.Option(False, "--open", help="Open the completed report in a browser.")) -> None:
    """Build a self-contained report, including a file:// entry point. Free.

    Examples: kronerbench report latest --open
    """
    from kronerbench.report.build import build_report
    path = build_report(resolve_run(run), Path(out) if out else None)
    typer.echo(str(path))
    if open:
        import webbrowser
        webbrowser.open(path.as_uri())


@app.command()
def compare(a: str, b: str, json: Json = False) -> None:
    """Compare condition-level SER between two stored runs. Free.

    Examples: kronerbench compare baseline updated --json
    """
    from kronerbench.scoring.metrics import compare_runs
    emit(compare_runs(resolve_run(a), resolve_run(b)))


@app.command()
def export(run: str, format: str = typer.Option("csv", help="Output format: csv, jsonl or parquet.")) -> None:
    """Export the scored field table without API calls. Free.

    Examples: kronerbench export latest --format jsonl
    """
    import polars as pl
    path = resolve_run(run)
    table = pl.read_parquet(path / "fields.parquet")
    target = path / f"export.{format}"
    if format == "csv":
        table.write_csv(target)
    elif format == "parquet":
        table.write_parquet(target)
    elif format == "jsonl":
        table.write_ndjson(target)
    else:
        raise typer.BadParameter("Choose csv, jsonl or parquet.")
    typer.echo(str(target))


@app.command()
def explain(case_id: str, run: str = typer.Option("latest", help="Run whose attempts and transcripts to inspect.")) -> None:
    """Show a case, its rationale and all recorded model answers. Free.

    Examples: kronerbench explain no-formats-0001 --run latest
    """
    cases_show(case_id)
    path = resolve_run(run)
    emit([json.loads(line) for line in (path / "trials.jsonl").read_text().splitlines() if json.loads(line)["case_id"] == case_id])


@app.command()
def selfcheck(json: Json = False, skip_live: bool = typer.Option(False, help="Skip checks requiring a published live run and GitHub access.")) -> None:
    """Run the acceptance checklist and name every unmet requirement. Free.

    Exits 5 on any failure. --skip-live is for development and CI.
    Examples: kronerbench selfcheck --skip-live --json
    """
    from kronerbench.selfcheck import check
    result = check(skip_live)
    emit(result)
    raise typer.Exit(0 if all(x["passed"] for x in result) else 5)


if __name__ == "__main__":
    app()
