import json
from pathlib import Path

from kronerbench.config import ROOT


def test_pilot_readme_numbers_and_budget_have_committed_evidence():
    def read(name):
        return json.loads((ROOT / "results" / name).read_text())

    summary = read("budget-summary.json")
    manifest = read("budget-manifest.json")
    smoke = read("budget-smoke-manifest.json")
    evidence = read("pilot.json")
    readme = (ROOT / "README.md").read_text()
    assert manifest["status"] == smoke["status"] == "completed"
    assert summary["pilot"] and not summary["fixture"]
    assert summary["run_id"] == manifest["run_id"] == evidence["run_id"]
    assert summary["total_cost_usd"] == manifest["total_cost_usd"]
    assert (
        abs(evidence["total_cost_usd"] - manifest["total_cost_usd"] - smoke["total_cost_usd"])
        < 1e-10
    )
    assert evidence["total_cost_usd"] <= evidence["spending_cap_usd"] == 5
    assert evidence["scored_trial_fraction"] == summary["scored_trial_fraction"] >= 0.95
    assert manifest["analysis_plan_commit"] == smoke["analysis_plan_commit"]
    assert len(manifest["analysis_plan_commit"]) == 40
    assert f"USD {evidence['total_cost_usd']:.4f}" in readme
    assert f"releases/tag/{evidence['release_tag']}" in readme
    for finding in summary["findings"]:
        assert finding["text"] in readme
    assert "provisional" in readme.lower()
    assert "TBD" not in readme and "XX%" not in readme
    for name in [
        "verdict-light-1440.png",
        "strict-vs-lenient-light-1440.png",
        "cost-vs-reliability-light-1440.png",
    ]:
        assert (ROOT / "docs/img" / name).exists()
    assert Path("ANALYSIS_PLAN.md").exists()
