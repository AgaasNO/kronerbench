"""Acceptance is evidence-based; an absent artifact is a failed check."""

import json
import subprocess

from kronerbench.config import ROOT


def check(skip_live: bool = False) -> list[dict[str, object]]:
    checks: list[dict[str, object]] = []

    def item(name: str, passed: bool, detail: str) -> None:
        checks.append({"item": name, "passed": passed, "detail": detail})

    from typer.testing import CliRunner

    from kronerbench.cli import app

    runner = CliRunner()
    commands = [
        [],
        ["doctor"],
        ["models"],
        ["models", "list"],
        ["models", "check"],
        ["cases"],
        ["cases", "build"],
        ["cases", "list"],
        ["cases", "show"],
        ["cases", "audit"],
        ["cases", "stats"],
    ] + [[s] for s in "estimate run score report compare export parse explain selfcheck".split()]
    bad = [
        " ".join(c) or "root"
        for c in commands
        if (r := runner.invoke(app, c + ["--help"])).exit_code != 0 or "Examples" not in r.output
    ]
    item("M1 CLI help", not bad, ", ".join(bad) or "All help pages contain Examples.")
    vectors = ROOT / "tests/parser_vectors.json"
    coverage = ROOT / "coverage.json"
    cov = json.loads(coverage.read_text()) if coverage.exists() else {}
    parser_files = [v for k, v in cov.get("files", {}).items() if "/parsers/" in k]
    complete = bool(parser_files) and all(
        v["summary"]["missing_lines"] == 0 and v["summary"].get("missing_branches", 1) == 0
        for v in parser_files
    )
    item(
        "M2 parsers",
        vectors.exists() and len(json.loads(vectors.read_text())) >= 300 and complete,
        "Need 300 vectors and current 100% line/branch coverage evidence.",
    )
    try:
        from kronerbench.cases.generate import verify_catalogue

        detail = verify_catalogue()
        item("M3 cases", True, detail)
    except (ImportError, ValueError, AssertionError, FileNotFoundError) as e:
        item("M3 cases", False, str(e))
    for name, cmd in [
        ("tests", ["uv", "run", "pytest", "-q"]),
        ("ruff", ["uv", "run", "ruff", "check", "."]),
        ("mypy", ["uv", "run", "mypy"]),
    ]:
        process = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        item(name, process.returncode == 0, (process.stdout + process.stderr)[-1800:])
    for name, path in [
        ("M4 fake pipeline", ".cache/fake-acceptance.json"),
        ("M5 report QA", "docs/img/qa.json"),
    ]:
        p = ROOT / path
        evidence = json.loads(p.read_text()) if p.exists() else {}
        item(name, evidence.get("passed") is True, str(p))
    if not skip_live:
        for name, path in [
            ("M6 case audit", "results/audit.json"),
            ("M7 frozen analysis", "results/analysis-freeze.json"),
            ("M8 published run", "results/published.json"),
            ("M9 README numbers", "results/readme-check.json"),
            ("M10 public repository, CI, Pages and release", "results/publication.json"),
        ]:
            p = ROOT / path
            evidence = json.loads(p.read_text()) if p.exists() else {}
            item(name, evidence.get("passed") is True, str(p))
    return checks
