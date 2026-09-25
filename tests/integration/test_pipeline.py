import json

import jsonschema
import polars as pl

from kronerbench.config import ROOT, read_json, write_json
from kronerbench.runner import scheduler


def test_fake_pipeline(tmp_path, monkeypatch):
    for directory in ["config", "prompts"]:
        (tmp_path / directory).symlink_to(ROOT / directory, target_is_directory=True)
    monkeypatch.setattr(scheduler, "ROOT", tmp_path)
    path = scheduler.run_benchmark(
        dict(profile="standard", dry_run=True, run_id="acceptance", sample=240)
    )
    rows = pl.read_parquet(path / "fields.parquet").to_dicts()
    perfect = [r for r in rows if r["model"] == "fake/perfect"]
    assert perfect and not any(r["outcome"] == "silent_error" for r in perfect)
    dropped = [
        r for r in rows if r["model"] == "fake/digit-dropper" and r["outcome"] == "silent_error"
    ]
    ratio = sum(r["error_class"] == "digit_drop" for r in dropped) / max(1, len(dropped))
    assert dropped and ratio >= 0.9
    assert any(r["retry_corruption"] for r in rows if r["model"] == "fake/retry-corruptor")
    for kind in ["manifest", "summary"]:
        jsonschema.validate(
            read_json(path / f"{kind}.json"), read_json(ROOT / f"schemas/{kind}.json")
        )
    trial_validator = jsonschema.Draft202012Validator(read_json(ROOT / "schemas/trial.json"))
    field_validator = jsonschema.Draft202012Validator(read_json(ROOT / "schemas/field.json"))
    for t in (path / "trials.jsonl").read_text().splitlines():
        trial_validator.validate(json.loads(t))
    for row in rows:
        field_validator.validate(row)
    old = read_json(path / "summary.json")
    from kronerbench.scoring.metrics import score_run

    assert score_run(path) == old
    write_json(
        ROOT / ".cache/fake-acceptance.json",
        dict(passed=True, fields=len(rows), digit_drop_ratio=ratio),
    )
